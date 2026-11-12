"""Async quantum re-scoring job (slow loop, Section 10). Never runs synchronously inside
a request. Loads pretrained artifacts (see training.py) — training never happens here.

Logs execution metadata only to the audit log, never raw vitals (Section 9A).
"""

import asyncio
import datetime
import functools
import json
import time
import uuid
from pathlib import Path

import numpy as np

from app.ai.quantum.model import QuantumAutoencoder
from app.ai.quantum.rate_limiter import quantum_rate_limiter
from app.audit.service import write_audit_event
from app.config import settings
from app.db.session import SessionLocal
from app.models.ai_prediction import AIPrediction
from app.models.background_job import BackgroundJob, JobStatus
from app.realtime.registry import registry

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MEASUREMENT_TYPES = [
    "heart_rate", "bp_systolic", "bp_diastolic", "spo2",
    "body_temperature", "blood_glucose", "respiratory_rate", "weight",
]

_cached_artifacts: dict | None = None


def _load_artifacts() -> dict:
    global _cached_artifacts
    if _cached_artifacts is not None:
        return _cached_artifacts

    npz = np.load(ARTIFACTS_DIR / "artifacts.npz")
    report = json.loads((ARTIFACTS_DIR / "benchmark_report.json").read_text())

    num_qubits = int(npz["num_qubits"])
    shots = int(npz["shots"])
    model = QuantumAutoencoder(num_qubits=num_qubits, reps=2, shots=min(shots, settings.quantum_max_shots))
    model.load_weights(npz["quantum_weights"])

    _cached_artifacts = {
        "model": model,
        "scaler_mean": npz["scaler_mean"],
        "scaler_scale": npz["scaler_scale"],
        "pca_components": npz["pca_components"],
        "pca_mean": npz["pca_mean"],
        "scale_factor": npz["scale_factor"],
        "evaluation_protocol_version": report["evaluation_protocol_version"],
    }
    return _cached_artifacts


def _prepare_input(feature_vector: dict[str, float], artifacts: dict) -> np.ndarray:
    row = np.array([[feature_vector.get(t, 0.0) for t in MEASUREMENT_TYPES]])
    scaled = (row - artifacts["scaler_mean"]) / artifacts["scaler_scale"]
    reduced = (scaled - artifacts["pca_mean"]) @ artifacts["pca_components"].T
    return reduced * artifacts["scale_factor"]


def _run_inference_sync(feature_vector: dict[str, float]) -> tuple[float, dict]:
    artifacts = _load_artifacts()
    model: QuantumAutoencoder = artifacts["model"]
    X = _prepare_input(feature_vector, artifacts)
    err = float(model.reconstruction_error(X)[0])
    # Squash reconstruction error into a 0..1 score; threshold tuned against the
    # training-time benchmark, not a clinical value.
    quantum_score = float(min(err / 2.0, 1.0))
    cost = model.cost_metadata(wall_clock_seconds=0.0)
    return quantum_score, {
        "qubit_count": cost.qubit_count,
        "shot_count": cost.shot_count,
        "circuit_depth": cost.circuit_depth,
        "circuit_hash": cost.circuit_hash,
    }


async def run_quantum_rescore_job(
    patient_id: uuid.UUID,
    measurement_id: uuid.UUID,
    ai_prediction_id: uuid.UUID,
    feature_vector: dict[str, float],
) -> None:
    if not quantum_rate_limiter.allow(patient_id):
        return  # silently dropped; classical score already stands on its own (Section 6)

    db = SessionLocal()
    job = BackgroundJob(job_type="quantum_rescore", status=JobStatus.running)
    db.add(job)
    db.commit()
    db.refresh(job)

    write_audit_event(
        db, "QUANTUM_JOB_SUBMITTED",
        target_reference=str(measurement_id),
        event_metadata={"job_id": str(job.id), "qubit_budget": settings.quantum_max_qubits},
    )
    db.commit()

    t0 = time.monotonic()
    try:
        loop = asyncio.get_running_loop()
        quantum_score, job_meta = await asyncio.wait_for(
            loop.run_in_executor(None, functools.partial(_run_inference_sync, feature_vector)),
            timeout=settings.quantum_job_timeout_seconds,
        )
        job_meta["wall_clock_seconds"] = round(time.monotonic() - t0, 3)

        prediction = db.get(AIPrediction, ai_prediction_id)
        if prediction is not None:
            prediction.quantum_score = quantum_score
            prediction.combined_score = float((prediction.classical_score + quantum_score) / 2)
            prediction.evaluation_protocol_version = _load_artifacts()["evaluation_protocol_version"]

        job.status = JobStatus.completed
        job.result_reference = str(ai_prediction_id)

        write_audit_event(
            db, "QUANTUM_JOB_COMPLETED",
            target_reference=str(measurement_id),
            event_metadata={"job_id": str(job.id), **job_meta},
        )
        db.commit()

        await registry.publish_to_patient(
            patient_id,
            {
                "event": "quantum_rescore_available",
                "data": {"measurement_id": str(measurement_id), "ai_prediction_id": str(ai_prediction_id)},
            },
        )
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001 — job failures must not crash the app
        job.status = JobStatus.failed
        write_audit_event(
            db, "QUANTUM_JOB_COMPLETED",
            target_reference=str(measurement_id),
            event_metadata={"job_id": str(job.id), "error": type(exc).__name__},
        )
        db.commit()
    finally:
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        db.close()
