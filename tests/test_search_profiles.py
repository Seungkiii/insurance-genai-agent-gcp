"""Tests for search profile classification."""

from app.rag.search_profiles import SEARCH_PROFILES, classify_search_profile


def test_search_profile_classifies_pension_payment() -> None:
    assert classify_search_profile("연금개시 후에는 어떤 방식으로 연금을 지급해?").name == "pension_payment"


def test_search_profile_classifies_cancer_coverage() -> None:
    assert classify_search_profile("암 진단비는 어떤 암을 보장해?").name == "cancer_coverage"


def test_search_profile_classifies_dental_coverage() -> None:
    assert classify_search_profile("임플란트 보장은 어떻게 돼?").name == "dental_coverage"


def test_search_profile_classifies_coverage_summary() -> None:
    assert classify_search_profile("이 상품의 주요 보장 내용은 뭐야?").name == "coverage_summary"


def test_search_profile_definition_contains_section_preferences() -> None:
    profile = SEARCH_PROFILES["premium_cost"]
    assert "premium" in profile.positive_sections
    assert "coverage" in profile.negative_sections
