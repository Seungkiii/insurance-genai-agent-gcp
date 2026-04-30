const SESSION_STATE_STORAGE_KEY = "insurance-genai-demo-session-state";
const demoStateUtils = window.DemoStateUtils || {};
const normalizeSelectedDocumentIds =
  demoStateUtils.normalizeSelectedDocumentIds || ((input) => (Array.isArray(input) ? input : []));
const buildChatPayload = demoStateUtils.buildChatPayload || ((question, sessionState) => ({ question, ...sessionState }));
const resolveDocumentSelectionState =
  demoStateUtils.resolveDocumentSelectionState ||
  ((availableDocuments, sessionState) => ({
    searchScope: sessionState?.searchScope === "all" ? "all" : "selected",
    selectedDocumentIds: normalizeSelectedDocumentIds(sessionState?.selectedDocumentIds),
    autoSelected: false,
  }));

const chatMessagesElement = document.getElementById("chatMessages");
const sessionIdLabel = document.getElementById("sessionIdLabel");
const topKInput = document.getElementById("topKInput");
const topKPerDocumentInput = document.getElementById("topKPerDocumentInput");
const documentCountLabel = document.getElementById("documentCountLabel");
const selectedProductsLabel = document.getElementById("selectedProductsLabel");
const selectedDocumentIdsPreview = document.getElementById("selectedDocumentIdsPreview");
const productList = document.getElementById("productList");
const searchAllToggle = document.getElementById("searchAllToggle");
const questionInput = document.getElementById("questionInput");
const sendButton = document.getElementById("sendButton");
const newChatButton = document.getElementById("newChatButton");
const settingsToggleButton = document.getElementById("settingsToggleButton");
const settingsPanel = document.getElementById("settingsPanel");
const errorBox = document.getElementById("errorBox");
const welcomeMessageTemplate = document.getElementById("welcomeMessageTemplate");
const debugPanel = document.getElementById("debugPanel");

const state = {
  sessionId: "",
  searchScope: "all",
  selectedDocumentIds: [],
  selectedProducts: [],
  availableDocuments: [],
  chatMessages: [],
  lastResolvedDocumentIds: [],
  lastResolvedDocumentNames: [],
  lastCitationsCount: 0,
  lastDebugInfo: null,
  isSubmitting: false,
  typingIndicatorRow: null,
};

initialize();

async function initialize() {
  restoreSessionState();
  updateSessionLabel();
  attachEventListeners();
  await Promise.all([loadAvailableDocuments(), loadSessionDocumentSelection(), loadSessionMessages()]);
  const selectionChanged = applyResolvedDocumentSelection();
  reconcileSelectedProducts();
  renderProductList();
  updateDocumentSelectionUI();
  if (selectionChanged) {
    await persistSessionDocumentSelection();
  }
  autoResizeTextarea();
}

function restoreSessionState() {
  const stored = readStoredSessionState();
  state.sessionId = stored.session_id || createSessionId();
  state.selectedDocumentIds = normalizeSelectedDocumentIds(stored.selectedDocumentIds);
  state.searchScope = stored.searchScope === "selected" ? "selected" : "all";
  persistSessionState();
}

function readStoredSessionState() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_STATE_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function persistSessionState() {
  localStorage.setItem(
    SESSION_STATE_STORAGE_KEY,
    JSON.stringify({
      session_id: state.sessionId,
      selectedDocumentIds: state.selectedDocumentIds,
      searchScope: state.searchScope,
    }),
  );
}

function attachEventListeners() {
  sendButton.addEventListener("click", submitQuestion);
  newChatButton.addEventListener("click", startNewChat);
  settingsToggleButton.addEventListener("click", toggleSettingsPanel);
  searchAllToggle.addEventListener("change", async () => {
    state.searchScope = searchAllToggle.checked ? "all" : "selected";
    persistSessionState();
    updateDocumentSelectionUI();
    renderProductList();
    await persistSessionDocumentSelection();
  });
  questionInput.addEventListener("input", () => {
    hideError();
    autoResizeTextarea();
  });
  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitQuestion();
    }
  });

  document.querySelectorAll(".demo-question-button").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.question || "";
      autoResizeTextarea();
      questionInput.focus();
    });
  });
}

