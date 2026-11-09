#!/usr/bin/env python3
"""
cleanupspec_em_evidence.py (bug-investigate-em, 2026-11-09): attribute CleanupSpec footprint hits
to the E->M squashed-RMW cleanup skip and write the evidence file read by
diag/diag_cleanupspec_em.py. Read-only on the campaign unless --out-dir is omitted.

Reuses cleanupspec_skip_evidence.py parse()/judge() (same directory) and re-checks every
EM_upgrade_squashed item strictly: the upgrader U is at the record's xmit pc, req=st, never
committed, younger than the squashing branch Q; the installer S never committed, S > Q, S != U;
the L1D hit is st=E nst=M; exactly one `cleanup_skip line=L seq=S ev=Inv_CLEANUP st=M`; U's own
cleanup is `cleanup_skip why=l1hit`. Passing items get cause EM_rmw_squashed, failing ones
EM_loose (stay NEW); every other cause is judge()'s (CS1_older_store_upgrade, UV4_split, ...).

Output: <out-dir or campaign/diagnostics>/cleanupspec_em_evidence.{json,log}, keyed "<mode>/<stem>";
the log has start/end, per-stem causes and every error with traceback.
Usage: python3 cleanupspec_em_evidence.py <campaign_dir> [--out-dir DIR]
"""
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleanupspec_skip_evidence as B  # noqa: E402


def strict(item, rec, evs, committed):
    line = item["line"]
    if item["term"] != "under_clean":
        return False, "not under_clean"
    es = [e for e in evs if str(e.get("id")) in {str(i) for i in item["event_ids"]}]
    S = es[0]["seqn"]
    L = es[0].get("line") if es[0]["kind"] == "evict" else line
    sk = [e for e in B._sel(evs, "L1D", "cleanup_skip", line=L, seq=str(S))
          if e.get("ev") == "Inv_CLEANUP" and e.get("st") == "M"]
    if len(sk) != 1:
        return False, f"{len(sk)} st=M skips"
    Q = B._squash_seq(evs, sk[0].get("sq"))
    t0 = min(e["tick"] for e in es)
    ups = [e for e in B._sel(evs, "L1D", "hit", line=L, st="E", nst="M") if t0 <= e["tick"] <= sk[0]["tick"]]
    if len(ups) != 1:
        return False, f"{len(ups)} upgraders"
    u = ups[0]
    U = u["seqn"]
    xpc = rec.get("xmit_pc")
    ok = (u.get("req") == "st" and xpc and int(u.get("pc", "0"), 16) == int(xpc, 16)
          and U not in committed and S not in committed and Q is not None and U > Q and S > Q and S != U)
    if not ok:
        return False, f"S={S} U={U} pc={u.get('pc')} xmit={xpc} req={u.get('req')} Q={Q}"
    own = [e for e in B._sel(evs, "L1D", "cleanup_skip", seq=str(U)) if e.get("why") == "l1hit"]
    if not own:
        return False, f"U={U} has no cleanup_skip why=l1hit"
    order = "S<U" if S < U else "S>U"
    return True, (f"{item['struct']} {line}: S={S} pc={es[0].get('pc')} installs {L} @{t0} (E); squashed RMW xmit U={U} "
                  f"pc={u.get('pc')} hits st=E->M @{u['tick']}; squash seq {Q}; U cleanup_skip why=l1hit; "
                  f"S cleanup_skip Inv_CLEANUP st=M @{sk[0]['tick']} ({order})")



def run(camp: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    log = (out_dir / "cleanupspec_em_evidence.log").open("w")
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
                key = f"{mode}/{rec['name'].split('__')[0]}"
                try:
                    fh = B._open(rec, camp, mode)
                    if fh is None:
                        items = [dict(o, cause="unattributed", why="no trace") for o in rec.get("offending", [])]
                    else:
                        with fh:
                            evs, by_id, committed = B.parse(fh)
                        items = []
                        for o in rec.get("offending", []):
                            c, why = B.judge(o, evs, by_id, committed)
                            if c == "EM_upgrade_squashed":
                                ok, w2 = strict(o, rec, evs, committed)
                                c, why = ("EM_rmw_squashed", w2) if ok else ("EM_loose", w2 + " | " + why)
                            items.append(dict(o, cause=c, why=why))
                except Exception:
                    log.write(f"ERROR {key} {rec['name']}\n{traceback.format_exc()}\n")
                    items = [dict(cause="unattributed", why="exception (see log)")]
                ent = res.setdefault(key, {"variants": []})
                ent["variants"].append({"record": rec["name"], "cache_setup": rec.get("cache_setup"),
                                        "terms": rec.get("terms_fired"), "items": items})
    for key, ent in sorted(res.items()):
        ent["causes"] = sorted({i["cause"] for v in ent["variants"] for i in v["items"]})
        log.write(f"{key} causes={ent['causes']}\n")
        for v in ent["variants"]:
            for i in v["items"]:
                log.write(f"    {v['record']} {i.get('struct')} {i.get('line')} {i.get('term')} -> {i['cause']}: {i['why']}\n")
    (out_dir / "cleanupspec_em_evidence.json").write_text(json.dumps(res, indent=1) + "\n")
    cnt = Counter(",".join(e["causes"]) for e in res.values())
    log.write(f"end {time.strftime('%F %T')} stems={len(res)} elapsed={time.time() - t0:.1f}s {dict(cnt)}\n")
    log.close()
    print(f"{camp}: {len(res)} hit stems -> {out_dir}/cleanupspec_em_evidence.json")
    for k, n in sorted(cnt.items()):
        print(f"  {n}\t{k}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    od = None
    if "--out-dir" in a:
        i = a.index("--out-dir"); od = Path(a[i + 1]); del a[i:i + 2]
    camp = Path(a[0]).resolve()
    run(camp, od or camp / "diagnostics")
