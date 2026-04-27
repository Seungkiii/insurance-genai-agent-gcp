"""RAG evaluator placeholder."""


def evaluate_retrieval_hit_rate(total: int, hits: int) -> float:
    """Compute retrieval hit rate safely."""
    if total <= 0:
        return 0.0
    return hits / total
