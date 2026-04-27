"""Admin router with placeholder analytics endpoints."""

from fastapi import APIRouter

from app.schemas.feedback_schema import FailedQuestion, StatisticsResponse

router = APIRouter()


@router.get("/admin/failed-questions", response_model=list[FailedQuestion])
def failed_questions() -> list[FailedQuestion]:
    """Return synthetic failed questions list."""
    return []


@router.get("/admin/statistics", response_model=StatisticsResponse)
def statistics() -> StatisticsResponse:
    """Return synthetic admin statistics."""
    return StatisticsResponse(total_questions=0, feedback_count=0, fallback_rate=0.0)
