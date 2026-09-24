/* LegalEase AI – Frontend Logic */

'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
const state = {
  docId: null,
  docName: null,
  docMeta: null,
  comparisonData: null,
  currentFilter: 'ALL'
};

// ─────────────────────────────────────────────────────────────────────────────
// DOM helpers
// ─────────────────────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const show = (el) => el && (el.hidden = false);
const hide = (el) => el && (el.hidden = true);

function setError(el, msg) {
  if (!el) return;
  el.textContent = msg;
  show(el);
}
function clearError(el) {
  if (!el) return;
  el.textContent = '';
  hide(el);
}

// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Upload
// ─────────────────────────────────────────────────────────────────────────────
const uploadSection  = $('#upload-section');
const uploadForm     = $('#upload-form');
const fileInput      = $('#file-input');
const uploadBtn      = $('#upload-btn');
const uploadError    = $('#upload-error');
const pageLoader     = $('#page-loader');
const loaderMsg      = $('#loader-msg');
const workspace      = $('#workspace');
const docName        = $('#doc-name');
const docMetaEl      = $('#doc-meta');
const newUploadBtn   = $('#new-upload-btn');
const dropZone       = $('#drop-zone');

// Drag-and-drop visuals
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
  }
});

uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearError(uploadError);
  const file = fileInput.files[0];
  if (!file) { setError(uploadError, 'Please select a file first.'); return; }

  const formData = new FormData();
  formData.append('file', file);
  const country = $('#country-input').value.trim();
  const region  = $('#region-input').value.trim();
  if (country) formData.append('country', country);
  if (region)  formData.append('region', region);

  uploadBtn.disabled = true;
  loaderMsg.textContent = 'Uploading and processing…';
  show(pageLoader);
  hide(uploadSection);

  try {
    const data = await apiFetch('/api/documents/upload', { method: 'POST', body: formData });
    state.docId   = data.document_id;
    state.docName = data.filename;
    state.docMeta = `${data.type.toUpperCase()} · ${data.page_count} page(s) · ${data.character_count.toLocaleString()} characters`;
    docName.textContent  = state.docName;
    docMetaEl.textContent = state.docMeta;
    hide(pageLoader);
    show(workspace);
    // Auto-load summary
    loadSummary();
  } catch (err) {
    hide(pageLoader);
    show(uploadSection);
    setError(uploadError, `Upload failed: ${err.message}`);
  } finally {
    uploadBtn.disabled = false;
  }
});

newUploadBtn.addEventListener('click', () => {
  state.docId = null;
  state.comparisonData = null;
  uploadForm.reset();
  hide(workspace);
  show(uploadSection);
  ['summary','risks','deadlines','clauses','consist','compare','nextsteps','lawyerprep'].forEach(resetTab);
  resetChat();
});

// ─────────────────────────────────────────────────────────────────────────────
// Tabs
// ─────────────────────────────────────────────────────────────────────────────
const tabs     = document.querySelectorAll('.tab');
const tabPanels = document.querySelectorAll('.tab-panel');

tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    tabs.forEach((t) => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
    tabPanels.forEach((p) => { p.classList.remove('active'); p.hidden = true; });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    const panel = $(`#tab-${tab.dataset.tab}`);
    if (panel) { panel.classList.add('active'); panel.hidden = false; }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// SUMMARY
// ─────────────────────────────────────────────────────────────────────────────
$('#load-summary-btn').addEventListener('click', loadSummary);

async function loadSummary() {
  if (!state.docId) return;
  const loading = $('#summary-loading');
  const errorEl = $('#summary-error');
  const content = $('#summary-content');
  clearError(errorEl);
  hide(content);
  show(loading);

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/summary`, { method: 'POST' });
    renderSummary(data);
    hide(loading);
    show(content);
  } catch (err) {
    hide(loading);
    setError(errorEl, err.message);
  }
}

function renderSummary(data) {
  const grid = $('#overview-grid');
  grid.innerHTML = '';
  const fields = [
    ['Document Type', data.document_type],
    ['Parties', data.parties?.join(', ')],
    ['Duration', data.duration],
  ];
  fields.forEach(([label, value]) => {
    if (!value) return;
    const card = document.createElement('div');
    card.className = 'overview-card';
    card.innerHTML = `<p class="overview-label">${label}</p><p class="overview-value">${escHtml(value)}</p>`;
    grid.appendChild(card);
  });

  if (data.key_points?.length) {
    data.key_points.forEach((kp) => {
      const card = document.createElement('div');
      card.className = 'overview-card';
      card.innerHTML = `<p class="overview-value">${escHtml(kp)}</p>`;
      grid.appendChild(card);
    });
  }

  $('#summary-text').textContent = data.summary || 'No summary available.';

  const kcs = $('#key-clauses-section');
  const kcl = $('#key-clauses-list');
  kcl.innerHTML = '';
  if (data.important_clauses?.length) {
    data.important_clauses.forEach((c) => kcl.appendChild(buildClauseCard(c)));
    show(kcs);
  } else {
    hide(kcs);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RISKS
// ─────────────────────────────────────────────────────────────────────────────
$('#load-risks-btn').addEventListener('click', loadRisks);

async function loadRisks() {
  if (!state.docId) return;
  const loading = $('#risks-loading');
  const errorEl = $('#risks-error');
  const content = $('#risks-content');
  const list    = $('#risks-list');
  const empty   = $('#risks-empty');
  clearError(errorEl); hide(content); show(loading);

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/risks`);
    list.innerHTML = '';
    if (!data.risks?.length) {
      hide(list); show(empty);
    } else {
      show(list); hide(empty);
      data.risks.forEach((r) => list.appendChild(buildRiskItem(r)));
    }
    hide(loading); show(content);
  } catch (err) {
    hide(loading); setError(errorEl, err.message);
  }
}

function buildRiskItem(r) {
  const item = document.createElement('div');
  item.className = `risk-item sev-${r.severity}`;
  item.innerHTML = `
    <div class="risk-badge"><span class="clause-sev sev-${r.severity}">${escHtml(r.severity)}</span></div>
    <div>
      <p class="risk-type">${escHtml(r.risk_type.replace(/_/g, ' '))}</p>
      <p class="risk-desc">${escHtml(r.description)}</p>
      ${r.evidence ? `<p class="risk-evidence">${escHtml(r.evidence.substring(0, 120))}</p>` : ''}
      <p class="risk-loc">Page ${r.page_number ?? '?'} · Clause ${r.clause_number ?? 'N/A'}${r.clause_title ? ' · ' + escHtml(r.clause_title) : ''}</p>
    </div>`;
  return item;
}

// ─────────────────────────────────────────────────────────────────────────────
// DEADLINES
// ─────────────────────────────────────────────────────────────────────────────
$('#load-deadlines-btn').addEventListener('click', loadDeadlines);

