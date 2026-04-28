"""Synthetic design-history-based recommendation service."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Protocol

from app.schemas.recommendation_schema import RecommendationRequest, RecommendationResult

DEFAULT_HISTORY_PATH = Path("data/sample_design_history/sample_design_history.csv")


class RecommendationEngine(Protocol):
    """Interface for recommendation implementations."""

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """Return a recommendation based on design history."""


class DesignHistoryRecommendationService:
    """Recommend synthetic plan settings from historical synthetic design data."""

    def __init__(self, csv_path: str | Path = DEFAULT_HISTORY_PATH) -> None:
        self.csv_path = Path(csv_path)

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """Filter similar rows and build a recommendation summary."""
        rows = self._load_rows()
        filtered_rows = self._filter_rows(rows, request)
        basis_count = len(filtered_rows)

        if basis_count == 0:
            return RecommendationResult(
                age_group=request.age_group,
                gender=request.gender,
                product_name=request.product_name,
                confidence_score=0.0,
                basis_count=0,
                fallback_reason=(
                    "No matching synthetic design history was found for the provided "
                    "age_group, gender, and product_name combination."
                ),
            )

        rider_counter = Counter(row["rider_name"] for row in filtered_rows if row["rider_name"])

        return RecommendationResult(
            age_group=request.age_group,
            gender=request.gender,
            product_name=request.product_name,
            recommended_riders=[name for name, _ in rider_counter.most_common(3)],
            recommended_payment_period=_most_common_value(filtered_rows, "payment_period"),
            recommended_insurance_period=_most_common_value(filtered_rows, "insurance_period"),
            recommended_payment_cycle=_most_common_value(filtered_rows, "payment_cycle"),
            recommended_coverage_amount=_recommended_coverage_amount(filtered_rows),
            confidence_score=_confidence_score(
                basis_count=basis_count,
                age_group=request.age_group,
                gender=request.gender,
                product_name=request.product_name,
            ),
            basis_count=basis_count,
            fallback_reason=_fallback_reason(basis_count),
        )

    def _load_rows(self) -> list[dict[str, str]]:
        """Load synthetic design history rows from CSV."""
        with self.csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            return list(csv.DictReader(csv_file))

    @staticmethod
    def _filter_rows(
        rows: list[dict[str, str]],
        request: RecommendationRequest,
    ) -> list[dict[str, str]]:
        """Filter rows by the provided similarity keys."""
        filtered = rows
        if request.age_group:
            filtered = [row for row in filtered if row["age_group"] == request.age_group]
        if request.gender:
            filtered = [row for row in filtered if row["gender"] == request.gender]
        if request.product_name:
            filtered = [row for row in filtered if row["product_name"] == request.product_name]
        return filtered


def _most_common_value(rows: list[dict[str, str]], key: str) -> str | None:
    """Return the most frequent string value for a field."""
    values = [row[key] for row in rows if row.get(key)]
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _recommended_coverage_amount(rows: list[dict[str, str]]) -> int | None:
    """Use the mode when repeated, otherwise fall back to median."""
    amounts = [int(row["coverage_amount"]) for row in rows if row.get("coverage_amount")]
    if not amounts:
        return None

    counts = Counter(amounts).most_common()
    if len(counts) == 1 or (len(counts) > 1 and counts[0][1] > counts[1][1]):
        return counts[0][0]
    return int(median(amounts))


def _confidence_score(
    basis_count: int,
    age_group: str | None,
    gender: str | None,
    product_name: str | None,
) -> float:
    """Estimate confidence from match count and filter specificity."""
    specificity = sum(value is not None for value in (age_group, gender, product_name))
    base_score = min(0.9, 0.35 + (basis_count * 0.15))
    specificity_bonus = specificity * 0.03
    return round(min(0.99, base_score + specificity_bonus), 2)


def _fallback_reason(basis_count: int) -> str | None:
    """Return a fallback note when the evidence set is too small."""
    if basis_count >= 2:
        return None
    return "Limited synthetic history matched the filters, so the recommendation is based on a very small sample."
