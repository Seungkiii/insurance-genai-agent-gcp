"""Tests for normalized insurance section taxonomy."""

from app.rag.metadata import normalize_section


def test_normalize_section_maps_major_coverage() -> None:
    assert normalize_section("보험금지급사유 및 지급제한사항", "보험금 지급사유를 설명합니다.") == "coverage"


def test_normalize_section_maps_exclusions() -> None:
    assert normalize_section("보장하지 않는 사유", "면책 및 지급 제한을 안내합니다.") == "exclusions"


def test_normalize_section_avoids_false_coverage_on_future_return_copy() -> None:
    assert normalize_section("보장", "상기 예시된 금액 및 환급률 등이 미래의 수익을 보장하는 것은 아닙니다.") == "refund"
