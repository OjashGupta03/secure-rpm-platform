import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.schemas import AlertOut, AlertStatusUpdate
from app.audit.service import write_audit_event
from app.authorization.dependencies import require_patient_access, require_role
from app.db.session import get_db
from app.models.alert import Alert, AlertStatus
from app.models.consent import Consent, ConsentStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient, UserRole.provider)),
) -> list[Alert]:
    if current_user.role == UserRole.patient:
        patient_ids = [current_user.id]
    else:
        patient_ids = list(
            db.execute(
                select(Consent.patient_id).where(
                    Consent.provider_id == current_user.id, Consent.status == ConsentStatus.active
                )
            ).scalars().all()
        )
        if not patient_ids:
            return []

    return db.execute(
        select(Alert).where(Alert.patient_id.in_(patient_ids)).order_by(Alert.created_at.desc()).limit(100)
    ).scalars().all()


@router.get("/patient/{patient_id}", response_model=list[AlertOut])
def list_alerts_for_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_patient_access),
) -> list[Alert]:
    return db.execute(
        select(Alert).where(Alert.patient_id == patient_id).order_by(Alert.created_at.desc()).limit(100)
    ).scalars().all()


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert_status(
    alert_id: uuid.UUID,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient, UserRole.provider)),
) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")

    if current_user.role == UserRole.patient and alert.patient_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your alert")
    if current_user.role == UserRole.provider:
        consent = db.execute(
            select(Consent).where(
                Consent.provider_id == current_user.id,
                Consent.patient_id == alert.patient_id,
                Consent.status == ConsentStatus.active,
            )
        ).scalar_one_or_none()
        if consent is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No active consent for this patient")

    try:
        alert.status = AlertStatus(payload.status)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid status")

    write_audit_event(
        db, "ALERT_STATUS_CHANGED", actor_id=current_user.id,
        target_reference=str(alert.id), event_metadata={"status": alert.status.value},
    )
    db.commit()
    db.refresh(alert)
    return alert
