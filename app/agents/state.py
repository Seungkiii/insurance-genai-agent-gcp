"""Agent state definitions."""

from __future__ import annotations

from typing import Literal, TypedDict

IntentType = Literal[
    "policy_qa",
    "design_recommendation",
    "design_modification",
    "claim_document",
    "general",
]


class DesignState(TypedDict, total=False):
    """Current synthetic design configuration."""

    product_name: str
    payment_period: str
    insurance_period: str
    payment_cycle: str
    coverage_amount: int
    rider_name: str


class CitationState(TypedDict):
    """Lightweight citation payload stored in workflow state."""

    document_name: str
    section: str
    page: int
    content: str


class AgentState(TypedDict, total=False):
    """LangGraph-like state for insurance design workflow."""

    session_id: str
    user_query: str
    intent: IntentType
    extracted_slots: dict[str, str]
    current_design: DesignState
    modified_design: DesignState
    retrieved_docs: list[CitationState]
    recommendation_result: dict[str, object]
    confidence_score: float
    answer: str
    citations: list[CitationState]
    disclaimer: str
    fallback_reason: str | None
    next_action: str
    error: str | None
