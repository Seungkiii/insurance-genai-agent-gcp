"""Design modification node for iterative design updates."""

from __future__ import annotations

from app.agents.state import AgentState, DesignState


def run_design_modify_node(state: AgentState) -> AgentState:
    """Modify the current design according to extracted slot hints."""
    current_design = dict(state.get("current_design", {}))
    slots = state.get("extracted_slots", {})
    query = state.get("user_query", "")

    design: DesignState = {
        "product_name": current_design.get("product_name") or slots.get("product_name", "Sample Care Plan"),
        "payment_period": current_design.get("payment_period", "20 years"),
        "insurance_period": current_design.get("insurance_period", "80 years"),
        "payment_cycle": current_design.get("payment_cycle", "monthly"),
        "coverage_amount": int(current_design.get("coverage_amount", 50000000)),
    }

    if "payment_period" in slots:
        design["payment_period"] = slots["payment_period"]
    elif any(token in query for token in ("납입기간만 짧게", "납입기간 짧게", "shorter payment period")):
        design["payment_period"] = "10 years"

    if "insurance_period" in slots:
        design["insurance_period"] = slots["insurance_period"]

    if "payment_cycle" in slots:
        design["payment_cycle"] = slots["payment_cycle"]

    if "coverage_amount" in slots:
        design["coverage_amount"] = int(slots["coverage_amount"])
    elif slots.get("modify_direction") == "decrease":
        design["coverage_amount"] = int(design["coverage_amount"] * 0.8)
    elif slots.get("modify_direction") == "increase":
        design["coverage_amount"] = int(design["coverage_amount"] * 1.2)

    updated = dict(state)
    updated["modified_design"] = design
    updated["confidence_score"] = 0.62
    updated["fallback_reason"] = None
    updated["next_action"] = "respond_modification"
    return updated
