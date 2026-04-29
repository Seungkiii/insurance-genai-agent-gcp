"""Document parsers for the RAG pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SKIPPED_SECTION_HEADINGS = {"Document Notice", "Product Overview", "Example Test Queries"}
SECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^상품의?특이사항$"), "상품 특이사항"),
    (re.compile(r"^보장하는손해$"), "보장하는 손해"),
    (re.compile(r"^보험금지급사유$"), "보험금 지급사유"),
    (re.compile(r"^보험금지급$"), "보험금 지급사유"),
    (re.compile(r"^보험급부$"), "보험급부"),
    (re.compile(r"^지급금액$"), "지급금액"),
    (re.compile(r"^고도재해장해보험금$"), "고도재해장해보험금"),
    (re.compile(r"^생존연금$"), "생존연금"),
    (re.compile(r"^연금지급형태$"), "연금지급형태"),
    (re.compile(r"^연금개시전$"), "연금개시전"),
    (re.compile(r"^연금개시후$"), "연금개시후"),
    (re.compile(r"^주요보장내용$"), "보장"),
    (re.compile(r"^보장내용$"), "보장"),
    (re.compile(r"^보장$"), "보장"),
    (re.compile(r"^지급하지않는사유$"), "지급하지 않는 사유"),
    (re.compile(r"^보장하지않는사유$"), "지급하지 않는 사유"),
    (re.compile(r"^보장하지않는손해$"), "지급하지 않는 사유"),
    (re.compile(r"^면책$"), "지급하지 않는 사유"),
    (re.compile(r"^특약$"), "특약"),
    (re.compile(r"^해약환급금$"), "해약환급금"),
    (re.compile(r"^환급률$"), "환급률"),
    (re.compile(r"^보험료$"), "보험료"),
    (re.compile(r"^수수료$"), "수수료"),
    (re.compile(r"^청구서류$"), "청구 서류"),
    (re.compile(r"^청구$"), "청구 서류"),
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

        normalized_heading = classify_section(heading, content)
        sections.append(ParsedSection(heading=normalized_heading, content=content, page=page))


def detect_section_heading(text: str) -> str | None:
    """Detect insurance-specific section names from a line of text."""
    stripped = text.strip()
    compact = re.sub(r"\s+", "", stripped)
    if not compact or _looks_like_sentence(stripped):
        return None

    compact = re.sub(r"^[0-9]+\.*", "", compact)
    compact = re.sub(r"^[()\[\]{}\-_.]+|[()\[\]{}\-_.:]+$", "", compact)
    for pattern, normalized_heading in SECTION_PATTERNS:
        if pattern.fullmatch(compact):
            return normalized_heading
    return None


def classify_section(heading: str, content: str) -> str:
    """Refine generic headings into business-meaningful insurance sections."""
    normalized_heading = heading.strip()
    text = re.sub(r"\s+", "", f"{heading} {content}")

    if "상품의특이사항" in text:
        return "상품 특이사항"
    if "보험금지급사유" in text or "지급사유" in text:
        return "보험금 지급사유"
    if "보험급부" in text:
        return "보험급부"
    if "지급금액" in text:
        return "지급금액"
    if "고도재해장해보험금" in text:
        return "고도재해장해보험금"
    if "생존연금" in text:
        return "생존연금"
    if "연금지급형태" in text:
        return "연금지급형태"
    if "연금개시전" in text:
        return "연금개시전"
    if "연금개시후" in text:
        return "연금개시후"
    if "해약환급금" in text:
        return "해약환급금"
    if "환급률" in text:
        return "환급률"
    if "수수료" in text or "계약관리비용" in text:
        return "수수료"
    if "보험료" in text:
        return "보험료"
    if (
        "미래의수익을보장하는것은아닙니다" in text
        or "미래수익을보장하지않습니다" in text
        or "환급률" in text
    ) and normalized_heading == "보장":
        return "환급률"
    return normalized_heading


def _looks_like_sentence(text: str) -> bool:
    """Filter out narrative lines that should not be treated as headings."""
    compact = re.sub(r"\s+", "", text)
    sentence_endings = ("입니다", "합니다", "됩니다", "있습니다", "없습니다", "않습니다", "않는다", "됩니다.")
    if len(compact) > 30:
        return True
    if any(compact.endswith(ending) for ending in sentence_endings):
        return True
    if any(symbol in text for symbol in (".", "!", "?")):
        return True
    return False
