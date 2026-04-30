const SESSION_STORAGE_KEY = "insurance-genai-demo-session-id";

const chatMessages = document.getElementById("chatMessages");
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

let currentSessionId = loadOrCreateSessionId();
let isSubmitting = false;
let typingIndicatorRow = null;
let availableDocuments = [];
let selectedDocumentIds = [];
let selectedProductNames = [];
let searchScope = "selected";

initialize();

async function initialize() {
  updateSessionLabel();
  attachEventListeners();
  await Promise.all([loadAvailableDocuments(), loadSessionDocumentSelection(), loadSessionMessages()]);
  updateDocumentSelectionUI();
  autoResizeTextarea();
}

function attachEventListeners() {
  sendButton.addEventListener("click", submitQuestion);
  newChatButton.addEventListener("click", startNewChat);
  settingsToggleButton.addEventListener("click", toggleSettingsPanel);
  searchAllToggle.addEventListener("change", async () => {
    searchScope = searchAllToggle.checked ? "all" : "selected";
    updateDocumentSelectionUI();
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
    availableDocuments = Array.isArray(payload.documents) ? payload.documents : [];
    renderProductList();
  } catch (error) {
    productList.innerHTML = '<div class="document-id-preview">문서 목록을 불러오지 못했습니다.</div>';
  }
}

async function loadSessionDocumentSelection() {
  try {
    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(currentSessionId)}/documents`);
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }
    const payload = await response.json();
    selectedDocumentIds = Array.isArray(payload.selected_document_ids) ? payload.selected_document_ids : [];
    selectedProductNames = Array.isArray(payload.selected_product_names) ? payload.selected_product_names : [];
    searchScope = payload.search_scope === "all" ? "all" : "selected";
  } catch {
    selectedDocumentIds = [];
    selectedProductNames = [];
    searchScope = "selected";
  }
}

async function loadSessionMessages() {
  renderWelcomeIfEmpty();
  hideError();

  try {
    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(currentSessionId)}/messages`);
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }

    const payload = await response.json();
    renderMessageHistory(payload.messages || []);
  } catch (error) {
    showError(error instanceof Error ? error.message : "대화 이력을 불러오지 못했습니다.");
  }
}

function renderMessageHistory(messages) {
  chatMessages.innerHTML = "";

  if (!messages.length) {
    renderWelcomeIfEmpty();
    return;
  }

  messages.forEach((message) => renderMessage(message));
  scrollToLatest();
}

function renderWelcomeIfEmpty() {
  if (chatMessages.children.length > 0) {
    return;
  }

  chatMessages.innerHTML = "";
  const welcomeNode = welcomeMessageTemplate.content.cloneNode(true);
  chatMessages.appendChild(welcomeNode);
}

async function submitQuestion() {
  if (isSubmitting) {
    return;
  }

  const question = questionInput.value.trim();
  if (!question) {
    showError("질문을 입력해 주세요.");
    return;
  }

  hideError();
  removeTypingIndicator();

  const userMessage = {
    message_id: `local-user-${Date.now()}`,
    role: "user",
    content: question,
    created_at: new Date().toISOString(),
  };

  if (isWelcomeState()) {
    chatMessages.innerHTML = "";
  }

  renderMessage(userMessage);
  questionInput.value = "";
  autoResizeTextarea();
  questionInput.focus();
  showTypingIndicator();
  setSubmitting(true);

  try {
    const payload = {
      session_id: currentSessionId,
      question,
      top_k: Number(topKInput.value || 5),
      top_k_per_document: Number(topKPerDocumentInput.value || 3),
    };
    if (searchScope !== "all" && selectedDocumentIds.length) {
      payload.document_ids = selectedDocumentIds;
    }

    const response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }

    const data = await response.json();
    syncSelectionFromAssistant(data);
    removeTypingIndicator();
    renderMessage(normalizeAssistantMessage(data));
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

  return {
    message_id: `assistant-${Date.now()}`,
    role: "assistant",
    content: data.answer || "",
    created_at: new Date().toISOString(),
    intent: data.intent ?? null,
    search_profile: data.search_profile ?? null,
    search_scope: data.search_scope ?? null,
    search_scope_label: data.search_scope_label ?? null,
    selected_product_names: Array.isArray(data.selected_product_names) ? data.selected_product_names : [],
    selected_document_ids: Array.isArray(data.selected_document_ids) ? data.selected_document_ids : [],
    confidence_score: typeof data.confidence_score === "number" ? data.confidence_score : null,
    fallback_required: data.fallback_required ?? null,
    citations: Array.isArray(data.citations) ? data.citations : [],
    tool_trace: Array.isArray(data.tool_trace) ? data.tool_trace : [],
    recommended_design: recommendedDesign,
    current_design: data.current_design ?? null,
  };
}

