"""Citation helpers for chat responses."""

from __future__ import annotations

from app.rag.retriever import RetrievalResult
from app.schemas.chat_schema import Citation


def build_citations(results: list[RetrievalResult]) -> list[Citation]:
    """Convert retrieval results into deduplicated citations with previews and scores."""
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
                normalized_section=result.chunk.normalized_section,
                document_type=result.chunk.document_type,
                product_type=result.chunk.product_type,
                page=result.chunk.page,
                content_preview=_build_preview(result.chunk.content),
                score=round(result.hybrid_score or result.score, 4),
                embedding_score=round(result.embedding_score or 0.0, 4),
                hybrid_score=round(result.hybrid_score or result.score, 4),
            )
        )

    return citations


def _build_preview(content: str, limit: int = 180) -> str:
    """Build a short readable preview for chat citations."""
    if len(content) <= limit:
        return content
    return f"{content[:limit].rstrip()}..."
