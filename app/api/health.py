"""Health and readiness check router."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, object]:
    """Return process-level liveness information."""
    settings: Settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version,
    }


@router.get("/ready")
def readiness_check() -> dict[str, object]:
    """Return readiness based on configuration presence only."""
    settings: Settings = get_settings()
    missing_settings = settings.missing_required_settings
    return {
        "status": "ready" if not missing_settings else "not_ready",
        "service": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version,
        "ready": not missing_settings,
        "missing_settings": missing_settings,
    }