async function loadAvailableDocuments() {
  try {
    const response = await fetch("/api/v1/documents");
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }
    const payload = await response.json();
    state.availableDocuments = Array.isArray(payload.documents) ? payload.documents : [];
  } catch {
    state.availableDocuments = [];
    productList.innerHTML = '<div class="document-id-preview">문서 목록을 불러오지 못했습니다.</div>';
  }
}

async function loadSessionDocumentSelection() {
  try {
    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(state.sessionId)}/documents`);
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }

    const payload = await response.json();
    const sessionDocumentIds = normalizeSelectedDocumentIds(payload.selected_document_ids);
    if (sessionDocumentIds.length || payload.search_scope === "selected") {
      state.selectedDocumentIds = sessionDocumentIds;
    }
    state.searchScope = payload.search_scope === "selected" ? "selected" : "all";
    persistSessionState();
  } catch {
    persistSessionState();
  }
}

async function loadSessionMessages() {
  renderWelcomeIfEmpty();
  hideError();

  try {
    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(state.sessionId)}/messages`);
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }

    const payload = await response.json();
    state.chatMessages = Array.isArray(payload.messages) ? payload.messages : [];
    renderMessageHistory();
  } catch (error) {
    showError(error instanceof Error ? error.message : "대화 이력을 불러오지 못했습니다.");
  }
}

function renderMessageHistory() {
  chatMessagesElement.innerHTML = "";

  if (!state.chatMessages.length) {
    renderWelcomeIfEmpty();
    return;
  }

  state.chatMessages.forEach((message) => renderMessage(message));
  scrollToLatest();
}

function renderWelcomeIfEmpty() {
  if (chatMessagesElement.children.length > 0) {
    return;
  }
  chatMessagesElement.innerHTML = "";
  chatMessagesElement.appendChild(welcomeMessageTemplate.content.cloneNode(true));
}

function reconcileSelectedProducts() {
  state.selectedDocumentIds = normalizeSelectedDocumentIds(state.selectedDocumentIds);
  state.selectedProducts = mergeSelectedProducts(state.availableDocuments, state.selectedDocumentIds);
  persistSessionState();
}

function applyResolvedDocumentSelection() {
  const previousScope = state.searchScope;
  const previousIds = JSON.stringify(state.selectedDocumentIds);
  const resolved = resolveDocumentSelectionState(state.availableDocuments, {
    searchScope: state.searchScope,
    selectedDocumentIds: state.selectedDocumentIds,
  });
  state.searchScope = resolved.searchScope;
  state.selectedDocumentIds = normalizeSelectedDocumentIds(resolved.selectedDocumentIds);
  persistSessionState();
  return previousScope !== state.searchScope || previousIds !== JSON.stringify(state.selectedDocumentIds);
}

function renderProductList() {
  if (!state.availableDocuments.length) {
    productList.innerHTML = '<div class="document-id-preview">표시할 indexed 문서가 없습니다.</div>';
    return;
  }

  productList.innerHTML = state.availableDocuments
    .map((document) => {
      const checked = state.selectedDocumentIds.includes(document.document_id);
      const disabled = state.searchScope === "all" ? "disabled" : "";
      return `
        <label class="product-option ${disabled}">
          <input
            type="checkbox"
            data-document-id="${escapeHtml(document.document_id)}"
            ${checked ? "checked" : ""}
            ${state.searchScope === "all" ? "disabled" : ""}
          />
          <span>
            <strong>${escapeHtml(getProductDisplayName(document))}</strong>
            <span class="product-option-meta">
              ${escapeHtml(document.product_type || "-")} · ${escapeHtml(document.document_type || "-")} · ${escapeHtml(document.status || "-")}
            </span>
          </span>
        </label>
      `;
    })
    .join("");

  productList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", async (event) => {
      const target = event.currentTarget;
      const documentId = target.dataset.documentId;
      if (!documentId) {
        return;
      }

      const nextSelection = target.checked
        ? [...state.selectedDocumentIds, documentId]
        : state.selectedDocumentIds.filter((value) => value !== documentId);
      state.selectedDocumentIds = normalizeSelectedDocumentIds(nextSelection);
      state.searchScope = state.selectedDocumentIds.length ? "selected" : "all";
      state.selectedProducts = mergeSelectedProducts(state.availableDocuments, state.selectedDocumentIds);
      persistSessionState();
      renderProductList();
      updateDocumentSelectionUI();
      await persistSessionDocumentSelection();
    });
  });
}

