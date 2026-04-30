"""Helpers for resolving document scope for chat requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    fallback_message: str | None = None


def resolve_document_scope(
    *,
    session_id: str,
    firestore_service: FirestoreService,
    request_document_ids: list[str] | None,
    query: str,
    product_type_hint: str | None = None,
) -> ResolvedDocumentScope:
    """Resolve the document ids that should be searched for this request."""
    requested_ids = _normalize_document_ids(request_document_ids)
    session_context = firestore_service.get_session_context(session_id) or {}
    session_scope = str(session_context.get("search_scope") or "").strip() or SELECTED_SEARCH_SCOPE
    session_selected_ids = _normalize_document_ids(session_context.get("selected_document_ids"))
    search_profile = classify_search_profile(query)

    if requested_ids:
        documents = _load_indexed_documents_by_id(firestore_service, requested_ids)
        return _build_scope(
            documents=documents,
            requested_ids=requested_ids,
            search_scope=SELECTED_SEARCH_SCOPE,
            source="request",
            fallback_message=_no_documents_message() if not documents else None,
        )

    if session_scope == ALL_SEARCH_SCOPE:
        candidates = _filter_candidates(
            firestore_service.list_documents(),
            query=query,
            product_type_hint=product_type_hint,
            search_profile=search_profile,
        )
        return _build_scope(
            documents=candidates,
            requested_ids=[],
            search_scope=ALL_SEARCH_SCOPE,
            source="all_documents",
            fallback_message=_resolve_all_scope_fallback(candidates, query),
        )

    if session_selected_ids:
        documents = _load_indexed_documents_by_id(firestore_service, session_selected_ids)
        return _build_scope(
            documents=documents,
            requested_ids=session_selected_ids,
            search_scope=SELECTED_SEARCH_SCOPE,
            source="session",
            fallback_message=_no_documents_message() if not documents else None,
        )

    candidates = _filter_candidates(
        firestore_service.list_documents(),
        query=query,
        product_type_hint=product_type_hint,
        search_profile=search_profile,
    )
    default_scope = SELECTED_SEARCH_SCOPE if len(candidates) == 1 else ALL_SEARCH_SCOPE
    return _build_scope(
        documents=candidates,
        requested_ids=[],
        search_scope=default_scope,
        source="all_documents",
        fallback_message=_resolve_all_scope_fallback(candidates, query),
    )


def infer_selected_documents_from_result(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Infer representative documents from workflow output for session continuity."""
    if result.get("current_design"):
        current_design = result["current_design"]
        document_ids = _normalize_document_ids(current_design.get("selected_document_ids"))
        product_names = _normalize_string_list(current_design.get("selected_product_names"))
        if product_names:
            return document_ids, product_names

    recommended_products = result.get("recommended_products", [])
    if isinstance(recommended_products, list) and recommended_products:
        document_ids = _normalize_document_ids([product.get("document_id") for product in recommended_products])
        product_names = [
            _record_display_name(product)
            for product in recommended_products
            if _record_display_name(product)
        ]
        if document_ids or product_names:
            return document_ids, product_names

    citations = result.get("citations", [])
    chunks = result.get("retrieved_chunks", [])
    document_ids = _normalize_document_ids([chunk.get("document_id") for chunk in chunks[:3]])
    product_names = [
        str(citation.get("document_name") or "").strip()
        for citation in citations[:3]
        if str(citation.get("document_name") or "").strip()
    ]
    return document_ids, product_names


def _build_scope(
    *,
    documents: list[dict[str, Any]],
    requested_ids: list[str],
    search_scope: str,
    source: str,
    fallback_message: str | None,
) -> ResolvedDocumentScope:
    document_ids = requested_ids or [str(document["document_id"]) for document in documents]
    product_names = [_record_display_name(document) for document in documents if _record_display_name(document)]
    scope_label = _build_scope_label(search_scope, product_names)
    return ResolvedDocumentScope(
        document_ids=document_ids,
        selected_document_ids=document_ids,
        selected_product_names=product_names,
        search_scope=search_scope,
        search_scope_label=scope_label,
        source=source,
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


def _build_scope_label(search_scope: str, product_names: list[str]) -> str:
    if search_scope == ALL_SEARCH_SCOPE:
        return "전체 상품"
    if not product_names:
        return "선택 상품 0개"
    return f"선택 상품 {len(product_names)}개"


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


def _normalize_document_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _query_name_tokens(query: str) -> list[str]:
    tokens = [
        token.strip().lower()
        for token in query.replace("/", " ").replace(",", " ").split()
        if len(token.strip()) >= 2
    ]
    return list(dict.fromkeys(tokens))


def derive_product_name(file_name: str) -> str:
    """Derive a user-facing product name from a stored file name."""
    return Path(file_name).stem
