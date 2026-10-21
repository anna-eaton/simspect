"""
SimSpect pipeline dashboard UI — single-page web app for visualizing Alloy generation,
XML fanout, corpus exploration, and test execution.

Serves as a read-mostly remote dashboard reached via SSH port-forward.
Exposes ONE module-level string constant PAGE containing the complete HTML document.
"""

PAGE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SimSpect Dashboard</title>
<style>
:root {
  --bg: #16181d;
  --panel: #1e2128;
  --panel2: #191c22;
  --border: #2c303a;
  --text: #d7dae0;
  --heading: #fff;
  --muted: #7c8190;
  --accent: #3a6ea5;
  --link: #6cb0ff;
  --navlink: #9fb6d6;
  --code-bg: #23272f;
  --code-text: #e6c07b;
  --pre-bg: #0f1115;
  --pre-text: #cdd3dc;
  --tab-bg: #272b34;
  --tab-text: #aab;
  --hover: #23272f;
  --quote-bg: #1b1e25;
  --err: #e06c5a;
  --ok: #7bc47b;
  --run: #7bc47b;
  --warn: #d9b54a;
  color-scheme: dark;
}
:root[data-theme="light"] {
  --bg: #f7f8fa;
  --panel: #ffffff;
  --panel2: #eef1f5;
  --border: #d6dae1;
  --text: #2a2e35;
  --heading: #14171c;
  --muted: #5f6772;
  --accent: #3a6ea5;
  --link: #1a5fb4;
  --navlink: #1a5fb4;
  --code-bg: #eceff3;
  --code-text: #9a5b00;
  --pre-bg: #f2f4f7;
  --pre-text: #2a2e35;
  --tab-bg: #e6e9ee;
  --tab-text: #555;
  --hover: #e3e8ef;
  --quote-bg: #eef1f5;
  --err: #c0392b;
  --ok: #27ae60;
  --run: #27ae60;
  --warn: #e67e22;
  color-scheme: light;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
}

header {
  padding: 10px 16px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 14px;
  position: sticky;
  top: 0;
  z-index: 100;
}

header h1 {
  font-size: 15px;
  margin: 0;
  font-weight: 600;
  color: var(--heading);
}

.main-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tab {
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  background: var(--tab-bg);
  color: var(--tab-text);
  border: 1px solid var(--border);
  font-size: 13px;
  white-space: nowrap;
  transition: background 0.2s, color 0.2s;
}

.tab:hover {
  background: var(--hover);
}

.tab.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.controls {
  margin-left: auto;
  color: var(--muted);
  font-size: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

#theme {
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  background: var(--tab-bg);
  color: var(--tab-text);
  border: 1px solid var(--border);
  font-size: 12px;
}

select {
  padding: 3px 6px;
  border-radius: 4px;
  background: var(--tab-bg);
  color: var(--text);
  border: 1px solid var(--border);
  font-size: 12px;
}

.wrap {
  display: flex;
  height: calc(100vh - 50px);
  overflow: hidden;
}

.main-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  max-width: 100%;
}

.utility-panel {
  width: 320px;
  background: var(--panel2);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.utility-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 8px;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
}

.util-tab {
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  background: var(--tab-bg);
  color: var(--tab-text);
  border: 1px solid var(--border);
  font-size: 11px;
  white-space: nowrap;
}

.util-tab.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.utility-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}

.card h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--heading);
}

.card-meta {
  font-size: 12px;
  color: var(--muted);
}

.badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
  margin-right: 4px;
}

