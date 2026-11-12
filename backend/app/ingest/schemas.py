import datetime
import uuid

from pydantic import BaseModel, Field

from app.models.ai_prediction import RiskLevel
from app.models.measurement import MeasurementType


class MeasurementCreate(BaseModel):
    measurement_type: MeasurementType
    value: float
    recorded_at: datetime.datetime | None = None


class AnalysisOut(BaseModel):
    classical_score: float
    quantum_score: float | None
    combined_score: float | None
    risk_level: RiskLevel
    explanation: str
    contributing_features: dict
    evaluation_protocol_version: str | None
    banner: str = "AI-generated information is for monitoring/research purposes and is not a medical diagnosis."
    quantum_banner: str = (
        "Quantum analysis is an experimental research component running on a classical "
        "simulator. It is benchmarked against, and does not replace, the classical baseline."
    )


class MeasurementOut(BaseModel):
    id: uuid.UUID
    measurement_type: MeasurementType
    value: float
    unit: str
    source: str
    recorded_at: datetime.datetime
    data_label: str
    analysis: AnalysisOut | None = None
