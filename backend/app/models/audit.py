import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Realtime + quantum audit event type constants (Section 9A, 26)
REALTIME_CONNECTION_OPENED = "REALTIME_CONNECTION_OPENED"
REALTIME_CONNECTION_CLOSED = "REALTIME_CONNECTION_CLOSED"
REALTIME_CONNECTION_REJECTED = "REALTIME_CONNECTION_REJECTED"
QUANTUM_JOB_SUBMITTED = "QUANTUM_JOB_SUBMITTED"
QUANTUM_JOB_COMPLETED = "QUANTUM_JOB_COMPLETED"
CONSENT_GRANTED = "CONSENT_GRANTED"
CONSENT_REVOKED = "CONSENT_REVOKED"


class AuditLog(Base):
    """Append-only, hash-chained audit log. Never stores raw health payloads —
    only event metadata and references (Section 9A, 24-26)."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Application-level (not DB-autoincrement) monotonic sequence: chain order must be
    # unambiguous even when two writes share a created_at timestamp, which DB timestamp
    # resolution does not rule out. Computed in app.audit.service as
    # (previous entry's seq + 1), the same single-writer read-then-write pattern already
    # used for prev_hash chaining, and portable across SQLite (dev/test) and Postgres
    # (deployment) without relying on backend-specific autoincrement/Identity semantics.
    seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    target_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Exact ISO-8601 string that was hashed into entry_hash. Kept as its own plain string
    # column (rather than re-deriving from `created_at`) because DateTime round-trips
    # through some DB backends (e.g. SQLite) can silently drop tzinfo, which would make
    # chain verification recompute a different hash than was originally signed.
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
