"""Product recommendation tool backed by the design-history recommendation service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.recommendation_schema import RecommendationRequest
from app.services.recommendation_service import DesignHistoryRecommendationService


@dataclass
class ProductRecommendTool:
    """Return design recommendations from synthetic design history."""

    name: str = "product_recommend_tool"
    description: str = (
        "Recommend riders and plan conditions from synthetic design history using age_group, gender, and product_name."
    )
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "age_group": {"type": "string"},
                "gender": {"type": "string", "enum": ["F", "M"]},
                "product_name": {"type": "string"},
            },
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool_name": {"type": "string"},
                "recommendation": {"type": "object"},
            },
        }
    )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the synthetic product recommendation flow."""
        request = RecommendationRequest(
            age_group=_optional_string(payload.get("age_group")),
            gender=_optional_string(payload.get("gender")),
            product_name=_optional_string(payload.get("product_name")),
        )
        service = DesignHistoryRecommendationService()
        result = service.recommend(request)

        return {
            "ok": True,
            "tool_name": self.name,
            "recommendation": result.model_dump(),
        }


def _optional_string(value: Any) -> str | None:
    """Normalize optional string inputs."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
