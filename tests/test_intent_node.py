"""Tests for workflow intent classification."""

from app.agents.nodes.intent_node import classify_intent


def test_policy_qa_intent() -> None:
    assert classify_intent("이 상품의 주요 보장 내용은 뭐야?", document_ids=["doc-1"]) == "policy_qa"


def test_single_product_advice_intent() -> None:
    assert (
        classify_intent(
            "55세 남성 고객에게 이 상품을 설명한다면 어떤 보장과 유의사항 중심으로 안내하면 좋을까?",
            document_ids=["doc-1"],
        )
        == "single_product_advice"
    )


def test_multi_product_recommendation_intent() -> None:
    assert classify_intent("55세 남성에게 적합한 보험 상품 추천해줘", document_ids=[]) == "multi_product_recommendation"


def test_product_comparison_intent() -> None:
    assert classify_intent("암보험과 건강보험 차이를 비교해줘", document_ids=[]) == "product_comparison"


def test_design_modification_intent() -> None:
    assert classify_intent("방금 추천 설계에서 입원 보장을 추가해줘", document_ids=["doc-1"]) == "design_modification"
