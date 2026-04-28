"""Tests for policy chunking behavior."""

from app.rag.chunker import chunk_document
from app.rag.parser import MarkdownPolicyParser


def test_chunk_document_creates_metadata_rich_chunks() -> None:
    """Chunking should preserve retrieval metadata for each clause."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md")

    chunks = chunk_document(document)

    assert chunks
    assert any(chunk.section == "보장하는 손해" for chunk in chunks)
    assert any("입원일당" in chunk.content for chunk in chunks)

    first_chunk = chunks[0]
    assert first_chunk.document_name == "sample_policy.md"
    assert first_chunk.page == 1
    assert first_chunk.content


def test_chunk_document_splits_numbered_and_bulleted_clauses() -> None:
    """Numbered and bulleted items should become separate chunks."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md")

    chunks = chunk_document(document)
    target_sections = [chunk for chunk in chunks if chunk.section == "청구 서류"]

    assert len(target_sections) >= 3
    assert any("보험금 청구서" in chunk.content for chunk in target_sections)
    assert any("신분 확인 서류 사본" in chunk.content for chunk in target_sections)
