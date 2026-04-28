"""Clause-based chunking utilities for policy documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.parser import ParsedDocument


@dataclass(frozen=True)
class RAGChunk:
    """Atomic retrieval unit with metadata."""

    document_name: str
    section: str
    page: int
    content: str


def chunk_document(document: ParsedDocument) -> list[RAGChunk]:
    """Split a parsed document into clause-level retrieval chunks."""
    chunks: list[RAGChunk] = []

    for section in document.sections:
        for clause in _split_section_into_clauses(section.content):
            chunks.append(
                RAGChunk(
                    document_name=document.document_name,
                    section=section.heading,
                    page=section.page,
                    content=clause,
                )
            )

    return chunks


def _split_section_into_clauses(content: str) -> list[str]:
    """Split section text by numbered items, bullet items, and paragraphs."""
    clauses: list[str] = []
    current_lines: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            _append_clause(clauses, current_lines)
            current_lines = []
            continue

        if _is_clause_boundary(line):
            _append_clause(clauses, current_lines)
            current_lines = [line]
            continue

        current_lines.append(line)

    _append_clause(clauses, current_lines)
    return clauses


def _is_clause_boundary(line: str) -> bool:
    """Return True when a line starts a new logical clause."""
    return bool(
        re.match(r"^\d+\.\s+", line)
        or re.match(r"^-\s+", line)
        or re.match(r"^###\s+", line)
    )


def _append_clause(clauses: list[str], lines: list[str]) -> None:
    """Normalize and store a clause block."""
    if not lines:
        return

    clause = " ".join(part.strip() for part in lines if part.strip())
    clause = re.sub(r"\s+", " ", clause).strip()
    if clause:
        clauses.append(clause)
