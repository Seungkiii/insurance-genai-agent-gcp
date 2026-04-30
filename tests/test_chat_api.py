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
        self.saved_designs: list[dict[str, Any]] = []
        self.saved_messages: list[dict[str, Any]] = []
        self.documents = {
            "doc-001": {
                "document_id": "doc-001",
                "file_name": "policy-a.pdf",
                "document_name": "policy-a.pdf",
                "product_name": "정책 A",
                "status": "indexed",
                "product_type": "health",
                "document_type": "policy_terms",
            },
            "coverage-doc": {
                "document_id": "coverage-doc",
                "file_name": "annuity.pdf",
                "document_name": "annuity.pdf",
                "product_name": "무배당엔젤하이브리드연금보험",
                "status": "indexed",
                "product_type": "annuity",
                "document_type": "product_summary",
            },
        }
        self.session_contexts: dict[str, dict[str, Any]] = {}

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

    def save_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        message_id: str | None = None,
        document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        search_scope_label: str | None = None,
        resolved_document_ids: list[str] | None = None,
        resolved_document_names: list[str] | None = None,
        debug_info: dict[str, Any] | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
        confidence_score: float | None = None,
        fallback_required: bool | None = None,
        citations: list[dict[str, Any]] | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
        recommended_design: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "session_id": session_id,
            "message_id": message_id or f"{role}-{len(self.saved_messages) + 1}",
            "role": role,
            "content": content,
            "selected_document_ids": document_ids or [],
            "selected_product_names": selected_product_names or [],
            "current_design": current_design,
            "intent": intent,
            "search_profile": search_profile,
            "search_scope": search_scope,
            "search_scope_label": search_scope_label,
            "resolved_document_ids": resolved_document_ids or [],
            "resolved_document_names": resolved_document_names or [],
            "confidence_score": confidence_score,
            "fallback_required": fallback_required,
            "citations": citations or [],
            "tool_trace": tool_trace or [],
            "recommended_design": recommended_design,
            "debug_info": debug_info,
            "created_at": "2026-04-30T00:00:00+00:00",
        }
        self.saved_messages.append(payload)
        return payload

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return [message for message in self.saved_messages if message["session_id"] == session_id]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        return self.documents.get(document_id)

    def list_documents(self) -> list[dict[str, Any]]:
        return list(self.documents.values())

    def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        return self.session_contexts.get(session_id)

    def update_session_context(
        self,
        session_id: str,
        *,
        selected_document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        current_design: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.session_contexts.get(session_id, {"session_id": session_id})
        updated = {
            **existing,
            "session_id": session_id,
            "selected_document_ids": selected_document_ids if selected_document_ids is not None else existing.get("selected_document_ids", []),
            "selected_product_names": selected_product_names if selected_product_names is not None else existing.get("selected_product_names", []),
            "search_scope": search_scope if search_scope is not None else existing.get("search_scope", "selected"),
            "current_design": current_design if current_design is not None else existing.get("current_design"),
        }
        self.session_contexts[session_id] = updated
        return updated

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        return {"session_id": session_id, "current_design": {"coverages": ["기본보장"]}}

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        payload = {"session_id": session_id, "current_design": design}
        self.saved_designs.append(payload)
        self.update_session_context(session_id, current_design=design)
        return payload


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
    assert "session_id" in payload
    assert "answer" in payload
    assert "tool_trace" in payload
    assert policy_tool.calls[0]["document_ids"] == ["doc-001"]
    assert [message["role"] for message in firestore_service.saved_messages] == ["user", "assistant"]


def test_chat_works_without_document_ids_using_indexed_documents() -> None:
    client, firestore_service, policy_tool, _, _ = create_test_client(
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
        }
    )
    firestore_service.documents = {"coverage-doc": firestore_service.documents["coverage-doc"]}

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "연금개시 후에는 어떤 방식으로 연금을 지급해?",
            "session_id": "session-no-docs",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert payload["selected_document_ids"] == []
    assert payload["resolved_document_ids"] == ["coverage-doc"]
    assert policy_tool.calls[0]["document_ids"] == ["coverage-doc"]


