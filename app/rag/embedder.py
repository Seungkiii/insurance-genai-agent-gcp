"""Embedding service interface placeholders."""

from typing import Protocol


class Embedder(Protocol):
    """Interface for embedding provider implementations."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for input texts."""


class DummyEmbedder:
    """Synthetic embedder for local scaffolding."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic dummy vectors."""
        return [[0.0, 0.1, 0.2] for _ in texts]
