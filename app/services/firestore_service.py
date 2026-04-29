"""Firestore service abstractions for document metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol


class FirestoreService(Protocol):
    """Interface for document metadata persistence."""

    def create_document(
        self,
        document_id: str,
        file_name: str,
        gcs_uri: str,
        status: str = "uploaded",
    ) -> dict[str, Any]:
        """Create and persist a document metadata record."""

    def list_documents(self) -> list[dict[str, Any]]:
        """Return persisted document metadata records."""

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Return a document metadata record by id."""

    def update_document_status(
        self,
        document_id: str,
        status: str,
        *,
        error_message: str | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any] | None:
        """Update document status and optional metadata."""

    def save_chat_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        citations: list[dict[str, Any]],
        latency_ms: int,
        *,
        tool_trace: list[dict[str, Any]] | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
    ) -> dict[str, Any]:
        """Persist a chat interaction for audit and session review."""

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        """Return the current design snapshot for a session when available."""

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        """Persist the current design snapshot for a session."""


class GCPFirestoreService:
    """Firestore-backed implementation for document metadata storage."""

    def __init__(
        self,
        database: str,
        collection_name: str = "documents",
        client: object | None = None,
    ) -> None:
        self.database = database
        self.collection_name = collection_name
        self.chat_collection_name = "chat_sessions"
        self.design_collection_name = "sessions"
        self._client = client

    def create_document(
        self,
        document_id: str,
        file_name: str,
        gcs_uri: str,
        status: str = "uploaded",
    ) -> dict[str, Any]:
        """Persist document metadata in Firestore."""
        record = {
            "document_id": document_id,
            "file_name": file_name,
            "gcs_uri": gcs_uri,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        client = self._client or self._create_client()
        client.collection(self.collection_name).document(document_id).set(record)
        return record

    def list_documents(self) -> list[dict[str, Any]]:
        """Return all documents ordered by creation time descending when available."""
        client = self._client or self._create_client()
        documents = client.collection(self.collection_name).stream()
        return [snapshot.to_dict() for snapshot in documents]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Fetch a single document record from Firestore."""
        client = self._client or self._create_client()
        snapshot = client.collection(self.collection_name).document(document_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def update_document_status(
        self,
        document_id: str,
        status: str,
        *,
        error_message: str | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any] | None:
        """Update document status and return the latest record."""
        client = self._client or self._create_client()
        document_ref = client.collection(self.collection_name).document(document_id)
        snapshot = document_ref.get()
        if not snapshot.exists:
            return None

        payload: dict[str, Any] = {"status": status}
        if error_message is not None:
            payload["error_message"] = error_message
        payload.update(extra_fields)
        document_ref.update(payload)
        updated = document_ref.get()
        return updated.to_dict()

    def save_chat_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        citations: list[dict[str, Any]],
        latency_ms: int,
        *,
        tool_trace: list[dict[str, Any]] | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
    ) -> dict[str, Any]:
        """Persist a chat interaction under a session-scoped collection."""
        client = self._client or self._create_client()
        payload = {
            "session_id": session_id,
            "user_message": user_message,
            "assistant_answer": assistant_answer,
            "citations": citations,
            "latency_ms": latency_ms,
            "tool_trace": tool_trace or [],
            "current_design": current_design,
            "intent": intent,
            "search_profile": search_profile,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        client.collection(self.chat_collection_name).document().set(payload)
        return payload

    def _create_client(self) -> object:
        """Create a Google Cloud Firestore client lazily."""
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise RuntimeError("google-cloud-firestore is required for Firestore access.") from exc
        return firestore.Client(database=self.database)

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a saved current design snapshot for a session."""
        client = self._client or self._create_client()
        snapshot = client.collection(self.design_collection_name).document(session_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        """Persist the current design snapshot for a session."""
        client = self._client or self._create_client()
        payload = {
            "session_id": session_id,
            "current_design": design,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        client.collection(self.design_collection_name).document(session_id).set(payload)
        return payload
