"""Persistence node for the insurance workflow agent."""

from __future__ import annotations

import time

from app.agents.state import AgentState
from app.services.firestore_service import FirestoreService


def run_persist_node(state: AgentState, firestore_service: FirestoreService) -> AgentState:
    """Persist the conversation turn without blocking the user response on failures."""
    updated = dict(state)
    started_at = float(updated.get("started_at", time.perf_counter()))
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    updated.setdefault("tool_trace", [])

    try:
        firestore_service.save_chat_interaction(
            session_id=updated.get("session_id", ""),
            user_message=updated.get("user_query", ""),
            assistant_answer=updated.get("answer", ""),
            citations=list(updated.get("citations", [])),
            latency_ms=latency_ms,
            tool_trace=list(updated.get("tool_trace", [])),
            current_design=updated.get("current_design"),
            intent=updated.get("intent"),
            search_profile=updated.get("search_profile"),
        )
        if updated.get("current_design") is not None:
            firestore_service.save_current_design(
                updated.get("session_id", ""),
                updated["current_design"],
            )
        updated["persistence_error"] = None
    except Exception as exc:  # noqa: BLE001
        updated["persistence_error"] = str(exc)
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
