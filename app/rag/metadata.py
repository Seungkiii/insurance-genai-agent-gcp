"""Metadata helpers for multi-product insurance document RAG."""

from __future__ import annotations

import re
from collections import Counter

ProductType = str
DocumentType = str
NormalizedSection = str

PRODUCT_TYPE_KEYWORDS: dict[ProductType, tuple[str, ...]] = {
    "annuity": ("연금", "생존연금", "연금지급형태", "연금개시", "공시이율", "계약자적립액"),
    "whole_life": ("종신", "사망보험금", "체증", "해약환급금 일부지급형", "유니버셜"),
    "cancer": ("암", "고액암", "일반암", "소액암", "암진단비", "암수술비", "보장체증형"),
    "health": ("건강보험", "2대 질환", "3대 질환", "치매", "입원", "수술", "진단비"),
    "accident": ("상해", "재해", "재해사망", "재해장해", "장해지급률", "직업급수"),
    "dental": ("치아", "치과", "보철치료", "보존치료", "크라운", "임플란트", "충치", "잇몸질환"),
    "simplified": ("간편심사", "유병자", "3.n.5", "3n5", "고지항목", "간편고지"),
    "custom_coverage": ("내가만드는", "선택보장", "맞춤형", "보장조립", "선택특약"),
}

DOCUMENT_TYPE_KEYWORDS: dict[DocumentType, tuple[str, ...]] = {
    "product_summary": ("상품요약서",),
    "business_method": ("사업방법서",),
    "policy_terms": ("보험약관", "약관"),
}

SECTION_PATTERNS: tuple[tuple[tuple[str, ...], NormalizedSection], ...] = (
    (("상품 특이사항", "상품 개요", "주요 특징", "상품특징"), "product_overview"),
    (("보험가입 자격요건", "가입나이", "가입연령", "보험기간", "납입기간", "가입조건"), "eligibility"),
    (("보험금 지급사유", "보험급부", "지급금액", "보장내용", "보장", "급부"), "coverage"),
    (("보험금 지급제한", "지급제한사항", "지급제한", "지급하지 않는 사유", "보장하지 않는 사유", "면책", "계약 전 알릴 의무"), "exclusions"),
    (("연금지급형태", "생존연금", "행복설계자금", "연금개시 후 보험기간", "연금개시후 보험기간", "연금개시후", "연금개시전", "복수연금선택제도", "조기연금전환옵션", "추가납입", "중도인출"), "annuity_payment"),
    (("사망보험금", "종신보장", "체증형 사망보험금"), "death_benefit"),
    (("암진단비", "고액암", "일반암", "소액암", "암수술비", "암입원"), "cancer_benefit"),
    (("2대 질환", "3대 질환", "치매", "입원", "수술", "진단비", "건강보험"), "health_benefit"),
    (("재해", "상해", "장해", "재해사망", "재해장해", "장해지급률"), "accident_benefit"),
    (("보철치료", "보존치료", "크라운", "임플란트", "치아치료", "충치", "잇몸질환"), "dental_benefit"),
    (("보험료", "적용이율", "위험률", "적립이율"), "premium"),
    (("해약환급금", "환급률", "계약자적립액", "해약공제"), "refund"),
    (("모집수수료", "계약체결비용", "계약관리비용", "공제금액", "수수료"), "fee"),
    (("보험금 청구", "필요서류", "제출서류", "청구 서류"), "claim"),
    (("특약", "선택특약", "제도성 특약"), "rider"),
)


def classify_product_type(text: str, file_name: str) -> ProductType:
    """Classify the insurance product type from filename and document text."""
    corpus = _normalize_space(f"{file_name} {text}").lower()
    scores: dict[ProductType, int] = {}
    for product_type, keywords in PRODUCT_TYPE_KEYWORDS.items():
        score = sum(corpus.count(keyword.lower()) for keyword in keywords)
        if score:
            scores[product_type] = score
    if not scores:
        return "unknown"
    return max(scores.items(), key=lambda item: item[1])[0]


def classify_document_type(text: str, file_name: str) -> DocumentType:
    """Classify the document type from filename and body text."""
    corpus = _normalize_space(f"{file_name} {text}")
    for document_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
        if any(keyword in corpus for keyword in keywords):
            return document_type
    return "unknown"


