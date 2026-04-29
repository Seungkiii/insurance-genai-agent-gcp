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

    def _create_client(self) -> object:
        """Create a Google Cloud Firestore client lazily."""
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise RuntimeError("google-cloud-firestore is required for Firestore access.") from exc
        return firestore.Client(database=self.database)
