import uuid

from pydantic import BaseModel


class ConsentGrantRequest(BaseModel):
    provider_id: uuid.UUID
    scope: list[str] | None = None  # None = all measurement types


class ConsentOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    provider_id: uuid.UUID
    status: str
    scope: list[str] | None

    model_config = {"from_attributes": True}


class ConsentedPatientOut(BaseModel):
    patient_id: uuid.UUID
    display_name: str
    consent_id: uuid.UUID
