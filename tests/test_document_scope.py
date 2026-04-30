"""Tests for session-aware document scope resolution."""

from __future__ import annotations

from app.services.document_context_service import resolve_document_scope


class StubFirestoreService:
    def __init__(self) -> None:
        self.documents = {
            "doc-1": {
                "document_id": "doc-1",
                "file_name": "annuity-a.pdf",
                "document_name": "annuity-a.pdf",
                "product_name": "연금보험 A",
                "status": "indexed",
                "product_type": "annuity",
                "document_type": "product_summary",
            },
            "doc-2": {
                "document_id": "doc-2",
                "file_name": "health-a.pdf",
                "document_name": "health-a.pdf",
                "product_name": "건강보험 A",
                "status": "indexed",
                "product_type": "health",
                "document_type": "policy_terms",
            },
        }
        self.session_contexts: dict[str, dict[str, object]] = {}

    def get_document(self, document_id: str) -> dict[str, object] | None:
        return self.documents.get(document_id)

    def list_documents(self) -> list[dict[str, object]]:
        return list(self.documents.values())

    def get_session_context(self, session_id: str) -> dict[str, object] | None:
        return self.session_contexts.get(session_id)


def test_request_document_ids_take_priority() -> None:
    service = StubFirestoreService()
    service.session_contexts["session-1"] = {
        "session_id": "session-1",
        "selected_document_ids": ["doc-2"],
        "selected_product_names": ["건강보험 A"],
        "search_scope": "selected",
    }

    scope = resolve_document_scope(
        session_id="session-1",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=["doc-1"],
        request_search_scope=None,
        query="이 상품의 보장 내용을 알려줘",
    )

    assert scope.document_ids == ["doc-1"]
    assert scope.source == "request"


def test_duplicated_request_document_ids_are_deduplicated() -> None:
    service = StubFirestoreService()

    scope = resolve_document_scope(
        session_id="session-dedup",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=["doc-1", "doc-1", "doc-1"],
        request_search_scope=None,
        query="이 상품의 보장 내용을 알려줘",
    )

    assert scope.document_ids == ["doc-1"]
    assert scope.invalid_document_ids == []


def test_invalid_request_document_ids_are_removed_and_recorded() -> None:
    service = StubFirestoreService()
    service.session_contexts["session-invalid"] = {
        "session_id": "session-invalid",
        "selected_document_ids": ["doc-2"],
        "selected_product_names": ["건강보험 A"],
        "search_scope": "selected",
    }

    scope = resolve_document_scope(
        session_id="session-invalid",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=["health-a.pdf", "", "missing-doc"],
        request_search_scope=None,
        query="유의사항도 알려줘",
    )

    assert scope.document_ids == ["doc-2"]
    assert scope.source == "session"
    assert "health-a.pdf" in scope.invalid_document_ids
    assert "missing-doc" in scope.invalid_document_ids


def test_session_selected_document_ids_are_used_when_request_is_empty() -> None:
    service = StubFirestoreService()
    service.session_contexts["session-2"] = {
        "session_id": "session-2",
        "selected_document_ids": ["doc-2"],
        "selected_product_names": ["건강보험 A"],
        "search_scope": "selected",
    }

    scope = resolve_document_scope(
        session_id="session-2",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=None,
        request_search_scope=None,
        query="유의사항도 알려줘",
    )

    assert scope.document_ids == ["doc-2"]
    assert scope.source == "session"


def test_all_indexed_documents_are_used_when_no_request_or_session_selection_exists() -> None:
    service = StubFirestoreService()

    scope = resolve_document_scope(
        session_id="session-3",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=None,
        request_search_scope=None,
        query="건강보험 주요 보장 알려줘",
    )

    assert set(scope.document_ids) == {"doc-1", "doc-2"}
    assert scope.source == "all_documents"


def test_fallback_message_is_returned_when_no_indexed_documents_exist() -> None:
    service = StubFirestoreService()
    service.documents = {}

    scope = resolve_document_scope(
        session_id="session-4",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=None,
        request_search_scope=None,
        query="이 상품의 주요 보장은 뭐야?",
    )

    assert scope.document_ids == []
    assert scope.fallback_message is not None
    assert "indexed 문서가 없습니다" in scope.fallback_message


def test_search_scope_all_ignores_session_selected_documents() -> None:
    service = StubFirestoreService()
    service.session_contexts["session-5"] = {
        "session_id": "session-5",
        "selected_document_ids": ["doc-2"],
        "selected_product_names": ["건강보험 A"],
        "search_scope": "all",
    }

    scope = resolve_document_scope(
        session_id="session-5",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=None,
        request_search_scope=None,
        query="여러 상품 중 어떤 상품이 적합해?",
    )

    assert set(scope.document_ids) == {"doc-1", "doc-2"}
    assert scope.search_scope == "all"


def test_request_search_scope_all_overrides_session_selected_documents() -> None:
    service = StubFirestoreService()
    service.session_contexts["session-6"] = {
        "session_id": "session-6",
        "selected_document_ids": ["doc-2"],
        "selected_product_names": ["건강보험 A"],
        "search_scope": "selected",
    }

    scope = resolve_document_scope(
        session_id="session-6",
        firestore_service=service,  # type: ignore[arg-type]
        request_document_ids=None,
        request_search_scope="all",
        query="여러 상품 중 어떤 상품이 적합해?",
    )

    assert set(scope.document_ids) == {"doc-1", "doc-2"}
    assert scope.search_scope == "all"
