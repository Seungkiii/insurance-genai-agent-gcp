"""Chat router backed by the insurance workflow agent."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.dependencies import WorkflowDependencies
from app.agents.graph import run_workflow
from app.core.config import Settings, get_settings
from app.mcp_server.tools.design_condition_tool import DesignConditionTool
from app.mcp_server.tools.policy_search_tool import PolicySearchTool
from app.mcp_server.tools.product_recommend_tool import ProductRecommendTool
from app.rag.embedder import Embedder, VertexAIEmbedder
from app.rag.generator import GeminiAnswerGenerator
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
    result = run_workflow(
        {
            "session_id": request.session_id,
            "user_query": request.question,
            "document_ids": request.document_ids,
            "top_k": request.top_k,
            "top_k_per_document": request.top_k_per_document,
            "started_at": time.perf_counter(),
        },
        workflow_dependencies,
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
        confidence_score=float(result.get("confidence_score", 0.0)),
        fallback_required=bool(result.get("fallback_required", False)),
        follow_up_questions=list(result.get("follow_up_questions", [])),
        tool_trace=list(result.get("tool_trace", [])),
        disclaimer=str(result.get("disclaimer", GUARDRAIL_DISCLAIMER)),
    )
