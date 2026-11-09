#!/usr/bin/env python3
"""
cleanupspec_skip_evidence.py: attribute every offending (struct, line) of every
CleanupSpec footprint hit to ONE trace-proven cause, and write the evidence file
read by diag/diag_cs1_store_upgrade.py and diag/diag_uv4_split.py
(unexplained-hits session, 2026-11-09).

Input: a testrun.py campaign dir whose raw checker records
(<campaign>/<mode>/_sweep_raw/*.json) carry check_footprint's `offending` list
(struct, line, event_ids, term) and whose hit traces are kept, either in the
record's `workdir` (m5out/pipeview.txt) or gzipped at
<campaign>/diagnostics/traces/<mode>/<record>.pipeview.txt.gz (uv3_rmw_evidence.py).
Read-only on everything except the output JSON + log.

Per offending item, with S = the event's own seq (the actor), L = the line S
installed, V = the line S evicted (victim terms), Q = the seq of the ROB:squash
whose sq= matches S's cleanup line:
  CS1_older_store_upgrade  (victim item) S never committed; S filled L and
      evicted V; exactly one `L1D:hit line=L st=E nst=M` between S's fill and
      S's cleanup, by U with req=st, U < Q (older than the squashing branch) and
      U committed; then `L1D:cleanup_skip line=L seq=S ev=Inv_CLEANUP st=M`;
      no cleanup_restore of V by S.  (SOURCE_AUDIT_CLEANUPSPEC_SPECLFB.md CS-1;
      MESI_Two_Level-L1cache.sm:2701-2705.)
  EM_upgrade_squashed  same chain but U never committed (the speculative RMW
      transmitter upgrades S's E line; URGENT_TODO DECIDE "CleanupSpec E->M case").
  UV4_split  S never committed and has `cleanup_skip seq=S why=split` (fill
      items: line=L on L1D or L2; victim items: V evicted by S).  AMuLeT UV4.
  UV5_older_load  (over_clean item) S filled L, an older committed U < S hits L
      after the fill, then `L1D:cleanup_inv line=L seq=S`.  AMuLeT UV5.
  unattributed  anything else (reason recorded).
A stem's `causes` is the set over all items of all hitting variants.

Output: <campaign>/diagnostics/cleanupspec_skip_evidence.json keyed "<mode>/<stem>";
log: <campaign>/diagnostics/cleanupspec_skip_evidence.log (start/end, per-stem
verdict, every error with traceback).

Usage: python3 cleanupspec_skip_evidence.py <campaign_dir> [<campaign_dir> ...]
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import traceback
from pathlib import Path

PREFIX = "O3PipeView:simspect:"
COMMIT_RE = re.compile(r"^\s*(\d+): .*Committing instruction with \[sn:(\d+)\]")


def _open(rec, camp: Path, mode: str):
    wd = rec.get("workdir")
    if wd and (Path(wd) / "m5out" / "pipeview.txt").exists():
        return open(Path(wd) / "m5out" / "pipeview.txt", errors="replace")
    gz = camp / "diagnostics" / "traces" / mode / f"{rec['name']}.pipeview.txt.gz"
    if gz.exists():
        return gzip.open(gz, "rt", errors="replace")
    return None


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def parse(fh):
    evs, by_id, committed, cur = [], {}, set(), None
    for ln in fh:
        if ln.startswith(PREFIX):
            p = ln.rstrip("\n").split(":")
            kv = dict(x.split("=", 1) for x in p[5:] if "=" in x)
            kv.update(tick=int(p[2]), struct=p[3], kind=p[4], seqn=_int(kv.get("seq")))
            evs.append(kv)
            if _int(kv.get("id")) is not None:
                by_id[int(kv["id"])] = kv
        elif ln.startswith("O3PipeView:fetch:"):
            q = ln.split(":")
            cur = _int(q[5]) if len(q) > 5 else None
        elif ln.startswith("O3PipeView:retire:") and cur is not None:
            if (_int(ln.split(":")[2]) or 0) > 0:
                committed.add(cur)
            cur = None
        elif "Committing instruction with [sn:" in ln:
            m = COMMIT_RE.match(ln)
            if m:
                committed.add(int(m.group(2)))
    return evs, by_id, committed


def _sel(evs, struct, kind, **kw):
    return [e for e in evs if e["struct"] == struct and e["kind"] == kind
            and all(e.get(k) == v for k, v in kw.items())]


def _squash_seq(evs, sq):
    q = [e["seqn"] for e in evs if e["struct"] == "ROB" and e["kind"] == "squash" and e.get("sq") == sq]
    return q[0] if q else None


def judge(item, evs, by_id, committed):
    ids = item.get("event_ids") or []
    es = [by_id[i] for i in ids if i in by_id]
    if not es or len(es) != len(ids):
        return "unattributed", "offending event id missing from trace"
    e0 = es[0]
    S = e0["seqn"]
    if S is None or S in committed:
        return "unattributed", f"actor seq {e0.get('seq')} committed or unknown"
    line = item["line"]
    split = _sel(evs, "L1D", "cleanup_skip", why="split")
    split_s = {e["seqn"] for e in split}

    if item["term"] == "under_clean" and all(e["kind"] == "evict" and e.get("victim") == line and e["seqn"] == S for e in es):
        L = e0.get("line")
        if S in split_s:
            return "UV4_split", f"S={S} filled {L} evicting V={line}; cleanup_skip seq={S} why=split"
        if _sel(evs, "L1D", "cleanup_restore", line=line, seq=str(S)):
            return "unattributed", "victim restored by S"
        sk = [e for e in _sel(evs, "L1D", "cleanup_skip", line=L, seq=str(S))
              if e.get("ev") == "Inv_CLEANUP" and e.get("st") == "M"]
        if len(sk) != 1:
            return "unattributed", f"S={S}: {len(sk)} Inv_CLEANUP st=M skips on {L}"
        t_fill, t_sk = e0["tick"], sk[0]["tick"]
        Q = _squash_seq(evs, sk[0].get("sq"))
        ups = [e for e in _sel(evs, "L1D", "hit", line=L, st="E", nst="M") if t_fill <= e["tick"] <= t_sk]
        if len(ups) != 1 or ups[0].get("req") != "st" or Q is None or not (S > Q):
            return "unattributed", f"S={S}: {len(ups)} E->M upgraders, squash seq {Q}"
        U = ups[0]["seqn"]
        chain = (f"S={S} fill {L} @{t_fill} evicts V={line}; U={U} st E->M @{ups[0]['tick']} pc={ups[0].get('pc')}; "
                 f"cleanup_skip Inv_CLEANUP st=M @{t_sk} (sq={sk[0].get('sq')}, squash seq {Q}); V never restored")
        if U is not None and U < Q and U in committed:
            return "CS1_older_store_upgrade", chain
        if U is not None and U not in committed and U > Q:
            return "EM_upgrade_squashed", chain
        return "unattributed", "upgrader neither older-committed nor squashed: " + chain

    if item["term"] == "under_clean" and all(e["kind"] == "fill" and e.get("line") == line and e["seqn"] == S for e in es):
        if any(e["seqn"] == S and e.get("line") == line for e in split):
            return "UV4_split", f"S={S} fill {item['struct']} {line}; cleanup_skip line={line} seq={S} why=split"
        sk = [e for e in _sel(evs, "L1D", "cleanup_skip", line=line, seq=str(S))
              if e.get("ev") == "Inv_CLEANUP" and e.get("st") == "M"]
        ups = [e for e in _sel(evs, "L1D", "hit", line=line, st="E", nst="M") if sk and e0["tick"] <= e["tick"] <= sk[0]["tick"]]
        if len(sk) == 1 and len(ups) == 1 and ups[0]["seqn"] not in committed:
            return "EM_upgrade_squashed", f"S={S} fill {line}; squashed U={ups[0]['seqn']} st E->M @{ups[0]['tick']}; cleanup_skip st=M @{sk[0]['tick']}"
        return "unattributed", "install item, no split/E->M chain"

    if item["term"] == "over_clean":
        fills = [e for e in es if e["kind"] == "fill" and e.get("line") == line and e["seqn"] == S]
        invs = _sel(evs, "L1D", "cleanup_inv", line=line, seq=str(S))
        if fills and invs:
            hits = [e for e in _sel(evs, "L1D", "hit", line=line)
                    if fills[0]["tick"] <= e["tick"] <= invs[0]["tick"] and e["seqn"] is not None
                    and e["seqn"] < S and e["seqn"] in committed]
            if hits:
                h = hits[0]
                return "UV5_older_load", (f"S={S} fill {line} @{fills[0]['tick']}; older committed U={h['seqn']} "
                                          f"req={h.get('req')} addr={h.get('addr')} size={h.get('size')} hits @{h['tick']}; "
                                          f"cleanup_inv @{invs[0]['tick']}")
        return "unattributed", "over_clean without older committed hit"
    return "unattributed", f"term {item['term']} events {[e['kind'] for e in es]}"


def run(camp: Path):
    out_dir = camp / "diagnostics"
    out_dir.mkdir(exist_ok=True)
    log = (out_dir / "cleanupspec_skip_evidence.log").open("w")
    t0 = time.time()
    log.write(f"start {time.strftime('%F %T')} campaign={camp}\n")
    res = {}
    for mdir in sorted(camp.glob("mispredict_*")):
        mode = mdir.name
        for rf in sorted(mdir.glob("_sweep_raw/*.json")):
            data = json.loads(rf.read_text())
            recs = data if isinstance(data, list) else (data.get("results") or list(data.values()))
            for rec in recs:
                if not (isinstance(rec, dict) and rec.get("issued_in_window")):
                    continue
                stem = rec["name"].split("__")[0]
                key = f"{mode}/{stem}"
                try:
                    fh = _open(rec, camp, mode)
                    if fh is None:
                        items = [dict(o, cause="unattributed", why="no trace") for o in rec.get("offending", [])]
                    else:
                        with fh:
                            evs, by_id, committed = parse(fh)
                        items = []
                        for o in rec.get("offending", []):
                            c, why = judge(o, evs, by_id, committed)
                            items.append(dict(o, cause=c, why=why))
                except Exception:
                    log.write(f"ERROR {key} {rec['name']}\n{traceback.format_exc()}\n")
                    items = [dict(cause="unattributed", why="exception (see log)")]
                ent = res.setdefault(key, {"variants": []})
                ent["variants"].append({"record": rec["name"], "terms": rec.get("terms_fired"),
                                        "inconsistent": rec.get("inconsistent"), "items": items})
    for key, ent in res.items():
        ent["causes"] = sorted({i["cause"] for v in ent["variants"] for i in v["items"]})
        log.write(f"{key} causes={ent['causes']}\n")
        for v in ent["variants"]:
            for i in v["items"]:
                log.write(f"    {v['record']} {i.get('struct')} {i.get('line')} {i.get('term')} -> {i['cause']}: {i['why']}\n")
    (out_dir / "cleanupspec_skip_evidence.json").write_text(json.dumps(res, indent=1) + "\n")
    log.write(f"end {time.strftime('%F %T')} stems={len(res)} elapsed={time.time() - t0:.1f}s\n")
    log.close()
    print(f"{camp}: {len(res)} hit stems -> {out_dir / 'cleanupspec_skip_evidence.json'}")
    for key, ent in sorted(res.items()):
        print(f"  {key}: {ent['causes']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for c in sys.argv[1:]:
        run(Path(c))