def normalize_section(section_title: str, content: str) -> NormalizedSection:
    """Normalize raw section names into a common insurance retrieval taxonomy."""
    title = _normalize_space(section_title)
    body = _normalize_space(content)
    compact = re.sub(r"\s+", "", f"{title} {body}")
    title_compact = re.sub(r"\s+", "", title)
    body_compact = re.sub(r"\s+", "", body)
    coverage_content_terms = (
        "지급사유",
        "지급금액",
        "급부명",
        "장해지급률",
        "보험금1,000만원",
        "보험금1000만원",
        "고도재해장해보험금",
    )
    exclusion_content_terms = (
        "계약전알릴의무",
        "지급제한",
        "보장하지않는",
        "면책",
        "고의",
        "해지할수있으며",
        "보험금을받지못하는경우",
    )

    if any(term in compact for term in ("상품의특이사항", "상품개요", "주요특징")):
        return "product_overview"
    if any(term in compact for term in ("보험가입자격요건", "가입나이", "가입연령", "보험기간", "납입기간", "가입조건")):
        return "eligibility"
    if any(term in compact for term in ("연금지급형태", "생존연금", "행복설계자금", "연금개시후보험기간", "연금개시후", "연금개시전", "복수연금선택제도", "조기연금전환옵션", "추가납입", "중도인출")):
        return "annuity_payment"
    if any(term in body_compact for term in coverage_content_terms):
        return "coverage"
    if any(term in body_compact for term in exclusion_content_terms):
        return "exclusions"
    if any(term in title_compact for term in ("보험금지급사유", "보험급부", "지급금액")):
        return "coverage"
    if any(term in compact for term in ("보험금지급제한", "지급제한사항", "지급하지않는사유", "보장하지않는사유", "면책", "계약전알릴의무", "지급제한")):
        return "exclusions"
    if any(term in compact for term in ("미래의수익을보장하는것은아닙니다", "미래수익을보장하지않", "환급률")):
        return "refund"
    if any(term in compact for term in ("계약체결비용", "계약관리비용", "모집수수료", "공제금액", "수수료")):
        return "fee"
    if any(term in compact for term in ("해약환급금", "환급률", "계약자적립액", "해약공제")):
        return "refund"
    if any(term in compact for term in ("보험료", "적용이율", "위험률", "적립이율")):
        return "premium"
    if any(term in compact for term in ("사망보험금", "종신보장", "체증형사망보험금")):
        return "death_benefit"
    if any(term in compact for term in ("암진단비", "고액암", "일반암", "소액암", "암수술비", "암입원")):
        return "cancer_benefit"
    if any(term in compact for term in ("2대질환", "3대질환", "치매", "입원", "수술", "진단비", "건강보험")):
        return "health_benefit"
    if any(term in compact for term in ("재해", "상해", "장해", "재해사망", "재해장해", "장해지급률")):
        return "accident_benefit"
    if any(term in compact for term in ("보철치료", "보존치료", "크라운", "임플란트", "치아치료", "충치", "잇몸질환")):
        return "dental_benefit"
    if any(term in compact for term in ("보험금청구", "필요서류", "제출서류", "청구서류")):
        return "claim"
    if any(term in compact for term in ("특약", "선택특약", "제도성특약")):
        return "rider"
    if any(term in compact for term in ("보험금지급사유", "보험급부", "지급금액", "보장내용", "보장하는손해")):
        return "coverage"
    return _fallback_section_from_terms(compact)


def section_label_from_normalized(normalized_section: str) -> str:
    """Return a human-readable fallback title for a normalized section."""
    labels = {
        "product_overview": "상품 특이사항",
        "eligibility": "보험가입 자격요건",
        "coverage": "보험금 지급사유",
        "exclusions": "지급제한사항",
        "annuity_payment": "연금지급형태",
        "death_benefit": "사망보험금",
        "cancer_benefit": "암 보장",
        "health_benefit": "건강 보장",
        "accident_benefit": "상해 보장",
        "dental_benefit": "치아 보장",
        "premium": "보험료",
        "refund": "해약환급금",
        "fee": "공제금액",
        "claim": "청구 서류",
        "rider": "특약",
        "miscellaneous": "기타",
    }
    return labels.get(normalized_section, "기타")


def summarize_text_features(text: str) -> dict[str, int]:
    """Return simple keyword frequency features for debugging or future reranking."""
    normalized = _normalize_space(text)
    tokens = re.findall(r"[0-9A-Za-z가-힣.]+", normalized.lower())
    return dict(Counter(tokens))


def _fallback_section_from_terms(compact: str) -> NormalizedSection:
    for keywords, normalized_section in SECTION_PATTERNS:
        if any(keyword.replace(" ", "") in compact for keyword in keywords):
            return normalized_section
    return "miscellaneous"


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
