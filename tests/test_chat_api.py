"""Tests for the workflow-backed chat API."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.agents.dependencies import WorkflowDependencies
from app.api.chat import get_workflow_dependencies
from app.main import create_app


class FakeTool:
    def __init__(self, name: str, output: dict[str, Any]) -> None:
        self.name = name
        self.output = output
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "tool_name": self.name,
            "status": "success",
            "input": payload,
            "output": self.output,
            "latency_ms": 8,
            "error": None,
            "trace_summary": [],
        }


class FakeGenerator:
    def generate_agent_response(
        self,
        *,
        question: str,
        intent: str,
        search_profile: str | None,
        retrieved_chunks: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        recommended_design: dict[str, Any] | None,
        recommended_products: list[dict[str, Any]],
        comparison_result: dict[str, Any] | None,
        current_design: dict[str, Any] | None,
        fallback_required: bool,
    ) -> str:
        return "검색된 근거를 바탕으로 답변을 생성했습니다.\n\n본 답변은 약관 해석을 돕기 위한 참고 정보이며, 보험금 지급 확정 또는 보상 승인 판단을 의미하지 않습니다."


class FakeFirestoreService:
    def __init__(self) -> None:
        self.saved_interactions: list[dict[str, Any]] = []

    def save_chat_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        citations: list[dict[str, Any]],
        latency_ms: int,
        *,
        tool_trace: list[dict[str, Any]] | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "session_id": session_id,
            "user_message": user_message,
            "assistant_answer": assistant_answer,
            "citations": citations,
            "latency_ms": latency_ms,
            "tool_trace": tool_trace or [],
            "current_design": current_design,
            "intent": intent,
            "search_profile": search_profile,
        }
        self.saved_interactions.append(payload)
        return payload

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        return {"session_id": session_id, "current_design": {"coverages": ["기본보장"]}}


def create_test_client(
    *,
    policy_output: dict[str, Any],
    recommendation_output: dict[str, Any] | None = None,
    design_output: dict[str, Any] | None = None,
) -> tuple[TestClient, FakeFirestoreService, FakeTool, FakeTool, FakeTool]:
    app = create_app()
    firestore_service = FakeFirestoreService()
    policy_tool = FakeTool("policy_search_tool", policy_output)
    recommendation_tool = FakeTool("product_recommend_tool", recommendation_output or {})
    design_tool = FakeTool("design_condition_tool", design_output or {})
    dependencies = WorkflowDependencies(
        policy_search_tool=policy_tool,  # type: ignore[arg-type]
        product_recommend_tool=recommendation_tool,  # type: ignore[arg-type]
        design_condition_tool=design_tool,  # type: ignore[arg-type]
        answer_generator=FakeGenerator(),  # type: ignore[arg-type]
        firestore_service=firestore_service,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_workflow_dependencies] = lambda: dependencies
    return TestClient(app), firestore_service, policy_tool, recommendation_tool, design_tool


def test_chat_returns_grounded_answer_and_citations() -> None:
    client, firestore_service, policy_tool, _, _ = create_test_client(
        policy_output={
            "search_profile": "payment_condition",
            "product_type": "health",
            "document_type": "policy_terms",
            "normalized_section": ["coverage"],
            "chunks": [
                {
                    "document_id": "doc-001",
                    "document_name": "policy-a.pdf",
                    "document_type": "policy_terms",
                    "product_type": "health",
                    "page": 2,
                    "section": "보험금 지급사유",
                    "normalized_section": "coverage",
                    "content": "보험금 지급 기준은 약관에 따릅니다.",
                }
            ],
            "citations": [
                {
                    "document_name": "policy-a.pdf",
                    "page": 2,
                    "end_page": 2,
                    "section": "보험금 지급사유",
                    "normalized_section": "coverage",
                    "document_type": "policy_terms",
                    "product_type": "health",
                    "content_preview": "보험금 지급 기준은 약관에 따릅니다.",
                    "score": 0.88,
                    "embedding_score": 0.81,
                    "hybrid_score": 0.88,
                }
            ],
            "confidence_score": 0.84,
            "fallback_required": False,
        }
    )

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "보험금 지급 기준은 어떻게 되나요?",
            "session_id": "session-001",
            "document_ids": ["doc-001"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-001"
    assert payload["intent"] == "policy_qa"
    assert payload["search_profile"] == "payment_condition"
    assert payload["citations"][0]["document_name"] == "policy-a.pdf"
    assert payload["citations"][0]["normalized_section"] == "coverage"
    assert payload["confidence_score"] == 0.84
    assert payload["fallback_required"] is False
    assert payload["tool_trace"][0]["tool_name"] == "policy_search_tool"
    assert policy_tool.calls[0]["document_ids"] == ["doc-001"]
    assert firestore_service.saved_interactions


def test_chat_requests_more_information_when_fallback_required() -> None:
    client, firestore_service, _, _, _ = create_test_client(
        policy_output={
            "search_profile": "coverage_summary",
            "product_type": "annuity",
            "document_type": "product_summary",
            "normalized_section": [],
            "chunks": [],
            "citations": [],
            "confidence_score": 0.2,
            "fallback_required": True,
        }
    )

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "이 상품의 보장 내용을 알려줘.",
            "session_id": "session-002",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_required"] is True
    assert payload["confidence_score"] == 0.2
    assert "질문 의도에 맞는 조항" in payload["answer"]
    assert firestore_service.saved_interactions


def test_chat_design_recommendation_returns_recommended_and_current_design() -> None:
    client, firestore_service, _, recommendation_tool, _ = create_test_client(
        policy_output={
            "search_profile": "coverage_summary",
            "product_type": "annuity",
            "document_type": "product_summary",
            "normalized_section": ["annuity_payment"],
            "chunks": [
                {
                    "document_id": "coverage-doc",
                    "document_name": "annuity.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "content": "연금개시후 연금지급형태를 안내합니다.",
                }
            ],
            "citations": [
                {
                    "document_name": "annuity.pdf",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "content_preview": "연금개시후 연금지급형태를 안내합니다.",
                    "score": 0.79,
                }
            ],
            "confidence_score": 0.73,
            "fallback_required": False,
        },
        recommendation_output={
            "search_profile": "coverage_summary",
            "recommended_design": {
                "product_type": "annuity",
                "focus_areas": ["연금개시 후 지급방식", "중도인출 유의사항"],
            },
            "recommended_products": [
                {
                    "document_id": "coverage-doc",
                    "document_name": "annuity.pdf",
                    "product_type": "annuity",
                    "recommendation_reason": "연금 니즈에 적합합니다.",
                }
            ],
            "current_design": {"coverages": ["기본보장"]},
            "citations": [
                {
                    "document_name": "annuity.pdf",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "content_preview": "연금개시후 연금지급형태를 안내합니다.",
                    "score": 0.79,
                }
            ],
            "fallback_required": False,
        },
    )

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "연금보험 추천 설계안을 근거와 함께 알려줘.",
            "session_id": "session-003",
            "document_ids": ["coverage-doc"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "single_product_advice"
    assert payload["recommended_design"]["product_type"] == "annuity"
    assert payload["recommended_products"][0]["product_type"] == "annuity"
    assert payload["current_design"]["coverages"] == ["기본보장"]
    assert recommendation_tool.calls
    assert firestore_service.saved_interactions[0]["current_design"] == {"coverages": ["기본보장"]}
