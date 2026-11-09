"""SessionBoard FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import check_db_health
from app.routers import directory, sessions
from app.schemas import HealthResponse, VersionResponse
from app.telemetry import TraceIdMiddleware, get_current_trace_id, setup_telemetry

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    setup_telemetry(app, settings)
    yield


app = FastAPI(
    title="SessionBoard API",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Correlation and security middlewares
app.add_middleware(TraceIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id"],
)

app.include_router(directory.router)
app.include_router(sessions.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Zero-PII global error handler capturing trace ID."""
    trace_id = getattr(request.state, "trace_id", get_current_trace_id())
    logger.exception("Unhandled server exception: %s [trace_id=%s]", type(exc).__name__, trace_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal_error", "trace_id": trace_id},
        headers={"X-Trace-Id": trace_id},
    )


@app.get(
    "/api/health",
    tags=["system"],
    response_model=HealthResponse,
    responses={
        200: {"model": HealthResponse, "description": "Application and database are healthy"},
        503: {"model": HealthResponse, "description": "Database is unreachable"},
    },
    operation_id="get_health",
)
def get_health() -> Response:
    """System health check endpoint verifying database connectivity."""
    db_ok = check_db_health()
    trace_id = get_current_trace_id()
    if db_ok:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "db": "ok"},
            headers={"X-Trace-Id": trace_id},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "degraded", "db": "error"},
        headers={"X-Trace-Id": trace_id},
    )


@app.get(
    "/api/version",
    tags=["system"],
    response_model=VersionResponse,
    operation_id="get_version",
)
def get_version() -> dict[str, str]:
    """Return application version and running environment."""
    return {
        "version": settings.app_version,
        "env": settings.app_env,
    }


# Static frontend SPA mount (when bundled into container)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Do not intercept API requests
        if full_path.startswith("api"):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "not_found"},
            )
        target = static_dir / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(target)
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "not_found"})
else:

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "app": "SessionBoard",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health",
        }
