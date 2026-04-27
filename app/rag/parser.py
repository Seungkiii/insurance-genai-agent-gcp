"""RAG parser interface placeholders."""

from typing import Protocol


class DocumentParser(Protocol):
    """Interface for policy document parser implementations."""

    def parse(self, document_path: str) -> str:
        """Parse a document file and return text content."""


class DummyDocumentParser:
    """Dummy parser returning synthetic content."""

    def parse(self, document_path: str) -> str:
        """Parse document path to synthetic text."""
        return f"Parsed synthetic text for {document_path}"
