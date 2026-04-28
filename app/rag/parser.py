"""Policy document parser implementations for the RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SKIPPED_SECTION_HEADINGS = {"Document Notice", "Product Overview", "Example Test Queries"}


@dataclass(frozen=True)
class ParsedSection:
    """A logical section extracted from a policy document."""

    heading: str
    content: str
    page: int = 1


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed policy document with normalized sections."""

    document_name: str
    sections: list[ParsedSection]


class DocumentParser(Protocol):
    """Interface for policy document parser implementations."""

    def parse(self, document_path: str) -> ParsedDocument:
        """Parse a document file and return a structured document."""


class MarkdownPolicyParser:
    """Parser for markdown-based synthetic policy documents."""

    def parse(self, document_path: str) -> ParsedDocument:
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
        return ParsedDocument(document_name=path.name, sections=sections)

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
        if not content:
            return
        if heading in SKIPPED_SECTION_HEADINGS:
            return

        sections.append(ParsedSection(heading=heading, content=content, page=1))
