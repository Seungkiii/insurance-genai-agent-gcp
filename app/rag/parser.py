"""Document parsers for the RAG pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SKIPPED_SECTION_HEADINGS = {"Document Notice", "Product Overview", "Example Test Queries"}
SECTION_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("보장하는 손해", "보장하는 손해"),
    ("보장", "보장"),
    ("보험금 지급", "보험금 지급"),
    ("지급하지 않는 사유", "지급하지 않는 사유"),
    ("보장하지 않는 사유", "지급하지 않는 사유"),
    ("보장하지 않는 손해", "지급하지 않는 사유"),
    ("면책", "지급하지 않는 사유"),
    ("특약", "특약"),
    ("해약환급금", "해약환급금"),
    ("보험료", "보험료"),
    ("청구 서류", "청구 서류"),
    ("청구", "청구 서류"),
)


@dataclass(frozen=True)
class ParsedSection:
    """A logical section extracted from a document."""

    heading: str
    content: str
    page: int


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed document with normalized sections."""

    document_id: str
    document_name: str
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
        return ParsedDocument(document_id=document_id, document_name=path.name, sections=sections)

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

        sections.append(ParsedSection(heading=heading, content=content, page=1))


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

        for page_index, page in enumerate(pdf, start=1):
            page_text = page.get_text("text")
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
        return ParsedDocument(document_id=document_id, document_name=path.name, sections=sections)

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

        sections.append(ParsedSection(heading=heading, content=content, page=page))


def detect_section_heading(text: str) -> str | None:
    """Detect insurance-specific section names from a line of text."""
    compact = re.sub(r"\s+", "", text)
    for keyword, normalized_heading in SECTION_KEYWORDS:
        if keyword.replace(" ", "") in compact:
            return normalized_heading
    return None
