"""Chat router for workflow orchestration entrypoint."""

from fastapi import APIRouter

from app.schemas.chat_schema import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Handle a chat request with placeholder response logic."""
    return ChatResponse(
        session_id=request.session_id or "session-sample-001",
        intent="unknown",
        answer="This is a placeholder response. Integrate agent workflow next.",
        citations=[],
        confidence_score=0.0,
        follow_up_questions=["Could you provide more details for the design scenario?"],
        disclaimer="Synthetic sample response for PoC scaffolding.",
    )
