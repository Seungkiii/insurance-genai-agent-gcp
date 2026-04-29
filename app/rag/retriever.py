"""Retrieval interfaces and implementations."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Protocol

from app.rag.chunker import RAGChunk
from app.rag.search_profiles import SearchProfile
from app.services.gcp_storage_service import StorageService

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
    """Retrieved chunk with scoring diagnostics."""

    chunk: RAGChunk
    score: float
    embedding_score: float | None = None
    hybrid_score: float | None = None


class ChunkRetriever(Protocol):
    """Interface for retrieval implementations."""

    def retrieve(self, question: str, chunks: list[RAGChunk], top_k: int = 3) -> list[RetrievalResult]:
        """Return the most relevant chunks for the given question."""


class EmbeddingRetriever(Protocol):
    """Interface for embedding-based retrieval implementations."""

    def retrieve(
        self,
        query_embedding: list[float],
        document_ids: list[str],
        top_k: int = 5,
        question: str | None = None,
        search_profile: SearchProfile | None = None,
        top_k_per_document: int = 3,
    ) -> list[RetrievalResult]:
        """Return the most relevant chunks using vector similarity."""


class KeywordChunkRetriever:
    """Simple keyword-overlap retriever for local synthetic policy lookups."""

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
            results.append(RetrievalResult(chunk=chunk, score=score, embedding_score=score, hybrid_score=score))

        results.sort(key=lambda item: item.score, reverse=True)
        return _prioritize_results(query_tokens, results, top_k)


class GcsEmbeddingRetriever:
    """Load stored embedding artifacts from GCS and perform hybrid retrieval."""

    def __init__(self, storage_service: StorageService, bucket_name: str) -> None:
        self.storage_service = storage_service
        self.bucket_name = bucket_name

    def retrieve(
        self,
        query_embedding: list[float],
        document_ids: list[str],
        top_k: int = 5,
        question: str | None = None,
        search_profile: SearchProfile | None = None,
        top_k_per_document: int = 3,
    ) -> list[RetrievalResult]:
        """Search document embedding artifacts using cosine similarity plus metadata boosts."""
        candidates: list[RetrievalResult] = []
        query_tokens = _tokenize(question or "")

        for document_id in document_ids:
            gcs_uri = f"gs://{self.bucket_name}/indexes/{document_id}/embeddings.jsonl"
            try:
                payload = self.storage_service.download_bytes(gcs_uri).decode("utf-8")
            except Exception:  # noqa: BLE001
                continue

            for line in payload.splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                chunk = RAGChunk(
                    document_id=record["document_id"],
                    document_name=record["document_name"],
                    document_type=record.get("document_type", "unknown"),
                    product_type=record.get("product_type", "unknown"),
                    chunk_id=record["chunk_id"],
                    page=int(record["page"]),
                    section=record["section"],
                    normalized_section=record.get("normalized_section", "miscellaneous"),
                    content=record["content"],
                )
                embedding = record.get("embedding", [])
                embedding_score = cosine_similarity(query_embedding, embedding)
                hybrid_score = compute_hybrid_score(
                    chunk=chunk,
                    embedding_score=embedding_score,
                    query_tokens=query_tokens,
                    search_profile=search_profile,
                )
                candidates.append(
                    RetrievalResult(
                        chunk=chunk,
                        score=hybrid_score,
                        embedding_score=round(embedding_score, 4),
                        hybrid_score=round(hybrid_score, 4),
                    )
                )

        candidates.sort(key=lambda item: item.hybrid_score or item.score, reverse=True)
        return _select_diverse_results(candidates, top_k=top_k, top_k_per_document=top_k_per_document)


def compute_hybrid_score(
    *,
    chunk: RAGChunk,
    embedding_score: float,
    query_tokens: set[str],
    search_profile: SearchProfile | None,
) -> float:
    """Combine similarity with metadata-aware retrieval boosts."""
    section_boost = 0.0
    document_type_boost = 0.0
    product_type_boost = 0.0
    exact_keyword_boost = _compute_exact_keyword_boost(query_tokens, chunk)
    negative_section_penalty = 0.0

    if search_profile:
        if chunk.normalized_section in search_profile.positive_sections:
            section_boost += 0.18
        if chunk.normalized_section in search_profile.negative_sections:
            negative_section_penalty += 0.18
        if chunk.document_type in search_profile.preferred_document_types:
            document_type_boost += 0.08
        if chunk.product_type in search_profile.product_type_hints:
            product_type_boost += 0.08

    hybrid_score = (
        embedding_score
        + section_boost
        + document_type_boost
        + product_type_boost
        + exact_keyword_boost
        - negative_section_penalty
    )
    return max(0.0, min(0.9999, hybrid_score))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _tokenize(text: str) -> set[str]:
    """Extract normalized Korean/English tokens for keyword matching."""
    tokens = {
        _normalize_token(token)
        for token in re.findall(r"[0-9A-Za-z가-힣]+", text)
        if len(token) > 1
    }
    return {token for token in tokens if token and token not in STOPWORDS}


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
    exact_phrase_bonus = _compute_exact_keyword_boost(query_tokens, chunk)
    return overlap_score + section_bonus + exact_phrase_bonus


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


def _compute_exact_keyword_boost(query_tokens: set[str], chunk: RAGChunk) -> float:
    normalized_content = chunk.content.lower()
    normalized_section = f"{chunk.section} {chunk.normalized_section}".lower()
    boost = 0.0
    for token in query_tokens:
        if token in normalized_section:
            boost += 0.03
        elif token in normalized_content:
            boost += 0.015
    return min(boost, 0.16)


def _select_diverse_results(
    results: list[RetrievalResult],
    *,
    top_k: int,
    top_k_per_document: int,
) -> list[RetrievalResult]:
    """Greedily select high-scoring yet diverse results across documents and sections."""
    selected: list[RetrievalResult] = []
    per_document_counts: dict[str, int] = {}
    seen_page_keys: set[tuple[str, int]] = set()
    seen_section_keys: set[tuple[str, str]] = set()

    for result in results:
        if len(selected) >= top_k:
            break
        document_count = per_document_counts.get(result.chunk.document_id, 0)
        if document_count >= top_k_per_document:
            continue

        penalty = 0.0
        if (result.chunk.document_id, result.chunk.page) in seen_page_keys:
            penalty += 0.05
        if (result.chunk.document_id, result.chunk.normalized_section) in seen_section_keys:
            penalty += 0.07

        adjusted_hybrid = (result.hybrid_score or result.score) - penalty
        if adjusted_hybrid <= 0:
            continue

        selected.append(
            RetrievalResult(
                chunk=result.chunk,
                score=round(adjusted_hybrid, 4),
                embedding_score=result.embedding_score,
                hybrid_score=round(adjusted_hybrid, 4),
            )
        )
        per_document_counts[result.chunk.document_id] = document_count + 1
        seen_page_keys.add((result.chunk.document_id, result.chunk.page))
        seen_section_keys.add((result.chunk.document_id, result.chunk.normalized_section))

    return selected
