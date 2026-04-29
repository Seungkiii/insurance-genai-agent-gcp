"""Rule-based intent classification node."""

from __future__ import annotations

from app.agents.state import AgentState, IntentType


def run_intent_node(state: AgentState) -> AgentState:
    """Classify the user query into one of the supported intents."""
    query = state.get("user_query", "")
    updated = dict(state)
    updated["intent"] = classify_intent(query, document_ids=state.get("document_ids", []))
    updated["next_action"] = "extract_slots"
    return updated


def classify_intent(query: str, *, document_ids: list[str] | None = None) -> IntentType:
    """Classify the broad user intent."""
    lowered = query.lower()
    document_ids = document_ids or []
    has_single_document = len(document_ids) == 1
    has_multiple_documents = len(document_ids) > 1
    mentions_this_product = "이 상품" in query
    asks_explanation = any(token in query for token in ("설명", "안내", "제안", "강조", "유의사항", "설계 포인트"))
    asks_recommendation = any(token in query for token in ("추천", "적합", "어떤 상품", "골라", "좋아"))
    asks_comparison = any(token in query for token in ("비교", "차이", "더 나은", "어느 상품", "이 두 상품", "A와 B"))
    asks_design_change = any(
        token in query
        for token in ("방금 추천", "기존 설계", "추가해", "빼줘", "유지해", "변경해", "수정", "조정", "줄이", "늘리", "제외")
    )
    asks_policy_detail = any(token in query for token in ("약관", "보장", "지급", "보험료", "환급", "면책", "연금", "특약"))

    if any(token in query for token in ("청구", "서류", "제출")) or "claim" in lowered:
        return "claim_document"
    if asks_design_change:
        return "design_modification"
    if asks_comparison or has_multiple_documents and any(token in query for token in ("비교", "차이", "적합")):
        return "product_comparison"
    if (has_single_document or mentions_this_product) and (asks_explanation or asks_recommendation) and not asks_comparison:
        return "single_product_advice"
    if asks_recommendation and not has_single_document:
        return "multi_product_recommendation"
    if any(token in query for token in ("요약", "정리", "한눈에")):
        return "summary"
    if asks_policy_detail:
        return "policy_qa"
    return "general"
