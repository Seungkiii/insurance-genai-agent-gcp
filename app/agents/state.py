"""Agent state definitions."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph-like state for insurance design workflow."""

    session_id: str
    user_query: str
    intent: str
    extracted_slots: dict[str, str]
    current_design: dict[str, str]
    retrieved_docs: list[dict[str, str]]
    recommendation_result: dict[str, str]
    confidence_score: float
    answer: str
    citations: list[dict[str, str]]
    next_action: str
    error: str | None
