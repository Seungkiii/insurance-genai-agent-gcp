"""Retrieval interfaces and implementations."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.rag.chunker import RAGChunk
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

MAJOR_COVERAGE_TERMS = (
    "주요 보장",
    "주요보장",
    "보장 내용",
    "보장내용",
)
MAJOR_COVERAGE_EXPANSION_TERMS = (
    "보험금 지급사유",
    "보험급부",
    "지급금액",
    "고도재해장해보험금",
    "생존연금",
    "연금지급형태",
    "연금개시전",
    "연금개시후",
)
PRIORITY_SECTIONS_FOR_MAJOR_COVERAGE = {
    "보험금 지급사유",
    "보험급부",
    "지급금액",
    "고도재해장해보험금",
    "생존연금",
    "연금지급형태",
    "연금개시전",
    "연금개시후",
    "상품 특이사항",
    "보장하는 손해",
}
PENALIZED_SECTIONS_FOR_MAJOR_COVERAGE = {"보험료", "수수료", "해약환급금", "환급률"}
PENALTY_QUERY_TERMS = ("보험료", "비용", "수수료", "환급금", "해약환급금", "환급률")


@dataclass(frozen=True)
class RetrievalResult:
    """Retrieved chunk with a relevance score."""

    chunk: RAGChunk
    score: float


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
    ) -> list[RetrievalResult]:
        """Return the most relevant chunks using vector similarity."""


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


class GcsEmbeddingRetriever:
    """Load stored embedding artifacts from GCS and perform cosine similarity search."""

    def __init__(self, storage_service: StorageService, bucket_name: str) -> None:
        self.storage_service = storage_service
        self.bucket_name = bucket_name

    def retrieve(
        self,
        query_embedding: list[float],
        document_ids: list[str],
        top_k: int = 5,
        question: str | None = None,
    ) -> list[RetrievalResult]:
        """Search document embedding artifacts using cosine similarity."""
        candidates: list[RetrievalResult] = []

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
                embedding = record.get("embedding", [])
                score = cosine_similarity(query_embedding, embedding)
                chunk = RAGChunk(
                    document_id=record["document_id"],
                    document_name=record["document_name"],
                    chunk_id=record["chunk_id"],
                    page=int(record["page"]),
                    section=record["section"],
                    content=record["content"],
                )
                adjusted_score = _adjust_embedding_score(question or "", chunk, score)
                candidates.append(RetrievalResult(chunk=chunk, score=adjusted_score))

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_k]


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


def expand_query(question: str) -> str:
    """Expand major coverage questions with coverage-specific search vocabulary."""
    if not is_major_coverage_question(question):
        return question
    suffix = " ".join(MAJOR_COVERAGE_EXPANSION_TERMS)
    return f"{question} {suffix}"


def is_major_coverage_question(question: str) -> bool:
    """Return True when the question asks for core guarantees or benefits."""
    normalized = re.sub(r"\s+", "", question)
    return any(term.replace(" ", "") in normalized for term in MAJOR_COVERAGE_TERMS)


def has_cost_or_refund_intent(question: str) -> bool:
    """Return True when the question is explicitly about premium or refund topics."""
    return any(term in question for term in PENALTY_QUERY_TERMS)


def has_major_coverage_alignment(results: list[RetrievalResult]) -> bool:
    """Return True when the retrieved sections match a major coverage question."""
    top_results = results[:3]
    return any(
        result.chunk.section in PRIORITY_SECTIONS_FOR_MAJOR_COVERAGE and result.score >= 0.4
        for result in top_results
    )


def _adjust_embedding_score(question: str, chunk: RAGChunk, base_score: float) -> float:
    """Adjust cosine similarity with section-aware boosts."""
    adjusted_score = base_score
    normalized_content = re.sub(r"\s+", "", chunk.content)
    semantic_match = base_score >= 0.05

    if is_major_coverage_question(question):
        if semantic_match and chunk.section in PRIORITY_SECTIONS_FOR_MAJOR_COVERAGE:
            adjusted_score += 0.18
        elif semantic_match and chunk.section == "보장" and any(
            term in normalized_content for term in ("보험금지급사유", "보험급부", "연금지급형태")
        ):
            adjusted_score += 0.1

        if chunk.section in PENALIZED_SECTIONS_FOR_MAJOR_COVERAGE and not has_cost_or_refund_intent(question):
            adjusted_score -= 0.2

        if semantic_match and any(
            term in normalized_content for term in ("보험금지급사유", "보험급부", "지급금액", "생존연금")
        ):
            adjusted_score += 0.06
        if any(term in normalized_content for term in ("보험료", "계약관리비용", "해약환급금", "환급률")) and not has_cost_or_refund_intent(question):
            adjusted_score -= 0.08

    return max(0.0, min(0.9999, adjusted_score))
