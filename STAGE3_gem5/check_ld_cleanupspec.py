#!/usr/bin/env python3
"""Per-defense load watcher for **CleanupSpec** (CleanupCache, Ruby MESI_Two_Level).

CleanupSpec is an *undo* defense: speculative loads execute and **install into L1
normally** (unlike InvisiSpec's invisible spec), and on a squash the CleanupCache
machinery is supposed to **undo** every speculative cache footprint. The AMuLeT
bugs here are POST-SQUASH RESIDUE — a footprint that the undo misses (UV3 spec
store not cleaned / UV4 split request not cleaned) or an over-undo that evicts a
line the speculation never touched (UV5).

This watcher detects the residue at its SOURCE in the ProtocolTrace — the cleanup
event itself — NOT by a final-state diff:

  * For the xmit load's data line L: was there a speculative ACCESS/INSTALL of L in
    the STRICT lc/fnc window, was the load SQUASHED, and did a CleanupCache undo
    event fire on L afterwards?
      - access-in-window + squash + cleanup-on-L      -> "cleaned" (defense working)
      - access-in-window + squash + NO cleanup-on-L    -> "RESIDUE_UV34" (bug candidate)
  * Over-undo (UV5): a cleanup/eviction event on a line that had NO speculative
    access in this run -> reported as orphan_cleanup_lines.

Cleanup-event vocabulary in THIS build's ProtocolTrace (NOT InvisiSpec's SpecLoad/
Inv_CLEANUP path — different machine):
    L1Cache: Inflight_CLEANUP_reqs / Inflight_CLEANUP_resp / Inv_CLEANUP /
             InvL2_CLEANUP / Load_ROLLBACK / Skip_ROLLBACK / Done_CLEANUP /
             Waiting_CLEANUP / Waiting_Rollback_CLEANUP / Drop_Load_Cleanup_Inflight
    (the Seq "... CLEANUP_INFLIGHT" suffix marks the op but the trailing token is
     not part of the regex-captured transition line, so we key on the L1Cache events.)
Install / eviction: L1_Replacement_OnInstall / AllocateLine_OnInstall / L1_Replacement.

The lc/fnc window (lc_retire < t < fnc_retire AND guarding branches unresolved) is
the model's FUNDAMENTAL gate and is kept STRICT here — never widened. A parallel
lc/fnc-OFF view is reported ONLY to measure how much the gate constrains.

Env (mirror the campaign exactly; see CLAUDE.md config->env bridge):
  SIMSPECT_GEM5_BIN  = .../amulet-gem5-CleanupSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt
  SIMSPECT_SE_CONFIG = .../configs/example/se.py
  SIMSPECT_GEM5_CPU  = DerivO3CPU
  SIMSPECT_GEM5_DBG_FLAG = ProtocolTrace,Squashed,O3PipeView,LSQUnit
  SIMSPECT_GEM5_EXTRA = --ruby <US> --l2cache <US> --l1d_size=2kB <US> --l1d_assoc=4 <US>
                        --scheme_invisispec=UnsafeBaseline <US>
                        --scheme_cleanupcache=Cleanup_FOR_L1L2 <US> --needsTSO=0
                        (<US> = 0x1f join; UnsafeBaseline cleanupcache = OFF control)
  SIMSPECT_BRANCH_ANN_ENABLE = 1 ; SIMSPECT_FNC_COMMIT_STALL_CYCLES = <stall>
NOTE: assoc-2 + small L1D + misprediction DEADLOCKS this Ruby build (spec-install
storm starves the 2-way set) -> use assoc>=4.
"""
import argparse, json, re, shutil, subprocess, sys, tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import gem5_common as gc
from gem5_common import (best_record, check_branch_resolutions,
                         collect_unresolved_branches, load_annotation,
                         parse_pipeview, parse_lsq,
                         parse_ticks_per_cycle, resolve_pc, build_binary, run_gem5)

# ── Ruby ProtocolTrace parsing ───────────────────────────────────────────────
# "   3865500   0    L1Cache  Inflight_CLEANUP_reqs  NP>NP  [0x3580, line 0x3580]"
# (the machine+event can be glued with no space, e.g. "L1CacheInflight_CLEANUP_reqs";
#  the regex tolerates an optional separator so both forms parse.)
_PT_RE = re.compile(
    r"^\s*(\d+)\s+\d+\s+(L1Cache|L2Cache|Directory|Seq)\s*(\S+)\s+(\S*)>(\S*)\s+\[(0x[0-9a-f]+), line (0x[0-9a-f]+)\]")
