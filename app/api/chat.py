"""Chat router backed by the insurance workflow agent."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.dependencies import WorkflowDependencies
from app.agents.graph import run_workflow
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.mcp_server.tools.design_condition_tool import DesignConditionTool
from app.mcp_server.tools.policy_search_tool import PolicySearchTool
from app.mcp_server.tools.product_recommend_tool import ProductRecommendTool
from app.rag.embedder import Embedder, VertexAIEmbedder
from app.rag.generator import GeminiAnswerGenerator
from app.rag.search_profiles import classify_search_profile
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.document_context_service import (
    infer_selected_documents_from_result,
    resolve_document_scope,
)
from app.services.firestore_service import FirestoreService, GCPFirestoreService
from app.services.gcp_storage_service import GCPStorageService, StorageService
from app.services.vertex_ai_service import VertexAIEmbeddingService, VertexAIGenerationService

router = APIRouter()
logger = get_logger("app.api.chat")

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


def get_workflow_dependencies(
    settings: Settings = Depends(get_settings),
    storage_service: StorageService = Depends(get_storage_service),
    firestore_service: FirestoreService = Depends(get_firestore_service),
    embedder: Embedder = Depends(get_query_embedder),
    generator: GeminiAnswerGenerator = Depends(get_answer_generator),
) -> WorkflowDependencies:
    """Create workflow-scoped dependencies for the chat agent."""
    policy_search_tool = PolicySearchTool(
        storage_service=storage_service,
        embedder=embedder,
        firestore_service=firestore_service,
        bucket_name=settings.gcs_bucket_name or "",
    )
    return WorkflowDependencies(
        policy_search_tool=policy_search_tool,
        product_recommend_tool=ProductRecommendTool(
            policy_search_tool=policy_search_tool,
            firestore_service=firestore_service,
        ),
        design_condition_tool=DesignConditionTool(firestore_service=firestore_service),
        answer_generator=generator,
        firestore_service=firestore_service,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    workflow_dependencies: WorkflowDependencies = Depends(get_workflow_dependencies),
) -> ChatResponse:
    """Answer a question using the LangGraph-style workflow agent."""
    resolved_scope = resolve_document_scope(
        session_id=request.session_id,
        firestore_service=workflow_dependencies.firestore_service,
        request_document_ids=request.document_ids,
        query=request.question,
        product_type_hint=None,
    )

    if resolved_scope.fallback_message:
        return ChatResponse(
            session_id=request.session_id,
            intent="general" if "어떤 상품을 기준으로 확인할까요?" in resolved_scope.fallback_message else "policy_qa",
            answer=resolved_scope.fallback_message,
            recommended_design=None,
            recommended_products=[],
            comparison_result=None,
            current_design=None,
            citations=[],
            search_profile=classify_search_profile(request.question).name,
            search_scope=resolved_scope.search_scope,
            search_scope_label=resolved_scope.search_scope_label,
            selected_product_names=resolved_scope.selected_product_names,
            selected_document_ids=resolved_scope.selected_document_ids,
            confidence_score=0.0,
            fallback_required=True,
            follow_up_questions=[],
            tool_trace=[],
            disclaimer=GUARDRAIL_DISCLAIMER,
        )

    try:
        workflow_dependencies.firestore_service.save_session_message(
            request.session_id,
            "user",
            request.question,
            document_ids=resolved_scope.selected_document_ids,
            selected_product_names=resolved_scope.selected_product_names,
            search_scope=resolved_scope.search_scope,
            search_scope_label=resolved_scope.search_scope_label,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "chat_user_message_persist_failed",
            extra={
                "session_id": request.session_id,
                "question_length": len(request.question),
                "error": str(exc),
            },
        )

    result = run_workflow(
        {
            "session_id": request.session_id,
            "user_query": request.question,
            "document_ids": resolved_scope.document_ids,
            "selected_document_ids": resolved_scope.selected_document_ids,
            "selected_product_names": resolved_scope.selected_product_names,
            "search_scope": resolved_scope.search_scope,
            "search_scope_label": resolved_scope.search_scope_label,
            "top_k": request.top_k if request.top_k is not None else 5,
            "top_k_per_document": request.top_k_per_document if request.top_k_per_document is not None else 3,
            "started_at": time.perf_counter(),
        },
        workflow_dependencies,
    )

    selected_document_ids, selected_product_names = infer_selected_documents_from_result(result)
    if not selected_document_ids:
        selected_document_ids = resolved_scope.selected_document_ids
    if not selected_product_names:
        selected_product_names = resolved_scope.selected_product_names

    try:
        existing_context = workflow_dependencies.firestore_service.get_session_context(request.session_id) or {}
        next_search_scope = str(existing_context.get("search_scope") or "").strip() or (
            "selected" if selected_document_ids else resolved_scope.search_scope
        )
        workflow_dependencies.firestore_service.update_session_context(
            request.session_id,
            selected_document_ids=selected_document_ids,
            selected_product_names=selected_product_names,
            search_scope=next_search_scope,
            current_design=result.get("current_design"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "session_context_update_failed",
            extra={"session_id": request.session_id, "error": str(exc)},
        )

    result["selected_document_ids"] = selected_document_ids
    result["selected_product_names"] = selected_product_names
    result["search_scope"] = result.get("search_scope") or resolved_scope.search_scope
    result["search_scope_label"] = result.get("search_scope_label") or (
        resolved_scope.search_scope_label
        if result["search_scope"] == resolved_scope.search_scope
        else ("전체 상품" if result["search_scope"] == "all" else f"선택 상품 {len(selected_product_names)}개")
    )

    return ChatResponse(
        session_id=request.session_id,
        intent=str(result.get("intent", "general")),
        answer=str(result.get("answer", "")),
        recommended_design=result.get("recommended_design"),
        recommended_products=list(result.get("recommended_products", [])),
        comparison_result=result.get("comparison_result"),
        current_design=result.get("current_design"),
        citations=list(result.get("citations", [])),
        search_profile=result.get("search_profile"),
        search_scope=result.get("search_scope"),
        search_scope_label=result.get("search_scope_label"),
        selected_product_names=list(result.get("selected_product_names", selected_product_names)),
        selected_document_ids=list(result.get("selected_document_ids", selected_document_ids)),
        confidence_score=float(result.get("confidence_score", 0.0)),
        fallback_required=bool(result.get("fallback_required", False)),
        follow_up_questions=list(result.get("follow_up_questions", [])),
        tool_trace=list(result.get("tool_trace", [])),
        disclaimer=str(result.get("disclaimer", GUARDRAIL_DISCLAIMER)),
    )
