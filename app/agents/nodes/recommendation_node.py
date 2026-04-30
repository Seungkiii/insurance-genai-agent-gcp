"""Recommendation node for agent workflow integration."""

from __future__ import annotations

from typing import Any

from app.agents.dependencies import WorkflowDependencies
from app.agents.state import AgentState


def run_recommendation_node(state: AgentState, dependencies: WorkflowDependencies) -> AgentState:
    """Run product recommendation and project the output into agent state."""
    payload: dict[str, Any] = {
        "query": state.get("user_query", ""),
        "session_id": state.get("session_id", ""),
        "document_ids": state.get("document_ids", []),
        "customer_profile": state.get("extracted_slots", {}),
        "top_k": state.get("top_k", 5),
    }
    if state.get("product_type_hint"):
        payload["product_type"] = state["product_type_hint"]

    result = dependencies.product_recommend_tool.run(payload)
    updated = dict(state)
    updated.setdefault("tool_trace", [])
    updated["tool_trace"].append(
        {
            "step": len(updated["tool_trace"]) + 1,
            "tool_name": "product_recommend_tool",
            "status": result["status"],
            "latency_ms": result["latency_ms"],
            "input_summary": {
                "query": payload["query"],
                "document_ids": payload.get("document_ids", []),
                "product_type_hint": payload.get("product_type"),
            },
            "output_summary": _recommendation_output_summary(result.get("output")),
            "error": result.get("error"),
        }
    )

    if result["status"] != "success":
        updated["fallback_required"] = True
        updated["error"] = result.get("error")
        return updated

    output = result["output"] or {}
    updated["recommended_design"] = output.get("recommended_design")
    updated["recommended_products"] = list(output.get("recommended_products", []))
    updated["current_design"] = output.get("current_design") or updated.get("current_design")
    updated["selected_document_ids"] = _collect_document_ids(
        updated["recommended_products"],
        updated.get("current_design"),
        updated.get("selected_document_ids", updated.get("document_ids", [])),
    )
    updated["selected_product_names"] = _collect_product_names(
        updated["recommended_products"],
        updated.get("current_design"),
        updated.get("selected_product_names", []),
    )
    if output.get("citations"):
        updated["citations"] = list(output["citations"])
    if output.get("search_profile"):
        updated["search_profile"] = str(output["search_profile"])
    updated["fallback_required"] = bool(output.get("fallback_required", updated.get("fallback_required", False)))
    return updated


def _recommendation_output_summary(output: dict[str, Any] | None) -> dict[str, object] | None:
    if not output:
        return None
    return {
        "search_profile": output.get("search_profile"),
        "citation_count": len(output.get("citations", [])),
        "has_recommended_design": bool(output.get("recommended_design")),
        "recommended_product_count": len(output.get("recommended_products", [])),
        "has_current_design": bool(output.get("current_design")),
        "fallback_required": output.get("fallback_required"),
    }


def _collect_document_ids(
    recommended_products: list[dict[str, Any]],
    current_design: dict[str, Any] | None,
    fallback_document_ids: list[str],
) -> list[str]:
    current_design_ids = list(current_design.get("selected_document_ids", [])) if current_design else []
    if current_design_ids:
        return [str(item) for item in current_design_ids if str(item).strip()]

    document_ids: list[str] = []
    for product in recommended_products:
        document_id = str(product.get("document_id") or "").strip()
        if document_id and document_id not in document_ids:
            document_ids.append(document_id)
    return document_ids or list(fallback_document_ids)


def _collect_product_names(
    recommended_products: list[dict[str, Any]],
    current_design: dict[str, Any] | None,
    fallback_product_names: list[str],
) -> list[str]:
    if current_design and isinstance(current_design.get("selected_product_names"), list):
        names = [str(item).strip() for item in current_design["selected_product_names"] if str(item).strip()]
        if names:
            return names

    names: list[str] = []
    for product in recommended_products:
        name = str(product.get("product_name") or product.get("document_name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names or list(fallback_product_names)
