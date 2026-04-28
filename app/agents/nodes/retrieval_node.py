"""Policy retrieval node for RAG-backed intents."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.agents.state import AgentState, CitationState
from app.rag.chunker import RAGChunk, chunk_document
from app.rag.citation import build_citations
from app.rag.parser import MarkdownPolicyParser
from app.rag.retriever import KeywordChunkRetriever

POLICY_PATH = Path("data/sample_policies/sample_policy.md")


@lru_cache(maxsize=1)
def get_policy_chunks() -> list[RAGChunk]:
    """Load and cache synthetic policy chunks."""
    parser = MarkdownPolicyParser()
    parsed_document = parser.parse(str(POLICY_PATH))
    return chunk_document(parsed_document)


def run_retrieval_node(state: AgentState) -> AgentState:
    """Retrieve relevant policy chunks and attach citations."""
    query = state.get("user_query", "")
    retriever = KeywordChunkRetriever()
    results = retriever.retrieve(query, get_policy_chunks(), top_k=3)
    citations = [
        CitationState(
            document_name=citation.document_name,
            section=citation.section,
            page=citation.page,
            content=citation.content,
        )
        for citation in build_citations(results)
    ]

    updated = dict(state)
    updated["retrieved_docs"] = citations
    updated["citations"] = citations
    updated["confidence_score"] = _compute_confidence_score(results)
    updated["fallback_reason"] = None if citations else "No relevant synthetic policy clauses were retrieved."
    updated["next_action"] = "respond_policy"
    return updated


def _compute_confidence_score(results: list[object]) -> float:
    """Convert retrieval scores into a bounded confidence score."""
    if not results:
        return 0.0
    top_score = getattr(results[0], "score", 0.0)
    return min(0.99, round(top_score / 5.0, 2))
