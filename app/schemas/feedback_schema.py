"""Feedback and admin schemas."""

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    """Feedback submission payload."""

    session_id: str
    rating: int
    comment: str | None = None


class FeedbackResponse(BaseModel):
    """Feedback save response payload."""

    session_id: str
    saved: bool


class FailedQuestion(BaseModel):
    """Failed question model."""

    session_id: str
    query: str


class StatisticsResponse(BaseModel):
    """Admin statistics model."""

    total_questions: int
    feedback_count: int
    fallback_rate: float
