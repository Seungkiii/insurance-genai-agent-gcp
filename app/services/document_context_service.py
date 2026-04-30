"""Helpers for resolving document scope for chat requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.rag.search_profiles import SearchProfile, classify_search_profile
from app.services.firestore_service import FirestoreService

ALL_SEARCH_SCOPE = "all"
SELECTED_SEARCH_SCOPE = "selected"


@dataclass(frozen=True)
class ResolvedDocumentScope:
    """Resolved document scope for a chat request."""

    document_ids: list[str]
    selected_document_ids: list[str]
    selected_product_names: list[str]
    search_scope: str
    search_scope_label: str
    source: str
    invalid_document_ids: list[str]
    fallback_message: str | None = None


def resolve_document_scope(
    *,
    session_id: str,
    firestore_service: FirestoreService,
    request_document_ids: list[str] | None,
    request_search_scope: str | None,
    query: str,
    product_type_hint: str | None = None,
) -> ResolvedDocumentScope:
    """Resolve the document ids that should be searched for this request."""
    session_context = firestore_service.get_session_context(session_id) or {}
    session_scope = str(session_context.get("search_scope") or "").strip() or ALL_SEARCH_SCOPE
    requested_scope = str(request_search_scope or "").strip()
    effective_request_scope = requested_scope if requested_scope in {ALL_SEARCH_SCOPE, SELECTED_SEARCH_SCOPE} else None
    search_profile = classify_search_profile(query)

    requested_ids, invalid_request_ids = sanitize_document_ids(
        firestore_service,
        request_document_ids,
    )
    session_selected_ids, invalid_session_ids = sanitize_document_ids(
        firestore_service,
        session_context.get("selected_document_ids"),
    )
    invalid_document_ids = invalid_request_ids + [item for item in invalid_session_ids if item not in invalid_request_ids]

    if requested_ids:
        documents = _load_indexed_documents_by_id(firestore_service, requested_ids)
        return _build_scope(
            documents=documents,
            selected_document_ids=requested_ids,
            search_scope=SELECTED_SEARCH_SCOPE,
            source="request",
            invalid_document_ids=invalid_document_ids,
            fallback_message=_no_documents_message() if not documents else None,
        )

    effective_scope = effective_request_scope or session_scope

    if effective_scope == ALL_SEARCH_SCOPE:
        candidates = _filter_candidates(
            firestore_service.list_documents(),
            query=query,
            product_type_hint=product_type_hint,
            search_profile=search_profile,
        )
        return _build_scope(
            documents=candidates,
            selected_document_ids=session_selected_ids,
            search_scope=ALL_SEARCH_SCOPE,
            source="all_documents",
            invalid_document_ids=invalid_document_ids,
            fallback_message=_resolve_all_scope_fallback(candidates, query),
        )

    if session_selected_ids:
        documents = _load_indexed_documents_by_id(firestore_service, session_selected_ids)
        return _build_scope(
            documents=documents,
            selected_document_ids=session_selected_ids,
            search_scope=SELECTED_SEARCH_SCOPE,
            source="session",
            invalid_document_ids=invalid_document_ids,
            fallback_message=_no_documents_message() if not documents else None,
        )

    candidates = _filter_candidates(
        firestore_service.list_documents(),
        query=query,
        product_type_hint=product_type_hint,
        search_profile=search_profile,
    )
    default_scope = ALL_SEARCH_SCOPE if len(candidates) != 1 else SELECTED_SEARCH_SCOPE
    return _build_scope(
        documents=candidates,
        selected_document_ids=[],
        search_scope=default_scope,
        source="all_documents",
        invalid_document_ids=invalid_document_ids,
        fallback_message=_resolve_all_scope_fallback(candidates, query),
    )


def sanitize_document_ids(
    firestore_service: FirestoreService,
    value: Any,
) -> tuple[list[str], list[str]]:
    """Return deduplicated indexed document ids plus rejected raw values."""
    if not isinstance(value, list):
        return [], []

    valid_ids: list[str] = []
    invalid_ids: list[str] = []
    for raw_item in value:
        normalized = str(raw_item or "").strip()
        if not normalized:
            continue

        record = firestore_service.get_document(normalized)
        if record is None:
            if _looks_like_uuid(normalized):
                invalid_ids.append(normalized)
            else:
                invalid_ids.append(normalized)
            continue

        if record.get("status") != "indexed":
            invalid_ids.append(normalized)
            continue

        if normalized not in valid_ids:
            valid_ids.append(normalized)
    return valid_ids, invalid_ids


def _build_scope(
    *,
    documents: list[dict[str, Any]],
    selected_document_ids: list[str],
    search_scope: str,
    source: str,
    invalid_document_ids: list[str],
    fallback_message: str | None,
) -> ResolvedDocumentScope:
    resolved_document_ids = [str(document["document_id"]) for document in documents]
    selected_product_names = [_record_display_name(document) for document in documents if _record_display_name(document)]
    scope_label = _build_scope_label(search_scope, resolved_document_ids)
    return ResolvedDocumentScope(
        document_ids=resolved_document_ids,
        selected_document_ids=selected_document_ids,
        selected_product_names=list(dict.fromkeys(selected_product_names)),
        search_scope=search_scope,
        search_scope_label=scope_label,
        source=source,
        invalid_document_ids=invalid_document_ids,
        fallback_message=fallback_message,
    )


def _filter_candidates(
    records: list[dict[str, Any]],
    *,
    query: str,
    product_type_hint: str | None,
    search_profile: SearchProfile,
) -> list[dict[str, Any]]:
    indexed = [record for record in records if record.get("status") == "indexed"]
    if len(indexed) <= 5:
        return indexed

    narrowed = indexed
    if product_type_hint:
        narrowed = [record for record in narrowed if record.get("product_type") == product_type_hint] or narrowed

    preferred_types = set(search_profile.preferred_document_types)
    if preferred_types:
        preferred = [record for record in narrowed if record.get("document_type") in preferred_types]
        if preferred:
            narrowed = preferred

    query_matches = [
        record
        for record in narrowed
        if any(token in _record_display_name(record).lower() for token in _query_name_tokens(query))
    ]
    if query_matches:
        narrowed = query_matches

    return narrowed


def _load_indexed_documents_by_id(
    firestore_service: FirestoreService,
    document_ids: list[str],
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for document_id in document_ids:
        record = firestore_service.get_document(document_id)
        if record is not None and record.get("status") == "indexed":
            documents.append(record)
    return documents


def _resolve_all_scope_fallback(documents: list[dict[str, Any]], query: str) -> str | None:
    if not documents:
        return _no_documents_message()

    if "이 상품" in query and len(documents) > 1:
        return "어떤 상품을 기준으로 확인할까요? 상품을 선택하거나 상품명을 질문에 함께 적어주시면 더 정확하게 안내해드릴게요."
    return None


def _no_documents_message() -> str:
    return "현재 검색 가능한 indexed 문서가 없습니다. 먼저 문서를 업로드하고 인덱싱한 뒤 다시 질문해 주세요."


def _build_scope_label(search_scope: str, resolved_document_ids: list[str]) -> str:
    if search_scope == ALL_SEARCH_SCOPE:
        return "전체 상품"
    return f"선택 상품 {len(resolved_document_ids)}개"


def _record_display_name(record: dict[str, Any]) -> str:
    product_name = str(record.get("product_name") or "").strip()
    if product_name:
        return product_name
    document_name = str(record.get("document_name") or "").strip()
    if document_name:
        return document_name
    file_name = str(record.get("file_name") or "").strip()
    if file_name:
        return file_name
    return ""


def _query_name_tokens(query: str) -> list[str]:
    tokens = [
        token.strip().lower()
        for token in query.replace("/", " ").replace(",", " ").split()
        if len(token.strip()) >= 2
    ]
    return list(dict.fromkeys(tokens))


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def derive_product_name(file_name: str) -> str:
    """Derive a user-facing product name from a stored file name."""
    return Path(file_name).stem
