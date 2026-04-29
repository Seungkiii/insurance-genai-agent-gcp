"""Guardrail node for disclaimer and safety annotations."""

from __future__ import annotations

from app.agents.state import AgentState

DEFAULT_DISCLAIMER = (
    "상품요약서와 검색된 근거를 기준으로 정리한 참고 답변입니다. 실제 약관, 인수 기준, 심사 결과를 반드시 추가 확인해야 합니다."
)
RESTRICTED_DISCLAIMER = (
    "검색 근거가 충분하지 않거나 fallback이 발생해 확정적인 답변은 제한합니다. 보험금 지급 확정 표현은 사용할 수 없으며, 실제 약관 확인이 필요합니다."
)


def run_guardrail_node(state: AgentState) -> AgentState:
    """Apply answer restrictions when citations are weak or fallback is required."""
    updated = dict(state)
    citations = updated.get("citations", [])
    fallback_required = bool(updated.get("fallback_required", False))

    if not citations or fallback_required:
        updated["disclaimer"] = RESTRICTED_DISCLAIMER
        updated["follow_up_questions"] = [
            "상품명, 보장 항목, 지급 조건, 보험료, 해약환급금, 청구 서류 중 어떤 기준을 더 확인할까요?"
        ]
    else:
        updated["disclaimer"] = DEFAULT_DISCLAIMER
        updated["follow_up_questions"] = ["원하시면 실제 약관 기준으로 추가 보장 항목도 이어서 확인해드릴게요."]

    return updated
