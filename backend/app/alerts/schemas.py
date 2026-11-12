import datetime
import uuid

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    severity: str
    status: str
    message: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AlertStatusUpdate(BaseModel):
    status: str  # "acknowledged" | "resolved"
