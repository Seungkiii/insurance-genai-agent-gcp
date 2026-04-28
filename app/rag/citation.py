"""Citation helpers for converting retrieval results into API payloads."""

from __future__ import annotations

from app.rag.retriever import RetrievalResult
from app.schemas.chat_schema import Citation


def build_citations(results: list[RetrievalResult]) -> list[Citation]:
    """Convert retrieval results into deduplicated citation objects."""
    citations: list[Citation] = []
    seen: set[tuple[str, str, int, str]] = set()

    for result in results:
        key = (
            result.chunk.document_name,
            result.chunk.section,
            result.chunk.page,
            result.chunk.content,
        )
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document_name=result.chunk.document_name,
                section=result.chunk.section,
                page=result.chunk.page,
                content=result.chunk.content,
            )
        )

    return citations
