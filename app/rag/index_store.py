"""Index persistence helpers for chunks and embeddings."""

from __future__ import annotations

from dataclasses import asdict

from app.rag.chunker import RAGChunk
from app.services.gcp_storage_service import StorageService


class IndexStore:
    """Persist chunk and embedding artifacts for a document index."""

    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def save_chunks(self, document_id: str, chunks: list[RAGChunk]) -> str:
        """Save chunk metadata as JSONL to Cloud Storage."""
        records = [asdict(chunk) for chunk in chunks]
        destination_path = f"indexes/{document_id}/chunks.jsonl"
        return self.storage_service.upload_jsonl(destination_path, records)

    def save_embeddings(
        self,
        document_id: str,
        chunks: list[RAGChunk],
        embeddings: list[list[float]],
    ) -> str:
        """Save chunk embeddings as JSONL to Cloud Storage."""
        records = [
            {
                "document_id": chunk.document_id,
                "chunk_id": chunk.chunk_id,
                "document_name": chunk.document_name,
                "page": chunk.page,
                "section": chunk.section,
                "embedding": embedding,
            }
            for chunk, embedding in zip(chunks, embeddings, strict=False)
        ]
        destination_path = f"indexes/{document_id}/embeddings.jsonl"
        return self.storage_service.upload_jsonl(destination_path, records)
