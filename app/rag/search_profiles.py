"""Intent-based search profiles for insurance document retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchProfile:
    """Query-time retrieval strategy."""

    name: str
    expansion_terms: list[str] = field(default_factory=list)
    positive_sections: list[str] = field(default_factory=list)
    negative_sections: list[str] = field(default_factory=list)
    preferred_document_types: list[str] = field(default_factory=list)
    product_type_hints: list[str] = field(default_factory=list)


SEARCH_PROFILES: dict[str, SearchProfile] = {
    "coverage_summary": SearchProfile(
        name="coverage_summary",
        expansion_terms=["주요 보장", "보장 내용", "보험금 지급사유", "보험급부", "지급금액", "지급제한", "특약"],
        positive_sections=["product_overview", "coverage", "rider", "exclusions"],
        negative_sections=["premium", "refund", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
    ),
    "payment_condition": SearchProfile(
        name="payment_condition",
        expansion_terms=["지급 조건", "보험금 지급사유", "지급금액", "지급 제한", "면책"],
        positive_sections=["coverage", "exclusions", "claim"],
        negative_sections=["premium", "fee"],
        preferred_document_types=["policy_terms", "product_summary"],
    ),
    "pension_payment": SearchProfile(
        name="pension_payment",
        expansion_terms=["연금개시 후", "연금지급형태", "생존연금", "종신연금형", "확정연금형", "상속연금형", "자유연금형", "행복설계자금"],
        positive_sections=["annuity_payment", "product_overview", "eligibility"],
        negative_sections=["premium", "fee", "refund"],
        preferred_document_types=["product_summary", "policy_terms"],
        product_type_hints=["annuity"],
    ),
    "death_benefit": SearchProfile(
        name="death_benefit",
        expansion_terms=["사망보험금", "종신", "체증", "종신보장", "전환 기능"],
        positive_sections=["death_benefit", "coverage", "product_overview"],
        negative_sections=["premium", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
        product_type_hints=["whole_life"],
    ),
    "cancer_coverage": SearchProfile(
        name="cancer_coverage",
        expansion_terms=["암", "암진단비", "고액암", "일반암", "소액암", "암수술비", "암입원", "보장개시일", "면책기간"],
        positive_sections=["cancer_benefit", "coverage", "exclusions", "rider"],
        negative_sections=["premium", "refund", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
        product_type_hints=["cancer"],
    ),
    "health_coverage": SearchProfile(
        name="health_coverage",
        expansion_terms=["질병", "건강보험", "2대 질환", "3대 질환", "치매", "입원", "수술", "진단비"],
        positive_sections=["health_benefit", "coverage", "exclusions", "rider"],
        negative_sections=["premium", "refund", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
        product_type_hints=["health"],
    ),
    "accident_coverage": SearchProfile(
        name="accident_coverage",
        expansion_terms=["상해", "재해", "재해사망", "재해장해", "장해지급률", "직업급수"],
        positive_sections=["accident_benefit", "coverage", "exclusions"],
        negative_sections=["premium", "refund", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
        product_type_hints=["accident"],
    ),
    "dental_coverage": SearchProfile(
        name="dental_coverage",
        expansion_terms=["치아", "임플란트", "크라운", "보철치료", "보존치료", "충치", "잇몸질환", "면책기간", "감액기간"],
        positive_sections=["dental_benefit", "coverage", "exclusions", "rider"],
        negative_sections=["premium", "refund", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
        product_type_hints=["dental"],
    ),
    "premium_cost": SearchProfile(
        name="premium_cost",
        expansion_terms=["보험료", "적용이율", "적립이율", "위험률", "계약체결비용", "계약관리비용", "수수료"],
        positive_sections=["premium", "fee"],
        negative_sections=["coverage", "exclusions"],
        preferred_document_types=["product_summary", "business_method"],
    ),
    "surrender_refund": SearchProfile(
        name="surrender_refund",
        expansion_terms=["해약환급금", "환급률", "계약자적립액", "해약공제", "중도해지"],
        positive_sections=["refund", "fee"],
        negative_sections=["coverage"],
        preferred_document_types=["product_summary", "business_method"],
    ),
    "eligibility": SearchProfile(
        name="eligibility",
        expansion_terms=["가입나이", "가입조건", "보험기간", "납입기간", "고지항목"],
        positive_sections=["eligibility", "product_overview"],
        negative_sections=["premium", "refund"],
        preferred_document_types=["product_summary", "business_method"],
    ),
    "rider_summary": SearchProfile(
        name="rider_summary",
        expansion_terms=["특약", "선택특약", "제도성 특약", "부가보장"],
        positive_sections=["rider", "coverage", "product_overview"],
        negative_sections=["fee"],
        preferred_document_types=["product_summary", "business_method"],
    ),
    "claim_document": SearchProfile(
        name="claim_document",
        expansion_terms=["청구", "서류", "제출서류", "필요서류"],
        positive_sections=["claim", "coverage"],
        negative_sections=["premium", "fee"],
        preferred_document_types=["product_summary", "policy_terms"],
    ),
    "exclusion_check": SearchProfile(
        name="exclusion_check",
        expansion_terms=["지급 제한", "면책", "보장하지 않는", "알릴 의무"],
        positive_sections=["exclusions", "coverage"],
        negative_sections=["premium", "refund"],
        preferred_document_types=["policy_terms", "product_summary"],
    ),
    "product_comparison": SearchProfile(
        name="product_comparison",
        expansion_terms=["비교", "차이", "장단점", "보장 차이", "보험료 차이"],
        positive_sections=["product_overview", "coverage", "premium", "refund"],
        negative_sections=[],
        preferred_document_types=["product_summary"],
    ),
    "general_policy_qa": SearchProfile(
        name="general_policy_qa",
        expansion_terms=["보험", "보장", "조건", "유의사항"],
        positive_sections=["product_overview", "coverage", "claim", "exclusions"],
        negative_sections=["fee"],
        preferred_document_types=["product_summary", "policy_terms"],
    ),
}

PRODUCT_TYPE_CONTEXT_TERMS: dict[str, list[str]] = {
    "annuity": ["연금지급형태", "생존연금", "연금개시후", "연금개시전", "행복설계자금"],
    "whole_life": ["사망보험금", "종신보장", "체증", "전환"],
    "cancer": ["암진단비", "고액암", "소액암", "면책기간", "감액기간"],
    "health": ["입원", "수술", "진단비", "치매", "질환"],
    "accident": ["재해사망", "재해장해", "장해지급률", "직업급수"],
    "dental": ["임플란트", "크라운", "보철치료", "보존치료", "면책기간"],
    "simplified": ["간편심사", "간편고지", "유병자", "고지항목"],
    "custom_coverage": ["선택보장", "맞춤형", "선택특약"],
}


def classify_search_profile(question: str) -> SearchProfile:
    """Classify a question into an insurance retrieval profile."""
    normalized = re.sub(r"\s+", "", question)

    rules: tuple[tuple[tuple[str, ...], str], ...] = (
        (("연금", "연금개시", "생존연금"), "pension_payment"),
        (("사망보험금", "종신"), "death_benefit"),
        (("고액암", "소액암", "암진단비", "암보험", "암"), "cancer_coverage"),
        (("치아", "임플란트", "크라운"), "dental_coverage"),
        (("상해", "재해", "장해"), "accident_coverage"),
        (("질병", "건강", "입원", "수술", "치매", "2대질환", "3대질환"), "health_coverage"),
        (("보험료", "비용", "수수료"), "premium_cost"),
        (("해약환급금", "환급률", "중도해지", "계약자적립액"), "surrender_refund"),
        (("가입나이", "가입조건", "보험기간", "납입기간"), "eligibility"),
        (("청구", "서류", "제출"), "claim_document"),
        (("지급제한", "면책", "보장하지않는"), "exclusion_check"),
        (("지급조건", "보험금", "언제지급"), "payment_condition"),
        (("주요보장", "보장내용", "어떤보장"), "coverage_summary"),
        (("특약", "선택특약"), "rider_summary"),
        (("비교", "차이"), "product_comparison"),
    )

    for keywords, profile_name in rules:
        if any(keyword in normalized for keyword in keywords):
            return SEARCH_PROFILES[profile_name]
    return SEARCH_PROFILES["general_policy_qa"]


def build_expanded_query(
    original_query: str,
    profile: SearchProfile,
    *,
    product_types: list[str] | None = None,
    max_terms: int = 8,
    include_product_context: bool = False,
) -> str:
    """Append a bounded set of profile terms while preserving the original query."""
    selected_terms: list[str] = []
    hinted_types = set(product_types or [])
    for term in profile.expansion_terms:
        if len(selected_terms) >= max_terms:
            break
        if term not in selected_terms:
            selected_terms.append(term)

    if profile.product_type_hints and hinted_types & set(profile.product_type_hints):
        selected_terms = selected_terms[:max_terms]
    else:
        selected_terms = selected_terms[: min(max_terms, 6)]

    if include_product_context:
        for product_type in product_types or []:
            for term in PRODUCT_TYPE_CONTEXT_TERMS.get(product_type, []):
                if len(selected_terms) >= max_terms:
                    break
                if term not in selected_terms:
                    selected_terms.append(term)

    if not selected_terms:
        return original_query
    return f"{original_query} {' '.join(selected_terms)}"
