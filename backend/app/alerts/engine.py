"""Alert engine (Section 28). Triggers directly off the classical baseline — the fast
loop never waits on the quantum module (Section 6, 10, 14A)."""

from app.ai.classical.scorer import ClassicalScoreResult
from app.audit.service import write_audit_event
from app.models.ai_prediction import AIPrediction, RiskLevel
from app.models.alert import Alert, AlertSeverity
from app.models.measurement import Measurement
from app.realtime.registry import registry

_RISK_TO_SEVERITY = {
    RiskLevel.elevated: AlertSeverity.medium,
    RiskLevel.high: AlertSeverity.high,
}


def should_alert(risk_level: RiskLevel) -> bool:
    return risk_level in _RISK_TO_SEVERITY


async def create_alert_and_notify(
    db, measurement: Measurement, prediction: AIPrediction, score: ClassicalScoreResult
) -> Alert | None:
    if not should_alert(prediction.risk_level):
        return None

    alert = Alert(
        patient_id=measurement.patient_id,
        measurement_id=measurement.id,
        ai_prediction_id=prediction.id,
        severity=_RISK_TO_SEVERITY[prediction.risk_level],
        message=score.explanation,
    )
    db.add(alert)
    db.flush()
    db.refresh(alert)

    write_audit_event(
        db, "ALERT_CREATED",
        target_reference=str(alert.id),
        event_metadata={"patient_id": str(measurement.patient_id), "severity": alert.severity.value},
    )

    # Minimal push payload — id/severity/timestamp only, never raw vitals (Section 14A.2, 23).
    await registry.publish_to_patient(
        measurement.patient_id,
        {
            "event": "new_alert",
            "data": {
                "alert_id": str(alert.id),
                "patient_id": str(measurement.patient_id),
                "severity": alert.severity.value,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            },
        },
    )
    return alert
