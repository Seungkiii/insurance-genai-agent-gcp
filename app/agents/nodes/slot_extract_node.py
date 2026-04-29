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
    updated.setdefault("recommended_products", [])
    updated.setdefault("comparison_result", None)
    updated.setdefault("fallback_required", False)
    updated["next_action"] = "route_tools"
    return updated


def extract_slots(query: str) -> dict[str, object]:
    """Extract generalized customer profile and design-modification hints."""
    slots: dict[str, object] = {
        "risk_needs": [],
        "add_coverages": [],
        "remove_coverages": [],
        "keep_coverages": [],
    }
    normalized = query.lower()

    age_match = re.search(r"(\d{2})\s*세", query)
    if age_match:
        age = int(age_match.group(1))
        slots["age"] = age
        slots["age_group"] = f"{age // 10 * 10}대"
    else:
        age_group_match = re.search(r"([2-7]0)대", query)
        if age_group_match:
            slots["age_group"] = f"{age_group_match.group(1)}대"
        english_age_group_match = re.search(r"([2-7]0)s", normalized)
        if english_age_group_match:
            slots["age_group"] = f"{english_age_group_match.group(1)}대"

    if "여성" in query:
        slots["gender"] = "female"
    elif "남성" in query:
        slots["gender"] = "male"

    if any(token in query for token in ("설명", "안내", "강조", "제안")):
        slots["customer_goal"] = "advice"
    elif any(token in query for token in ("추천", "적합", "골라")):
        slots["customer_goal"] = "recommendation"
    elif "비교" in query or "차이" in query:
        slots["customer_goal"] = "comparison"

    if "이 상품" in query:
        slots["product_preference"] = "current_document"

    risk_needs = _extract_risk_needs(query)
    if risk_needs:
        slots["risk_needs"] = risk_needs

    if any(token in query for token in ("보험료 부담", "가성비", "저렴", "비용", "예산")):
        slots["budget_preference"] = "cost_sensitive"

    for token in ("암", "치아", "치료비", "사망보장", "노후", "연금", "상해", "재해", "건강", "질병", "입원"):
        if token in query and any(keyword in query for keyword in ("추가", "넣", "포함")):
            slots["add_coverages"].append(token)
        if token in query and any(keyword in query for keyword in ("제외", "빼", "삭제")):
            slots["remove_coverages"].append(token)
        if token in query and "유지" in query:
            slots["keep_coverages"].append(token)

    return slots


def _detect_product_type_hint(query: str, profile: SearchProfile) -> str | None:
    for product_type, keywords in PRODUCT_TYPE_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return product_type
    if profile.product_type_hints:
        return profile.product_type_hints[0]
    return None


def _extract_risk_needs(query: str) -> list[str]:
    risk_tokens = ("암", "치아", "치료비", "사망보장", "노후", "연금", "상해", "재해", "건강", "질병")
    return [token for token in risk_tokens if token in query]
