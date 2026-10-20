#!/usr/bin/env python3
"""
check_ld_invisispec_compound.py — COMPOUND load-transmitter checker for InvisiSpec.

A speculative load transmits through EVERY microarchitectural structure its access
perturbs, not just the cache line it installs. This checker flags an Unsafe
Speculative Load (USL) touching ANY structure on the transmission surface while it
is still speculative (in the window lc_retire < t < fnc_retire, guarding branches
unresolved). Design: docs/COMPOUND_TRANSMISSION_CRITERION.md §3.

★ REQUIRES --ruby ★  InvisiSpec's defense (Spec-GetS invisibility, the Speculative
Buffer, the eviction toggle) lives in the Ruby MESI protocol (.sm). The SimSpect
pipeline's default `--caches` runs the CLASSIC cache model, where NONE of that is
active (the earlier cache.cc:192 aborts were the classic cache). The launcher must
put `--ruby` in SIMSPECT_GEM5_EXTRA and `ProtocolTrace,Squashed` in the debug flags.

Observed structures (each maps to an AMuLeT bug class):
  - L1D eviction of a victim line      ......... InvisiSpec UV1   [forbidden]
  - L1 TBE/MSHR allocation (miss)      ......... InvisiSpec UV2   [needs_pressure]
  - L1 cache-line install              ......... (should never happen for a USL)
  - L1 LRU/MRU on a hit                ......... structurally absent (h_spec_load_hit
                                                 omits setMRU) — reported for completeness
  - L2 eviction                        ......... [forbidden]
  - Directory state change (SpecFetch) ......... [forbidden]
A spec load that HITS in L1 (SpecLoad M>M / S>S / E>E) touches none of these = the
intended invisible behaviour.

Observation: the Ruby `ProtocolTrace` (one line per controller transition:
"<tick> <node> <Machine> <Event> <cur>><next> [<addr>, line <line>]") gives the full
per-line footprint of the spec access on L1/L2/dir. The xmit load's line address is
recovered from the LSQUnit/Squashed "Spec Read Request for PC <xmit>, Paddr 0x.." line.

Usage (env mirrors results/STT_6_invisispec_compound/run_*.py):
  SIMSPECT_GEM5_BIN=.../build/X86_MESI_Two_Level/gem5.opt
  SIMSPECT_GEM5_DBG_FLAG=O3PipeView,LSQUnit,Squashed,ProtocolTrace
  SIMSPECT_GEM5_EXTRA="--ruby"$'\x1f'"--scheme=SpectreSafeInvisibleSpec"$'\x1f'"--needsTSO=1"
  python3 check_ld_invisispec_compound.py <dir-with-.s+.ann.json> --jobs 8 --out out.json
"""
import argparse, json, re, shutil, subprocess, sys, tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import gem5_common as gc
from gem5_common import (best_record, check_branch_resolutions,
                         collect_unresolved_branches, load_annotation,
                         parse_pipeview, parse_lsq, parse_commit_squashes,
                         parse_ticks_per_cycle, resolve_pc, build_binary, run_gem5)

# ── Ruby ProtocolTrace parsing ───────────────────────────────────────────────
# Line: "   3168000   0    L1Cache   SpecLoad   M>M   [0x3580, line 0x3580] ..."
_PT_RE = re.compile(
    r"^\s*(\d+)\s+\d+\s+(\S+)\s+(\S+)\s+(\S*)>(\S*)\s+\[(0x[0-9a-f]+), line (0x[0-9a-f]+)\]")
# xmit line addr: "... Spec Read Request for PC 0x.., Paddr 0x.." / "Attempting load request - PC 0x.., ... Paddr 0x.."
_PADDR_RE = re.compile(r"(?:Spec Read Request for PC|Attempting load request - PC)\s*(0x[0-9a-f]+),.*?Paddr\s*(0x[0-9a-f]+)")