function syncSelectionFromAssistant(data) {
  if (Array.isArray(data.selected_document_ids)) {
    selectedDocumentIds = data.selected_document_ids;
  }
  if (Array.isArray(data.selected_product_names)) {
    selectedProductNames = data.selected_product_names;
  }
  if (data.search_scope === "all" || data.search_scope === "selected") {
    searchScope = data.search_scope;
  }
  renderProductList();
  updateDocumentSelectionUI();
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
  chatMessages.appendChild(row);
  scrollToLatest();
}

function renderProductList() {
  if (!availableDocuments.length) {
    productList.innerHTML = '<div class="document-id-preview">표시할 indexed 문서가 없습니다.</div>';
    return;
  }

  productList.innerHTML = availableDocuments
    .map((document) => {
      const checked = selectedDocumentIds.includes(document.document_id);
      const disabled = searchScope === "all" ? "disabled" : "";
      return `
        <label class="product-option ${disabled}">
          <input
            type="checkbox"
            data-document-id="${escapeHtml(document.document_id)}"
            ${checked ? "checked" : ""}
            ${searchScope === "all" ? "disabled" : ""}
          />
          <span>
            <strong>${escapeHtml(document.product_name || document.document_name || document.file_name || document.document_id)}</strong>
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

      if (target.checked) {
        if (!selectedDocumentIds.includes(documentId)) {
          selectedDocumentIds.push(documentId);
        }
      } else {
        selectedDocumentIds = selectedDocumentIds.filter((value) => value !== documentId);
      }

      selectedProductNames = selectedDocumentIds
        .map((id) => getDocumentDisplayName(id))
        .filter(Boolean);
      updateDocumentSelectionUI();
      await persistSessionDocumentSelection();
    });
  });
}

async function persistSessionDocumentSelection() {
  try {
    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(currentSessionId)}/documents`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_document_ids: selectedDocumentIds,
        search_scope: searchScope,
      }),
    });
    if (!response.ok) {
      throw new Error(await safeReadError(response));
    }
    const payload = await response.json();
    selectedDocumentIds = Array.isArray(payload.selected_document_ids) ? payload.selected_document_ids : [];
    selectedProductNames = Array.isArray(payload.selected_product_names) ? payload.selected_product_names : [];
    searchScope = payload.search_scope === "all" ? "all" : "selected";
    updateDocumentSelectionUI();
    renderProductList();
  } catch (error) {
    showError(error instanceof Error ? error.message : "세션 문서 설정을 저장하지 못했습니다.");
  }
}

function updateDocumentSelectionUI() {
  searchAllToggle.checked = searchScope === "all";
  documentCountLabel.textContent = String(selectedDocumentIds.length);
  selectedProductsLabel.textContent = buildSelectionSummary();
  selectedDocumentIdsPreview.textContent = selectedDocumentIds.length
    ? selectedDocumentIds.join(", ")
    : "선택된 document_id가 없습니다.";
}

