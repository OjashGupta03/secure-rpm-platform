import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    display_name: str = Field(min_length=1, max_length=255)
    role: UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: UserRole
    simulated_device_enabled: bool
    synthetic_persona: str

    model_config = {"from_attributes": True}


class DeviceSettingsUpdate(BaseModel):
    simulated_device_enabled: bool
    synthetic_persona: str = "normotensive_adult"


class ProviderDirectoryEntry(BaseModel):
    id: uuid.UUID
    display_name: str
    email: EmailStr

    model_config = {"from_attributes": True}
