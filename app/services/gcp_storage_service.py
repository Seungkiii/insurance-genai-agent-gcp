"""Google Cloud Storage service abstractions."""

from __future__ import annotations

from typing import Protocol


class StorageService(Protocol):
    """Interface for cloud storage document uploads."""

    def upload_document(self, document_id: str, file_name: str, content: bytes, content_type: str) -> str:
        """Upload a document and return its `gs://` URI."""


class GCPStorageService:
    """Cloud Storage-backed implementation for PDF document uploads."""

    def __init__(self, bucket_name: str, client: object | None = None) -> None:
        self.bucket_name = bucket_name
        self._client = client

    def upload_document(self, document_id: str, file_name: str, content: bytes, content_type: str) -> str:
        """Upload a PDF to `documents/{document_id}/original.pdf` and return its URI."""
        client = self._client or self._create_client()
        bucket = client.bucket(self.bucket_name)
        destination_path = f"documents/{document_id}/original.pdf"
        blob = bucket.blob(destination_path)
        blob.upload_from_string(content, content_type=content_type)
        return f"gs://{self.bucket_name}/{destination_path}"

    @staticmethod
    def _create_client() -> object:
        """Create a Google Cloud Storage client lazily."""
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCP uploads.") from exc
        return storage.Client()
