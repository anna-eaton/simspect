# How I build dashboards — a style guide

*Distilled from the SimSpect dashboard (`dashboard/dashboard.py` + `dashboard_data.py` + `dashboard_ui.py`, ~5,400 lines). This is the repeatable pattern I use for a live, self-hosted project console: a single-file web app, zero dependencies, that surfaces every source of truth in a repo and never crashes a panel on bad data. Written to be shared — nothing here is SimSpect-specific except the examples.*

---

## The one-paragraph version

A dashboard is three hard-separated layers in three files: a **pure-data backend** (functions that return JSON-serializable dicts, no web code), a **thin stdlib HTTP server** (routes URLs to those functions, wraps each in an error-catcher), and a **single-page frontend** (one Python string holding the whole HTML/CSS/JS app). Everything is stdlib-only — no pip installs, no npm, no build step, no CDN. The backend's job is to *surface sources of truth* (spec JSON files, run outputs, the filesystem) rather than recompute them, and every function is wrapped so a missing file yields an empty-but-well-formed shape instead of a 500. The frontend is config-driven tabs that each fetch one endpoint and render a template string into one container, with a "quiet refresh" that polls on a timer but only touches the DOM when the data actually changed. You run it on the dev box and reach it over an SSH port-forward.

---

## Layer 0 — the three-file split (the architecture)

The whole thing is three files with a strict, one-directional dependency: `dashboard_ui.py` (frontend) ← `dashboard.py` (server) → `dashboard_data.py` (backend). The server imports both; the two leaf files never import each other.

- **`dashboard_data.py` — the data layer.** Pure functions, each returning JSON-serializable dicts/lists. States its own contract in the module docstring: *"This module contains NO web/HTTP/HTML code."* This is where all the real work lives (reading specs, scanning the filesystem, parsing run outputs).
- **`dashboard.py` — the server.** Stdlib `http.server` only. It does three things: serve the one HTML page at `/`, route every `/api/*` URL to a `dashboard_data` function, and render markdown→HTML for the docs panel. Binds loopback only.
- **`dashboard_ui.py` — the frontend.** Exposes exactly ONE module-level constant, `PAGE`, a raw string holding a complete self-contained HTML document (shell + one `<style>` block + one `<script>` block). No templating engine, no framework.

Why three files and not one: the backend is independently testable (it has a real `--selftest`), the page is one static string the server hands out verbatim, and the server stays tiny (~480 lines) because it has no logic of its own — it's pure routing.

---

## Layer 1 — the data backend

**One public function per panel / endpoint.** The file reads as a numbered sequence of top-level functions, each the backend for exactly one UI panel: `overview()`, `generation()`, `fanout()`, `corpora()`, `pipeline_graph()`, `specs()`, `run_detail()`, and so on. Section-divider banners literally number them (`# 1. overview`, `# 2. generation`, …). If you know the panel, you know the function.

**Two return-shape families, used consistently.** Collection endpoints return a bare `{"<plural_noun>": [ ...records... ]}` (e.g. `{"corpora": [...]}`, `{"items": [...]}`). Anything that can fail or that mutates returns an **`ok`-envelope**: `{"ok": True/False, "error": "...", ...}`. That dualism is consistent enough to be a rule: a bare plural means "always works, here's the list"; an `ok` field means "this might not be found."

**The single most defining idiom: wrap every endpoint in a safety decorator.** A `@_safe(default_factory)` decorator catches any exception, prints the traceback to stderr, and returns the default — and the default is always a lambda returning a *well-formed empty version of that exact shape*:
```python
@_safe(lambda: {"corpora": []})
def corpora() -> dict:
    ...
@_safe(lambda: {"ok": False, "error": "add_todo failed"})
def add_todo(text, urgent=False) -> dict:
    ...
```
This makes "never crash a panel, always return the right shape" a one-line guarantee, and the lambda doubles as inline documentation of the empty shape. The contract is actually tested: the selftest requires every endpoint to run cleanly on a machine with no `testsets/` or `results/` yet.

**Belt-and-suspenders inside, too.** Even under `@_safe`, inner reads that have a sensible local fallback catch narrowly and continue — so one unreadable file degrades one row, not the whole panel:
```python
try:
    man = json.loads(mp.read_text())
except Exception:
    man = {}
```
Directory scans catch `OSError` and leave a partial list; per-file `stat()` calls are individually guarded because a file can vanish mid-scan. Graceful degradation returns *partial* data with an explanatory `note`, never an exception.

