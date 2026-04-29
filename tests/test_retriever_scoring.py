"""Tests for hybrid retriever scoring."""

from app.rag.chunker import RAGChunk
from app.rag.retriever import compute_hybrid_score
from app.rag.search_profiles import SEARCH_PROFILES


def test_hybrid_score_penalizes_premium_for_coverage_summary() -> None:
    premium_chunk = RAGChunk(
        document_id="doc-1",
        document_name="a.pdf",
        document_type="product_summary",
        product_type="annuity",
        chunk_id="c1",
        page=1,
        end_page=1,
        section="보험료",
        normalized_section="premium",
        content="기본보험료와 적용이율을 설명합니다.",
    )
    coverage_chunk = RAGChunk(
        document_id="doc-1",
        document_name="a.pdf",
        document_type="product_summary",
        product_type="annuity",
        chunk_id="c2",
        page=2,
        end_page=2,
        section="보험금 지급사유",
        normalized_section="coverage",
        content="보험금 지급사유와 지급금액을 설명합니다.",
    )

    premium_score = compute_hybrid_score(
        chunk=premium_chunk,
        embedding_score=0.8,
        query_tokens={"주요", "보장", "내용"},
        search_profile=SEARCH_PROFILES["coverage_summary"],
    )
    coverage_score = compute_hybrid_score(
        chunk=coverage_chunk,
        embedding_score=0.76,
        query_tokens={"주요", "보장", "내용"},
        search_profile=SEARCH_PROFILES["coverage_summary"],
    )

    assert coverage_score > premium_score


def test_hybrid_score_boosts_premium_for_premium_question() -> None:
    premium_chunk = RAGChunk(
        document_id="doc-1",
        document_name="a.pdf",
        document_type="product_summary",
        product_type="annuity",
        chunk_id="c1",
        page=1,
        end_page=1,
        section="보험료",
        normalized_section="premium",
        content="기본보험료와 적용이율을 설명합니다.",
    )

    score = compute_hybrid_score(
        chunk=premium_chunk,
        embedding_score=0.7,
        query_tokens={"보험료", "비용"},
        search_profile=SEARCH_PROFILES["premium_cost"],
    )

    assert score > 0.8
