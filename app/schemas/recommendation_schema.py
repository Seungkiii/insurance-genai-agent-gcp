"""Recommendation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    """Recommendation input payload."""

    age_group: str | None = None
    gender: str | None = None
    product_name: str | None = None


class RecommendationResult(BaseModel):
    """Recommendation output payload."""

    age_group: str | None = None
    gender: str | None = None
    product_name: str | None = None
    recommended_riders: list[str] = Field(default_factory=list)
    recommended_payment_period: str | None = None
    recommended_insurance_period: str | None = None
    recommended_payment_cycle: str | None = None
    recommended_coverage_amount: int | None = None
    confidence_score: float
    basis_count: int
    fallback_reason: str | None = None
