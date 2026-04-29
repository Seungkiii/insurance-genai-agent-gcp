const sessionIdInput = document.getElementById("sessionId");
const documentIdsInput = document.getElementById("documentIds");
const topKInput = document.getElementById("topK");
const questionInput = document.getElementById("questionInput");
const sendButton = document.getElementById("sendButton");
const loadingIndicator = document.getElementById("loadingIndicator");
const errorBox = document.getElementById("errorBox");
const answerContent = document.getElementById("answerContent");
const metaGrid = document.getElementById("metaGrid");
const citationsList = document.getElementById("citationsList");
const toolTraceList = document.getElementById("toolTraceList");
const recommendedDesignCard = document.getElementById("recommendedDesignCard");
const currentDesignCard = document.getElementById("currentDesignCard");

document.querySelectorAll(".demo-question").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.question || "";
    questionInput.focus();
  });
});

sendButton.addEventListener("click", submitQuestion);
questionInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    submitQuestion();
  }
});

async function submitQuestion() {
  const question = questionInput.value.trim();
  if (!question) {
    showError("질문을 입력해 주세요.");
    return;
  }

  setLoading(true);
  hideError();

  try {
    const payload = {
      session_id: sessionIdInput.value.trim() || "demo-session-001",
      question,
      document_ids: parseDocumentIds(documentIdsInput.value),
      top_k: Number(topKInput.value || 5),
    };

    const response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const detail = await safeReadError(response);
      throw new Error(detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    renderResponse(data);
  } catch (error) {
    showError(error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.");
  } finally {
    setLoading(false);
  }
}

function parseDocumentIds(rawValue) {
  return rawValue
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function renderResponse(data) {
  answerContent.classList.remove("empty-state");
  answerContent.textContent = data.answer || "-";

  renderMeta(data);
  renderCitations(data.citations || []);
  renderToolTrace(data.tool_trace || []);
  renderJsonCard(recommendedDesignCard, data.recommended_design, "recommended_design이 없습니다.");
  renderJsonCard(currentDesignCard, data.current_design, "current_design이 없습니다.");
}

function renderMeta(data) {
  const entries = [
    ["Intent", data.intent ?? "-"],
    ["Search Profile", data.search_profile ?? "-"],
    ["Confidence", data.confidence_score ?? "-"],
    ["Fallback", String(data.fallback_required ?? "-")],
  ];

  metaGrid.innerHTML = entries
    .map(
      ([label, value]) =>
        `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value))}</dd></div>`,
    )
    .join("");
}

function renderCitations(citations) {
  if (!citations.length) {
    citationsList.className = "card-list empty-state";
    citationsList.textContent = "citation이 없습니다.";
    return;
  }

  citationsList.className = "card-list";
  citationsList.innerHTML = citations
    .map((citation) => {
      const score = citation.hybrid_score ?? citation.score ?? "-";
      return `
        <article class="citation-card">
          <h3>${escapeHtml(citation.document_name || "Unknown document")}</h3>
          <div class="citation-grid">
            <div><strong>Page</strong> ${escapeHtml(String(citation.page ?? "-"))}</div>
            <div><strong>Section</strong> ${escapeHtml(citation.section || "-")}</div>
            <div><strong>Normalized</strong> ${escapeHtml(citation.normalized_section || "-")}</div>
            <div><strong>Doc Type</strong> ${escapeHtml(citation.document_type || "-")}</div>
            <div><strong>Product Type</strong> ${escapeHtml(citation.product_type || "-")}</div>
            <div><strong>Score</strong> ${escapeHtml(String(score))}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderToolTrace(toolTrace) {
  if (!toolTrace.length) {
    toolTraceList.className = "timeline empty-state";
    toolTraceList.textContent = "tool trace가 없습니다.";
    return;
  }

  toolTraceList.className = "timeline";
  toolTraceList.innerHTML = toolTrace
    .map((item) => {
      const summary = item.output_summary ? JSON.stringify(item.output_summary, null, 2) : "-";
      return `
        <article class="timeline-item">
          <h3>${escapeHtml(item.tool_name || "tool")}</h3>
          <div class="trace-meta">
            <span>step ${escapeHtml(String(item.step ?? "-"))}</span>
            <span>${escapeHtml(item.status || "-")}</span>
            <span>${escapeHtml(String(item.latency_ms ?? 0))}ms</span>
          </div>
          <pre>${escapeHtml(summary)}</pre>
          ${item.error ? `<div class="error-box">${escapeHtml(item.error)}</div>` : ""}
        </article>
      `;
    })
    .join("");
}

function renderJsonCard(container, payload, emptyText) {
  if (!payload) {
    container.className = "json-card empty-state";
    container.textContent = emptyText;
    return;
  }

  container.className = "json-card";
  container.innerHTML = `<pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
}

function setLoading(isLoading) {
  loadingIndicator.classList.toggle("hidden", !isLoading);
  sendButton.disabled = isLoading;
  sendButton.style.opacity = isLoading ? "0.68" : "1";
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

async function safeReadError(response) {
  try {
    const payload = await response.json();
    return payload.detail || JSON.stringify(payload);
  } catch {
    return await response.text();
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
