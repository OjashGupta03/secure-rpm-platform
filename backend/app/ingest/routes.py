import asyncio
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.classical.scorer import score_measurement_window
from app.ai.quantum.job_runner import run_quantum_rescore_job
from app.alerts.engine import create_alert_and_notify
from app.audit.service import write_audit_event
from app.authorization.dependencies import require_patient_access, require_role
from app.core.crypto import decrypt_value, encrypt_value
from app.db.session import get_db
from app.ingest.schemas import AnalysisOut, MeasurementCreate, MeasurementOut
from app.ingest.validation import UNITS, is_within_valid_range
from app.models.ai_prediction import AIPrediction, RiskLevel
from app.models.measurement import Measurement, MeasurementSource, MeasurementType
from app.models.user import User, UserRole

router = APIRouter(prefix="/measurements", tags=["measurements"])

HISTORY_WINDOW_SIZE = 20


def _predictions_by_measurement_id(db: Session, measurement_ids: list) -> dict:
    if not measurement_ids:
        return {}
    rows = db.execute(
        select(AIPrediction).where(AIPrediction.input_reference.in_(measurement_ids))
    ).scalars().all()
    return {p.input_reference: p for p in rows}


def _measurement_out(m: Measurement, prediction: AIPrediction | None) -> MeasurementOut:
    analysis = None
    if prediction is not None:
        analysis = AnalysisOut(
            classical_score=prediction.classical_score,
            quantum_score=prediction.quantum_score,
            combined_score=prediction.combined_score,
            risk_level=prediction.risk_level,
            explanation=prediction.explanation,
            contributing_features=prediction.contributing_features,
            evaluation_protocol_version=prediction.evaluation_protocol_version,
        )
    return MeasurementOut(
        id=m.id,
        measurement_type=m.measurement_type,
        value=float(decrypt_value(m.encrypted_value)),
        unit=m.unit,
        source=m.source.value,
        recorded_at=m.recorded_at,
        data_label=m.data_label,
        analysis=analysis,
    )


def _history_for_patient(db: Session, patient_id, exclude_id=None) -> dict[str, list[float]]:
    rows = db.execute(
        select(Measurement)
        .where(Measurement.patient_id == patient_id)
        .order_by(Measurement.recorded_at.desc())
        .limit(500)
    ).scalars().all()

    by_type: dict[str, list[float]] = {}
    latest_by_type: dict[str, float] = {}
    for m in rows:
        if exclude_id is not None and m.id == exclude_id:
            continue
        val = decrypt_value(m.encrypted_value)
        by_type.setdefault(m.measurement_type.value, [])
        if len(by_type[m.measurement_type.value]) < HISTORY_WINDOW_SIZE:
            by_type[m.measurement_type.value].append(float(val))
        latest_by_type.setdefault(m.measurement_type.value, float(val))
    # oldest..newest for the scorer
    for k in by_type:
        by_type[k].reverse()
    return by_type, latest_by_type


async def _ingest_measurement(
    db: Session, patient_id, payload: MeasurementCreate, source: MeasurementSource
) -> MeasurementOut:
    if not is_within_valid_range(payload.measurement_type, payload.value):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Value outside plausible range")

    recorded_at = payload.recorded_at or datetime.datetime.now(datetime.timezone.utc)
    measurement = Measurement(
        patient_id=patient_id,
        measurement_type=payload.measurement_type,
        encrypted_value=encrypt_value(str(payload.value)),
        unit=UNITS[payload.measurement_type],
        source=source,
        recorded_at=recorded_at,
    )
    db.add(measurement)
    db.flush()
    db.refresh(measurement)

    history_by_type, latest_by_type = _history_for_patient(db, patient_id, exclude_id=measurement.id)
    score = score_measurement_window(
        current_type=payload.measurement_type.value,
        current_value=payload.value,
        history_by_type=history_by_type,
        latest_by_type=latest_by_type,
    )

    prediction = AIPrediction(
        patient_id=patient_id,
        input_reference=measurement.id,
        model_version="classical-v1",
        classical_score=score.classical_score,
        risk_level=RiskLevel(score.risk_level),
        explanation=score.explanation,
        contributing_features=score.contributing_features,
    )
    db.add(prediction)
    db.flush()
    db.refresh(prediction)

    await create_alert_and_notify(db, measurement, prediction, score)

    write_audit_event(
        db, "MEASUREMENT_INGESTED",
        actor_id=patient_id,
        target_reference=str(measurement.id),
        event_metadata={"measurement_type": payload.measurement_type.value, "source": source.value},
    )
    db.commit()

    # Slow loop: fire-and-forget async quantum re-score, never blocks this response.
    latest_by_type[payload.measurement_type.value] = payload.value
    asyncio.create_task(
        run_quantum_rescore_job(patient_id, measurement.id, prediction.id, latest_by_type)
    )

    return _measurement_out(measurement, prediction)


@router.post("", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
async def submit_measurement(
    payload: MeasurementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient)),
) -> MeasurementOut:
    return await _ingest_measurement(db, current_user.id, payload, MeasurementSource.manual_entry)


@router.get("", response_model=list[MeasurementOut])
def list_measurements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient)),
    limit: int = 50,
) -> list[MeasurementOut]:
    rows = db.execute(
        select(Measurement)
        .where(Measurement.patient_id == current_user.id)
        .order_by(Measurement.recorded_at.desc())
        .limit(min(limit, 200))
    ).scalars().all()

    predictions = _predictions_by_measurement_id(db, [m.id for m in rows])
    return [_measurement_out(m, predictions.get(m.id)) for m in rows]


@router.get("/patient/{patient_id}", response_model=list[MeasurementOut])
def list_measurements_for_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_patient_access),
    limit: int = 50,
) -> list[MeasurementOut]:
    rows = db.execute(
        select(Measurement)
        .where(Measurement.patient_id == patient_id)
        .order_by(Measurement.recorded_at.desc())
        .limit(min(limit, 200))
    ).scalars().all()

    predictions = _predictions_by_measurement_id(db, [m.id for m in rows])
    return [_measurement_out(m, predictions.get(m.id)) for m in rows]


@router.get("/{measurement_id}/analysis", response_model=AnalysisOut)
def get_analysis(
    measurement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient)),
) -> AnalysisOut:
    measurement = db.get(Measurement, measurement_id)
    if measurement is None or measurement.patient_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Measurement not found")

    prediction = db.execute(
        select(AIPrediction).where(AIPrediction.input_reference == measurement_id)
    ).scalar_one_or_none()
    if prediction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not yet available")

    return AnalysisOut(
        classical_score=prediction.classical_score,
        quantum_score=prediction.quantum_score,
        combined_score=prediction.combined_score,
        risk_level=prediction.risk_level,
        explanation=prediction.explanation,
        contributing_features=prediction.contributing_features,
        evaluation_protocol_version=prediction.evaluation_protocol_version,
    )
