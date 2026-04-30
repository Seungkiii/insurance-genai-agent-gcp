"""Document-related schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    """Document metadata returned by the API."""

    document_id: str
    file_name: str
    document_name: str | None = None
    product_name: str | None = None
    status: str
    gcs_uri: str
    product_type: str | None = None
    document_type: str | None = None
    created_at: str | None = None
    indexed_at: str | None = None
    error_message: str | None = None


class DocumentUploadResponse(BaseModel):
    """Document upload response."""

    document_id: str
    file_name: str
    status: str
    gcs_uri: str
    product_type: str | None = None
    document_type: str | None = None


class DocumentListResponse(BaseModel):
    """List of persisted documents."""

    documents: list[DocumentRecord]


class DocumentIndexRequest(BaseModel):
    """Document index request."""

    document_id: str


class DocumentIndexResponse(BaseModel):
    """Document index response."""

    document_id: str
    file_name: str
    gcs_uri: str
    status: str
    chunks: int
    chunk_count: int | None = None
    product_type: str | None = None
    document_type: str | None = None
    normalized_section_counts: dict[str, int] | None = None
