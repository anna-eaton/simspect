#!/usr/bin/env python3
"""
classify_uv3_cold.py: bucket CleanupSpec footprint hits per offending line (2026-11-08, cache-setup session).

Input: testrun.py campaign dirs run with pipeline.keep_tmp=true (raw records in
<campaign>/<mode>/_sweep_raw/*.json carry `workdir`, `offending`, `terms_fired`,
`xmit_pc`). Traces are read from the kept workdir, else from
<campaign>/diagnostics/traces/<mode>/<record>.pipeview.txt.gz (uv3_rmw_evidence.py).

Per offending line (struct, line, event_ids) of a hit record:
  textbook_uv3  every offending event is a `fill` with req=st (L1D msg=ST / L2 msg=GETX),
                from state NP/I (the line was not present), by the xmit pc, by an
                instance (seq) that never retired, and the trace has
                `L1D:cleanup_skip line=<line> seq=<seq> why=nohitinfo` for it
                (the same chain as STAGE3_gem5/triage/uv3_rmw_evidence.py judge()).
  em_upgrade    the trace has `L1D:cleanup_skip line=<line> ... ev=Inv_CLEANUP st=M` and an
                `L1D:hit line=<line> st=E nst=M req=st` by the xmit pc from a never-retired
                seq (older load installs E, RMW upgrades E->M, cleanup skipped on M; the
                warm-run example inst-021314).
  uv4_split     every offending event is a fill by a never-retired seq whose cleanup was
                skipped with `cleanup_skip line=<line> seq=<seq> why=split` (AMuLeT UV4,
                a line-crossing speculative load).
  other         anything else (reason recorded).
Record bucket: UV3_textbook (all lines textbook), UV3_textbook_plus_other, EM_upgrade (all
lines em_upgrade), EM_upgrade_plus_other, UV4_split, UV4_split_plus_other, NEW. Stem bucket: the record buckets of its
hitting variants (a stem is UV3_textbook only if every hitting variant is).
Also reports, per stem present in every campaign, lc_retire->fnc_retire (cycles) to see
whether cold lengthens the speculative window.

Usage: python3 classify_uv3_cold.py --out <json> <campaign_dir> [<campaign_dir> ...]
"""
import argparse
import gzip
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PREFIX = "O3PipeView:simspect:"


def open_trace(rec, camp: Path, mode: str):
    wd = rec.get("workdir")
    if wd and (Path(wd) / "m5out" / "pipeview.txt").exists():
        return open(Path(wd) / "m5out" / "pipeview.txt", errors="replace")
    gz = camp / "diagnostics" / "traces" / mode / f"{rec['name']}.pipeview.txt.gz"
    if gz.exists():
        return gzip.open(gz, "rt", errors="replace")
    return None


def parse(fh):
    ev, skips, hits, retired, cur = {}, [], [], set(), None
    for ln in fh:
        if ln.startswith(PREFIX):
            p = ln.rstrip("\n").split(":")
            kv = dict(x.split("=", 1) for x in p[5:] if "=" in x)
            kv.update(tick=int(p[2]), struct=p[3], kind=p[4])
            if kv.get("id", "-") != "-":
                ev[int(kv["id"])] = kv
            if p[3] == "L1D" and p[4] == "cleanup_skip":
                skips.append(kv)
            if p[3] == "L1D" and p[4] == "hit" and kv.get("req") == "st" and kv.get("st") == "E" \
               and kv.get("nst") == "M":
                hits.append(kv)
        elif ln.startswith("O3PipeView:fetch:"):
            q = ln.split(":")
            cur = int(q[5]) if len(q) > 5 and q[5].strip().isdigit() else None
        elif ln.startswith("O3PipeView:retire:") and cur is not None:
            if int(ln.split(":")[2]) > 0:
                retired.add(cur)
            cur = None
    return ev, skips, hits, retired


