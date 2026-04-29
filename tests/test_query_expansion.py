"""Tests for bounded query expansion."""

from app.rag.search_profiles import SEARCH_PROFILES, build_expanded_query


def test_query_expansion_preserves_original_question() -> None:
    query = "이 상품의 주요 보장 내용은 뭐야?"
    expanded = build_expanded_query(query, SEARCH_PROFILES["coverage_summary"])

    assert expanded.startswith(query)


def test_query_expansion_adds_profile_terms_with_limit() -> None:
    expanded = build_expanded_query(
        "연금개시 후에는 어떤 방식으로 연금을 지급해?",
        SEARCH_PROFILES["pension_payment"],
        product_types=["annuity"],
        max_terms=6,
    )

    assert "연금지급형태" in expanded
    assert "생존연금" in expanded