def parse_protocol_trace(trace_path):
    """Return {by_line: {line_addr:int -> [event dicts]}, events: [all, ordered]}.
    event = {tick, machine, event, cur, next, addr, line}. Empty on non-Ruby runs."""
    by_line = defaultdict(list)
    events = []
    with open(trace_path) as f:
        for ln in f:
            m = _PT_RE.match(ln)
            if not m:
                continue
            rec = dict(tick=int(m.group(1)), machine=m.group(2), event=m.group(3),
                       cur=m.group(4), next=m.group(5),
                       addr=int(m.group(6), 16), line=int(m.group(7), 16))
            by_line[rec["line"]].append(rec)
            events.append(rec)
    return dict(by_line=dict(by_line), events=events)


def parse_load_paddrs(trace_path):
    """pc(int) -> cache-line addr(int) for loads (from the Squashed spec-read line)."""
    out = {}
    with open(trace_path) as f:
        for ln in f:
            m = _PADDR_RE.search(ln)
            if m:
                out.setdefault(int(m.group(1), 16), int(m.group(2), 16) & ~0x3F)
    return out


# ── Compound transmission analysis ───────────────────────────────────────────

def _in_window(t, lc_retire, fnc_retire):
    return t > 0 and (lc_retire == 0 or t > lc_retire) and (fnc_retire == 0 or t < fnc_retire)


