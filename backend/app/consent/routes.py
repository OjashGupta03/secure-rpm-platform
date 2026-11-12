import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_event
from app.authorization.dependencies import require_role
from app.consent.schemas import ConsentedPatientOut, ConsentGrantRequest, ConsentOut
from app.db.session import get_db
from app.models.consent import Consent, ConsentStatus
from app.models.user import User, UserRole
from app.realtime.registry import registry

router = APIRouter(prefix="/consent", tags=["consent"])


@router.post("", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
def grant_consent(
    payload: ConsentGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient)),
) -> Consent:
    consent = Consent(
        patient_id=current_user.id,
        provider_id=payload.provider_id,
        scope=payload.scope,
        status=ConsentStatus.active,
    )
    db.add(consent)
    write_audit_event(
        db, "CONSENT_GRANTED", actor_id=current_user.id,
        target_reference=str(payload.provider_id),
        event_metadata={"scope": payload.scope},
    )
    db.commit()
    db.refresh(consent)
    return consent


@router.get("", response_model=list[ConsentOut])
def list_my_consents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient)),
) -> list[Consent]:
    return db.execute(
        select(Consent).where(Consent.patient_id == current_user.id)
    ).scalars().all()


@router.get("/my-patients", response_model=list[ConsentedPatientOut])
def list_my_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.provider)),
) -> list[ConsentedPatientOut]:
    rows = db.execute(
        select(Consent, User)
        .join(User, User.id == Consent.patient_id)
        .where(Consent.provider_id == current_user.id, Consent.status == ConsentStatus.active)
    ).all()
    return [
        ConsentedPatientOut(patient_id=user.id, display_name=user.display_name, consent_id=consent.id)
        for consent, user in rows
    ]


@router.delete("/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_consent(
    consent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.patient)),
) -> None:
    consent = db.get(Consent, consent_id)
    if consent is None or consent.patient_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Consent not found")
    if consent.status != ConsentStatus.active:
        return

    consent.status = ConsentStatus.revoked
    consent.revoked_at = datetime.datetime.now(datetime.timezone.utc)
    write_audit_event(
        db, "CONSENT_REVOKED", actor_id=current_user.id,
        target_reference=str(consent.provider_id),
    )
    db.commit()

    # Same request cycle: drop the provider's live view of this patient immediately,
    # not on next reconnect (Section 18/19, 14A.3).
    await registry.revoke_patient_for_provider(consent.provider_id, current_user.id)
