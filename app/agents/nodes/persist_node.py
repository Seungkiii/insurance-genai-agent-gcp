"""Persistence node for the insurance workflow agent."""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.agents.state import AgentState
from app.services.firestore_service import FirestoreService

logger = get_logger("app.agents.persist_node")


def run_persist_node(state: AgentState, firestore_service: FirestoreService) -> AgentState:
    """Persist the conversation turn without blocking the user response on failures."""
    updated = dict(state)
    started_at = float(updated.get("started_at", time.perf_counter()))
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    updated.setdefault("tool_trace", [])

    try:
        firestore_service.save_session_message(
            updated.get("session_id", ""),
            "assistant",
            updated.get("answer", ""),
            document_ids=list(updated.get("selected_document_ids", updated.get("document_ids", []))),
            selected_product_names=list(updated.get("selected_product_names", [])),
            search_scope=updated.get("search_scope"),
            search_scope_label=updated.get("search_scope_label"),
            current_design=updated.get("current_design"),
            intent=updated.get("intent"),
            search_profile=updated.get("search_profile"),
            confidence_score=float(updated.get("confidence_score", 0.0)),
            fallback_required=bool(updated.get("fallback_required", False)),
            citations=list(updated.get("citations", [])),
            tool_trace=list(updated.get("tool_trace", [])),
            recommended_design=_build_recommended_design_payload(updated),
        )
        if updated.get("current_design") is not None:
            firestore_service.save_current_design(
                updated.get("session_id", ""),
                updated["current_design"],
            )
        updated["persistence_error"] = None
    except Exception as exc:  # noqa: BLE001
        updated["persistence_error"] = str(exc)
        logger.warning(
            "assistant_message_persist_failed",
            extra={
                "session_id": updated.get("session_id", ""),
                "answer_length": len(str(updated.get("answer", ""))),
                "latency_ms": latency_ms,
                "error": str(exc),
            },
        )
        updated["tool_trace"].append(
            {
                "step": len(updated["tool_trace"]) + 1,
                "tool_name": "persist_node",
                "status": "error",
                "latency_ms": 0,
                "input_summary": {"session_id": updated.get("session_id", "")},
                "output_summary": None,
                "error": str(exc),
            }
        )
    return updated


def _build_recommended_design_payload(state: AgentState) -> dict[str, object] | None:
    recommended_design = state.get("recommended_design")
    if recommended_design is None:
        return None

    payload = dict(recommended_design)
    payload["recommended_products"] = list(state.get("recommended_products", []))
    return payload
