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
from app.services.document_context_service import resolve_document_scope
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
        request_search_scope=request.search_scope,
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
            resolved_document_ids=resolved_scope.document_ids,
            resolved_document_count=len(resolved_scope.document_ids),
            resolved_document_names=resolved_scope.selected_product_names,
            confidence_score=0.0,
            fallback_required=True,
            follow_up_questions=[],
            tool_trace=[],
            disclaimer=GUARDRAIL_DISCLAIMER,
            debug_info={
                "session_id": request.session_id,
                "raw_request_document_ids": request.document_ids or [],
                "request_search_scope": request.search_scope,
                "search_scope": resolved_scope.search_scope,
                "selected_document_ids": resolved_scope.selected_document_ids,
                "resolved_document_ids": resolved_scope.document_ids,
                "resolved_document_count": len(resolved_scope.document_ids),
                "resolved_document_names": resolved_scope.selected_product_names,
                "invalid_document_ids": resolved_scope.invalid_document_ids,
            },
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
            resolved_document_ids=resolved_scope.document_ids,
            resolved_document_names=resolved_scope.selected_product_names,
            debug_info={
                "session_id": request.session_id,
                "raw_request_document_ids": request.document_ids or [],
                "request_search_scope": request.search_scope,
                "search_scope": resolved_scope.search_scope,
                "selected_document_ids": resolved_scope.selected_document_ids,
                "resolved_document_ids": resolved_scope.document_ids,
                "resolved_document_count": len(resolved_scope.document_ids),
                "resolved_document_names": resolved_scope.selected_product_names,
                "invalid_document_ids": resolved_scope.invalid_document_ids,
            },
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

    # Persist resolved scope into the session context so subsequent queries inherit it
    try:
        workflow_dependencies.firestore_service.update_session_context(
            request.session_id,
            selected_document_ids=resolved_scope.selected_document_ids or None,
            selected_product_names=resolved_scope.selected_product_names or None,
            search_scope=resolved_scope.search_scope,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "chat_session_context_update_failed",
            extra={"session_id": request.session_id, "error": str(exc)},
        )

    result = run_workflow(
        {
            "session_id": request.session_id,
            "user_query": request.question,
            "raw_request_document_ids": request.document_ids or [],
            "document_ids": resolved_scope.document_ids,
            "selected_document_ids": resolved_scope.selected_document_ids,
            "selected_product_names": resolved_scope.selected_product_names,
            "search_scope": resolved_scope.search_scope,
            "search_scope_label": resolved_scope.search_scope_label,
            "resolved_document_ids": resolved_scope.document_ids,
            "resolved_document_names": resolved_scope.selected_product_names,
            "invalid_document_ids": resolved_scope.invalid_document_ids,
            "product_type_hint": _infer_product_type_hint(
                workflow_dependencies.firestore_service,
                resolved_scope.document_ids,
            ),
            "top_k": request.top_k if request.top_k is not None else 5,
            "top_k_per_document": request.top_k_per_document if request.top_k_per_document is not None else 3,
            "started_at": time.perf_counter(),
        },
        workflow_dependencies,
    )
    if resolved_scope.invalid_document_ids or request.document_ids or request.search_scope:
        result.setdefault("tool_trace", [])
        result["tool_trace"].append(
            {
                "step": len(result["tool_trace"]) + 1,
                "tool_name": "document_scope_resolver",
                "status": "warning",
                "latency_ms": 0,
                "input_summary": {
                    "raw_request_document_ids": request.document_ids or [],
                    "request_search_scope": request.search_scope,
                },
                "output_summary": {
                    "selected_document_ids": resolved_scope.selected_document_ids,
                    "resolved_document_ids": resolved_scope.document_ids,
                    "resolved_document_names": resolved_scope.selected_product_names,
                    "resolved_document_count": len(resolved_scope.document_ids),
                    "search_scope": resolved_scope.search_scope,
                    "invalid_document_ids": resolved_scope.invalid_document_ids,
                },
                "error": None,
            }
        )

    result["selected_document_ids"] = resolved_scope.selected_document_ids
    result["selected_product_names"] = resolved_scope.selected_product_names
    result["search_scope"] = resolved_scope.search_scope
    result["search_scope_label"] = resolved_scope.search_scope_label
    result["resolved_document_ids"] = resolved_scope.document_ids
    result["resolved_document_count"] = len(resolved_scope.document_ids)
    result["resolved_document_names"] = resolved_scope.selected_product_names
    result["debug_info"] = {
        "session_id": request.session_id,
        "raw_request_document_ids": request.document_ids or [],
        "request_search_scope": request.search_scope,
        "search_scope": resolved_scope.search_scope,
        "selected_document_ids": resolved_scope.selected_document_ids,
        "resolved_document_ids": resolved_scope.document_ids,
        "resolved_document_count": len(resolved_scope.document_ids),
        "resolved_document_names": resolved_scope.selected_product_names,
        "invalid_document_ids": resolved_scope.invalid_document_ids,
    }

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
        selected_product_names=list(result.get("selected_product_names", [])),
        selected_document_ids=list(result.get("selected_document_ids", [])),
        resolved_document_ids=list(result.get("resolved_document_ids", [])),
        resolved_document_count=int(result.get("resolved_document_count", 0)),
        resolved_document_names=list(result.get("resolved_document_names", [])),
        confidence_score=float(result.get("confidence_score", 0.0)),
        fallback_required=bool(result.get("fallback_required", False)),
        follow_up_questions=list(result.get("follow_up_questions", [])),
        tool_trace=list(result.get("tool_trace", [])),
        disclaimer=str(result.get("disclaimer", GUARDRAIL_DISCLAIMER)),
        debug_info=result.get("debug_info"),
    )


def _infer_product_type_hint(
    firestore_service: FirestoreService,
    document_ids: list[str],
) -> str | None:
    product_types: list[str] = []
    for document_id in document_ids:
        record = firestore_service.get_document(document_id)
        product_type = str(record.get("product_type") or "").strip() if record else ""
        if product_type and product_type not in product_types:
            product_types.append(product_type)
    if len(product_types) == 1:
        return product_types[0]
    return None
