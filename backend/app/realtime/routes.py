import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.audit.service import write_audit_event
from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.session import get_db
from app.models.consent import Consent, ConsentStatus
from app.models.user import User, UserRole
from app.realtime.registry import Connection, registry

router = APIRouter(prefix="/realtime", tags=["realtime"])

HEARTBEAT_SECONDS = 15


def _authorized_patient_ids(db: Session, user: User) -> set[uuid.UUID]:
    if user.role == UserRole.patient:
        return {user.id}
    if user.role == UserRole.provider:
        rows = db.execute(
            select(Consent.patient_id).where(
                Consent.provider_id == user.id, Consent.status == ConsentStatus.active
            )
        ).scalars().all()
        return set(rows)
    return set()  # admins: no default health-data access, no events


@router.get("/stream")
async def stream(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    existing = registry.connections_for_user(current_user.id)
    if len(existing) >= settings.realtime_max_connections_per_user:
        write_audit_event(
            db, "REALTIME_CONNECTION_REJECTED", actor_id=current_user.id,
            event_metadata={"reason": "max_connections_exceeded"},
        )
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many open realtime connections")

    authorized = _authorized_patient_ids(db, current_user)
    connection_id = str(uuid.uuid4())
    conn = Connection(
        connection_id=connection_id,
        user_id=current_user.id,
        role=current_user.role.value,
        authorized_patient_ids=authorized,
    )
    await registry.register(conn)
    write_audit_event(
        db, "REALTIME_CONNECTION_OPENED", actor_id=current_user.id,
        event_metadata={"connection_id": connection_id, "authorized_patient_count": len(authorized)},
    )
    db.commit()

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(conn.queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"event: {event.get('event', 'message')}\ndata: {json.dumps(event.get('data', {}))}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await registry.unregister(connection_id)
            db2_gen = get_db()
            db2 = next(db2_gen)
            try:
                write_audit_event(
                    db2, "REALTIME_CONNECTION_CLOSED", actor_id=current_user.id,
                    event_metadata={"connection_id": connection_id},
                )
                db2.commit()
            finally:
                db2_gen.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
