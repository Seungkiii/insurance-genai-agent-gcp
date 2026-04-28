"""Policy search tool backed by the keyword RAG retriever."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.nodes.retrieval_node import get_policy_chunks
from app.rag.citation import build_citations
from app.rag.retriever import KeywordChunkRetriever


@dataclass
class PolicySearchTool:
    """Search synthetic policy clauses using the existing RAG retriever."""

    name: str = "policy_search_tool"
    description: str = (
        "Search the synthetic sample policy and return the most relevant clauses with citation metadata."
    )
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Policy or claim-related question."},
                "top_k": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool_name": {"type": "string"},
                "query": {"type": "string"},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "document_name": {"type": "string"},
                            "section": {"type": "string"},
                            "page": {"type": "integer"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        }
    )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute keyword retrieval against the synthetic sample policy."""
        query = str(payload.get("query", "")).strip()
        top_k = int(payload.get("top_k", 3))
        if not query:
            return {
                "ok": False,
                "tool_name": self.name,
                "error": "The 'query' field is required.",
            }

        retriever = KeywordChunkRetriever()
        results = retriever.retrieve(query, get_policy_chunks(), top_k=top_k)
        citations = [citation.model_dump() for citation in build_citations(results)]

        return {
            "ok": True,
            "tool_name": self.name,
            "query": query,
            "results": citations,
        }
