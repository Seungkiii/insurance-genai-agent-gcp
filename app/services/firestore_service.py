"""Firestore service abstractions for document metadata and chat sessions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Protocol


class FirestoreService(Protocol):
    """Interface for document metadata persistence."""

    def create_document(
        self,
        document_id: str,
        file_name: str,
        gcs_uri: str,
        status: str = "uploaded",
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """Create and persist a document metadata record."""

    def list_documents(self) -> list[dict[str, Any]]:
        """Return persisted document metadata records."""

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Return a document metadata record by id."""

    def update_document_status(
        self,
        document_id: str,
        status: str,
        *,
        error_message: str | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any] | None:
        """Update document status and optional metadata."""

    def save_chat_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        citations: list[dict[str, Any]],
        latency_ms: int,
        *,
        tool_trace: list[dict[str, Any]] | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
    ) -> dict[str, Any]:
        """Persist a chat interaction for audit and session review."""

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        """Return the current design snapshot for a session when available."""

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        """Persist the current design snapshot for a session."""

    def save_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        message_id: str | None = None,
        document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        search_scope_label: str | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
        confidence_score: float | None = None,
        fallback_required: bool | None = None,
        citations: list[dict[str, Any]] | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
        recommended_design: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a single session message."""

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Return ordered session messages for the requested session."""

    def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        """Return the session context document when available."""

    def update_session_context(
        self,
        session_id: str,
        *,
        selected_document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        current_design: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update session-level context used for future searches."""


class GCPFirestoreService:
    """Firestore-backed implementation for document metadata storage."""

    def __init__(
        self,
        database: str,
        collection_name: str = "documents",
        client: object | None = None,
    ) -> None:
        self.database = database
        self.collection_name = collection_name
        self.chat_collection_name = "chat_sessions"
        self.session_collection_name = "sessions"
        self._client = client

    def create_document(
        self,
        document_id: str,
        file_name: str,
        gcs_uri: str,
        status: str = "uploaded",
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """Persist document metadata in Firestore."""
        record = {
            "document_id": document_id,
            "file_name": file_name,
            "document_name": extra_fields.get("document_name", file_name),
            "product_name": extra_fields.get("product_name"),
            "gcs_uri": gcs_uri,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        record.update(extra_fields)
        client = self._client or self._create_client()
        client.collection(self.collection_name).document(document_id).set(record)
        return record

    def list_documents(self) -> list[dict[str, Any]]:
        """Return all documents ordered by creation time descending when available."""
        client = self._client or self._create_client()
        documents = client.collection(self.collection_name).stream()
        return [snapshot.to_dict() for snapshot in documents]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Fetch a single document record from Firestore."""
        client = self._client or self._create_client()
        snapshot = client.collection(self.collection_name).document(document_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def update_document_status(
        self,
        document_id: str,
        status: str,
        *,
        error_message: str | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any] | None:
        """Update document status and return the latest record."""
        client = self._client or self._create_client()
        document_ref = client.collection(self.collection_name).document(document_id)
        snapshot = document_ref.get()
        if not snapshot.exists:
            return None

        payload: dict[str, Any] = {"status": status}
        if error_message is not None:
            payload["error_message"] = error_message
        payload.update(extra_fields)
        document_ref.update(payload)
        updated = document_ref.get()
        return updated.to_dict()

    def save_chat_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        citations: list[dict[str, Any]],
        latency_ms: int,
        *,
        tool_trace: list[dict[str, Any]] | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
    ) -> dict[str, Any]:
        """Persist a chat interaction and mirror it into session messages."""
        interaction_payload = {
            "session_id": session_id,
            "user_message": user_message,
            "assistant_answer": assistant_answer,
            "citations": citations,
            "latency_ms": latency_ms,
            "tool_trace": tool_trace or [],
            "current_design": current_design,
            "intent": intent,
            "search_profile": search_profile,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        client = self._client or self._create_client()
        client.collection(self.chat_collection_name).document().set(interaction_payload)

        self.save_session_message(
            session_id,
            "user",
            user_message,
            document_ids=_coerce_string_list(current_design.get("selected_document_ids", [])) if current_design else None,
        )
        assistant_record = self.save_session_message(
            session_id,
            "assistant",
            assistant_answer,
            current_design=current_design,
            intent=intent,
            search_profile=search_profile,
            citations=citations,
            tool_trace=tool_trace,
        )
        return {"interaction": interaction_payload, "assistant_message": assistant_record}

    def _create_client(self) -> object:
        """Create a Google Cloud Firestore client lazily."""
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise RuntimeError("google-cloud-firestore is required for Firestore access.") from exc
        return firestore.Client(database=self.database)

    def get_current_design(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a saved current design snapshot for a session."""
        client = self._client or self._create_client()
        snapshot = client.collection(self.session_collection_name).document(session_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def save_current_design(self, session_id: str, design: dict[str, Any]) -> dict[str, Any]:
        """Persist the current design snapshot for a session."""
        payload = {
            "session_id": session_id,
            "current_design": design,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._upsert_session(
            session_id,
            selected_document_ids=_coerce_string_list(design.get("selected_document_ids")),
            selected_product_names=_coerce_string_list(design.get("selected_product_names")),
            current_design=design,
            extra_fields={"updated_at": payload["updated_at"]},
        )
        return payload

    def save_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        message_id: str | None = None,
        document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        search_scope_label: str | None = None,
        current_design: dict[str, Any] | None = None,
        intent: str | None = None,
        search_profile: str | None = None,
        confidence_score: float | None = None,
        fallback_required: bool | None = None,
        citations: list[dict[str, Any]] | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
        recommended_design: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a single session message under sessions/{session_id}/messages."""
        client = self._client or self._create_client()
        created_at = datetime.now(timezone.utc).isoformat()
        resolved_message_id = message_id or f"{role}-{uuid4().hex}"
        payload: dict[str, Any] = {
            "message_id": resolved_message_id,
            "role": role,
            "content": content,
            "created_at": created_at,
            "intent": intent,
            "search_profile": search_profile,
            "search_scope": search_scope,
            "search_scope_label": search_scope_label,
            "selected_product_names": selected_product_names or [],
            "selected_document_ids": document_ids or [],
            "confidence_score": confidence_score,
            "fallback_required": fallback_required,
            "citations": citations or [],
            "tool_trace": tool_trace or [],
            "recommended_design": recommended_design,
            "current_design": current_design,
        }
        session_ref = self._upsert_session(
            session_id,
            selected_document_ids=document_ids,
            selected_product_names=selected_product_names,
            search_scope=search_scope,
            current_design=current_design,
            extra_fields={"updated_at": created_at},
        )
        session_ref.collection("messages").document(resolved_message_id).set(payload)
        return {"session_id": session_id, **payload}

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch ordered session messages for a session."""
        client = self._client or self._create_client()
        session_snapshot = client.collection(self.session_collection_name).document(session_id).get()
        if not session_snapshot.exists:
            return []

        message_snapshots = (
            client.collection(self.session_collection_name)
            .document(session_id)
            .collection("messages")
            .order_by("created_at")
            .stream()
        )
        return [snapshot.to_dict() for snapshot in message_snapshots]

    def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        """Fetch the parent session context."""
        client = self._client or self._create_client()
        snapshot = client.collection(self.session_collection_name).document(session_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def update_session_context(
        self,
        session_id: str,
        *,
        selected_document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        current_design: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update session-level selection context."""
        session_ref = self._upsert_session(
            session_id,
            selected_document_ids=selected_document_ids,
            selected_product_names=selected_product_names,
            search_scope=search_scope,
            current_design=current_design,
        )
        return session_ref.get().to_dict()

    def _upsert_session(
        self,
        session_id: str,
        *,
        selected_document_ids: list[str] | None = None,
        selected_product_names: list[str] | None = None,
        search_scope: str | None = None,
        current_design: dict[str, Any] | None = None,
        extra_fields: Mapping[str, Any] | None = None,
    ) -> Any:
        """Ensure the parent session document exists and return its reference."""
        client = self._client or self._create_client()
        session_ref = client.collection(self.session_collection_name).document(session_id)
        snapshot = session_ref.get()
        existing = snapshot.to_dict() if snapshot.exists else {}
        now = datetime.now(timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "session_id": session_id,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "selected_document_ids": (
                selected_document_ids
                if selected_document_ids is not None
                else existing.get("selected_document_ids", [])
            ),
            "selected_product_names": (
                selected_product_names
                if selected_product_names is not None
                else existing.get("selected_product_names", [])
            ),
            "search_scope": search_scope if search_scope is not None else existing.get("search_scope", "selected"),
            "current_design": current_design if current_design is not None else existing.get("current_design"),
        }
        if extra_fields:
            payload.update(dict(extra_fields))
        session_ref.set(payload, merge=True)
        return session_ref


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
