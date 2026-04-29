"""Google Cloud Storage service abstractions."""

from __future__ import annotations

import json
from typing import Protocol


class StorageService(Protocol):
    """Interface for cloud storage document uploads."""

    def upload_document(self, document_id: str, file_name: str, content: bytes, content_type: str) -> str:
        """Upload a document and return its `gs://` URI."""

    def upload_jsonl(self, destination_path: str, records: list[dict[str, object]]) -> str:
        """Upload structured JSONL content and return its `gs://` URI."""

    def download_bytes(self, gcs_uri: str) -> bytes:
        """Download raw bytes from a `gs://` URI."""


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

    def upload_jsonl(self, destination_path: str, records: list[dict[str, object]]) -> str:
        """Upload JSONL data to Cloud Storage and return its URI."""
        client = self._client or self._create_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(destination_path)
        payload = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        blob.upload_from_string(payload, content_type="application/jsonl")
        return f"gs://{self.bucket_name}/{destination_path}"

    def download_bytes(self, gcs_uri: str) -> bytes:
        """Download raw bytes from a Cloud Storage URI."""
        bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
        client = self._client or self._create_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_bytes()

    @staticmethod
    def _create_client() -> object:
        """Create a Google Cloud Storage client lazily."""
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCP uploads.") from exc
        return storage.Client()


def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    """Split a `gs://` URI into bucket and blob path."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError("Invalid GCS URI.")
    path = gcs_uri.removeprefix("gs://")
    bucket_name, _, blob_name = path.partition("/")
    if not bucket_name or not blob_name:
        raise ValueError("Invalid GCS URI.")
    return bucket_name, blob_name
