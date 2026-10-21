#!/usr/bin/env python3
"""
SimSpect dashboard — a stdlib-only, dependency-free live web console for the
whole pipeline: Alloy Generation, Fanout/concretization, gem5 campaigns, the
Corpora browser, plus a utility panel (annotation/checker viewer, fanout tables,
launch-fanout, execution-graph stub) and the consolidated docs (STATUS.md + the
.md files it links).

    python3 dashboard.py                 # serve on 127.0.0.1:8765
    python3 dashboard.py --port 9000
    python3 dashboard.py --selftest      # exercise every endpoint once, no server

Reach it from your laptop over an SSH forward:
    ssh -N -L 8765:127.0.0.1:8765 <dev-box>        # on your laptop
    open http://127.0.0.1:8765

Binds loopback only. All data comes from dashboard_data.py (which reuses
sweep_monitor / parsexml / jobs_registry); the single-page UI is dashboard_ui.PAGE.
Paths are canonical via simspect_paths (no hardcoded /tests/simspect).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# This file lives in dashboard/; the shared modules (simspect_paths, jobs_registry,
# sweep_monitor, pipeline) live at the repo root. Put the repo root on sys.path so
# they import whether run as `python3 dashboard/dashboard.py` or from the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import simspect_paths as P
import dashboard_data as D
from dashboard_ui import PAGE

# ---------------------------------------------------------------- docs config
# Consolidated docs: the code repo's STATUS.md + anything it links, plus the
# paper repo if it exists on this host (it won't on a laptop checkout).
CODE_ROOT = str(P.ROOT)
PAPER_ROOT = "/tests/SimSpect-S-P-2027"

DASHBOARDS = {"code": {"label": "Code STATUS",
                       "status": os.path.join(CODE_ROOT, "STATUS.md"),
                       "root": CODE_ROOT}}
if os.path.isdir(PAPER_ROOT):
    DASHBOARDS["paper"] = {"label": "Paper STATUS",
                           "status": os.path.join(PAPER_ROOT, "STATUS.md"),
                           "root": PAPER_ROOT}

ALLOWED_ROOTS = [os.path.realpath(d["root"]) for d in DASHBOARDS.values()]
RESOLVE_BASES = [d["root"] for d in DASHBOARDS.values()] + ["/tests"]


# ---------------------------------------------------------------- markdown -> html
_FENCE = re.compile(r"^```")
_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
_HR = re.compile(r"^([-*_])\1{2,}\s*$")
_BULLET = re.compile(r"^(\s*)([-*])\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _inline(text: str) -> str:
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "`":
            j = text.find("`", i + 1)
            if j != -1:
                out.append("<code>" + html.escape(text[i + 1:j]) + "</code>")
                i = j + 1
                continue
        if c == "[":
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
            if m:
                out.append('<a href="%s" target="_blank">%s</a>'
                           % (html.escape(m.group(2), quote=True), _inline(m.group(1))))
                i += m.end()
                continue
        if text.startswith("**", i):
            j = text.find("**", i + 2)
            if j != -1:
                out.append("<strong>" + _inline(text[i + 2:j]) + "</strong>")
                i = j + 2
                continue
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
    html_parts: list = []
    list_stack: list = []
    para: list = []

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
        if _FENCE.match(line.strip()):
            flush_para(); close_lists()
            i += 1
            buf = []
            while i < n and not _FENCE.match(lines[i].strip()):
                buf.append(lines[i]); i += 1
            i += 1
            html_parts.append("<pre class='code'>" + html.escape("\n".join(buf)) + "</pre>")
            continue
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
        m = _HEAD.match(line)
        if m:
            flush_para(); close_lists()
            lvl = len(m.group(1))
            html_parts.append("<h%d>%s</h%d>" % (lvl, _inline(m.group(2)), lvl))
            i += 1
            continue
        if _HR.match(line):
            flush_para(); close_lists()
            html_parts.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith(">"):
            flush_para(); close_lists()
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip()[1:].lstrip()); i += 1
            html_parts.append("<blockquote>" + "<br>".join(_inline(x) for x in buf) + "</blockquote>")
            continue
        mb = _BULLET.match(line)
        mo = _ORDERED.match(line)
        if mb or mo:
            flush_para()
            indent = len((mb or mo).group(1))
            tag = "ul" if mb else "ol"
            content = (mb or mo).group(3)
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
        if not line.strip():
            flush_para(); close_lists()
            i += 1
            continue
        para.append(line.strip())
        i += 1

    flush_para(); close_lists()
    return "\n".join(html_parts)


# ---------------------------------------------------------------- docs helpers
def find_md_links(status_path: str, root: str) -> list:
    try:
        text = open(status_path, encoding="utf-8").read()
    except OSError:
        return []
    seen, out = set(), []
    for raw in re.findall(r"[\w./\-]+\.md", text):
        if raw in seen:
            continue
        seen.add(raw)
        for base in ([root] + RESOLVE_BASES):
            cand = raw if os.path.isabs(raw) else os.path.join(base, raw)
            cand = os.path.realpath(cand)
            if os.path.isfile(cand) and any(cand.startswith(r) for r in ALLOWED_ROOTS):
                out.append({"label": raw, "path": cand})
                break
    out.sort(key=lambda d: d["label"].lower())
    return out


def safe_md_path(path: str):
    rp = os.path.realpath(path)
    if rp.endswith(".md") and os.path.isfile(rp) and any(rp.startswith(r) for r in ALLOWED_ROOTS):
        return rp
    return None


def render_status(which: str) -> str:
    cfg = DASHBOARDS.get(which)
    if not cfg:
        return "<p class='err'>unknown dashboard</p>"
    try:
        return md_to_html(open(cfg["status"], encoding="utf-8").read())
    except OSError as e:
        return "<p class='err'>could not read %s: %s</p>" % (
            html.escape(cfg["status"]), html.escape(str(e)))


# ---------------------------------------------------------------- HTTP handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj), ctype="application/json", code=code)

    def _safe(self, fn, *a, **k):
        """Call a dashboard_data function, returning its result or an error dict."""
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa
            return {"error": "%s: %s" % (type(e).__name__, e)}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        one = lambda k, d=None: (q.get(k) or [d])[0]
        path = u.path

        if path == "/":
            return self._send(PAGE)

        # ── live status ───────────────────────────────────────────────
        if path == "/api/overview":
            return self._json(self._safe(D.overview))
        if path == "/api/generation":
            return self._json(self._safe(D.generation))
        if path == "/api/fanout":
            return self._json(self._safe(D.fanout))
        if path == "/api/jobs":
            return self._json(self._safe(D.overview))

        # ── corpora browser ───────────────────────────────────────────
        if path == "/api/corpora":
            return self._json(self._safe(D.corpora))
        if path == "/api/corpus":
            model = one("model")
            if not model:
                return self._json({"error": "model required"}, code=400)
            mode = one("mode")
            offset = int(one("offset", "0") or 0)
            limit = int(one("limit", "200") or 200)
            return self._json(self._safe(D.corpus, model, mode, offset, limit))
        if path == "/api/test":
            return self._json(self._safe(D.test_features,
                                         one("model"), one("mode"), one("stem")))
        if path == "/api/file":
            res = self._safe(D.file_text, one("model"), one("mode"),
                             one("stem"), one("kind"))
            if isinstance(res, dict) and res.get("ok"):
                return self._json({"ok": True, "text": res.get("text", ""),
                                   "path": res.get("path"),
                                   "vscode": D.vscode_uri(res.get("path", ""))})
            err = res.get("error") if isinstance(res, dict) else "file not available"
            return self._json({"ok": False, "error": err or "file not available"},
                              code=404)

        # ── unified pipeline stage graph + sources-of-truth specs ──────
        if path == "/api/pipeline":
            return self._json(self._safe(D.pipeline_graph))
        if path == "/api/specs":
            return self._json(self._safe(D.specs))
        if path == "/api/models":
            return self._json(self._safe(D.model_inventory))
        if path == "/api/model":
            return self._json(self._safe(D.model_source, one("name")))
        if path == "/api/catalog":
            return self._json(self._safe(D.catalog, one("kind")))
        if path == "/api/hit_categories":
            return self._json(self._safe(D.hit_categories))
        if path == "/api/run":
            return self._json(self._safe(D.run_detail, one("name")))
        if path == "/api/run_hits":
            return self._json(self._safe(D.run_hit_stems, one("name"),
                                         one("bucket"), one("mode"), one("limit", "500")))
        if path == "/api/defense_units":
            return self._json(self._safe(D.defense_units))
        if path == "/api/transmitter_criteria":
            return self._json(self._safe(D.transmitter_criteria))

        # ── utilities ─────────────────────────────────────────────────
        if path == "/api/tables":
            return self._json(self._safe(D.instruction_tables))
        if path == "/api/checkers":
            return self._json(self._safe(D.checkers))
        if path == "/api/execgraph":
            return self._json(self._safe(D.exec_graph, one("model"), one("stem")))

        # ── consolidated docs ─────────────────────────────────────────
        if path == "/api/docs":
            groups = [{"label": cfg["label"].split()[0],
                       "links": find_md_links(cfg["status"], cfg["root"])}
                      for cfg in DASHBOARDS.values()]
            return self._json({"groups": groups})
        if path == "/api/status":
            return self._send(render_status(one("which", "code")))
        if path == "/api/md":
            rp = safe_md_path(one("path", ""))
            if not rp:
                return self._send("<p class='err'>file not allowed or not found</p>",
                                  code=404)
            try:
                _vs = html.escape(D.vscode_uri(rp))
                body = ("<h2><code>%s</code> "
                        "<a class='vscode-link' href='%s'>open in VSCode</a></h2>"
                        % (html.escape(rp), _vs)
                        + md_to_html(open(rp, encoding="utf-8").read()))
            except OSError as e:
                body = "<p class='err'>%s</p>" % html.escape(str(e))
            return self._send(body)

        return self._send("<p class='err'>404</p>", code=404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/launch":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception as e:
                return self._json({"ok": False, "error": "bad request: %s" % e}, code=400)
            model = payload.get("model")
            config = payload.get("config")
            if not model or not config:
                return self._json({"ok": False, "error": "model and config required"},
                                  code=400)
            return self._json(self._safe(D.launch_fanout, model, config))
        return self._json({"error": "404"}, code=404)


# ---------------------------------------------------------------- selftest / main
def selftest():
    checks = [
        ("overview", lambda: D.overview()),
        ("generation", lambda: D.generation()),
        ("fanout", lambda: D.fanout()),
        ("corpora", lambda: D.corpora()),
        ("tables", lambda: D.instruction_tables()),
        ("checkers", lambda: D.checkers()),
        ("docs", lambda: find_md_links(DASHBOARDS["code"]["status"], CODE_ROOT)),
        ("status(code)", lambda: render_status("code")),
    ]
    ok = True
    for name, fn in checks:
        try:
            r = fn()
            print("[ok] %-16s -> %s" % (name, type(r).__name__))
        except Exception as e:  # noqa
            ok = False
            print("[FAIL] %-16s -> %s: %s" % (name, type(e).__name__, e))
    assert "<!doctype html" in PAGE.lower(), "dashboard_ui.PAGE missing doctype"
    print("[ok] PAGE length = %d bytes" % len(PAGE))
    print("selftest:", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--selftest", action="store_true", help="exercise endpoints once, no server")
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
