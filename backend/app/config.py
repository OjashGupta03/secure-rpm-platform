from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", Path(__file__).resolve().parents[2] / ".env"),
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str
    session_cookie_name: str = "rpm_session"
    session_ttl_minutes: int = 60

    database_url: str

    field_encryption_key_b64: str

    realtime_transport: str = "sse"
    realtime_max_connections_per_user: int = 3
    realtime_message_rate_limit: int = 20

    quantum_max_qubits: int = 6
    quantum_max_shots: int = 1024
    quantum_job_timeout_seconds: int = 30
    quantum_jobs_per_user_per_minute: int = 3

    synthetic_data_seed: int = 42
    synthetic_device_interval_seconds: int = 120

    frontend_origin: str = "http://localhost:5173"


settings = Settings()

SYNTHETIC_DATA_BANNER = "SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION"
AI_DISCLAIMER = (
    "AI-generated information is for monitoring/research purposes and is not a medical diagnosis."
)
QUANTUM_DISCLAIMER = (
    "Quantum analysis is an experimental research component running on a classical simulator. "
    "It is benchmarked against, and does not replace, the classical baseline."
)
