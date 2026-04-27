"""Retriever placeholders."""

from app.schemas.chat_schema import Citation


def retrieve(query: str, top_k: int = 3) -> list[Citation]:
    """Return synthetic retrieval citations."""
    del query, top_k
    return []
