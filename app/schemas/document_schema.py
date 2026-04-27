"""Document-related schemas."""

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Document upload response."""

    document_id: str
    status: str


class DocumentIndexRequest(BaseModel):
    """Document index request."""

    document_id: str


class DocumentIndexResponse(BaseModel):
    """Document index response."""

    document_id: str
    status: str
    chunks: int
