"""Application entrypoint for the Insurance GenAI Agent API."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import admin, chat, documents, feedback, health, sessions
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings: Settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FastAPI backend for a synthetic insurance GenAI PoC.",
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
    app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])

    return app


app = create_app()
