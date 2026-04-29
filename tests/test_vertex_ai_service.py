"""Tests for Vertex AI service initialization behavior."""

from __future__ import annotations

from app.services.vertex_ai_service import _init_vertex_ai


class FakeVertexAI:
    """Minimal stub for capturing init arguments."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def init(self, **kwargs: str) -> None:
        self.calls.append(kwargs)


def test_init_vertex_ai_uses_global_base_endpoint_for_global_location() -> None:
    """Global location should use the location-invariant API host."""
    fake_vertexai = FakeVertexAI()

    _init_vertex_ai(fake_vertexai, project_id="demo-project", location="global")

    assert fake_vertexai.calls == [
        {
            "project": "demo-project",
            "location": "global",
            "api_endpoint": "aiplatform.googleapis.com",
        }
    ]


def test_init_vertex_ai_keeps_regional_defaults_for_non_global_location() -> None:
    """Regional locations should continue using SDK defaults."""
    fake_vertexai = FakeVertexAI()

    _init_vertex_ai(fake_vertexai, project_id="demo-project", location="asia-northeast3")

    assert fake_vertexai.calls == [
        {
            "project": "demo-project",
            "location": "asia-northeast3",
        }
    ]
