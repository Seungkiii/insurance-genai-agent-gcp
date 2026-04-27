"""Application entrypoint for the Insurance GenAI Agent API."""

from fastapi import FastAPI

from app.api import admin, chat, documents, feedback, health, sessions
from app.core.config import Settings, get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings: Settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FastAPI backend for a synthetic insurance GenAI PoC.",
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
    app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])

    return app


app = create_app()
