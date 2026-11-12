from fastapi import APIRouter

from app.alerts.routes import router as alerts_router
from app.auth.routes import router as auth_router
from app.consent.routes import router as consent_router
from app.ingest.routes import router as measurements_router
from app.realtime.routes import router as realtime_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(consent_router)
api_router.include_router(measurements_router)
api_router.include_router(alerts_router)
api_router.include_router(realtime_router)
