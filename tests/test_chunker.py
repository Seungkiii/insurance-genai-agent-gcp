"""Tests for document chunking behavior."""

from app.rag.chunker import chunk_document
from app.rag.parser import MarkdownPolicyParser


def test_chunk_document_creates_metadata_rich_chunks() -> None:
    """Chunking should preserve retrieval metadata for each chunk."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md", document_id="doc-sample-001")

    chunks = chunk_document(document)

    assert chunks
    assert any(chunk.section == "보장하는 손해" for chunk in chunks)
    assert any("입원일당" in chunk.content for chunk in chunks)

    first_chunk = chunks[0]
    assert first_chunk.document_id == "doc-sample-001"
    assert first_chunk.document_name == "sample_policy.md"
    assert first_chunk.document_type in {"unknown", "policy_terms"}
    assert first_chunk.product_type
    assert first_chunk.chunk_id.startswith("doc-sample-001-chunk-")
    assert first_chunk.page == 1
    assert first_chunk.normalized_section
    assert first_chunk.content


def test_chunk_document_uses_overlap_for_long_sections() -> None:
    """Long sections should be split into multiple overlapping chunks."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md", document_id="doc-sample-002")
    long_content = " ".join(["보장 내용 설명"] * 500)
    document = type(document)(
        document_id=document.document_id,
        document_name=document.document_name,
        product_type=document.product_type,
        document_type=document.document_type,
        sections=[
            type(document.sections[0])(
                heading="보장",
                normalized_section="coverage",
                content=long_content,
                page=1,
            )
        ],
    )

    chunks = chunk_document(document)

    assert len(chunks) >= 2
    assert len(chunks[0].content) <= 1200
    assert chunks[0].content[-80:] in chunks[1].content
