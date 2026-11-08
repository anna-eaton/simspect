#!/usr/bin/env python3
"""Per-hit facts for a fixed-harness campaign (2026-11-07).

Reads every raw per-record file of a testrun.py campaign
(results/<name>__<ts>/<mode>/_sweep_raw/*.json), keeps the hit records
(issued_in_window), and writes one compact fact row per hit record: the window
edges the checker used, the branch instances the BR resolve lines saw, and the
timing facts the triage buckets key on. No gem5 is run.

    python3 hit_facts.py <campaign_dir> --out facts.json

Fact fields (ticks):
  common  stem, mode, kind, grid (sweep point tag from the raw file name),
          lc_retire, fnc_retire, signal (the checker's xmit_signal),
          ctrl: the oldest unresolved non-xmit branch (by Alloy pc) with its
          instances [{seq, fetch, hold, release, bcast, visible, mispred}],
          window_close = min(resolve_tick of the unresolved branches the
          checker tested, fnc_retire if > 0)
  ld      cache_fate, execute, packet_tick, complete, data_tick (packet tick
          for reached_cache, complete tick for store_forward), retired
  br_x    xmit instances [{seq, fetch, visible, mispred, bcast}],
          first_mispred_xmit (lowest seq that resolved mispredicted),
          its fetch vs the controlling branch's bcast/visible
"""
import argparse, glob, json, re
from pathlib import Path


def _inst(seqs):
    out = []
    for q, d in sorted(seqs.items(), key=lambda kv: int(kv[0])):
        out.append(dict(seq=int(q), fetch=d.get("predict_force", 0), hold=d.get("resolve_hold", 0),
                        release=d.get("resolve_release", 0), bcast=d.get("resolve_bcast", 0),
                        visible=d.get("resolve_visible", 0), drop=d.get("resolve_drop", 0),
                        mispred=d.get("resolve_visible_mispred", d.get("resolve_hold_mispred"))))
    return out


def facts(r, mode, grid):
    ev = r.get("br_events") or {}
    plan = r.get("force_plan") or []
    xpc = r.get("xmit_pc")
    unres = sorted((p for p in plan if p.get("mode") != "correctly_not_taken"
                    and hex(p["addr"]) != xpc), key=lambda p: p.get("branch_pc") or 0)
    ctrl = None
    if unres:
        c = unres[0]
        ctrl = dict(addr=hex(c["addr"]), branch_pc=c.get("branch_pc"),
                    inst=_inst(ev.get(hex(c["addr"]), {})))
    br = r.get("branch_resolutions") or []
    closes = [b.get("resolve_tick") or b.get("prop_tick") or 0 for b in br]
    closes = [t for t in closes if t]
    if (r.get("fnc_retire") or 0) > 0:
        closes.append(r["fnc_retire"])
    f = dict(stem=r["name"], mode=mode, kind=r.get("xmit_kind"), grid=grid,
             lc_retire=r.get("lc_retire"), fnc_retire=r.get("fnc_retire"),
             signal=r.get("xmit_signal"), window_close=min(closes) if closes else None,
             branch_resolutions=br, ctrl=ctrl, xmit_pc=xpc,
             resolved_before_signal=r.get("resolved_before_signal"))
    if r.get("xmit_kind") == "ld":
        fate = r.get("cache_fate")
        f.update(cache_fate=fate, execute=r.get("xmit_execute"), packet_tick=r.get("packet_tick"),
                 complete=r.get("xmit_complete"), retired=r.get("xmit_retire"),
                 data_tick=(r.get("packet_tick") if fate == "reached_cache"
                            else r.get("xmit_complete") if fate == "store_forward" else None))
    elif r.get("xmit_kind") == "br_x":
        xi = _inst(ev.get(xpc, {})) if xpc else []
        f["xmit_inst"] = xi
        mis = [i for i in xi if i["mispred"] == 1 and i["visible"]]
        f["first_mispred_xmit"] = mis[0] if mis else None
        if mis and ctrl and ctrl["inst"]:
            c0 = [i for i in ctrl["inst"] if i["mispred"] == 1 and (i["bcast"] or i["visible"])]
            if c0:
                f["ctrl_primary"] = c0[0]
                f["xmit_fetched_before_ctrl_squash"] = mis[0]["fetch"] < (c0[0]["bcast"] or c0[0]["visible"])
        f["xmit_redirect"] = r.get("xmit_redirect")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = []
    for md in sorted(a.campaign.glob("mispredict_*")):
        for fp in sorted(md.glob("_sweep_raw/*.json")):
            m = re.search(r"_(grid\d+)_", fp.name)
            for r in json.load(open(fp)):
                if r.get("issued_in_window"):
                    rows.append(facts(r, md.name, m.group(1) if m else None))
    a.out.write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} hit records -> {a.out}")


if __name__ == "__main__":
    main()
