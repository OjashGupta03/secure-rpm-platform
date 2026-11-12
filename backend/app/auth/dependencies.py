import datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_session_token
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.user import User


def get_current_session(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> tuple[User, AuthSession]:
    raw_token = session_token
    if raw_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    token_hash = hash_session_token(raw_token)
    session = db.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    ).scalar_one_or_none()

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = session.expires_at if session else None
    # Some DB backends (e.g. SQLite, used in local/dev testing) drop tzinfo on round-trip
    # through DateTime(timezone=True); Postgres (the deployed target) does not. Normalize
    # defensively so the comparison below is correct on either backend.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

    if (
        session is None
        or session.revoked_at is not None
        or expires_at < now
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")

    return user, session


def get_current_user(
    session_data: tuple[User, AuthSession] = Depends(get_current_session),
) -> User:
    return session_data[0]