_PADDR_RE = re.compile(
    r"(?:Spec Read Request for PC|Attempting load request - PC)\s*(0x[0-9a-f]+),.*?Paddr\s*(0x[0-9a-f]+)")

CLEANUP_EVENTS = {
    "Inflight_CLEANUP_reqs", "Inflight_CLEANUP_resp", "Inv_CLEANUP",
    "InvL2_CLEANUP", "Load_ROLLBACK", "Skip_ROLLBACK", "Done_CLEANUP",
    "Waiting_CLEANUP", "Waiting_Rollback_CLEANUP", "Drop_Load_Cleanup_Inflight",
    "Waiting_CLEANUP_inprogress",
}
INSTALL_EVENTS = {"L1_Replacement_OnInstall", "AllocateLine_OnInstall"}
ACCESS_EVENTS  = {"Load", "SpecLoad"}   # L1Cache load access on the xmit line


def parse_protocol_trace(trace_path):
    """{by_line: {line:int -> [ev]}, events: [ev ordered]}. ev has tick/machine/event/cur/next/addr/line."""
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
    out = {}
    with open(trace_path) as f:
        for ln in f:
            m = _PADDR_RE.search(ln)
            if m:
                out.setdefault(int(m.group(1), 16), int(m.group(2), 16) & ~0x3F)
    return out


# ── CleanupCache residue analysis ────────────────────────────────────────────

def analyze_cleanup(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle,
                    proto, xmit_line, load_squash_tick=0):
    lc_rec  = best_record(by_pc.get(lc_pc,  [])) if lc_pc  else None
    fnc_rec = best_record(by_pc.get(fnc_pc, [])) if fnc_pc else None
    lc_retire  = lc_rec["retire"]  if lc_rec  else 0
    fnc_retire = fnc_rec["retire"] if fnc_rec else 0

    by_line = proto["by_line"]
    events  = proto["events"]
    ruby_seen = bool(events)

    def spec_ok(t, lcfnc=True):
        # STRICT model window — NOT tunable. lcfnc=False = parallel measurement only.
        unresolved_ok, _ = check_branch_resolutions(by_pc, t, unresolved, ticks_per_cycle)
        before_squash = (load_squash_tick == 0) or (t < load_squash_tick)
        if not lcfnc:
            return unresolved_ok and before_squash
        after_lc   = (lc_retire == 0) or (t > lc_retire)
        before_fnc = (fnc_retire == 0) or (t < fnc_retire)
        return after_lc and before_fnc and unresolved_ok

    # The transmitter (e.g. an indexed load->load gadget) often HITS a line a prior
    # speculative load already brought in, so it issues no "Attempting load request"
    # line and parse_load_paddrs misses it. So we do NOT key on a single xmit PC.
    # Instead the speculative FOOTPRINT = the set of cache lines touched by an
    # L1Cache load / install event in the STRICT lc/fnc window while the xmit's
    # guarding branch is unresolved (i.e. wrong-path, to-be-squashed). CleanupCache
    # must undo EVERY such footprint; an uncleaned one is the UV3/4 residue.

    # A speculative load only creates a footprint the defense must undo if it
    # changes cache state: a MISS (cur in {NP,I} -> triggers a fetch/install) or an
    # install/replacement event. A clean HIT (cur==next in {M,E,S}) on a line that
    # is already architecturally resident (e.g. from a committed store) leaves NO
    # new footprint, so the absence of a cleanup on it is CORRECT, not residue.
    # (Verified: inst-000005 `Load M>M` hit on a committed line = no residue; vs
    #  inst-000004 `Load NP>NP` miss = inflight fetch that WAS cleaned.)
    MISS_CUR = {"NP", "I"}

    def compute(lcfnc):
        # line -> earliest in-window speculative *footprint* touch tick
        touch = {}
        for e in events:
            if not (e["machine"] == "L1Cache" and spec_ok(e["tick"], lcfnc)):
                continue
            footprint = (e["event"] in INSTALL_EVENTS
                         or (e["event"] in ACCESS_EVENTS and e["cur"] in MISS_CUR))
            if not footprint:
                continue
            L = e["line"]
            if L not in touch or e["tick"] < touch[L]:
                touch[L] = e["tick"]
        # per line: did a cleanup fire on it at/after its speculative touch?
        cleaned, residue = {}, {}
        for L, t0 in touch.items():
            cl = [e for e in by_line.get(L, [])
                  if e["event"] in CLEANUP_EVENTS and e["tick"] >= t0]
            (cleaned if cl else residue)[L] = (t0, cl)
        return dict(touch=touch, cleaned=cleaned, residue=residue)

    on, off = compute(True), compute(False)
    spec_lines    = on["touch"]
    residue_lines = on["residue"]
    cleaned_lines = on["cleaned"]

    # Over-undo (UV5): cleanup events on lines that were NEVER load-accessed in this
    # run (orphan cleanup = the defense evicted a line speculation never touched).
    accessed_lines = {e["line"] for e in events
                      if e["machine"] == "L1Cache" and e["event"] in ACCESS_EVENTS}
    orphan_cleanup = sorted({e["line"] for e in events
                             if e["event"] in CLEANUP_EVENTS
                             and e["line"] not in accessed_lines})

    if not ruby_seen:
        outcome = "no_ruby_trace"            # ran classic (no --ruby) — INVALID for CleanupSpec
        residue = None
    elif not spec_lines:
        outcome = "no_spec_touch_in_window"
        residue = False
    elif residue_lines:
        # In-window speculative footprint with NO CleanupCache undo on it -> the
        # footprint persists past squash. THE BUG SIGNAL (UV3/4).
        outcome = "RESIDUE_uv34"
        residue = True
    else:
        outcome = "cleaned"                  # the intended behaviour (every footprint undone)
        residue = False

    return dict(
        issued_in_window=residue,            # True == residue (UV3/4 candidate)
        outcome=outcome,
        residue=residue,
        n_spec_lines=len(spec_lines),
        n_cleaned_lines=len(cleaned_lines),
        n_residue_lines=len(residue_lines),
        residue_lines=[hex(L) for L in sorted(residue_lines)],   # uncleaned footprints
        # parallel lc/fnc-OFF view (measurement only; never the verdict)
        n_spec_lines_nolcfnc=len(off["touch"]),
        n_residue_lines_nolcfnc=len(off["residue"]),
        ruby_seen=ruby_seen,
        xmit_line=hex(xmit_line) if xmit_line is not None else None,
        orphan_cleanup_lines=[hex(x) for x in orphan_cleanup],   # UV5 surface
        spec_lines=[hex(L) for L in sorted(spec_lines)],
        cleanup_events=[{k: (hex(e[k]) if k in ("addr", "line") else e[k])
                         for k in ("tick", "machine", "event", "cur", "next")}
                        for L in sorted(cleaned_lines) for e in cleaned_lines[L][1]][:40],
        load_squash_tick=load_squash_tick,
        lc_retire=lc_retire, fnc_retire=fnc_retire,
    )


