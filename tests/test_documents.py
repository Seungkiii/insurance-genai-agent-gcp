"""Tests for document upload and metadata endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.documents import get_firestore_service, get_storage_service
from app.main import create_app


class FakeStorageService:
    """Mock Cloud Storage uploader for tests."""

    def upload_document(self, document_id: str, file_name: str, content: bytes, content_type: str) -> str:
        assert file_name.endswith(".pdf")
        assert content_type == "application/pdf"
        assert content.startswith(b"%PDF")
        return f"gs://sample-bucket/documents/{document_id}/original.pdf"


class FakeFirestoreService:
    """Mock Firestore repository for tests."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, str]] = {}

    def create_document(
        self,
        document_id: str,
        file_name: str,
        gcs_uri: str,
        status: str = "uploaded",
    ) -> dict[str, str]:
        record = {
            "document_id": document_id,
            "file_name": file_name,
            "gcs_uri": gcs_uri,
            "status": status,
            "created_at": "2026-04-29T00:00:00+00:00",
        }
        self.records[document_id] = record
        return record

    def list_documents(self) -> list[dict[str, str]]:
        return list(self.records.values())

    def get_document(self, document_id: str) -> dict[str, str] | None:
        return self.records.get(document_id)

    def update_document_status(
        self,
        document_id: str,
        status: str,
        *,
        error_message: str | None = None,
        **extra_fields: str,
    ) -> dict[str, str] | None:
        record = self.records.get(document_id)
        if record is None:
            return None
        record["status"] = status
        if error_message is not None:
            record["error_message"] = error_message
        for key, value in extra_fields.items():
            record[key] = value
        return record


def create_test_client() -> tuple[TestClient, FakeFirestoreService]:
    """Create an app client with mocked GCP services."""
    app = create_app()
    firestore_service = FakeFirestoreService()
    app.dependency_overrides[get_storage_service] = lambda: FakeStorageService()
    app.dependency_overrides[get_firestore_service] = lambda: firestore_service
    return TestClient(app), firestore_service


def test_upload_document_saves_to_storage_and_firestore() -> None:
    """Uploading a PDF should return document metadata and persist a record."""
    client, firestore_service = create_test_client()

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample_policy.pdf", b"%PDF-1.4 sample content", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_name"] == "sample_policy.pdf"
    assert payload["status"] == "uploaded"
    assert payload["gcs_uri"].startswith("gs://sample-bucket/documents/")
    assert payload["document_id"] in firestore_service.records


def test_upload_document_rejects_non_pdf_files() -> None:
    """Only PDF uploads should be accepted."""
    client, _ = create_test_client()

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed."


def test_list_documents_returns_uploaded_records() -> None:
    """Document list endpoint should return persisted metadata."""
    client, firestore_service = create_test_client()
    created = firestore_service.create_document(
        document_id="doc-001",
        file_name="sample_policy.pdf",
        gcs_uri="gs://sample-bucket/documents/doc-001/original.pdf",
    )

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json() == {"documents": [created]}


def test_get_document_returns_document_status() -> None:
    """Single document endpoint should return the requested metadata."""
    client, firestore_service = create_test_client()
    created = firestore_service.create_document(
        document_id="doc-002",
        file_name="sample_policy.pdf",
        gcs_uri="gs://sample-bucket/documents/doc-002/original.pdf",
    )

    response = client.get("/api/v1/documents/doc-002")

    assert response.status_code == 200
    assert response.json() == created


def test_get_document_returns_404_when_missing() -> None:
    """Missing documents should return a 404 response."""
    client, _ = create_test_client()

    response = client.get("/api/v1/documents/missing-doc")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."
