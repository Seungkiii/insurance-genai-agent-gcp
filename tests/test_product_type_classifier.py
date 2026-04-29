"""Tests for insurance product type classification."""

from app.rag.metadata import classify_product_type


def test_classify_product_type_detects_annuity() -> None:
    assert classify_product_type("생존연금과 연금지급형태, 연금개시 후 지급 구조를 안내합니다.", "연금보험 상품요약서.pdf") == "annuity"


def test_classify_product_type_detects_cancer() -> None:
    assert classify_product_type("고액암, 일반암, 소액암 및 암진단비 보장을 설명합니다.", "암보험.pdf") == "cancer"


def test_classify_product_type_detects_dental() -> None:
    assert classify_product_type("임플란트, 크라운, 보철치료와 보존치료 내용을 포함합니다.", "치아보험.pdf") == "dental"
