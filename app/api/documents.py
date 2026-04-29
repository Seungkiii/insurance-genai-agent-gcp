"""Document upload and metadata routers."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.schemas.document_schema import (
    DocumentIndexRequest,
    DocumentIndexResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentUploadResponse,
)
from app.services.firestore_service import FirestoreService, GCPFirestoreService
from app.services.gcp_storage_service import GCPStorageService, StorageService

router = APIRouter()


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    """Return the storage service implementation."""
    if not settings.gcs_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GCS_BUCKET_NAME is not configured.",
        )
    return GCPStorageService(bucket_name=settings.gcs_bucket_name)


def get_firestore_service(settings: Settings = Depends(get_settings)) -> FirestoreService:
    """Return the Firestore service implementation."""
    if not settings.firestore_database:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FIRESTORE_DATABASE is not configured.",
        )
    return GCPFirestoreService(database=settings.firestore_database)


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    storage_service: StorageService = Depends(get_storage_service),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> DocumentUploadResponse:
    """Upload a PDF to Cloud Storage and persist document status in Firestore."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed.",
        )

    document_id = str(uuid4())
    content = await file.read()
    gcs_uri = storage_service.upload_document(
        document_id=document_id,
        file_name=file.filename,
        content=content,
        content_type=file.content_type or "application/pdf",
    )
    record = firestore_service.create_document(
        document_id=document_id,
        file_name=file.filename,
        gcs_uri=gcs_uri,
        status="uploaded",
    )

    return DocumentUploadResponse(
        document_id=record["document_id"],
        file_name=record["file_name"],
        status=record["status"],
        gcs_uri=record["gcs_uri"],
    )


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> DocumentListResponse:
    """List uploaded document metadata records."""
    documents = [DocumentRecord(**record) for record in firestore_service.list_documents()]
    return DocumentListResponse(documents=documents)


@router.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(
    document_id: str,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> DocumentRecord:
    """Fetch a single document metadata record."""
    record = firestore_service.get_document(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentRecord(**record)


@router.post("/documents/index", response_model=DocumentIndexResponse)
def index_document(request: DocumentIndexRequest) -> DocumentIndexResponse:
    """Placeholder endpoint for document indexing."""
    return DocumentIndexResponse(document_id=request.document_id, status="indexed", chunks=0)