async function loadDeadlines() {
  if (!state.docId) return;
  const loading = $('#deadlines-loading');
  const errorEl = $('#deadlines-error');
  const content = $('#deadlines-content');
  const list    = $('#deadlines-list');
  const empty   = $('#deadlines-empty');
  clearError(errorEl); hide(content); show(loading);

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/deadlines`);
    list.innerHTML = '';
    if (!data.deadlines?.length) {
      hide(list); show(empty);
    } else {
      show(list); hide(empty);
      data.deadlines.forEach((d) => {
        const item = document.createElement('div');
        item.className = 'deadline-item';
        item.innerHTML = `
          <p class="deadline-phrase">${escHtml(d.deadline)}</p>
          <p class="deadline-ctx">${escHtml(d.context)}</p>
          <p class="deadline-loc">Page ${d.page ?? '?'} · Clause ${d.clause ?? 'N/A'}${d.clause_title ? ' · ' + escHtml(d.clause_title) : ''}</p>`;
        list.appendChild(item);
      });
    }
    hide(loading); show(content);
  } catch (err) {
    hide(loading); setError(errorEl, err.message);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// KEY CLAUSES
// ─────────────────────────────────────────────────────────────────────────────
$('#load-clauses-btn').addEventListener('click', loadClauses);

async function loadClauses() {
  if (!state.docId) return;
  const loading = $('#clauses-loading');
  const errorEl = $('#clauses-error');
  const content = $('#clauses-content');
  const list    = $('#clauses-list');
  const empty   = $('#clauses-empty');
  clearError(errorEl); hide(content); show(loading);

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/important-clauses`);
    list.innerHTML = '';
    if (!data.important_clauses?.length) {
      hide(list); show(empty);
    } else {
      show(list); hide(empty);
      data.important_clauses.forEach((c) => list.appendChild(buildClauseCard(c)));
    }
    hide(loading); show(content);
  } catch (err) {
    hide(loading); setError(errorEl, err.message);
  }
}

function buildClauseCard(c) {
  const card = document.createElement('div');
  card.className = 'clause-card';
  card.setAttribute('tabindex', '0');
  card.setAttribute('role', 'button');
  card.setAttribute('aria-label', `View clause: ${c.title || c.type}`);
  card.innerHTML = `
    <span class="clause-sev sev-${c.severity}">${escHtml(c.severity)}</span>
    <p class="clause-title-text">${escHtml(c.title || c.type?.replace(/_/g, ' ') || 'Clause')}</p>
    <p class="clause-loc">Page ${c.page ?? '?'} · Clause ${c.clause ?? 'N/A'}</p>
    ${c.reason ? `<p class="clause-reason">${escHtml(c.reason)}</p>` : ''}`;

  if (c.chunk_id) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-secondary btn-sm explain-btn';
    btn.textContent = '📖 Explain this clause';
    btn.setAttribute('aria-label', `Explain clause ${c.clause ?? ''}`);
    btn.addEventListener('click', (e) => { e.stopPropagation(); openExplainDrawer(c.chunk_id, c.title); });
    card.appendChild(btn);
  }
  return card;
}

// ─────────────────────────────────────────────────────────────────────────────
// CLAUSE EXPLANATION DRAWER
// ─────────────────────────────────────────────────────────────────────────────
const drawer        = $('#clause-drawer');
const drawerClose   = $('#drawer-close-btn');
const drawerLoading = $('#drawer-loading');
const drawerContent = $('#drawer-content');
const drawerTitle   = $('#drawer-title');

drawerClose.addEventListener('click', closeDrawer);
drawer.addEventListener('click', (e) => { if (e.target === drawer) closeDrawer(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !drawer.hidden) closeDrawer(); });

function closeDrawer() {
  hide(drawer);
  document.body.style.overflow = '';
}

