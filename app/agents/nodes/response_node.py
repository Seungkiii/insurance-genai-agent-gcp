"""Response assembly node for workflow outputs."""

from __future__ import annotations

from app.agents.state import AgentState


def run_response_node(state: AgentState) -> AgentState:
    """Build the final answer payload from the current workflow state."""
    updated = dict(state)
    intent = updated.get("intent", "general")

    if intent in {"policy_qa", "claim_document"}:
        updated["answer"] = _build_policy_answer(updated)
    elif intent == "design_recommendation":
        updated["answer"] = _build_recommendation_answer(updated)
        updated.setdefault("citations", [])
    elif intent == "design_modification":
        updated["answer"] = _build_modification_answer(updated)
        updated.setdefault("citations", [])
    else:
        updated["answer"] = (
            "현재 MVP는 synthetic sample policy Q&A, 가입설계 추천, 설계 변경 시나리오를 우선 지원합니다. "
            "질문을 약관, 추천, 변경, 청구 서류 중 하나로 구체화해 주세요."
        )
        updated.setdefault("citations", [])
        updated.setdefault("confidence_score", 0.2)

    return updated


def _build_policy_answer(state: AgentState) -> str:
    """Create a citation-grounded policy answer."""
    citations = state.get("citations", [])
    if not citations:
        fallback_reason = state.get("fallback_reason") or "Relevant clauses were not found."
        return (
            "질문과 직접적으로 일치하는 synthetic sample policy 조항을 찾지 못했습니다. "
            f"사유: {fallback_reason}"
        )

    primary = citations[0]
    supporting = [citation["content"] for citation in citations[1:3]]
    lines = [
        f"질문과 가장 관련된 조항은 '{primary['section']}' 섹션입니다.",
        f"핵심 내용: {primary['content']}",
    ]
    if supporting:
        lines.append(f"추가 참고 내용: {' / '.join(supporting)}")
    return " ".join(lines)


def _build_recommendation_answer(state: AgentState) -> str:
    """Create a recommendation summary from aggregated history."""
    result = state.get("recommendation_result", {})
    if not result:
        return "추천에 필요한 synthetic sample 가입설계 이력을 찾지 못했습니다."

    riders = result.get("recommended_riders", [])
    parts = [
        f"유사 이력 {result.get('basis_count', 0)}건을 기준으로 추천했습니다.",
        f"추천 상품: {result.get('product_name') or 'Sample product'}",
        f"추천 특약: {', '.join(riders) if riders else '없음'}",
        f"추천 납입기간: {result.get('recommended_payment_period') or 'N/A'}",
        f"추천 보험기간: {result.get('recommended_insurance_period') or 'N/A'}",
        f"추천 납입주기: {result.get('recommended_payment_cycle') or 'N/A'}",
        f"추천 보장금액: {result.get('recommended_coverage_amount') or 'N/A'}",
    ]
    if result.get("fallback_reason"):
        parts.append(f"참고: {result['fallback_reason']}")
    return " ".join(parts)


def _build_modification_answer(state: AgentState) -> str:
    """Summarize how the design was adjusted."""
    design = state.get("modified_design", {})
    if not design:
        return "수정할 현재 설계 정보가 충분하지 않아 synthetic sample 기본 설계를 제안하지 못했습니다."

    return (
        "현재 설계를 기준으로 수정안을 반영했습니다. "
        f"상품: {design.get('product_name')}, "
        f"납입기간: {design.get('payment_period')}, "
        f"보험기간: {design.get('insurance_period')}, "
        f"납입주기: {design.get('payment_cycle')}, "
        f"보장금액: {design.get('coverage_amount')}."
    )
