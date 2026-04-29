"""Tests for MCP-compatible tool implementations."""

from __future__ import annotations

import json

from app.mcp_server.tools.design_condition_tool import DesignConditionTool
from app.mcp_server.tools.policy_search_tool import PolicySearchTool
from app.mcp_server.tools.product_recommend_tool import ProductRecommendTool


class MockStorageService:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads

    def download_bytes(self, gcs_uri: str) -> bytes:
        return self.payloads[gcs_uri].encode("utf-8")


class MockEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        text = texts[0]
        if "연금지급형태" in text or "생존연금" in text:
            return [[0.0, 1.0]]
        return [[1.0, 0.0]]


class MockFirestoreService:
    def __init__(self) -> None:
        self.documents = {
            "annuity-doc": {
                "document_id": "annuity-doc",
                "file_name": "annuity.pdf",
                "status": "indexed",
                "product_type": "annuity",
                "document_type": "product_summary",
            }
        }
        self.designs = {
            "session-1": {
                "session_id": "session-1",
                "current_design": {
                    "product_name": "연금보험",
                    "coverages": ["기본보장", "사망보험금"],
                },
            }
        }

    def get_document(self, document_id: str) -> dict[str, object] | None:
        return self.documents.get(document_id)

    def list_documents(self) -> list[dict[str, object]]:
        return list(self.documents.values())

    def get_current_design(self, session_id: str) -> dict[str, object] | None:
        return self.designs.get(session_id)

    def save_current_design(self, session_id: str, design: dict[str, object]) -> dict[str, object]:
        payload = {"session_id": session_id, "current_design": design}
        self.designs[session_id] = payload
        return payload


class FailingFirestoreService(MockFirestoreService):
    def save_current_design(self, session_id: str, design: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("firestore unavailable")


def _policy_payload() -> str:
    return "\n".join(
        [
            json.dumps(
                {
                    "document_id": "annuity-doc",
                    "document_name": "annuity.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "chunk_id": "c1",
                    "page": 3,
                    "end_page": 3,
                    "section": "보험료",
                    "normalized_section": "premium",
                    "content": "기본보험료와 적용이율을 설명합니다.",
                    "embedding": [1.0, 0.0],
                }
            ),
            json.dumps(
                {
                    "document_id": "annuity-doc",
                    "document_name": "annuity.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "chunk_id": "c2",
                    "page": 5,
                    "end_page": 5,
                    "section": "상품 특이사항",
                    "normalized_section": "product_overview",
                    "content": "상품 특이사항과 핵심 구조를 설명합니다.",
                    "embedding": [0.0, 1.0],
                }
            ),
            json.dumps(
                {
                    "document_id": "annuity-doc",
                    "document_name": "annuity.pdf",
                    "document_type": "policy_terms",
                    "product_type": "annuity",
                    "chunk_id": "c3",
                    "page": 7,
                    "end_page": 7,
                    "section": "보험금 지급사유",
                    "normalized_section": "coverage",
                    "content": "보험금 지급사유와 지급금액을 설명합니다.",
                    "embedding": [0.0, 1.0],
                }
            ),
            json.dumps(
                {
                    "document_id": "annuity-doc",
                    "document_name": "annuity.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "chunk_id": "c4",
                    "page": 9,
                    "end_page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "content": "연금개시후 연금지급형태와 생존연금 구조를 설명합니다.",
                    "embedding": [0.0, 1.0],
                }
            ),
        ]
    )


def create_policy_search_tool() -> PolicySearchTool:
    storage_service = MockStorageService({"gs://sample-bucket/indexes/annuity-doc/embeddings.jsonl": _policy_payload()})
    return PolicySearchTool(
        storage_service=storage_service,
        embedder=MockEmbedder(),
        firestore_service=MockFirestoreService(),
        bucket_name="sample-bucket",
    )


def test_policy_search_tool_uses_hybrid_rag_and_returns_fallback_signal() -> None:
    tool = create_policy_search_tool()

    result = tool.run(
        {
            "query": "이 상품의 주요 보장 내용은 뭐야?",
            "document_ids": ["annuity-doc"],
            "top_k": 3,
        }
    )

    assert result["status"] == "success"
    output = result["output"]
    assert output["search_profile"] == "coverage_summary"
    assert output["fallback_required"] is True
    assert "coverage" in output["normalized_section"]
    assert output["chunks"][0]["normalized_section"] in {"premium", "coverage", "product_overview"}
    assert output["chunks"][0]["hybrid_score"] is not None


def test_product_recommend_tool_builds_product_type_specific_summary() -> None:
    policy_tool = create_policy_search_tool()
    tool = ProductRecommendTool(policy_search_tool=policy_tool, firestore_service=MockFirestoreService())

    result = tool.run(
        {
            "query": "연금개시 후에는 어떤 방식으로 연금을 지급해?",
            "session_id": "session-1",
            "document_ids": ["annuity-doc"],
            "customer_profile": {"age_group": "50s"},
        }
    )

    assert result["status"] == "success"
    output = result["output"]
    assert output["recommended_design"]["product_type"] == "annuity"
    assert "연금개시 전 고도재해장해보험금" in output["recommended_design"]["focus_areas"]
    assert output["recommended_design"]["main_focus"]
    assert output["recommended_design"]["recommended_explanation_points"]
    assert output["recommended_design"]["caution_notes"]
    assert output["recommended_design"]["evidence_summary"]
    assert output["current_design"]["session_id"] == "session-1"
    assert output["current_design"]["product_type"] == "annuity"
    assert output["citations"]


def test_design_condition_tool_returns_before_and_after_design() -> None:
    tool = DesignConditionTool(firestore_service=MockFirestoreService())

    result = tool.run(
        {
            "session_id": "session-1",
            "add_coverages": ["연금지급형태"],
            "remove_coverages": ["사망보험금"],
            "keep_coverages": ["기본보장", "사망보험금"],
        }
    )

    assert result["status"] == "success"
    output = result["output"]
    assert output["previous_design"]["coverages"] == ["기본보장", "사망보험금"]
    assert output["updated_design"]["coverages"] == ["기본보장", "연금지급형태"]


def test_design_condition_tool_returns_error_result_when_firestore_save_fails() -> None:
    tool = DesignConditionTool(firestore_service=FailingFirestoreService())

    result = tool.run(
        {
            "session_id": "session-1",
            "add_coverages": ["연금지급형태"],
        }
    )

    assert result["status"] == "error"
    assert "Failed to persist current_design" in result["error"]
