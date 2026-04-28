"""Tests for the workflow agent MVP."""

from app.agents.graph import run_workflow


def test_policy_qa_flow_returns_citations() -> None:
    """Policy Q&A should route through retrieval and return citations."""
    result = run_workflow(
        {
            "session_id": "session-policy",
            "user_query": "미용 목적 시술도 보장되나요?",
        }
    )

    assert result["intent"] == "policy_qa"
    assert result["citations"]
    assert result["confidence_score"] > 0
    assert "보장" in result["answer"]


def test_claim_document_flow_returns_claim_citations() -> None:
    """Claim-document questions should surface the claim section."""
    result = run_workflow(
        {
            "session_id": "session-claim",
            "user_query": "입원일당 청구 서류는 무엇인가요?",
        }
    )

    assert result["intent"] == "claim_document"
    assert result["citations"]
    assert any(citation["section"] == "청구 서류" for citation in result["citations"])


def test_design_recommendation_flow_calls_recommendation_service() -> None:
    """Recommendation questions should return aggregated design suggestions."""
    result = run_workflow(
        {
            "session_id": "session-recommend",
            "user_query": "30s 여성에게 Sample Care Plan 기준으로 추천 설계안을 알려줘.",
        }
    )

    assert result["intent"] == "design_recommendation"
    assert result["recommendation_result"]["product_name"] == "Sample Care Plan"
    assert result["recommendation_result"]["basis_count"] == 1
    assert "추천 특약" in result["answer"]


def test_design_modification_flow_updates_design_state() -> None:
    """Design modification should rewrite the design state."""
    result = run_workflow(
        {
            "session_id": "session-modify",
            "user_query": "Sample Care Plan 설계에서 월 보험료 부담을 낮추기 위해 보장금액을 줄이고 납입기간만 짧게 바꿔줘.",
            "current_design": {
                "product_name": "Sample Care Plan",
                "payment_period": "20 years",
                "insurance_period": "80 years",
                "payment_cycle": "monthly",
                "coverage_amount": 50000000,
            },
        }
    )

    assert result["intent"] == "design_modification"
    assert result["modified_design"]["payment_period"] == "10 years"
    assert result["modified_design"]["coverage_amount"] == 40000000
    assert "수정안" in result["answer"]


def test_general_flow_returns_general_answer() -> None:
    """General questions should fall back to a scoped MVP explanation."""
    result = run_workflow(
        {
            "session_id": "session-general",
            "user_query": "안녕하세요, 이 시스템은 무엇을 하나요?",
        }
    )

    assert result["intent"] == "general"
    assert result["citations"] == []
    assert result["confidence_score"] == 0.2


def test_guardrail_adds_missing_citation_disclaimer() -> None:
    """Policy-like answers without citations should get a stronger disclaimer."""
    result = run_workflow(
        {
            "session_id": "session-guard",
            "user_query": "보장 내용을 알려줘",
        }
    )

    assert result["intent"] == "policy_qa"
    assert result["disclaimer"]
