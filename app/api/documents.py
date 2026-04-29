"""Document upload and metadata routers."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.rag.chunker import chunk_document
from app.rag.embedder import DummyEmbedder, Embedder, VertexAIEmbedder
from app.rag.index_store import IndexStore
from app.rag.parser import PDFDocumentParser
from app.schemas.document_schema import (
    DocumentIndexResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentUploadResponse,
)
from app.services.firestore_service import FirestoreService, GCPFirestoreService
from app.services.gcp_storage_service import GCPStorageService, StorageService
from app.services.vertex_ai_service import VertexAIEmbeddingService

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


def get_embedder(settings: Settings = Depends(get_settings)) -> Embedder:
    """Return the embedding implementation."""
    if (
        settings.vertex_ai_project_id
        and settings.vertex_ai_location
        and settings.embedding_model_name
    ):
        service = VertexAIEmbeddingService(
            project_id=settings.vertex_ai_project_id,
            location=settings.vertex_ai_location,
            model_name=settings.embedding_model_name,
        )
        return VertexAIEmbedder(service)
    return DummyEmbedder()


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


@router.get("/documents", response_model=DocumentListResponse, response_model_exclude_none=True)
def list_documents(
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> DocumentListResponse:
    """List uploaded document metadata records."""
    documents = [DocumentRecord(**record) for record in firestore_service.list_documents()]
    return DocumentListResponse(documents=documents)


@router.get("/documents/{document_id}", response_model=DocumentRecord, response_model_exclude_none=True)
def get_document(
    document_id: str,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> DocumentRecord:
    """Fetch a single document metadata record."""
    record = firestore_service.get_document(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentRecord(**record)


@router.post("/documents/{document_id}/index", response_model=DocumentIndexResponse)
def index_document(
    document_id: str,
    firestore_service: FirestoreService = Depends(get_firestore_service),
    storage_service: StorageService = Depends(get_storage_service),
    embedder: Embedder = Depends(get_embedder),
) -> DocumentIndexResponse:
    """Parse an uploaded PDF, build chunks, create embeddings, and persist index artifacts."""
    record = firestore_service.get_document(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    firestore_service.update_document_status(document_id, "indexing", error_message=None)

    try:
        pdf_bytes = storage_service.download_bytes(record["gcs_uri"])
        with TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / record["file_name"]
            pdf_path.write_bytes(pdf_bytes)

            parser = PDFDocumentParser()
            parsed_document = parser.parse(str(pdf_path), document_id=document_id)

        chunks = chunk_document(parsed_document)
        embeddings = embedder.embed_texts([chunk.content for chunk in chunks])

        index_store = IndexStore(storage_service)
        index_store.save_chunks(document_id, chunks)
        index_store.save_embeddings(document_id, chunks, embeddings)

        updated = firestore_service.update_document_status(
            document_id,
            "indexed",
            error_message=None,
            chunk_count=len(chunks),
        )
        response_record = updated or record
        return DocumentIndexResponse(
            document_id=response_record["document_id"],
            file_name=response_record["file_name"],
            gcs_uri=response_record["gcs_uri"],
            status=response_record["status"],
            chunks=response_record.get("chunk_count", len(chunks)),
        )
    except Exception as exc:  # noqa: BLE001
        firestore_service.update_document_status(
            document_id,
            "failed",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document indexing failed.",
        ) from exc
