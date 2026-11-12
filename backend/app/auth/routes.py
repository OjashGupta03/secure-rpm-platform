import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_event
from app.auth.dependencies import get_current_session, get_current_user
from app.auth.schemas import (
    DeviceSettingsUpdate,
    LoginRequest,
    ProviderDirectoryEntry,
    RegisterRequest,
    UserOut,
)
from app.authorization.dependencies import require_role
from app.config import settings
from app.core.security import generate_session_token, hash_password, verify_password
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit_event(db, "USER_REGISTERED", actor_id=user.id, target_reference=str(user.id))
    db.commit()
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password) or not user.is_active:
        # Deliberately generic error — do not reveal whether the email exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    raw_token, token_hash = generate_session_token()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.session_ttl_minutes
    )
    session = AuthSession(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(session)
    write_audit_event(db, "USER_LOGIN", actor_id=user.id)
    db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    session_data: tuple[User, AuthSession] = Depends(get_current_session),
) -> None:
    current_user, session = session_data
    session.revoked_at = datetime.datetime.now(datetime.timezone.utc)
    write_audit_event(db, "USER_LOGOUT", actor_id=current_user.id)
    db.commit()
    response.delete_cookie(settings.session_cookie_name)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/providers", response_model=list[ProviderDirectoryEntry])
def list_providers(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.patient)),
) -> list[User]:
    """Minimal directory lookup so a patient can find a provider's id to grant consent
    to. Deliberately provider-only (not full user search) to limit exposure."""
    return db.execute(select(User).where(User.role == UserRole.provider)).scalars().all()


@router.patch("/me/device", response_model=UserOut)
def update_device_settings(
    payload: DeviceSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.patient:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only patients have a simulated device stream")
    current_user.simulated_device_enabled = payload.simulated_device_enabled
    current_user.synthetic_persona = payload.synthetic_persona
    write_audit_event(
        db, "DEVICE_SETTINGS_UPDATED", actor_id=current_user.id,
        event_metadata={"enabled": payload.simulated_device_enabled, "persona": payload.synthetic_persona},
    )
    db.commit()
    db.refresh(current_user)
    return current_user
