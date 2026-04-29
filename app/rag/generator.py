"""Grounded answer generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.rag.retriever import RetrievalResult
from app.rag.search_profiles import SearchProfile
from app.services.vertex_ai_service import VertexAIGenerationService

GUARDRAIL_TEXT = "본 답변은 약관 해석을 돕기 위한 참고 정보이며, 보험금 지급 확정 또는 보상 승인 판단을 의미하지 않습니다."

PRODUCT_TYPE_GUIDANCE: dict[str, str] = {
    "annuity": "연금보험 질문이면 연금개시 전 보장, 연금개시 후 지급방식, 추가납입 또는 중도인출 가능성, 유의사항 순으로 정리하세요.",
    "whole_life": "종신보험 질문이면 사망보험금, 체증 여부, 해약환급금 일부지급형 여부, 전환 기능, 유의사항 순으로 정리하세요.",
    "cancer": "암보험 질문이면 암 종류별 진단비, 보장개시일, 면책기간 또는 감액기간, 지급제한, 유의사항 순으로 정리하세요.",
    "health": "건강보험 질문이면 주요 질환 보장, 진단비·입원·수술 보장, 환급 구조, 유의사항 순으로 정리하세요.",
    "accident": "상해보험 질문이면 재해사망, 재해장해, 직업급수, 지급제한, 유의사항 순으로 정리하세요.",
    "dental": "치아보험 질문이면 보철치료, 보존치료, 크라운, 임플란트, 면책기간 또는 감액기간, 유의사항 순으로 정리하세요.",
}


class AnswerGenerator(Protocol):
    """Interface for retrieval-grounded answer generation implementations."""

    def generate(
        self,
        question: str,
        results: list[RetrievalResult],
        *,
        search_profile: SearchProfile,
        fallback_required: bool,
    ) -> str:
        """Generate a grounded answer from retrieved evidence."""


class WorkflowAnswerGenerator(Protocol):
    """Interface for workflow-level answer generation."""

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
        """Generate a workflow response constrained to retrieved evidence."""


@dataclass
class GeminiAnswerGenerator:
    """Answer generator backed by Gemini through a service facade."""

    generation_service: VertexAIGenerationService

    def generate(
        self,
        question: str,
        results: list[RetrievalResult],
        *,
        search_profile: SearchProfile,
        fallback_required: bool,
    ) -> str:
        """Generate a grounded answer using retrieved context."""
        context_blocks = [
            {
                "document_name": result.chunk.document_name,
                "document_type": result.chunk.document_type,
                "product_type": result.chunk.product_type,
                "section": result.chunk.section,
                "normalized_section": result.chunk.normalized_section,
                "page": result.chunk.page,
                "content": result.chunk.content,
            }
            for result in results
        ]
        citations = [
            {
                "document_name": result.chunk.document_name,
                "page": result.chunk.page,
                "section": result.chunk.section,
                "normalized_section": result.chunk.normalized_section,
            }
            for result in results[:5]
        ]
        return self.generate_agent_response(
            question=question,
            intent="policy_qa",
            search_profile=search_profile.name,
            retrieved_chunks=context_blocks,
            citations=citations,
            recommended_design=None,
            recommended_products=[],
            comparison_result=None,
            current_design=None,
            fallback_required=fallback_required,
        )

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
        """Generate a workflow answer constrained to retrieved evidence."""
        primary_product_type = "unknown"
        if retrieved_chunks:
            primary_product_type = str(retrieved_chunks[0].get("product_type") or "unknown")
        elif recommended_design and recommended_design.get("product_type"):
            primary_product_type = str(recommended_design["product_type"])
        product_guidance = PRODUCT_TYPE_GUIDANCE.get(primary_product_type, "질문 의도에 맞는 보장, 조건, 유의사항을 구분해서 설명하세요.")

        chunk_blocks = [
            (
                f"[문서: {chunk.get('document_name')} | 문서유형: {chunk.get('document_type')} | "
                f"상품군: {chunk.get('product_type')} | 섹션: {chunk.get('section')} | "
                f"정규화섹션: {chunk.get('normalized_section')} | 페이지: {chunk.get('page')}]\n"
                f"{chunk.get('content') or chunk.get('content_preview') or ''}"
            )
            for chunk in retrieved_chunks[:6]
        ]

        prompt = (
            "당신은 Insurance Workflow Agent입니다.\n"
            "검색된 context와 상태 정보 밖의 내용을 단정하지 마세요.\n"
            "answer는 반드시 근거 중심으로 작성하고, citation이 없는 내용을 사실처럼 쓰지 마세요.\n"
            "보험금 지급 확정, 보상 승인 확정, 인수 확정 표현은 금지합니다.\n"
            "상품요약서 기준과 실제 약관 확인 필요성을 자연스럽게 포함하세요.\n"
            "search_profile, product_type, document_type, normalized_section을 반영해 답변 구조를 조정하세요.\n"
            "summary/coverage 질문이면 주요 보장, 상품 기능, 유의사항, 근거 순으로 정리하세요.\n"
            "coverage_summary에서는 exclusions를 주요 보장 근거로 쓰지 말고 유의사항 근거로만 사용하세요.\n"
            "single_product_advice이면 설명 포인트, 유의사항, 근거를 구분하세요.\n"
            "multi_product_recommendation이면 상품별 추천 이유를 비교형으로 정리하세요.\n"
            "product_comparison이면 상품별 보장, 유의사항, 적합 고객을 비교 요약하세요.\n"
            "design_modification이면 변경된 current_design만 설명하고 없는 조건을 꾸며내지 마세요.\n"
            f"intent: {intent}\n"
            f"search_profile: {search_profile}\n"
            f"fallback_required: {fallback_required}\n"
            f"상품군 가이드: {product_guidance}\n"
            f"추천 설계: {recommended_design}\n"
            f"추천 상품 목록: {recommended_products}\n"
            f"비교 결과: {comparison_result}\n"
            f"현재 설계: {current_design}\n"
            f"citations: {citations}\n\n"
            f"질문:\n{question}\n\n"
            f"검색 근거:\n{'\n\n'.join(chunk_blocks)}\n\n"
            "답변:"
        )
        answer = self.generation_service.generate_text(prompt)
        return f"{answer}\n\n{GUARDRAIL_TEXT}"


def build_low_confidence_answer() -> str:
    """Return a fallback answer when retrieval confidence is weak."""
    return (
        "현재 검색된 근거만으로는 질문 의도에 맞는 조항을 충분히 찾지 못했습니다. "
        "상품명, 보장 항목, 지급 조건, 보험료, 해약환급금, 청구 서류 중 어떤 내용을 확인하려는지 조금 더 구체적으로 알려주시면 다시 찾아드릴 수 있습니다.\n\n"
        f"{GUARDRAIL_TEXT}"
    )
