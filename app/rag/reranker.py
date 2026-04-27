"""Reranker placeholder."""


def rerank(chunks: list[str], query: str) -> list[str]:
    """Return chunks unchanged for placeholder behavior."""
    del query
    return chunks