async function persistSessionDocumentSelection() {
  try {
    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(state.sessionId)}/documents`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_document_ids: state.selectedDocumentIds,
        search_scope: state.searchScope,
      }),
    });
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }
  } catch (error) {
    console.warn("Failed to persist session document selection.", error);
  }
}

async function submitQuestion() {
  if (state.isSubmitting) {
    return;
  }

  const question = questionInput.value.trim();
  if (!question) {
    showError("질문을 입력해 주세요.");
    return;
  }

  hideError();
  removeTypingIndicator();

  if (isWelcomeState()) {
    chatMessagesElement.innerHTML = "";
  }

  const userMessage = {
    message_id: `local-user-${Date.now()}`,
    role: "user",
    content: question,
    created_at: new Date().toISOString(),
  };
  state.chatMessages.push(userMessage);
  renderMessage(userMessage);

  questionInput.value = "";
  autoResizeTextarea();
  questionInput.focus();
  showTypingIndicator();
  setSubmitting(true);

  try {
    const payload = buildChatPayload(question, {
      sessionId: state.sessionId,
      searchScope: state.searchScope,
      selectedDocumentIds: state.selectedDocumentIds,
      topK: Number(topKInput.value || 5),
      topKPerDocument: Number(topKPerDocumentInput.value || 3),
    });

    const response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }

    const data = await response.json();
    const assistantMessage = normalizeAssistantMessage(data);
    state.lastResolvedDocumentIds = assistantMessage.resolved_document_ids;
    state.lastResolvedDocumentNames = assistantMessage.resolved_document_names;
    state.lastCitationsCount = assistantMessage.citations.length;
    state.lastDebugInfo = assistantMessage.debug_info || null;
    removeTypingIndicator();
    state.chatMessages.push(assistantMessage);
    renderMessage(assistantMessage);
    updateDebugPanel();
    scrollToLatest();
  } catch (error) {
    removeTypingIndicator();
    renderErrorBubble(error instanceof Error ? error.message : "응답을 불러오지 못했습니다.");
    showError(error instanceof Error ? error.message : "응답을 불러오지 못했습니다.");
  } finally {
    setSubmitting(false);
  }
}

function normalizeAssistantMessage(data) {
  const recommendedDesign = data.recommended_design
    ? {
        ...data.recommended_design,
        recommended_products: Array.isArray(data.recommended_products) ? data.recommended_products : [],
      }
    : null;
  const resolvedDocumentIds = normalizeSelectedDocumentIds(data.resolved_document_ids);
  const resolvedDocumentNames = getUniqueStrings(data.resolved_document_names);

  return {
    message_id: `assistant-${Date.now()}`,
    role: "assistant",
    content: data.answer || "",
    created_at: new Date().toISOString(),
    intent: data.intent ?? null,
    search_profile: data.search_profile ?? null,
    search_scope: data.search_scope ?? null,
    search_scope_label: data.search_scope_label ?? null,
    selected_product_names: getUniqueDisplayProducts(state.selectedProducts).map((product) => getProductDisplayName(product)),
    selected_document_ids: [...state.selectedDocumentIds],
    resolved_document_ids: resolvedDocumentIds,
    resolved_document_count: Number(data.resolved_document_count || resolvedDocumentIds.length || 0),
    resolved_document_names: resolvedDocumentNames.length
      ? resolvedDocumentNames
      : mergeSelectedProducts(state.availableDocuments, resolvedDocumentIds).map((product) => getProductDisplayName(product)),
    confidence_score: typeof data.confidence_score === "number" ? data.confidence_score : null,
    fallback_required: data.fallback_required ?? null,
    citations: Array.isArray(data.citations) ? data.citations : [],
    response_citations: Array.isArray(data.citations) ? data.citations : [],
    tool_trace: Array.isArray(data.tool_trace) ? data.tool_trace : [],
    recommended_design: recommendedDesign,
    current_design: data.current_design ?? null,
    debug_info: data.debug_info ?? null,
  };
}

function renderMessage(message) {
  const row = document.createElement("div");
  row.className = `message-row ${escapeClassName(message.role || "assistant")}`;

  const bubble = document.createElement("article");
  bubble.className = "chat-bubble";
  bubble.innerHTML = `
    <div class="message-meta">
      <span class="message-role">${escapeHtml(resolveRoleLabel(message.role))}</span>
      <time class="message-time">${escapeHtml(formatMessageTime(message.created_at))}</time>
    </div>
    <div class="message-content">${renderRichText(message.content || "")}</div>
  `;

  if (message.role === "assistant") {
    bubble.appendChild(renderAssistantDetails(message));
  }

  row.appendChild(bubble);
  chatMessagesElement.appendChild(row);
  scrollToLatest();
}

function renderAssistantDetails(message) {
  const wrapper = document.createElement("div");

  const badges = buildMetaBadges(message);
  if (badges.length) {
    const badgeContainer = document.createElement("div");
    badgeContainer.className = "meta-badges";
    badgeContainer.innerHTML = badges.join("");
    wrapper.appendChild(badgeContainer);
  }

  const detailSections = [
    createDetailSection(
      "현재 선택 상품",
      getUniqueDisplayProducts(state.selectedProducts).length,
      renderSelectedProducts(state.selectedProducts),
    ),
    createDetailSection(
      "이번 답변 근거 문서",
      getUniqueCitationDocumentNames(message.response_citations || []).length,
      renderCitationDocumentSummary(message.response_citations || []),
    ),
    createDetailSection("근거 보기", Array.isArray(message.citations) ? message.citations.length : 0, renderCitations(message.citations || [])),
    createDetailSection(
      "Agent 동작 보기",
      Array.isArray(message.tool_trace) ? message.tool_trace.length : 0,
      renderToolTrace(message.tool_trace || []),
    ),
  ];

  if (message.recommended_design) {
    detailSections.push(createDetailSection("추천 설계 보기", null, renderRecommendedDesign(message.recommended_design)));
  }

  if (message.current_design) {
    detailSections.push(createDetailSection("현재 설계 상태", null, renderCurrentDesign(message.current_design)));
  }

  const detailsGroup = document.createElement("div");
  detailsGroup.className = "details-group";
  detailSections.forEach((section) => detailsGroup.appendChild(section));
  wrapper.appendChild(detailsGroup);
  return wrapper;
}

function renderSelectedProducts(products) {
  const uniqueProducts = getUniqueDisplayProducts(products);
  if (!uniqueProducts.length) {
    return '<div class="citation-card">선택된 상품이 없습니다.</div>';
  }

  return uniqueProducts
    .map(
      (product) => `
        <article class="citation-card">
          <h4>${escapeHtml(getProductDisplayName(product))}</h4>
          <div class="mini-grid">
            <div><strong>document_id</strong>${escapeHtml(product.document_id || "-")}</div>
            <div><strong>product_type</strong>${escapeHtml(product.product_type || "-")}</div>
            <div><strong>document_type</strong>${escapeHtml(product.document_type || "-")}</div>
            <div><strong>file_name</strong>${escapeHtml(product.file_name || "-")}</div>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderCitationDocumentSummary(citations) {
  const names = getUniqueCitationDocumentNames(citations);
  if (!names.length) {
    return '<div class="citation-card">이번 답변에서 참조한 문서가 없습니다.</div>';
  }

  return names
    .map(
      (name) => `
        <article class="citation-card">
          <h4>${escapeHtml(name)}</h4>
        </article>
      `,
    )
    .join("");
}

function createDetailSection(title, count, contentHtml) {
  const section = document.createElement("section");
  section.className = "detail-section";
  section.innerHTML = `
    <button class="detail-toggle" type="button" aria-expanded="false">
      <span>${escapeHtml(title)}</span>
      <small>${count !== null ? `${count}개` : "보기"}</small>
    </button>
    <div class="detail-panel">${contentHtml}</div>
  `;

  const toggle = section.querySelector(".detail-toggle");
  toggle.addEventListener("click", () => {
    const expanded = section.classList.toggle("expanded");
    toggle.setAttribute("aria-expanded", String(expanded));
  });
  return section;
}

function renderCitations(citations) {
  if (!citations.length) {
    return '<div class="citation-card">표시할 근거가 없습니다.</div>';
  }

  return citations
    .map((citation) => {
      const pageLabel = citation.end_page && citation.end_page !== citation.page
        ? `${citation.page}~${citation.end_page}`
        : `${citation.page ?? "-"}`;
      const score = citation.hybrid_score ?? citation.score ?? "-";
      return `
        <article class="citation-card">
          <h4>${escapeHtml(citation.document_name || "Unknown document")}</h4>
          <div class="mini-grid">
            <div><strong>Page</strong>${escapeHtml(pageLabel)}</div>
            <div><strong>Section</strong>${escapeHtml(citation.section || "-")}</div>
            <div><strong>Normalized</strong>${escapeHtml(citation.normalized_section || "-")}</div>
            <div><strong>Doc Type</strong>${escapeHtml(citation.document_type || "-")}</div>
            <div><strong>Product Type</strong>${escapeHtml(citation.product_type || "-")}</div>
            <div><strong>Score</strong>${escapeHtml(String(score))}</div>
          </div>
          <div class="content-preview">${escapeHtml(citation.content_preview || "-")}</div>
        </article>
      `;
    })
    .join("");
}

function renderToolTrace(toolTrace) {
  if (!toolTrace.length) {
    return '<div class="tool-trace-card">표시할 Agent 동작 내역이 없습니다.</div>';
  }

  return `
    <div class="trace-timeline">
      ${toolTrace
        .map(
          (item, index) => `
            <article class="tool-trace-card">
              <h4><span class="trace-index">${escapeHtml(String(item.step ?? index + 1))}</span> ${escapeHtml(item.tool_name || "tool")}</h4>
              <div class="mini-grid">
                <div><strong>Status</strong>${escapeHtml(item.status || "-")}</div>
                <div><strong>Latency</strong>${escapeHtml(String(item.latency_ms ?? 0))}ms</div>
              </div>
              <div class="trace-summary">Input: ${escapeHtml(formatJsonLike(item.input_summary))}

Output: ${escapeHtml(formatJsonLike(item.output_summary))}
${item.error ? `\nError: ${escapeHtml(String(item.error))}` : ""}</div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderRecommendedDesign(recommendedDesign) {
  const products = Array.isArray(recommendedDesign.recommended_products)
    ? recommendedDesign.recommended_products
    : [];
  const recommendedProductsHtml = products.length
    ? products
        .map(
          (product) => `
            <article class="design-card">
              <h4>${escapeHtml(product.product_name || product.document_name || "추천 상품")}</h4>
              <div class="mini-grid">
                <div><strong>상품 유형</strong>${escapeHtml(product.product_type || "-")}</div>
                <div><strong>추천 이유</strong>${escapeHtml(product.recommendation_reason || product.reason || "-")}</div>
                <div><strong>주요 근거</strong>${escapeHtml(joinValue(product.main_evidence || product.citations || []))}</div>
                <div><strong>유의사항</strong>${escapeHtml(joinValue(product.caution_notes || product.cautions || []))}</div>
                <div><strong>Ranking Reason</strong>${escapeHtml(product.ranking_reason || "-")}</div>
              </div>
            </article>
          `,
        )
        .join("")
    : "";

  return `
    <article class="design-card">
      <h4>추천 설계 요약</h4>
      <div class="mini-grid">
        <div><strong>customer_profile</strong>${escapeHtml(formatJsonLike(recommendedDesign.customer_profile || {}))}</div>
        <div><strong>product_type</strong>${escapeHtml(recommendedDesign.product_type || recommendedDesign.product_group || "-")}</div>
        <div><strong>main_focus</strong>${escapeHtml(recommendedDesign.main_focus || "-")}</div>
        <div><strong>focus_areas</strong>${escapeHtml(joinValue(recommendedDesign.focus_areas || []))}</div>
        <div><strong>recommended_explanation_points</strong>${escapeHtml(joinValue(recommendedDesign.recommended_explanation_points || []))}</div>
        <div><strong>caution_notes</strong>${escapeHtml(joinValue(recommendedDesign.caution_notes || []))}</div>
      </div>
      <div class="design-list">${escapeHtml(joinValue(recommendedDesign.evidence_summary || []))}</div>
    </article>
    ${recommendedProductsHtml}
  `;
}

function renderCurrentDesign(currentDesign) {
  return `
    <article class="design-card">
      <h4>현재 설계 상태</h4>
      <div class="mini-grid">
        <div><strong>session_id</strong>${escapeHtml(currentDesign.session_id || state.sessionId)}</div>
        <div><strong>selected_product</strong>${escapeHtml(joinValue(currentDesign.selected_product_names || currentDesign.selected_document_ids || []))}</div>
        <div><strong>customer_profile</strong>${escapeHtml(formatJsonLike(currentDesign.customer_profile || {}))}</div>
        <div><strong>focus_areas</strong>${escapeHtml(joinValue(currentDesign.focus_areas || []))}</div>
        <div><strong>keep_coverages</strong>${escapeHtml(joinValue(currentDesign.keep_coverages || []))}</div>
        <div><strong>add_coverages</strong>${escapeHtml(joinValue(currentDesign.add_coverages || []))}</div>
        <div><strong>remove_coverages</strong>${escapeHtml(joinValue(currentDesign.remove_coverages || []))}</div>
        <div><strong>caution_notes</strong>${escapeHtml(joinValue(currentDesign.caution_notes || []))}</div>
        <div><strong>updated_at</strong>${escapeHtml(formatMessageTime(currentDesign.updated_at || ""))}</div>
      </div>
    </article>
  `;
}

function renderErrorBubble(message) {
  const row = document.createElement("div");
  row.className = "message-row error";
  row.innerHTML = `
    <article class="chat-bubble">
      <div class="message-meta">
        <span class="message-role">System</span>
        <time class="message-time">${escapeHtml(formatMessageTime(new Date().toISOString()))}</time>
      </div>
      <div class="message-content"><p>${escapeHtml(message)}</p></div>
    </article>
  `;
  chatMessagesElement.appendChild(row);
  scrollToLatest();
}

function showTypingIndicator() {
  removeTypingIndicator();

  state.typingIndicatorRow = document.createElement("div");
  state.typingIndicatorRow.className = "message-row assistant";
  state.typingIndicatorRow.innerHTML = `
    <article class="chat-bubble">
      <div class="message-meta">
        <span class="message-role">Assistant</span>
        <time class="message-time">${escapeHtml(formatMessageTime(new Date().toISOString()))}</time>
      </div>
      <div class="typing-indicator">
        <span>답변 생성 중...</span>
        <span class="typing-dots"><span></span><span></span><span></span></span>
      </div>
    </article>
  `;
  chatMessagesElement.appendChild(state.typingIndicatorRow);
  scrollToLatest();
}

function removeTypingIndicator() {
  if (state.typingIndicatorRow) {
    state.typingIndicatorRow.remove();
    state.typingIndicatorRow = null;
  }
}

function startNewChat() {
  state.sessionId = createSessionId();
  state.searchScope = "all";
  state.selectedDocumentIds = [];
  state.selectedProducts = [];
  state.chatMessages = [];
  state.lastResolvedDocumentIds = [];
  state.lastResolvedDocumentNames = [];
  state.lastCitationsCount = 0;
  state.lastDebugInfo = null;
  persistSessionState();
  updateSessionLabel();
  hideError();
  removeTypingIndicator();
  chatMessagesElement.innerHTML = "";
  renderWelcomeIfEmpty();
  questionInput.value = "";
  autoResizeTextarea();
  applyResolvedDocumentSelection();
  renderProductList();
  updateDocumentSelectionUI();
}

function toggleSettingsPanel() {
  const hidden = settingsPanel.classList.toggle("hidden");
  settingsToggleButton.setAttribute("aria-expanded", String(!hidden));
}

function updateSessionLabel() {
  sessionIdLabel.textContent = state.sessionId;
}

function updateDocumentSelectionUI() {
  reconcileSelectedProducts();
  searchAllToggle.checked = state.searchScope === "all";
  documentCountLabel.textContent = String(state.selectedDocumentIds.length);
  selectedProductsLabel.textContent = buildSelectionSummary();
  selectedDocumentIdsPreview.textContent = state.selectedDocumentIds.length
    ? state.selectedDocumentIds.join(", ")
    : "선택된 document_id가 없습니다.";
  updateDebugPanel();
}

function updateDebugPanel() {
  debugPanel.textContent = [
    `session_id: ${state.sessionId}`,
    `searchScope: ${state.searchScope}`,
    `selectedDocumentIds: ${JSON.stringify(state.selectedDocumentIds)}`,
    `resolvedDocumentIds: ${JSON.stringify(state.lastResolvedDocumentIds)}`,
    `resolvedDocumentNames: ${JSON.stringify(state.lastResolvedDocumentNames)}`,
    `selectedProducts count: ${state.selectedProducts.length}`,
    `lastResponse citations count: ${state.lastCitationsCount}`,
    state.lastDebugInfo ? `debug_info: ${formatJsonLike(state.lastDebugInfo)}` : "debug_info: -",
  ].join("\n");
}

function buildSelectionSummary() {
  if (state.searchScope === "all") {
    return "전체 상품에서 검색 중";
  }
  const names = getUniqueDisplayProducts(state.selectedProducts).map((product) => getProductDisplayName(product));
  if (!names.length) {
    return "선택된 상품이 없으면 전체 indexed 문서에서 자동 검색합니다.";
  }
  return names.join(", ");
}

function setSubmitting(submitting) {
  state.isSubmitting = submitting;
  sendButton.disabled = submitting || !questionInput.value.trim();
  questionInput.disabled = submitting;
}

function createSessionId() {
  return `demo-session-${Date.now()}`;
}

function scrollToLatest() {
  chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight;
}

function autoResizeTextarea() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 200)}px`;
  sendButton.disabled = state.isSubmitting || !questionInput.value.trim();
}

function buildMetaBadges(message) {
  const badges = [];
  if (message.intent) {
    badges.push(renderBadge("intent", message.intent));
  }
  if (message.search_profile) {
    badges.push(renderBadge("search_profile", message.search_profile));
  }
  if (message.search_scope_label) {
    badges.push(renderBadge("검색 범위", message.search_scope_label));
  }
  if (message.resolved_document_names?.length) {
    badges.push(renderBadge("이번 검색 상품", message.resolved_document_names.join(", ")));
  }
  if (message.confidence_score !== null && message.confidence_score !== undefined) {
    badges.push(renderBadge("confidence", Number(message.confidence_score).toFixed(2)));
  }
  if (message.fallback_required !== null && message.fallback_required !== undefined) {
    badges.push(renderBadge("fallback", String(message.fallback_required)));
  }
  return badges;
}

function renderBadge(label, value) {
  return `<span class="badge"><strong>${escapeHtml(label)}</strong>${escapeHtml(String(value))}</span>`;
}

function renderRichText(text) {
  const lines = String(text || "").split("\n");
  let html = "";
  let inList = false;

  lines.forEach((rawLine) => {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      return;
    }

    if (line.startsWith("### ")) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<h3>${escapeHtml(line.slice(4))}</h3>`;
      return;
    }
    if (line.startsWith("## ")) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<h2>${escapeHtml(line.slice(3))}</h2>`;
      return;
    }
    if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${escapeHtml(line.slice(2))}</li>`;
      return;
    }

    if (inList) {
      html += "</ul>";
      inList = false;
    }
    html += `<p>${escapeHtml(line)}</p>`;
  });

  if (inList) {
    html += "</ul>";
  }

  return html || "<p>-</p>";
}