async function openExplainDrawer(chunkId, title) {
  drawerTitle.textContent = `Explain: ${title || 'Clause'}`;
  drawerContent.innerHTML = '';
  hide(drawerContent);
  show(drawerLoading);
  show(drawer);
  document.body.style.overflow = 'hidden';

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chunk_id: chunkId }),
    });

    drawerContent.innerHTML = `
      <div class="explain-section">
        <p class="explain-label">Original Text</p>
        <pre class="explain-original">${escHtml(data.original_text || '')}</pre>
      </div>
      <div class="explain-section">
        <p class="explain-label">Plain-Language Explanation</p>
        <p class="explain-plain">${escHtml(data.plain_language || 'Not available.')}</p>
      </div>
      <div class="explain-section">
        <p class="explain-label">Why It Matters</p>
        <p class="explain-matters">${escHtml(data.why_it_matters || 'Not available.')}</p>
      </div>
      <div class="explain-section">
        <p class="explain-label">Source</p>
        <span class="source-chip">Page ${data.source?.page ?? '?'} · Clause ${data.source?.clause ?? 'N/A'} · ${escHtml(data.source?.title || '')}</span>
      </div>
      <p class="explain-notice">⚠️ This explanation is provided for general understanding only. Consult a qualified lawyer for legal advice.</p>`;

    hide(drawerLoading);
    show(drawerContent);
  } catch (err) {
    drawerContent.innerHTML = `<p class="explain-plain" style="color:var(--red)">Error: ${escHtml(err.message)}</p>`;
    hide(drawerLoading);
    show(drawerContent);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CONSISTENCY
// ─────────────────────────────────────────────────────────────────────────────
$('#load-consist-btn').addEventListener('click', loadConsistency);

async function loadConsistency() {
  if (!state.docId) return;
  const loading = $('#consist-loading');
  const errorEl = $('#consist-error');
  const content = $('#consist-content');
  const list    = $('#consist-list');
  const empty   = $('#consist-empty');
  clearError(errorEl); hide(content); show(loading);

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/consistency`);
    list.innerHTML = '';
    if (!data.issues?.length) {
      hide(list); show(empty);
    } else {
      show(list); hide(empty);
      data.issues.forEach((issue) => {
        const item = document.createElement('div');
        item.className = `risk-item sev-${issue.severity}`;
        item.innerHTML = `
          <div class="risk-badge"><span class="clause-sev sev-${issue.severity}">${escHtml(issue.severity)}</span></div>
          <div>
            <p class="risk-type">${escHtml(issue.category || issue.type)}</p>
            <p class="risk-desc">${escHtml(issue.description)}</p>
            <p class="risk-loc" style="margin-top:0.4rem;color:var(--amber)">⚠️ ${escHtml(issue.action)}</p>
          </div>`;
        list.appendChild(item);
      });
    }
    hide(loading); show(content);
  } catch (err) {
    hide(loading); setError(errorEl, err.message);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CHAT
// ─────────────────────────────────────────────────────────────────────────────
const chatMessages = $('#chat-messages');
const chatForm     = $('#chat-form');
const chatInput    = $('#chat-input');
const chatSendBtn  = $('#chat-send-btn');

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question || !state.docId) return;
  chatInput.value = '';
  chatSendBtn.disabled = true;

  appendBubble('user', question);

  const thinkingId = 'thinking-' + Date.now();
  const thinking = document.createElement('div');
  thinking.className = 'chat-bubble bubble-assistant';
  thinking.id = thinkingId;
  thinking.innerHTML = '<div class="spinner-sm" aria-hidden="true"></div> Thinking…';
  chatMessages.appendChild(thinking);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const data = await apiFetch(`/api/documents/${state.docId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    document.getElementById(thinkingId)?.remove();
    appendAssistantBubble(data);
  } catch (err) {
    document.getElementById(thinkingId)?.remove();
    appendBubble('assistant', `Error: ${err.message}`);
  } finally {
    chatSendBtn.disabled = false;
    chatInput.focus();
  }
});

