"""Grounded answer generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.rag.retriever import RetrievalResult, is_major_coverage_question
from app.services.vertex_ai_service import VertexAIGenerationService

GUARDRAIL_TEXT = "본 답변은 약관 해석을 돕기 위한 참고 정보이며, 보험금 지급 확정 또는 보상 승인 판단을 의미하지 않습니다."


class AnswerGenerator(Protocol):
    """Interface for answer generation implementations."""

    def generate(self, question: str, results: list[RetrievalResult]) -> str:
        """Generate a grounded answer from retrieved evidence."""


@dataclass
class GeminiAnswerGenerator:
    """Answer generator backed by Gemini through a service facade."""

    generation_service: VertexAIGenerationService

    def generate(self, question: str, results: list[RetrievalResult]) -> str:
        """Generate a grounded answer using retrieved context."""
        question_is_major_coverage = is_major_coverage_question(question)
        context_blocks = [
            f"[문서: {result.chunk.document_name} | 섹션: {result.chunk.section} | 페이지: {result.chunk.page}]\n{result.chunk.content}"
            for result in results
        ]
        prompt = (
            "당신은 보험상품 설명서 RAG Assistant입니다.\n"
            "아래 근거만 사용해 질문에 답변하세요.\n"
            "보험금 지급 확정 표현은 피하고, 확정 판단이 필요한 경우 약관과 심사 절차 확인이 필요하다고 안내하세요.\n\n"
            f"질문 유형: {'주요 보장 내용 확인' if question_is_major_coverage else '일반 보험 질의'}\n"
            "주요 보장 질문이면 보험금 지급사유, 보험급부, 지급금액, 연금지급형태, 상품 특이사항을 우선적으로 정리하세요.\n"
            "보험료, 수수료, 해약환급금, 환급률 근거만 있을 때는 이를 주요 보장으로 오인하지 말고, 보장 관련 근거가 부족한지 분명히 설명하세요.\n\n"
            f"질문:\n{question}\n\n"
            f"근거:\n{'\n\n'.join(context_blocks)}\n\n"
            "답변:"
        )
        answer = self.generation_service.generate_text(prompt)
        return f"{answer}\n\n{GUARDRAIL_TEXT}"


def build_low_confidence_answer() -> str:
    """Return a fallback answer when retrieval confidence is weak."""
    return (
        "현재 검색된 근거만으로는 질문에 대해 확정적으로 안내하기 어렵습니다. "
        "보험상품명, 보장 항목, 사고 상황, 청구 유형 등 추가 정보를 알려주시면 더 정확히 찾아드릴 수 있습니다.\n\n"
        f"{GUARDRAIL_TEXT}"
    )
