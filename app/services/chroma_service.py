"""Vector database placeholder service."""


class DummyChromaService:
    """Synthetic vector search interface."""

    def search(self, query_vector: list[float], top_k: int = 3) -> list[dict[str, object]]:
        """Return empty result set for placeholder behavior."""
        del query_vector, top_k
        return []
