from datetime import datetime, timezone, timedelta
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from backend.config import settings
from backend.database import get_supabase_client

logger = logging.getLogger("signalforge")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def recover_stale_discovery_jobs() -> int:
    """Reset campaigns stuck in discovering for > 15 minutes per docs/decisions.md Section 9."""
    try:
        db = get_supabase_client()
        fifteen_mins_ago = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

        stale_res = (
            db.table("campaigns")
            .select("id")
            .eq("status", "discovering")
            .lt("started_at", fifteen_mins_ago)
            .execute()
        )
        if stale_res.data:
            stale_ids = [r["id"] for r in stale_res.data]
            db.table("campaigns").update({"status": "draft"}).in_("id", stale_ids).execute()
            logger.warning(f"Startup recovery: reset {len(stale_ids)} stale discovering campaign(s) to draft: {stale_ids}")
            return len(stale_ids)
        return 0
    except Exception as exc:
        logger.error(f"Error during startup discovery job recovery: {exc}", exc_info=True)
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler for server startup and shutdown."""
    logger.info("SignalForge AI backend starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Supabase configured: {bool(settings.SUPABASE_URL)}")

    # Run background recovery on startup (docs/decisions.md Section 9)
    await recover_stale_discovery_jobs()

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


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle explicit HTTP exceptions with standard error response envelope."""
    error_code = getattr(exc, "error_code", f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": error_code},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Handle validation errors without exposing internal traces."""
    from fastapi.encoders import jsonable_encoder

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "error_code": "VALIDATION_ERROR",
            "errors": jsonable_encoder(exc.errors()),
        },
    )



@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """Log full trace server-side and return generic sanitized error to client (security.md)."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint per decisions.md contract."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }


# Include Routers with /api prefix per decisions.md Section 4
from backend.routers.auth import router as auth_router
from backend.routers.campaigns import router as campaigns_router
from backend.routers.leads import router as leads_router

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(campaigns_router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(leads_router, prefix="/api", tags=["Leads"])



if __name__ == "__main__":
    # Strictly one worker per decisions.md Section 9 for APScheduler safety
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,
        reload=settings.ENVIRONMENT == "development",
    )
