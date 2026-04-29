"""Confidence scoring for insurance RAG responses."""

from __future__ import annotations

from statistics import mean

from app.rag.retriever import RetrievalResult
from app.rag.search_profiles import SearchProfile


def compute_confidence_score(
    *,
    results: list[RetrievalResult],
    profile: SearchProfile,
    fallback_required: bool,
    answer: str | None = None,
) -> float:
    """Compute a bounded confidence score from retrieval quality and alignment."""
    if not results:
        return 0.0

    top_results = results[:5]
    hybrid_scores = [result.hybrid_score if result.hybrid_score is not None else result.score for result in top_results]
    avg_hybrid = mean(hybrid_scores)
    positive_count = sum(1 for result in top_results if result.chunk.normalized_section in profile.positive_sections)
    negative_count = sum(1 for result in top_results if result.chunk.normalized_section in profile.negative_sections)
    preferred_doc_count = sum(1 for result in top_results if result.chunk.document_type in profile.preferred_document_types)
    diverse_sections = len({result.chunk.normalized_section for result in top_results})
    diverse_documents = len({result.chunk.document_id for result in top_results})

    positive_bonus = min(positive_count * 0.08, 0.24)
    preferred_doc_bonus = min(preferred_doc_count * 0.04, 0.12)
    diversity_bonus = min(((diverse_sections - 1) * 0.03) + ((diverse_documents - 1) * 0.02), 0.12)
    negative_penalty = min(negative_count * 0.1, 0.3)

    confidence = (avg_hybrid * 0.55) + positive_bonus + preferred_doc_bonus + diversity_bonus - negative_penalty
    if positive_count == 0 and profile.positive_sections:
        confidence = min(confidence, 0.6)
    if fallback_required:
        confidence = min(confidence, 0.4)
    if answer and "근거 부족" in answer:
        confidence = min(confidence, 0.35)

    return round(max(0.0, min(0.99, confidence)), 2)
