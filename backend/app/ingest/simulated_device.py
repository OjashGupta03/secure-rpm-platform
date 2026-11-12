"""Simulated device ingest loop (Section 14A.1 — 'both' manual entry and simulated
device stream). Mimics a continuous wearable's ~2-minute cadence (Section 37.1) for
any patient who has opted in via PATCH /auth/me/device.
"""

import asyncio
import datetime
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "database" / "synthetic_data" / "vitals_generator"))
from generator import Persona, VitalsGenerator  # noqa: E402

from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.ingest.schemas import MeasurementCreate
from app.models.measurement import MeasurementSource, MeasurementType
from app.models.user import User

logger = logging.getLogger("rpm.simulated_device")

_call_counters: dict = {}


async def _generate_and_ingest_for_patient(patient: User) -> None:
    from app.ingest.routes import _ingest_measurement  # local import avoids a circular import

    db = SessionLocal()
    try:
        count = _call_counters.get(patient.id, 0)
        _call_counters[patient.id] = count + 1
        try:
            persona = Persona(patient.synthetic_persona)
        except ValueError:
            persona = Persona.normotensive_adult

        gen = VitalsGenerator(persona, seed=settings.synthetic_data_seed + count, anomaly_rate=0.08)
        window = gen.generate_window(datetime.datetime.now(datetime.timezone.utc), count=1, interval_seconds=1)

        for m in window:
            if m.value is None:
                continue  # dropout — nothing to ingest this cycle for that type
            payload = MeasurementCreate(
                measurement_type=MeasurementType(m.measurement_type),
                value=m.value,
                recorded_at=m.recorded_at,
            )
            await _ingest_measurement(db, patient.id, payload, MeasurementSource.simulated_device)
    except Exception:  # noqa: BLE001 — one patient's failure must not stop the loop
        logger.exception("Simulated device ingest failed for patient %s", patient.id)
    finally:
        db.close()


async def simulated_device_loop() -> None:
    while True:
        await asyncio.sleep(settings.synthetic_device_interval_seconds)
        db = SessionLocal()
        try:
            patients = db.execute(
                select(User).where(User.simulated_device_enabled.is_(True))
            ).scalars().all()
        finally:
            db.close()

        for patient in patients:
            asyncio.create_task(_generate_and_ingest_for_patient(patient))
