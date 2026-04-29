"""Document parsers for the RAG pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.rag.metadata import classify_document_type, classify_product_type, normalize_section

SKIPPED_SECTION_HEADINGS = {"Document Notice", "Product Overview", "Example Test Queries"}
SECTION_HEADING_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^상품의?특이사항$"), "상품 특이사항"),
    (re.compile(r"^상품개요$"), "상품 개요"),
    (re.compile(r"^주요특징$"), "주요 특징"),
    (re.compile(r"^가입나이$"), "가입나이"),
    (re.compile(r"^가입조건$"), "가입조건"),
    (re.compile(r"^보험기간$"), "보험기간"),
    (re.compile(r"^납입기간$"), "납입기간"),
    (re.compile(r"^보험금지급사유및지급제한사항$"), "보험금지급사유 및 지급제한사항"),
    (re.compile(r"^보험금지급사유$"), "보험금 지급사유"),
    (re.compile(r"^보험금지급$"), "보험금 지급사유"),
    (re.compile(r"^보험급부$"), "보험급부"),
    (re.compile(r"^지급금액$"), "지급금액"),
    (re.compile(r"^보장내용$"), "보장내용"),
    (re.compile(r"^보장$"), "보장"),
    (re.compile(r"^지급하지않는사유$"), "지급하지 않는 사유"),
    (re.compile(r"^보장하지않는사유$"), "보장하지 않는 사유"),
    (re.compile(r"^면책$"), "면책"),
    (re.compile(r"^연금지급형태$"), "연금지급형태"),
    (re.compile(r"^생존연금$"), "생존연금"),
    (re.compile(r"^연금개시전$"), "연금개시전"),
    (re.compile(r"^연금개시후$"), "연금개시후"),
    (re.compile(r"^사망보험금$"), "사망보험금"),
    (re.compile(r"^보험료$"), "보험료"),
    (re.compile(r"^수수료$"), "수수료"),
    (re.compile(r"^해약환급금$"), "해약환급금"),
    (re.compile(r"^환급률$"), "환급률"),
    (re.compile(r"^청구서류$"), "청구 서류"),
    (re.compile(r"^청구$"), "청구 서류"),
    (re.compile(r"^특약$"), "특약"),
)


@dataclass(frozen=True)
class ParsedSection:
    """A logical section extracted from a document."""

    heading: str
    normalized_section: str
    content: str
    page: int


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed document with normalized sections and document-level metadata."""

    document_id: str
    document_name: str
    product_type: str
    document_type: str
    sections: list[ParsedSection]


class DocumentParser(Protocol):
    """Interface for document parser implementations."""

    def parse(self, document_path: str, document_id: str) -> ParsedDocument:
        """Parse a document file and return a structured document."""


class MarkdownPolicyParser:
    """Parser for markdown-based synthetic policy documents."""

    def parse(self, document_path: str, document_id: str) -> ParsedDocument:
        """Parse markdown headings into structured sections."""
        path = Path(document_path)
        raw_text = path.read_text(encoding="utf-8")

        sections: list[ParsedSection] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                self._append_section(sections, current_heading, current_lines)
                current_heading = stripped.removeprefix("## ").strip()
                current_lines = []
                continue

            if current_heading is None:
                continue

            if stripped.startswith("# "):
                continue

            current_lines.append(line)

        self._append_section(sections, current_heading, current_lines)
        return ParsedDocument(
            document_id=document_id,
            document_name=path.name,
            product_type=classify_product_type(raw_text[:4000], path.name),
            document_type=classify_document_type(raw_text[:2000], path.name),
            sections=sections,
        )

    @staticmethod
    def _append_section(
        sections: list[ParsedSection],
        heading: str | None,
        lines: list[str],
    ) -> None:
        """Store a section if it has a heading and meaningful content."""
        if heading is None:
            return

        content = "\n".join(lines).strip()
        if not content or heading in SKIPPED_SECTION_HEADINGS:
            return

        sections.append(
            ParsedSection(
                heading=heading,
                normalized_section=normalize_section(heading, content),
                content=content,
                page=1,
            )
        )


class PDFDocumentParser:
    """Parser for insurance product PDFs using PyMuPDF."""

    def parse(self, document_path: str, document_id: str) -> ParsedDocument:
        """Extract text per page and group it into insurance-friendly sections."""
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required for PDF parsing.") from exc

        path = Path(document_path)
        pdf = fitz.open(path)

        sections: list[ParsedSection] = []
        current_heading = "일반"
        current_page = 1
        current_lines: list[str] = []
        full_text_parts: list[str] = []

        for page_index, page in enumerate(pdf, start=1):
            page_text = page.get_text("text")
            full_text_parts.append(page_text)
            normalized_lines = [line.strip() for line in page_text.splitlines() if line.strip()]

            for line in normalized_lines:
                detected_heading = detect_section_heading(line)
                if detected_heading:
                    self._append_pdf_section(sections, current_heading, current_lines, current_page)
                    current_heading = detected_heading
                    current_page = page_index
                    current_lines = [line]
                    continue

                current_lines.append(line)

        self._append_pdf_section(sections, current_heading, current_lines, current_page)
        pdf.close()

        full_text = "\n".join(full_text_parts)
        return ParsedDocument(
            document_id=document_id,
            document_name=path.name,
            product_type=classify_product_type(full_text[:8000], path.name),
            document_type=classify_document_type(full_text[:4000], path.name),
            sections=sections,
        )

    @staticmethod
    def _append_pdf_section(
        sections: list[ParsedSection],
        heading: str,
        lines: list[str],
        page: int,
    ) -> None:
        """Store parsed PDF section content."""
        if not lines:
            return

        content = "\n".join(lines).strip()
        if not content:
            return

        sections.append(
            ParsedSection(
                heading=heading,
                normalized_section=normalize_section(heading, content),
                content=content,
                page=page,
            )
        )


def detect_section_heading(text: str) -> str | None:
    """Detect insurance-specific section names from a line of text."""
    stripped = text.strip()
    compact = re.sub(r"\s+", "", stripped)
    if not compact or _looks_like_sentence(stripped):
        return None

    compact = re.sub(r"^[0-9]+\.*", "", compact)
    compact = re.sub(r"^[()\[\]{}\-_.]+|[()\[\]{}\-_.:]+$", "", compact)
    for pattern, normalized_heading in SECTION_HEADING_RULES:
        if pattern.fullmatch(compact):
            return normalized_heading
    return None


def classify_section(heading: str, content: str) -> str:
    """Return the normalized section class for compatibility with existing tests."""
    return normalize_section(heading, content)


def _looks_like_sentence(text: str) -> bool:
    """Filter out narrative lines that should not be treated as headings."""
    compact = re.sub(r"\s+", "", text)
    if len(compact) > 35:
        return True
    if any(symbol in text for symbol in (".", "!", "?")):
        return True
    sentence_endings = ("입니다", "합니다", "됩니다", "있습니다", "없습니다", "않습니다", "않는다")
    return any(compact.endswith(ending) for ending in sentence_endings)
