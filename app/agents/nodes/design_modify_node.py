"""Design modification node for iterative design updates."""

from __future__ import annotations

from typing import Any

from app.agents.dependencies import WorkflowDependencies
from app.agents.state import AgentState


def run_design_modify_node(state: AgentState, dependencies: WorkflowDependencies) -> AgentState:
    """Modify the current design through the design_condition_tool."""
    payload = _build_design_payload(state)
    result = dependencies.design_condition_tool.run(payload)

    updated = dict(state)
    updated.setdefault("tool_trace", [])
    updated["tool_trace"].append(
        {
            "step": len(updated["tool_trace"]) + 1,
            "tool_name": "design_condition_tool",
            "status": result["status"],
            "latency_ms": result["latency_ms"],
            "input_summary": {
                "session_id": payload["session_id"],
                "add_coverages": payload.get("add_coverages", []),
                "remove_coverages": payload.get("remove_coverages", []),
                "keep_coverages": payload.get("keep_coverages", []),
            },
            "output_summary": _design_output_summary(result.get("output")),
            "error": result.get("error"),
        }
    )

    if result["status"] != "success":
        updated["fallback_required"] = True
        updated["error"] = result.get("error")
        return updated

    output = result["output"] or {}
    updated["current_design"] = output.get("updated_design") or updated.get("current_design")
    updated.setdefault("confidence_score", 0.62)
    updated.setdefault("fallback_required", False)
    return updated


def _build_design_payload(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query", "")
    add_coverages: list[str] = []
    remove_coverages: list[str] = []
    keep_coverages: list[str] = []

    for token in ("암진단비", "입원", "수술", "사망보험금", "연금지급형태", "치아보철", "기본보장"):
        if token in query and any(keyword in query for keyword in ("추가", "넣", "포함")):
            add_coverages.append(token)
        if token in query and any(keyword in query for keyword in ("제외", "삭제", "빼")):
            remove_coverages.append(token)

    return {
        "session_id": state.get("session_id", ""),
        "add_coverages": add_coverages,
        "remove_coverages": remove_coverages,
        "keep_coverages": keep_coverages,
    }


def _design_output_summary(output: dict[str, Any] | None) -> dict[str, object] | None:
    if not output:
        return None
    updated_design = output.get("updated_design", {})
    return {
        "session_id": output.get("session_id"),
        "coverage_count": len(updated_design.get("coverages", [])),
        "applied_changes": output.get("applied_changes", {}),
    }
