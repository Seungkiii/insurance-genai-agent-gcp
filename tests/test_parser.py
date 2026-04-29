"""Tests for markdown and PDF parsers."""

from __future__ import annotations

import sys
import types

from app.rag.parser import MarkdownPolicyParser, PDFDocumentParser


def test_markdown_parser_preserves_sections() -> None:
    """Markdown parser should preserve section headings and contents."""
    parser = MarkdownPolicyParser()
    document = parser.parse("data/sample_policies/sample_policy.md", document_id="doc-markdown-001")

    assert document.document_id == "doc-markdown-001"
    assert document.document_name == "sample_policy.md"
    assert any(section.heading == "청구 서류" for section in document.sections)


def test_pdf_parser_extracts_text_and_detects_sections(monkeypatch, tmp_path) -> None:
    """PDF parser should extract page text and detect insurance section headings."""
    pdf_path = tmp_path / "sample_product.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    class FakePage:
        def get_text(self, mode: str) -> str:
            assert mode == "text"
            return "보험금 지급\n보험금 지급 기준은 약관에 따릅니다.\n청구 서류\n보험금 청구서와 신분증 사본이 필요합니다."

    class FakeDocument:
        def __iter__(self):
            return iter([FakePage()])

        def close(self) -> None:
            return None

    fake_fitz = types.SimpleNamespace(open=lambda path: FakeDocument())
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    parser = PDFDocumentParser()
    document = parser.parse(str(pdf_path), document_id="doc-pdf-001")

    assert document.document_id == "doc-pdf-001"
    assert document.document_name == "sample_product.pdf"
    assert any(section.heading == "보험금 지급" for section in document.sections)
    assert any(section.heading == "청구 서류" for section in document.sections)
    assert any("보험금 청구서" in section.content for section in document.sections)