def test_chat_reuses_session_selected_documents_on_follow_up_question() -> None:
    client, firestore_service, policy_tool, _, _ = create_test_client(
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
        }
    )
    firestore_service.documents = {"coverage-doc": firestore_service.documents["coverage-doc"]}

    first_response = client.post(
        "/api/v1/chat",
        json={
            "question": "연금개시 후에는 어떤 방식으로 연금을 지급해?",
            "session_id": "session-follow-up",
        },
    )
    second_response = client.post(
        "/api/v1/chat",
        json={
            "question": "그럼 유의사항도 알려줘.",
            "session_id": "session-follow-up",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert policy_tool.calls[0]["document_ids"] == ["coverage-doc"]
    assert policy_tool.calls[1]["document_ids"] == ["coverage-doc"]


def test_chat_keeps_same_session_document_scope_across_multiple_questions() -> None:
    client, firestore_service, policy_tool, _, _ = create_test_client(
        policy_output={
            "search_profile": "pension_payment",
            "product_type": "annuity",
            "document_type": "product_summary",
            "normalized_section": ["annuity_payment"],
            "chunks": [
                {
                    "document_id": "630e5103-61d3-44c3-8efe-646c6be9ec60",
                    "document_name": "2025041516121911948953.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "content": "연금개시후 연금지급형태와 생존연금 구조를 설명합니다.",
                }
            ],
            "citations": [
                {
                    "document_name": "2025041516121911948953.pdf",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "content_preview": "연금개시후 연금지급형태와 생존연금 구조를 설명합니다.",
                    "score": 0.9,
                }
            ],
            "confidence_score": 0.9,
            "fallback_required": False,
        }
    )
    firestore_service.documents = {
        "630e5103-61d3-44c3-8efe-646c6be9ec60": {
            "document_id": "630e5103-61d3-44c3-8efe-646c6be9ec60",
            "file_name": "2025041516121911948953.pdf",
            "document_name": "2025041516121911948953.pdf",
            "product_name": "무배당엔젤하이브리드연금보험 상품요약서",
            "status": "indexed",
            "product_type": "annuity",
            "document_type": "product_summary",
        }
    }
    firestore_service.update_session_context(
        "session-stable-scope",
        selected_document_ids=["630e5103-61d3-44c3-8efe-646c6be9ec60"],
        selected_product_names=["무배당엔젤하이브리드연금보험 상품요약서"],
        search_scope="selected",
    )

    questions = [
        "이 상품의 주요 보장 내용은 뭐야?",
        "이 상품을 어떤 유형의 고객에게 추천해줄수 있어?",
        "연금개시 후에는 어떤 방식으로 연금을 지급해?",
        "이 상품의 주요 보장 내용은 뭐야?",
    ]
    responses = [
        client.post("/api/v1/chat", json={"question": question, "session_id": "session-stable-scope"})
        for question in questions
    ]

    assert all(response.status_code == 200 for response in responses)
    assert [call["document_ids"] for call in policy_tool.calls] == [
        ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
        ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
        ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
        ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
    ]
    assert responses[2].json()["search_profile"] == "pension_payment"
    assert responses[2].json()["citations"]
    assert responses[0].json()["resolved_document_ids"] == responses[3].json()["resolved_document_ids"]


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
            "question": "보장 내용을 알려줘.",
            "session_id": "session-002",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_required"] is True
    assert payload["confidence_score"] == 0.2
    assert "질문 의도에 맞는 조항" in payload["answer"]
    assert firestore_service.saved_messages[-1]["role"] == "assistant"


def test_chat_requests_product_clarification_when_scope_is_ambiguous() -> None:
    client, _, _, _, _ = create_test_client(
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
            "session_id": "session-ambiguous",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "어떤 상품을 기준으로 확인할까요?" in payload["answer"]
    assert payload["fallback_required"] is True


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
                "focus_areas": ["연금개시 전 고도재해장해보험금", "연금개시 후 생존연금"],
                "main_focus": "연금개시 전후 보장 구조",
                "recommended_explanation_points": ["연금지급형태 중심으로 설명"],
                "caution_notes": ["공시이율 변동 가능성 확인 필요"],
                "evidence_summary": ["설명 근거 | annuity_payment | 연금지급형태 | annuity.pdf p.9"],
            },
            "recommended_products": [
                {
                    "document_id": "coverage-doc",
                    "document_name": "annuity.pdf",
                    "product_type": "annuity",
                    "recommendation_reason": "연금 니즈에 적합합니다.",
                }
            ],
            "current_design": {
                "session_id": "session-003",
                "customer_profile": {"product_preference": "current_document"},
                "product_type": "annuity",
                "selected_document_ids": ["coverage-doc"],
                "focus_areas": ["연금개시 전 고도재해장해보험금", "연금개시 후 생존연금"],
                "caution_notes": ["공시이율 변동 가능성 확인 필요"],
                "evidence_summary": ["설명 근거 | annuity_payment | 연금지급형태 | annuity.pdf p.9"],
                "coverages": ["연금개시 전 고도재해장해보험금", "연금개시 후 생존연금"],
            },
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
    assert payload["recommended_design"]["main_focus"]
    assert payload["recommended_products"][0]["product_type"] == "annuity"
    assert payload["current_design"]["product_type"] == "annuity"
    assert recommendation_tool.calls
    assert firestore_service.saved_messages[-1]["current_design"]["product_type"] == "annuity"
    assert firestore_service.saved_designs[0]["current_design"]["session_id"] == "session-003"
