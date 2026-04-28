"""Recommendation node for agent workflow integration."""

from __future__ import annotations

from app.agents.state import AgentState
from app.schemas.recommendation_schema import RecommendationRequest
from app.services.recommendation_service import DesignHistoryRecommendationService


def run_recommendation_node(
    state: AgentState,
    service: DesignHistoryRecommendationService | None = None,
) -> AgentState:
    """Populate recommendation_result in the shared agent state."""
    recommendation_service = service or DesignHistoryRecommendationService()
    slots = state.get("extracted_slots", {})

    request = RecommendationRequest(
        age_group=slots.get("age_group"),
        gender=slots.get("gender"),
        product_name=slots.get("product_name"),
    )
    result = recommendation_service.recommend(request)

    updated = dict(state)
    updated["recommendation_result"] = result.model_dump()
    updated["confidence_score"] = result.confidence_score
    updated["next_action"] = "respond_recommendation"
    return updated
