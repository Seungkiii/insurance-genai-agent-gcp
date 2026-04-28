"""Slot extraction node for synthetic workflow orchestration."""

from __future__ import annotations

import re

from app.agents.state import AgentState

AGE_GROUPS = ("20s", "30s", "40s", "50s", "60s", "70s")
PRODUCT_NAMES = (
    "Sample Care Plan",
    "Sample Life Plan",
    "Sample Family Shield",
    "Sample Senior Balance",
    "Sample Starter Plan",
)


def run_slot_extract_node(state: AgentState) -> AgentState:
    """Extract simple slots from the user query."""
    query = state.get("user_query", "")
    slots = extract_slots(query)

    updated = dict(state)
    updated["extracted_slots"] = slots
    updated["next_action"] = "route_by_intent"
    return updated


def extract_slots(query: str) -> dict[str, str]:
    """Extract age group, gender, product, and simple design-change hints."""
    slots: dict[str, str] = {}

    for age_group in AGE_GROUPS:
        if age_group in query:
            slots["age_group"] = age_group
            break

    if "여성" in query or re.search(r"\bF\b", query):
        slots["gender"] = "F"
    elif "남성" in query or re.search(r"\bM\b", query):
        slots["gender"] = "M"

    for product_name in PRODUCT_NAMES:
        if product_name in query:
            slots["product_name"] = product_name
            break

    payment_period_match = re.search(r"(\d+\s*years?)\s*납입", query, flags=re.IGNORECASE)
    if payment_period_match:
        slots["payment_period"] = payment_period_match.group(1).replace("  ", " ").strip()

    insurance_period_match = re.search(r"(\d+\s*years?)\s*(보장|유지)", query, flags=re.IGNORECASE)
    if insurance_period_match:
        slots["insurance_period"] = insurance_period_match.group(1).replace("  ", " ").strip()

    coverage_match = re.search(r"(\d+)\s*(만원|원)", query)
    if coverage_match:
        amount = int(coverage_match.group(1))
        if coverage_match.group(2) == "만원":
            amount *= 10000
        slots["coverage_amount"] = str(amount)

    if "월납" in query or "monthly" in query.lower():
        slots["payment_cycle"] = "monthly"

    if any(token in query for token in ("낮추", "줄이", "감액")):
        slots["modify_direction"] = "decrease"
    elif any(token in query for token in ("늘리", "확대", "증액")):
        slots["modify_direction"] = "increase"

    return slots