**Surface sources of truth; don't recompute them.** The backend's main job is to read human-curated spec files and live filesystem state and hand them to the UI. The canonical "read a source-of-truth file and surface it" pattern:
```python
p = _SPECS_DIR / "gem5_builds.json"
if not p.exists():
    return {"ok": False, "error": f"missing {p}", "builds": []}
data = json.loads(p.read_text(encoding="utf-8"))
data["ok"] = True
data["_path"] = str(p)          # metadata the UI uses for an "edit" link
data["_vscode"] = vscode_uri(str(p))
return data
```
Resolve the path, existence-check into the right empty shape, load the JSON wholesale, then **mutate the loaded dict in place** to add `ok`, `_path`, `_vscode`. Underscore-prefixed keys (`_path`, `_vscode`, `_doc`, `_generated`) mark "added by the surfacing layer, not part of the source file" — a consistent convention.

**Join curated annotations onto auto-derived data.** A recurring move: auto-parse the raw thing (e.g. scan the model files), then enrich each row with curated fields from a spec JSON via `{**auto_row, "tier": curated.get("tier"), "summary": ...}`. The filesystem gives you *what exists*; the spec file gives you *what it means*; the panel shows both.

**Reuse the repo's canonical modules — never reimplement or hardcode.** All filesystem locations come from one canonical paths module (`simspect_paths`), never a hardcoded string. Parsing, discovery, and config-loading reuse the pipeline's own modules (so the dashboard can't drift from the real pipeline). Optional heavy imports degrade to `None` in a `try/except` and the code checks `if mod is not None:` with an inline fallback — so the dashboard still imports on a laptop checkout that lacks them.

**Cache only the expensive endpoint, with TTL + double-checked locking.** Most endpoints are cheap filesystem reads and aren't cached. The one ~9s scan gets a 5-second TTL cache behind a lock, split into a cached public wrapper + a `_compute` worker:
```python
_PG_LOCK = threading.Lock(); _PG_CACHE = {"t": 0.0, "val": None}; _PG_TTL = 5.0
def pipeline_graph():
    now = time.time()
    if _PG_CACHE["val"] is not None and now - _PG_CACHE["t"] < _PG_TTL:
        return _PG_CACHE["val"]
    with _PG_LOCK:
        if _PG_CACHE["val"] is not None and now - _PG_CACHE["t"] < _PG_TTL:
            return _PG_CACHE["val"]          # another thread computed while we waited
        val = _pipeline_graph_compute(); _PG_CACHE.update(t=now, val=val); return val
```
The reason is written in a comment right there: the page's poll plus a browser's parallel on-load calls would each kick off a cold scan and wedge the page on "loading…"; the TTL makes them share one computation. "Split a cached wrapper from a `_compute` worker" is the reusable shape for anything expensive-and-pollable.

**Pagination and byte caps keep it responsive.** List endpoints take `offset`/`limit` (clamped, with `except (TypeError, ValueError)` defaults) and echo `offset`/`limit`/`total` back; expensive per-item reads only happen for the current page. File reads are capped (`read_bytes()[:MAX]`).

**Writes are atomic and locked.** The few mutating endpoints (add/toggle a todo) write via temp-file + atomic rename under a module-level lock, with human-readable `indent=2` JSON:
```python
with _todo_lock:
    d = _read_todos_json()           # defensively returns {"todos": []} on any corruption
    ...modify d...
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)                # atomic — never a partial file on disk
```
Input is sanitized hard before any write or process spawn: model names checked against a regex, path args rejected if they contain `/`, `\`, or `..` (traversal guard), launch configs required to live inside the repo root. The selftest even fires a `../../etc/passwd` attempt to prove the guard holds.

**Naming:** functions are lowercase `snake_case` and usually just the panel noun (`overview`, `fanout`) or `noun_noun`/`verb_noun` for detail/actions (`run_detail`, `add_todo`). Private helpers get a leading underscore and sit directly above the public function that uses them. Return-dict keys are short domain terms, no Hungarian (`hits`, `total`, `live`, `complete`, `mtime`). Constants are `UPPER_SNAKE`.

**Comment the *why*, with numbers and war-stories.** Comments cite measured latencies ("cold was ~9s; warm ~0.01s"), narrate the bug a code path fixes, and name the real artifact that motivated a special case. Stubs are labeled honestly (`(STUB)`, `# pragma: no cover`) with a pointer to the plan doc.

---

## Layer 2 — the HTTP server

**Keep it tiny and logic-free.** The server is pure routing over stdlib `http.server.ThreadingHTTPServer`. It serves `PAGE` at `/`, maps each `/api/*` path to a data function, and that's nearly all.

**Every data call goes through one error-catcher.** The handler has a `_safe(fn, *a)` that returns the function's result or an `{"error": "..."}` dict — so even if an endpoint somehow raises, the HTTP layer answers JSON instead of a 500:
```python
if path == "/api/overview":  return self._json(self._safe(D.overview))
if path == "/api/corpus":
    model = one("model")
    if not model: return self._json({"error": "model required"}, code=400)
    return self._json(self._safe(D.corpus, model, one("mode"), int(one("offset","0")), ...))
```
Small helpers (`_send`, `_json`, `_safe`, and a `one(key, default)` query-param getter) keep every route a one-liner. POST routes validate required fields and return `code=400` with an error before touching the data layer.

**The server owns markdown rendering.** The docs panel is powered by a hand-rolled `md_to_html()` in the server (fenced code, tables, headings, lists, blockquotes, inline code/links/bold/italic) — so the dashboard can render any `.md` in the repo with no dependency. It finds linked docs by scanning `STATUS.md` for `*.md` references and resolves them against an allow-list of roots (path-traversal safe).

**Loopback + SSH forward is the deployment.** It binds `127.0.0.1` only and prints the forward command on startup (`ssh -N -L 8765:127.0.0.1:8765 <dev-box>`). No auth, no TLS, no exposure — the SSH tunnel is the security boundary.

**A real `--selftest`.** `python3 dashboard.py --selftest` exercises every endpoint once with no server and asserts the page has a doctype — so breakage is caught before deploy.

---

## Layer 3 — the single-page frontend

**One string, three blocks.** `PAGE` is `<head>` + one big `<style>` + a minimal static `<body>` (just mount points: a header with an empty `#mainTabs` and a `#main` container) + one big `<script>`. Everything visible is built by JS into `#main`. Pure vanilla JS — no framework, no libraries, no CDN.

**Design tokens via CSS custom properties, with dark/light by overriding the same names.** `:root` defines the dark palette; `:root[data-theme="light"]` redefines the *same token names* for light. Theme switches by setting `data-theme` on `<html>`. Each block also sets `color-scheme` so native controls and scrollbars follow. The palette is a layered set of surfaces plus a semantic status trio:
```css
--bg:#16181d; --panel:#1e2128; --panel2:#191c22; --border:#2c303a;
--text:#d7dae0; --muted:#7c8190; --accent:#3a6ea5; --link:#6cb0ff;
--err:#e06c5a; --ok:#7bc47b; --warn:#d9b54a; --run:#7bc47b;
```
`--bg < --panel2 < --panel` is the page/nested/card layering; `--err`/`--ok`/`--warn` (red/green/amber) is reused everywhere a status needs a color; `--accent` is the one brand color and is identical in both themes. Status is applied via modifier classes mapped to tokens (`.badge.running{background:var(--run)}`, `.pl-box.bad{border-left-color:var(--err)}`).

**Config-driven two-level tabs.** Tabs are arrays of `{id, label}` (`MAIN_TABS`, `UTIL_TABS`); a `renderTabs()` maps them to clickable chips; `switchTab(id)` sets state, persists the choice to `localStorage`, re-renders the bar, and dispatches to the tab's renderer. Active tab, sub-tab, theme, and refresh interval all persist in `localStorage` and restore on init.

**Three function roles, by prefix — a naming discipline worth copying.**
- `render*` → `async`, fetches an endpoint, returns an HTML string.
- `build*` → pure/sync, returns HTML (or SVG) from already-fetched data.
- `load*` → fetches and injects into an existing element by id.
- plus `open*` (open a modal), `ensure*` (lazily create a singleton modal/timer), `show*`/`switch*` (navigation).

**Rendering is template strings, lists are `.map().join('')`.** The universal idiom is build a big backtick string and assign it to `.innerHTML`; arrays become HTML via `.map(x => \`...\`).join('')` with a `|| '<p class="empty">none</p>'` fallback. DOM-building (`createElement`) is reserved for the modal shells, created once lazily and reused.

**Two fetch helpers that never throw.** `apiCall(path)` wraps `fetch`, returns parsed JSON (or `{html: text}` for non-JSON), and on any error returns `{error: '...'}`; every renderer opens with the same guard ladder: `if (data.error) return '<p class="err">…</p>'; if (!data.items.length) return '<p class="empty">…</p>';`. `apiPost(path, body)` returns an `{ok:false, error}` shape on failure.

**`esc()` on every dynamic value.** A tiny `esc()` (escape via a detached `<div>.textContent`) wraps literally every piece of server/dynamic data interpolated into HTML. This is the single most consistent habit in the frontend — it's what makes "build HTML with template strings" safe.

**The quiet diff-refresh — the signature live-update pattern.** Polling must never disrupt the user. The pattern: fetch, compute a signature (`JSON.stringify(data)`), compare to the stored one; **if unchanged, return and touch nothing** (no spinner, no flicker, no scroll jump); on a transient error, keep the current view; only when it changed, save `window.scrollY`, re-render, then restore scroll. The Status tab's refresh additionally **bails if an input is focused or has text** (`if (ti.value || document.activeElement === ti) return;`) so a poll never wipes something you're typing. Full tab-switches show a spinner; quiet refreshes never do. There's also a refresh-on-`window.focus`.

**Timers:** a generic auto-refresh timer driven by a header dropdown (off/15/30/60s), plus a dedicated faster timer (8s) for the live "centerpiece" tab that only ticks when that tab is active.

**Reusable components, built as template strings:** cards (`.card` + `.card-meta`), status `badge`s (status string = class name), verdict pills, progress bars (`width:${pct}%`), filled/hollow dots (`● / ○` for on/off flags), and native `<details><summary>` for expandable sections (no custom accordion JS). Tables use `tr.clickable` for drill-down. Hit counts render red+bold when `> 0`.

**"Edit in VSCode" everywhere.** The data layer ships a `vscode://` deep-link (`_vscode`) with every record that points at a file; the UI renders a copy-pasted file-bar snippet — `<code>${path}</code> <a class="vscode-link">open in VSCode</a>` — in every file viewer. Every source-of-truth panel is read-mostly with a one-click "edit the real file" escape hatch. (The link form is container/remote-aware via an env var.)

**Modals are one generic `openUModal(title)` + id-based lookup.** Click handlers pass only ids (`openInspector('gem5', model, id)`), and the handler finds the object in a cached payload (`PL_DATA`, etc.) — rather than serializing JSON into HTML attributes. Modals close on backdrop-click and `Escape`. One generic modal is reused by every inspector.

**Hand-rolled inline SVG, no chart libs.** Diagrams (graphs, timelines) are built as SVG strings with `var(--...)` fills (theme-aware), a `<title>` child on every element for hover tooltips, and legends that show the actual line *style*, not just a color chip. A `MutationObserver` on `data-theme` re-renders an open diagram so its colors track a theme switch.

**Small human touches:** submit-on-Enter (`onkeydown="if(event.key==='Enter')..."`), `confirm()` before anything that spawns a real job, drill-in panels `scrollIntoView` after loading below the fold, dropdowns pre-select the likely choice, `title="..."` tooltips throughout, and zero-click defaults so a viewer renders something useful immediately.

**Comments name the author and narrate history** ("kept for reuse", "superseded by…", "the ones Anna cares about"), flag stubs honestly ("coming soon (stub)"), and justify the tricky guards (`if (!target.isConnected) return; // panel may have been replaced while this was in flight`).

---

## The recipe: adding a new panel end-to-end

This is the whole point — a new panel is a handful of touchpoints across the three layers, no plumbing:

1. **Data layer** — write `def newthing()` returning `{"items": [...]}` (or an `ok`-envelope), wrapped in `@_safe(lambda: {"items": []})`. Read your source of truth, add `_path`/`_vscode`. Add it to the selftest list.
2. **Server** — add one route: `if path == "/api/newthing": return self._json(self._safe(D.newthing))`.
3. **Frontend** — add `{ id:'newthing', label:'New Thing' }` to the tabs array; write `async function renderNewThing()` (error-guard → build cards/table with `esc()` on all data → return the string); add one `case 'newthing': html = await renderNewThing(); break;` to the dispatch switch.

Tab-config entry + render function + one switch case + one route + one data function. That's it.

---

## Principles, condensed

- **Zero dependencies.** Stdlib Python + vanilla JS + inline CSS. No pip, no npm, no build, no CDN. It runs anywhere Python does, forever.
- **Surface, don't recompute.** The dashboard reads the same source-of-truth files the real system uses, and reuses the system's own modules — so it can't drift.
- **Never crash a panel.** Every endpoint returns a well-formed empty shape on failure; the UI guards every render.
- **Never disrupt the user.** Quiet diff-refresh: poll freely, but only touch the DOM when data changed, and never clobber a focused input or the scroll position.
- **Read-mostly, with an edit escape hatch.** Show the truth; link to the real file to change it.
- **One function/route/renderer per panel.** Adding a view is mechanical, not architectural.
- **Loopback + SSH forward.** The tunnel is the security boundary; the app has no auth of its own.
