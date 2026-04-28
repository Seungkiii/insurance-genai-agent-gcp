"""Rule-based intent classification node."""

from __future__ import annotations

from app.agents.state import AgentState, IntentType


def run_intent_node(state: AgentState) -> AgentState:
    """Classify the user query into one of the supported intents."""
    query = state.get("user_query", "")
    updated = dict(state)
    updated["intent"] = classify_intent(query)
    updated["next_action"] = "extract_slots"
    return updated


def classify_intent(query: str) -> IntentType:
    """Rule-based intent classifier for the MVP."""
    lowered = query.lower()

    if any(token in query for token in ("서류", "청구")) or "claim" in lowered:
        return "claim_document"
    if any(token in query for token in ("변경", "수정", "조정", "줄이", "낮추", "늘리", "바꾸")):
        return "design_modification"
    if any(token in query for token in ("추천", "설계안", "설계 이력", "상품 조합")):
        return "design_recommendation"
    if any(token in query for token in ("약관", "보장", "면책", "지급", "특약")):
        return "policy_qa"
    if any(token in query for token in ("보험", "설계", "가입")):
        return "general"
    return "general"