def judge_line(o, xpc, ev, skips, hits, retired):
    line = o["line"]
    seqs, ok = [], True
    for eid in o["event_ids"]:
        e = ev.get(int(eid))
        want = {"L1D": "ST", "L2": "GETX"}.get(e["struct"]) if e else None
        if not (e and e["kind"] == "fill" and want and e.get("req") == "st" and e.get("msg") == want
                and e.get("line") == line and e.get("st") in ("NP", "I")
                and e.get("pc") not in (None, "-") and int(e["pc"], 16) == xpc
                and e.get("seq") not in (None, "-") and int(e["seq"]) not in retired):
            ok = False
            break
        if not any(s.get("line") == line and s.get("seq") == e["seq"] and s.get("why") == "nohitinfo"
                   for s in skips):
            ok = False
            break
        seqs.append(int(e["seq"]))
    if ok and seqs:
        return "textbook_uv3", f"req=st fill(s) by xmit seq {seqs}, cleanup_skip why=nohitinfo"
    em_skip = [s for s in skips if s.get("line") == line and s.get("ev") == "Inv_CLEANUP"
               and s.get("st") == "M"]
    em_hit = [h for h in hits if h.get("line") == line and h.get("pc") not in (None, "-")
              and int(h["pc"], 16) == xpc and h.get("seq") not in (None, "-")
              and int(h["seq"]) not in retired]
    if em_skip and em_hit:
        return "em_upgrade", f"xmit E->M hit seq {em_hit[0]['seq']}, cleanup_skip Inv_CLEANUP st=M id {em_skip[0].get('id')}"
    split = []
    for eid in o.get("event_ids") or []:
        e = ev.get(int(eid))
        if not (e and e["kind"] == "fill" and e.get("line") == line and e.get("seq") not in (None, "-")
                and int(e["seq"]) not in retired
                and any(s.get("line") == line and s.get("seq") == e["seq"] and s.get("why") == "split"
                        for s in skips)):
            split = []
            break
        split.append(int(e["seq"]))
    if split:
        return "uv4_split", f"fill by unretired seq {split}, cleanup_skip why=split (AMuLeT UV4)"
    e0 = ev.get(int(o["event_ids"][0])) if o.get("event_ids") else None
    d = (f"{e0['struct']}:{e0['kind']} req={e0.get('req')} msg={e0.get('msg')} st={e0.get('st')} "
         f"pc={e0.get('pc')} seq={e0.get('seq')}") if e0 else "no event"
    return "other", d


def record_bucket(kinds):
    s = set(kinds)
    if s == {"textbook_uv3"}:
        return "UV3_textbook"
    if "textbook_uv3" in s:
        return "UV3_textbook_plus_other"
    if s == {"em_upgrade"}:
        return "EM_upgrade"
    if "em_upgrade" in s:
        return "EM_upgrade_plus_other"
    if s == {"uv4_split"}:
        return "UV4_split"
    if "uv4_split" in s:
        return "UV4_split_plus_other"
    return "NEW"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaigns", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    report = {}
    windows = defaultdict(dict)
    for camp in a.campaigns:
        camp = camp.resolve()
        stems = defaultdict(list)
        n_rec, n_err, statuses = 0, 0, Counter()
        for mode_dir in sorted(camp.glob("mispredict_*")):
            mode = mode_dir.name
            for rf in sorted((mode_dir / "_sweep_raw").glob("*.json")):
                for rec in json.loads(rf.read_text()):
                    n_rec += 1
                    statuses[rec.get("status")] += 1
                    key = f"{mode}/{rec['name'].split('__')[0]}"
                    if rec.get("lc_retire") and rec.get("fnc_retire"):
                        windows[key][camp.name] = (rec["fnc_retire"] - rec["lc_retire"]) / 500.0
                    if rec.get("issued_in_window") is not True:
                        continue
                    fh = open_trace(rec, camp, mode)
                    if fh is None:
                        stems[key].append(dict(record=rec["name"], bucket="NEW", why="no trace"))
                        continue
                    with fh:
                        ev, skips, hits, retired = parse(fh)
                    xpc = int(rec["xmit_pc"], 16)
                    lines = [dict(struct=o["struct"], line=o["line"],
                                  **dict(zip(("kind", "why"), judge_line(o, xpc, ev, skips, hits, retired))))
                             for o in rec.get("offending") or []]
                    b = record_bucket([l["kind"] for l in lines]) if lines else "NEW"
                    if set(rec.get("terms_fired") or []) - {"under_clean"} and b != "NEW":
                        b += "+terms:" + ",".join(sorted(rec["terms_fired"]))
                    stems[key].append(dict(record=rec["name"], bucket=b, terms=rec.get("terms_fired"),
                                           xmit_pc=rec["xmit_pc"], lines=lines))
        per_stem = {}
        for k, vs in stems.items():
            bs = {v["bucket"] for v in vs}
            per_stem[k] = dict(bucket=(bs.pop() if len(bs) == 1 else "MIXED:" + "|".join(sorted(bs))),
                               variants=vs)
        report[camp.name] = dict(records=n_rec, statuses=dict(statuses), hit_stems=len(per_stem),
                                 buckets=dict(Counter(v["bucket"] for v in per_stem.values())),
                                 stems=per_stem)
    names = [c.resolve().name for c in a.campaigns]
    common = [k for k, v in windows.items() if all(n in v for n in names)]
    report["_window_cycles_lc_to_fnc_retire"] = {
        n: dict(n=len(common), median=statistics.median(windows[k][n] for k in common) if common else None,
                mean=statistics.mean(windows[k][n] for k in common) if common else None)
        for n in names}
    a.out.write_text(json.dumps(report, indent=1) + "\n")
    for n in names:
        r = report[n]
        print(n, "records", r["records"], r["statuses"], "hit stems", r["hit_stems"], r["buckets"])
    print("window", json.dumps(report["_window_cycles_lc_to_fnc_retire"]))


if __name__ == "__main__":
    sys.exit(main())
