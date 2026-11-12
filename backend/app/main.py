import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import AI_DISCLAIMER, QUANTUM_DISCLAIMER, SYNTHETIC_DATA_BANNER, settings
from app.ingest.simulated_device import simulated_device_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(simulated_device_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Secure RPM Platform (Research Prototype)",
    description=f"{SYNTHETIC_DATA_BANNER}. {AI_DISCLAIMER} {QUANTUM_DISCLAIMER}",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "banner": SYNTHETIC_DATA_BANNER}
