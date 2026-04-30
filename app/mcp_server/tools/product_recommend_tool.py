"""Product recommendation tool grounded in multi-product insurance RAG evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.firestore_service import FirestoreService

from .base import BaseTool
from .policy_search_tool import PolicySearchTool

RECOMMENDATION_GUIDANCE: dict[str, list[str]] = {
    "annuity": ["연금개시 전 보장", "연금개시 후 지급방식", "중도인출/추가납입 유의사항"],
    "whole_life": ["사망보험금", "체증 여부", "해약환급금 일부지급형", "전환 기능"],
    "cancer": ["암 종류별 진단비", "면책기간", "보장체증 여부"],
    "health": ["주요 질환", "진단비/입원/수술", "환급 구조"],
    "dental": ["보철/보존/크라운/임플란트", "면책/감액기간"],
}

RISK_NEED_PRODUCT_PRIORITY: dict[str, list[str]] = {
    "암": ["cancer"],
    "치아": ["dental"],
    "치료비": ["health", "dental"],
    "사망보장": ["whole_life"],
    "노후": ["annuity"],
    "연금": ["annuity"],
    "상해": ["accident"],
    "재해": ["accident"],
    "건강": ["health"],
    "질병": ["health"],
}


@dataclass
class ProductRecommendTool(BaseTool):
    """Create evidence-based recommendation scaffolds from policy search results."""

    policy_search_tool: PolicySearchTool
    firestore_service: FirestoreService | None = None
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
                "risk_needs": {"type": "array", "items": {"type": "string"}},
                "mode": {"type": "string"},
            },
            "required": ["query", "session_id"],
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "recommended_design": {"type": "object"},
                "recommended_products": {"type": "array"},
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
        mode = str(payload.get("mode") or ("single_product" if payload.get("document_ids") else "multi_product"))
        if mode == "multi_product":
            return self._execute_multi_product_mode(payload, trace_summary, query=query, session_id=session_id)
        return self._execute_single_product_mode(payload, trace_summary, query=query, session_id=session_id)

    def _execute_single_product_mode(
        self,
        payload: dict[str, Any],
        trace_summary: list[str],
        *,
        query: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Build product-type-aware advice for a single product scope."""

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
        citations = list(search_output.get("citations", []))
        evidence_summary = _build_evidence_summary(citations)
        focus_areas = _build_focus_areas(product_type)
        explanation_points = _build_explanation_points(search_output)
        caution_notes = _build_caution_notes(search_output)
        recommended_design = {
            "session_id": session_id,
            "customer_profile": payload.get("customer_profile", {}),
            "product_type": product_type,
            "focus_areas": focus_areas,
            "main_focus": _build_main_focus(product_type),
            "recommended_explanation_points": explanation_points,
            "caution_notes": caution_notes,
            "evidence_summary": evidence_summary,
            "note": "근거 문서에 나타난 보장 구조를 요약한 것으로, 임의 가입금액이나 확정 추천은 포함하지 않습니다.",
        }
        current_design = _build_current_design(
            session_id=session_id,
            customer_profile=payload.get("customer_profile", {}),
            product_type=product_type,
            selected_document_ids=[str(item) for item in payload.get("document_ids", []) if str(item).strip()],
            selected_product_names=_collect_selected_product_names(citations, search_output.get("chunks", [])),
            focus_areas=focus_areas,
            caution_notes=caution_notes,
            evidence_summary=evidence_summary,
        )

        return {
            "query": query,
            "search_profile": search_output.get("search_profile"),
            "recommended_design": recommended_design,
            "recommended_products": [],
            "current_design": current_design,
            "evidence_summary": evidence_summary,
            "explanation_points": explanation_points,
            "citations": citations,
            "caution_notes": caution_notes,
            "fallback_required": search_output.get("fallback_required", False),
        }

    def _execute_multi_product_mode(
        self,
        payload: dict[str, Any],
        trace_summary: list[str],
        *,
        query: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Build multi-product recommendations from indexed document metadata and RAG evidence."""
        if self.firestore_service is None:
            raise RuntimeError("ProductRecommendTool requires Firestore access for multi-product recommendations.")

        customer_profile = payload.get("customer_profile", {})
        risk_needs = [str(item) for item in payload.get("risk_needs", []) if str(item).strip()]
        requested_document_ids = [str(item) for item in payload.get("document_ids", []) if str(item).strip()]
        candidate_documents = self._resolve_candidate_documents(requested_document_ids, risk_needs)
        trace_summary.append(f"candidate_document_count={len(candidate_documents)}")
        if not candidate_documents:
            raise ValueError("No indexed documents matched the recommendation scope.")

        recommended_products: list[dict[str, Any]] = []
        all_citations: list[dict[str, Any]] = []
        caution_notes: list[str] = []

        for record in candidate_documents[:3]:
            policy_result = self.policy_search_tool.run(
                {
                    "query": query,
                    "document_ids": [record["document_id"]],
                    "product_type": record.get("product_type"),
                    "top_k": payload.get("top_k", 5),
                }
            )
            if policy_result["status"] != "success":
                continue
            search_output = policy_result["output"] or {}
            citations = list(search_output.get("citations", []))
            recommended_products.append(
                {
                    "document_id": record["document_id"],
                    "document_name": record.get("file_name"),
                    "product_name": record.get("product_name") or record.get("document_name") or record.get("file_name"),
                    "product_type": record.get("product_type"),
                    "recommendation_reason": _build_product_recommendation_reason(
                        record.get("product_type"),
                        risk_needs,
                        search_output,
                        customer_profile,
                    ),
                    "caution_notes": _build_caution_notes(search_output),
                    "citations": citations[:3],
                }
            )
            all_citations.extend(citations[:3])
            caution_notes.extend(_build_caution_notes(search_output))

        ranking_reason = _build_ranking_reason(risk_needs, recommended_products)
        current_design = None
        if recommended_products:
            top_product = recommended_products[0]
            current_design = _build_current_design(
                session_id=session_id,
                customer_profile=customer_profile,
                product_type=str(top_product.get("product_type") or "unknown"),
                selected_document_ids=[str(top_product.get("document_id") or "")],
                selected_product_names=[str(top_product.get("product_name") or top_product.get("document_name") or "")],
                focus_areas=_build_focus_areas(str(top_product.get("product_type") or "unknown")),
                caution_notes=list(dict.fromkeys(caution_notes)),
                evidence_summary=_build_evidence_summary(all_citations),
            )
        return {
            "query": query,
            "search_profile": "product_comparison" if len(recommended_products) > 1 else "coverage_summary",
            "recommended_design": None,
            "recommended_products": recommended_products,
            "current_design": current_design or self._load_current_design(session_id),
            "ranking_reason": ranking_reason,
            "citations": all_citations,
            "caution_notes": list(dict.fromkeys(caution_notes)),
            "fallback_required": not recommended_products,
        }

    def _resolve_candidate_documents(
        self,
        requested_document_ids: list[str],
        risk_needs: list[str],
    ) -> list[dict[str, Any]]:
        if self.firestore_service is None:
            return []
        if requested_document_ids:
            records: list[dict[str, Any]] = []
            for document_id in requested_document_ids:
                record = self.firestore_service.get_document(document_id)
                if record is not None and record.get("status") == "indexed":
                    records.append(record)
            return records

        product_type_priority: list[str] = []
        for risk_need in risk_needs:
            for product_type in RISK_NEED_PRODUCT_PRIORITY.get(risk_need, []):
                if product_type not in product_type_priority:
                    product_type_priority.append(product_type)

        records = [
            record for record in self.firestore_service.list_documents() if record.get("status") == "indexed"
        ]
        if not product_type_priority:
            return records[:3]
        prioritized = [record for record in records if record.get("product_type") in product_type_priority]
        fallback = [record for record in records if record.get("product_type") not in product_type_priority]
        prioritized.sort(key=lambda item: product_type_priority.index(str(item.get("product_type"))))
        return prioritized + fallback

    def _load_current_design(self, session_id: str) -> dict[str, Any] | None:
        if self.firestore_service is None:
            return None
        current_design_record = self.firestore_service.get_current_design(session_id)
        if current_design_record is None:
            return None
        return current_design_record.get("current_design")


def _build_evidence_summary(citations: list[dict[str, Any]]) -> list[str]:
    summaries: list[str] = []
    for citation in citations[:4]:
        normalized_section = str(citation.get("normalized_section") or "miscellaneous")
        summary_prefix = "유의사항 근거" if normalized_section == "exclusions" else "설명 근거"
        summaries.append(
            f"{summary_prefix} | {normalized_section} | {citation['section']} | {citation['document_name']} p.{citation['page']}"
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


def _build_explanation_points(search_output: dict[str, Any]) -> list[str]:
    chunks = search_output.get("chunks", [])
    return [
        f"{chunk['section']} 중심으로 설명"
        for chunk in chunks[:3]
        if chunk.get("normalized_section") != "exclusions"
    ]


def _build_focus_areas(product_type: str) -> list[str]:
    if product_type == "annuity":
        return [
            "연금개시 전 고도재해장해보험금",
            "연금개시 후 생존연금",
            "사망보장 없는 연금보험",
            "공시이율 변동 가능성",
            "추가납입/중도인출",
            "복수연금선택제도/행복설계자금/조기연금전환옵션",
        ]
    return RECOMMENDATION_GUIDANCE.get(product_type, ["핵심 보장", "지급 조건", "유의사항"])


def _build_main_focus(product_type: str) -> str:
    if product_type == "annuity":
        return "연금개시 전후 보장 구조, 생존연금 중심 설명, 그리고 공시이율 변동 및 부가 기능 유의사항"
    return "상품 핵심 보장과 설명 포인트"


def _build_current_design(
    *,
    session_id: str,
    customer_profile: dict[str, Any],
    product_type: str,
    selected_document_ids: list[str],
    selected_product_names: list[str],
    focus_areas: list[str],
    caution_notes: list[str],
    evidence_summary: list[str],
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "customer_profile": customer_profile,
        "product_type": product_type,
        "selected_document_ids": selected_document_ids,
        "selected_product_names": [name for name in selected_product_names if name],
        "focus_areas": focus_areas,
        "caution_notes": caution_notes,
        "evidence_summary": evidence_summary,
        "coverages": focus_areas,
    }


def _collect_selected_product_names(
    citations: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[str]:
    names = [str(citation.get("document_name") or "").strip() for citation in citations if str(citation.get("document_name") or "").strip()]
    if names:
        return list(dict.fromkeys(names))
    return [
        str(chunk.get("document_name") or "").strip()
        for chunk in chunks
        if str(chunk.get("document_name") or "").strip()
    ]


def _build_product_recommendation_reason(
    product_type: Any,
    risk_needs: list[str],
    search_output: dict[str, Any],
    customer_profile: Any,
) -> str:
    normalized_sections = ", ".join(search_output.get("normalized_section", [])[:3])
    return (
        f"상품군 {product_type}가 risk_needs={risk_needs}와 가장 가깝고, "
        f"검색 근거 섹션은 {normalized_sections or 'coverage'} 중심입니다. "
        f"고객 프로필={customer_profile}를 기준으로 설명 포인트를 정리했습니다."
    )


def _build_ranking_reason(risk_needs: list[str], recommended_products: list[dict[str, Any]]) -> str:
    return (
        f"risk_needs={risk_needs} 우선순위와 각 상품의 검색 근거를 기준으로 {len(recommended_products)}개 후보를 정렬했습니다."
    )
