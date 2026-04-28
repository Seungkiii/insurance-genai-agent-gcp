"""Rule-based workflow graph for the Insurance GenAI Agent MVP."""

from __future__ import annotations

from app.agents.nodes.design_modify_node import run_design_modify_node
from app.agents.nodes.guardrail_node import run_guardrail_node
from app.agents.nodes.intent_node import run_intent_node
from app.agents.nodes.recommendation_node import run_recommendation_node
from app.agents.nodes.response_node import run_response_node
from app.agents.nodes.retrieval_node import run_retrieval_node
from app.agents.nodes.slot_extract_node import run_slot_extract_node
from app.agents.state import AgentState


def run_workflow(state: AgentState) -> AgentState:
    """Run the MVP workflow using LangGraph-style node transitions."""
    current = run_intent_node(state)
    current = run_slot_extract_node(current)

    intent = current["intent"]
    if intent in {"policy_qa", "claim_document"}:
        current = run_retrieval_node(current)
    elif intent == "design_recommendation":
        current = run_recommendation_node(current)
    elif intent == "design_modification":
        current = run_design_modify_node(current)
    else:
        current.setdefault("confidence_score", 0.2)
        current.setdefault("next_action", "respond_general")

    current = run_guardrail_node(current)
    current = run_response_node(current)
    return current
