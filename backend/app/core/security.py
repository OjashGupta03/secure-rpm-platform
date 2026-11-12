"""Password hashing (Argon2id) and server-side session token handling (Section 15-17)."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def generate_session_token() -> tuple[str, str]:
    """Returns (raw_token_for_cookie, sha256_hash_for_db_storage).

    Only the hash is ever persisted, so a DB leak does not yield usable session tokens
    (same principle as password-reset tokens).
    """
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, token_hash


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
