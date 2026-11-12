"""Seeds one demo patient, one demo provider (with consent granted), and an admin —
plus a few days of synthetic vitals history for the patient. SYNTHETIC / DEMO DATA ONLY.

Usage (from backend/): python -m scripts.seed_demo
"""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "database" / "synthetic_data" / "vitals_generator"))
from generator import Persona, generate_patient_history  # noqa: E402

from app.core.crypto import encrypt_value
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.consent import Consent, ConsentStatus
from app.models.measurement import Measurement, MeasurementSource, MeasurementType
from app.models.user import User, UserRole


def run() -> None:
    db = SessionLocal()
    try:
        patient = User(
            email="demo.patient@example.com",
            hashed_password=hash_password("DemoPatient123!"),
            role=UserRole.patient,
            display_name="Demo Patient",
            synthetic_persona=Persona.normotensive_adult.value,
        )
        provider = User(
            email="demo.provider@example.com",
            hashed_password=hash_password("DemoProvider123!"),
            role=UserRole.provider,
            display_name="Dr. Demo Provider",
        )
        admin = User(
            email="demo.admin@example.com",
            hashed_password=hash_password("DemoAdmin123!"),
            role=UserRole.admin,
            display_name="Demo Admin",
        )
        db.add_all([patient, provider, admin])
        db.flush()

        db.add(Consent(patient_id=patient.id, provider_id=provider.id, status=ConsentStatus.active))

        history = generate_patient_history(Persona.normotensive_adult, seed=42, days=2, interval_seconds=120)
        for m in history:
            if m.value is None:
                continue
            db.add(
                Measurement(
                    patient_id=patient.id,
                    measurement_type=MeasurementType(m.measurement_type),
                    encrypted_value=encrypt_value(str(m.value)),
                    unit=m.unit,
                    source=MeasurementSource.simulated_device,
                    recorded_at=m.recorded_at,
                )
            )

        db.commit()
        print("Seeded demo users:")
        print("  patient:  demo.patient@example.com  / DemoPatient123!")
        print("  provider: demo.provider@example.com / DemoProvider123!")
        print("  admin:    demo.admin@example.com    / DemoAdmin123!")
        print(f"  + {len(history)} synthetic historical measurements for the patient")
    finally:
        db.close()


if __name__ == "__main__":
    run()
