"""Chat router backed by the policy RAG MVP pipeline."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

from app.rag.chunker import RAGChunk, chunk_document
from app.rag.citation import build_citations
from app.rag.parser import MarkdownPolicyParser
from app.rag.retriever import KeywordChunkRetriever, RetrievalResult
from app.schemas.chat_schema import ChatRequest, ChatResponse

router = APIRouter()

POLICY_PATH = Path("data/sample_policies/sample_policy.md")


@lru_cache(maxsize=1)
def get_policy_chunks() -> tuple[str, list[RAGChunk]]:
    """Load and cache synthetic policy chunks for the MVP."""
    parser = MarkdownPolicyParser()
    parsed_document = parser.parse(str(POLICY_PATH))
    return parsed_document.document_name, chunk_document(parsed_document)


def detect_intent(question: str) -> str:
    """Infer a lightweight intent label from the incoming question."""
    lowered = question.lower()
    if "서류" in question or "청구" in question:
        return "claim_document"
    if "변경" in question or "조정" in question:
        return "design_modification"
    if "추천" in question or "설계" in question:
        return "design_recommendation"
    if "약관" in question or "보장" in question or "지급" in question:
        return "policy_qa"
    if "claim" in lowered:
        return "claim_document"
    return "policy_qa"


def build_answer(question: str, results: list[RetrievalResult]) -> str:
    """Create a grounded template response from retrieved chunks."""
    if not results:
        return (
            "질문과 직접적으로 일치하는 조항을 찾지 못했습니다. "
            "질문 표현을 조금 더 구체화하거나 보장 항목, 지급 기준, 청구 서류 중 하나를 포함해 다시 질문해 주세요."
        )

    primary = results[0].chunk
    supporting_clauses = [result.chunk.content for result in results if result.chunk.content != primary.content][:2]
    answer_lines = [
        f"질문과 가장 관련된 조항은 '{primary.section}' 섹션입니다.",
        f"핵심 내용: {primary.content}",
    ]

    if supporting_clauses:
        answer_lines.append(f"추가 참고 내용: {' / '.join(supporting_clauses)}")

    answer_lines.append(f"응답은 synthetic sample policy 기준으로 생성되었습니다. 질문: {question}")
    return " ".join(answer_lines)


def compute_confidence_score(results: list[RetrievalResult]) -> float:
    """Convert retrieval scores into a bounded confidence score."""
    if not results:
        return 0.0

    top_score = results[0].score
    confidence = min(0.99, round(top_score / 5.0, 2))
    return confidence


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Handle a chat request by retrieving relevant policy clauses."""
    _, chunks = get_policy_chunks()
    retriever = KeywordChunkRetriever()
    results = retriever.retrieve(request.question, chunks, top_k=3)

    return ChatResponse(
        session_id=request.session_id or "session-sample-001",
        intent=detect_intent(request.question),
        answer=build_answer(request.question, results),
        citations=build_citations(results),
        confidence_score=compute_confidence_score(results),
        follow_up_questions=[
            "보장하는 손해, 보장하지 않는 손해, 보험금 지급 기준 중 어떤 항목을 더 확인할까요?"
        ],
        disclaimer="Synthetic sample response generated without real insurer data or live model calls.",
    )
