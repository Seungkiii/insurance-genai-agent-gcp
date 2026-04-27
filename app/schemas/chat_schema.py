"""Chat-related request and response schemas."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    query: str = Field(..., min_length=1)
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
    riders: list[str] = []


class ChatResponse(BaseModel):
    """Outgoing chat response payload."""

    session_id: str
    intent: str
    answer: str
    recommended_design: RecommendedDesign | None = None
    citations: list[Citation]
    confidence_score: float
    follow_up_questions: list[str]
    disclaimer: str


class SessionMessage(BaseModel):
    """Session message item."""

    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    """Session history response."""

    session_id: str
    messages: list[SessionMessage]
