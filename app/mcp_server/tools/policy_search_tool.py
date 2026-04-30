"""Policy search tool backed by the hybrid insurance RAG retriever."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.rag.citation import build_citations
from app.rag.confidence import compute_confidence_score
from app.rag.embedder import Embedder
from app.rag.retriever import GcsEmbeddingRetriever, RetrievalResult
from app.rag.search_profiles import SEARCH_PROFILES, SearchProfile, build_expanded_query, classify_search_profile
from app.services.firestore_service import FirestoreService
from app.services.gcp_storage_service import StorageService

from .base import BaseTool


@dataclass
class PolicySearchTool(BaseTool):
    """Search indexed insurance documents using the hybrid retriever."""

    storage_service: StorageService | None = None
    embedder: Embedder | None = None
    firestore_service: FirestoreService | None = None
    bucket_name: str = ""
    name: str = "policy_search_tool"
    description: str = (
        "Search indexed insurance product PDFs using search profiles, metadata-aware query expansion, and hybrid retrieval."
    )
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "document_ids": {"type": "array", "items": {"type": "string"}},
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                "top_k_per_document": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                "search_profiles": {"type": "array", "items": {"type": "string"}},
                "product_type": {"type": "string"},
            },
            "required": ["query"],
        }
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "citations": {"type": "array"},
                "search_profile": {"type": "string"},
                "product_type": {"type": "string"},
                "document_type": {"type": "string"},
                "normalized_section": {"type": "array", "items": {"type": "string"}},
                "confidence_signal": {"type": "string"},
                "fallback_required": {"type": "boolean"},
            },
        }
    )

    def execute(self, payload: dict[str, Any], trace_summary: list[str]) -> dict[str, Any]:
        """Execute metadata-aware policy retrieval."""
        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError("The 'query' field is required.")
        if self.storage_service is None or self.embedder is None or self.firestore_service is None or not self.bucket_name:
            raise RuntimeError("PolicySearchTool is not configured with storage, embedder, firestore, and bucket_name.")

        top_k = int(payload.get("top_k", 5))
        top_k_per_document = int(payload.get("top_k_per_document", 3))
        requested_document_ids = [str(item) for item in payload.get("document_ids", []) if str(item).strip()]
        requested_product_type = _optional_string(payload.get("product_type"))
        requested_search_profiles = [
            str(item).strip()
            for item in payload.get("search_profiles", [])
            if str(item).strip() in SEARCH_PROFILES
        ]

        candidate_documents = self._resolve_documents(requested_document_ids, requested_product_type)
        if not candidate_documents:
            raise ValueError("No indexed documents matched the requested scope.")

        product_types = [str(record.get("product_type", "unknown")) for record in candidate_documents]
        search_profiles = (
            [SEARCH_PROFILES[name] for name in requested_search_profiles]
            if requested_search_profiles
            else [classify_search_profile(query)]
        )
        primary_search_profile = search_profiles[0]
        expanded_queries = [
            build_expanded_query(
                query,
                search_profile,
                product_types=product_types,
                include_product_context=len(search_profiles) > 1,
            )
            for search_profile in search_profiles
        ]
        trace_summary.extend(
            [
                f"profile={primary_search_profile.name}",
                f"search_profiles={[profile.name for profile in search_profiles]}",
                f"expanded_query={expanded_queries[0]}",
                f"document_count={len(candidate_documents)}",
            ]
        )

        retriever = GcsEmbeddingRetriever(self.storage_service, self.bucket_name)
        result_sets = []
        embedding_record_count = 0
        for search_profile, expanded_query in zip(search_profiles, expanded_queries, strict=False):
            query_embedding = self.embedder.embed_texts([expanded_query])[0]
            retrieval_output = retriever.retrieve(
                query_embedding,
                [str(record["document_id"]) for record in candidate_documents],
                top_k=top_k,
                question=expanded_query,
                search_profile=search_profile,
                top_k_per_document=2 if search_profile.name == "product_comparison" else top_k_per_document,
            )
            if isinstance(retrieval_output, tuple):
                results, diagnostics = retrieval_output
                embedding_record_count += int(diagnostics.get("embedding_record_count", 0))
            else:
                results = retrieval_output
            result_sets.append(results)
        results = _merge_results(result_sets, top_k=top_k)

        fallback_required, fallback_reason = _requires_fallback(results, primary_search_profile)
        confidence_score = compute_confidence_score(
            results=results,
            profile=primary_search_profile,
            fallback_required=fallback_required,
        )
        confidence_signal = _confidence_signal(confidence_score)
        citations = [citation.model_dump() for citation in build_citations(results)]
        chunks = [_serialize_result(result) for result in results]

        return {
            "query": query,
            "expanded_query": expanded_queries[0],
            "search_profile": primary_search_profile.name,
            "product_type": _dominant_value(results, "product_type"),
            "document_type": _dominant_value(results, "document_type"),
            "normalized_section": sorted({result.chunk.normalized_section for result in results}),
            "candidate_document_count": len(candidate_documents),
            "candidate_document_ids": [str(record["document_id"]) for record in candidate_documents],
            "embedding_record_count": embedding_record_count,
            "selected_result_count": len(results),
            "chunks": chunks,
            "citations": citations,
            "confidence_score": confidence_score,
            "confidence_signal": confidence_signal,
            "fallback_required": fallback_required,
            "fallback_reason": fallback_reason,
        }

    def _resolve_documents(
        self,
        requested_document_ids: list[str],
        requested_product_type: str | None,
    ) -> list[dict[str, Any]]:
        if self.firestore_service is None:
            return []
        if requested_document_ids:
            records: list[dict[str, Any]] = []
            for document_id in requested_document_ids:
                record = self.firestore_service.get_document(document_id)
                if record is not None:
                    records.append(record)
            return records

        records = [
            record
            for record in self.firestore_service.list_documents()
            if record.get("status") == "indexed"
        ]
        if requested_product_type:
            records = [record for record in records if record.get("product_type") == requested_product_type]
        return records


def _serialize_result(result: RetrievalResult) -> dict[str, Any]:
    return {
        "document_id": result.chunk.document_id,
        "document_name": result.chunk.document_name,
        "document_type": result.chunk.document_type,
        "product_type": result.chunk.product_type,
        "chunk_id": result.chunk.chunk_id,
        "page": result.chunk.page,
        "end_page": result.chunk.end_page,
        "section": result.chunk.section,
        "normalized_section": result.chunk.normalized_section,
        "content": result.chunk.content,
        "embedding_score": result.embedding_score,
        "hybrid_score": result.hybrid_score or result.score,
    }


def _dominant_value(results: list[RetrievalResult], field_name: str) -> str | None:
    if not results:
        return None
    first_chunk = results[0].chunk
    return str(getattr(first_chunk, field_name))


def _confidence_signal(confidence_score: float) -> str:
    if confidence_score >= 0.75:
        return "high"
    if confidence_score >= 0.45:
        return "medium"
    return "low"


def _requires_fallback(results: list[RetrievalResult], search_profile: SearchProfile) -> tuple[bool, str | None]:
    if not results:
        return True, "no_results"
    top_result = results[0]
    if (top_result.hybrid_score or top_result.score) < 0.45:
        return True, "low_top_score"
    if top_result.chunk.normalized_section in search_profile.negative_sections:
        return True, "negative_section_ranked_first"
    positive_matches = sum(
        1 for result in results[:5] if result.chunk.normalized_section in search_profile.positive_sections
    )
    negative_matches = sum(
        1 for result in results[:5] if result.chunk.normalized_section in search_profile.negative_sections
    )
    if positive_matches == 0:
        return True, "no_positive_section_match"
    if negative_matches > positive_matches:
        return True, "negative_sections_outnumber_positive"
    return False, None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _merge_results(result_sets: list[list[RetrievalResult]], *, top_k: int) -> list[RetrievalResult]:
    merged: list[RetrievalResult] = []
    seen: set[tuple[str, str]] = set()
    for results in result_sets:
        for result in results:
            key = (result.chunk.document_id, result.chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            merged.append(result)
    merged.sort(key=lambda item: item.hybrid_score or item.score, reverse=True)
    return merged[:top_k]
