"""Cloud Storage service interface placeholders."""

from typing import Protocol


class StorageService(Protocol):
    """Interface for cloud storage service."""

    def upload(self, local_path: str, destination_path: str) -> str:
        """Upload a file and return URI."""


class DummyStorageService:
    """Dummy storage service for local testing."""

    def upload(self, local_path: str, destination_path: str) -> str:
        """Return synthetic gs:// URI without external calls."""
        return f"gs://dummy-bucket/{destination_path}"
