"""Regression tests for demo document selection payload state."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_single_indexed_document_is_auto_selected() -> None:
    result = _run_node(
        """
const utils = require("./app/static/demo_state.js");
const output = utils.resolveDocumentSelectionState(
  [
    {
      document_id: "630e5103-61d3-44c3-8efe-646c6be9ec60",
      file_name: "2025041516121911948953.pdf",
      status: "indexed",
    },
  ],
  {
    searchScope: "all",
    selectedDocumentIds: [],
  },
);
process.stdout.write(JSON.stringify(output));
"""
    )

    assert result == {
      "searchScope": "selected",
      "selectedDocumentIds": ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
      "autoSelected": True,
    }


def test_build_chat_payload_includes_real_document_ids_only() -> None:
    result = _run_node(
        """
const utils = require("./app/static/demo_state.js");
const payload = utils.buildChatPayload("질문", {
  sessionId: "demo-session-1",
  searchScope: "selected",
  selectedDocumentIds: [
    "630e5103-61d3-44c3-8efe-646c6be9ec60",
    "2025041516121911948953.pdf",
    "무배당엔젤하이브리드연금보험 상품요약서",
  ],
  topK: 5,
  topKPerDocument: 3,
});
process.stdout.write(JSON.stringify(payload));
"""
    )

    assert result == {
      "question": "질문",
      "session_id": "demo-session-1",
      "search_scope": "selected",
      "document_ids": ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
      "top_k": 5,
      "top_k_per_document": 3,
    }


def test_build_chat_payload_omits_document_ids_for_all_scope() -> None:
    result = _run_node(
        """
const utils = require("./app/static/demo_state.js");
const payload = utils.buildChatPayload("질문", {
  sessionId: "demo-session-1",
  searchScope: "all",
  selectedDocumentIds: ["630e5103-61d3-44c3-8efe-646c6be9ec60"],
  topK: 5,
  topKPerDocument: 3,
});
process.stdout.write(JSON.stringify(payload));
"""
    )

    assert result == {
      "question": "질문",
      "session_id": "demo-session-1",
      "search_scope": "all",
      "top_k": 5,
      "top_k_per_document": 3,
    }
