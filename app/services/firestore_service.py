"""Firestore service placeholder."""


class DummyFirestoreService:
    """Synthetic in-memory-like interface for session storage."""

    def save_session(self, session_id: str, payload: dict[str, object]) -> bool:
        """Pretend to save session payload."""
        del session_id, payload
        return True
