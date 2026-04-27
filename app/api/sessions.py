"""Session router for synthetic chat history."""

from fastapi import APIRouter

from app.schemas.chat_schema import SessionHistoryResponse

router = APIRouter()


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
def get_session(session_id: str) -> SessionHistoryResponse:
    """Return placeholder session history."""
    return SessionHistoryResponse(session_id=session_id, messages=[])
