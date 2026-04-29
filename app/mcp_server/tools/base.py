"""Base tool abstractions for the MCP-compatible tool server."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standard tool execution result envelope."""

    tool_name: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    latency_ms: int = 0
    error: str | None = None
    trace_summary: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a plain dictionary."""
        return asdict(self)


class BaseTool(ABC):
    """Shared interface and helpers for MCP-compatible tools."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool and wrap the result using ToolResult."""
        started_at = time.perf_counter()
        trace_summary: list[str] = []
        try:
            output = self.execute(payload, trace_summary)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return ToolResult(
                tool_name=self.name,
                status="success",
                input=payload,
                output=output,
                latency_ms=latency_ms,
                trace_summary=trace_summary,
            ).to_dict()
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return ToolResult(
                tool_name=self.name,
                status="error",
                input=payload,
                output=None,
                latency_ms=latency_ms,
                error=str(exc),
                trace_summary=trace_summary,
            ).to_dict()

    @abstractmethod
    def execute(self, payload: dict[str, Any], trace_summary: list[str]) -> dict[str, Any]:
        """Perform the actual tool work."""
