import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.consent import Consent, ConsentStatus
from app.models.user import User, UserRole


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this resource")
        return current_user

    return _dependency


def has_active_consent(db: Session, provider_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
    consent = db.execute(
        select(Consent).where(
            Consent.provider_id == provider_id,
            Consent.patient_id == patient_id,
            Consent.status == ConsentStatus.active,
        )
    ).scalar_one_or_none()
    return consent is not None


def require_patient_access(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Backend-enforced resource authorization: patients see only their own data;
    providers only see patients with active consent; admins get no default health-data
    access. `patient_id` is bound by FastAPI from the route's own {patient_id} path
    parameter — this must only be used with `Depends(require_patient_access)` (no call)
    on a route whose path includes {patient_id}."""
    if current_user.role == UserRole.patient:
        if current_user.id != patient_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot access another patient's data")
        return current_user
    if current_user.role == UserRole.provider:
        if not has_active_consent(db, current_user.id, patient_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No active consent for this patient")
        return current_user
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrators have no default health-data access")
