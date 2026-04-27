"""Document upload and indexing routers."""

from fastapi import APIRouter

from app.schemas.document_schema import DocumentIndexRequest, DocumentIndexResponse, DocumentUploadResponse

router = APIRouter()


@router.post("/documents/upload", response_model=DocumentUploadResponse)
def upload_document() -> DocumentUploadResponse:
    """Placeholder endpoint for policy document uploads."""
    return DocumentUploadResponse(document_id="doc-sample-001", status="uploaded")


@router.post("/documents/index", response_model=DocumentIndexResponse)
def index_document(request: DocumentIndexRequest) -> DocumentIndexResponse:
    """Placeholder endpoint for document indexing."""
    return DocumentIndexResponse(document_id=request.document_id, status="indexed", chunks=0)
