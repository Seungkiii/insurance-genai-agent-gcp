"""Chat-related request and response schemas."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    question: str = Field(..., min_length=1, validation_alias=AliasChoices("question", "query"))
    session_id: str
    document_ids: list[str] | None = None
    search_scope: str | None = Field(default=None, pattern="^(selected|all)$")
    top_k: int | None = Field(default=None, ge=1, le=20)
    top_k_per_document: int | None = Field(default=None, ge=1, le=10)


class Citation(BaseModel):
    """Citation model for grounded answers."""

    document_name: str
    page: int
    end_page: int | None = None
    section: str
    normalized_section: str | None = None
    document_type: str | None = None
    product_type: str | None = None
    content_preview: str
    score: float
    embedding_score: float | None = None
    hybrid_score: float | None = None


class ToolTraceItem(BaseModel):
    """Structured trace entry for a tool-like retrieval step."""

    step: int
    tool_name: str
    status: str
    latency_ms: int
    input_summary: dict[str, object]
    output_summary: dict[str, object] | None = None
    error: str | None = None


class RecommendedDesign(BaseModel):
    """Synthetic recommended design structure."""

    product_group: str | None = None
    product_name: str | None = None
    riders: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Outgoing chat response payload."""

    session_id: str
    intent: str
    answer: str
    recommended_design: dict[str, object] | None = None
    recommended_products: list[dict[str, object]] = Field(default_factory=list)
    comparison_result: dict[str, object] | None = None
    current_design: dict[str, object] | None = None
    citations: list[Citation]
    search_profile: str | None = None
    search_scope: str | None = None
    search_scope_label: str | None = None
    selected_product_names: list[str] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    resolved_document_ids: list[str] = Field(default_factory=list)
    resolved_document_count: int = 0
    resolved_document_names: list[str] = Field(default_factory=list)
    confidence_score: float
    fallback_required: bool | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)
    disclaimer: str
    debug_info: dict[str, object] | None = None


class SessionMessage(BaseModel):
    """Session message item."""

    message_id: str
    role: str
    content: str
    created_at: str
    intent: str | None = None
    search_profile: str | None = None
    search_scope: str | None = None
    search_scope_label: str | None = None
    selected_product_names: list[str] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    resolved_document_ids: list[str] = Field(default_factory=list)
    resolved_document_count: int = 0
    resolved_document_names: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    fallback_required: bool | None = None
    citations: list[Citation] = Field(default_factory=list)
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)
    recommended_design: dict[str, object] | None = None
    current_design: dict[str, object] | None = None
    debug_info: dict[str, object] | None = None


class SessionHistoryResponse(BaseModel):
    """Session history response."""

    session_id: str
    messages: list[SessionMessage]


class SessionDocumentSelectionRequest(BaseModel):
    """Session-level document selection payload."""

    selected_document_ids: list[str] = Field(default_factory=list)
    search_scope: str = Field(default="selected", pattern="^(selected|all)$")


class SessionDocumentSelectionResponse(BaseModel):
    """Session-level document selection response."""

    session_id: str
    selected_document_ids: list[str] = Field(default_factory=list)
    selected_product_names: list[str] = Field(default_factory=list)
    search_scope: str = "selected"
