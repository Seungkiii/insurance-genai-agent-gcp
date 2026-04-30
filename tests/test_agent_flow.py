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
        recommended_products: list[dict[str, Any]],
        comparison_result: dict[str, Any] | None,
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
                "recommended_products": recommended_products,
                "comparison_result": comparison_result,
                "current_design": current_design,
                "fallback_required": fallback_required,
            }
        )
        return "검색된 context만 기준으로 답변했습니다.\n\n본 답변은 약관 해석을 돕기 위한 참고 정보이며, 보험금 지급 확정 또는 보상 승인 판단을 의미하지 않습니다."


class FakeFirestoreService:
    def __init__(self) -> None:
        self.saved_interactions: list[dict[str, Any]] = []
        self.saved_designs: list[dict[str, Any]] = []
        self.saved_messages: list[dict[str, Any]] = []

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
            "confidence_score": confidence_score,
            "fallback_required": fallback_required,
            "citations": citations or [],
            "tool_trace": tool_trace or [],
            "recommended_design": recommended_design,
            "created_at": "2026-04-30T00:00:00+00:00",
        }
        self.saved_messages.append(payload)
        return payload

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return [message for message in self.saved_messages if message["session_id"] == session_id]

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        return {"session_id": session_id, "current_design": {"coverages": ["기본보장"]}}

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        payload = {"session_id": session_id, "current_design": design}
        self.saved_designs.append(payload)
        return payload


class FailingFirestoreService(FakeFirestoreService):
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
                "focus_areas": ["연금개시 전 고도재해장해보험금", "연금개시 후 생존연금"],
                "main_focus": "연금개시 전후 보장 구조",
                "recommended_explanation_points": ["상품 특이사항 중심으로 설명", "연금지급형태 중심으로 설명"],
                "caution_notes": ["공시이율 변동 가능성 확인 필요"],
                "evidence_summary": ["설명 근거 | annuity_payment | 연금지급형태 | annuity.pdf p.9"],
            },
            "recommended_products": [
                {
                    "document_id": "doc-1",
                    "document_name": "annuity.pdf",
                    "product_type": "annuity",
                    "recommendation_reason": "노후/연금 니즈와 잘 맞습니다.",
                }
            ],
            "current_design": {
                "session_id": "session-recommend",
                "customer_profile": {"age_group": "50대"},
                "product_type": "annuity",
                "selected_document_ids": ["doc-1"],
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
            "user_query": "55세 남성에게 적합한 보험 상품 추천해줘.",
        },
        dependencies,
    )

    assert result["intent"] == "multi_product_recommendation"
    assert result["recommended_design"] is not None
    assert result["recommended_products"]
    assert result["current_design"]["session_id"] == "session-recommend"
    assert result["current_design"]["product_type"] == "annuity"
    assert recommendation_tool.calls
    assert not policy_tool.calls
    assert [item["tool_name"] for item in result["tool_trace"]] == ["product_recommend_tool"]


def test_single_product_advice_calls_product_recommend_tool() -> None:
    dependencies, policy_tool, recommendation_tool, _, _ = create_dependencies()

    result = run_workflow(
        {
            "session_id": "session-single-advice",
            "user_query": "55세 남성 고객에게 이 상품을 설명한다면 어떤 보장과 유의사항 중심으로 안내하면 좋을까?",
            "document_ids": ["doc-1"],
        },
        dependencies,
    )

    assert result["intent"] == "single_product_advice"
    assert recommendation_tool.calls
    assert policy_tool.calls
    assert [item["tool_name"] for item in result["tool_trace"]] == ["product_recommend_tool", "policy_search_tool"]


def test_product_comparison_uses_policy_search_for_multiple_documents() -> None:
    dependencies, policy_tool, _, _, _ = create_dependencies()
    policy_tool.result = {
        **policy_tool.result,
        "chunks": [
            {
                "document_id": "doc-1",
                "document_name": "annuity-a.pdf",
                "document_type": "product_summary",
                "product_type": "annuity",
                "page": 3,
                "section": "상품 특이사항",
                "normalized_section": "product_overview",
                "content": "A 상품 설명",
            },
            {
                "document_id": "doc-2",
                "document_name": "annuity-b.pdf",
                "document_type": "product_summary",
                "product_type": "health",
                "page": 4,
                "section": "보험금 지급사유",
                "normalized_section": "coverage",
                "content": "B 상품 설명",
            },
        ],
    }

    result = run_workflow(
        {
            "session_id": "session-compare",
            "user_query": "이 두 상품 중 50대 남성에게 더 적합한 상품은 뭐야? 비교해줘.",
            "document_ids": ["doc-1", "doc-2"],
        },
        dependencies,
    )

    assert result["intent"] == "product_comparison"
    assert policy_tool.calls
    assert policy_tool.calls[0]["document_ids"] == ["doc-1", "doc-2"]
    assert result["comparison_result"] is not None


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
    assert result["tool_trace"][-1]["tool_name"] == "persist_node"
