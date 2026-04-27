"""Vertex AI service placeholders."""


class DummyVertexAIService:
    """Synthetic LLM and embedding facade."""

    def generate(self, prompt: str) -> str:
        """Return dummy generated text."""
        return f"Dummy generation for: {prompt}"
