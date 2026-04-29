"""Tests for insurance document type classification."""

from app.rag.metadata import classify_document_type


def test_classify_document_type_product_summary() -> None:
    assert classify_document_type("", "동양생명 상품요약서.pdf") == "product_summary"


def test_classify_document_type_business_method() -> None:
    assert classify_document_type("사업방법서 기준으로 운영 방식을 설명합니다.", "sample.pdf") == "business_method"


def test_classify_document_type_policy_terms() -> None:
    assert classify_document_type("보험약관 및 면책 조항", "약관.pdf") == "policy_terms"
