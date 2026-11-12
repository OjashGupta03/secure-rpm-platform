"""Offline training + mandatory benchmarking (Section 9.3). Run this as a script, not
inside a request. Produces artifacts/ (pca + scaler + trained weights + metadata) and a
benchmark report. Training happens once; the async job runner only does inference.

Usage: python -m app.ai.quantum.training
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "database" / "synthetic_data" / "vitals_generator"))
from generator import AnomalyType, Persona, VitalsGenerator  # noqa: E402

from app.ai.quantum.classical_control import ClassicalControlModel, choose_matching_rank
from app.ai.quantum.model import QuantumAutoencoder

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
EVAL_PROTOCOL_VERSION = "eval-protocol-v1-2026-08-24"
MEASUREMENT_TYPES = [
    "heart_rate", "bp_systolic", "bp_diastolic", "spo2",
    "body_temperature", "blood_glucose", "respiratory_rate", "weight",
]


def _build_dataset(seed: int, n_windows: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """Generates feature vectors (one per time window, one value per measurement type)
    and binary anomaly labels from the synthetic generator, for benchmarking only."""
    gen = VitalsGenerator(Persona.normotensive_adult, seed=seed, anomaly_rate=0.15)
    import datetime
    start = datetime.datetime.now(datetime.timezone.utc)
    measurements = gen.generate_window(start, count=n_windows, interval_seconds=120)

    by_ts: dict = {}
    for m in measurements:
        by_ts.setdefault(m.recorded_at, {})[m.measurement_type] = (m.value, m.anomaly_label)

    X, y = [], []
    for ts, values in by_ts.items():
        if len(values) != len(MEASUREMENT_TYPES):
            continue  # dropout window, skip for benchmarking dataset
        row = [values[t][0] for t in MEASUREMENT_TYPES]
        if any(v is None for v in row):
            continue
        is_anomaly = any(values[t][1] != AnomalyType.none for t in MEASUREMENT_TYPES)
        X.append(row)
        y.append(1 if is_anomaly else 0)
    return np.array(X), np.array(y)


def train_and_benchmark(num_qubits: int = 6, shots: int = 1024, k_folds: int = 5) -> dict:
    ARTIFACTS_DIR.mkdir(exist_ok=True)

    X, y = _build_dataset(seed=42)
    X_normal = X[y == 0]

    scaler = StandardScaler().fit(X_normal)
    X_scaled = scaler.transform(X)
    X_normal_scaled = scaler.transform(X_normal)

    pca = PCA(n_components=num_qubits, random_state=42).fit(X_normal_scaled)
    X_reduced = pca.transform(X_scaled)
    X_normal_reduced = pca.transform(X_normal_scaled)

    # Angle-encoding expects roughly [-pi, pi]; squash PCA output accordingly.
    scale_factor = np.pi / (np.abs(X_normal_reduced).max() + 1e-6)
    X_reduced_angles = X_reduced * scale_factor
    X_normal_angles = X_normal_reduced * scale_factor

    quantum_model = QuantumAutoencoder(num_qubits=num_qubits, reps=2, shots=shots)
    t0 = time.time()
    from scipy.optimize import minimize

    def q_loss(flat_w: np.ndarray) -> float:
        return float(np.mean(quantum_model.reconstruction_error(X_normal_angles, flat_w)))

    x0 = np.random.default_rng(42).normal(scale=0.1, size=quantum_model.num_parameters)
    result = minimize(q_loss, x0, method="COBYLA", options={"maxiter": 150})
    quantum_model.load_weights(result.x)
    quantum_train_seconds = time.time() - t0

    classical_rank = choose_matching_rank(num_qubits, quantum_model.num_parameters)
    classical_model = ClassicalControlModel(num_features=num_qubits, rank=classical_rank)
    t0 = time.time()
    classical_model.fit(X_normal_angles, max_iter=150)
    classical_train_seconds = time.time() - t0

    # --- Mandatory benchmarking protocol (Section 9.3): k-fold CV, both models,
    # reconstruction-error-as-anomaly-score AUC, paired significance test. ---
    kf = KFold(n_splits=k_folds, shuffle=True, random_state=42)
    quantum_aucs, classical_aucs = [], []
    for _, test_idx in kf.split(X_reduced_angles):
        X_test, y_test = X_reduced_angles[test_idx], y[test_idx]
        if len(set(y_test)) < 2:
            continue
        q_scores = quantum_model.reconstruction_error(X_test)
        c_scores = classical_model.reconstruction_error(X_test)
        quantum_aucs.append(roc_auc_score(y_test, q_scores))
        classical_aucs.append(roc_auc_score(y_test, c_scores))

    t_stat, p_value = stats.ttest_rel(quantum_aucs, classical_aucs) if len(quantum_aucs) > 1 else (0.0, 1.0)
    significant = bool(p_value < 0.05)

    report = {
        "evaluation_protocol_version": EVAL_PROTOCOL_VERSION,
        "num_qubits": num_qubits,
        "shots": shots,
        "quantum_num_parameters": quantum_model.num_parameters,
        "classical_num_parameters": classical_model.num_parameters,
        "k_folds": k_folds,
        "quantum_auc_mean": float(np.mean(quantum_aucs)) if quantum_aucs else None,
        "quantum_auc_ci95": float(1.96 * np.std(quantum_aucs) / max(len(quantum_aucs), 1) ** 0.5) if quantum_aucs else None,
        "classical_auc_mean": float(np.mean(classical_aucs)) if classical_aucs else None,
        "classical_auc_ci95": float(1.96 * np.std(classical_aucs) / max(len(classical_aucs), 1) ** 0.5) if classical_aucs else None,
        "paired_ttest_statistic": float(t_stat),
        "paired_ttest_p_value": float(p_value),
        "quantum_advantage_statistically_significant": significant,
        "quantum_train_wall_clock_seconds": quantum_train_seconds,
        "classical_train_wall_clock_seconds": classical_train_seconds,
        "note": (
            "Any observed AUC difference is an experimental finding scoped to this "
            "prototype's synthetic data, not a general claim of quantum advantage."
        ),
    }

    np.savez(
        ARTIFACTS_DIR / "artifacts.npz",
        scaler_mean=scaler.mean_, scaler_scale=scaler.scale_,
        pca_components=pca.components_, pca_mean=pca.mean_,
        scale_factor=scale_factor,
        quantum_weights=quantum_model.trained_weights,
        classical_weights=classical_model.weights,
        classical_rank=classical_rank,
        num_qubits=num_qubits, shots=shots,
    )
    (ARTIFACTS_DIR / "benchmark_report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    r = train_and_benchmark()
    print(json.dumps(r, indent=2))
