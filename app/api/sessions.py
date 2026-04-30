"""Session router for persisted chat history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.chat import get_firestore_service
from app.schemas.chat_schema import (
    SessionDocumentSelectionRequest,
    SessionDocumentSelectionResponse,
    SessionHistoryResponse,
)
from app.services.firestore_service import FirestoreService

router = APIRouter()


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
@router.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
def get_session_messages(
    session_id: str,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SessionHistoryResponse:
    """Return ordered session history for the requested session."""
    try:
        messages = firestore_service.get_session_messages(session_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session history is temporarily unavailable.",
        ) from exc

    return SessionHistoryResponse(session_id=session_id, messages=messages)


@router.get("/sessions/{session_id}/documents", response_model=SessionDocumentSelectionResponse)
def get_session_documents(
    session_id: str,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SessionDocumentSelectionResponse:
    """Return the current session document selection context."""
    context = firestore_service.get_session_context(session_id) or {}
    return SessionDocumentSelectionResponse(
        session_id=session_id,
        selected_document_ids=list(context.get("selected_document_ids", [])),
        selected_product_names=list(context.get("selected_product_names", [])),
        search_scope=str(context.get("search_scope") or "selected"),
    )


@router.put("/sessions/{session_id}/documents", response_model=SessionDocumentSelectionResponse)
def update_session_documents(
    session_id: str,
    request: SessionDocumentSelectionRequest,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SessionDocumentSelectionResponse:
    """Update the session document selection context."""
    selected_product_names: list[str] = []
    for document_id in request.selected_document_ids:
        record = firestore_service.get_document(document_id)
        if record is None:
            continue
        selected_product_names.append(
            str(record.get("product_name") or record.get("document_name") or record.get("file_name") or document_id)
        )

    context = firestore_service.update_session_context(
        session_id,
        selected_document_ids=request.selected_document_ids,
        selected_product_names=selected_product_names,
        search_scope=request.search_scope,
    )
    return SessionDocumentSelectionResponse(
        session_id=session_id,
        selected_document_ids=list(context.get("selected_document_ids", [])),
        selected_product_names=list(context.get("selected_product_names", [])),
        search_scope=str(context.get("search_scope") or request.search_scope),
    )
