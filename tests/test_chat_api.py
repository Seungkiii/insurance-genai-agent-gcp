"""Tests for the indexed-document chat API."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api.chat import get_answer_generator, get_firestore_service, get_query_embedder, get_storage_service
from app.main import create_app
from app.rag.generator import AnswerGenerator
from app.rag.retriever import RetrievalResult


class FakeStorageService:
    """Mock storage service that returns stored embedding artifacts."""

    def download_bytes(self, gcs_uri: str) -> bytes:
        if gcs_uri.endswith("doc-001/embeddings.jsonl"):
            return (
                '{"document_id":"doc-001","document_name":"policy-a.pdf","chunk_id":"doc-001-chunk-0001","page":2,"section":"보험금 지급","content":"보험금 지급 기준은 약관에 따릅니다.","embedding":[1.0,0.0,0.0]}\n'
                '{"document_id":"doc-001","document_name":"policy-a.pdf","chunk_id":"doc-001-chunk-0002","page":4,"section":"청구 서류","content":"보험금 청구서와 신분증 사본이 필요합니다.","embedding":[0.0,1.0,0.0]}'
            ).encode("utf-8")
        raise FileNotFoundError(gcs_uri)


class FakeEmbedder:
    """Mock query embedder."""

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == 1
        return [self.vector]


class ConditionalFakeEmbedder:
    """Mock embedder that changes vectors for expanded fallback queries."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == 1
        text = texts[0]
        if "보험금 지급사유" in text and "연금지급형태" in text:
            return [[0.0, 1.0]]
        return [[1.0, 0.0]]


class CoverageFallbackStorageService:
    """Mock storage service to validate fallback retrieval for major coverage questions."""

    def download_bytes(self, gcs_uri: str) -> bytes:
        if gcs_uri.endswith("coverage-doc/embeddings.jsonl"):
            payload = "\n".join(
                [
                    json.dumps(
                        {
                            "document_id": "coverage-doc",
                            "document_name": "2025041516121911948953.pdf",
                            "chunk_id": "coverage-doc-chunk-0001",
                            "page": 22,
                            "section": "보험료",
                            "content": "1차월 기본보험료의 3.400%(1,700,000원)가 안내됩니다.",
                            "embedding": [1.0, 0.0],
                        }
                    ),
                    json.dumps(
                        {
                            "document_id": "coverage-doc",
                            "document_name": "2025041516121911948953.pdf",
                            "chunk_id": "coverage-doc-chunk-0002",
                            "page": 3,
                            "section": "상품 특이사항",
                            "content": "이 상품의 특이사항과 핵심 보장 구조를 설명합니다.",
                            "embedding": [0.0, 1.0],
                        }
                    ),
                    json.dumps(
                        {
                            "document_id": "coverage-doc",
                            "document_name": "2025041516121911948953.pdf",
                            "chunk_id": "coverage-doc-chunk-0003",
                            "page": 7,
                            "section": "보험금 지급사유",
                            "content": "고도재해장해보험금의 보험금 지급사유와 지급금액을 안내합니다.",
                            "embedding": [0.0, 1.0],
                        }
                    ),
                    json.dumps(
                        {
                            "document_id": "coverage-doc",
                            "document_name": "2025041516121911948953.pdf",
                            "chunk_id": "coverage-doc-chunk-0004",
                            "page": 9,
                            "section": "연금지급형태",
                            "content": "연금개시후 연금지급형태와 생존연금 지급 구조를 안내합니다.",
                            "embedding": [0.0, 1.0],
                        }
                    ),
                ]
            )
            return payload.encode("utf-8")
        raise FileNotFoundError(gcs_uri)


class FakeGenerator(AnswerGenerator):
    """Mock Gemini generator."""

    def generate(self, question: str, results: list[RetrievalResult]) -> str:
        assert question
        assert results
        return "검색된 근거를 바탕으로 답변을 생성했습니다.\n\n본 답변은 약관 해석을 돕기 위한 참고 정보이며, 보험금 지급 확정 또는 보상 승인 판단을 의미하지 않습니다."


class FakeFirestoreService:
    """Mock Firestore service that records saved chat interactions."""

    def __init__(self) -> None:
        self.saved_interactions: list[dict[str, object]] = []

    def save_chat_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        citations: list[dict[str, object]],
        latency_ms: int,
    ) -> dict[str, object]:
        payload = {
            "session_id": session_id,
            "user_message": user_message,
            "assistant_answer": assistant_answer,
            "citations": citations,
            "latency_ms": latency_ms,
        }
        self.saved_interactions.append(payload)
        return payload


def create_test_client(
    *,
    query_vector: list[float],
) -> tuple[TestClient, FakeFirestoreService]:
    """Create a chat client with mocked retrieval and generation dependencies."""
    app = create_app()
    firestore_service = FakeFirestoreService()
    app.dependency_overrides[get_storage_service] = lambda: FakeStorageService()
    app.dependency_overrides[get_query_embedder] = lambda: FakeEmbedder(query_vector)
    app.dependency_overrides[get_answer_generator] = lambda: FakeGenerator()
    app.dependency_overrides[get_firestore_service] = lambda: firestore_service
    return TestClient(app), firestore_service


def create_major_coverage_test_client() -> tuple[TestClient, FakeFirestoreService]:
    """Create a chat client that exercises retrieval fallback for major coverage questions."""
    app = create_app()
    firestore_service = FakeFirestoreService()
    app.dependency_overrides[get_storage_service] = lambda: CoverageFallbackStorageService()
    app.dependency_overrides[get_query_embedder] = lambda: ConditionalFakeEmbedder()
    app.dependency_overrides[get_answer_generator] = lambda: FakeGenerator()
    app.dependency_overrides[get_firestore_service] = lambda: firestore_service
    return TestClient(app), firestore_service


def test_chat_returns_grounded_answer_and_citations() -> None:
    """High-similarity results should return a grounded answer with citations."""
    client, firestore_service = create_test_client(query_vector=[1.0, 0.0, 0.0])

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
    assert payload["citations"]
    assert payload["citations"][0]["document_name"] == "policy-a.pdf"
    assert payload["citations"][0]["score"] > 0.9
    assert payload["confidence_score"] > 0
    assert "보험금 지급 여부는 실제 약관" in payload["disclaimer"]
    assert firestore_service.saved_interactions


def test_chat_requests_more_information_when_scores_are_low() -> None:
    """Low-similarity results should avoid definitive answers and request more detail."""
    client, firestore_service = create_test_client(query_vector=[0.0, 0.0, 1.0])

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "이 상품 괜찮나요?",
            "session_id": "session-002",
            "document_ids": ["doc-001"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "추가 정보를 알려주시면" in payload["answer"]
    assert payload["confidence_score"] <= 0.2
    assert firestore_service.saved_interactions


def test_chat_major_coverage_question_retries_with_expanded_query() -> None:
    """Major coverage questions should fall back to coverage-centric sections instead of premium chunks."""
    client, firestore_service = create_major_coverage_test_client()

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "이 상품의 주요 보장 내용은 뭐야?",
            "session_id": "session-coverage-001",
            "document_ids": ["coverage-doc"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    sections = [citation["section"] for citation in payload["citations"]]
    assert "상품 특이사항" in sections
    assert "보험금 지급사유" in sections
    assert "연금지급형태" in sections
    assert sections[0] != "보험료"
    assert payload["confidence_score"] >= 0.45
    assert firestore_service.saved_interactions
