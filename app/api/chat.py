"""Chat router backed by indexed-document RAG."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.rag.citation import build_citations
from app.rag.confidence import compute_confidence_score
from app.rag.embedder import Embedder, VertexAIEmbedder
from app.rag.generator import GeminiAnswerGenerator, build_low_confidence_answer
from app.rag.retriever import GcsEmbeddingRetriever, RetrievalResult
from app.rag.search_profiles import SearchProfile, build_expanded_query, classify_search_profile
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

    target_documents = _resolve_target_documents(request.document_ids, firestore_service)
    product_types = [record.get("product_type", "unknown") for record in target_documents]
    search_profile = classify_search_profile(request.question)
    expanded_query = build_expanded_query(request.question, search_profile, product_types=product_types)
    tool_trace = [
        f"profile={search_profile.name}",
        f"expanded_query={expanded_query}",
        f"document_count={len(target_documents)}",
    ]

    retriever = GcsEmbeddingRetriever(storage_service, settings.gcs_bucket_name or "")
    query_embedding = embedder.embed_texts([expanded_query])[0]
    results = retriever.retrieve(
        query_embedding,
        [record["document_id"] for record in target_documents],
        top_k=request.top_k,
        question=request.question,
        search_profile=search_profile,
        top_k_per_document=request.top_k_per_document,
    )

    fallback_required = _requires_fallback(results, search_profile)
    if fallback_required and search_profile.expansion_terms:
        fallback_query = build_expanded_query(
            request.question,
            search_profile,
            product_types=product_types,
            max_terms=10,
            include_product_context=True,
        )
        fallback_embedding = embedder.embed_texts([fallback_query])[0]
        fallback_results = retriever.retrieve(
            fallback_embedding,
            [record["document_id"] for record in target_documents],
            top_k=request.top_k,
            question=fallback_query,
            search_profile=search_profile,
            top_k_per_document=request.top_k_per_document,
        )
        if fallback_results:
            results = fallback_results
            tool_trace.append("fallback_retrieval=true")

    citations = build_citations(results)
    provisional_answer = None
    if not results:
        provisional_answer = build_low_confidence_answer()
    confidence_score = compute_confidence_score(
        results=results,
        profile=search_profile,
        fallback_required=fallback_required,
        answer=provisional_answer,
    )

    if not results or confidence_score < 0.45:
        answer = provisional_answer or build_low_confidence_answer()
        follow_up_questions = [
            "보장 내용, 지급 조건, 보험료, 해약환급금, 청구 서류 중 어떤 항목을 더 자세히 확인할까요?"
        ]
    else:
        answer = generator.generate(
            request.question,
            results,
            search_profile=search_profile,
            fallback_required=fallback_required,
        )
        confidence_score = compute_confidence_score(
            results=results,
            profile=search_profile,
            fallback_required=fallback_required,
            answer=answer,
        )
        follow_up_questions = ["다른 보장 항목이나 약관 기준도 함께 확인해드릴까요?"]

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
        search_profile=search_profile.name,
        confidence_score=confidence_score,
        fallback_required=fallback_required,
        follow_up_questions=follow_up_questions,
        tool_trace=tool_trace,
        disclaimer=GUARDRAIL_DISCLAIMER,
    )


def _resolve_target_documents(
    requested_document_ids: list[str],
    firestore_service: FirestoreService,
) -> list[dict[str, object]]:
    """Resolve chat target documents from explicit ids or all indexed documents."""
    if requested_document_ids:
        documents: list[dict[str, object]] = []
        for document_id in requested_document_ids:
            record = firestore_service.get_document(document_id)
            if record is not None:
                documents.append(record)
        return documents

    return [
        record
        for record in firestore_service.list_documents()
        if record.get("status") == "indexed"
    ]


def _requires_fallback(results: list[RetrievalResult], search_profile: SearchProfile) -> bool:
    """Return True when retrieval mostly misses the profile's positive sections."""
    if not results:
        return True
    top_result = results[0]
    if (top_result.hybrid_score or top_result.score) < 0.45:
        return True
    if top_result.chunk.normalized_section in search_profile.negative_sections:
        return True
    positive_matches = sum(
        1 for result in results[:5] if result.chunk.normalized_section in search_profile.positive_sections
    )
    negative_matches = sum(
        1 for result in results[:5] if result.chunk.normalized_section in search_profile.negative_sections
    )
    return positive_matches == 0 or negative_matches > positive_matches
