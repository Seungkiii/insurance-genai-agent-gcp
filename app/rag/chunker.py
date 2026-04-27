"""RAG chunker placeholders."""


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Chunk text into fixed-size slices for placeholder behavior."""
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
