"""Policy search node backed by the policy_search_tool."""

from __future__ import annotations

from typing import Any

from app.agents.dependencies import WorkflowDependencies
from app.agents.state import AgentState


def run_policy_search_node(state: AgentState, dependencies: WorkflowDependencies) -> AgentState:
    """Run policy search and project the tool output into agent state."""
    payload: dict[str, Any] = {
        "query": state.get("user_query", ""),
        "document_ids": state.get("document_ids", []),
        "top_k": state.get("top_k", 5),
    }
    if state.get("product_type_hint"):
        payload["product_type"] = state["product_type_hint"]

    result = dependencies.policy_search_tool.run(payload)
    updated = dict(state)
    updated.setdefault("tool_trace", [])
    updated["tool_trace"].append(
        {
            "step": len(updated["tool_trace"]) + 1,
            "tool_name": "policy_search_tool",
            "status": result["status"],
            "latency_ms": result["latency_ms"],
            "input_summary": {
                "query": payload["query"],
                "document_ids": payload.get("document_ids", []),
                "top_k": payload["top_k"],
                "product_type_hint": payload.get("product_type"),
            },
            "output_summary": _policy_output_summary(result.get("output")),
            "error": result.get("error"),
        }
    )

    if result["status"] != "success":
        updated["retrieved_chunks"] = []
        updated["citations"] = []
        updated["fallback_required"] = True
        updated["confidence_score"] = 0.0
        updated["error"] = result.get("error")
        return updated

    output = result["output"] or {}
    updated["retrieved_chunks"] = list(output.get("chunks", []))
    updated["citations"] = list(output.get("citations", []))
    updated["search_profile"] = str(output.get("search_profile") or updated.get("search_profile"))
    updated["product_type_hint"] = str(output.get("product_type") or updated.get("product_type_hint") or "")
    if not updated["product_type_hint"]:
        updated["product_type_hint"] = None
    updated["fallback_required"] = bool(output.get("fallback_required", False))
    updated["confidence_score"] = float(output.get("confidence_score", updated.get("confidence_score", 0.0)))
    return updated


def _policy_output_summary(output: dict[str, Any] | None) -> dict[str, object] | None:
    if not output:
        return None
    return {
        "search_profile": output.get("search_profile"),
        "citation_count": len(output.get("citations", [])),
        "chunk_count": len(output.get("chunks", [])),
        "product_type": output.get("product_type"),
        "document_type": output.get("document_type"),
        "normalized_section": output.get("normalized_section", []),
        "fallback_required": output.get("fallback_required"),
        "confidence_score": output.get("confidence_score"),
    }
