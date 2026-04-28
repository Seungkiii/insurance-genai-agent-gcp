"""MCP-compatible tool server for the portfolio MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.mcp_server.tools.design_condition_tool import DesignConditionTool
from app.mcp_server.tools.policy_search_tool import PolicySearchTool
from app.mcp_server.tools.product_recommend_tool import ProductRecommendTool


class MCPCompatibleTool(Protocol):
    """Minimal MCP-compatible tool interface for the MVP."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool with the given payload."""


@dataclass
class MCPToolServer:
    """Simple registry-based tool server for local execution and demos."""

    tools: dict[str, MCPCompatibleTool]

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tool metadata for discovery."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
            }
            for tool in self.tools.values()
        ]

    def call_tool(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a named tool using the MCP-compatible payload contract."""
        tool = self.tools.get(name)
        if tool is None:
            return {
                "ok": False,
                "tool_name": name,
                "error": f"Unknown tool: {name}",
            }
        return tool.run(payload)


def create_mcp_server() -> MCPToolServer:
    """Build the portfolio MVP tool registry."""
    tool_instances: list[MCPCompatibleTool] = [
        PolicySearchTool(),
        ProductRecommendTool(),
        DesignConditionTool(),
    ]
    return MCPToolServer(tools={tool.name: tool for tool in tool_instances})


def start_mcp_server() -> MCPToolServer:
    """Return the local MCP-compatible server instance."""
    return create_mcp_server()
