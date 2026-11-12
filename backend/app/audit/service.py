"""Tamper-evident audit log writer. Each entry hashes the previous entry's hash in,
so any retroactive edit/delete breaks the chain and is detectable (Section 25)."""

import datetime
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

GENESIS_HASH = "0" * 64


def _compute_entry_hash(prev_hash: str, event_type: str, actor_id: str | None,
                         target_reference: str | None, event_metadata: dict, created_at_iso: str) -> str:
    payload = json.dumps(
        {
            "prev_hash": prev_hash,
            "event_type": event_type,
            "actor_id": actor_id,
            "target_reference": target_reference,
            "event_metadata": event_metadata,
            "created_at": created_at_iso,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_audit_event(
    db: Session,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    target_reference: str | None = None,
    event_metadata: dict | None = None,
) -> AuditLog:
    event_metadata = event_metadata or {}

    last_entry = db.execute(
        select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)
    ).scalar_one_or_none()
    prev_hash = last_entry.entry_hash if last_entry else GENESIS_HASH
    next_seq = (last_entry.seq + 1) if last_entry else 0

    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()
    entry_hash = _compute_entry_hash(
        prev_hash, event_type, str(actor_id) if actor_id else None, target_reference, event_metadata, now_iso
    )

    entry = AuditLog(
        event_type=event_type,
        actor_id=actor_id,
        target_reference=target_reference,
        event_metadata=event_metadata,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=now,
        created_at_iso=now_iso,
        seq=next_seq,
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain_integrity(db: Session) -> bool:
    """Recomputes hashes over the full chain; returns False if any entry was tampered with."""
    entries = db.execute(select(AuditLog).order_by(AuditLog.seq.asc())).scalars().all()
    prev_hash = GENESIS_HASH
    for entry in entries:
        expected = _compute_entry_hash(
            prev_hash,
            entry.event_type,
            str(entry.actor_id) if entry.actor_id else None,
            entry.target_reference,
            entry.event_metadata,
            entry.created_at_iso,
        )
        if entry.prev_hash != prev_hash or entry.entry_hash != expected:
            return False
        prev_hash = entry.entry_hash
    return True
