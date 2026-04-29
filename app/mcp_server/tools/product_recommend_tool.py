"""Product recommendation tool grounded in multi-product insurance RAG evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseTool
from .policy_search_tool import PolicySearchTool

RECOMMENDATION_GUIDANCE: dict[str, list[str]] = {
    "annuity": ["연금개시 전 보장", "연금개시 후 지급방식", "중도인출/추가납입 유의사항"],
    "whole_life": ["사망보험금", "체증 여부", "해약환급금 일부지급형", "전환 기능"],
    "cancer": ["암 종류별 진단비", "면책기간", "보장체증 여부"],
    "health": ["주요 질환", "진단비/입원/수술", "환급 구조"],
    "dental": ["보철/보존/크라운/임플란트", "면책/감액기간"],
}


@dataclass
class ProductRecommendTool(BaseTool):
    """Create evidence-based recommendation scaffolds from policy search results."""

    policy_search_tool: PolicySearchTool
    name: str = "product_recommend_tool"
    description: str = (
        "Build product recommendation guidance from policy_search_tool evidence without inventing insured amounts or deterministic sales advice."
    )
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "session_id": {"type": "string"},
                "document_ids": {"type": "array", "items": {"type": "string"}},
                "customer_profile": {"type": "object"},
            },
            "required": ["query", "session_id"],
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "recommended_design": {"type": "object"},
                "evidence_summary": {"type": "array"},
                "citations": {"type": "array"},
                "caution_notes": {"type": "array"},
            },
        }
    )

    def execute(self, payload: dict[str, Any], trace_summary: list[str]) -> dict[str, Any]:
        """Build a product-type-aware recommendation summary."""
        query = str(payload.get("query", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        if not query or not session_id:
            raise ValueError("Both 'query' and 'session_id' are required.")

        policy_result = self.policy_search_tool.run(
            {
                "query": query,
                "document_ids": payload.get("document_ids", []),
                "product_type": payload.get("product_type"),
                "top_k": payload.get("top_k", 5),
            }
        )
        trace_summary.append(f"policy_search_status={policy_result['status']}")
        if policy_result["status"] != "success":
            raise RuntimeError(policy_result.get("error") or "policy_search_tool failed.")

        search_output = policy_result["output"] or {}
        product_type = str(search_output.get("product_type") or "unknown")
        evidence_summary = _build_evidence_summary(search_output.get("chunks", []))
        recommended_design = {
            "session_id": session_id,
            "customer_profile": payload.get("customer_profile", {}),
            "product_type": product_type,
            "focus_areas": RECOMMENDATION_GUIDANCE.get(
                product_type,
                ["핵심 보장", "지급 조건", "유의사항"],
            ),
            "note": "근거 문서에 나타난 보장 구조를 요약한 것으로, 임의 가입금액이나 확정 추천은 포함하지 않습니다.",
        }
        caution_notes = _build_caution_notes(search_output)

        return {
            "query": query,
            "search_profile": search_output.get("search_profile"),
            "recommended_design": recommended_design,
            "evidence_summary": evidence_summary,
            "citations": search_output.get("citations", []),
            "caution_notes": caution_notes,
        }


def _build_evidence_summary(chunks: list[dict[str, Any]]) -> list[str]:
    summaries: list[str] = []
    for chunk in chunks[:4]:
        summaries.append(
            f"{chunk['normalized_section']} | {chunk['section']} | {chunk['document_name']} p.{chunk['page']}"
        )
    return summaries


def _build_caution_notes(search_output: dict[str, Any]) -> list[str]:
    notes = [
        "추천 결과는 검색된 상품 설명서와 약관 근거를 요약한 것이며, 확정 인수나 지급 판단을 의미하지 않습니다.",
        "세부 인수 조건, 면책기간, 감액기간, 지급 제한은 반드시 원문 약관을 추가 확인해야 합니다.",
    ]
    if search_output.get("fallback_required"):
        notes.append("검색 결과가 질문 의도와 완전히 일치하지 않을 수 있어 추가 확인이 필요합니다.")
    return notes
