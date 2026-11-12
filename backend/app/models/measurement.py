import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class MeasurementType(str, enum.Enum):
    heart_rate = "heart_rate"
    bp_systolic = "bp_systolic"
    bp_diastolic = "bp_diastolic"
    spo2 = "spo2"
    body_temperature = "body_temperature"
    blood_glucose = "blood_glucose"
    respiratory_rate = "respiratory_rate"
    weight = "weight"


class MeasurementSource(str, enum.Enum):
    manual_entry = "manual_entry"
    simulated_device = "simulated_device"


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    measurement_type: Mapped[MeasurementType] = mapped_column(Enum(MeasurementType), nullable=False)
    # AES-256-GCM encrypted value (nonce || ciphertext); decrypted only in the service layer.
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[MeasurementSource] = mapped_column(Enum(MeasurementSource), nullable=False)
    data_label: Mapped[str] = mapped_column(String(128), nullable=False, default="SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
