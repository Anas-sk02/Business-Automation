import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import settings

logger = logging.getLogger("signalforge")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler for server startup and shutdown."""
    logger.info("SignalForge AI backend starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Supabase configured: {bool(settings.SUPABASE_URL)}")
    yield
    logger.info("SignalForge AI backend shutting down...")


app = FastAPI(
    title="SignalForge AI API",
    description="Evidence-driven business intelligence and WhatsApp outreach platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware configuration
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint per decisions.md contract."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    # Strictly one worker per decisions.md Section 9 for APScheduler safety
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,
        reload=settings.ENVIRONMENT == "development",
    )
