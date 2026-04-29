"""Workflow graph for the Insurance LangGraph-style agent."""

from __future__ import annotations

from app.agents.dependencies import WorkflowDependencies
from app.agents.nodes.design_modify_node import run_design_modify_node
from app.agents.nodes.guardrail_node import run_guardrail_node
from app.agents.nodes.intent_node import run_intent_node
from app.agents.nodes.persist_node import run_persist_node
from app.agents.nodes.policy_search_node import run_policy_search_node
from app.agents.nodes.recommendation_node import run_recommendation_node
from app.agents.nodes.response_node import run_response_node
from app.agents.nodes.slot_extract_node import run_slot_extract_node
from app.agents.nodes.tool_router_node import run_tool_router_node
from app.agents.state import AgentState


def run_workflow(state: AgentState, dependencies: WorkflowDependencies) -> AgentState:
    """Run the workflow using LangGraph-style node transitions."""
    current = run_intent_node(state)
    current = run_slot_extract_node(current)
    current = run_tool_router_node(current)

    for tool_name in current.get("tool_plan", []):
        if tool_name == "policy_search_tool":
            current = run_policy_search_node(current, dependencies)
        elif tool_name == "product_recommend_tool":
            current = run_recommendation_node(current, dependencies)
        elif tool_name == "design_condition_tool":
            current = run_design_modify_node(current, dependencies)

    current = run_guardrail_node(current)
    current = run_response_node(current, dependencies.answer_generator)
    current = run_persist_node(current, dependencies.firestore_service)
    return current