.badge.running { background: var(--run); color: #fff; }
.badge.enumerating { background: var(--run); color: #fff; }
.badge.following { background: var(--run); color: #fff; }
.badge.done { background: var(--accent); color: #fff; }
.badge.stale { background: var(--err); color: #fff; }
.badge.failed { background: var(--err); color: #fff; }

.progress-bar {
  width: 100%;
  height: 6px;
  background: var(--code-bg);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 6px;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  width: 0%;
}

.breadcrumb {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 12px;
}

.breadcrumb a {
  color: var(--link);
  cursor: pointer;
  text-decoration: none;
}

.breadcrumb a:hover {
  text-decoration: underline;
}

.breadcrumb > * + *::before {
  content: " / ";
  margin: 0 4px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-top: 8px;
}

th, td {
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
}

th {
  background: var(--code-bg);
  font-weight: 600;
}

tr:hover {
  background: var(--hover);
}

tr.clickable:hover {
  cursor: pointer;
  background: var(--hover);
}

.empty {
  text-align: center;
  padding: 20px;
  color: var(--muted);
}

.spin {
  color: var(--muted);
}

.err {
  color: var(--err);
}

button {
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--tab-bg);
  color: var(--text);
  cursor: pointer;
  font-size: 12px;
}

button:hover {
  background: var(--hover);
}

button.primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

input, textarea {
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--code-bg);
  color: var(--text);
  font-family: inherit;
  font-size: 12px;
}

label {
  display: block;
  margin: 8px 0 4px 0;
  font-size: 12px;
  font-weight: 500;
  color: var(--heading);
}

.form-group {
  margin-bottom: 12px;
}

.file-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 6px; font-size: 11px;
}
.file-bar code { color: var(--pre-text); opacity: 0.8; word-break: break-all; }
a.vscode-link {
  display: inline-block; padding: 1px 8px; border: 1px solid var(--border);
  border-radius: 4px; font-size: 11px; text-decoration: none; white-space: nowrap;
}
a.vscode-link::before { content: "↗ "; }
a.vscode-link:hover { background: var(--pre-bg); }
pre.file-content {
  background: var(--pre-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 10px;
  overflow-x: auto;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 11px;
  color: var(--pre-text);
  max-height: 400px;
}

.node-list, .edge-list {
  font-size: 12px;
  margin-top: 8px;
}

.node-item {
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
}

.node-item strong {
  color: var(--heading);
}

code {
  background: var(--code-bg);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  color: var(--code-text);
  font-size: 12px;
}

@media (max-width: 900px) {
  .utility-panel {
    width: 280px;
  }
}

@media (max-width: 700px) {
  .wrap {
    flex-direction: column;
  }
  .utility-panel {
    width: 100%;
    height: 300px;
    border-left: none;
    border-top: 1px solid var(--border);
  }
  .main-tabs {
    gap: 3px;
  }
  .tab {
    padding: 4px 8px;
    font-size: 12px;
  }
}
</style>
</head>
<body>

<header>
  <h1>SimSpect</h1>
  <div class="main-tabs" id="mainTabs"></div>
  <div class="controls">
    <button id="theme" title="toggle light/dark">🌙 dark</button>
    <label style="margin:0">
      auto-refresh
      <select id="iv">
        <option value="0">off</option>
        <option value="15">15s</option>
        <option value="30" selected>30s</option>
        <option value="60">60s</option>
      </select>
    </label>
    <span id="updated" style="min-width:120px; text-align:right"></span>
  </div>
</header>

<div class="wrap">
  <div class="main-area" id="main"></div>
  <div class="utility-panel">
    <div class="utility-tabs" id="utilTabs"></div>
    <div class="utility-content" id="util"></div>
  </div>
</div>

<script>
// ====== State & Config ======
let state = {
  activeMainTab: 'generation',
  activeUtilTab: 'annotation',
  theme: localStorage.getItem('theme') || 'dark',
  autoRefreshInterval: 30,
  timer: null,
  // Corpora drill-down state
  selectedCorpus: null,
  selectedMode: null,
  selectedTest: null,
  corpusOffset: 0,
  corpusLimit: 200,
};

const MAIN_TABS = [
  { id: 'generation', label: 'Generation' },
  { id: 'fanout', label: 'Fanout' },
  { id: 'corpora', label: 'Corpora' },
];

const UTIL_TABS = [
  { id: 'annotation', label: 'Annotation / Check' },
  { id: 'tables', label: 'Fanout Tables' },
  { id: 'launch', label: 'Launch Fanout' },
  { id: 'execgraph', label: 'Execution Graph' },
  { id: 'docs', label: 'Docs' },
];

// ====== Utilities ======
function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function stamp() {
  const now = new Date();
  document.getElementById('updated').textContent = 'updated ' + now.toLocaleTimeString();
}

function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  document.getElementById('theme').textContent = t === 'light' ? '☀️ light' : '🌙 dark';
  localStorage.setItem('theme', t);
  state.theme = t;
}

// ====== API Calls ======
async function apiCall(path, opts = {}) {
  try {
    const res = await fetch(path, opts);
    if (!res.ok) {
      return { error: `HTTP ${res.status}` };
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('json')) {
      return await res.json();
    } else {
      return { html: await res.text() };
    }
  } catch (e) {
    return { error: e.message };
  }
}

// ====== Main Tab Renderers ======

async function renderGeneration() {
  const data = await apiCall('/api/generation');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  if (!data.items || data.items.length === 0) {
    return `<p class="empty">No Alloy generations running.</p>`;
  }
  let html = `<h2>Generation Jobs</h2>`;
  for (const job of data.items) {
    const pct = job.xml_total > 0 ? Math.round(100 * job.xml_done / job.xml_total) : 0;
    const badge = `<span class="badge ${job.state}">${esc(job.state)}</span>`;
    html += `
      <div class="card">
        <h3>${esc(job.model)}</h3>
        <div class="card-meta">
          ${badge}
          <code>${esc(job.config)}</code>
        </div>
        <div>${esc(job.xml_done)}/${esc(job.xml_total)} XML done</div>
        <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
        <div class="card-meta" style="margin-top:6px">
          Runtime: ${esc(job.etime || 'pending')}
          ${job.live ? ' (live)' : ''}
        </div>
      </div>
    `;
  }
  return html;
}

async function renderFanout() {
  const data = await apiCall('/api/fanout');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h2>Fanout Status</h2>`;

  // Producers
  html += `<h3>Concretization (Producers)</h3>`;
  if (data.producers && data.producers.length > 0) {
    for (const prod of data.producers) {
      const badge = `<span class="badge ${prod.state}">${esc(prod.state)}</span>`;
      html += `
        <div class="card">
          <h3>${esc(prod.model)}</h3>
          <div class="card-meta">
            ${badge}
            <code>${esc(prod.config)}</code>
            <br>Runtime: ${esc(prod.etime || 'pending')}
            <br>XML: ${esc(String(prod.xml || 0))}
          </div>
          <table>
            <thead><tr><th>Mode</th><th>LLVM</th><th>ASM</th><th>Annotated</th></tr></thead>
            <tbody>
      `;
      if (prod.modes) {
        for (const m of prod.modes) {
          html += `<tr><td>${esc(m.mode)}</td><td>${m.llvm || 0}</td><td>${m.asm || 0}</td><td>${m.ann || 0}</td></tr>`;
        }
      }
      html += `</tbody></table></div>`;
    }
  } else {
    html += `<p class="empty">No producers.</p>`;
  }

  // Campaigns
  html += `<h3 style="margin-top:20px">gem5 Campaigns</h3>`;
  if (data.campaigns && data.campaigns.length > 0) {
    for (const camp of data.campaigns) {
      const badge = `<span class="badge ${camp.state}">${esc(camp.state)}</span>`;
      html += `
        <div class="card">
          <h3>${esc(camp.results_name)}</h3>
          <div class="card-meta">
            ${badge}
            <code>${esc(camp.model)} / ${esc(camp.campaign)}</code>
            <br>Binary: ${esc(camp.gem5_binary || 'N/A')}
            <br>Started: ${esc(camp.started_at || 'N/A')}
          </div>
          <table>
            <thead><tr><th>Mode</th><th>Kind</th><th>Total</th><th>Hits</th></tr></thead>
            <tbody>
      `;
      if (camp.modes) {
        for (const m of camp.modes) {
          if (m.kinds) {
            for (const k of m.kinds) {
              html += `<tr><td>${esc(m.mode)}</td><td>${esc(k.kind)}</td><td>${k.total || 0}</td><td>${k.hits || 0}</td></tr>`;
            }
          }
        }
      }
      html += `</tbody></table></div>`;
    }
  } else {
    html += `<p class="empty">No campaigns.</p>`;
  }

  html += `<div style="margin-top:16px"><button class="primary" onclick="showUtilTab('launch')">Launch new fanout</button></div>`;
  return html;
}

async function renderCorpora() {
  if (state.selectedTest) {
    return renderTestView();
  }
  if (state.selectedMode) {
    return renderModeView();
  }
  if (state.selectedCorpus) {
    return renderCorpusView();
  }
  return renderCorporaList();
}

async function renderCorporaList() {
  const data = await apiCall('/api/corpora');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  if (!data.corpora || data.corpora.length === 0) {
    return `<p class="empty">No corpora.</p>`;
  }
  let html = `<h2>Corpora</h2>`;
  for (const corp of data.corpora) {
    const modes = (corp.modes || []).map(m => `${esc(m.mode)} (${m.llvm})`).join(', ');
    html += `
      <div class="card" onclick="selectCorpus('${esc(corp.model)}')">
        <h3 style="cursor:pointer; color:var(--link)">${esc(corp.model)}</h3>
        <div class="card-meta">
          ${corp.xml || 0} XML files
          ${corp.has_provenance ? '(with provenance)' : ''}
          <br>Modified: ${esc(corp.mtime || 'N/A')}
          <br>Modes: ${modes}
        </div>
      </div>
    `;
  }
  return html;
}

async function selectCorpus(model) {
  state.selectedCorpus = model;
  state.selectedMode = null;
  state.selectedTest = null;
  await refreshMainTab();
}

async function renderCorpusView() {
  const data = await apiCall('/api/corpus?model=' + encodeURIComponent(state.selectedCorpus));
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `
    <div class="breadcrumb">
      <a onclick="state.selectedCorpus=null; refreshMainTab()">Corpora</a>
      <span>${esc(state.selectedCorpus)}</span>
    </div>
    <h2>${esc(state.selectedCorpus)}</h2>
    <p>${data.xml || 0} XML files</p>
    <h3>Modes</h3>
  `;
  if (data.modes && data.modes.length > 0) {
    html += `<table><thead><tr><th>Mode</th><th>LLVM</th><th>ASM</th><th>Annotated</th></tr></thead><tbody>`;
    for (const m of data.modes) {
      html += `<tr class="clickable" onclick="selectMode('${esc(m.mode)}')">
        <td>${esc(m.mode)}</td>
        <td>${m.llvm || 0}</td>
        <td>${m.asm || 0}</td>
        <td>${m.ann || 0}</td>
      </tr>`;
    }
    html += `</tbody></table>`;
  }
  return html;
}

async function selectMode(mode) {
  state.selectedMode = mode;
  state.selectedTest = null;
  state.corpusOffset = 0;
  await refreshMainTab();
}

async function renderModeView() {
  const params = `model=${encodeURIComponent(state.selectedCorpus)}&mode=${encodeURIComponent(state.selectedMode)}&offset=${state.corpusOffset}&limit=${state.corpusLimit}`;
  const data = await apiCall('/api/corpus?model=' + encodeURIComponent(state.selectedCorpus) + '&mode=' + encodeURIComponent(state.selectedMode) + '&offset=' + state.corpusOffset + '&limit=' + state.corpusLimit);
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `
    <div class="breadcrumb">
      <a onclick="state.selectedCorpus=null;state.selectedMode=null;refreshMainTab()">Corpora</a>
      <a onclick="state.selectedMode=null;state.corpusOffset=0;refreshMainTab()">${esc(state.selectedCorpus)}</a>
      <span>${esc(state.selectedMode)}</span>
    </div>
    <h2>${esc(state.selectedCorpus)} / ${esc(state.selectedMode)}</h2>
    <p>Total: ${data.total || 0} tests</p>
  `;
  if (data.tests && data.tests.length > 0) {
    html += `<table><thead><tr><th>Stem</th><th>Kind</th></tr></thead><tbody>`;
    for (const t of data.tests) {
      html += `<tr class="clickable" onclick="selectTest('${esc(t.stem)}')">
        <td><code>${esc(t.stem)}</code></td>
        <td>${esc(t.kind)}</td>
      </tr>`;
    }
    html += `</tbody></table>`;
    // Pagination
    const nextOffset = state.corpusOffset + state.corpusLimit;
    if (nextOffset < (data.total || 0)) {
      html += `<button onclick="state.corpusOffset+=${state.corpusLimit};refreshMainTab()">Load more</button>`;
    }
  } else {
    html += `<p class="empty">No tests.</p>`;
  }
  return html;
}

async function selectTest(stem) {
  state.selectedTest = stem;
  await refreshMainTab();
}

async function renderTestView() {
  const params = `model=${encodeURIComponent(state.selectedCorpus)}&mode=${encodeURIComponent(state.selectedMode)}&stem=${encodeURIComponent(state.selectedTest)}`;
  const data = await apiCall('/api/test?' + params);
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `
    <div class="breadcrumb">
      <a onclick="state.selectedCorpus=null;state.selectedMode=null;state.selectedTest=null;refreshMainTab()">Corpora</a>
      <a onclick="state.selectedMode=null;state.selectedTest=null;state.corpusOffset=0;refreshMainTab()">${esc(state.selectedCorpus)}</a>
      <a onclick="state.selectedTest=null;refreshMainTab()">${esc(state.selectedMode)}</a>
      <span>${esc(state.selectedTest)}</span>
    </div>
    <h2>${esc(state.selectedTest)}</h2>
    <p><strong>Kind:</strong> <code>${esc(data.kind)}</code></p>
  `;
  if (data.checker) {
    html += `<p><strong>Checker:</strong> ${esc(data.checker.name)}<br><strong>Criterion:</strong> ${esc(data.checker.criterion)}</p>`;
  }
  if (data.ann) {
    html += `<h3>Annotation</h3><pre class="file-content">${esc(JSON.stringify(data.ann, null, 2))}</pre>`;
  }
  if (data.has) {
    html += `<h3>Files</h3>`;
    if (data.has.xml) {
      html += `<button onclick="loadFile('xml')">View XML</button> `;
    }
    if (data.has.ll) {
      html += `<button onclick="loadFile('ll')">View LLVM IR</button> `;
    }
    if (data.has.s) {
      html += `<button onclick="loadFile('s')">View Assembly</button> `;
    }
    if (data.has.ann) {
      html += `<button onclick="loadFile('ann')">View Annotation</button> `;
    }
    html += `<div id="fileContent"></div>`;
  }
  if (data.has && data.has.xml) {
    html += `<h3>Execution graph</h3>
      <button onclick="openExecGraph('${esc(state.selectedCorpus)}','${esc(state.selectedTest)}')">View execution graph</button>`;
  }
  return html;
}

async function loadFile(kind) {
  const params = `model=${encodeURIComponent(state.selectedCorpus)}&mode=${encodeURIComponent(state.selectedMode)}&stem=${encodeURIComponent(state.selectedTest)}&kind=${kind}`;
  const data = await apiCall('/api/file?' + params);
  if (data.error) {
    document.getElementById('fileContent').innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
  } else {
    const txt = data.text !== undefined ? data.text : (data.html || data.content || '');
    const bar = data.vscode
      ? `<div class="file-bar"><code>${esc(data.path || '')}</code> `
        + `<a class="vscode-link" href="${esc(data.vscode)}">open in VSCode</a></div>`
      : '';
    document.getElementById('fileContent').innerHTML =
      bar + `<pre class="file-content">${esc(txt)}</pre>`;
  }
}

// ====== Utility Tab Renderers ======

async function renderAnnotationChecker() {
  const data = await apiCall('/api/checkers');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3>Checkers by Kind</h3>`;
  for (const kind in data) {
    const c = data[kind];
    html += `
      <div class="card" style="margin-bottom:10px">
        <strong>${esc(kind)}</strong><br>
        <span style="font-size:11px">
          <strong>Checker:</strong> ${esc(c.checker)}<br>
          <strong>Criterion:</strong> ${esc(c.criterion)}
        </span>
      </div>
    `;
  }
  return html;
}

async function renderFanoutTables() {
  const data = await apiCall('/api/tables');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3 style="font-size:12px;margin-top:0">Kinds & Candidates</h3>`;
  if (data.by_kind && data.by_kind.length > 0) {
    html += `<table><thead><tr><th>Kind</th><th>Instruction</th><th>LLVM Op</th></tr></thead><tbody>`;
    for (const k of data.by_kind) {
      for (const cand of (k.candidates || [])) {
        html += `<tr>
          <td>${esc(k.kind)}</td>
          <td><code>${esc(cand.name)}</code></td>
          <td><code>${esc(cand.llvm_op)}</code></td>
        </tr>`;
      }
    }
    html += `</tbody></table>`;
  }
  return html;
}

async function renderLaunchFanout() {
  return `
    <h3 style="font-size:12px;margin-top:0">Launch Fanout Job</h3>
    <div class="form-group">
      <label>Model</label>
      <input type="text" id="launchModel" placeholder="STT_6">
    </div>
    <div class="form-group">
      <label>Config</label>
      <input type="text" id="launchConfig" placeholder="runconfigs/run_config_STT_6.jsonc">
    </div>
    <div class="form-group">
      <button class="primary" onclick="submitLaunch()" style="width:100%">Launch</button>
    </div>
    <div id="launchResult"></div>
  `;
}

async function submitLaunch() {
  const model = document.getElementById('launchModel').value.trim();
  const config = document.getElementById('launchConfig').value.trim();
  if (!model || !config) {
    document.getElementById('launchResult').innerHTML = '<p class="err">Model and config required</p>';
    return;
  }
  const data = await apiCall('/api/launch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'gen', model, config }),
  });
  if (data.error) {
    document.getElementById('launchResult').innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
  } else if (data.ok) {
    document.getElementById('launchResult').innerHTML = `
      <p class="err" style="color:var(--ok)">Job launched: ${esc(data.job_id)}</p>
      <p style="font-size:11px">${esc(data.log || '')}</p>
    `;
  } else {
    document.getElementById('launchResult').innerHTML = `<p class="err">${esc(data.error || 'Unknown error')}</p>`;
  }
}

async function renderExecGraph() {
  // The utility panel is narrow; the diagram itself opens in a full-width modal.
  return `
    <h3 style="font-size:12px;margin-top:0">Execution Graph</h3>
    <p style="font-size:11px;color:var(--muted);margin:0 0 8px">
      Renders an Alloy instance's instructions (program order) with data-flow
      (rf) and taint (ddi) edges. Opens in a full-width overlay. You can also
      reach it from any test in the Corpora tab.</p>
    <div class="form-group">
      <label style="font-size:11px">Model</label>
      <input type="text" id="egModel" placeholder="STT_6" style="width:100%;font-size:11px;padding:3px">
    </div>
    <div class="form-group">
      <label style="font-size:11px">Stem</label>
      <input type="text" id="egStem" placeholder="inst-000123" style="width:100%;font-size:11px;padding:3px">
    </div>
    <button onclick="fetchExecGraph()" style="width:100%;font-size:11px">Open graph</button>
  `;
}

async function fetchExecGraph() {
  const model = document.getElementById('egModel').value.trim();
  const stem = document.getElementById('egStem').value.trim();
  if (!model || !stem) { alert('Model and stem required'); return; }
  openExecGraph(model, stem);
}

// ====== Execution-graph node-link diagram (inline SVG, no external libs) ======
function egPalette(theme) {
  const dark = {
    ld:'#5a9bd4', str:'#c678dd', br_n:'#7c8190', br_x:'#d9b54a',
    other_n:'#56b6c2', other_x:'#e06c5a', unknown:'#9aa0ac',
    boxText:'#e6e9ef', spo:'#5b6270', rf:'#4a90d9', ddi:'#e08a3c',
    xm:'#ffcf4d', boundary:'#d9534f', muted:'#8b92a0'
  };
  const light = {
    ld:'#2b6cb0', str:'#7b3fa0', br_n:'#6b7280', br_x:'#9a6b00',
    other_n:'#217a86', other_x:'#b23b2a', unknown:'#6b7280',
    boxText:'#1a1e24', spo:'#9aa2ae', rf:'#2b6cb0', ddi:'#b4621a',
    xm:'#b8860b', boundary:'#b23b2a', muted:'#5f6772'
  };
  return theme === 'light' ? light : dark;
}

function egLegend() {
  const theme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const P = egPalette(theme);
  const kinds = [['ld','load'],['str','store'],['br_n','branch'],['br_x','branch·xmit'],['other_n','ALU'],['other_x','ALU·xmit']];
  let h = '<div class="eg-legend">';
  for (const [k, lbl] of kinds) h += `<span><i class="eg-swatch" style="background:${P[k]}"></i>${lbl}</span>`;
  h += `<span><i class="eg-swatch" style="background:${P.spo}"></i>spo (program order)</span>`;
  h += `<span><i class="eg-swatch" style="background:${P.rf}"></i>rf (data-flow)</span>`;
  h += `<span><i class="eg-swatch" style="background:${P.ddi}"></i>ddi (taint)</span>`;
  h += `<span style="color:${P.xm};font-weight:bold">⚡ transmitter</span>`;
  h += '</div>';
  return h;
}

function buildExecGraphSVG(data) {
  const theme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const P = egPalette(theme);
  const nodes = (data.nodes || []).slice().sort((a, b) => a.pc - b.pc);
  if (!nodes.length) return '<p class="spin">No nodes in this instance.</p>';
  const edges = data.edges || [];
  const byId = {}, byPc = {};
  nodes.forEach((n, i) => { n._i = i; byId[n.id] = n; byPc[n.pc] = n; });
  const look = k => (byId[k] !== undefined ? byId[k] : byPc[k]);

  const boxW = 170, boxH = 48, ROW = 86, top = 52;
  const spo = edges.filter(e => e.type === 'spo');
  const rf  = edges.filter(e => e.type === 'rf');
  const ddi = edges.filter(e => e.type === 'ddi');
  const bulge = e => { const a = look(e.src), b = look(e.dst); if (!a || !b) return 40;
    return Math.min(160, 30 + Math.abs(a._i - b._i) * 16); };
  const maxRf  = rf.reduce((m, e) => Math.max(m, bulge(e)), 40);
  const maxDdi = ddi.reduce((m, e) => Math.max(m, (look(e.src) === look(e.dst) ? 50 : bulge(e))), 40);
  const PADL = Math.max(120, maxDdi + 40);
  const boxLeft = PADL, boxRight = PADL + boxW, centerX = PADL + boxW / 2;
  const width = Math.ceil(boxRight + maxRf + 44);
  const height = top + nodes.length * ROW + 24;
  const cy = n => top + n._i * ROW + boxH / 2;

  let s = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;font-family:ui-monospace,Menlo,Consolas,monospace">`;
  s += `<defs>
    <marker id="egSpo" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="${P.spo}"/></marker>
    <marker id="egRf"  markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="${P.rf}"/></marker>
    <marker id="egDdi" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="${P.ddi}"/></marker>
  </defs>`;

  // commit boundary (committed is an in-order prefix): divider after last committed pc
  const committed = nodes.filter(n => n.committed);
  if (committed.length) {
    const lc = committed.reduce((m, n) => (n.pc > m.pc ? n : m), committed[0]);
    const fnc = nodes.find(n => n.pc > lc.pc);
    if (fnc) {
      const yB = (cy(lc) + cy(fnc)) / 2;
      s += `<line x1="8" y1="${yB}" x2="${width - 8}" y2="${yB}" stroke="${P.boundary}" stroke-width="1.5" stroke-dasharray="5 4"/>`;
      s += `<text x="12" y="${yB - 5}" fill="${P.boundary}" font-size="10">commit boundary — above: committed (lc) · below: speculative (fnc)</text>`;
    }
  }

  // spo backbone (earlier pc → later pc, arrow points down to the successor)
  spo.forEach(e => {
    const a = look(e.src), b = look(e.dst); if (!a || !b) return;
    const up = a._i < b._i ? a : b, dn = a._i < b._i ? b : a;
    s += `<line x1="${centerX}" y1="${cy(up) + boxH / 2}" x2="${centerX}" y2="${cy(dn) - boxH / 2}" stroke="${P.spo}" stroke-width="2" marker-end="url(#egSpo)"><title>spo: pc${up.pc} → pc${dn.pc}</title></line>`;
  });

  // rf (data-flow) arcs on the right
  rf.forEach(e => {
    const a = look(e.src), b = look(e.dst); if (!a || !b) return;
    const bl = bulge(e), y1 = cy(a), y2 = cy(b);
    s += `<path d="M${boxRight},${y1} Q${boxRight + bl},${(y1 + y2) / 2} ${boxRight},${y2}" fill="none" stroke="${P.rf}" stroke-width="1.6" marker-end="url(#egRf)"><title>rf (data): pc${a.pc} → pc${b.pc}</title></path>`;
  });

  // ddi (taint) arcs on the left; self-taint drawn as a small loop
  ddi.forEach(e => {
    const a = look(e.src), b = look(e.dst); if (!a || !b) return;
    if (a === b) {
      const y = cy(a);
      s += `<path d="M${boxLeft},${y - 10} C${boxLeft - 46},${y - 26} ${boxLeft - 46},${y + 26} ${boxLeft},${y + 10}" fill="none" stroke="${P.ddi}" stroke-width="1.6" marker-end="url(#egDdi)"><title>ddi (self-taint): pc${a.pc}</title></path>`;
    } else {
      const bl = bulge(e), y1 = cy(a), y2 = cy(b);
      s += `<path d="M${boxLeft},${y1} Q${boxLeft - bl},${(y1 + y2) / 2} ${boxLeft},${y2}" fill="none" stroke="${P.ddi}" stroke-width="1.6" marker-end="url(#egDdi)"><title>ddi (taint): pc${a.pc} → pc${b.pc}</title></path>`;
    }
  });

  // nodes on top
  nodes.forEach(n => {
    const y = cy(n) - boxH / 2;
    const col = P[n.kind] || P.unknown;
    const stroke = n.isxm ? P.xm : col;
    const sw = n.isxm ? 3 : 1.4;
    const flags = [];
    flags.push(n.committed ? 'committed' : 'speculative');
    flags.push(n.resolved ? 'resolved' : 'unresolved');
    if (n.isxm) flags.unshift('XMIT');
    s += `<g><title>pc ${n.pc} · ${n.kind}${n.isxm ? ' · TRANSMITTER' : ''} · ${flags.join(' · ')}</title>`;
    s += `<rect x="${boxLeft}" y="${y}" width="${boxW}" height="${boxH}" rx="7" fill="${col}22" stroke="${stroke}" stroke-width="${sw}"/>`;
    s += `<rect x="${boxLeft}" y="${y}" width="5" height="${boxH}" rx="2" fill="${col}"/>`;
    s += `<text x="${boxLeft + 14}" y="${y + 19}" fill="${P.boxText}" font-size="12" font-weight="bold">pc ${n.pc}  ${esc(n.kind)}${n.isxm ? '  ⚡' : ''}</text>`;
    s += `<text x="${boxLeft + 14}" y="${y + 35}" fill="${P.muted}" font-size="10">${esc(flags.join(' · '))}</text>`;
    s += `</g>`;
  });

  s += `</svg>`;
  return s;
}

function buildExecGraphView(data) {
  let h = '';
  if (data.note) h += `<p style="font-size:11px;color:var(--muted);margin:0 0 8px">${esc(data.note)}</p>`;
  h += egLegend();
  h += `<div style="overflow:auto;border:1px solid var(--border);border-radius:8px;padding:8px;background:var(--panel2)">${buildExecGraphSVG(data)}</div>`;
  return h;
}

function ensureEgModal() {
  let m = document.getElementById('egModal');
  if (m) return m;
  const st = document.createElement('style');
  st.textContent = `
    .eg-modal{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:60;display:none;align-items:center;justify-content:center;padding:20px}
    .eg-modal-inner{background:var(--panel);border:1px solid var(--border);border-radius:10px;width:1100px;max-width:96vw;max-height:92vh;display:flex;flex-direction:column;overflow:hidden}
    .eg-modal-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;border-bottom:1px solid var(--border)}
    .eg-modal-head strong{font-size:13px;color:var(--heading)}
    .eg-modal-body{overflow:auto;padding:14px}
    .eg-close{cursor:pointer;background:var(--tab-bg);color:var(--tab-text);border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:12px}
    .eg-legend{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:10px;font-size:11px;color:var(--muted)}
    .eg-legend span{display:inline-flex;align-items:center;gap:5px}
    .eg-swatch{width:12px;height:12px;border-radius:3px;display:inline-block;flex:0 0 auto}`;
  document.head.appendChild(st);
  m = document.createElement('div');
  m.id = 'egModal';
  m.className = 'eg-modal';
  m.innerHTML = `<div class="eg-modal-inner">
      <div class="eg-modal-head">
        <strong id="egModalTitle">Execution graph</strong>
        <button class="eg-close" onclick="closeExecGraph()">✕ close</button>
      </div>
      <div id="egModalBody" class="eg-modal-body"></div>
    </div>`;
  m.addEventListener('click', e => { if (e.target === m) closeExecGraph(); });
  document.body.appendChild(m);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeExecGraph(); });
  // Re-render on theme toggle so SVG colors track the active theme.
  new MutationObserver(() => {
    const mm = document.getElementById('egModal');
    if (mm && mm.style.display === 'flex' && window.__egLast)
      openExecGraph(window.__egLast.model, window.__egLast.stem);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  return m;
}

async function openExecGraph(model, stem) {
  if (!model || !stem) return;
  window.__egLast = { model, stem };
  ensureEgModal();
  document.getElementById('egModalTitle').textContent = `Execution graph — ${model} / ${stem}`;
  const body = document.getElementById('egModalBody');
  body.innerHTML = '<p class="spin">loading…</p>';
  document.getElementById('egModal').style.display = 'flex';
  const data = await apiCall('/api/execgraph?model=' + encodeURIComponent(model) + '&stem=' + encodeURIComponent(stem));
  if (data.error) { body.innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`; return; }
  body.innerHTML = buildExecGraphView(data);
}

function closeExecGraph() {
  const m = document.getElementById('egModal');
  if (m) m.style.display = 'none';
}

async function renderDocs() {
  const data = await apiCall('/api/docs');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3 style="font-size:12px;margin-top:0">Documentation</h3>`;
  if (data.groups && data.groups.length > 0) {
    for (const grp of data.groups) {
      html += `<h4 style="font-size:11px;margin:8px 0 4px">${esc(grp.label)}</h4>`;
      for (const link of (grp.links || [])) {
        html += `<div><a onclick="loadDoc('${esc(link.path)}', '${esc(link.label)}')" style="color:var(--link);cursor:pointer;font-size:11px">${esc(link.label)}</a></div>`;
      }
    }
  }
  html += `<hr style="margin:12px 0;border:none;border-top:1px solid var(--border)">`;
  html += `<button onclick="loadStatusDoc()" style="width:100%;font-size:11px">Load STATUS</button>`;
  return html;
}

async function loadDoc(path, label) {
  const data = await apiCall('/api/md?path=' + encodeURIComponent(path));
  if (data.error) {
    document.getElementById('util').innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
  } else if (data.html) {
    document.getElementById('util').innerHTML = `
      <div style="padding:10px;font-size:11px;overflow-y:auto;height:100%">
        <a onclick="showUtilTab('docs')" style="color:var(--link);cursor:pointer">&larr; back</a>
        ${data.html}
      </div>
    `;
  }
}

async function loadStatusDoc() {
  const data = await apiCall('/api/status?which=code');
  if (data.error) {
    document.getElementById('util').innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
  } else if (data.html) {
    document.getElementById('util').innerHTML = `
      <div style="padding:10px;font-size:11px;overflow-y:auto;height:100%">
        <a onclick="showUtilTab('docs')" style="color:var(--link);cursor:pointer">&larr; back</a>
        ${data.html}
      </div>
    `;
  }
}

// ====== Tab Management ======

function renderMainTabs() {
  let html = '';
  for (const tab of MAIN_TABS) {
    const active = state.activeMainTab === tab.id ? ' active' : '';
    html += `<div class="tab${active}" data-tab="${tab.id}" onclick="switchMainTab('${tab.id}')">${tab.label}</div>`;
  }
  document.getElementById('mainTabs').innerHTML = html;
}

function renderUtilTabs() {
  let html = '';
  for (const tab of UTIL_TABS) {
    const active = state.activeUtilTab === tab.id ? ' active' : '';
    html += `<div class="util-tab${active}" data-tab="${tab.id}" onclick="showUtilTab('${tab.id}')">${tab.label}</div>`;
  }
  document.getElementById('utilTabs').innerHTML = html;
}

function switchMainTab(tabId) {
  state.activeMainTab = tabId;
  localStorage.setItem('activeMainTab', tabId);
  refreshMainTab();
}

async function refreshMainTab() {
  const main = document.getElementById('main');
  main.innerHTML = '<p class="spin">loading…</p>';
  let html = '';
  switch (state.activeMainTab) {
    case 'generation':
      html = await renderGeneration();
      break;
    case 'fanout':
      html = await renderFanout();
      break;
    case 'corpora':
      html = await renderCorpora();
      break;
  }
  main.innerHTML = html;
  stamp();
}

async function showUtilTab(tabId) {
  state.activeUtilTab = tabId;
  localStorage.setItem('activeUtilTab', tabId);
  renderUtilTabs();
  const util = document.getElementById('util');
  util.innerHTML = '<p class="spin">loading…</p>';
  let html = '';
  switch (tabId) {
    case 'annotation':
      html = await renderAnnotationChecker();
      break;
    case 'tables':
      html = await renderFanoutTables();
      break;
    case 'launch':
      html = await renderLaunchFanout();
      break;
    case 'execgraph':
      html = await renderExecGraph();
      break;
    case 'docs':
      html = await renderDocs();
      break;
  }
  util.innerHTML = html;
}

// ====== Initialization ======

function setAutoRefresh() {
  if (state.timer) clearInterval(state.timer);
  const interval = parseInt(document.getElementById('iv').value) || 0;
  state.autoRefreshInterval = interval;
  if (interval > 0) {
    state.timer = setInterval(() => {
      refreshMainTab();
      showUtilTab(state.activeUtilTab);
    }, interval * 1000);
  }
  localStorage.setItem('autoRefreshInterval', interval);
}

function init() {
  // Restore state
  state.activeMainTab = localStorage.getItem('activeMainTab') || 'generation';
  state.activeUtilTab = localStorage.getItem('activeUtilTab') || 'annotation';
  const saved_iv = localStorage.getItem('autoRefreshInterval');
  if (saved_iv !== null) {
    document.getElementById('iv').value = saved_iv;
  }

  // Apply theme
  applyTheme(state.theme);
  document.getElementById('theme').onclick = () => {
    const newTheme = state.theme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
  };

  // Tabs
  renderMainTabs();
  renderUtilTabs();

  // Auto-refresh
  document.getElementById('iv').onchange = setAutoRefresh;
  setAutoRefresh();

  // Focus refresh
  window.addEventListener('focus', () => {
    refreshMainTab();
    showUtilTab(state.activeUtilTab);
  });

  // Load initial
  refreshMainTab();
  showUtilTab(state.activeUtilTab);
}

document.addEventListener('DOMContentLoaded', init);
</script>

</body>
</html>
"""
