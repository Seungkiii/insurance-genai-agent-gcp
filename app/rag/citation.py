"""Citation helper placeholder."""

from app.schemas.chat_schema import Citation


def format_citations(raw_items: list[dict[str, str]]) -> list[Citation]:
    """Convert raw citation dictionaries into schema objects."""
    return [Citation(**item) for item in raw_items]
