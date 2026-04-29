"""Profile and slot extraction node for workflow orchestration."""

from __future__ import annotations

import re

from app.agents.state import AgentState
from app.rag.search_profiles import SearchProfile, classify_search_profile

PRODUCT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "annuity": ("연금", "연금보험", "생존연금"),
    "whole_life": ("종신", "사망보험금"),
    "cancer": ("암", "암보험", "암진단비"),
    "health": ("건강", "질병", "입원", "수술"),
    "accident": ("상해", "재해", "장해"),
    "dental": ("치아", "임플란트", "크라운"),
}


def run_slot_extract_node(state: AgentState) -> AgentState:
    """Extract profile-aware slots from the user query."""
    query = state.get("user_query", "")
    profile = classify_search_profile(query)
    slots = extract_slots(query)

    updated = dict(state)
    updated["document_ids"] = list(state.get("document_ids", []))
    updated["top_k"] = int(state.get("top_k", 5))
    updated["top_k_per_document"] = int(state.get("top_k_per_document", 3))
    updated["search_profile"] = profile.name
    updated["product_type_hint"] = _detect_product_type_hint(query, profile)
    updated["extracted_slots"] = slots
    updated["comparison_mode"] = profile.name == "product_comparison" or len(updated["document_ids"]) > 1
    updated.setdefault("tool_trace", [])
    updated.setdefault("citations", [])
    updated.setdefault("retrieved_chunks", [])
    updated.setdefault("fallback_required", False)
    updated["next_action"] = "route_tools"
    return updated


def extract_slots(query: str) -> dict[str, str]:
    """Extract customer profile and design-modification hints from the query."""
    slots: dict[str, str] = {}
    normalized = query.lower()

    age_match = re.search(r"([2-7]0)s", normalized)
    if age_match:
        slots["age_group"] = age_match.group(1)

    if "여성" in query:
        slots["gender"] = "F"
    elif "남성" in query:
        slots["gender"] = "M"

    payment_period_match = re.search(r"(\d+)\s*년\s*납", query)
    if payment_period_match:
        slots["payment_period"] = f"{payment_period_match.group(1)} years"

    insurance_period_match = re.search(r"(\d+)\s*세\s*(만기|보장)", query)
    if insurance_period_match:
        slots["insurance_period"] = f"{insurance_period_match.group(1)} years"

    coverage_match = re.search(r"(\d+)\s*(만원|원)", query)
    if coverage_match:
        amount = int(coverage_match.group(1))
        if coverage_match.group(2) == "만원":
            amount *= 10000
        slots["coverage_amount"] = str(amount)

    if "월납" in query:
        slots["payment_cycle"] = "monthly"

    if any(token in query for token in ("낮추", "줄이", "감액")):
        slots["modify_direction"] = "decrease"
    elif any(token in query for token in ("늘리", "확대", "증액")):
        slots["modify_direction"] = "increase"

    if any(token in query for token in ("추가", "넣어", "포함")):
        slots["design_add"] = "true"
    if any(token in query for token in ("제외", "빼", "삭제")):
        slots["design_remove"] = "true"

    return slots


def _detect_product_type_hint(query: str, profile: SearchProfile) -> str | None:
    for product_type, keywords in PRODUCT_TYPE_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return product_type
    if profile.product_type_hints:
        return profile.product_type_hints[0]
    return None