def process_one(s_path, ann_path, keep_tmp=False):
    name = s_path.stem
    workdir = Path(tempfile.mkdtemp(prefix=f"gem5cc_{name}_"))
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
        result.update(analyze_cleanup(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved,
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
        print("WARNING: ProtocolTrace not in SIMSPECT_GEM5_DBG_FLAG — needs it", file=sys.stderr)
    if "--ruby" not in gc.os.environ.get("SIMSPECT_GEM5_EXTRA", ""):
        print("WARNING: --ruby not in SIMSPECT_GEM5_EXTRA — CleanupCache is INACTIVE on classic caches",
              file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(process_one, s, a, args.keep_tmp): s for s, a in pairs}
        for fut in as_completed(futs):
            r = fut.result(); results.append(r)
            tag = {True: "RESIDUE", False: "ok", None: "?"}[r.get("issued_in_window")]
            orph = r.get("orphan_cleanup_lines") or []
            extra = f" orphan_cleanup={len(orph)}" if orph else ""
            print(f"  [{tag:7}] {r['name']:20} {r.get('outcome')}{extra}", flush=True)

    nr = sum(1 for r in results if r.get("residue"))
    ne = sum(1 for r in results if r.get("status") == "error")
    no = sum(1 for r in results if r.get("orphan_cleanup_lines"))
    print(f"\nRESIDUE(uv3/4): {nr}  |  orphan-cleanup(uv5 surface): {no}  |  "
          f"error: {ne}  (total {len(results)})")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2))
        print(f"written {args.out}")


if __name__ == "__main__":
    main()
