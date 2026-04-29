"""Tests for synthetic design-history recommendation logic."""

from __future__ import annotations

from pathlib import Path

from app.agents.dependencies import WorkflowDependencies
from app.agents.nodes.recommendation_node import run_recommendation_node
from app.schemas.recommendation_schema import RecommendationRequest
from app.services.recommendation_service import DesignHistoryRecommendationService


class FakeRecommendTool:
    def run(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tool_name": "product_recommend_tool",
            "status": "success",
            "input": payload,
            "output": {
                "search_profile": "coverage_summary",
                "recommended_design": {
                    "product_name": "Sample Care Plan",
                    "product_type": "health",
                    "focus_areas": ["주요 보장", "유의사항"],
                    "main_focus": "상품 핵심 보장과 설명 포인트",
                    "recommended_explanation_points": ["보험금 지급사유 중심으로 설명"],
                    "caution_notes": ["지급 제한은 약관 확인 필요"],
                    "evidence_summary": ["설명 근거 | coverage | 보험금 지급사유 | policy-a.pdf p.2"],
                },
                "current_design": {
                    "session_id": "session-1",
                    "customer_profile": {"age_group": "30s"},
                    "product_type": "health",
                    "selected_document_ids": ["doc-1"],
                    "focus_areas": ["주요 보장", "유의사항"],
                    "caution_notes": ["지급 제한은 약관 확인 필요"],
                    "evidence_summary": ["설명 근거 | coverage | 보험금 지급사유 | policy-a.pdf p.2"],
                    "coverages": ["주요 보장", "유의사항"],
                },
                "citations": [
                    {
                        "document_name": "policy-a.pdf",
                        "page": 2,
                        "section": "보험금 지급사유",
                        "normalized_section": "coverage",
                        "content_preview": "보험금 지급 기준은 약관에 따릅니다.",
                        "score": 0.8,
                    }
                ],
                "fallback_required": False,
            },
            "latency_ms": 5,
            "error": None,
            "trace_summary": [],
        }


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
        "user_query": "Sample Care Plan 추천 설계안을 알려줘.",
        "extracted_slots": {
            "age_group": "30s",
            "gender": "F",
            "product_name": "Sample Care Plan",
        },
    }
    dependencies = WorkflowDependencies(
        policy_search_tool=FakeRecommendTool(),  # type: ignore[arg-type]
        product_recommend_tool=FakeRecommendTool(),  # type: ignore[arg-type]
        design_condition_tool=FakeRecommendTool(),  # type: ignore[arg-type]
        answer_generator=FakeRecommendTool(),  # type: ignore[arg-type]
        firestore_service=FakeRecommendTool(),  # type: ignore[arg-type]
    )

    updated = run_recommendation_node(state, dependencies)

    assert updated["recommended_design"] is not None
    assert updated["recommended_design"]["product_name"] == "Sample Care Plan"
    assert updated["current_design"]["product_type"] == "health"
    assert updated["search_profile"] == "coverage_summary"
    assert updated["citations"]