def analyze_compound(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle,
                     proto, xmit_line, load_squash_tick=0):
    lc_rec  = best_record(by_pc.get(lc_pc,  [])) if lc_pc  else None
    fnc_rec = best_record(by_pc.get(fnc_pc, [])) if fnc_pc else None
    lc_retire  = lc_rec["retire"]  if lc_rec  else 0
    fnc_retire = fnc_rec["retire"] if fnc_rec else 0

    by_line = proto["by_line"]
    events  = proto["events"]
    ruby_seen = bool(events)

    # The xmit load's own SpecLoad events on its line.
    spec_evs = [e for e in by_line.get(xmit_line, [])
                if e["event"] in ("SpecLoad", "Load")] if xmit_line is not None else []

    # Speculative gate — the model's lc/fnc commit-boundary window, KEPT:
    #   after_lc   : t > lc_retire   (after the last-committed retires — fundamental
    #                lower bound; a touch before this is committed/architectural)
    #   before_fnc : t < fnc_retire  (before the first-non-committed retires — the
    #                classic upper bound)
    # PLUS an upper-bound extension: when the xmit's guarding MISPREDICT branch is
    # program-order LATER than fnc (so the resolve-stall holds *that* branch, not fnc),
    # the speculative region extends past fnc_retire. There the binding "still
    # speculative" condition is branches_unresolved(t) (the guarding branch hasn't
    # resolved). Under --ruby the invisible Spec-GetS is a slow memory access whose
    # event lands after fnc_retire yet is genuinely speculative — this captures it.
    # before_squash confirms the load was still a live wrong-path instruction.
    # lcfnc=True = the STRICT model window  lc_retire < t < fnc_retire  AND branches
    # unresolved. This is the fundamental model formulation and is NOT tuned: we do
    # NOT widen the upper bound. (before_fnc is vacuously true only when fnc_retire==0,
    # i.e. fnc itself was squashed — an open window, which is the model's own rule.)
    # lcfnc=False = PARALLEL diagnostic view with the lc/fnc check OFF (speculation by
    # branch-resolution + before-squash only) — used ONLY to MEASURE how much lc/fnc
    # constrains, never as the detection verdict.
    def spec_ok(t, lcfnc=True):
        unresolved_ok, _ = check_branch_resolutions(by_pc, t, unresolved, ticks_per_cycle)
        before_squash = (load_squash_tick == 0) or (t < load_squash_tick)
        if not lcfnc:
            return unresolved_ok and before_squash
        after_lc   = (lc_retire == 0) or (t > lc_retire)
        before_fnc = (fnc_retire == 0) or (t < fnc_retire)
        return after_lc and before_fnc and unresolved_ok

    def compute(lcfnc):
        sw = [e for e in spec_evs if spec_ok(e["tick"], lcfnc)]
        st = {e["tick"] for e in sw}
        tbe  = any(e["next"] == "IX" for e in sw)
        inst = any(e["machine"] == "L1Cache" and e["next"] in ("S", "E", "M")
                   and e["cur"] in ("NP", "I", "IX", "IS") for e in sw)
        hit  = any(e["event"] == "SpecLoad" and e["cur"] == e["next"]
                   and e["cur"] in ("S", "E", "M") for e in sw)
        # Eviction attributed to the spec load by tick-coincidence with a windowed
        # SpecLoad (Ruby processes one mandatory entry/controller-cycle, so an
        # L1_Replacement at the same tick is caused by that access).
        def ev(m, n):
            return [e for e in events if e["machine"] == m and e["event"] == n
                    and e["tick"] in st and e["line"] != xmit_line]
        l1e, l2e = ev("L1Cache", "L1_Replacement"), ev("L2Cache", "L2_Replacement")
        df = [e for e in by_line.get(xmit_line, [])
              if e["machine"] == "Directory" and e["event"] == "SpecFetch"
              and spec_ok(e["tick"], lcfnc)]
        forb = {"l1_eviction": bool(l1e), "l2_eviction": bool(l2e),
                "l1_install": bool(inst), "dir_specfetch": bool(df)}
        return dict(spec_win=sw, forbidden=forb, touched=any(forb.values()),
                    tbe=tbe, hit=hit, l1_evict=l1e, l2_evict=l2e)

    on, off = compute(True), compute(False)
    spec_win, forbidden, touched_forbidden = on["spec_win"], on["forbidden"], on["touched"]
    tbe_alloc, spec_hit_clean = on["tbe"], on["hit"]
    l1_evict, l2_evict = on["l1_evict"], on["l2_evict"]
    needs_pressure = {"tbe_mshr_alloc": bool(tbe_alloc)}  # inherent; leaks only under contention

    if not ruby_seen:
        outcome = "no_ruby_trace"          # ran classic (no --ruby) — INVALID for InvisiSpec
    elif xmit_line is None:
        outcome = "no_spec_read"           # load never issued a spec read (Paddr unknown)
    elif not spec_win:
        outcome = "no_spec_access_in_window"
    elif touched_forbidden:
        outcome = "touched_forbidden:" + ",".join(k for k, v in forbidden.items() if v)
    elif spec_hit_clean:
        outcome = "invisible_spec_hit"     # the intended behaviour
    elif tbe_alloc:
        outcome = "spec_miss_tbe_only"     # missed → TBE/MSHR (UV2 surface, needs pressure)
    else:
        outcome = "spec_access_no_forbidden_touch"

    return dict(
        issued_in_window=touched_forbidden,
        outcome=outcome,
        # PARALLEL view with the lc/fnc check OFF (speculation by branch-resolution
        # + before-squash only) — to gauge how much lc/fnc constrains. If equal to
        # the lc/fnc-on verdict, lc/fnc is not the limiting factor.
        issued_in_window_nolcfnc=off["touched"],
        forbidden_nolcfnc=off["forbidden"],
        ruby_seen=ruby_seen,
        xmit_line=hex(xmit_line) if xmit_line is not None else None,
        forbidden=forbidden,
        needs_pressure=needs_pressure,
        spec_events_in_window=[{k: (hex(e[k]) if k in ("addr", "line") else e[k])
                                for k in ("tick", "machine", "event", "cur", "next")}
                               for e in spec_win],
        l1_eviction_victims=[hex(e["line"]) for e in l1_evict],
        l1_eviction_ticks=[e["tick"] for e in l1_evict],
        l2_eviction_victims=[hex(e["line"]) for e in l2_evict],
        load_squash_tick=load_squash_tick,
        lc_retire=lc_retire, fnc_retire=fnc_retire,
    )


