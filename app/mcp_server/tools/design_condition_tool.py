"""Design condition adjustment tool for current design state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.firestore_service import FirestoreService

from .base import BaseTool


@dataclass
class DesignConditionTool(BaseTool):
    """Apply add/remove coverage changes to the current design snapshot."""

    firestore_service: FirestoreService | None = None
    name: str = "design_condition_tool"
    description: str = (
        "Load current_design from Firestore, apply add/remove/keep coverage changes, and return both the original and updated design."
    )
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "add_coverages": {"type": "array", "items": {"type": "string"}},
                "remove_coverages": {"type": "array", "items": {"type": "string"}},
                "keep_coverages": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["session_id"],
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "previous_design": {"type": "object"},
                "updated_design": {"type": "object"},
                "applied_changes": {"type": "object"},
            },
        }
    )

    def execute(self, payload: dict[str, Any], trace_summary: list[str]) -> dict[str, Any]:
        """Load and update the session design state."""
        if self.firestore_service is None:
            raise RuntimeError("DesignConditionTool is not configured with a Firestore service.")

        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            raise ValueError("The 'session_id' field is required.")

        previous_record = self.firestore_service.get_current_design(session_id)
        if previous_record is None:
            raise ValueError("No current_design was found for the session.")

        previous_design = dict(previous_record.get("current_design", {}))
        updated_design = dict(previous_design)
        current_coverages = list(updated_design.get("coverages", []))
        add_coverages = _normalize_items(payload.get("add_coverages", []))
        remove_coverages = _normalize_items(payload.get("remove_coverages", []))
        keep_coverages = _normalize_items(payload.get("keep_coverages", []))

        if keep_coverages:
            current_coverages = [coverage for coverage in current_coverages if coverage in keep_coverages]
        current_coverages = [coverage for coverage in current_coverages if coverage not in remove_coverages]
        for coverage in add_coverages:
            if coverage not in current_coverages:
                current_coverages.append(coverage)
        updated_design["coverages"] = current_coverages

        try:
            self.firestore_service.save_current_design(session_id, updated_design)
            trace_summary.append("current_design_saved=true")
        except Exception as exc:  # noqa: BLE001
            trace_summary.append("current_design_saved=false")
            raise RuntimeError(f"Failed to persist current_design: {exc}") from exc

        return {
            "session_id": session_id,
            "previous_design": previous_design,
            "updated_design": updated_design,
            "applied_changes": {
                "add_coverages": add_coverages,
                "remove_coverages": remove_coverages,
                "keep_coverages": keep_coverages,
            },
        }


def _normalize_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized
