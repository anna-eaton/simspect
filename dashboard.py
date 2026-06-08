#!/usr/bin/env python3
"""
SimSpect status dashboard — a tiny, dependency-free web view of the project's
human dashboards (STATUS.md) plus a live sweep-monitor panel.

    python3 dashboard.py                 # serve on 127.0.0.1:8765
    python3 dashboard.py --port 9000
    python3 dashboard.py --selftest      # render everything once, no server

Then forward the port to your laptop and open it in a browser:
    ssh -N -L 8765:127.0.0.1:8765 <dev-box>        # on your laptop
    open http://127.0.0.1:8765

What it shows (read-only):
  - Both STATUS.md dashboards (Code repo + Paper repo), rendered as HTML.
  - Click-through to every .md the STATUS files reference (resolved + existence-checked).
  - A "Sweep Monitor" tab that runs `sweep_monitor.py --once` (cached, timed-out) and
    shows its colored output.

Stdlib only (no flask/markdown). Binds to loopback by default — reach it via SSH forward.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------- configuration
CODE_ROOT = "/tests/simspect"
PAPER_ROOT = "/tests/SimSpect-S-P-2027"

DASHBOARDS = {
    "code":  {"label": "Code STATUS",  "status": os.path.join(CODE_ROOT,  "STATUS.md"), "root": CODE_ROOT},
    "paper": {"label": "Paper STATUS", "status": os.path.join(PAPER_ROOT, "STATUS.md"), "root": PAPER_ROOT},
}
# roots a /api/md request is allowed to read from (prevents path traversal)
ALLOWED_ROOTS = [os.path.realpath(CODE_ROOT), os.path.realpath(PAPER_ROOT)]
# extra dirs to try when resolving a bare reference like `docs/foo.md`
RESOLVE_BASES = [CODE_ROOT, PAPER_ROOT, "/tests"]

SWEEP_CMD = ["python3", "sweep_monitor.py", "--once"]
SWEEP_CWD = CODE_ROOT
SWEEP_TIMEOUT = 40          # seconds; kill a hung monitor
SWEEP_MIN_INTERVAL = 25     # seconds; don't re-run more often than this

# ---------------------------------------------------------------- markdown -> html
_FENCE = re.compile(r"^```")
_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
_HR = re.compile(r"^([-*_])\1{2,}\s*$")
_BULLET = re.compile(r"^(\s*)([-*])\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _inline(text: str) -> str:
    """Inline markdown -> HTML on an already-plain string."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        # inline code `...`
        if c == "`":
            j = text.find("`", i + 1)
            if j != -1:
                out.append("<code>" + html.escape(text[i + 1:j]) + "</code>")
                i = j + 1
                continue
        # links [text](url)
        if c == "[":
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
            if m:
                out.append('<a href="%s" target="_blank">%s</a>'
                           % (html.escape(m.group(2), quote=True), _inline(m.group(1))))
                i += m.end()
                continue
        # bold **...**
        if text.startswith("**", i):
            j = text.find("**", i + 2)
            if j != -1:
                out.append("<strong>" + _inline(text[i + 2:j]) + "</strong>")
                i = j + 2
                continue
        # italic *...* or _..._
        if c in "*_":
            j = text.find(c, i + 1)
            if j != -1 and j > i + 1 and "\n" not in text[i + 1:j]:
                out.append("<em>" + _inline(text[i + 1:j]) + "</em>")
                i = j + 1
                continue
        out.append(html.escape(c))
        i += 1
    return "".join(out)


def md_to_html(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    html_parts: list[str] = []
    # list nesting stack of (indent, tag)
    list_stack: list[tuple[int, str]] = []
    para: list[str] = []

    def close_lists(to_indent: int = -1):
        while list_stack and list_stack[-1][0] > to_indent:
            html_parts.append("</li></%s>" % list_stack[-1][1])
            list_stack.pop()

    def flush_para():
        if para:
            html_parts.append("<p>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para.clear()

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        # fenced code block
        if _FENCE.match(line.strip()):
            flush_para(); close_lists()
            i += 1
            buf = []
            while i < n and not _FENCE.match(lines[i].strip()):
                buf.append(lines[i]); i += 1
            i += 1  # skip closing fence
            html_parts.append("<pre class='code'>" + html.escape("\n".join(buf)) + "</pre>")
            continue
        # table (header row followed by a |---| separator)
        if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            flush_para(); close_lists()
            def cells(row):
                row = row.strip().strip("|")
                return [c.strip() for c in row.split("|")]
            header = cells(line)
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            t = ["<table><thead><tr>"]
            t += ["<th>%s</th>" % _inline(h) for h in header]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join("<td>%s</td>" % _inline(c) for c in r) + "</tr>")
            t.append("</tbody></table>")
            html_parts.append("".join(t))
            continue
        # heading
        m = _HEAD.match(line)
        if m:
            flush_para(); close_lists()
            lvl = len(m.group(1))
            html_parts.append("<h%d>%s</h%d>" % (lvl, _inline(m.group(2)), lvl))
            i += 1
            continue
        # hr
        if _HR.match(line):
            flush_para(); close_lists()
            html_parts.append("<hr>")
            i += 1
            continue
        # blockquote
        if line.lstrip().startswith(">"):
            flush_para(); close_lists()
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip()[1:].lstrip()); i += 1
            html_parts.append("<blockquote>" + "<br>".join(_inline(x) for x in buf) + "</blockquote>")
            continue
        # list items (with simple indent nesting + continuation lines)
        mb = _BULLET.match(line)
        mo = _ORDERED.match(line)
        if mb or mo:
            flush_para()
            indent = len((mb or mo).group(1))
            tag = "ul" if mb else "ol"
            content = (mb or mo).group(3)
            # gather wrapped continuation lines (indented further, not a new bullet/blank)
            j = i + 1
            while j < n and lines[j].strip() and not _BULLET.match(lines[j]) \
                    and not _ORDERED.match(lines[j]) and not _HEAD.match(lines[j]) \
                    and (len(lines[j]) - len(lines[j].lstrip())) > indent:
                content += " " + lines[j].strip()
                j += 1
            if not list_stack or indent > list_stack[-1][0]:
                html_parts.append("<%s>" % tag)
                list_stack.append((indent, tag))
            else:
                close_lists(indent)
                if not list_stack or list_stack[-1][0] < indent:
                    html_parts.append("<%s>" % tag)
                    list_stack.append((indent, tag))
                else:
                    html_parts.append("</li>")
            html_parts.append("<li>" + _inline(content))
            i = j
            continue
        # blank line
        if not line.strip():
            flush_para(); close_lists()
            i += 1
            continue
        # plain paragraph text
        para.append(line.strip())
        i += 1

    flush_para(); close_lists()
    return "\n".join(html_parts)


# ---------------------------------------------------------------- ansi -> html
_ANSI = re.compile(r"\x1b\[([0-9;]*)m")
_CSI_OTHER = re.compile(r"\x1b\[[0-9;]*[A-HJKf]")  # strip cursor moves etc.
_FG = {30: "#000", 31: "#e06c5a", 32: "#7bc47b", 33: "#d9b54a", 34: "#5a9bd4",
       35: "#c678dd", 36: "#56b6c2", 37: "#ccc",
       90: "#888", 91: "#ff7b6b", 92: "#9be29b", 93: "#f0d060", 94: "#7cb6ef",
       95: "#d99be0", 96: "#7fd6e0", 97: "#fff"}


def ansi_to_html(text: str) -> str:
    text = _CSI_OTHER.sub("", text)
    out, last, open_span = [], 0, False
    for m in _ANSI.finditer(text):
        out.append(html.escape(text[last:m.start()]))
        last = m.end()
        codes = [int(x) for x in m.group(1).split(";") if x != ""] or [0]
        for code in codes:
            if code == 0:
                if open_span:
                    out.append("</span>"); open_span = False
            elif code == 1:
                if open_span:
                    out.append("</span>")
                out.append("<span style='font-weight:bold'>"); open_span = True
            elif code in _FG:
                if open_span:
                    out.append("</span>")
                out.append("<span style='color:%s'>" % _FG[code]); open_span = True
    out.append(html.escape(text[last:]))
    if open_span:
        out.append("</span>")
    return "".join(out)


# ---------------------------------------------------------------- sweep cache
class SweepCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._html = "<em>(not run yet)</em>"
        self._ts = 0.0
        self._running = False

    def get(self) -> tuple[str, float]:
        with self._lock:
            stale = (time.time() - self._ts) > SWEEP_MIN_INTERVAL
            if stale and not self._running:
                self._running = True
                threading.Thread(target=self._run, daemon=True).start()
            return self._html, self._ts

    def _run(self):
        try:
            p = subprocess.run(SWEEP_CMD, cwd=SWEEP_CWD, capture_output=True,
                               text=True, timeout=SWEEP_TIMEOUT)
            raw = p.stdout + (("\n" + p.stderr) if p.stderr.strip() else "")
            body = ansi_to_html(raw) or "<em>(no output)</em>"
        except subprocess.TimeoutExpired:
            body = "<em>sweep_monitor.py --once timed out after %ds</em>" % SWEEP_TIMEOUT
        except Exception as e:  # noqa
            body = "<em>error running sweep_monitor.py: %s</em>" % html.escape(str(e))
        with self._lock:
            self._html = body
            self._ts = time.time()
            self._running = False


SWEEP = SweepCache()


# ---------------------------------------------------------------- md link extraction
def find_md_links(status_path: str, root: str) -> list[dict]:
    try:
        text = open(status_path, encoding="utf-8").read()
    except OSError:
        return []
    seen, out = set(), []
    for raw in re.findall(r"[\w./\-]+\.md", text):
        if raw in seen:
            continue
        seen.add(raw)
        resolved = None
        for base in ([root] + RESOLVE_BASES):
            cand = raw if os.path.isabs(raw) else os.path.join(base, raw)
            cand = os.path.realpath(cand)
            if os.path.isfile(cand) and any(cand.startswith(r) for r in ALLOWED_ROOTS):
                resolved = cand
                break
        if resolved:
            out.append({"label": raw, "path": resolved})
    out.sort(key=lambda d: d["label"].lower())
    return out


def safe_md_path(path: str) -> str | None:
    rp = os.path.realpath(path)
    if rp.endswith(".md") and os.path.isfile(rp) and any(rp.startswith(r) for r in ALLOWED_ROOTS):
        return rp
    return None


def render_status(which: str) -> str:
    cfg = DASHBOARDS[which]
    try:
        text = open(cfg["status"], encoding="utf-8").read()
        return md_to_html(text)
    except OSError as e:
        return "<p class='err'>could not read %s: %s</p>" % (html.escape(cfg["status"]), html.escape(str(e)))


# ---------------------------------------------------------------- HTML shell
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>SimSpect dashboards</title>
<style>
:root{
  --bg:#16181d;--panel:#1e2128;--panel2:#191c22;--border:#2c303a;--text:#d7dae0;
  --heading:#fff;--muted:#7c8190;--accent:#3a6ea5;--link:#6cb0ff;--navlink:#9fb6d6;
  --code-bg:#23272f;--code-text:#e6c07b;--pre-bg:#0f1115;--pre-text:#cdd3dc;
  --tab-bg:#272b34;--tab-text:#aab;--hover:#23272f;--quote-bg:#1b1e25;--err:#e06c5a;
  color-scheme:dark;
}
:root[data-theme="light"]{
  --bg:#f7f8fa;--panel:#ffffff;--panel2:#eef1f5;--border:#d6dae1;--text:#2a2e35;
  --heading:#14171c;--muted:#5f6772;--accent:#3a6ea5;--link:#1a5fb4;--navlink:#1a5fb4;
  --code-bg:#eceff3;--code-text:#9a5b00;--pre-bg:#f2f4f7;--pre-text:#2a2e35;
  --tab-bg:#e6e9ee;--tab-text:#555;--hover:#e3e8ef;--quote-bg:#eef1f5;--err:#c0392b;
  color-scheme:light;
}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--border);display:flex;
       align-items:center;gap:14px;position:sticky;top:0;z-index:5}
