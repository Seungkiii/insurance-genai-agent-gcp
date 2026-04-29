"""Demo web UI routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


@router.get("/demo", include_in_schema=False)
def demo_page() -> FileResponse:
    """Serve the static chatbot demo page."""
    return FileResponse(STATIC_DIR / "demo.html")
