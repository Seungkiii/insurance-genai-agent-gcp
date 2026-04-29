"""Index an uploaded document from Cloud Storage into chunk and embedding artifacts."""

from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.rag.chunker import chunk_document
from app.rag.embedder import DummyEmbedder, VertexAIEmbedder
from app.rag.index_store import IndexStore
from app.rag.parser import PDFDocumentParser
from app.services.firestore_service import GCPFirestoreService
from app.services.gcp_storage_service import GCPStorageService
from app.services.vertex_ai_service import VertexAIEmbeddingService


def main() -> None:
    """Run the document ingestion pipeline for a stored document."""
    parser = argparse.ArgumentParser(description="Ingest an uploaded insurance PDF into RAG artifacts.")
    parser.add_argument("document_id", help="Document id stored in Firestore.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.gcs_bucket_name or not settings.firestore_database:
        raise SystemExit("GCS_BUCKET_NAME and FIRESTORE_DATABASE must be configured.")

    storage_service = GCPStorageService(bucket_name=settings.gcs_bucket_name)
    firestore_service = GCPFirestoreService(database=settings.firestore_database)

    record = firestore_service.get_document(args.document_id)
    if record is None:
        raise SystemExit("Document not found.")

    firestore_service.update_document_status(args.document_id, "indexing", error_message=None)
    pdf_bytes = storage_service.download_bytes(record["gcs_uri"])

    from pathlib import Path
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / record["file_name"]
        pdf_path.write_bytes(pdf_bytes)
        parsed_document = PDFDocumentParser().parse(str(pdf_path), document_id=args.document_id)

    chunks = chunk_document(parsed_document)
    if (
        settings.vertex_ai_project_id
        and settings.effective_embedding_location
        and settings.embedding_model_name
    ):
        embedder = VertexAIEmbedder(
            VertexAIEmbeddingService(
                project_id=settings.vertex_ai_project_id,
                location=settings.effective_embedding_location or "",
                model_name=settings.embedding_model_name,
            )
        )
    else:
        embedder = DummyEmbedder()

    embeddings = embedder.embed_texts([chunk.content for chunk in chunks])
    store = IndexStore(storage_service)
    store.save_chunks(args.document_id, chunks)
    store.save_embeddings(args.document_id, chunks, embeddings)
    firestore_service.update_document_status(args.document_id, "indexed", error_message=None, chunk_count=len(chunks))


if __name__ == "__main__":
    main()