function appendBubble(role, text) {
  const div = document.createElement('div');
  div.className = `chat-bubble bubble-${role}`;
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendAssistantBubble(data) {
  const div = document.createElement('div');
  div.className = 'chat-bubble bubble-assistant';

  let html = `<p class="bubble-intent">Intent: ${escHtml(data.intent || 'QUESTION')}</p>`;
  html += `<p>${escHtml(data.answer || '')}</p>`;

  if (data.evidence?.length) {
    html += '<div class="bubble-evidence">';
    data.evidence.forEach((ev) => {
      html += `<span class="evidence-chip" title="View source" data-chunk="${ev.chunk_id}">📄 Clause ${escHtml(String(ev.clause || 'N/A'))} · Page ${ev.page ?? '?'}</span>`;
    });
    html += '</div>';
  }

  html += '<p class="chat-notice">⚖️ Legal information only · Not professional legal advice</p>';
  div.innerHTML = html;

  div.querySelectorAll('[data-chunk]').forEach((chip) => {
    chip.addEventListener('click', () => openExplainDrawer(parseInt(chip.dataset.chunk), `Clause ${chip.textContent}`));
  });

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function resetChat() {
  chatMessages.innerHTML = `
    <div class="chat-welcome">
      <span>💬</span>
      <p>Ask a question about this document.</p>
      <p class="chat-hint">e.g. "What happens if I terminate early?" or "What are the payment terms?"</p>
    </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// PROMPT 5: COMPARISON
// ─────────────────────────────────────────────────────────────────────────────
const compareForm = $('#compare-form');
const fileBInput  = $('#file-b-input');

if (compareForm) {
  compareForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.docId) return;
    const fileB = fileBInput.files[0];
    const loading = $('#compare-loading');
    const errorEl = $('#compare-error');
    const content = $('#compare-content');
    clearError(errorEl); hide(content);

    if (!fileB) { setError(errorEl, 'Please select Document B to compare.'); return; }

    show(loading);
    try {
      // 1. Upload Document B
      const formData = new FormData();
      formData.append('file', fileB);
      const docBData = await apiFetch('/api/documents/upload', { method: 'POST', body: formData });

      // 2. Compare Document A and Document B
      const compData = await apiFetch('/api/documents/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_a_id: state.docId, document_b_id: docBData.document_id }),
      });

      state.comparisonData = compData;
      renderComparison(compData);
      hide(loading);
      show(content);
    } catch (err) {
      hide(loading);
      setError(errorEl, `Comparison failed: ${err.message}`);
    }
  });
}

// Filter buttons for comparison
document.querySelectorAll('.filter-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    state.currentFilter = btn.dataset.filter;
    if (state.comparisonData) renderComparisonList(state.comparisonData.changes);
  });
});

function renderComparison(data) {
  const summaryGrid = $('#compare-summary-grid');
  summaryGrid.innerHTML = `
    <div class="overview-card"><p class="overview-label">Total Clauses Compared</p><p class="overview-value">${data.summary.total_compared}</p></div>
    <div class="overview-card"><p class="overview-label" style="color:var(--amber)">Modified</p><p class="overview-value">${data.summary.modified}</p></div>
    <div class="overview-card"><p class="overview-label" style="color:var(--green)">Added</p><p class="overview-value">${data.summary.added}</p></div>
    <div class="overview-card"><p class="overview-label" style="color:var(--red)">Removed</p><p class="overview-value">${data.summary.removed}</p></div>
    <div class="overview-card"><p class="overview-label" style="color:var(--text-muted)">Unchanged</p><p class="overview-value">${data.summary.unchanged}</p></div>
  `;
  renderComparisonList(data.changes);
}

function renderComparisonList(changes) {
  const list = $('#compare-list');
  list.innerHTML = '';
  const filtered = changes.filter((c) => state.currentFilter === 'ALL' || c.status === state.currentFilter);

  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state"><span>🔍</span><p>No clauses match this filter.</p></div>';
    return;
  }

  filtered.forEach((c) => {
    const item = document.createElement('div');
    item.className = 'card mb-4';
    item.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="status-badge status-${c.status}">${c.status}</span>
        <span class="clause-loc">Doc A: Page ${c.document_a_page ?? 'N/A'} · Doc B: Page ${c.document_b_page ?? 'N/A'}</span>
      </div>
      <h4 style="margin: 0.5rem 0; font-size: 0.95rem;">CLAUSE ${escHtml(c.clause)} ${c.clause_title ? '— ' + escHtml(c.clause_title) : ''}</h4>
      <div class="diff-grid">
        <div class="diff-box">
          <p class="diff-box-label">DOCUMENT A (${escHtml(state.docName || 'Old')})</p>
          ${escHtml(c.old_text || '(Not present in Document A)')}
        </div>
        <div class="diff-box">
          <p class="diff-box-label">DOCUMENT B (New)</p>
          ${escHtml(c.new_text || '(Not present in Document B)')}
        </div>
      </div>
      <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.5rem;"><strong>EXPLANATION:</strong> ${escHtml(c.explanation)}</p>
    `;
    list.appendChild(item);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// PROMPT 5: NEXT STEPS
// ─────────────────────────────────────────────────────────────────────────────
const nextStepsForm = $('#nextsteps-form');
if (nextStepsForm) {
  nextStepsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.docId) return;
    const situation = $('#situation-input').value.trim();
    const loading = $('#nextsteps-loading');
    const errorEl = $('#nextsteps-error');
    const content = $('#nextsteps-content');
    clearError(errorEl); hide(content); show(loading);

    try {
      const data = await apiFetch(`/api/documents/${state.docId}/next-steps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ situation }),
      });
      renderNextSteps(data);
      hide(loading);
      show(content);
    } catch (err) {
      hide(loading);
      setError(errorEl, err.message);
    }
  });
}

function renderNextSteps(data) {
  const container = $('#nextsteps-content');
  container.innerHTML = `
    ${data.jurisdiction_context?.jurisdiction_note ? `
      <div class="explain-notice mb-4">
        📌 <strong>Jurisdiction Context:</strong> ${escHtml(data.jurisdiction_context.jurisdiction_note)}
      </div>
    ` : ''}

    <div class="overview-grid mb-4">
      <div class="card">
        <h4 class="card-heading">📄 Document Facts</h4>
        <ul style="padding-left:1.2rem; font-size:0.88rem; color:var(--text);">
          ${data.document_facts.map((f) => `<li style="margin-bottom:0.4rem;">${escHtml(f)}</li>`).join('')}
        </ul>
      </div>
      <div class="card">
        <h4 class="card-heading">🔍 Things to Check</h4>
        <ul style="padding-left:1.2rem; font-size:0.88rem; color:var(--text);">
          ${data.things_to_check.map((t) => `<li style="margin-bottom:0.4rem;">${escHtml(t)}</li>`).join('')}
        </ul>
      </div>
    </div>

    <div class="overview-grid mb-4">
      <div class="card">
        <h4 class="card-heading">❓ Questions to Consider</h4>
        <ul style="padding-left:1.2rem; font-size:0.88rem; color:var(--text);">
          ${data.questions_to_consider.map((q) => `<li style="margin-bottom:0.4rem;">${escHtml(q)}</li>`).join('')}
        </ul>
      </div>
      <div class="card">
        <h4 class="card-heading">📁 Documents to Preserve</h4>
        <ul style="padding-left:1.2rem; font-size:0.88rem; color:var(--text);">
          ${data.documents_to_preserve.map((d) => `<li style="margin-bottom:0.4rem;">${escHtml(d)}</li>`).join('')}
        </ul>
      </div>
    </div>

    <p class="explain-notice">⚖️ <strong>Legal Information Disclaimer:</strong> These points are for practical orientation only. They do not constitute definitive legal advice or guarantees.</p>
  `;
}

// ─────────────────────────────────────────────────────────────────────────────
// PROMPT 5: LAWYER PREP
// ─────────────────────────────────────────────────────────────────────────────
const lawyerPrepForm = $('#lawyerprep-form');
if (lawyerPrepForm) {
  lawyerPrepForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.docId) return;
    const situation = $('#lawyerprep-situation-input').value.trim();
    const loading = $('#lawyerprep-loading');
    const errorEl = $('#lawyerprep-error');
    const content = $('#lawyerprep-content');
    clearError(errorEl); hide(content); show(loading);

    try {
      const data = await apiFetch(`/api/documents/${state.docId}/lawyer-prep`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ situation }),
      });
      renderLawyerPrep(data);
      hide(loading);
      show(content);
    } catch (err) {
      hide(loading);
      setError(errorEl, err.message);
    }
  });
}

function renderLawyerPrep(data) {
  const container = $('#lawyerprep-content');
  container.innerHTML = `
    <div class="card">
      <div style="border-bottom: 1px solid var(--border); padding-bottom: 0.75rem; margin-bottom: 1rem;">
        <h3 style="font-size: 1.2rem; font-weight: 700; color: var(--accent);">${escHtml(data.title)}</h3>
        <p class="clause-loc">Document: ${escHtml(data.filename)} (${escHtml(data.document_type)})</p>
      </div>

      <div class="explain-section">
        <p class="explain-label">1. Situation Summary</p>
        <p class="body-text">${escHtml(data.situation_summary)}</p>
      </div>

      <div class="explain-section">
        <p class="explain-label">2. Documents Identified</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem;">
          ${data.documents_identified.map((d) => `<li>${escHtml(d)}</li>`).join('')}
        </ul>
      </div>

      <div class="explain-section">
        <p class="explain-label">3. Important Clauses</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem;">
          ${data.important_clauses.map((c) => `<li><strong>${escHtml(c.title || 'Clause')}:</strong> ${escHtml(c.description)} (Page ${c.page ?? '?'})</li>`).join('')}
        </ul>
      </div>

      <div class="explain-section">
        <p class="explain-label">4. Important Dates</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem;">
          ${data.important_dates.map((d) => `<li><strong>${escHtml(d.deadline)}:</strong> ${escHtml(d.context)}</li>`).join('')}
        </ul>
      </div>

      <div class="explain-section">
        <p class="explain-label">5. Questions to Ask a Lawyer</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem; color: var(--amber);">
          ${data.questions_to_ask_lawyer.map((q) => `<li>${escHtml(q)}</li>`).join('')}
        </ul>
      </div>

      <div class="explain-section">
        <p class="explain-label">6. Missing Information</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem;">
          ${data.missing_information.map((m) => `<li>${escHtml(m)}</li>`).join('')}
        </ul>
      </div>

      <div class="explain-section">
        <p class="explain-label">7. Documents to Bring</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem;">
          ${data.documents_to_bring.map((b) => `<li>${escHtml(b)}</li>`).join('')}
        </ul>
      </div>

      <div class="explain-section">
        <p class="explain-label">8. Items Requiring Verification</p>
        <ul style="padding-left:1.2rem; font-size:0.88rem;">
          ${data.items_requiring_verification.map((v) => `<li>${escHtml(v)}</li>`).join('')}
        </ul>
      </div>

      <div class="explain-notice mt-4">
        💼 <strong>Consultation Brief Note:</strong> Take this brief to your consultation with a licensed attorney to ensure a focused, productive meeting.
      </div>
    </div>
  `;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function resetTab(name) {
  const ids = [`${name}-loading`, `${name}-content`, `${name}-error`, `${name}-empty`, `${name}-list`];
  ids.forEach((id) => { const el = document.getElementById(id); if (el) hide(el); });
}

// Build Drawer DOM
(function buildDrawerDOM() {
  const drawer = $('#clause-drawer');
  if (!drawer) return;
  drawer.innerHTML = '';
  const panel = document.createElement('div');
  panel.className = 'drawer-panel';
  panel.innerHTML = `
    <div class="drawer-header">
      <h3 id="drawer-title" class="drawer-heading">Clause Explanation</h3>
      <button class="drawer-close" id="drawer-close-btn" aria-label="Close explanation">✕</button>
    </div>
    <div id="drawer-loading" class="loading-state">
      <div class="spinner-sm" aria-hidden="true"></div> Generating explanation…
    </div>
    <div id="drawer-content"></div>`;
  drawer.appendChild(panel);

  document.getElementById('drawer-close-btn').addEventListener('click', closeDrawer);
})();
