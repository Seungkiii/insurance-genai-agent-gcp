"""Chat-related request and response schemas."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    question: str = Field(..., min_length=1, validation_alias=AliasChoices("question", "query"))
    session_id: str | None = None


class Citation(BaseModel):
    """Citation model for grounded answers."""

    document_name: str
    page: int
    section: str
    content: str


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
    confidence_score: float
    follow_up_questions: list[str] = Field(default_factory=list)
    disclaimer: str


class SessionMessage(BaseModel):
    """Session message item."""

    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    """Session history response."""

    session_id: str
    messages: list[SessionMessage]
