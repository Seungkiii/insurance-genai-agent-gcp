"""Grounded answer generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
    """Interface for answer generation implementations."""

    def generate(
        self,
        question: str,
        results: list[RetrievalResult],
        *,
        search_profile: SearchProfile,
        fallback_required: bool,
    ) -> str:
        """Generate a grounded answer from retrieved evidence."""


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
            (
                f"[문서: {result.chunk.document_name} | 문서유형: {result.chunk.document_type} | "
                f"상품군: {result.chunk.product_type} | 섹션: {result.chunk.section} | "
                f"정규화섹션: {result.chunk.normalized_section} | 페이지: {result.chunk.page}]\n"
                f"{result.chunk.content}"
            )
            for result in results
        ]
        primary_product_type = results[0].chunk.product_type if results else "unknown"
        product_guidance = PRODUCT_TYPE_GUIDANCE.get(primary_product_type, "질문 의도에 맞는 보장, 조건, 유의사항을 구분해서 설명하세요.")

        prompt = (
            "당신은 보험상품 설명서 RAG Assistant입니다.\n"
            "검색된 context 안에서만 답변하고, citation에 없는 내용을 단정하지 마세요.\n"
            "답변은 기본적으로 요약 -> 근거 -> 유의사항 -> 추가 확인사항 구조를 따르세요.\n"
            "여러 보장 항목이 있으면 목록형으로 요약하고, 보험금 지급 확정 표현은 금지하세요.\n"
            "상품요약서 기준임을 적절히 밝히고, 약관 확인 필요 및 심사 결과에 따라 달라질 수 있음을 안내하세요.\n"
            "문서 표현이 'A를 B로 본다' 또는 '간주한다'에 가까우면, 이를 '지급된다'처럼 단정적으로 바꾸지 마세요.\n"
            "추가납입, 중도인출, 복수연금선택제도, 행복설계자금, 조기연금전환옵션은 주요 보장이 아니라 상품 기능으로 구분하세요.\n"
            "coverage_summary 질문이면 답변 구조를 1. 주요 보장 2. 상품 기능 3. 가입·유의사항 4. 근거 순서로 정리하세요.\n"
            f"검색 프로필: {search_profile.name}\n"
            f"fallback_required: {fallback_required}\n"
            f"상품군 가이드: {product_guidance}\n\n"
            f"질문:\n{question}\n\n"
            f"근거:\n{'\n\n'.join(context_blocks)}\n\n"
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
