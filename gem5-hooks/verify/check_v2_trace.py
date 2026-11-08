#!/usr/bin/env python3
"""check_v2_trace.py — structural checks on a SimSpect hooks v2 trace.

Usage: python3 check_v2_trace.py <pipeview.txt> [--build InvisiSpec|CleanupSpec|SpecLFB]

Self-contained (own parser, same rules as STAGE3_gem5/gem5_common.py:
parse_simspect_line). Prints one JSON object; exits 1 if a hard check fails.
Hard checks (each one is a v2 fix from wiki/findings/audits/2026-10-28/APPROVALS.md §E):
  meta        first simspect line is META:hooks with ver=2 and the right build
  parse       every simspect line is <prefix>:<tick>:<struct>:<kind>:k=v...
  v1_fields   the 7 v1 fields appear first, in v1 order
  no_line0    no line=0x0 on the squash-time prints that read a load's
              physEffAddr (SB:buf_release why=squash, L1D:cleanup_skip): an
              untranslated load must print line=- (v1 bug). Other events may
              legitimately name physical line 0x0 (in SE mode the code page at
              vaddr 0x401000 maps to paddr 0x0, so instruction fetch does).
  cause_once  no fill id is the cause= of two evicts (stale g_pendingFill)
  done_once   CleanupSpec: at most one cleanup_done per sq id
  sb_paired   InvisiSpec: every SB:buf_fill with post_squash=1 has a release
Soft facts (reported, never fail): kind counts, SB fills without a release,
LFB fills/releases, LSQ:unsafe flag combinations, cleanup_done without bufd.
Doc: wiki/design/SIMSPECT_HOOKS.md ("How to verify").
"""
import argparse, collections, json, sys

PREFIX = "O3PipeView:simspect:"
V1 = ["line", "seq", "pc", "victim", "cause", "sq", "id"]


def parse(path):
    evs, bad = [], []
    with open(path) as f:
        for n, raw in enumerate(f, 1):
            i = raw.find(PREFIX)   # native prints can glue residue in front (gem5_common._unglue)
            if i < 0:
                continue
            raw = raw[i:]
            p = raw.rstrip("\n").split(":")
            if len(p) < 5:
                bad.append((n, raw.strip()))
                continue
            ev = {"_n": n, "tick": p[2], "struct": p[3], "kind": p[4], "_keys": []}
            ok = True
            for fld in p[5:]:
                if "=" not in fld:
                    ok = False
                    break
                k, v = fld.split("=", 1)
                ev[k] = v
                ev["_keys"].append(k)
            if not ok:
                bad.append((n, raw.strip()))
                continue
            evs.append(ev)
    return evs, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--build")
    a = ap.parse_args()
    evs, bad = parse(a.trace)
    res = {"trace": a.trace, "n_events": len(evs), "hard": {}, "soft": {}}
    hard = res["hard"]

    m = evs[0] if evs else {}
    hard["meta"] = bool(evs) and m["struct"] == "META" and m["kind"] == "hooks" \
        and m.get("ver") == "2" and (a.build is None or m.get("build") == a.build)
    hard["parse"] = not bad
    if bad:
        res["soft"]["bad_lines"] = bad[:10]
    v1bad = [e["_n"] for e in evs if e["_keys"][:7] != V1]
    hard["v1_fields"] = not v1bad
    if v1bad:
        res["soft"]["v1_order_bad_lines"] = v1bad[:10]
    line0 = [e["_n"] for e in evs if e.get("line") == "0x0" and (
        (e["struct"] == "SB" and e["kind"] == "buf_release" and e.get("why") == "squash")
        or e["kind"] == "cleanup_skip")]
    res["soft"]["line0_other_events"] = sum(1 for e in evs if e.get("line") == "0x0") - len(line0)
    hard["no_line0"] = not line0
    if line0:
        res["soft"]["line0_lines"] = line0[:10]

    causes = collections.Counter(e["cause"] for e in evs
                                 if e["kind"] == "evict" and e.get("cause", "-") != "-")
    dup = {c: k for c, k in causes.items() if k > 1}
    hard["cause_once"] = not dup
    if dup:
        res["soft"]["dup_causes"] = dict(list(dup.items())[:10])

    done = collections.Counter(e["sq"] for e in evs if e["kind"] == "cleanup_done")
    hard["done_once"] = all(k == 1 for k in done.values())
    res["soft"]["cleanup_done_per_sq"] = dict(done)
    res["soft"]["squashes"] = sum(1 for e in evs if e["struct"] == "ROB" and e["kind"] == "squash")
    res["soft"]["cleanup_done_bufd0"] = sum(1 for e in evs
                                            if e["kind"] == "cleanup_done" and e.get("bufd") == "0")

    sbf = [(e["seq"], e["line"]) for e in evs if e["struct"] == "SB" and e["kind"] == "buf_fill"]
    sbr = collections.Counter((e["seq"], e["line"]) for e in evs
                              if e["struct"] == "SB" and e["kind"] == "buf_release")
    post = [(e["seq"], e["line"]) for e in evs if e["struct"] == "SB"
            and e["kind"] == "buf_fill" and e.get("post_squash") == "1"]
    hard["sb_paired"] = all(sbr[k] > 0 for k in post)
    res["soft"]["sb_fill_without_release"] = sum(1 for k in sbf if sbr[k] == 0)
    res["soft"]["sb_post_squash_fills"] = len(post)

    res["soft"]["kinds"] = dict(sorted(collections.Counter(
        f'{e["struct"]}:{e["kind"]}' for e in evs).items()))
    res["soft"]["lsq_unsafe_flags"] = dict(collections.Counter(
        "unsafe=%s cusl=%s musl=%s prevnounsafe=%s reallyunsafe=%s lqhead=%s" % tuple(
            e.get(k, "?") for k in ("unsafe", "cusl", "musl", "prevnounsafe", "reallyunsafe", "lqhead"))
        for e in evs if e["struct"] == "LSQ" and e["kind"] == "unsafe"))
    res["soft"]["lfb"] = dict(collections.Counter(
        e["kind"] for e in evs if e["struct"] == "LFB"))
    res["ok"] = all(hard.values())
    print(json.dumps(res, indent=1))
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
