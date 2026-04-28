"""Design condition adjustment tool for rider add/remove scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DesignConditionTool:
    """Apply rider add/remove changes to a synthetic current design state."""

    name: str = "design_condition_tool"
    description: str = (
        "Apply add/remove rider operations to a synthetic current design state and return the updated design."
    )
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "current_design": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "payment_period": {"type": "string"},
                        "insurance_period": {"type": "string"},
                        "payment_cycle": {"type": "string"},
                        "coverage_amount": {"type": "integer"},
                        "riders": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "add_riders": {"type": "array", "items": {"type": "string"}},
                "remove_riders": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["current_design"],
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool_name": {"type": "string"},
                "updated_design": {"type": "object"},
                "applied_changes": {"type": "object"},
            },
        }
    )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply rider additions and removals to the current design."""
        current_design = payload.get("current_design")
        if not isinstance(current_design, dict):
            return {
                "ok": False,
                "tool_name": self.name,
                "error": "The 'current_design' field must be an object.",
            }

        updated_design = dict(current_design)
        riders = list(updated_design.get("riders", []))
        add_riders = _normalize_riders(payload.get("add_riders", []))
        remove_riders = _normalize_riders(payload.get("remove_riders", []))

        riders = [rider for rider in riders if rider not in remove_riders]
        for rider in add_riders:
            if rider not in riders:
                riders.append(rider)

        updated_design["riders"] = riders

        return {
            "ok": True,
            "tool_name": self.name,
            "updated_design": updated_design,
            "applied_changes": {
                "added_riders": add_riders,
                "removed_riders": remove_riders,
                "final_rider_count": len(riders),
            },
        }


def _normalize_riders(value: Any) -> list[str]:
    """Normalize rider list inputs."""
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        rider = str(item).strip()
        if rider:
            normalized.append(rider)
    return normalized
