"""Chat router backed by the workflow agent MVP."""

from __future__ import annotations

from fastapi import APIRouter

from app.agents.graph import run_workflow
from app.agents.state import AgentState
from app.schemas.chat_schema import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Handle a chat request through the workflow agent."""
    initial_state: AgentState = {
        "session_id": request.session_id or "session-sample-001",
        "user_query": request.question,
    }
    result = run_workflow(initial_state)

    return ChatResponse(
        session_id=result.get("session_id", request.session_id or "session-sample-001"),
        intent=result.get("intent", "general"),
        answer=result.get("answer", ""),
        citations=result.get("citations", []),
        confidence_score=result.get("confidence_score", 0.0),
        follow_up_questions=[
            "약관 조회, 가입설계 추천, 설계 변경, 청구 서류 확인 중 어떤 흐름을 더 진행할까요?"
        ],
        disclaimer=result.get("disclaimer", "Synthetic sample response generated without real insurer data."),
    )
