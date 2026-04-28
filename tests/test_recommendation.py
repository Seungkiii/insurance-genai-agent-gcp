"""Tests for synthetic design-history recommendation logic."""

from __future__ import annotations

from pathlib import Path

from app.agents.nodes.recommendation_node import run_recommendation_node
from app.schemas.recommendation_schema import RecommendationRequest
from app.services.recommendation_service import DesignHistoryRecommendationService


def test_recommendation_service_returns_fallback_for_sparse_default_data() -> None:
    """Default sample history should still produce a scoped recommendation with fallback context."""
    service = DesignHistoryRecommendationService()

    result = service.recommend(
        RecommendationRequest(
            age_group="30s",
            gender="F",
            product_name="Sample Care Plan",
        )
    )

    assert result.product_name == "Sample Care Plan"
    assert result.basis_count == 1
    assert result.recommended_riders == ["Critical Diagnosis Rider"]
    assert result.recommended_payment_period == "20 years"
    assert result.recommended_insurance_period == "90 years"
    assert result.recommended_payment_cycle == "monthly"
    assert result.recommended_coverage_amount == 70000000
    assert result.confidence_score > 0
    assert result.fallback_reason is not None


def test_recommendation_service_aggregates_top_values_from_similar_rows(tmp_path: Path) -> None:
    """Service should return top riders, mode fields, and median/mode coverage from matching rows."""
    csv_path = tmp_path / "sample_design_history.csv"
    csv_path.write_text(
        "\n".join(
            [
                "age_group,gender,product_name,rider_name,payment_period,insurance_period,payment_cycle,coverage_amount",
                "30s,F,Sample Care Plan,Critical Diagnosis Rider,20 years,90 years,monthly,70000000",
                "30s,F,Sample Care Plan,Standard Hospital Rider,20 years,90 years,monthly,90000000",
                "30s,F,Sample Care Plan,Critical Diagnosis Rider,20 years,90 years,monthly,110000000",
                "30s,F,Sample Care Plan,Accident Support Rider,15 years,80 years,monthly,130000000",
                "40s,M,Sample Life Plan,Hospital Income Rider,20 years,90 years,monthly,110000000",
            ]
        ),
        encoding="utf-8",
    )
    service = DesignHistoryRecommendationService(csv_path)

    result = service.recommend(
        RecommendationRequest(
            age_group="30s",
            gender="F",
            product_name="Sample Care Plan",
        )
    )

    assert result.basis_count == 4
    assert result.recommended_riders == [
        "Critical Diagnosis Rider",
        "Standard Hospital Rider",
        "Accident Support Rider",
    ]
    assert result.recommended_payment_period == "20 years"
    assert result.recommended_insurance_period == "90 years"
    assert result.recommended_payment_cycle == "monthly"
    assert result.recommended_coverage_amount == 100000000
    assert result.confidence_score >= 0.5
    assert result.fallback_reason is None


def test_recommendation_service_returns_zero_match_fallback() -> None:
    """Missing matches should return an explicit fallback reason."""
    service = DesignHistoryRecommendationService()

    result = service.recommend(
        RecommendationRequest(
            age_group="70s",
            gender="F",
            product_name="Sample Care Plan",
        )
    )

    assert result.basis_count == 0
    assert result.confidence_score == 0.0
    assert result.recommended_riders == []
    assert result.fallback_reason is not None


def test_recommendation_node_updates_agent_state() -> None:
    """Workflow node should write recommendation output into the agent state."""
    state = {
        "session_id": "session-1",
        "intent": "design_recommendation",
        "extracted_slots": {
            "age_group": "30s",
            "gender": "F",
            "product_name": "Sample Care Plan",
        },
    }

    updated = run_recommendation_node(state)

    assert updated["next_action"] == "respond_recommendation"
    assert updated["confidence_score"] > 0
    assert updated["recommendation_result"]["product_name"] == "Sample Care Plan"
    assert updated["recommendation_result"]["basis_count"] == 1
