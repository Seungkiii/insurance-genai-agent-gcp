"""Feedback router."""

from fastapi import APIRouter

from app.schemas.feedback_schema import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Store feedback with placeholder behavior."""
    return FeedbackResponse(session_id=request.session_id, saved=True)
