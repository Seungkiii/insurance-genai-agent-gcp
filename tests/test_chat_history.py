"""Tests for session message history APIs and persistence behavior."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.agents.dependencies import WorkflowDependencies
from app.api.chat import get_workflow_dependencies
from app.api.sessions import get_firestore_service
from app.main import create_app


class FakeTool:
    def __init__(self, name: str, output: dict[str, Any]) -> None:
        self.name = name
        self.output = output

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool_name": self.name,
            "status": "success",
            "input": payload,
            "output": self.output,
            "latency_ms": 5,
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
        return "테스트용 응답입니다."


class MemoryFirestoreService:
    def __init__(self) -> None:
        self.saved_messages: list[dict[str, Any]] = []
        self.saved_designs: list[dict[str, Any]] = []
        self.session_contexts: dict[str, dict[str, Any]] = {}
        self.documents = {
            "doc-1": {
                "document_id": "doc-1",
                "file_name": "annuity.pdf",
                "document_name": "annuity.pdf",
                "product_name": "무배당엔젤하이브리드연금보험",
                "status": "indexed",
                "product_type": "annuity",
                "document_type": "product_summary",
            }
        }

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
            "created_at": "2026-04-30T00:00:00+00:00",
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
        }
        self.saved_messages.append(payload)
        return payload

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return [message for message in self.saved_messages if message["session_id"] == session_id]

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        for design in reversed(self.saved_designs):
            if design["session_id"] == session_id:
                return design
        return None

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        payload = {"session_id": session_id, "current_design": design}
        self.saved_designs.append(payload)
        self.update_session_context(session_id, current_design=design)
        return payload

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


class FailingMessageFirestoreService(MemoryFirestoreService):
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
        raise RuntimeError("firestore unavailable")


def create_history_client(
    firestore_service: MemoryFirestoreService,
) -> TestClient:
    app = create_app()
    dependencies = WorkflowDependencies(
        policy_search_tool=FakeTool(
            "policy_search_tool",
            {
                "search_profile": "coverage_summary",
                "product_type": "annuity",
                "document_type": "product_summary",
                "normalized_section": ["coverage"],
                "chunks": [],
                "citations": [],
                "confidence_score": 0.67,
                "fallback_required": False,
            },
        ),  # type: ignore[arg-type]
        product_recommend_tool=FakeTool("product_recommend_tool", {}),  # type: ignore[arg-type]
        design_condition_tool=FakeTool("design_condition_tool", {}),  # type: ignore[arg-type]
        answer_generator=FakeGenerator(),  # type: ignore[arg-type]
        firestore_service=firestore_service,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_workflow_dependencies] = lambda: dependencies
    app.dependency_overrides[get_firestore_service] = lambda: firestore_service
    return TestClient(app)


def test_session_messages_returns_empty_history() -> None:
    client = create_history_client(MemoryFirestoreService())

    response = client.get("/api/v1/sessions/empty-session/messages")

    assert response.status_code == 200
    assert response.json() == {"session_id": "empty-session", "messages": []}


def test_chat_persists_user_and_assistant_messages() -> None:
    firestore_service = MemoryFirestoreService()
    client = create_history_client(firestore_service)

    response = client.post(
        "/api/v1/chat",
        json={"question": "이 상품의 주요 보장 내용은 뭐야?", "session_id": "session-history-1"},
    )

    assert response.status_code == 200
    roles = [message["role"] for message in firestore_service.saved_messages]
    assert roles == ["user", "assistant"]

    history_response = client.get("/api/v1/sessions/session-history-1/messages")
    payload = history_response.json()
    assert history_response.status_code == 200
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "assistant"


def test_chat_succeeds_when_firestore_message_persistence_fails() -> None:
    client = create_history_client(FailingMessageFirestoreService())

    response = client.post(
        "/api/v1/chat",
        json={"question": "연금개시 후에는 어떤 방식으로 연금을 지급해?", "session_id": "session-history-2"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-history-2"
    assert payload["answer"]
