"""In-process Realtime Connection Registry (Section 14A, ADR-002).

Each open SSE connection registers itself here with the set of patient_ids it's
currently authorized to receive events for. Publishers (alert engine, quantum module)
call publish_to_patient(); every connection whose authorized set contains that patient_id
gets the event pushed to its queue.

Consent revocation calls revoke_patient_for_provider(), which removes the patient_id from
every matching connection's authorized set *synchronously*, in the same request cycle that
processes the revocation — not on next reconnect (Section 18/19, 14A.3).

Single-process design, matching ADR-002 (no broker unless the job queue needs one).
"""

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class Connection:
    connection_id: str
    user_id: uuid.UUID
    role: str
    authorized_patient_ids: set[uuid.UUID]
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))


class ConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, Connection] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: Connection) -> None:
        async with self._lock:
            self._connections[conn.connection_id] = conn

    async def unregister(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    def connections_for_user(self, user_id: uuid.UUID) -> list[Connection]:
        return [c for c in self._connections.values() if c.user_id == user_id]

    async def publish_to_patient(self, patient_id: uuid.UUID, event: dict) -> None:
        async with self._lock:
            targets = [c for c in self._connections.values() if patient_id in c.authorized_patient_ids]
        for conn in targets:
            if not conn.queue.full():
                await conn.queue.put(event)

    async def revoke_patient_for_provider(self, provider_id: uuid.UUID, patient_id: uuid.UUID) -> None:
        """Called synchronously from the consent-revocation transaction. Removes the
        patient from every open connection belonging to that provider, immediately."""
        async with self._lock:
            for conn in self._connections.values():
                if conn.user_id == provider_id:
                    conn.authorized_patient_ids.discard(patient_id)
                    await conn.queue.put(
                        {"event": "scope_revoked", "data": {"patient_id": str(patient_id)}}
                    )


registry = ConnectionRegistry()
