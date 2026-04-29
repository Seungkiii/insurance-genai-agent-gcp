"""Application entrypoint for the Insurance GenAI Agent API."""

from __future__ import annotations

import os
import platform
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import admin, chat, demo, documents, feedback, health, sessions
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger


logger = get_logger("app.main")
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Emit startup diagnostics that are easy to spot in Cloud Run logs."""
    settings: Settings = get_settings()
    missing_settings = settings.missing_required_settings
    logger.info(
        "application_starting",
        extra={
            "service": settings.app_name,
            "environment": settings.environment,
            "version": settings.app_version,
            "python_version": platform.python_version(),
            "port": os.getenv("PORT", "unset"),
            "missing_settings": missing_settings,
            "ready": not missing_settings,
        },
    )
    yield
    logger.info(
        "application_stopping",
        extra={
            "service": settings.app_name,
            "environment": settings.environment,
            "version": settings.app_version,
        },
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings: Settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FastAPI backend for a synthetic insurance GenAI PoC.",
        lifespan=lifespan,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
    app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(demo.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


try:
    app = create_app()
except Exception:
    logger.exception("application_bootstrap_failed")
    raise
