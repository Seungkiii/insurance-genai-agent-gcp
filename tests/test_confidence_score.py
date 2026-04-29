"""Tests for confidence score behavior."""

from app.rag.chunker import RAGChunk
from app.rag.confidence import compute_confidence_score
from app.rag.retriever import RetrievalResult
from app.rag.search_profiles import SEARCH_PROFILES


def _result(section: str, normalized_section: str, score: float) -> RetrievalResult:
    chunk = RAGChunk(
        document_id="doc-1",
        document_name="a.pdf",
        document_type="product_summary",
        product_type="annuity",
        chunk_id=f"{section}-{normalized_section}",
        page=1,
        section=section,
        normalized_section=normalized_section,
        content="sample",
    )
    return RetrievalResult(chunk=chunk, score=score, embedding_score=score, hybrid_score=score)


def test_confidence_score_drops_on_section_mismatch() -> None:
    results = [
        _result("보험료", "premium", 0.9),
        _result("해약환급금", "refund", 0.85),
    ]
    score = compute_confidence_score(
        results=results,
        profile=SEARCH_PROFILES["coverage_summary"],
        fallback_required=False,
    )
    assert score <= 0.6


def test_confidence_score_increases_with_positive_sections() -> None:
    results = [
        _result("상품 특이사항", "product_overview", 0.78),
        _result("보험금 지급사유", "coverage", 0.8),
        _result("특약", "rider", 0.74),
    ]
    score = compute_confidence_score(
        results=results,
        profile=SEARCH_PROFILES["coverage_summary"],
        fallback_required=False,
    )
    assert score >= 0.6


def test_confidence_score_caps_when_fallback_required() -> None:
    results = [_result("보험금 지급사유", "coverage", 0.82)]
    score = compute_confidence_score(
        results=results,
        profile=SEARCH_PROFILES["coverage_summary"],
        fallback_required=True,
    )
    assert score <= 0.4
