"""
FastAPI application entrypoint.

Owns app-level concerns only: instantiation, router registration,
logging setup, and centralized exception handling. All business logic
lives in services; all route definitions live in app/api/.
"""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.services.exceptions import (
    EmptyResponseError,
    GeminiAPIError,
    InvalidJSONError,
    SchemaValidationError,
)

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background scheduler
    logger.info("Initializing background scheduler on startup.")
    from app.services.scheduler import start_scheduler, shutdown_scheduler
    start_scheduler()
    yield
    # Shutdown: Stop the background scheduler cleanly
    logger.info("Shutting down background scheduler on shutdown.")
    shutdown_scheduler()


app = FastAPI(
    title="Deadline Sentinel AI",
    description=(
        "AI-powered service that extracts structured placement, internship, "
        "scholarship, hackathon, and event deadline data from unstructured "
        "text, PDFs, and screenshots."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(api_router)


# --- Centralized exception handling -------------------------------------
# Registered once here instead of try/except inside every route. This
# guarantees every endpoint returns a consistent error shape, and adding
# a new endpoint automatically inherits correct error handling for free.

@app.exception_handler(SchemaValidationError)
async def schema_validation_handler(
    request: Request, exc: SchemaValidationError
) -> JSONResponse:
    logger.warning("Extraction schema validation failed: %s", exc)

    safe_errors = []

    for error in exc.raw_errors:
        safe_error = error.copy()

        if "ctx" in safe_error:
            safe_error["ctx"] = {
                k: str(v)
                for k, v in safe_error["ctx"].items()
            }

        safe_errors.append(safe_error)

    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "errors": safe_errors,
        },
    )


@app.exception_handler(EmptyResponseError)
async def empty_response_handler(request: Request, exc: EmptyResponseError) -> JSONResponse:
    """Empty input text or empty Gemini output -> 400 (caller's input problem)."""
    logger.warning("Empty response/input: %s", exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(GeminiAPIError)
async def gemini_api_error_handler(request: Request, exc: GeminiAPIError) -> JSONResponse:
    """The Gemini API call itself failed (network/auth/quota) -> 502."""
    logger.error("Gemini API error: %s", exc)
    return JSONResponse(
        status_code=502, content={"detail": f"Upstream AI service error: {exc}"}
    )


@app.exception_handler(InvalidJSONError)
async def invalid_json_handler(request: Request, exc: InvalidJSONError) -> JSONResponse:
    """Gemini responded but not with valid JSON -> 502 (upstream's fault)."""
    logger.error("Gemini returned invalid JSON: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": f"Upstream AI service returned malformed data: {exc}"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all safety net -> 500. Never leaks internal error details to callers."""
    logger.exception("Unhandled exception.")
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


# --- Health endpoints -----------------------------------------------------
# Kept in main.py rather than api/ since they're app-level infrastructure
# concerns (uptime monitoring, load balancer checks), not domain routes.

@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Basic liveness message."""
    return {"message": "Deadline Sentinel AI is running."}


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check endpoint for uptime monitoring / load balancers."""
    return {"status": "healthy"}