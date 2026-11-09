"""VENDORED COPY (timing-amulet 2026-11-09) of cafe2 /tests/simspect_fixed_20261030/results/STT_6_speclfb_v2hooks__20261107/helpers/analyze.py, unchanged except that the STAGE3_gem5 path comes from $SIMSPECT_STAGE3 (default: the original path). Used by classify_hits.py for the SpecLFB UV6 / walk-order / jmp-shadow tags.

Per-test analysis of a SpecLFB v2 trace (session 2026-11-07). Read-only on the trace.
Uses check_footprint.TraceModel for the actor test (same rule as the checker: squashed and younger
than lc_seq) and the checker record's offending / footprint_outside_window event ids for the window.

Per speculative (actor) load: first LSQ:unsafe flags, rank within its squash group (rank 0 = the
first speculative load of that window = UV6 as published), prevnounsafe / cusl set ticks, any L1D
miss (normal, or the hit-USL probe miss = hitusl=1), and L1D/L2 fill/evict ids split in/out of window.
Per hit: each in-window footprint event gets a cause tag:
  uv6_first      rank-0 actor load, unsafe=0 at translation
  walk_order     rank>=1 actor load, unsafe=0 with prevnounsafe=1 (sticky ROB-walk flag)
  jmp_shadow     rank>=1 actor load never CUSL/mUSL with a direct JMP_I/CALL_NEAR_I between the squashing
                 branch and it (rob.cc ROB::updateSafeState resets prevBrsResolved=true at a direct
                 unconditional control op); "+walk_order" if prevnounsafe=1 as well
  safe_other     rank>=1 actor load, unsafe=0, none of the above
  unsafe1_filled actor load unsafe=1 at its last translation, never re-sent after a bounce, yet filled
  replayed_after_safe  unsafe=1 load that was bounced, then re-sent (sent=1) after the walks cleared it
  no_unsafe_line event seq has no LSQ:unsafe line (not a load the LSQ tagged: ifetch/store/writeback)
"""
import sys
from collections import defaultdict
from pathlib import Path

import os
sys.path.insert(0, os.environ.get("SIMSPECT_STAGE3", "/tests/simspect_fixed_20261030/STAGE3_gem5"))
import gem5_common as gc  # noqa: E402
import check_footprint as cf  # noqa: E402

FLAGS = ("unsafe", "cusl", "musl", "prevnounsafe", "reallyunsafe", "prevbrsres", "lqhead", "split", "requsl")


def _i(v):
    try:
        return int(v, 0) if isinstance(v, str) else v
    except ValueError:
        return v


