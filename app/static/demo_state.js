(function (globalScope, factory) {
  const api = factory();
  globalScope.DemoStateUtils = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const UUID_PATTERN =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  function normalizeSelectedDocumentIds(input) {
    if (!Array.isArray(input)) {
      return [];
    }
    const normalized = [];
    for (const item of input) {
      const value = String(item || "").trim();
      if (!value || !UUID_PATTERN.test(value)) {
        continue;
      }
      if (!normalized.includes(value)) {
        normalized.push(value);
      }
    }
    return normalized;
  }

  function resolveDocumentSelectionState(availableDocuments, sessionState) {
    const documents = Array.isArray(availableDocuments) ? availableDocuments : [];
    const indexedDocuments = documents.filter((document) => document && document.status === "indexed");
    const indexedDocumentIds = indexedDocuments
      .map((document) => String(document.document_id || "").trim())
      .filter((documentId) => UUID_PATTERN.test(documentId));
    const selectedDocumentIds = normalizeSelectedDocumentIds(sessionState?.selectedDocumentIds).filter((documentId) =>
      indexedDocumentIds.includes(documentId),
    );
    const storedSearchScope = sessionState?.searchScope === "all" ? "all" : "selected";

    if (indexedDocuments.length === 1) {
      return {
        searchScope: "selected",
        selectedDocumentIds: [indexedDocumentIds[0]],
        autoSelected: selectedDocumentIds.length === 0 || selectedDocumentIds[0] !== indexedDocumentIds[0],
      };
    }

    if (selectedDocumentIds.length > 0) {
      return {
        searchScope: "selected",
        selectedDocumentIds,
        autoSelected: false,
      };
    }

    return {
      searchScope: storedSearchScope === "all" ? "all" : "all",
      selectedDocumentIds: [],
      autoSelected: false,
    };
  }

  function buildChatPayload(question, sessionState) {
    const documentIds = normalizeSelectedDocumentIds(sessionState?.selectedDocumentIds);
    const payload = {
      question,
      session_id: sessionState?.sessionId,
      search_scope: sessionState?.searchScope === "selected" ? "selected" : "all",
      top_k: sessionState?.topK,
      top_k_per_document: sessionState?.topKPerDocument,
    };
    if (payload.search_scope === "selected" && documentIds.length) {
      payload.document_ids = documentIds;
    }
    return payload;
  }

  return {
    UUID_PATTERN,
    normalizeSelectedDocumentIds,
    resolveDocumentSelectionState,
    buildChatPayload,
  };
});
