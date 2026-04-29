"""Response assembly node for workflow outputs."""

from __future__ import annotations

from app.agents.state import AgentState
from app.rag.generator import WorkflowAnswerGenerator, build_low_confidence_answer


def run_response_node(state: AgentState, generator: WorkflowAnswerGenerator) -> AgentState:
    """Build the final answer payload from the current workflow state."""
    updated = dict(state)
    intent = updated.get("intent", "general")
    updated.setdefault("citations", [])
    updated.setdefault("recommended_design", None)
    updated.setdefault("current_design", None)
    updated.setdefault("tool_trace", [])
    updated.setdefault("confidence_score", 0.0)

    if intent == "general":
        updated["answer"] = (
            "현재 에이전트는 약관 질의, 상품 요약, 청구 서류 확인, 가입설계 추천, 설계 변경을 우선 지원합니다. "
            "상품명이나 확인하려는 기준을 조금 더 구체적으로 알려주시면 근거 기반으로 도와드릴게요."
        )
        updated.setdefault("confidence_score", 0.2)
        return updated

    if not updated["citations"] or updated.get("fallback_required", False):
        updated["answer"] = build_low_confidence_answer()
        return updated

    updated["answer"] = generator.generate_agent_response(
        question=updated.get("user_query", ""),
        intent=intent,
        search_profile=updated.get("search_profile"),
        retrieved_chunks=updated.get("retrieved_chunks", []),
        citations=updated.get("citations", []),
        recommended_design=updated.get("recommended_design"),
        current_design=updated.get("current_design"),
        fallback_required=bool(updated.get("fallback_required", False)),
    )
    return updated
