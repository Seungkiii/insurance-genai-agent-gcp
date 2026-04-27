"""Health check router."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return basic service status."""
    return {"status": "ok"}
