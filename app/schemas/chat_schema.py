"""Chat-related request and response schemas."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    question: str = Field(..., min_length=1, validation_alias=AliasChoices("question", "query"))
    session_id: str
    document_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
    top_k_per_document: int = Field(default=3, ge=1, le=10)


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
    recommended_design: RecommendedDesign | None = None
    citations: list[Citation]
    search_profile: str | None = None
    confidence_score: float
    fallback_required: bool | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)
    disclaimer: str


class SessionMessage(BaseModel):
    """Session message item."""

    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    """Session history response."""

    session_id: str
    messages: list[SessionMessage]
