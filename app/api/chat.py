"""Chat router backed by indexed-document RAG."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.rag.citation import build_citations
from app.rag.embedder import Embedder, VertexAIEmbedder
from app.rag.generator import GeminiAnswerGenerator, build_low_confidence_answer
from app.rag.retriever import (
    GcsEmbeddingRetriever,
    RetrievalResult,
    expand_query,
    has_cost_or_refund_intent,
    has_major_coverage_alignment,
    is_major_coverage_question,
)
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.firestore_service import FirestoreService, GCPFirestoreService
from app.services.gcp_storage_service import GCPStorageService, StorageService
from app.services.vertex_ai_service import VertexAIEmbeddingService, VertexAIGenerationService

router = APIRouter()

GUARDRAIL_DISCLAIMER = "보험금 지급 여부는 실제 약관, 심사 기준, 사고 사실관계 확인 이후 최종 판단됩니다."


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    """Return the storage service implementation."""
    if not settings.gcs_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GCS_BUCKET_NAME is not configured.",
        )
    return GCPStorageService(bucket_name=settings.gcs_bucket_name)


def get_firestore_service(settings: Settings = Depends(get_settings)) -> FirestoreService:
    """Return the Firestore service implementation."""
    if not settings.firestore_database:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FIRESTORE_DATABASE is not configured.",
        )
    return GCPFirestoreService(database=settings.firestore_database)


def get_query_embedder(settings: Settings = Depends(get_settings)) -> Embedder:
    """Return the query embedding implementation."""
    if not (
        settings.vertex_ai_project_id
        and settings.effective_embedding_location
        and settings.embedding_model_name
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding runtime settings are not configured.",
        )

    service = VertexAIEmbeddingService(
        project_id=settings.vertex_ai_project_id,
        location=settings.effective_embedding_location or "",
        model_name=settings.embedding_model_name,
    )
    return VertexAIEmbedder(service)


def get_answer_generator(settings: Settings = Depends(get_settings)) -> GeminiAnswerGenerator:
    """Return the Gemini answer generator."""
    if not (
        settings.vertex_ai_project_id
        and settings.effective_generation_location
        and settings.gemini_model_name
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini runtime settings are not configured.",
        )

    service = VertexAIGenerationService(
        project_id=settings.vertex_ai_project_id,
        location=settings.effective_generation_location or "",
        model_name=settings.gemini_model_name,
    )
    return GeminiAnswerGenerator(service)


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    storage_service: StorageService = Depends(get_storage_service),
    firestore_service: FirestoreService = Depends(get_firestore_service),
    embedder: Embedder = Depends(get_query_embedder),
    generator: GeminiAnswerGenerator = Depends(get_answer_generator),
) -> ChatResponse:
    """Answer a question using indexed document embeddings and Gemini generation."""
    started_at = time.perf_counter()

    retriever = GcsEmbeddingRetriever(storage_service, settings.gcs_bucket_name or "")
    query_embedding = embedder.embed_texts([request.question])[0]
    results = retriever.retrieve(
        query_embedding,
        request.document_ids,
        top_k=request.top_k,
        question=request.question,
    )
    results = _maybe_retry_major_coverage_search(
        question=request.question,
        document_ids=request.document_ids,
        top_k=request.top_k,
        retriever=retriever,
        embedder=embedder,
        initial_results=results,
    )
    citations = build_citations(results)
    confidence_score = _compute_confidence_score(request.question, results)
    top_score = results[0].score if results else 0.0

    if not results or top_score < 0.45 or confidence_score < 0.45:
        answer = build_low_confidence_answer()
        follow_up_questions = [
            "보험상품명, 보장 항목, 사고 내용, 청구 서류 종류 중 어떤 정보를 더 알려주실 수 있나요?"
        ]
    else:
        answer = generator.generate(request.question, results)
        follow_up_questions = ["다른 약관 조항이나 청구 서류 항목도 함께 확인해드릴까요?"]

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    firestore_service.save_chat_interaction(
        session_id=request.session_id,
        user_message=request.question,
        assistant_answer=answer,
        citations=[citation.model_dump() for citation in citations],
        latency_ms=latency_ms,
    )

    return ChatResponse(
        session_id=request.session_id,
        intent="policy_qa",
        answer=answer,
        citations=citations,
        confidence_score=confidence_score,
        follow_up_questions=follow_up_questions,
        disclaimer=GUARDRAIL_DISCLAIMER,
    )


def _maybe_retry_major_coverage_search(
    *,
    question: str,
    document_ids: list[str],
    top_k: int,
    retriever: GcsEmbeddingRetriever,
    embedder: Embedder,
    initial_results: list[RetrievalResult],
) -> list[RetrievalResult]:
    """Retry retrieval with expanded coverage terms when the first pass is misaligned."""
    if not is_major_coverage_question(question):
        return initial_results
    if has_major_coverage_alignment(initial_results):
        return initial_results

    expanded_query = expand_query(question)
    expanded_embedding = embedder.embed_texts([expanded_query])[0]
    fallback_results = retriever.retrieve(
        expanded_embedding,
        document_ids,
        top_k=top_k,
        question=expanded_query,
    )
    if not fallback_results:
        return initial_results

    merged: dict[str, RetrievalResult] = {}
    for result in initial_results + fallback_results:
        existing = merged.get(result.chunk.chunk_id)
        if existing is None or result.score > existing.score:
            merged[result.chunk.chunk_id] = result

    reranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    return reranked[:top_k]


def _compute_confidence_score(question: str, results: list[RetrievalResult]) -> float:
    """Combine top score, citation count, and average score into a bounded confidence score."""
    if not results:
        return 0.0

    scores = [float(result.score) for result in results]
    top_score = max(scores)
    average_score = sum(scores) / len(scores)
    citation_count = len(scores)
    section_alignment = _compute_section_alignment(question, results)

    confidence = (top_score * 0.3) + (average_score * 0.25) + (section_alignment * 0.35) + min(
        citation_count / 20.0,
        0.1,
    )
    return round(min(0.99, confidence), 2)


def _compute_section_alignment(question: str, results: list[RetrievalResult]) -> float:
    """Measure how well retrieved sections match the question intent."""
    if not results:
        return 0.0

    if is_major_coverage_question(question):
        aligned = sum(
            1
            for result in results[:5]
            if result.chunk.section in {"상품 특이사항", "보험금 지급사유", "보험급부", "지급금액", "고도재해장해보험금", "생존연금", "연금지급형태", "연금개시전", "연금개시후", "보장하는 손해"}
        )
        penalized = sum(
            1
            for result in results[:5]
            if result.chunk.section in {"보험료", "수수료", "해약환급금", "환급률"}
        )
        if has_cost_or_refund_intent(question):
            penalized = 0
        return max(0.0, min(1.0, (aligned * 0.3) + 0.2 - (penalized * 0.2)))

    return 0.2
