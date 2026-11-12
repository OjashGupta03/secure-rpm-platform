"""Classical baseline AI (Section 8): rolling Z-score + Isolation Forest ensemble.

Fully transparent, deterministic-enough to reproduce, and produces a plain-language
explanation naming the largest-|z| contributing feature. Operates entirely independently
of the quantum module (Section 6) — this is the model that gates alerts in the fast loop.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

MEASUREMENT_TYPES_ORDER = [
    "heart_rate",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
    "body_temperature",
    "blood_glucose",
    "respiratory_rate",
    "weight",
]

MIN_STD = 1e-6
MIN_HISTORY_FOR_BASELINE = 5


@dataclass
class ClassicalScoreResult:
    classical_score: float  # normalized 0..1
    risk_level: str  # normal | watch | elevated | high
    explanation: str
    contributing_features: dict


def _risk_level_from_score(score: float) -> str:
    if score < 0.4:
        return "normal"
    if score < 0.6:
        return "watch"
    if score < 0.8:
        return "elevated"
    return "high"


def score_single_type(
    measurement_type: str, current_value: float, history_values: list[float]
) -> tuple[float, float]:
    """Returns (z_score, normalized_score_0_to_1) for one measurement type."""
    if len(history_values) < MIN_HISTORY_FOR_BASELINE:
        return 0.0, 0.0
    mean = float(np.mean(history_values))
    std = max(float(np.std(history_values)), MIN_STD)
    z = (current_value - mean) / std
    # squash |z| into 0..1 via a capped linear scale (|z|=6 -> 1.0)
    normalized = min(abs(z) / 6.0, 1.0)
    return z, normalized


def score_measurement_window(
    current_type: str,
    current_value: float,
    history_by_type: dict[str, list[float]],
    latest_by_type: dict[str, float],
    model_version: str = "classical-v1",
) -> ClassicalScoreResult:
    """
    history_by_type: {measurement_type: [recent decrypted values, oldest..newest, excluding current]}
    latest_by_type: {measurement_type: most recent decrypted value across all types, for the IF feature vector}
    """
    z_scores: dict[str, float] = {}
    normalized_scores: dict[str, float] = {}

    for mtype in MEASUREMENT_TYPES_ORDER:
        if mtype == current_type:
            z, norm = score_single_type(mtype, current_value, history_by_type.get(mtype, []))
        elif mtype in latest_by_type and mtype in history_by_type:
            z, norm = score_single_type(mtype, latest_by_type[mtype], history_by_type.get(mtype, []))
        else:
            continue
        z_scores[mtype] = z
        normalized_scores[mtype] = norm

    zscore_component = max(normalized_scores.values()) if normalized_scores else 0.0

    # Isolation Forest over the multivariate feature vector, fit on the type's own history
    # as a stand-in "normal" distribution (unsupervised, single-sample scoring).
    if_component = 0.0
    hist_current = history_by_type.get(current_type, [])
    if len(hist_current) >= MIN_HISTORY_FOR_BASELINE:
        X_train = np.array(hist_current).reshape(-1, 1)
        clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        clf.fit(X_train)
        raw_score = clf.decision_function(np.array([[current_value]]))[0]
        # decision_function: higher = more normal. Flip and squash to 0..1.
        if_component = min(max((0.0 - raw_score) * 2.0 + 0.5, 0.0), 1.0)

    classical_score = float(max(zscore_component, if_component))
    risk_level = _risk_level_from_score(classical_score)

    top_feature = max(normalized_scores, key=normalized_scores.get) if normalized_scores else current_type
    top_z = z_scores.get(top_feature, 0.0)
    explanation = (
        f"{top_feature.replace('_', ' ')} deviates {top_z:.2f} standard deviations from this "
        f"patient's rolling baseline (demonstration/configuration threshold, not a medical guideline)."
    )

    return ClassicalScoreResult(
        classical_score=classical_score,
        risk_level=risk_level,
        explanation=explanation,
        contributing_features={"z_scores": z_scores, "isolation_forest_component": if_component},
    )
