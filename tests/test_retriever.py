"""Tests for retrieval behavior."""

from __future__ import annotations

import json

from app.rag.chunker import RAGChunk
from app.rag.retriever import (
    GcsEmbeddingRetriever,
    KeywordChunkRetriever,
    cosine_similarity,
)
from app.rag.search_profiles import SEARCH_PROFILES, build_expanded_query


class FakeStorageService:
    """Mock storage service for embedding artifact retrieval."""

    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads

    def download_bytes(self, gcs_uri: str) -> bytes:
        return self.payloads[gcs_uri].encode("utf-8")


def test_keyword_retriever_finds_relevant_claim_document_chunks() -> None:
    """Keyword retriever should still support local synthetic policy lookups."""
    chunks = [
        RAGChunk(
            document_id="doc-001",
            document_name="sample_policy.md",
            document_type="product_summary",
            product_type="health",
            chunk_id="doc-001-chunk-0001",
            page=1,
            end_page=1,
            section="청구 서류",
            normalized_section="claim",
            content="1. 보험금 청구서",
        ),
        RAGChunk(
            document_id="doc-001",
            document_name="sample_policy.md",
            document_type="product_summary",
            product_type="health",
            chunk_id="doc-001-chunk-0002",
            page=1,
            end_page=1,
            section="보장",
            normalized_section="coverage",
            content="입원일당 보장 안내",
        ),
    ]
    retriever = KeywordChunkRetriever()

    results = retriever.retrieve("입원일당 청구 서류는 무엇인가요?", chunks, top_k=3)

    assert results
    assert results[0].score > 0
    assert any(result.chunk.section == "청구 서류" for result in results)


def test_embedding_retriever_loads_jsonl_and_sorts_by_cosine_similarity() -> None:
    """Embedding retriever should load stored artifacts and rank by cosine similarity."""
    payload = "\n".join(
        [
            json.dumps(
                {
                    "document_id": "doc-101",
                    "document_name": "policy-a.pdf",
                    "document_type": "policy_terms",
                    "product_type": "health",
                    "chunk_id": "doc-101-chunk-0001",
                    "page": 2,
                    "end_page": 2,
                    "section": "보험금 지급",
                    "normalized_section": "coverage",
                    "content": "보험금 지급 기준은 약관에 따릅니다.",
                    "embedding": [1.0, 0.0, 0.0],
                }
            ),
            json.dumps(
                {
                    "document_id": "doc-101",
                    "document_name": "policy-a.pdf",
                    "document_type": "product_summary",
                    "product_type": "health",
                    "chunk_id": "doc-101-chunk-0002",
                    "page": 3,
                    "end_page": 3,
                    "section": "청구 서류",
                    "normalized_section": "claim",
                    "content": "보험금 청구서와 신분증 사본이 필요합니다.",
                    "embedding": [0.0, 1.0, 0.0],
                }
            ),
        ]
    )
    storage_service = FakeStorageService(
        {"gs://sample-bucket/indexes/doc-101/embeddings.jsonl": payload}
    )
    retriever = GcsEmbeddingRetriever(storage_service, "sample-bucket")

    results, diagnostics = retriever.retrieve([0.9, 0.1, 0.0], ["doc-101"], top_k=2)

    assert len(results) == 2
    assert results[0].chunk.section == "보험금 지급"
    assert results[0].score > results[1].score
    assert diagnostics["embedding_record_count"] == 2


def test_cosine_similarity_handles_zero_vectors() -> None:
    """Zero vectors should not raise and should return zero."""
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0


def test_embedding_retriever_boosts_coverage_sections_for_major_coverage_questions() -> None:
    """Coverage-oriented sections should outrank premium chunks for major coverage questions."""
    payload = "\n".join(
        [
            json.dumps(
                {
                    "document_id": "doc-202",
                    "document_name": "policy-b.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "chunk_id": "doc-202-chunk-0001",
                    "page": 22,
                    "end_page": 22,
                    "section": "보험료",
                    "normalized_section": "premium",
                    "content": "1차월 기본보험료의 3.400%(1,700,000원) 및 계약관리비용 안내",
                    "embedding": [1.0, 0.0],
                }
            ),
            json.dumps(
                {
                    "document_id": "doc-202",
                    "document_name": "policy-b.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "chunk_id": "doc-202-chunk-0002",
                    "page": 7,
                    "end_page": 7,
                    "section": "보험금 지급사유",
                    "normalized_section": "coverage",
                    "content": "보험금 지급사유와 지급금액을 안내합니다.",
                    "embedding": [0.97, 0.0],
                }
            ),
        ]
    )
    storage_service = FakeStorageService(
        {"gs://sample-bucket/indexes/doc-202/embeddings.jsonl": payload}
    )
    retriever = GcsEmbeddingRetriever(storage_service, "sample-bucket")

    results, diagnostics = retriever.retrieve(
        [1.0, 0.0],
        ["doc-202"],
        top_k=2,
        question="이 상품의 주요 보장 내용은 뭐야?",
        search_profile=SEARCH_PROFILES["coverage_summary"],
    )

    assert results[0].chunk.section == "보험금 지급사유"
    assert results[0].score > results[1].score
    assert diagnostics["embedding_record_count"] == 2


def test_expand_query_adds_major_coverage_terms() -> None:
    """Major coverage questions should be expanded with insurance benefit vocabulary."""
    expanded = build_expanded_query(
        "이 상품의 주요 보장 내용은 뭐야?",
        SEARCH_PROFILES["coverage_summary"],
    )

    assert "보험금 지급사유" in expanded
    assert "지급금액" in expanded
