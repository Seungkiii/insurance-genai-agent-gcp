"""Chunking utilities for policy and product documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.parser import ParsedDocument

DEFAULT_TARGET_CHUNK_SIZE = 1000
DEFAULT_MIN_CHUNK_SIZE = 800
DEFAULT_MAX_CHUNK_SIZE = 1200
DEFAULT_OVERLAP_SIZE = 100


@dataclass(frozen=True)
class RAGChunk:
    """Atomic retrieval unit with metadata."""

    document_id: str
    document_name: str
    document_type: str
    product_type: str
    chunk_id: str
    page: int
    end_page: int
    section: str
    normalized_section: str
    content: str


def chunk_document(
    document: ParsedDocument,
    target_chunk_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
    overlap_size: int = DEFAULT_OVERLAP_SIZE,
) -> list[RAGChunk]:
    """Split a parsed document into retrieval chunks with overlap."""
    chunks: list[RAGChunk] = []
    chunk_index = 1

    for section in document.sections:
        normalized_content = _normalize_text(section.content)
        if not normalized_content:
            continue

        for part in _split_into_windows(
            normalized_content,
            target_chunk_size=target_chunk_size,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            overlap_size=overlap_size,
        ):
            chunks.append(
                RAGChunk(
                    document_id=document.document_id,
                    document_name=document.document_name,
                    document_type=document.document_type,
                    product_type=document.product_type,
                    chunk_id=f"{document.document_id}-chunk-{chunk_index:04d}",
                    page=section.page,
                    end_page=section.end_page,
                    section=section.heading,
                    normalized_section=section.normalized_section,
                    content=part,
                )
            )
            chunk_index += 1

    return chunks


def _split_into_windows(
    content: str,
    target_chunk_size: int,
    min_chunk_size: int,
    max_chunk_size: int,
    overlap_size: int,
) -> list[str]:
    """Split text into 800-1200 character windows with overlap."""
    segments = _split_content_into_segments(content)
    if not segments:
        return []

    windows: list[str] = []
    current = ""

    for segment in segments:
        candidate = f"{current} {segment}".strip() if current else segment
        if len(candidate) <= max_chunk_size:
            current = candidate
            continue

        if current:
            windows.append(current)
            current = _with_overlap(current, segment, overlap_size)
            if len(current) > max_chunk_size:
                windows.extend(_force_split(current, max_chunk_size, overlap_size))
                current = ""
        else:
            forced_parts = _force_split(segment, max_chunk_size, overlap_size)
            windows.extend(forced_parts[:-1])
            current = forced_parts[-1]

    if current:
        if windows and len(current) < min_chunk_size:
            merged = f"{windows[-1]} {current}".strip()
            if len(merged) <= max_chunk_size + overlap_size:
                windows[-1] = merged
            else:
                windows.append(current)
        else:
            windows.append(current)

    return [_normalize_text(window) for window in windows if _normalize_text(window)]


def _split_content_into_segments(content: str) -> list[str]:
    """Split text by clauses and sentence boundaries for chunk assembly."""
    segments: list[str] = []
    for block in re.split(r"\n{2,}", content):
        normalized_block = _normalize_text(block)
        if not normalized_block:
            continue

        if len(normalized_block) <= DEFAULT_MAX_CHUNK_SIZE:
            segments.append(normalized_block)
            continue

        sentence_parts = re.split(r"(?<=[.!?다])\s+", normalized_block)
        segments.extend(part.strip() for part in sentence_parts if part.strip())

    return segments


def _force_split(content: str, max_chunk_size: int, overlap_size: int) -> list[str]:
    """Split a long text chunk by raw character length when needed."""
    parts: list[str] = []
    start = 0
    step = max_chunk_size - overlap_size
    if step <= 0:
        step = max_chunk_size

    while start < len(content):
        end = start + max_chunk_size
        parts.append(content[start:end].strip())
        start += step

    return [part for part in parts if part]


def _with_overlap(current: str, next_segment: str, overlap_size: int) -> str:
    """Carry over the tail of the previous chunk into the next chunk."""
    overlap = current[-overlap_size:] if len(current) > overlap_size else current
    return _normalize_text(f"{overlap} {next_segment}")


def _normalize_text(text: str) -> str:
    """Normalize whitespace while preserving readable content."""
    return re.sub(r"\s+", " ", text).strip()