def analyze(rec: dict, pv, mode: str) -> dict:
    out = dict(name=rec.get("name"), mode=mode, status=rec.get("status"), error=(rec.get("error") or None),
               hit=rec.get("issued_in_window") is True, leak=rec.get("leak"),
               validity_notes=(rec.get("validity") or {}).get("notes"), xmit_pc=rec.get("xmit_pc"),
               lc_seq=rec.get("lc_seq"), lc_retire=rec.get("lc_retire"), fnc_retire=rec.get("fnc_retire"),
               disqualified=rec.get("disqualified"), n_squashes=rec.get("n_squashes"),
               offending=rec.get("offending"), n_footprint_events=rec.get("n_footprint_events"),
               br_resolve_source=rec.get("br_resolve_source"))
    if pv is None:
        out["trace"] = None
        return out
    events = gc.parse_simspect_events(pv)
    pv_seq = gc.parse_pipeview_by_seq(pv)
    tm = cf.TraceModel(events, pv_seq)
    lc_seq = rec.get("lc_seq")
    in_ids = {i for d in (rec.get("offending") or []) for i in d.get("event_ids", [])}
    out_ids = {i for d in (rec.get("footprint_outside_window") or []) for i in d.get("event_ids", [])}
    unsafe = defaultdict(list)
    flagset = defaultdict(dict)
    misses = defaultdict(list)
    foot = defaultdict(list)
    issues = defaultdict(list)
    lfb = []
    for e in events:
        s = e["seq"]
        if e["struct"] == "LSQ" and e["kind"] == "unsafe":
            unsafe[s].append(dict(tick=e["tick"], pc=hex(e["pc"]) if e["pc"] is not None else None,
                                  **{f: _i(e.get(f)) for f in FLAGS}, vaddr=e.get("vaddr")))
        elif e["struct"] == "LSQ" and e["kind"] == "usl_flag":
            flagset[s].setdefault(f"{e.get('f')}={e.get('v')}:{e.get('by')}", e["tick"])
        elif e["struct"] == "LSQ" and e["kind"] == "issue":
            issues[s].append(dict(tick=e["tick"], sent=_i(e.get("sent")), bounced=_i(e.get("bounced")),
                                  usl=_i(e.get("usl")), hitusl=_i(e.get("hitusl")), blocked=_i(e.get("blocked"))))
        elif e["struct"] == "L1D" and e["kind"] == "miss":
            misses[s].append(dict(tick=e["tick"], line=hex(e["line"]) if e["line"] is not None else None, hitusl=_i(e.get("hitusl")), usl=_i(e.get("usl")), req=e.get("req")))
        elif e["struct"] in ("L1D", "L2") and e["kind"] in ("fill", "evict"):
            foot[s].append(dict(id=e["id"], tick=e["tick"], struct=e["struct"], kind=e["kind"],
                                line=hex(e["line"]) if e["line"] is not None else None, req=e.get("req"),
                                inw=e["id"] in in_ids, outw=e["id"] in out_ids))
        elif e["struct"] == "LFB":
            lfb.append({k: (hex(v) if k in ("line", "pc") and isinstance(v, int) else v) for k, v in e.items()})

    def actor(s):
        return s is not None and tm.squash_of(s) is not None and (lc_seq is None or s > lc_seq)

    # macro-op mnemonic per seq (fetch lines), for the direct-jump check below
    mnem = {}
    with open(pv) as fh:
        for line in fh:
            if line.startswith("O3PipeView:fetch:"):
                p = line.rstrip("\n").split(":", 6)
                try:
                    mnem[int(p[5])] = p[6].strip().split(" ")[0]
                except (IndexError, ValueError):
                    pass

    groups = defaultdict(list)
    for s in unsafe:
        if actor(s):
            groups[tm.squash_of(s)["id"]].append(s)
    loads = {}
    for sqid, ss in groups.items():
        for rank, s in enumerate(sorted(ss)):
            u0, ul = unsafe[s][0], unsafe[s][-1]
            loads[s] = dict(seq=s, sq_id=sqid, rank=rank, pc=u0["pc"], is_xmit=(u0["pc"] == rec.get("xmit_pc")),
                            first=u0, last=ul, n_translations=len(unsafe[s]),
                            combo=" ".join(f"{f}={u0[f]}" for f in ("unsafe", "cusl", "musl", "prevnounsafe", "reallyunsafe", "lqhead", "split")),
                            flag_ticks=flagset.get(s, {}), misses=misses.get(s, []), issues=issues.get(s, []),
                            footprint=foot.get(s, []))
    # why each actor load was unsafe=0 at translation (reasons, not a verdict)
    for sqid, ss in groups.items():
        ss = sorted(ss)
        sq = next(x for x in tm.squashes if x["id"] == sqid)
        for s in ss:
            L = loads[s]; f = L["first"]; why = []
            jm_all = [q for q in range(sq["seq"] + 1, s) if mnem.get(q, "").startswith(("JMP_I", "CALL_NEAR_I"))]
            L["jmp_in_shadow"] = bool(jm_all)
            # cusl clear by the ROB walk before translation (rob.cc:463-471), if any
            L["rob_cusl_clear_before_xlate"] = any(k == "cusl=0:rob" and t <= f["tick"] for k, t in L["flag_ticks"].items())
            if f["unsafe"] == 0:
                if f["prevnounsafe"] == 1:
                    why.append("prevnounsafe")
                    older = [o for o in ss if o < s]
                    oflag = [t for o in older for k, t in loads[o]["flag_ticks"].items() if k in ("cusl=1:lsq", "musl=1:lsq")]
                    pt = L["flag_ticks"].get("prevnounsafe=1:rob")
                    if not older:
                        L["pns_vs_older"] = "no_older_actor_load"
                    elif not oflag:
                        L["pns_vs_older"] = "older_never_flagged"
                    elif pt is not None and pt < min(oflag):
                        L["pns_vs_older"] = "set_before_older_flagged"
                    else:
                        L["pns_vs_older"] = "set_at_or_after_older_flagged"
                if f["cusl"] == 0 and f["musl"] == 0:
                    why.append("not_cusl_musl")
                    if f["lqhead"] == 1:
                        why.append("lqhead")
                    jm = [q for q in range(sq["seq"] + 1, s) if mnem.get(q, "").startswith(("JMP_I", "CALL_NEAR_I"))]
                    if jm:
                        why.append("direct_jmp_call_in_shadow")
                        L["shadow_jmps"] = sorted({mnem[q] for q in jm})
                if f["reallyunsafe"] == 0 and f["prevnounsafe"] == 0:
                    why.append("reallyunsafe0_without_pns")
            L["why_safe"] = why
            L["squash_seq"] = sq["seq"]

    # in-window footprint cause tags
    causes = []
    for s, evs in foot.items():
        for ev in evs:
            if not ev["inw"]:
                continue
            L = loads.get(s)
            if L is None:
                tag = "no_unsafe_line"
            elif L["last"]["unsafe"] == 1:
                # a stalled unsafe load is re-sent without a new LSQ:unsafe line once the walks
                # clear its flags (sent=1 after bounced=1); that is a replay, not a failed block
                bounced = [i["tick"] for i in L["issues"] if i["bounced"] == 1]
                resent = [i["tick"] for i in L["issues"] if i["sent"] == 1 and bounced and i["tick"] > min(bounced)]
                tag = ("replayed_after_safe" + ("(jmp_in_shadow)" if L.get("jmp_in_shadow") else "")) if resent else "unsafe1_filled"
            elif L["rank"] == 0:
                tag = "uv6_first"
            elif "direct_jmp_call_in_shadow" in L["why_safe"]:
                tag = "jmp_shadow" + ("+walk_order" if "prevnounsafe" in L["why_safe"] else "")
            elif L["first"]["prevnounsafe"] == 1:
                tag = "walk_order"
            else:
                tag = "safe_other"
            causes.append(dict(seq=s, tag=tag, ev=ev, load=(None if L is None else
                               dict(rank=L["rank"], pc=L["pc"], is_xmit=L["is_xmit"], combo=L["combo"],
                                    last_unsafe=L["last"]["unsafe"], n_translations=L["n_translations"],
                                    why_safe=L.get("why_safe"), pns_vs_older=L.get("pns_vs_older")))))
    out.update(trace=str(pv), n_events=len(events), n_actor_loads=len(loads),
               n_actor_loads_l1d_miss=sum(1 for L in loads.values() if L["misses"]),
               n_actor_loads_probe_miss=sum(1 for L in loads.values() if any(m["hitusl"] == 1 for m in L["misses"])),
               n_actor_loads_normal_miss=sum(1 for L in loads.values() if any(m["hitusl"] == 0 for m in L["misses"])),
               n_actor_loads_bounced=sum(1 for L in loads.values() if any(i["bounced"] == 1 for i in L["issues"])),
               n_actor_loads_fill_inw=sum(1 for L in loads.values() if any(f["inw"] and f["kind"] == "fill" for f in L["footprint"])),
               n_lfb_events=len(lfb), lfb=lfb[:20], loads=list(loads.values()), causes=causes,
               cause_tags=sorted({c["tag"] for c in causes}))
    return out