function buildSelectionSummary() {
  if (searchScope === "all") {
    return "전체 상품에서 검색 중";
  }
  if (!selectedProductNames.length) {
    return "선택된 상품이 없으면 전체 indexed 문서에서 자동 검색합니다.";
  }
  return selectedProductNames.join(", ");
}

function getDocumentDisplayName(documentId) {
  const document = availableDocuments.find((item) => item.document_id === documentId);
  if (!document) {
    return "";
  }
  return document.product_name || document.document_name || document.file_name || document.document_id;
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

  const detailSections = [];
  detailSections.push(
    createDetailSection(
      "근거 보기",
      Array.isArray(message.citations) ? message.citations.length : 0,
      renderCitations(message.citations || []),
    ),
  );
  detailSections.push(
    createDetailSection(
      "Agent 동작 보기",
      Array.isArray(message.tool_trace) ? message.tool_trace.length : 0,
      renderToolTrace(message.tool_trace || []),
    ),
  );

  if (message.recommended_design) {
    detailSections.push(
      createDetailSection("추천 설계 보기", null, renderRecommendedDesign(message.recommended_design)),
    );
  }

  if (message.current_design) {
    detailSections.push(
      createDetailSection("현재 설계 상태", null, renderCurrentDesign(message.current_design)),
    );
  }

  if (detailSections.length) {
    const detailsGroup = document.createElement("div");
    detailsGroup.className = "details-group";
    detailSections.forEach((section) => detailsGroup.appendChild(section));
    wrapper.appendChild(detailsGroup);
  }

  return wrapper;
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
        <div><strong>session_id</strong>${escapeHtml(currentDesign.session_id || currentSessionId)}</div>
        <div><strong>selected_product</strong>${escapeHtml(currentDesign.selected_product || joinValue(currentDesign.selected_product_names || currentDesign.selected_document_ids || []))}</div>
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
  chatMessages.appendChild(row);
  scrollToLatest();
}

function showTypingIndicator() {
  removeTypingIndicator();

  typingIndicatorRow = document.createElement("div");
  typingIndicatorRow.className = "message-row assistant";
  typingIndicatorRow.innerHTML = `
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
  chatMessages.appendChild(typingIndicatorRow);
  scrollToLatest();
}

function removeTypingIndicator() {
  if (typingIndicatorRow) {
    typingIndicatorRow.remove();
    typingIndicatorRow = null;
  }
}

function startNewChat() {
  currentSessionId = createSessionId();
  localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId);
  selectedDocumentIds = [];
  selectedProductNames = [];
  searchScope = "selected";
  updateSessionLabel();
  hideError();
  removeTypingIndicator();
  chatMessages.innerHTML = "";
  renderWelcomeIfEmpty();
  questionInput.value = "";
  autoResizeTextarea();
  renderProductList();
  updateDocumentSelectionUI();
}

function toggleSettingsPanel() {
  const hidden = settingsPanel.classList.toggle("hidden");
  settingsToggleButton.setAttribute("aria-expanded", String(!hidden));
}

function updateSessionLabel() {
  sessionIdLabel.textContent = currentSessionId;
}

function setSubmitting(submitting) {
  isSubmitting = submitting;
  sendButton.disabled = submitting || !questionInput.value.trim();
  questionInput.disabled = submitting;
}

function loadOrCreateSessionId() {
  const stored = localStorage.getItem(SESSION_STORAGE_KEY);
  if (stored) {
    return stored;
  }

  const sessionId = createSessionId();
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
}

function createSessionId() {
  return `demo-session-${Date.now()}`;
}

function scrollToLatest() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function autoResizeTextarea() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 200)}px`;
  sendButton.disabled = isSubmitting || !questionInput.value.trim();
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
  if (Array.isArray(message.selected_product_names) && message.selected_product_names.length) {
    badges.push(renderBadge("검색 상품", message.selected_product_names.join(", ")));
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
  return chatMessages.querySelector(".system-card") !== null && chatMessages.children.length === 1;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
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
