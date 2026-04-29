"""Tool routing node for the insurance workflow agent."""

from __future__ import annotations

from app.agents.state import AgentState


def run_tool_router_node(state: AgentState) -> AgentState:
    """Choose the tool plan based on intent and comparison needs."""
    updated = dict(state)
    intent = updated.get("intent", "general")

    if intent in {"policy_qa", "claim_document", "summary"}:
        updated["tool_plan"] = ["policy_search_tool"]
    elif intent == "design_recommendation":
        updated["tool_plan"] = ["product_recommend_tool", "policy_search_tool"]
    elif intent == "design_modification":
        updated["tool_plan"] = ["design_condition_tool"]
    else:
        updated["tool_plan"] = []
        updated.setdefault("confidence_score", 0.2)
        updated.setdefault("fallback_required", True)

    updated["next_action"] = "run_tools"
    return updated