header h1{font-size:15px;margin:0;font-weight:600;color:var(--heading)}
.tabs{display:flex;gap:6px}
.tab{padding:5px 12px;border-radius:6px;cursor:pointer;background:var(--tab-bg);color:var(--tab-text);border:1px solid var(--border)}
.tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.meta{margin-left:auto;color:var(--muted);font-size:12px;display:flex;gap:12px;align-items:center}
#theme{padding:4px 10px;border-radius:6px;cursor:pointer;background:var(--tab-bg);
       color:var(--tab-text);border:1px solid var(--border);font-size:12px}
.wrap{display:flex;min-height:calc(100vh - 46px)}
nav{width:280px;border-right:1px solid var(--border);padding:12px;overflow:auto;background:var(--panel2)}
nav h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:14px 0 6px}
nav a{display:block;padding:4px 8px;border-radius:5px;color:var(--navlink);cursor:pointer;
      text-decoration:none;word-break:break-all;font-size:12.5px}
nav a:hover{background:var(--hover)}
main{flex:1;padding:22px 30px;overflow:auto;max-width:1000px}
h1,h2,h3,h4{color:var(--heading);line-height:1.25}
h2{border-bottom:1px solid var(--border);padding-bottom:5px;margin-top:26px}
code{background:var(--code-bg);padding:1px 5px;border-radius:4px;font-size:12.5px;
     font-family:ui-monospace,Menlo,Consolas,monospace;color:var(--code-text)}
pre.code{background:var(--pre-bg);border:1px solid var(--border);border-radius:8px;padding:12px;overflow:auto;
         font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;color:var(--pre-text);white-space:pre-wrap}
a{color:var(--link)}
hr{border:0;border-top:1px solid var(--border);margin:18px 0}
blockquote{border-left:3px solid var(--accent);margin:10px 0;padding:2px 12px;color:var(--muted);background:var(--quote-bg)}
table{border-collapse:collapse;margin:12px 0;width:100%}
th,td{border:1px solid var(--border);padding:6px 10px;text-align:left;vertical-align:top}
th{background:var(--code-bg)}
ul,ol{padding-left:22px}
li{margin:2px 0}
.err{color:var(--err)}
.docref{margin-top:8px;padding:8px 10px;background:var(--quote-bg);border:1px solid var(--border);border-radius:6px}
.docref h4{margin:0 0 6px;font-size:12px;color:var(--muted)}
/* terminal output stays dark in both themes so ANSI colors keep their contrast */
#sweep{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;white-space:pre-wrap;
       background:#0f1115;border:1px solid var(--border);border-radius:8px;padding:14px;color:#cdd3dc}
.spin{color:var(--muted)}
</style></head><body>
<header>
  <h1>SimSpect</h1>
  <div class="tabs">
    <div class="tab" data-view="code">Code STATUS</div>
    <div class="tab" data-view="paper">Paper STATUS</div>
    <div class="tab" data-view="sweep">Sweep Monitor</div>
  </div>
  <div class="meta">
    <button id="theme" title="toggle light/dark">🌙 dark</button>
    <label>auto-refresh <select id="iv">
      <option value="0">off</option><option value="15">15s</option>
      <option value="30" selected>30s</option><option value="60">60s</option>
    </select></label>
    <span id="updated"></span>
  </div>
</header>
<div class="wrap">
  <nav id="nav"></nav>
  <main id="main"><p class="spin">loading…</p></main>
</div>
<script>
let view="code", timer=null;
const main=document.getElementById('main'), nav=document.getElementById('nav'),
      updated=document.getElementById('updated'), themeBtn=document.getElementById('theme');
function applyTheme(t){
  document.documentElement.setAttribute('data-theme',t);
  themeBtn.textContent = t==='light' ? '☀️ light' : '🌙 dark';
  localStorage.setItem('theme',t);
}
themeBtn.onclick=()=>applyTheme(
  document.documentElement.getAttribute('data-theme')==='light' ? 'dark' : 'light');
applyTheme(localStorage.getItem('theme')||'dark');
function setActive(){document.querySelectorAll('.tab').forEach(t=>
  t.classList.toggle('active', t.dataset.view===view));}
async function loadNav(){
  const r=await fetch('/api/links'); const d=await r.json();
  let h='';
  for(const grp of d){
    h+='<h3>'+grp.label+' docs</h3>';
    if(!grp.links.length) h+='<div class="spin" style="padding:4px 8px">none found</div>';
    for(const l of grp.links) h+='<a data-path="'+encodeURIComponent(l.path)+'">'+l.label+'</a>';
  }
  nav.innerHTML=h;
  nav.querySelectorAll('a[data-path]').forEach(a=>a.onclick=()=>openDoc(a.dataset.path,a.textContent));
}
async function openDoc(path,label){
  view='doc'; setActive();
  main.innerHTML='<p class="spin">loading '+label+'…</p>';
  const r=await fetch('/api/md?path='+path);
  main.innerHTML='<p><a id="back">&larr; back to dashboards</a></p>'+(await r.text());
  document.getElementById('back').onclick=()=>show('code');
  stamp();
}
async function show(v){
  view=v; setActive();
  if(v==='sweep'){
    const r=await fetch('/api/sweep');
    main.innerHTML='<h2>Sweep Monitor <code>sweep_monitor.py --once</code></h2><div id="sweep">'+(await r.text())+'</div>';
  }else if(v==='code'||v==='paper'){
    const r=await fetch('/api/status?which='+v);
    main.innerHTML=await r.text();
  }
  stamp();
}
function stamp(){updated.textContent='updated '+new Date().toLocaleTimeString();}
function refresh(){ if(view==='code'||view==='paper'||view==='sweep') show(view); }
function setIv(){ if(timer)clearInterval(timer); const s=+document.getElementById('iv').value;
  if(s>0) timer=setInterval(refresh,s*1000); }
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>show(t.dataset.view));
document.getElementById('iv').onchange=setIv;
window.addEventListener('focus',refresh);
loadNav(); show('code'); setIv();
</script></body></html>"""


# ---------------------------------------------------------------- HTTP handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, body: str, ctype="text/html; charset=utf-8", code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self._send(PAGE)
        if u.path == "/api/status":
            which = (q.get("which") or ["code"])[0]
            if which not in DASHBOARDS:
                return self._send("<p class='err'>unknown dashboard</p>", code=404)
            return self._send(render_status(which))
        if u.path == "/api/links":
            import json
            groups = [{"label": cfg["label"].split()[0],
                       "links": find_md_links(cfg["status"], cfg["root"])}
                      for cfg in DASHBOARDS.values()]
            return self._send(json.dumps(groups), ctype="application/json")
        if u.path == "/api/md":
            path = (q.get("path") or [""])[0]
            rp = safe_md_path(path)
            if not rp:
                return self._send("<p class='err'>file not allowed or not found</p>", code=404)
            try:
                body = "<h2><code>%s</code></h2>" % html.escape(rp) + md_to_html(open(rp, encoding="utf-8").read())
            except OSError as e:
                body = "<p class='err'>%s</p>" % html.escape(str(e))
            return self._send(body)
        if u.path == "/api/sweep":
            body, ts = SWEEP.get()
            note = "" if ts else "<div class='spin'>running sweep_monitor.py… refresh in a moment</div>"
            return self._send(note + body)
        return self._send("<p class='err'>404</p>", code=404)


def selftest():
    for which in DASHBOARDS:
        h = render_status(which)
        print("[ok] %-6s STATUS -> %d bytes html" % (which, len(h)))
        for l in find_md_links(DASHBOARDS[which]["status"], DASHBOARDS[which]["root"]):
            assert safe_md_path(l["path"]), l
        print("       %d linked .md docs resolved" % len(find_md_links(DASHBOARDS[which]["status"], DASHBOARDS[which]["root"])))
    print("[ok] markdown render + link resolution clean")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--selftest", action="store_true", help="render once, no server")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("SimSpect dashboard on http://%s:%d  (Ctrl-C to stop)" % (a.host, a.port))
    print("forward it:  ssh -N -L %d:127.0.0.1:%d <dev-box>" % (a.port, a.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
