"""Keyword-based retrieval interfaces and implementations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.rag.chunker import RAGChunk

STOPWORDS = {
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
    "도",
    "과",
    "와",
    "로",
    "으로",
    "및",
    "좀",
    "수",
    "때",
    "경우",
    "기준",
    "관련",
    "대한",
    "에서",
    "하는",
    "있나요",
    "알려줘",
    "설명해줘",
    "무엇인가요",
}

PARTICLE_SUFFIXES = (
    "인가요",
    "있나요",
    "인가",
    "까요",
    "으로",
    "에서",
    "에게",
    "처럼",
    "하는",
    "했다",
    "합니다",
    "되는",
    "되나요",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
    "도",
    "과",
    "와",
    "로",
)


@dataclass(frozen=True)
class RetrievalResult:
    """Retrieved chunk with a lightweight relevance score."""

    chunk: RAGChunk
    score: float


class ChunkRetriever(Protocol):
    """Interface for retrieval implementations."""

    def retrieve(self, question: str, chunks: list[RAGChunk], top_k: int = 3) -> list[RetrievalResult]:
        """Return the most relevant chunks for the given question."""


class KeywordChunkRetriever:
    """Simple keyword-overlap retriever for cost-efficient MVP use."""

    def retrieve(self, question: str, chunks: list[RAGChunk], top_k: int = 3) -> list[RetrievalResult]:
        """Rank chunks by overlap between question tokens and chunk tokens."""
        query_tokens = _tokenize(question)
        if not query_tokens:
            return []

        results: list[RetrievalResult] = []
        for chunk in chunks:
            score = _score_chunk(query_tokens, chunk)
            if score <= 0:
                continue
            results.append(RetrievalResult(chunk=chunk, score=score))

        results.sort(key=lambda item: item.score, reverse=True)
        return _prioritize_results(query_tokens, results, top_k)


def _tokenize(text: str) -> set[str]:
    """Extract normalized Korean/English tokens for keyword matching."""
    tokens = {
        _normalize_token(token)
        for token in re.findall(r"[0-9A-Za-z가-힣]+", text)
        if len(token) > 1
    }
    return {token for token in tokens if token not in STOPWORDS}


def _normalize_token(token: str) -> str:
    """Trim lightweight Korean particles and normalize case."""
    normalized = token.lower()
    for suffix in PARTICLE_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 1:
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _score_chunk(query_tokens: set[str], chunk: RAGChunk) -> float:
    """Compute a simple lexical relevance score."""
    content_tokens = _tokenize(chunk.content)
    section_tokens = _tokenize(chunk.section)

    overlap = query_tokens & content_tokens
    section_overlap = query_tokens & section_tokens
    if not overlap and not section_overlap:
        return 0.0

    overlap_score = float(len(overlap))
    section_bonus = float(len(section_overlap)) * 0.5
    exact_phrase_bonus = 0.0

    normalized_question = " ".join(sorted(query_tokens))
    normalized_content = chunk.content.lower()
    for token in query_tokens:
        if token in normalized_content:
            exact_phrase_bonus += 0.1

    if normalized_question and normalized_question in normalized_content:
        exact_phrase_bonus += 1.0

    list_item_bonus = 0.0
    if "서류" in query_tokens and re.match(r"^(\d+\.|-)\s+", chunk.content):
        list_item_bonus += 0.5

    return overlap_score + section_bonus + exact_phrase_bonus + list_item_bonus


def _prioritize_results(
    query_tokens: set[str],
    results: list[RetrievalResult],
    top_k: int,
) -> list[RetrievalResult]:
    """Prefer actionable list items for document-oriented questions."""
    if not results:
        return []

    selected: list[RetrievalResult] = []
    seen: set[tuple[str, str, int, str]] = set()

    def add_result(result: RetrievalResult) -> None:
        key = (
            result.chunk.document_name,
            result.chunk.section,
            result.chunk.page,
            result.chunk.content,
        )
        if key in seen or len(selected) >= top_k:
            return
        seen.add(key)
        selected.append(result)

    add_result(results[0])

    if "서류" in query_tokens:
        top_section = results[0].chunk.section
        for result in results:
            if result.chunk.section != top_section:
                continue
            if not re.match(r"^(\d+\.|-)\s+", result.chunk.content):
                continue
            add_result(result)

    for result in results:
        add_result(result)

    return selected
