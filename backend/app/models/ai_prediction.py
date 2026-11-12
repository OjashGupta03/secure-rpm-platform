import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class RiskLevel(str, enum.Enum):
    normal = "normal"
    watch = "watch"
    elevated = "elevated"
    high = "high"


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    input_reference: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("measurements.id"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_protocol_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    classical_score: Mapped[float] = mapped_column(Float, nullable=False)
    quantum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    combined_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False)
    explanation: Mapped[str] = mapped_column(String(1024), nullable=False)
    contributing_features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
