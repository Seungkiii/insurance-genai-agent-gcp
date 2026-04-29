"""Tests for keyword-based retrieval behavior."""

from app.rag.chunker import chunk_document
from app.rag.parser import MarkdownPolicyParser
from app.rag.retriever import KeywordChunkRetriever


def test_keyword_retriever_finds_relevant_claim_document_chunks() -> None:
    """Retriever should return claim-document-related chunks for matching questions."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md", document_id="doc-retriever-001")
    chunks = chunk_document(document)
    retriever = KeywordChunkRetriever()

    results = retriever.retrieve("입원일당 청구 서류는 무엇인가요?", chunks, top_k=3)

    assert results
    assert results[0].score > 0
    assert any(result.chunk.section == "청구 서류" for result in results)
    assert any("보험금 청구서" in result.chunk.content for result in results)


def test_keyword_retriever_finds_relevant_coverage_chunks() -> None:
    """Retriever should rank coverage-related clauses for coverage questions."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md", document_id="doc-retriever-002")
    chunks = chunk_document(document)
    retriever = KeywordChunkRetriever()

    results = retriever.retrieve("미용 목적 시술도 보장되나요?", chunks, top_k=3)

    assert results
    assert results[0].chunk.section in {"보장하지 않는 손해", "보장하는 손해"}
    assert any("미용 목적의 시술" in result.chunk.content for result in results)