function resolveRoleLabel(role) {
  if (role === "user") {
    return "You";
  }
  if (role === "assistant") {
    return "Assistant";
  }
  return "System";
}

function formatMessageTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function joinValue(value) {
  if (Array.isArray(value)) {
    return value.join(", ") || "-";
  }
  if (value && typeof value === "object") {
    return formatJsonLike(value);
  }
  return String(value || "-");
}

function formatJsonLike(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function safeReadError(response) {
  try {
    const payload = await response.json();
    return payload.detail || JSON.stringify(payload);
  } catch {
    return (await response.text()) || "요청 처리 중 오류가 발생했습니다.";
  }
}

function isWelcomeState() {
  return chatMessagesElement.querySelector(".system-card") !== null && chatMessagesElement.children.length === 1;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

function mergeSelectedProducts(documents, selectedDocumentIds) {
  const selectedIds = normalizeSelectedDocumentIds(selectedDocumentIds);
  return selectedIds
    .map((documentId) => documents.find((document) => document.document_id === documentId))
    .filter(Boolean);
}

function getUniqueDisplayProducts(products) {
  const unique = [];
  const seen = new Set();
  for (const product of products || []) {
    const documentId = String(product.document_id || "").trim();
    if (!documentId || seen.has(documentId)) {
      continue;
    }
    seen.add(documentId);
    unique.push(product);
  }
  return unique;
}

function getUniqueCitationDocumentNames(citations) {
  return getUniqueStrings(
    (Array.isArray(citations) ? citations : []).map((citation) => citation.document_name),
  );
}

function getUniqueStrings(values) {
  const unique = [];
  for (const value of Array.isArray(values) ? values : []) {
    const normalized = String(value || "").trim();
    if (!normalized || unique.includes(normalized)) {
      continue;
    }
    unique.push(normalized);
  }
  return unique;
}

function getProductDisplayName(product) {
  return product.product_name || product.document_name || product.file_name || product.document_id;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeClassName(value) {
  return String(value).replace(/[^a-z0-9_-]/gi, "") || "assistant";
}
