"""MCP-compatible tool server for the portfolio MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_settings
from app.rag.embedder import DummyEmbedder, VertexAIEmbedder
from app.mcp_server.tools.design_condition_tool import DesignConditionTool
from app.mcp_server.tools.policy_search_tool import PolicySearchTool
from app.mcp_server.tools.product_recommend_tool import ProductRecommendTool
from app.services.firestore_service import GCPFirestoreService
from app.services.gcp_storage_service import GCPStorageService
from app.services.vertex_ai_service import VertexAIEmbeddingService


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
    settings = get_settings()
    storage_service = (
        GCPStorageService(bucket_name=settings.gcs_bucket_name)
        if settings.gcs_bucket_name
        else None
    )
    firestore_service = (
        GCPFirestoreService(database=settings.firestore_database)
        if settings.firestore_database
        else None
    )
    if (
        settings.vertex_ai_project_id
        and settings.effective_embedding_location
        and settings.embedding_model_name
    ):
        embedding_service = VertexAIEmbeddingService(
            project_id=settings.vertex_ai_project_id,
            location=settings.effective_embedding_location or "",
            model_name=settings.embedding_model_name,
        )
        embedder = VertexAIEmbedder(embedding_service)
    else:
        embedder = DummyEmbedder()

    policy_search_tool = PolicySearchTool(
        storage_service=storage_service,
        embedder=embedder,
        firestore_service=firestore_service,
        bucket_name=settings.gcs_bucket_name or "",
    )
    tool_instances: list[MCPCompatibleTool] = [
        policy_search_tool,
        ProductRecommendTool(policy_search_tool=policy_search_tool),
        DesignConditionTool(firestore_service=firestore_service),
    ]
    return MCPToolServer(tools={tool.name: tool for tool in tool_instances})


def start_mcp_server() -> MCPToolServer:
    """Return the local MCP-compatible server instance."""
    return create_mcp_server()