def process_one(s_path, ann_path, keep_tmp=False):
    name = s_path.stem
    workdir = Path(tempfile.mkdtemp(prefix=f"gem5c_{name}_"))
    result = dict(name=name, status="ok", xmit_kind=None, xmit_pc=None,
                  issued_in_window=None, outcome=None, error=None)
    try:
        parts = load_annotation(ann_path)
        xmit, lc, fnc = parts["xmit"], parts["lc"], parts["fnc"]
        result["xmit_kind"] = xmit.get("kind", "")
        binary  = build_binary(s_path, workdir)
        xmit_pc = resolve_pc(binary, name, xmit)
        lc_pc   = resolve_pc(binary, name, lc)
        fnc_pc  = resolve_pc(binary, name, fnc)
        result["xmit_pc"] = hex(xmit_pc) if xmit_pc else None
        if xmit_pc is None:
            result["status"] = "warn"; result["error"] = "no xmit x86 PC"; return result
        trace = run_gem5(binary, workdir, ann_path=ann_path, fnc_pc=fnc_pc)
        by_pc       = parse_pipeview(trace)
        proto       = parse_protocol_trace(trace)
        paddrs      = parse_load_paddrs(trace)
        lsq_by_pc   = parse_lsq(trace)
        ticks_per_cycle = parse_ticks_per_cycle(workdir / "m5out")
        unresolved  = [u for u in collect_unresolved_branches(
                          dict(annotations=parts["annotations"]), binary, name)
                       if u["pc"] != xmit_pc]
        xmit_line = paddrs.get(xmit_pc)
        load_squash = max((r.get("squash_tick", 0) for r in lsq_by_pc.get(xmit_pc, [])),
                          default=0)
        result.update(analyze_compound(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved,
                                       ticks_per_cycle, proto, xmit_line, load_squash))
    except subprocess.CalledProcessError as e:
        result["status"] = "error"
        stderr = (e.stderr or b"").decode(errors="replace")
        cause = next((l.strip() for l in stderr.splitlines()
                      if l.startswith(("panic:", "fatal:"))), None)
        result["error"] = (cause + " | " if cause else "") + stderr[-300:]
    except Exception as e:
        result["status"] = "error"; result["error"] = str(e)
    finally:
        if keep_tmp:
            result["workdir"] = str(workdir)
        else:
            shutil.rmtree(workdir, ignore_errors=True)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--keep-tmp", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    pairs = []
    for s in sorted(args.input_dir.resolve().glob("*.s")):
        a = s.with_suffix(".ann.json")
        if a.exists():
            pairs.append((s, a))
    if args.limit:
        pairs = pairs[:args.limit]
    if not pairs:
        sys.exit("no .s/.ann.json pairs")

    if "ProtocolTrace" not in gc.GEM5_DBG_FLAG:
        print("WARNING: ProtocolTrace not in SIMSPECT_GEM5_DBG_FLAG — compound checker needs it",
              file=sys.stderr)
    if "--ruby" not in gc.os.environ.get("SIMSPECT_GEM5_EXTRA", ""):
        print("WARNING: --ruby not in SIMSPECT_GEM5_EXTRA — InvisiSpec defense is INACTIVE on classic caches",
              file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(process_one, s, a, args.keep_tmp): s for s, a in pairs}
        for fut in as_completed(futs):
            r = fut.result(); results.append(r)
            tag = {True: "FORBIDDEN", False: "ok", None: "?"}[r.get("issued_in_window")]
            print(f"  [{tag:9}] {r['name']:20} {r.get('outcome')}", flush=True)

    nf = sum(1 for r in results if r.get("issued_in_window"))
    ne = sum(1 for r in results if r.get("status") == "error")
    print(f"\nForbidden-touch: {nf}  |  clean: {len(results)-nf-ne}  |  error: {ne}  (total {len(results)})")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2))
        print(f"written {args.out}")


if __name__ == "__main__":
    main()
