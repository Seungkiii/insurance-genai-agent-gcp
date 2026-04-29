"""Embedding provider interfaces and implementations."""

from __future__ import annotations

from typing import Protocol

from app.services.vertex_ai_service import VertexAIEmbeddingService


class Embedder(Protocol):
    """Interface for embedding provider implementations."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for input texts."""


class DummyEmbedder:
    """Synthetic embedder for local scaffolding and tests."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic dummy vectors."""
        return [[0.0, 0.1, 0.2] for _ in texts]


class VertexAIEmbedder:
    """Embedder backed by a Vertex AI embedding service facade."""

    def __init__(self, embedding_service: VertexAIEmbeddingService) -> None:
        self.embedding_service = embedding_service

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Delegate embedding creation to Vertex AI."""
        return self.embedding_service.embed_texts(texts)
