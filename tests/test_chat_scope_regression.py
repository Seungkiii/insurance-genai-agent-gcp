"""Regression tests for chat document scope persistence."""

from __future__ import annotations

from tests.test_chat_api import create_test_client


def test_session_selected_documents_are_resolved_without_request_document_ids() -> None:
    client, firestore_service, policy_tool, _, _ = create_test_client(
        policy_output={
            "search_profile": "coverage_summary",
            "product_type": "annuity",
            "document_type": "product_summary",
            "normalized_section": ["coverage"],
            "candidate_document_count": 1,
            "candidate_document_ids": ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
            "embedding_record_count": 3,
            "selected_result_count": 1,
            "chunks": [
                {
                    "document_id": "630e5103-61d3-44c3-8efe-646c6be9ec60",
                    "document_name": "2025041516121911948953.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "page": 4,
                    "section": "상품 개요",
                    "normalized_section": "product_overview",
                    "content": "이 상품의 주요 보장 구조를 설명합니다.",
                }
            ],
            "citations": [
                {
                    "document_name": "2025041516121911948953.pdf",
                    "page": 4,
                    "section": "상품 개요",
                    "normalized_section": "product_overview",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "content_preview": "이 상품의 주요 보장 구조를 설명합니다.",
                    "score": 0.88,
                }
            ],
            "confidence_score": 0.88,
            "fallback_required": False,
            "fallback_reason": None,
        }
    )
    firestore_service.documents = {
        "630e5103-61d3-44c3-8efe-646c6be9ec60": {
            "document_id": "630e5103-61d3-44c3-8efe-646c6be9ec60",
            "file_name": "2025041516121911948953.pdf",
            "document_name": "2025041516121911948953.pdf",
            "product_name": "무배당엔젤하이브리드연금보험 상품요약서",
            "status": "indexed",
            "product_type": "annuity",
            "document_type": "product_summary",
        }
    }
    firestore_service.update_session_context(
        "session-regression-1",
        selected_document_ids=["630e5103-61d3-44c3-8efe-646c6be9ec60"],
        selected_product_names=["무배당엔젤하이브리드연금보험 상품요약서"],
        search_scope="selected",
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "이 상품의 주요 보장 내용은 뭐야?", "session_id": "session-regression-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolved_document_ids"] == ["630e5103-61d3-44c3-8efe-646c6be9ec60"]
    assert policy_tool.calls[0]["document_ids"] == ["630e5103-61d3-44c3-8efe-646c6be9ec60"]
    assert payload["tool_trace"][0]["input_summary"]["resolved_document_ids"] == [
        "630e5103-61d3-44c3-8efe-646c6be9ec60"
    ]


def test_same_session_keeps_resolved_documents_and_citations_across_repeated_questions() -> None:
    client, firestore_service, _, _, _ = create_test_client(
        policy_output={
            "search_profile": "pension_payment",
            "product_type": "annuity",
            "document_type": "product_summary",
            "normalized_section": ["annuity_payment"],
            "candidate_document_count": 1,
            "candidate_document_ids": ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
            "embedding_record_count": 4,
            "selected_result_count": 1,
            "chunks": [
                {
                    "document_id": "630e5103-61d3-44c3-8efe-646c6be9ec60",
                    "document_name": "2025041516121911948953.pdf",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "content": "연금개시 후에는 생존연금 중심으로 지급합니다.",
                }
            ],
            "citations": [
                {
                    "document_name": "2025041516121911948953.pdf",
                    "page": 9,
                    "section": "연금지급형태",
                    "normalized_section": "annuity_payment",
                    "document_type": "product_summary",
                    "product_type": "annuity",
                    "content_preview": "연금개시 후에는 생존연금 중심으로 지급합니다.",
                    "score": 0.91,
                }
            ],
            "confidence_score": 0.91,
            "fallback_required": False,
            "fallback_reason": None,
        }
    )
    firestore_service.documents = {
        "630e5103-61d3-44c3-8efe-646c6be9ec60": {
            "document_id": "630e5103-61d3-44c3-8efe-646c6be9ec60",
            "file_name": "2025041516121911948953.pdf",
            "document_name": "2025041516121911948953.pdf",
            "product_name": "무배당엔젤하이브리드연금보험 상품요약서",
            "status": "indexed",
            "product_type": "annuity",
            "document_type": "product_summary",
        }
    }
    firestore_service.update_session_context(
        "session-regression-2",
        selected_document_ids=["630e5103-61d3-44c3-8efe-646c6be9ec60"],
        selected_product_names=["무배당엔젤하이브리드연금보험 상품요약서"],
        search_scope="selected",
    )

    questions = [
        "이 상품의 주요 보장 내용은 뭐야?",
        "연금개시 후에는 어떤 방식으로 연금을 지급해?",
        "이 상품의 주요 보장 내용은 뭐야?",
    ]
    responses = [
        client.post("/api/v1/chat", json={"question": question, "session_id": "session-regression-2"})
        for question in questions
    ]

    assert all(response.status_code == 200 for response in responses)
    payloads = [response.json() for response in responses]
    assert payloads[0]["resolved_document_ids"] == payloads[2]["resolved_document_ids"]
    assert payloads[0]["citations"]
    assert payloads[1]["citations"]
    assert payloads[2]["citations"]
    assert payloads[1]["search_profile"] == "pension_payment"
    assert payloads[0]["fallback_required"] is False
    assert payloads[2]["fallback_required"] is False
