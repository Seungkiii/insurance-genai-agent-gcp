"""Document-related schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    """Document metadata returned by the API."""

    document_id: str
    file_name: str
    status: str
    gcs_uri: str
    created_at: str | None = None


class DocumentUploadResponse(BaseModel):
    """Document upload response."""

    document_id: str
    file_name: str
    status: str
    gcs_uri: str


class DocumentListResponse(BaseModel):
    """List of persisted documents."""

    documents: list[DocumentRecord]


class DocumentIndexRequest(BaseModel):
    """Document index request."""

    document_id: str


class DocumentIndexResponse(BaseModel):
    """Document index response."""

    document_id: str
    status: str
    chunks: int
