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

.main-area {
  padding: 16px 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.utility-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.util-tab {
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  background: var(--tab-bg);
  color: var(--tab-text);
  border: 1px solid var(--border);
  font-size: 12px;
  white-space: nowrap;
}

.util-tab.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
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

/* ---------- Pipeline tab: jobs strip ---------- */
.jobs-strip { margin-bottom: 14px; }
.jobs-strip .badge { font-size: 12px; padding: 3px 9px; }
.jobs-table { margin-top: 10px; }

/* ---------- Pipeline tab: the XML | PROGRAMS | GEM5 grid ---------- */
.pl-grid { display: flex; flex-direction: column; gap: 18px; margin-top: 10px; }
.pl-row {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 12px;
  align-items: start;
}
.pl-row.pl-head {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--muted);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.pl-rowlabel {
  font-weight: 600;
  color: var(--heading);
  padding-top: 8px;
  word-break: break-word;
}
/* The "rest of the row" — a nested 3-col grid (XML/PROGRAMS/GEM5) so a
   defense-unit box can be drawn around just these three cells. */
.pl-rowbody {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  position: relative;
}
.pl-rowbody.unit-box {
  border: 2px solid var(--muted);
  border-radius: 10px;
  padding: 16px 10px 14px;
}
.pl-rowbody.unit-done { border-color: var(--ok); }
.pl-rowbody.unit-inprogress { border-color: var(--warn); }
.unit-badges {
  position: absolute;
  top: -12px;
  right: 10px;
  display: flex;
  gap: 4px;
  z-index: 2;
}
.unit-badge {
  background: var(--panel);
  border: 2px solid var(--ok);
  color: var(--heading);
  border-radius: 50%;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  flex: 0 0 auto;
}
.unit-badge:hover { background: var(--hover); }
.unit-badge.unit-badge-static { cursor: default; border-color: var(--warn); margin-right: 6px; }
.unit-badge.unit-badge-inprogress { border-color: var(--warn); }
.pl-rowbody.unit-inprogress .unit-badge:not(.unit-badge-static) { border-color: var(--warn); }
.unit-status-corner {
  position: absolute;
  bottom: -10px;
  left: 12px;
  background: var(--panel);
  color: var(--muted);
  border: 1px solid var(--border);
  padding: 0 7px;
  font-size: 10px;
  font-weight: 700;
  border-radius: 4px;
  z-index: 2;
}
.pl-col { display: flex; flex-direction: column; gap: 8px; }
.pl-box {
  background: var(--panel);
  border: 1px solid var(--border);
  border-left: 4px solid var(--muted);
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  transition: background 0.15s;
}
.pl-box:hover { background: var(--hover); }
.pl-box.ok { border-left-color: var(--ok); }
.pl-box.bad { border-left-color: var(--err); }
.pl-box.unknown { border-left-color: var(--warn); }
.pl-box.unenum { opacity: .72; border-style: dashed; border-left-style: dashed; border-left-color: var(--muted); }
.pl-defense {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}
.pl-defense.df-stt { background: rgba(90,155,212,.16); color: #5a9bd4; border: 1px solid #5a9bd4; }
.pl-defense.df-spt { background: rgba(198,120,221,.16); color: #c678dd; border: 1px solid #c678dd; }
.pl-defense.df-recon { background: rgba(217,181,74,.16); color: #d9b54a; border: 1px solid #d9b54a; }
.pl-defense.df-unknown { background: rgba(124,129,144,.16); color: var(--muted); border: 1px solid var(--muted); }

/* ---------- gem5 run-detail inspector + hit-categories verdict badges ---------- */
.vb {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: .02em;
  white-space: nowrap;
}
.vb-checker { background: rgba(217,181,74,.18); color: #d9b54a; border: 1px solid #d9b54a; }
.vb-artifact { background: rgba(124,129,144,.18); color: #7c8190; border: 1px solid #7c8190; }
.vb-real_bug { background: rgba(224,108,90,.18); color: #e06c5a; border: 1px solid #e06c5a; }
.vb-new { background: #e0493a; color: #fff; border: 1px solid #e0493a; font-weight: 800; }
.hitcats-legend { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
.run-timing {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 2px 14px;
  font-size: 11px;
  margin-top: 4px;
}
.run-totals { font-size: 14px; }
.run-totals .run-tot-hit { color: var(--err); font-weight: 800; font-size: 18px; }
.run-bucket { cursor: pointer; }
.run-bucket:hover { background: var(--hover); }
.run-bucket-new { border: 2px solid var(--err); }
.run-stem-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 260px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px;
}
.run-stem-row {
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.run-stem-row:hover { background: var(--hover); }
.pl-box-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 2px;
  font-size: 12px;
}
.pl-box-actions { margin-top: 6px; }
.pl-box-actions button { font-size: 11px; padding: 3px 8px; }
.pl-tag {
  font-size: 10px;
  color: var(--ok);
  border: 1px solid var(--ok);
  border-radius: 3px;
  padding: 0 4px;
  white-space: nowrap;
}
.pl-kinds { margin-top: 6px; font-size: 11px; }
.pl-kind-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 1px 0;
  color: var(--muted);
}
.pl-kind-row .pl-hit { color: var(--err); font-weight: 700; }
.pl-orphans {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 460px;
}

/* ---------- To-run panel (defense units with status=="to_run") ---------- */
.to-run-panel {
  border: 2px solid var(--warn);
  border-radius: 10px;
  margin-bottom: 20px;
}
.to-run-card {
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.to-run-card:last-child { margin-bottom: 0; }
.to-run-checklist {
  margin: 6px 0 0;
  padding-left: 20px;
  font-size: 12px;
}
.to-run-checklist li { list-style: "\2610  "; padding: 1px 0; }

/* ---------- Status tab ---------- */
.status-cols { display: flex; gap: 20px; flex-wrap: wrap; }
.status-col { flex: 1 1 420px; min-width: 320px; font-size: 12px; }
.status-col h3 { color: var(--heading); margin-top: 0; }

/* ---------- Generic modal (pipeline inspector / launch form) ---------- */
.u-modal {
  position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 55;
  display: none; align-items: center; justify-content: center; padding: 20px;
}
.u-modal-inner {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  width: 900px; max-width: 96vw; max-height: 92vh;
  display: flex; flex-direction: column; overflow: hidden;
}
.u-modal-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; border-bottom: 1px solid var(--border);
}
.u-modal-head strong { font-size: 13px; color: var(--heading); }
.u-modal-body { overflow: auto; padding: 14px; }
.u-close {
  cursor: pointer; background: var(--tab-bg); color: var(--tab-text);
  border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; font-size: 12px;
}

/* ---------- Execution-graph overlay + legend (used by both the modal and the
   Utilities "XML graph" inline viewer — kept global so both render correctly
   even if the modal has never been opened). ---------- */
.eg-modal {
  position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 60;
  display: none; align-items: center; justify-content: center; padding: 20px;
}
.eg-modal-inner {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  width: 1100px; max-width: 96vw; max-height: 92vh;
  display: flex; flex-direction: column; overflow: hidden;
}
.eg-modal-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; border-bottom: 1px solid var(--border);
}
.eg-modal-head strong { font-size: 13px; color: var(--heading); }
.eg-modal-body { overflow: auto; padding: 14px; }
.eg-close {
  cursor: pointer; background: var(--tab-bg); color: var(--tab-text);
  border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; font-size: 12px;
}
.eg-legend { display: flex; flex-wrap: wrap; gap: 12px 16px; margin-bottom: 10px; font-size: 11px; color: var(--muted); align-items: center; }
.eg-legend span { display: inline-flex; align-items: center; gap: 5px; }
.eg-swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; flex: 0 0 auto; }

@media (max-width: 900px) {
  .pl-row { grid-template-columns: 110px 1fr; }
}

@media (max-width: 700px) {
  .main-tabs { gap: 3px; }
  .tab { padding: 4px 8px; font-size: 12px; }
  .pl-row { grid-template-columns: 1fr; }
  .pl-rowbody { grid-template-columns: 1fr; }
  .pl-row.pl-head { display: none; }
  .status-cols { flex-direction: column; }
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

<div class="main-area" id="main"></div>

<script>
// ====== State & Config ======
let state = {
  activeMainTab: 'pipeline',
  activeUtilTab: 'annotation',
  theme: localStorage.getItem('theme') || 'dark',
  autoRefreshInterval: 30,
  timer: null,
  pipelineTimer: null,
  // Corpora drill-down state (reused inside the Pipeline inspector modal)
  selectedCorpus: null,
  selectedMode: null,
  selectedTest: null,
  corpusOffset: 0,
  corpusLimit: 200,
};

// Last /api/pipeline payload — box onclick handlers look nodes up here by
// model/id rather than serializing JSON into HTML attributes.
let PL_DATA = null;

// Default model/stem so the graph utils are click-to-visualize (and auto-render).
const DEFAULT_MODEL = 'STT_6';
const DEFAULT_STEM = 'inst-000001';

const MAIN_TABS = [
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'status', label: 'Status' },
  { id: 'utilities', label: 'Utilities' },
];

const UTIL_TABS = [
  { id: 'annotation', label: 'Annotation / Check' },
  { id: 'tables', label: 'Fanout Tables' },
  { id: 'launch', label: 'Launch Fanout' },
  { id: 'execgraph', label: 'Execution Graph' },
  { id: 'alloymodels', label: 'Alloy models' },
  { id: 'gem5builds', label: 'gem5 builds' },
  { id: 'hookreg', label: 'Hooks (purposes)' },
  { id: 'docs', label: 'Docs' },
  { id: 'specs', label: 'Sources of Truth' },
  { id: 'runconfigs', label: 'Run configs' },
  { id: 'gem5hooks', label: 'gem5 hooks (files)' },
  { id: 'findings', label: 'Findings' },
  { id: 'hitcats', label: 'Hit categories' },
  { id: 'xmlviz', label: 'XML graph' },
];

// Last /api/models payload (every .als on disk, enumerated or not) — joined
// with PL_DATA by model name to build the Pipeline grid rows.
let MODELS_DATA = null;

// Last /api/defense_units payload — the (leakage-defense × gem5-implementation)
// registry. Drives the outlined unit-boxes on the Pipeline grid, the to-run
// panel, and the Status-tab rollup.
let DEFENSE_UNITS_DATA = null;

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

// ====== stub action (Regen XML / Run on build — not implemented yet) ======
function stubAction(label) {
  alert(label + ': coming soon (stub).');
}

// ====== Legacy main-tab renderers (superseded by the Pipeline tab, kept for reuse) ======
// renderGeneration()/renderFanout() predate the unified /api/pipeline view; the
// Pipeline tab below folds in everything they showed (xml progress, per-mode
// fanout counts, gem5 hits, jobs). Preserved rather than deleted in case a future
// narrower view wants them again.

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

// ====== Corpus drill-down (reused inside the Pipeline inspector modal) ======
// These render functions used to live under a top-level "Corpora" tab; that tab
// is gone (Pipeline/Status/Utilities replace it), but the XML and PROGRAMS boxes
// on the Pipeline tab open these same views inside the inspector modal — see
// refreshInspectorBody() below. Their internal navigation targets the modal
// (refreshInspectorBody) instead of the old full-page main tab.

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
  await refreshInspectorBody();
}

async function renderCorpusView() {
  const data = await apiCall('/api/corpus?model=' + encodeURIComponent(state.selectedCorpus));
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `
    <div class="breadcrumb">
      <span>${esc(state.selectedCorpus)}</span>
    </div>
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
  } else {
    html += `<p class="empty">No modes on disk yet.</p>`;
  }
  return html;
}

async function selectMode(mode) {
  state.selectedMode = mode;
  state.selectedTest = null;
  state.corpusOffset = 0;
  await refreshInspectorBody();
}

async function renderModeView() {
  const data = await apiCall('/api/corpus?model=' + encodeURIComponent(state.selectedCorpus) + '&mode=' + encodeURIComponent(state.selectedMode) + '&offset=' + state.corpusOffset + '&limit=' + state.corpusLimit);
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `
    <div class="breadcrumb">
      <a onclick="state.selectedMode=null;refreshInspectorBody()">${esc(state.selectedCorpus)}</a>
      <span>${esc(state.selectedMode)}</span>
    </div>
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
      html += `<button onclick="state.corpusOffset+=${state.corpusLimit};refreshInspectorBody()">Load more</button>`;
    }
  } else {
    html += `<p class="empty">No tests.</p>`;
  }
  return html;
}

async function selectTest(stem) {
  state.selectedTest = stem;
  await refreshInspectorBody();
}

async function renderTestView() {
  const params = `model=${encodeURIComponent(state.selectedCorpus)}&mode=${encodeURIComponent(state.selectedMode)}&stem=${encodeURIComponent(state.selectedTest)}`;
  const data = await apiCall('/api/test?' + params);
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `
    <div class="breadcrumb">
      <a onclick="state.selectedMode=null;state.selectedTest=null;state.corpusOffset=0;refreshInspectorBody()">${esc(state.selectedCorpus)}</a>
      <a onclick="state.selectedTest=null;refreshInspectorBody()">${esc(state.selectedMode)}</a>
      <span>${esc(state.selectedTest)}</span>
    </div>
    <h3 style="margin-top:0">${esc(state.selectedTest)}</h3>
    <p><strong>Kind:</strong> <code>${esc(data.kind)}</code></p>
  `;
  if (data.checker) {
    html += `<p><strong>Checker:</strong> ${esc(data.checker.name)}<br><strong>Criterion:</strong> ${esc(data.checker.criterion)}</p>`;
  }
  if (data.ann) {
    html += `<h4>Annotation</h4><pre class="file-content">${esc(JSON.stringify(data.ann, null, 2))}</pre>`;
  }
  if (data.has) {
    html += `<h4>Files</h4>`;
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
    html += `<h4>Execution graph</h4>
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

// ====== Generic modal (pipeline inspector + launch-fanout form) ======

function ensureUModal() {
  let m = document.getElementById('uModal');
  if (m) return m;
  m = document.createElement('div');
  m.id = 'uModal';
  m.className = 'u-modal';
  m.innerHTML = `<div class="u-modal-inner">
      <div class="u-modal-head">
        <strong id="uModalTitle">—</strong>
        <button class="u-close" onclick="closeUModal()">✕ close</button>
      </div>
      <div id="uModalBody" class="u-modal-body"></div>
    </div>`;
  m.addEventListener('click', e => { if (e.target === m) closeUModal(); });
  document.body.appendChild(m);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeUModal(); });
  return m;
}

function openUModal(title) {
  ensureUModal();
  document.getElementById('uModalTitle').textContent = title;
  document.getElementById('uModal').style.display = 'flex';
}

function closeUModal() {
  const m = document.getElementById('uModal');
  if (m) m.style.display = 'none';
}

async function openLaunchModal() {
  openUModal('Launch new fanout');
  document.getElementById('uModalBody').innerHTML = await renderLaunchFanout();
}

// ---- Pipeline inspector: XML / PROGRAMS boxes reuse the corpus drill-down ----

async function refreshInspectorBody() {
  const body = document.getElementById('inspBody');
  if (!body) return;
  body.innerHTML = '<p class="spin">loading…</p>';
  let html = '';
  if (state.selectedTest) html = await renderTestView();
  else if (state.selectedMode) html = await renderModeView();
  else if (state.selectedCorpus) html = await renderCorpusView();
  body.innerHTML = html;
}

function defenseFamilyClass(fam) {
  if (!fam) return 'df-unknown';
  if (fam.indexOf('STT') === 0) return 'df-stt';
  if (fam.indexOf('SPT') === 0) return 'df-spt';
  if (fam.indexOf('Recon') === 0) return 'df-recon';
  return 'df-unknown';
}

// XML box click → the .als source (name/defense_family/instr_scope/transmitters
// via /api/model) is the headline; if the model also has a live testset
// (pl != null) the existing corpus drill-down is appended below it.
async function openXmlInspector(model, pl, inv) {
  openUModal('XML — ' + model);
  const xml = pl ? (pl.xml || {}) : null;
  const completeTxt = xml && xml.complete === true ? 'yes'
    : xml && xml.complete === false ? 'no (hit cap)' : 'unknown';
  const defenseTag = inv && inv.defense_family
    ? `<span class="pl-defense ${defenseFamilyClass(inv.defense_family)}">${esc(inv.defense_family)}</span>` : '';
  const isUnenum = !!(inv && !inv.enumerated);
  let meta = `<div class="card">
    ${defenseTag ? `<div style="margin-bottom:6px">${defenseTag}</div>` : ''}
    <div class="card-meta">
      <strong>model:</strong> ${esc(model)}<br>
      ${inv ? `<strong>instr scope:</strong> ${esc(inv.instr_scope || '?')}<br>
      <strong>transmitters:</strong> <code>${esc(inv.transmitters || '?')}</code><br>
      <strong>bytes:</strong> ${inv.bytes || 0}<br>
      ${inv.symlink_target ? `<strong>symlink:</strong> &rarr; ${esc(inv.symlink_target)}<br>` : ''}` : ''}
      ${xml ? `<strong>instances:</strong> ${xml.instances || 0}${xml.cap ? ' / ' + xml.cap : ''}<br>
      <strong>complete:</strong> ${completeTxt}<br>
      <strong>live:</strong> ${xml.live ? 'yes' + (xml.etime ? ' (' + esc(xml.etime) + ')' : '') : 'no'}<br>
      <strong>provenance:</strong> ${xml.has_provenance ? 'yes' : 'no'}<br>`
      : '<strong>enumerated:</strong> no<br>'}
    </div>
    <div style="margin-top:8px">
      <button onclick="stubAction('${isUnenum ? 'Enumerate' : 'Regen XML'} — ${esc(model)}')">${isUnenum ? 'Enumerate (stub)' : 'Regen XML (stub)'}</button>
    </div>
  </div>
  <div class="card" id="xmlInstancesBody"><p class="spin">loading instances…</p></div>
  <div id="alsSourceBody"><p class="spin">loading .als source…</p></div>`;
  if (pl) meta += `<div id="inspBody"><p class="spin">loading…</p></div>`;
  document.getElementById('uModalBody').innerHTML = meta;
  loadAlsSource(model);
  loadXmlInstancesList(model);
  if (pl) {
    state.selectedCorpus = model;
    state.selectedMode = null;
    state.selectedTest = null;
    refreshInspectorBody();
  }
}

// Instances section: a dropdown of the first N generated XML-instance stems
// for this model, so Anna can inspect one right from the XML-card inspector.
async function loadXmlInstancesList(model) {
  const target = document.getElementById('xmlInstancesBody');
  if (!target) return;
  const data = await apiCall('/api/xml_instances?model=' + encodeURIComponent(model) + '&limit=50');
  if (data.error || !data.ok) {
    target.innerHTML = `<h4 style="margin:0 0 4px">Instances</h4>
      <p class="err">Error: ${esc(data.error || 'could not list instances')}</p>`;
    return;
  }
  const stems = data.stems || [];
  const total = data.total || 0;
  if (!total) {
    target.innerHTML = `<h4 style="margin:0 0 4px">Instances</h4><p class="empty">no instances generated yet</p>`;
    return;
  }
  const opts = stems.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  target.innerHTML = `<h4 style="margin:0 0 4px">Instances</h4>
    <div class="card-meta" style="margin-bottom:6px">first ${stems.length} of ${total}</div>
    <select onchange="loadXmlInstance('${esc(model)}', this.value)">
      <option value="">— choose an instance —</option>
      ${opts}
    </select>
    <div id="xmlInstBody" style="margin-top:10px"></div>`;
}

async function loadXmlInstance(model, stem) {
  const target = document.getElementById('xmlInstBody');
  if (!target) return;
  if (!stem) { target.innerHTML = ''; return; }
  target.innerHTML = '<p class="spin">loading…</p>';
  const data = await apiCall('/api/file?model=' + encodeURIComponent(model)
    + '&stem=' + encodeURIComponent(stem) + '&kind=xml');
  if (data.error) {
    target.innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
    return;
  }
  const txt = data.text !== undefined ? data.text : (data.html || data.content || '');
  const bar = data.vscode
    ? `<div class="file-bar"><code>${esc(data.path || '')}</code> `
      + `<a class="vscode-link" href="${esc(data.vscode)}">open in VSCode</a></div>`
    : '';
  target.innerHTML = `${bar}<pre class="file-content">${esc(txt)}</pre>
    <div style="margin-top:6px">
      <button onclick="stubAction('graph for ${esc(stem)}')">View as graph</button>
    </div>`;
}

async function loadAlsSource(model) {
  const data = await apiCall('/api/model?name=' + encodeURIComponent(model));
  const target = document.getElementById('alsSourceBody');
  if (!target) return;
  if (data.error || !data.ok) {
    target.innerHTML = `<p class="err">Error: ${esc(data.error || 'not found')}</p>`;
    return;
  }
  const bar = data.vscode
    ? `<div class="file-bar"><code>${esc(data.path || '')}</code> `
      + `<a class="vscode-link" href="${esc(data.vscode)}">open in VSCode</a></div>`
    : '';
  target.innerHTML = `<h4 style="margin:10px 0 4px">.als source</h4>${bar}<pre class="file-content">${esc(data.text || '')}</pre>`;
}

function openProgramInspector(m, p) {
  const label = p.mode || p.fanout || p.id;
  openUModal('Programs — ' + m.model + ' / ' + label);
  const meta = `<div class="card">
    <div class="card-meta">
      <strong>llvm:</strong> ${p.llvm || 0} &nbsp; <strong>asm:</strong> ${p.asm || 0} &nbsp;
      <strong>ann:</strong> ${p.ann || 0} &nbsp; <strong>expected:</strong> ${p.expected || 0}<br>
      ${p.dirty ? '<span class="badge stale">stale — parent XML changed since this was built</span>' : ''}
    </div>
    <div style="margin-top:8px"><button onclick="stubAction('Run on build — ${esc(label)}')">Run on build (stub)</button></div>
  </div>`;
  document.getElementById('uModalBody').innerHTML = meta + `<div id="inspBody"><p class="spin">loading…</p></div>`;
  if (p.mode) {
    state.selectedCorpus = m.model;
    state.selectedMode = p.mode;
    state.selectedTest = null;
    state.corpusOffset = 0;
    refreshInspectorBody();
  } else {
    document.getElementById('inspBody').innerHTML =
      '<p class="empty">Instance-level browsing for fanout-layout programs is a stub — coming soon.</p>';
  }
}

// Minimal fallback when /api/run has no data for this campaign (e.g. running
// on a checkout with no results/ — the rich viewer only has data once deployed
// on the box that ran the sweep). Falls back to the summary pipeline_graph()
// already gave us for this gem5 node.
function renderGem5FallbackHtml(g, errMsg) {
  let rows = '';
  for (const mo of (g.modes || [])) {
    for (const k of (mo.kinds || [])) {
      const hits = k.hits || 0;
      const hitsHtml = hits > 0 ? `<strong style="color:var(--err)">${hits}</strong>` : String(hits);
      rows += `<tr><td>${esc(mo.mode)}</td><td>${esc(k.kind || '-')}</td><td>${k.total || 0}</td><td>${hitsHtml}</td></tr>`;
    }
  }
  return `<p class="card-meta" style="margin-top:0">Run detail unavailable${errMsg ? ': ' + esc(errMsg) : ''} — showing the summary from the Pipeline grid instead.</p>
    <div class="card">
      <div class="card-meta">
        <strong>results_name:</strong> ${esc(g.results_name || '')}<br>
        <strong>model:</strong> ${esc(g.model || '')}<br>
        <strong>campaign:</strong> ${esc(g.campaign || '')}<br>
        <strong>gem5_binary:</strong> ${esc(g.gem5_binary || '')}<br>
        <strong>variant:</strong> ${esc(g.variant || '')}<br>
        <strong>started_at:</strong> ${esc(g.started_at || '')}
      </div>
    </div>
    <table><thead><tr><th>Mode</th><th>Kind</th><th>Total</th><th>Hits</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="empty">no results yet</td></tr>'}</tbody></table>`;
}

// The rich run-monitor-equivalent view: header/timing provenance, totals,
// hits-by-mode×kind, and the categorized-hit buckets (joined to the
// hit_categories registry) with click-to-drill-in stem lists.
function buildRunDetailHtml(data) {
  const timingEntries = Object.entries(data.timing || {});
  const timingHtml = timingEntries.length
    ? `<div class="run-timing">${timingEntries.map(([k, v]) =>
        `<div><strong>${esc(k)}:</strong> <code>${esc(String(v))}</code></div>`).join('')}</div>`
    : '<p class="card-meta" style="margin:4px 0 0">(no timing config recorded)</p>';

  let html = `<div class="card">
    <div class="card-meta">
      <strong>results_name:</strong> ${esc(data.results_name || '')}<br>
      <strong>model:</strong> ${esc(data.model || '')}<br>
      <strong>variant:</strong> ${esc(data.variant || '')}<br>
      <strong>gem5_binary:</strong> ${esc(data.gem5_binary || '')}<br>
      <strong>campaign:</strong> ${esc(data.campaign || '')}<br>
      <strong>started_at:</strong> ${esc(data.started_at || '')}
    </div>
    <h4 style="margin:10px 0 2px">Timing config</h4>
    ${timingHtml}
  </div>`;

  const totHits = data.total_hits || 0;
  html += `<div class="card run-totals">
    <span class="${totHits > 0 ? 'run-tot-hit' : ''}">${totHits} hits</span> / ${data.total_records || 0} records
  </div>`;

  // Hits by mode × kind — the old run-monitor table.
  const modes = data.modes || [];
  const kindsSet = new Set();
  for (const m of modes) for (const k of (m.kinds || [])) kindsSet.add(k.kind || '-');
  const kindsList = [...kindsSet];
  html += `<h4 style="margin:16px 0 4px">Hits by mode &times; kind</h4>`;
  if (!modes.length || !kindsList.length) {
    html += `<p class="empty">No per-mode data.</p>`;
  } else {
    html += `<table><thead><tr><th>Mode</th>${kindsList.map(k => `<th>${esc(k)}</th>`).join('')}</tr></thead><tbody>`;
    for (const m of modes) {
      const byKind = {};
      for (const k of (m.kinds || [])) byKind[k.kind || '-'] = k;
      html += `<tr><td>${esc(m.mode)}</td>`;
      for (const k of kindsList) {
        const rec = byKind[k];
        const hits = rec ? (rec.hits || 0) : 0;
        const total = rec ? (rec.total || 0) : 0;
        const cell = `${hits}/${total}`;
        html += `<td>${hits > 0 ? `<strong style="color:var(--err)">${cell}</strong>` : cell}</td>`;
      }
      html += `</tr>`;
    }
    html += `</tbody></table>`;
  }

  // Categorized hits (diagnostics/buckets joined to the hit_categories registry).
  html += `<h4 style="margin:18px 0 4px">Categorized hits</h4>`;
  if (!data.has_diagnostics) {
    html += `<p class="empty">no diagnostics bucketing for this run yet.</p>`;
  } else if (!data.buckets || !data.buckets.length) {
    html += `<p class="empty">No buckets recorded.</p>`;
  } else {
    html += `<div id="runBucketsBody">`;
    for (const b of data.buckets) {
      const emphasize = b.category === 'NEW_candidate_pure_bug' || b.verdict === 'new';
      const vb = `<span class="vb vb-${esc(b.verdict || '')}">${esc(b.verdict || '?')}</span>`;
      let writeup = '';
      if (b.bug_md) {
        writeup = String(b.bug_md).endsWith('.md')
          ? `<a onclick="event.stopPropagation(); loadRunBucketWriteup('${esc(b.bug_md)}')" style="color:var(--link);cursor:pointer">open writeup</a>`
          : `<code>${esc(b.bug_md)}</code>`;
      }
      html += `<div class="card run-bucket${emphasize ? ' run-bucket-new' : ''}" onclick="loadRunHits('${esc(data.results_name)}','${esc(b.category)}','${esc(data.model || '')}')">
        <div class="pl-box-top"><strong>${b.count}</strong>&nbsp;<span>${esc(b.label || b.category)}</span>${vb}</div>
        <div class="card-meta">${esc(b.description || '')}${writeup ? ' &middot; ' + writeup : ''}</div>
      </div>`;
    }
    html += `</div><div id="runHitsBody" style="margin-top:10px"></div>`;
  }
  return html;
}

// bucket drill-in: /api/run_hits now returns stems as {stem, mode} objects
// (not bare strings) — each row is clickable and shows that test's program.
async function loadRunHits(name, bucket, model) {
  const target = document.getElementById('runHitsBody');
  if (!target) return;
  target.innerHTML = '<p class="spin">loading…</p>';
  const data = await apiCall('/api/run_hits?name=' + encodeURIComponent(name)
    + '&bucket=' + encodeURIComponent(bucket) + '&limit=500');
  if (data.error || !data.ok) {
    target.innerHTML = `<p class="err">Error: ${esc(data.error || 'unavailable')}</p>`;
    return;
  }
  const stems = data.stems || [];
  const note = (data.total || 0) > stems.length
    ? `total ${data.total}, showing first ${stems.length}` : `${data.total || 0} stem(s)`;
  const rows = stems.map(s => {
    const stem = (s && typeof s === 'object') ? (s.stem || '') : (s || '');
    const mode = (s && typeof s === 'object') ? (s.mode || '') : '';
    return `<div class="run-stem-row" onclick="loadRunStemProgram('${esc(model || '')}','${esc(mode)}','${esc(stem)}')">
      <code>${esc(stem)}</code>${mode ? ` <span class="card-meta">(${esc(mode)})</span>` : ''}
    </div>`;
  }).join('');
  target.innerHTML = `<h4 style="margin:6px 0 4px">${esc(bucket)} &mdash; ${esc(note)}</h4>
    <div class="run-stem-list">${rows || '<p class="empty">no stems</p>'}</div>
    <div id="runProgramBody" style="margin-top:10px"></div>`;
}

// Stem click → the PROGRAM (assembly) for that test, reusing the same
// /api/file + file-bar/vscode-link rendering as the corpus file viewer.
async function loadRunStemProgram(model, mode, stem) {
  const target = document.getElementById('runProgramBody');
  if (!target) return;
  target.innerHTML = '<p class="spin">loading…</p>';
  const data = await apiCall('/api/file?model=' + encodeURIComponent(model)
    + '&mode=' + encodeURIComponent(mode) + '&stem=' + encodeURIComponent(stem) + '&kind=s');
  if (data.error) {
    target.innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
    return;
  }
  const txt = data.text !== undefined ? data.text : (data.html || data.content || '');
  const bar = data.vscode
    ? `<div class="file-bar"><code>${esc(data.path || '')}</code> `
      + `<a class="vscode-link" href="${esc(data.vscode)}">open in VSCode</a></div>`
    : '';
  target.innerHTML = `<h4 style="margin:6px 0 4px">${esc(stem)} &mdash; program</h4>
    ${bar}<pre class="file-content">${esc(txt)}</pre>
    <div style="margin-top:6px">
      <button onclick="stubAction('exec graph for ${esc(stem)}')">View execution graph</button>
    </div>`;
}

async function loadRunBucketWriteup(path) {
  const target = document.getElementById('runHitsBody');
  if (!target) return;
  target.innerHTML = '<p class="spin">loading…</p>';
  const data = await apiCall('/api/md?path=' + encodeURIComponent(path));
  target.innerHTML = (data && data.html) ? data.html : `<p class="err">Could not load ${esc(path)}</p>`;
}

async function openGem5Inspector(g) {
  openUModal('gem5 — ' + (g.variant || g.results_name || ''));
  document.getElementById('uModalBody').innerHTML = '<p class="spin">loading…</p>';
  const data = await apiCall('/api/run?name=' + encodeURIComponent(g.results_name || ''));
  if (!data || data.error || !data.ok) {
    document.getElementById('uModalBody').innerHTML =
      renderGem5FallbackHtml(g, (data && data.error) || 'no run detail found');
    return;
  }
  document.getElementById('uModalBody').innerHTML = buildRunDetailHtml(data);
}

function openInspector(kind, model, id) {
  if (kind === 'xml') {
    const pl = PL_DATA && (PL_DATA.models || []).find(x => x.model === model);
    const inv = MODELS_DATA && (MODELS_DATA.models || []).find(x => x.name === model);
    if (pl || inv) openXmlInspector(model, pl || null, inv || null);
    return;
  }
  if (!PL_DATA) return;
  const m = (PL_DATA.models || []).find(x => x.model === model);
  if (kind === 'program') {
    if (!m) return;
    const p = (m.programs || []).find(x => x.id === id);
    if (p) openProgramInspector(m, p);
    return;
  }
  if (kind === 'gem5') {
    let node = null;
    if (m) node = (m.gem5 || []).find(x => x.id === id);
    if (!node) node = (PL_DATA.gem5_orphans || []).find(x => x.id === id);
    if (node) openGem5Inspector(node);
  }
}

// ====== Pipeline tab (the centerpiece) ======

function renderJobsStrip(jobs) {
  const counts = { running: 0, stale: 0, done: 0, failed: 0 };
  for (const j of (jobs || [])) {
    const s = j.status || 'done';
    if (counts[s] !== undefined) counts[s]++;
  }
  let html = `<div class="jobs-strip">
    <span class="badge running">${counts.running} running</span>
    <span class="badge stale">${counts.stale} stale</span>
    <span class="badge done">${counts.done} done</span>
    <span class="badge failed">${counts.failed} failed</span>
  </div>`;
  const active = (jobs || []).filter(j => j.status === 'running' || j.status === 'stale');
  if (active.length) {
    html += `<table class="jobs-table"><thead><tr><th>Kind</th><th>Model</th><th>Status</th><th>Started</th></tr></thead><tbody>`;
    for (const j of active) {
      html += `<tr><td>${esc(j.kind)}</td><td>${esc(j.model)}</td>
        <td><span class="badge ${esc(j.status)}">${esc(j.status)}</span></td>
        <td>${esc(j.started_at || '')}</td></tr>`;
    }
    html += `</tbody></table>`;
  }
  return `<div class="card" id="jobsStrip">${html}</div>`;
}

// row = { model, pl (that model's /api/pipeline node, or null), inv (that
// model's /api/models inventory record, or null) } — see mergeModelRows().
function xmlBoxHtml(row) {
  const model = row.model;
  const inv = row.inv;
  const pl = row.pl;
  const defenseTag = inv && inv.defense_family
    ? `<span class="pl-defense ${defenseFamilyClass(inv.defense_family)}">${esc(inv.defense_family)}</span>` : '';
  const scopeLine = inv && inv.instr_scope
    ? `<div class="card-meta">${esc(inv.instr_scope)}</div>` : '';
  const symlinkLine = inv && inv.symlink_target
    ? `<div class="card-meta">&rarr; ${esc(inv.symlink_target)}</div>` : '';

  // Never enumerated: no testset on disk at all (xml_count 0 per /api/models).
  if (inv && !inv.enumerated) {
    return `<div class="pl-box unknown unenum" onclick="openInspector('xml','${esc(model)}')">
      <div class="pl-box-top"><strong>${esc(model)}</strong> ${defenseTag}</div>
      ${scopeLine}${symlinkLine}
      <div class="card-meta">not enumerated</div>
      <div class="pl-box-actions">
        <button onclick="event.stopPropagation(); stubAction('Enumerate — ${esc(model)}')">Enumerate</button>
      </div>
    </div>`;
  }

  const xml = pl ? (pl.xml || {}) : {};
  const cap = xml.cap || 0;
  const pct = cap > 0 ? Math.min(100, Math.round(100 * (xml.instances || 0) / cap)) : 0;
  let cls = 'unknown';
  if (xml.complete === true) cls = 'ok';
  else if (xml.complete === false) cls = 'bad';
  const liveBadge = xml.live
    ? `<span class="badge running">running${xml.etime ? ' · ' + esc(xml.etime) : ''}</span>` : '';
  const prov = xml.has_provenance ? '<span class="pl-tag">provenance ✓</span>' : '';
  const instances = xml.instances !== undefined ? xml.instances : (inv ? (inv.xml_count || 0) : 0);
  return `<div class="pl-box ${cls}" onclick="openInspector('xml','${esc(model)}')">
    <div class="pl-box-top"><strong>${esc(model)}</strong> ${defenseTag} ${liveBadge}</div>
    ${scopeLine}${symlinkLine}
    <div class="card-meta">${instances}${cap ? ' / ' + cap : ''} instances ${prov}</div>
    ${cap ? `<div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>` : ''}
    <div class="pl-box-actions">
      <button onclick="event.stopPropagation(); stubAction('Regen XML — ${esc(model)}')">Regen XML</button>
    </div>
  </div>`;
}

function programBoxHtml(model, p) {
  const label = p.mode || p.fanout || p.id;
  const expected = p.expected || 0;
  const pct = expected > 0 ? Math.min(100, Math.round(100 * (p.asm || 0) / expected)) : 0;
  const dirty = p.dirty
    ? `<span class="badge stale" title="parent XML changed since this was built">stale</span>` : '';
  return `<div class="pl-box ${p.dirty ? 'bad' : 'ok'}" onclick="openInspector('program','${esc(model)}','${esc(p.id)}')">
    <div class="pl-box-top"><strong>${esc(label)}</strong> ${dirty}</div>
    <div class="card-meta">llvm ${p.llvm || 0} &middot; asm ${p.asm || 0} &middot; ann ${p.ann || 0}${expected ? ' / ' + expected : ''}</div>
    ${expected ? `<div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>` : ''}
    <div class="pl-box-actions">
      <button onclick="event.stopPropagation(); stubAction('Run on build — ${esc(label)}')">Run on build</button>
    </div>
  </div>`;
}

function gem5BoxHtml(g) {
  let kindsHtml = '';
  let anyHit = false;
  for (const mo of (g.modes || [])) {
    for (const k of (mo.kinds || [])) {
      const hits = k.hits || 0;
      if (hits > 0) anyHit = true;
      const cls = hits > 0 ? 'pl-hit' : '';
      kindsHtml += `<div class="pl-kind-row"><span>${esc(mo.mode)} / ${esc(k.kind || '-')}</span>
        <span class="${cls}">${hits}/${k.total || 0}</span></div>`;
    }
  }
  return `<div class="pl-box ${anyHit ? 'bad' : 'ok'}" onclick="openInspector('gem5','${esc(g.model || '')}','${esc(g.id)}')">
    <div class="pl-box-top"><strong>${esc(g.variant || g.campaign || g.results_name)}</strong></div>
    <div class="card-meta">${esc(g.gem5_binary || '')}<br>started ${esc(g.started_at || 'N/A')}</div>
    <div class="pl-kinds">${kindsHtml || '<span class="muted">no results yet</span>'}</div>
  </div>`;
}

// Union of /api/pipeline's models[] (testsets that exist on disk) and
// /api/models' models[] (every .als source, enumerated or not), keyed by
// model name, so un-enumerated models are visible too.
function mergeModelRows(pipelineData, modelsData) {
  const plByName = {};
  for (const m of ((pipelineData && pipelineData.models) || [])) plByName[m.model] = m;
  const invByName = {};
  for (const m of ((modelsData && modelsData.models) || [])) invByName[m.name] = m;
  const names = new Set([...Object.keys(plByName), ...Object.keys(invByName)]);
  const rows = [...names].sort().map(name => ({
    model: name,
    pl: plByName[name] || null,
    inv: invByName[name] || null,
    programs: (plByName[name] && plByName[name].programs) || [],
    gem5: (plByName[name] && plByName[name].gem5) || [],
  }));
  return rows;
}

// Groups defense_units[] by alloy_model, so a model row can draw a box for
// each of the (possibly several) units it backs.
function unitsByModel(units) {
  const map = {};
  for (const u of (units || [])) {
    if (!u.alloy_model) continue;
    (map[u.alloy_model] = map[u.alloy_model] || []).push(u);
  }
  return map;
}

function renderPipelineGrid(rows, unitsMap) {
  if (!rows || !rows.length) {
    return '<p class="empty">No Alloy models found.</p>';
  }
  unitsMap = unitsMap || {};
  let html = `<div class="pl-grid">`;
  html += `<div class="pl-row pl-head">
    <div>Model</div>
    <div class="pl-rowbody"><div>XML</div><div>PROGRAMS</div><div>GEM5</div></div>
  </div>`;
  for (const row of rows) {
    const units = unitsMap[row.model] || [];
    // Only done/in_progress units get the visible row box — to_run units live
    // in the to-run panel above the grid instead.
    const boxUnits = units.filter(u => u.status === 'done' || u.status === 'in_progress').sort((a, b) => a.number - b.number);
    let bodyCls = 'pl-rowbody';
    let cornerHtml = '';
    if (boxUnits.length) {
      const anyInProgress = boxUnits.some(u => u.status === 'in_progress');
      bodyCls += anyInProgress ? ' unit-box unit-inprogress' : ' unit-box unit-done';
      const badges = boxUnits.map(u =>
        `<span class="unit-badge" title="unit ${u.number}: ${esc(u.defense || '')} — ${esc(u.status)}" onclick="openUnitInspector(${u.number})">${u.number}</span>`
      ).join('');
      const statusTxt = [...new Set(boxUnits.map(u => u.status))].join(' / ');
      cornerHtml = `<div class="unit-badges">${badges}</div>
        <div class="unit-status-corner">${esc(statusTxt)}</div>`;
    }
    html += `<div class="pl-row">`;
    html += `<div class="pl-rowlabel">${esc(row.model)}</div>`;
    html += `<div class="${bodyCls}">
      ${cornerHtml}
      <div class="pl-col">${xmlBoxHtml(row)}</div>
      <div class="pl-col">${row.programs.map(p => programBoxHtml(row.model, p)).join('')
        || '<p class="empty" style="padding:4px">none</p>'}</div>
      <div class="pl-col">${row.gem5.map(g => gem5BoxHtml(g)).join('')
        || '<p class="empty" style="padding:4px">none</p>'}</div>
    </div>`;
    html += `</div>`;
  }
  html += `</div>`;
  return html;
}

// Unit-badge click → full unit detail (the three criteria specs + results).
function openUnitInspector(number) {
  const units = (DEFENSE_UNITS_DATA && DEFENSE_UNITS_DATA.units) || [];
  const u = units.find(x => x.number === number);
  if (!u) return;
  openUModal('Unit ' + u.number + ' — ' + (u.defense || ''));
  const statusBadgeCls = u.status === 'done' ? 'done' : (u.status === 'in_progress' ? 'running' : 'stale');
  let html = `<div class="card">
    <div class="pl-box-top" style="margin-bottom:6px">
      <span class="badge ${statusBadgeCls}">${esc(u.status || '')}</span>
      <strong>#${u.number}</strong>
    </div>
    <div class="card-meta">
      <strong>defense:</strong> ${esc(u.defense || '')}<br>
      <strong>implementation:</strong> ${esc(u.implementation || '')}<br>
      <strong>alloy_model:</strong> ${esc(u.alloy_model || '')}
      ${u.notes ? `<br><strong>notes:</strong> ${esc(u.notes)}` : ''}
    </div>
  </div>`;

  const specBlock = (label, filename, spec) => {
    if (!filename) return '';
    const needsTag = String(filename).toUpperCase().startsWith('NEEDS')
      ? ' <span class="badge failed">NEEDS</span>' : '';
    return `<div class="card">
      <strong>${esc(label)}:</strong> <code>${esc(filename)}</code>${needsTag}
      ${spec ? `<pre class="file-content">${esc(JSON.stringify(spec, null, 2))}</pre>` : ''}
    </div>`;
  };
  html += specBlock('leakage criterion', u.leakage, u.leakage_spec);
  html += specBlock('timing criterion', u.timing, u.timing_spec);
  html += specBlock('fanout criterion', u.fanout, u.fanout_spec);

  const all = u.results || [];
  const present = u.results_present || [];
  html += `<h4 style="margin:14px 0 4px">Results</h4>`;
  html += all.length
    ? `<ul style="margin:0;padding-left:18px;font-size:12px">${all.map(r =>
        `<li>${present.includes(r)
          ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:var(--err)">✗</span>'} <code>${esc(r)}</code></li>`).join('')}</ul>`
    : `<p class="empty">none listed</p>`;

  if (u.needs && u.needs.length) {
    html += `<h4 style="margin:14px 0 4px">Needs</h4>
      <ul class="to-run-checklist">${u.needs.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`;
  }
  document.getElementById('uModalBody').innerHTML = html;
}

// To-run (TODO) panel — pinned below the grid: defense units with no results
// on disk yet, each with its checklist of what's needed.
function renderToRunPanel(units) {
  const toRun = (units || []).filter(u => u.status === 'to_run').sort((a, b) => a.number - b.number);
  if (!toRun.length) return '';
  let html = `<div class="card to-run-panel">
    <h3 style="margin-top:0;color:var(--warn)">To run — TODO</h3>`;
  for (const u of toRun) {
    html += `<div class="to-run-card">
      <div class="pl-box-top">
        <span class="unit-badge unit-badge-static">${u.number}</span>
        <strong>${esc(u.defense || '')}</strong>
        <span class="card-meta">${esc(u.implementation || '')}</span>
      </div>
      <div class="card-meta" style="margin-top:2px">alloy_model: <code>${esc(u.alloy_model || '')}</code></div>`;
    const needs = (u.needs || []).slice();
    // Also flag any criteria value that itself reads "NEEDS: ..." as a
    // to-create item, if it isn't already reflected in the needs[] checklist.
    for (const [label, val] of [['leakage', u.leakage], ['timing', u.timing], ['fanout', u.fanout]]) {
      if (val && String(val).toUpperCase().startsWith('NEEDS')
          && !needs.some(n => n.indexOf(val) !== -1)) {
        needs.push(`${label}: ${val}`);
      }
    }
    if (needs.length) {
      html += `<ul class="to-run-checklist">${needs.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`;
    }
    if (u.notes) html += `<div class="card-meta" style="margin-top:4px">${esc(u.notes)}</div>`;
    html += `</div>`;
  }
  html += `</div>`;
  return html;
}

// Prose rollup of defense-units status — used at the top of the Status tab.
function renderUnitsRollup(units) {
  if (!units || !units.length) return '';
  const done = units.filter(u => u.status === 'done');
  const inProgress = units.filter(u => u.status === 'in_progress');
  const toRun = units.filter(u => u.status === 'to_run').sort((a, b) => a.number - b.number);
  const nameList = arr => arr.map(u => `#${u.number} ${u.defense}`).join(', ');
  let html = `<div class="card">
    <h3 style="margin-top:0">Defense units</h3>
    <p style="font-size:13px;margin:0 0 4px">
      <span style="color:var(--ok);font-weight:700">${done.length} done</span>${done.length ? ' (' + esc(nameList(done)) + ')' : ''}.
      ${inProgress.length ? `<span style="color:var(--warn);font-weight:700">${inProgress.length} in progress</span> (${esc(nameList(inProgress))}). ` : ''}
      <span style="color:var(--warn);font-weight:700">${toRun.length} TODO</span>${toRun.length ? ' (' + esc(nameList(toRun)) + ')' : ''}.
    </p>`;
  if (toRun.length) {
    for (const u of toRun) {
      const needs = u.needs || [];
      html += `<p style="font-size:12px;margin:6px 0 0"><strong>#${u.number} ${esc(u.defense || '')}</strong>
        (${esc(u.implementation || '')}) &mdash; ${needs.length ? esc(needs.join('; ')) : 'no checklist recorded'}</p>`;
    }
  }
  html += `</div>`;
  return html;
}

function renderGem5Orphans(orphans) {
  if (!orphans || !orphans.length) return '';
  let html = `<h3 style="margin-top:24px">Orphan gem5 campaigns (no live testset)</h3>
    <div class="pl-orphans">`;
  for (const g of orphans) html += gem5BoxHtml(g);
  html += `</div>`;
  return html;
}

function buildPipelineHtml(pipelineData, modelsData, unitsData) {
  const units = (unitsData && unitsData.units) || [];
  let html = renderJobsStrip(pipelineData.jobs || []);
  html += `<div style="margin:10px 0 16px">
    <button class="primary" onclick="openLaunchModal()">+ New fanout</button>
  </div>`;
  html += `<h2 style="margin-top:0">Pipeline</h2>
    <p class="card-meta" style="margin-top:-6px">XML (Alloy enumeration) &rarr; PROGRAMS (concretization/fanout) &rarr; GEM5 (campaigns). Click any box for detail; numbered badges are defense units (green=done, yellow=in progress) — click a badge for the unit's criteria.
    ${modelsData && modelsData.archived ? ' &middot; ' + modelsData.archived + ' archived model(s) not shown.' : ''}</p>`;
  const rows = mergeModelRows(pipelineData, modelsData);
  html += renderPipelineGrid(rows, unitsByModel(units));
  html += renderGem5Orphans(pipelineData.gem5_orphans || []);
  html += renderToRunPanel(units);
  return html;
}

async function fetchPipelineAndModels() {
  const [pipelineData, modelsData, unitsData] = await Promise.all([
    apiCall('/api/pipeline'),
    apiCall('/api/models'),
    apiCall('/api/defense_units'),
  ]);
  return {
    pipelineData,
    modelsData: modelsData.error ? { models: [], archived: 0 } : modelsData,
    unitsData: unitsData.error ? { units: [] } : unitsData,
  };
}

// Initial / manual load (goes through refreshMainTab's spinner).
async function renderPipelineTab() {
  const { pipelineData, modelsData, unitsData } = await fetchPipelineAndModels();
  if (pipelineData.error) {
    return `<p class="err">Error: ${esc(pipelineData.error)}</p>`;
  }
  PL_DATA = pipelineData;
  MODELS_DATA = modelsData;
  DEFENSE_UNITS_DATA = unitsData;
  state.pipelineSig = JSON.stringify(pipelineData) + '|' + JSON.stringify(modelsData) + '|' + JSON.stringify(unitsData);
  return buildPipelineHtml(pipelineData, modelsData, unitsData);
}

// Quiet background poll: fetch /api/pipeline + /api/models + /api/defense_units,
// and ONLY touch the DOM if any of them actually changed. No spinner, no full-tab
// rebuild → the page doesn't jump to the top. When it does change, we re-render
// in place and restore the scroll position.
async function pollPipeline() {
  const { pipelineData, modelsData, unitsData } = await fetchPipelineAndModels();
  if (pipelineData.error) return;                // keep the current view on a transient error
  const sig = JSON.stringify(pipelineData) + '|' + JSON.stringify(modelsData) + '|' + JSON.stringify(unitsData);
  if (sig === state.pipelineSig) return;         // unchanged → do nothing (no jump, no flicker)
  state.pipelineSig = sig;
  PL_DATA = pipelineData;
  MODELS_DATA = modelsData;
  DEFENSE_UNITS_DATA = unitsData;
  const main = document.getElementById('main');
  if (!main) return;
  const y = window.scrollY;                      // preserve scroll across the re-render
  main.innerHTML = buildPipelineHtml(pipelineData, modelsData, unitsData);
  window.scrollTo(0, y);
  stamp();
}

// ====== Status tab ======

async function renderStatusTab() {
  const [codeData, paperData, unitsData] = await Promise.all([
    apiCall('/api/status?which=code'),
    apiCall('/api/status?which=paper'),
    apiCall('/api/defense_units'),
  ]);
  let html = renderUnitsRollup((unitsData && unitsData.units) || []);
  html += `<p class="card-meta">Live sweep status now lives on the
    <a onclick="switchMainTab('pipeline')" style="color:var(--link);cursor:pointer">Pipeline</a> tab.</p>`;
  html += `<div class="status-cols">`;
  html += `<div class="status-col"><h3>Code STATUS</h3>${codeData.html
    || (codeData.error ? `<p class="err">${esc(codeData.error)}</p>` : '')}</div>`;
  html += `<div class="status-col"><h3>Paper STATUS</h3>${paperData.html
    || (paperData.error ? `<p class="err">${esc(paperData.error)}</p>` : '')}</div>`;
  html += `</div>`;
  html += `<div style="margin-top:20px">${await renderDocs()}</div>`;
  return html;
}

// ====== Utility renderers ======

async function renderAnnotationChecker() {
  const [data, tcData] = await Promise.all([
    apiCall('/api/checkers'),
    apiCall('/api/transmitter_criteria'),
  ]);
  let html = '';
  if (data.error) {
    html += `<p class="err">Error: ${esc(data.error)}</p>`;
  } else {
    html += `<h3 style="margin-top:0">Checkers by Kind</h3>`;
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
  }
  html += renderTransmitterCriteria(tcData);
  return html;
}

// The detailed "did it actually leak" definition per transmitter kind (the
// CLAUDE.md "Leak criteria" work), plus each defense's transmitter set —
// surfaced here since it's the natural extension of "checkers by kind" above.
function renderTransmitterCriteria(data) {
  if (!data || data.error) {
    return `<p class="err" style="margin-top:16px">Transmitter criteria unavailable${data && data.error ? ': ' + esc(data.error) : ''}</p>`;
  }
  const crit = data.criteria || {};
  let html = `<h3 style="margin-top:20px">Transmitter Criteria</h3>`;
  if (data._vscode) {
    html += `<p class="card-meta"><a class="vscode-link" href="${esc(data._vscode)}">open registry in VSCode</a></p>`;
  }
  if (crit.window) {
    html += `<p class="card-meta"><strong>Window:</strong> ${esc(crit.window)}</p>`;
  }

  const kinds = crit.kinds || {};
  for (const kindId of Object.keys(kinds)) {
    const k = kinds[kindId] || {};
    const weak = k.status && /weak|pending|needs/i.test(k.status);
    html += `<div class="card">
      <h3 style="display:flex;align-items:center;gap:8px;font-size:13px">
        <code>${esc(kindId)}</code>
        ${k.status ? `<span class="badge ${weak ? 'stale' : 'done'}" style="text-transform:none">${esc(k.status)}</span>` : ''}
      </h3>
      <div class="card-meta">
        <strong>checker:</strong> <code>${esc(k.checker || '?')}</code><br>
        <strong>signal:</strong> ${esc(k.signal || '?')}<br>
        <strong>gate:</strong> ${esc(k.gate || '?')}
      </div>`;
    if (k.leak_if && k.leak_if.length) {
      html += `<div style="margin-top:6px"><strong style="font-size:12px;color:var(--ok)">leak if:</strong>
        <ul style="margin:4px 0;padding-left:18px;font-size:12px">${k.leak_if.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>`;
    }
    if (k.not_leak_if && k.not_leak_if.length) {
      html += `<div style="margin-top:4px"><strong style="font-size:12px;color:var(--muted)">not leak if:</strong>
        <ul style="margin:4px 0;padding-left:18px;font-size:12px">${k.not_leak_if.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>`;
    }
    if (k.notes) html += `<p style="font-size:11px;color:var(--muted);margin-top:6px">${esc(k.notes)}</p>`;
    html += `</div>`;
  }

  const leak = data.leakage || {};
  const leakIds = Object.keys(leak);
  if (leakIds.length) {
    html += `<h4 style="margin:16px 0 6px">Per-defense transmitter sets</h4>`;
    html += `<table><thead><tr><th>defense</th><th>transmitters</th><th>checkers</th><th>note</th></tr></thead><tbody>`;
    for (const defId of leakIds) {
      const d = leak[defId] || {};
      const transmitters = (d.transmitters || []).join(', ');
      const checkersTxt = d.checkers
        ? Object.entries(d.checkers).map(([kk, vv]) => `${kk}: ${vv}`).join('; ') : '';
      html += `<tr>
        <td><code>${esc(d.defense || defId)}</code></td>
        <td style="font-size:11px">${esc(transmitters)}</td>
        <td style="font-size:11px">${esc(checkersTxt)}</td>
        <td style="font-size:11px">${esc(d.note || '')}</td>
      </tr>`;
    }
    html += `</tbody></table>`;
  }

  if (data.stage_mapping) {
    html += `<h4 style="margin:16px 0 6px">Stage mapping</h4>
      <pre class="file-content">${esc(JSON.stringify(data.stage_mapping, null, 2))}</pre>`;
  }
  return html;
}

async function renderFanoutTables() {
  const data = await apiCall('/api/tables');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3 style="margin-top:0">Kinds & Candidates</h3>`;
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
    <h3 style="margin-top:0">Launch Fanout Job</h3>
    <div class="form-group">
      <label>Model</label>
      <input type="text" id="launchModel" placeholder="STT_6" style="width:100%">
    </div>
    <div class="form-group">
      <label>Config</label>
      <input type="text" id="launchConfig" placeholder="runconfigs/run_config_STT_6.jsonc" style="width:100%">
    </div>
    <div class="form-group">
      <button class="primary" onclick="submitLaunch()">Launch</button>
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
  // The content column may be narrow on small screens; the diagram itself opens
  // in a full-width overlay regardless.
  return `
    <h3 style="margin-top:0">Execution Graph</h3>
    <p style="font-size:12px;color:var(--muted);margin:0 0 8px">
      Renders an Alloy instance's instructions (program order) with data-flow
      (rf) and taint (ddi) edges. Opens in a full-width overlay. You can also
      reach it from any test in the Pipeline tab's XML/PROGRAMS inspector.</p>
    <div class="form-group">
      <label>Model</label>
      <input type="text" id="egModel" value="${DEFAULT_MODEL}" placeholder="STT_6" style="width:260px">
    </div>
    <div class="form-group">
      <label>Stem</label>
      <input type="text" id="egStem" value="${DEFAULT_STEM}" placeholder="inst-000123" style="width:260px">
    </div>
    <button onclick="fetchExecGraph()">Open graph</button>
  `;
}

async function fetchExecGraph() {
  const model = document.getElementById('egModel').value.trim();
  const stem = document.getElementById('egStem').value.trim();
  if (!model || !stem) { alert('Model and stem required'); return; }
  openExecGraph(model, stem);
}

// ====== XML graph — full inline viewer (Utilities tab) ======
// Same data (/api/execgraph) + same renderer (buildExecGraphView) as the modal
// path below, just rendered directly into the section instead of an overlay,
// with a model dropdown (from /api/models) instead of a free-text field.
async function renderXmlGraphUtil() {
  const modelsData = await apiCall('/api/models');
  const modelNames = (modelsData.models || []).map(m => m.name).sort();
  const modelsErr = modelsData.error
    ? `<p class="err" style="font-size:11px">Could not load model list: ${esc(modelsData.error)}</p>` : '';
  let html = `
    <h3 style="margin-top:0">XML Graph</h3>
    <p style="font-size:12px;color:var(--muted);margin:0 0 10px">
      Visualize one Alloy instance's instruction/operand graph: program order
      (spo), data-flow (rf — the leak path), and taint dependency (ddi), with
      the speculative window and the transmitter highlighted. You can also
      reach this from any test in the Pipeline tab's XML/PROGRAMS inspector.</p>
    ${modelsErr}
    <div class="form-group">
      <label>Model</label>
      <select id="xvModel" style="width:280px">
        <option value="">— choose a model —</option>
        ${modelNames.map(n => `<option value="${esc(n)}"${n === DEFAULT_MODEL ? ' selected' : ''}>${esc(n)}</option>`).join('')}
      </select>
    </div>
    <div class="form-group">
      <label>Stem</label>
      <input type="text" id="xvStem" value="${DEFAULT_STEM}" placeholder="inst-000123" style="width:280px">
    </div>
    <button class="primary" onclick="loadXmlGraphUtil()">Render graph</button>
    <div id="xmlGraphBody" style="margin-top:14px"></div>
  `;
  // Auto-render the default (STT_6 / inst-000001) so it's zero-click "for fun".
  setTimeout(() => { if (document.getElementById('xvStem')) loadXmlGraphUtil(); }, 60);
  return html;
}

async function loadXmlGraphUtil() {
  const model = document.getElementById('xvModel').value.trim();
  const stem = document.getElementById('xvStem').value.trim();
  const target = document.getElementById('xmlGraphBody');
  if (!model || !stem) { alert('Model and stem required'); return; }
  target.innerHTML = '<p class="spin">loading…</p>';
  const data = await apiCall('/api/execgraph?model=' + encodeURIComponent(model) + '&stem=' + encodeURIComponent(stem));
  if (data.error) { target.innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`; return; }
  target.innerHTML = buildExecGraphView(data);
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

// Small inline-SVG line swatch so the legend actually shows each edge's LINE
// STYLE (thin/solid vs bold vs dashed), not just a color chip.
function egLineIcon(stroke, opts) {
  opts = opts || {};
  const w = opts.bold ? 3.2 : (opts.thin ? 1.3 : 1.8);
  const dash = opts.dashed ? ' stroke-dasharray="5 4"' : '';
  return `<svg width="26" height="12" style="vertical-align:middle;flex:0 0 auto">`
    + `<line x1="1" y1="6" x2="25" y2="6" stroke="${stroke}" stroke-width="${w}"${dash} stroke-linecap="round"/></svg>`;
}

function egLegend() {
  const theme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const P = egPalette(theme);
  const kinds = [['ld','load'],['str','store'],['br_n','branch'],['br_x','branch·xmit'],['other_n','ALU'],['other_x','ALU·xmit']];
  let h = '<div class="eg-legend">';
  for (const [k, lbl] of kinds) h += `<span><i class="eg-swatch" style="background:${P[k]}"></i>${lbl}</span>`;
  h += `<span>${egLineIcon(P.spo, { thin: true })} spo (program order)</span>`;
  h += `<span>${egLineIcon(P.rf, { bold: true })} rf (data-flow — the leak path)</span>`;
  h += `<span>${egLineIcon(P.ddi, { dashed: true })} ddi (taint dependency)</span>`;
  h += `<span style="color:${P.xm};font-weight:bold">★ transmitter</span>`;
  h += `<span><i class="eg-swatch" style="background:${P.xm}22;border:1px solid ${P.xm}"></i>speculative window (uncommitted)</span>`;
  h += `<span><i class="eg-swatch" style="border:1.6px dashed ${P.muted};background:transparent"></i>unresolved</span>`;
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

  const boxW = 210, boxH = 52, ROW = 94, top = 62;
  const spo = edges.filter(e => e.type === 'spo');
  const rf  = edges.filter(e => e.type === 'rf');
  const ddi = edges.filter(e => e.type === 'ddi');
  const bulge = e => { const a = look(e.src), b = look(e.dst); if (!a || !b) return 42;
    return Math.min(170, 32 + Math.abs(a._i - b._i) * 17); };
  const maxRf  = rf.reduce((m, e) => Math.max(m, bulge(e)), 44);
  const maxDdi = ddi.reduce((m, e) => Math.max(m, (look(e.src) === look(e.dst) ? 54 : bulge(e))), 44);
  const PADL = Math.max(130, maxDdi + 44);
  const boxLeft = PADL, boxRight = PADL + boxW, centerX = PADL + boxW / 2;
  const width = Math.ceil(boxRight + maxRf + 48);
  const height = top + nodes.length * ROW + 24;
  const cy = n => top + n._i * ROW + boxH / 2;

  let s = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;font-family:ui-monospace,Menlo,Consolas,monospace">`;
  s += `<defs>
    <marker id="egSpo" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="${P.spo}"/></marker>
    <marker id="egRf"  markerWidth="11" markerHeight="11" refX="7" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="${P.rf}"/></marker>
    <marker id="egDdi" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="${P.ddi}"/></marker>
  </defs>`;

  // Speculative-window shading: committed is an in-order prefix (per DESIGN.md),
  // so the uncommitted tail IS the speculative window the transmitter must sit
  // in — shade it and draw a bold boundary so that's obvious at a glance.
  const committed = nodes.filter(n => n.committed);
  const firstSpec = nodes.find(n => !n.committed);
  if (firstSpec) {
    const prevCommitted = committed.length ? committed[committed.length - 1] : null;
    const yTop = prevCommitted ? (cy(prevCommitted) + cy(firstSpec)) / 2 : (top - 18);
    const yBottom = height - 8;
    s += `<rect x="2" y="${yTop}" width="${width - 4}" height="${yBottom - yTop}" fill="${P.xm}14" stroke="none"/>`;
    s += `<line x1="4" y1="${yTop}" x2="${width - 4}" y2="${yTop}" stroke="${P.xm}" stroke-width="2" stroke-dasharray="7 4"/>`;
    s += `<text x="10" y="${yTop - 6}" fill="${P.xm}" font-size="10" font-weight="bold">▼ speculative window (uncommitted — the transmitter must sit in here)</text>`;
  }

  // spo backbone — thin, grey, program order (earlier pc → later pc)
  spo.forEach(e => {
    const a = look(e.src), b = look(e.dst); if (!a || !b) return;
    const up = a._i < b._i ? a : b, dn = a._i < b._i ? b : a;
    s += `<line x1="${centerX}" y1="${cy(up) + boxH / 2}" x2="${centerX}" y2="${cy(dn) - boxH / 2}" stroke="${P.spo}" stroke-width="1.4" marker-end="url(#egSpo)"><title>spo (program order): pc${up.pc} → pc${dn.pc}</title></line>`;
  });

  // rf (data-flow) arcs on the right — BOLD: this is the taint/leak path
  rf.forEach(e => {
    const a = look(e.src), b = look(e.dst); if (!a || !b) return;
    const bl = bulge(e), y1 = cy(a), y2 = cy(b);
    s += `<path d="M${boxRight},${y1} Q${boxRight + bl},${(y1 + y2) / 2} ${boxRight},${y2}" fill="none" stroke="${P.rf}" stroke-width="3.2" stroke-linecap="round" marker-end="url(#egRf)"><title>rf (data-flow — leak path): pc${a.pc} → pc${b.pc}</title></path>`;
  });

  // ddi (taint dependency) arcs on the left — dashed; self-taint as a small loop
  ddi.forEach(e => {
    const a = look(e.src), b = look(e.dst); if (!a || !b) return;
    if (a === b) {
      const y = cy(a);
      s += `<path d="M${boxLeft},${y - 10} C${boxLeft - 50},${y - 28} ${boxLeft - 50},${y + 28} ${boxLeft},${y + 10}" fill="none" stroke="${P.ddi}" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#egDdi)"><title>ddi (self-taint): pc${a.pc}</title></path>`;
    } else {
      const bl = bulge(e), y1 = cy(a), y2 = cy(b);
      s += `<path d="M${boxLeft},${y1} Q${boxLeft - bl},${(y1 + y2) / 2} ${boxLeft},${y2}" fill="none" stroke="${P.ddi}" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#egDdi)"><title>ddi (taint dependency): pc${a.pc} → pc${b.pc}</title></path>`;
    }
  });

  // nodes on top: label = "pc: kind"; transmitter gets a gold halo + star;
  // unresolved gets a dashed outline; speculative nodes read "hotter" (higher
  // fill opacity) than committed/retired ones.
  nodes.forEach(n => {
    const y = cy(n) - boxH / 2;
    const col = P[n.kind] || P.unknown;
    const isXm = !!n.isxm;
    const stroke = isXm ? P.xm : col;
    const sw = isXm ? 3.6 : 1.5;
    const dashAttr = n.resolved ? '' : ' stroke-dasharray="6 3"';
    const fillAlpha = n.committed ? '12' : '2c';
    const flags = [];
    flags.push(n.committed ? 'committed (retired)' : 'speculative (uncommitted)');
    flags.push(n.resolved ? 'resolved' : 'UNRESOLVED');
    if (isXm) flags.unshift('★ TRANSMITTER');
    s += `<g><title>pc ${n.pc} · ${n.kind}${isXm ? ' · TRANSMITTER' : ''} · ${flags.join(' · ')}</title>`;
    if (isXm) {
      s += `<rect x="${boxLeft - 5}" y="${y - 5}" width="${boxW + 10}" height="${boxH + 10}" rx="11" fill="none" stroke="${P.xm}" stroke-width="1.4" opacity="0.55"/>`;
    }
    s += `<rect x="${boxLeft}" y="${y}" width="${boxW}" height="${boxH}" rx="7" fill="${col}${fillAlpha}" stroke="${stroke}" stroke-width="${sw}"${dashAttr}/>`;
    s += `<rect x="${boxLeft}" y="${y}" width="5" height="${boxH}" rx="2" fill="${col}"/>`;
    s += `<text x="${boxLeft + 14}" y="${y + 21}" fill="${P.boxText}" font-size="13" font-weight="bold">${isXm ? '★ ' : ''}${n.pc}: ${esc(n.kind)}</text>`;
    s += `<text x="${boxLeft + 14}" y="${y + 38}" fill="${P.muted}" font-size="10">${esc(flags.join(' · '))}</text>`;
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
  // .eg-modal/.eg-legend/etc. live in the page's main <style> now (so the
  // Utilities "XML graph" inline viewer is styled even if this modal is
  // never opened); this function just creates the modal element itself.
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
  let html = `<h3>Documentation</h3>`;
  if (data.groups && data.groups.length > 0) {
    for (const grp of data.groups) {
      html += `<h4 style="font-size:12px;margin:8px 0 4px">${esc(grp.label)}</h4>`;
      for (const link of (grp.links || [])) {
        html += `<div><a onclick="loadDoc('${esc(link.path)}', '${esc(link.label)}')" style="color:var(--link);cursor:pointer;font-size:12px">${esc(link.label)}</a></div>`;
      }
    }
  }
  html += `<hr style="margin:12px 0;border:none;border-top:1px solid var(--border)">`;
  html += `<button onclick="loadStatusDoc()">Load STATUS</button>`;
  html += `<div id="docBody" style="margin-top:12px"></div>`;
  return html;
}

async function loadDoc(path, label) {
  const data = await apiCall('/api/md?path=' + encodeURIComponent(path));
  const target = document.getElementById('docBody');
  if (!target) return;
  if (data.error) {
    target.innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
  } else if (data.html) {
    target.innerHTML = data.html;
  }
}

async function loadStatusDoc() {
  const data = await apiCall('/api/status?which=code');
  const target = document.getElementById('docBody');
  if (!target) return;
  if (data.error) {
    target.innerHTML = `<p class="err">Error: ${esc(data.error)}</p>`;
  } else if (data.html) {
    target.innerHTML = data.html;
  }
}

// ====== Sources of truth (specs) — Utilities tab ======

async function renderSpecsSection() {
  const data = await apiCall('/api/specs');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3 style="margin-top:0">Sources of Truth</h3>`;
  if (!data.specs || !data.specs.length) {
    html += `<p class="empty">No specs configured.</p>`;
    return html;
  }
  for (const s of data.specs) {
    html += `<div class="card">
      <h3>${esc(s.name)} ${s.exists ? '' : '<span class="badge failed">MISSING</span>'}</h3>
      <div class="card-meta">
        ${esc(s.desc || '')}<br>
        <code>${esc(s.path || '')}</code>
        ${s.vscode ? `<a class="vscode-link" href="${esc(s.vscode)}">open in VSCode</a>` : ''}
      </div>
      ${s.exists ? `<pre class="file-content">${esc(s.text || '')}</pre>` : ''}
    </div>`;
  }
  return html;
}

// ====== Generic catalog browser (Run configs / gem5 hooks / Findings) ======
// Single reusable renderer for /api/catalog?kind=runconfigs|gem5hooks|findings.
async function renderCatalog(kind, label) {
  const data = await apiCall('/api/catalog?kind=' + encodeURIComponent(kind));
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3 style="margin-top:0">${esc(label)}</h3>`;
  const entries = data.entries || [];
  if (!entries.length) {
    html += `<p class="empty">No files found.</p>`;
    return html;
  }
  for (const e of entries) {
    html += `<div class="card">
      <h3 style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:13px">
        <code>${esc(e.name)}</code>
        ${e.vscode ? `<a class="vscode-link" href="${esc(e.vscode)}">open in VSCode</a>` : ''}
      </h3>`;
    if (e.text === undefined) {
      html += `<p class="card-meta">(file too large to inline — open in VSCode)</p>`;
    } else if (e.is_markdown) {
      // Reuse the existing markdown renderer (/api/md → md_to_html) when the
      // path is one it's willing to serve; otherwise fall back to raw text.
      const md = await apiCall('/api/md?path=' + encodeURIComponent(e.path));
      html += (md && md.html) ? md.html : `<pre class="file-content">${esc(e.text)}</pre>`;
    } else {
      html += `<pre class="file-content">${esc(e.text)}</pre>`;
    }
    html += `</div>`;
  }
  return html;
}

// ====== Hit categories (source-of-truth registry) — Utilities tab ======
async function renderHitCategories() {
  const data = await apiCall('/api/hit_categories');
  if (data.error) {
    return `<p class="err">Error: ${esc(data.error)}</p>`;
  }
  let html = `<h3 style="margin-top:0">Hit Categories</h3>`;
  if (data._vscode) {
    html += `<p class="card-meta"><a class="vscode-link" href="${esc(data._vscode)}">open registry in VSCode</a></p>`;
  }

  const verdicts = data.verdicts || {};
  html += `<h4 style="margin:10px 0 6px">Verdicts</h4><div class="hitcats-legend">`;
  for (const [id, v] of Object.entries(verdicts)) {
    html += `<span class="vb vb-${esc(id)}" title="${esc(v.note || '')}">${esc(v.label || id)}</span>`;
  }
  html += `</div>`;

  const categories = data.categories || {};
  const ids = Object.keys(categories);
  html += `<h4 style="margin:16px 0 6px">Categories</h4>`;
  if (!ids.length) {
    html += `<p class="empty">No categories registered.</p>`;
  } else {
    html += `<table><thead><tr><th>id</th><th>label</th><th>verdict</th><th>phase</th><th>scope</th><th>description</th></tr></thead><tbody>`;
    for (const id of ids) {
      const c = categories[id] || {};
      const scope = c.scope || {};
      const scopeParts = [];
      if (scope.testsets && scope.testsets.length) scopeParts.push('testsets: ' + scope.testsets.join(', '));
      if (scope.builds && scope.builds.length) scopeParts.push('builds: ' + scope.builds.join(', '));
      const scopeTxt = scopeParts.length ? esc(scopeParts.join(' · ')) : '<span class="muted">(global)</span>';
      html += `<tr>
        <td><code>${esc(id)}</code></td>
        <td>${esc(c.label || '')}</td>
        <td><span class="vb vb-${esc(c.verdict || '')}">${esc(c.verdict || '?')}</span></td>
        <td>${esc(c.phase || '')}</td>
        <td style="font-size:11px">${scopeTxt}</td>
        <td style="font-size:11px">${esc(c.description || '')}</td>
      </tr>`;
    }
    html += `</tbody></table>`;
  }
  return html;
}

// ====== Alloy models (annotated table) — Utilities tab ======
async function renderAlloyModels() {
  const data = await apiCall('/api/alloy_models');
  if (data.error || data.ok === false) {
    return `<p class="err">Error: ${esc(data.error || 'failed to load')}</p>`;
  }
  let html = `<h3 style="margin-top:0">Alloy models</h3>`;
  html += `<p class="card-meta">Every <code>.als</code> in <code>STAGE1_alloy/models/</code>, grouped by tier. Auto-parsed (defense family / scope / transmitters / XML count) + curated annotations from <code>specs/alloy_models.json</code>${data._vscode ? ` <a class="vscode-link" href="${esc(data._vscode)}">edit annotations</a>` : ''}. ${data.archived ? data.archived + ' archived in old_models/.' : ''}</p>`;
  const models = data.models || [];
  if (!models.length) { html += `<p class="empty">No models found.</p>`; return html; }
  const tierLabel = {production: '⭐ Production (latest)', variant: 'Variants', bugsynth: 'Bugsynth probes', legacy: 'Legacy', '': 'Other'};
  let curTier = null;
  html += `<table><thead><tr><th>model</th><th>tier</th><th>defense</th><th>scope</th><th>transmitters</th><th>XML</th><th>summary / intention</th></tr></thead><tbody>`;
  for (const m of models) {
    if (m.tier !== curTier) {
      curTier = m.tier;
      html += `<tr><td colspan="7" style="background:var(--border);font-weight:600;font-size:11px;padding:4px 8px">${esc(tierLabel[curTier] || curTier)}</td></tr>`;
    }
    const link = m.symlink_target ? ` <span class="muted">→ ${esc(m.symlink_target)}</span>` : '';
    const enumBadge = m.enumerated ? `<span class="badge ok">${m.xml_count}</span>` : `<span class="muted">0</span>`;
    let note = esc(m.summary || '');
    if (m.intention) note += `<br><span class="muted">▸ ${esc(m.intention)}</span>`;
    if (m.caveat) note += `<br><span style="color:var(--warn,#c80)">⚠ ${esc(m.caveat)}</span>`;
    if (m.aliases) note += `<br><span class="muted">aliases: ${esc(m.aliases)}</span>`;
    html += `<tr>
      <td><code>${esc(m.name)}</code>${link}${m.vscode ? ` <a class="vscode-link" href="${esc(m.vscode)}">src</a>` : ''}</td>
      <td style="font-size:11px">${esc(m.tier || '')}</td>
      <td style="font-size:11px">${esc(m.defense_family || '')}</td>
      <td style="font-size:11px">${esc(m.instr_scope || '')}</td>
      <td style="font-size:11px"><code>${esc(m.transmitters || '')}</code></td>
      <td>${enumBadge}</td>
      <td style="font-size:11px">${note}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

// ====== gem5 builds (annotated table + timing-hook status) — Utilities tab ======
async function renderGem5Builds() {
  const data = await apiCall('/api/gem5_builds');
  if (data.error || data.ok === false) {
    return `<p class="err">Error: ${esc(data.error || 'failed to load')}</p>`;
  }
  let html = `<h3 style="margin-top:0">gem5 builds</h3>`;
  html += `<p class="card-meta">One entry per distinct build tree. <b>Timing hooks</b>: BF = branch-force (<code>--branch-ann-file</code> BTB override + resolve-stall); FNC = first-not-committed commit stall (window widener). Source of truth: <code>specs/gem5_builds.json</code>${data._vscode ? ` <a class="vscode-link" href="${esc(data._vscode)}">edit</a>` : ''}.</p>`;
  const builds = data.builds || [];
  if (!builds.length) { html += `<p class="empty">No builds registered.</p>`; return html; }
  const dot = (ok) => ok ? '<span style="color:#2a2">●</span>' : '<span style="color:#c33">○</span>';
  const statusBadge = (s) => {
    const cls = s === 'full' ? 'ok' : (s === 'none' ? 'failed' : 'warn');
    return `<span class="badge ${cls}">${esc(s || '?')}</span>`;
  };
  html += `<table><thead><tr><th>build</th><th>defense</th><th>CPU / cache</th><th>scheme</th><th>timing hooks</th><th>git</th><th>intention</th></tr></thead><tbody>`;
  for (const b of builds) {
    const t = b.timing_hooks || {};
    const hooks = `BF ${dot(t.branch_force)} &nbsp; FNC ${dot(t.fnc_commit_stall)}<br>${statusBadge(t.status)}${t.note ? `<br><span class="muted" style="font-size:10px">${esc(t.note)}</span>` : ''}`;
    let intent = esc(b.intention || '');
    if (b.variants && b.variants !== 'none') intent += `<br><span class="muted">variants: ${esc(b.variants)}</span>`;
    if (b.hooks_backup) intent += `<br><span class="muted">hooks: ${esc(b.hooks_backup)}</span>`;
    html += `<tr>
      <td><code>${esc(b.id)}</code><br><span class="muted" style="font-size:10px">${esc(b.path || '')}</span></td>
      <td style="font-size:11px">${esc(b.defense || '')}</td>
      <td style="font-size:11px">${esc(b.cpu || '')}</td>
      <td style="font-size:11px"><code>${esc(b.scheme || '')}</code></td>
      <td style="font-size:11px">${hooks}</td>
      <td style="font-size:11px">${b.git_tracked ? '<span class="badge ok">git</span>' : '<span class="badge failed">no git</span>'}</td>
      <td style="font-size:11px">${intent}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

// ====== gem5 hooks registry (purposes table) — Utilities tab ======
async function renderHookRegistry() {
  const data = await apiCall('/api/gem5_hooks');
  if (data.error || data.ok === false) {
    return `<p class="err">Error: ${esc(data.error || 'failed to load')}</p>`;
  }
  let html = `<h3 style="margin-top:0">gem5 hooks — purposes</h3>`;
  html += `<p class="card-meta">Every instrumentation / observation hook we've built + its purpose. <b>realization</b> = gem5 source change (manufactures the scenario); <b>observation</b> = checker-side trace parser (no source change); <b>bridge</b> = config→env plumbing. ⏱ = timing hook. Source: <code>specs/gem5_hooks.json</code>${data._vscode ? ` <a class="vscode-link" href="${esc(data._vscode)}">edit</a>` : ''}.</p>`;
  const hooks = data.hooks || [];
  if (!hooks.length) { html += `<p class="empty">No hooks registered.</p>`; return html; }
  const catOrder = {realization: 0, observation: 1, bridge: 2};
  hooks.sort((a, b) => (catOrder[a.category] ?? 9) - (catOrder[b.category] ?? 9));
  let curCat = null;
  html += `<table><thead><tr><th>hook</th><th>⏱</th><th>site</th><th>purpose</th><th>builds</th></tr></thead><tbody>`;
  for (const h of hooks) {
    if (h.category !== curCat) {
      curCat = h.category;
      html += `<tr><td colspan="5" style="background:var(--border);font-weight:600;font-size:11px;padding:4px 8px">${esc((curCat||'').toUpperCase())} — ${esc((data.categories||{})[curCat] || '')}</td></tr>`;
    }
    html += `<tr>
      <td><b>${esc(h.name || h.id)}</b><br><span class="muted" style="font-size:10px"><code>${esc(h.id)}</code></span></td>
      <td style="text-align:center">${h.timing ? '⏱' : ''}</td>
      <td style="font-size:10px"><code>${esc(h.site || '')}</code></td>
      <td style="font-size:11px">${esc(h.purpose || '')}</td>
      <td style="font-size:10px">${esc(h.builds || '')}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  const gaps = data.known_gaps || [];
  if (gaps.length) {
    html += `<h4 style="margin:16px 0 6px">Known gaps / TODO hooks</h4><ul style="font-size:11px">`;
    for (const g of gaps) html += `<li>${esc(g)}</li>`;
    html += `</ul>`;
  }
  return html;
}

// ====== Utilities tab (sub-tab/section selector) ======

function renderUtilSubTabs() {
  let html = '<div class="utility-tabs" style="padding-bottom:10px;border-bottom:1px solid var(--border);margin-bottom:14px">';
  for (const tab of UTIL_TABS) {
    const active = state.activeUtilTab === tab.id ? ' active' : '';
    html += `<div class="util-tab${active}" onclick="showUtilSection('${tab.id}')">${tab.label}</div>`;
  }
  html += '</div>';
  return html;
}

async function showUtilSection(id) {
  state.activeUtilTab = id;
  localStorage.setItem('activeUtilTab', id);
  const main = document.getElementById('main');
  main.innerHTML = renderUtilSubTabs() + '<div id="utilSectionBody"><p class="spin">loading…</p></div>';
  let html = '';
  switch (id) {
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
    case 'alloymodels':
      html = await renderAlloyModels();
      break;
    case 'gem5builds':
      html = await renderGem5Builds();
      break;
    case 'hookreg':
      html = await renderHookRegistry();
      break;
    case 'docs':
      html = await renderDocs();
      break;
    case 'specs':
      html = await renderSpecsSection();
      break;
    case 'runconfigs':
      html = await renderCatalog('runconfigs', 'Run configs');
      break;
    case 'gem5hooks':
      html = await renderCatalog('gem5hooks', 'gem5 hooks');
      break;
    case 'findings':
      html = await renderCatalog('findings', 'Findings');
      break;
    case 'hitcats':
      html = await renderHitCategories();
      break;
    case 'xmlviz':
      html = await renderXmlGraphUtil();
      break;
  }
  const bodyEl = document.getElementById('utilSectionBody');
  if (bodyEl) bodyEl.innerHTML = html;
  stamp();
}

// Backward-compatible alias: legacy renderFanout()'s "Launch new fanout" button
// calls showUtilTab('launch'); keep it working by routing through the new
// Utilities tab + section.
function showUtilTab(id) {
  switchMainTab('utilities');
  showUtilSection(id);
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

function switchMainTab(tabId) {
  state.activeMainTab = tabId;
  localStorage.setItem('activeMainTab', tabId);
  renderMainTabs();
  refreshMainTab();
}

async function refreshMainTab() {
  const main = document.getElementById('main');
  if (state.activeMainTab === 'utilities') {
    await showUtilSection(state.activeUtilTab);
    return;
  }
  main.innerHTML = '<p class="spin">loading…</p>';
  let html = '';
  switch (state.activeMainTab) {
    case 'pipeline':
      html = await renderPipelineTab();
      break;
    case 'status':
      html = await renderStatusTab();
      break;
  }
  main.innerHTML = html;
  stamp();
}

// ====== Initialization ======

function setAutoRefresh() {
  if (state.timer) clearInterval(state.timer);
  const interval = parseInt(document.getElementById('iv').value) || 0;
  state.autoRefreshInterval = interval;
  if (interval > 0) {
    state.timer = setInterval(() => {
      // Pipeline has its own faster dedicated poll (see ensurePipelineTimer);
      // this generic interval drives Status/Utilities refresh.
      if (state.activeMainTab !== 'pipeline') refreshMainTab();
    }, interval * 1000);
  }
  localStorage.setItem('autoRefreshInterval', interval);
}

function ensurePipelineTimer() {
  if (state.pipelineTimer) clearInterval(state.pipelineTimer);
  state.pipelineTimer = setInterval(() => {
    if (state.activeMainTab === 'pipeline') pollPipeline();  // quiet diff-refresh, no jump
  }, 8000);
}

function init() {
  // Restore state
  state.activeMainTab = localStorage.getItem('activeMainTab') || 'pipeline';
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

  // Auto-refresh
  document.getElementById('iv').onchange = setAutoRefresh;
  setAutoRefresh();
  ensurePipelineTimer();

  // Focus refresh
  window.addEventListener('focus', () => {
    refreshMainTab();
  });

  // Load initial
  refreshMainTab();
}

document.addEventListener('DOMContentLoaded', init);
</script>

</body>
</html>
"""
