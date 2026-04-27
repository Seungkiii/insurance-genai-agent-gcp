"""Recommendation schemas."""

from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    """Recommendation input payload."""

    age_group: str | None = None
    gender: str | None = None
    product_name: str | None = None


class RecommendationResponse(BaseModel):
    """Recommendation output payload."""

    riders: list[str]
    reason: str
