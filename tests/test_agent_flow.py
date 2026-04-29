"""Tests for the insurance workflow agent."""

from __future__ import annotations

from typing import Any

from app.agents.dependencies import WorkflowDependencies
from app.agents.graph import run_workflow


class FakeTool:
    def __init__(self, name: str, result: dict[str, Any]) -> None:
        self.name = name
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        response = {
            "tool_name": self.name,
            "status": "success",
            "input": payload,
            "output": self.result,
            "latency_ms": 12,
            "error": None,
            "trace_summary": [],
        }
        return response


class FakeGenerator:
    def __init__(self) -> None:
        self.prompts: list[dict[str, Any]] = []

    def generate_agent_response(
        self,
        *,
        question: str,
        intent: str,
        search_profile: str | None,
        retrieved_chunks: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        recommended_design: dict[str, Any] | None,
        current_design: dict[str, Any] | None,
        fallback_required: bool,
    ) -> str:
        self.prompts.append(
            {
                "question": question,
                "intent": intent,
                "search_profile": search_profile,
                "retrieved_chunks": retrieved_chunks,
                "citations": citations,
                "recommended_design": recommended_design,
                "current_design": current_design,
                "fallback_required": fallback_required,
            }
        )
        return "검색된 context만 기준으로 답변했습니다.\n\n본 답변은 약관 해석을 돕기 위한 참고 정보이며, 보험금 지급 확정 또는 보상 승인 판단을 의미하지 않습니다."


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


class FailingFirestoreService(FakeFirestoreService):
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
        raise RuntimeError("firestore unavailable")


def create_dependencies(*, firestore_service: FakeFirestoreService | None = None) -> tuple[WorkflowDependencies, FakeTool, FakeTool, FakeTool, FakeGenerator]:
    policy_tool = FakeTool(
        "policy_search_tool",
        {
            "search_profile": "coverage_summary",
            "product_type": "annuity",
            "document_type": "product_summary",
            "normalized_section": ["product_overview", "coverage"],
            "chunks": [
                {
                    "document_id": "doc-1",
                    "document_name": "annuity.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "page": 3,
                    "section": "상품 특이사항",
                    "normalized_section": "product_overview",
                    "content": "핵심 보장 구조를 설명합니다.",
                }
            ],
            "citations": [
                {
                    "document_name": "annuity.pdf",
                    "page": 3,
                    "section": "상품 특이사항",
                    "normalized_section": "product_overview",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "content_preview": "핵심 보장 구조를 설명합니다.",
                    "score": 0.86,
                }
            ],
            "confidence_score": 0.82,
            "fallback_required": False,
        },
    )
    recommendation_tool = FakeTool(
        "product_recommend_tool",
        {
            "search_profile": "coverage_summary",
            "recommended_design": {
                "session_id": "session-recommend",
                "product_type": "annuity",
                "focus_areas": ["연금개시 후 지급방식", "중도인출 유의사항"],
            },
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
    design_tool = FakeTool(
        "design_condition_tool",
        {
            "session_id": "session-modify",
            "previous_design": {"coverages": ["기본보장", "사망보험금"]},
            "updated_design": {"coverages": ["기본보장", "암진단비"]},
            "applied_changes": {"add_coverages": ["암진단비"], "remove_coverages": ["사망보험금"]},
        },
    )
    generator = FakeGenerator()
    dependencies = WorkflowDependencies(
        policy_search_tool=policy_tool,  # type: ignore[arg-type]
        product_recommend_tool=recommendation_tool,  # type: ignore[arg-type]
        design_condition_tool=design_tool,  # type: ignore[arg-type]
        answer_generator=generator,
        firestore_service=firestore_service or FakeFirestoreService(),  # type: ignore[arg-type]
    )
    return dependencies, policy_tool, recommendation_tool, design_tool, generator


def test_policy_qa_flow_uses_policy_search_and_returns_profile_aware_output() -> None:
    dependencies, policy_tool, _, _, generator = create_dependencies()

    result = run_workflow(
        {
            "session_id": "session-policy",
            "user_query": "이 상품의 주요 보장 내용은 뭐야?",
            "document_ids": ["doc-1", "doc-2"],
            "top_k": 4,
        },
        dependencies,
    )

    assert result["intent"] == "policy_qa"
    assert result["search_profile"] == "coverage_summary"
    assert result["citations"]
    assert result["tool_trace"][0]["tool_name"] == "policy_search_tool"
    assert policy_tool.calls[0]["document_ids"] == ["doc-1", "doc-2"]
    assert generator.prompts[0]["search_profile"] == "coverage_summary"
    assert result["confidence_score"] == 0.82


def test_design_recommendation_flow_runs_recommendation_then_policy_search() -> None:
    dependencies, policy_tool, recommendation_tool, _, _ = create_dependencies()

    result = run_workflow(
        {
            "session_id": "session-recommend",
            "user_query": "50s 고객에게 연금보험 추천 설계안을 근거와 함께 알려줘.",
            "document_ids": ["doc-1"],
        },
        dependencies,
    )

    assert result["intent"] == "design_recommendation"
    assert result["recommended_design"] is not None
    assert result["current_design"] == {"coverages": ["기본보장"]}
    assert recommendation_tool.calls
    assert policy_tool.calls
    assert [item["tool_name"] for item in result["tool_trace"]] == [
        "product_recommend_tool",
        "policy_search_tool",
    ]


def test_design_modification_flow_updates_current_design_from_tool() -> None:
    dependencies, _, _, design_tool, _ = create_dependencies()

    result = run_workflow(
        {
            "session_id": "session-modify",
            "user_query": "사망보험금은 빼고 암진단비를 추가해줘.",
        },
        dependencies,
    )

    assert result["intent"] == "design_modification"
    assert design_tool.calls
    assert result["current_design"] == {"coverages": ["기본보장", "암진단비"]}
    assert result["tool_trace"][0]["tool_name"] == "design_condition_tool"


def test_guardrail_restricts_answer_when_citations_are_missing() -> None:
    dependencies, policy_tool, _, _, _ = create_dependencies()
    policy_tool.result = {
        "search_profile": "coverage_summary",
        "product_type": "annuity",
        "document_type": "product_summary",
        "normalized_section": [],
        "chunks": [],
        "citations": [],
        "confidence_score": 0.1,
        "fallback_required": True,
    }

    result = run_workflow(
        {
            "session_id": "session-guard",
            "user_query": "보장 내용을 알려줘",
        },
        dependencies,
    )

    assert result["fallback_required"] is True
    assert "확정적인 답변은 제한" in result["disclaimer"]
    assert "질문 의도에 맞는 조항" in result["answer"]


def test_persist_node_does_not_fail_user_response_when_firestore_save_fails() -> None:
    dependencies, _, _, _, _ = create_dependencies(firestore_service=FailingFirestoreService())

    result = run_workflow(
        {
            "session_id": "session-persist-fail",
            "user_query": "이 상품의 주요 보장 내용은 뭐야?",
        },
        dependencies,
    )

    assert result["answer"]
    assert result["persistence_error"] == "firestore unavailable"
