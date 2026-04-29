"""Agent state definitions."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

IntentType = Literal[
    "policy_qa",
    "single_product_advice",
    "multi_product_recommendation",
    "product_comparison",
    "design_recommendation",
    "design_modification",
    "claim_document",
    "summary",
    "general",
]


class CitationState(TypedDict, total=False):
    """Citation payload stored in workflow state."""

    document_name: str
    page: int
    end_page: int | None
    section: str
    normalized_section: str | None
    document_type: str | None
    product_type: str | None
    content_preview: str
    score: float
    embedding_score: float | None
    hybrid_score: float | None


class ToolTraceState(TypedDict, total=False):
    """Tool trace payload stored in workflow state."""

    step: int
    tool_name: str
    status: str
    latency_ms: int
    input_summary: dict[str, object]
    output_summary: dict[str, object] | None
    error: str | None


class AgentState(TypedDict, total=False):
    """LangGraph-like state for the insurance workflow agent."""

    session_id: str
    user_query: str
    document_ids: list[str]
    top_k: int
    top_k_per_document: int
    intent: IntentType
    extracted_slots: dict[str, Any]
    search_profile: str | None
    product_type_hint: str | None
    retrieved_chunks: list[dict[str, Any]]
    citations: list[CitationState]
    recommended_design: dict[str, Any] | None
    recommended_products: list[dict[str, Any]]
    comparison_result: dict[str, Any] | None
    current_design: dict[str, Any] | None
    tool_trace: list[ToolTraceState]
    fallback_required: bool
    confidence_score: float
    answer: str
    disclaimer: str
    follow_up_questions: list[str]
    next_action: str
    error: str | None
    started_at: float
    tool_plan: list[str]
    comparison_mode: bool
    persistence_error: str | None
