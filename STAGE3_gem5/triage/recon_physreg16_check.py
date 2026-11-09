#!/usr/bin/env python3
"""Evidence for R-SA-12 (physical int reg 16 is never tainted) on ld hits of a gem5-recon* campaign (2026-11-08).

Bug: gem5-recon*/src/cpu/o3/secure_scheme/taint_tracker.cc:59 `if (regId->flatIndex() == 16) return;`
in TaintTracker::insertTaint. Every taint insertion (rename.cc:714-720: insertTaintInst for a speculative
load, propagateTaints for everything else) goes through it, so a value renamed to physical int reg 16
(flat index 16 = IntRegClass 16; x86 has no zero register) is never tainted.

For each (mode, stem) ld hit in --campaign, this re-runs the test faithfully at its lowest hit grid index
(spt_taint_probe.probe_one, the campaign's own run config + the `Rename` debug flag, which only adds
prints) and decides from the trace:
  S1 reproduced       the re-run is still a hit (issued_in_window).
  S2 gem5_untainted   the xmit's decisive execution (the LSQ "Executing load" at tick == xmit_signal)
                      prints "STL_CHECK: load PC <xmit> isTainted=0 isSpeculative=1" (lsq_unit.cc:1886):
                      the tracker itself saw no tainted source.
  slice               backward register slice of that xmit instance from the Rename trace
                      ("Processing instruction [sn:N]", "Looking up <cls> arch reg a, got phys reg p (<cls>)",
                      "Renaming arch reg a (<cls>) to physical reg p (flat)"), producer = latest
                      non-squashed rename of that phys reg before the consumer.
  origins             loads in the slice that were speculative at rename AND still under an unresolved
                      forced branch at the xmit signal: sn > the sn of a held branch (BR:resolve_hold)
                      whose resolve_visible is after xmit_signal, and their own STL_CHECK says
                      isSpeculative=1. Other loads only propagate (conservative: fewer origins).
  S3 sim_with_rule    STT's rename rule replayed over the slice WITH the reg-16 skip: xmit untainted
                      (must agree with S2).
  S4 sim_without_rule the same replay WITHOUT the skip: some xmit source tainted.
  S5 via16            an instruction in the slice writes IntRegClass phys 16 and would be tainted
                      without the skip.
  S6 no_reveal        stats allowlistedTaintsFromTT == 0 (no ReCon untaint could explain it).
  S7 parse_ok         every slice instruction's rename block parsed (no garbled lookup line inside it).
The diagnostic diag_recon_physreg16.py buckets a hit only if S1..S7 all hold. Workdirs are deleted.

    python3 recon_physreg16_check.py --campaign results/<camp> --config <run_config> --testset testsets_latest/<model> \
        --out recon_physreg16_evidence.json [--only mode/stem ...] [--jobs 8] [--keep]
"""
import argparse, glob, json, re, shutil, sys, tempfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "STAGE3_gem5"))

RN = re.compile(r"^\s*(\d+): system\.cpu\.rename: (.*)$")
PROC = re.compile(r"\[tid:\d+\] Processing instruction \[sn:(\d+)\] with PC \((0x[0-9a-f]+)=>")
LOOK = re.compile(r"Looking up (\w+RegClass) arch reg (\d+), got phys reg (\d+) \((\w+RegClass)\)")
DEST = re.compile(r"Renaming arch reg (\d+) \((\w+RegClass)\) to physical reg (\d+) \((\d+)\)")
SQ = re.compile(r"\[squash sn:(\d+)\] Squashing instructions")
OK_IN_BLOCK = ("Looking up", "Register ", "Renaming arch reg", "Adding instruction to history buffer",
               "Serialize", "Renaming pinned")
EXEC = re.compile(r"^\s*(\d+): system\.cpu\.iew\.lsq\.thread\d+: Executing load PC \((0x[0-9a-f]+)=>.*\[sn:(\d+)\]")
INSL = re.compile(r"^\s*(\d+): system\.cpu\.iew\.lsq\.thread\d+: Inserting load PC \((0x[0-9a-f]+)=>.*\[sn:(\d+)\]")
STL = re.compile(r"STL_CHECK: load PC (0x[0-9a-f]+) isTainted=(\d) isSpeculative=(\d)")


def parse_trace(path):
    """Rename blocks (in order), squash events, load sns, per-load STL_CHECKs (paired with the preceding
    'Executing load' of the same PC within 4 lines)."""
    blocks, loads, stl_by_sn, execs = [], set(), defaultdict(list), []
    cur = None; last_exec = None
    with open(path, errors="replace") as f:
        for i, ln in enumerate(f):
            m = RN.match(ln)
            if m:
                body = m.group(2)
                p = PROC.search(body)
                if p:
                    cur = dict(sn=int(p.group(1)), pc=p.group(2), srcs=[], dests=[], garbled=False, line=i)
                    blocks.append(("rename", cur)); continue
                s = SQ.search(body)
                if s:
                    blocks.append(("squash", int(s.group(1)))); cur = None; continue
                if cur is not None and any(k in body for k in OK_IN_BLOCK):
                    looks = list(LOOK.finditer(body))
                    for lk in looks:
                        cur["srcs"].append((lk.group(1), int(lk.group(3))))
                    # An InvalidRegClass source prints a truncated "Looking up " glued to the next line, with
                    # "Register 65535 (flat: 65535)"; such a source is never tainted (taint_tracker.cc:60/83).
                    # Any OTHER unparsed lookup makes the block unreliable.
                    if body.count("Looking up") - len(looks) > body.count("Register 65535 (flat: 65535)"):
                        cur["garbled"] = True
                    for d in DEST.finditer(body):
                        cur["dests"].append((d.group(2), int(d.group(3)), int(d.group(4))))
                    continue
                cur = None
                continue
            m = INSL.match(ln)
            if m:
                loads.add(int(m.group(3))); continue
            m = EXEC.match(ln)
            if m:
                last_exec = (i, int(m.group(1)), m.group(2), int(m.group(3))); execs.append(last_exec); continue
            m = STL.search(ln)
            if m and last_exec and i - last_exec[0] <= 4 and int(m.group(1), 16) == int(last_exec[2], 16):
                stl_by_sn[last_exec[3]].append(dict(tick=last_exec[1], tainted=int(m.group(2)), spec=int(m.group(3))))
    return blocks, loads, stl_by_sn, execs


def analyse(trace, xmit_pc, xmit_signal, br_events):
    blocks, loads, stl_by_sn, execs = parse_trace(trace)
    out = dict(gem5_untainted=False, sim_with_rule=None, sim_without_rule=None, via16=[], parse_ok=False,
               origins=[], slice=[], xmit_seq=None, stl=None)
    xs = [e for e in execs if int(e[2], 16) == int(xmit_pc, 16) and e[1] == xmit_signal]
    if not xs:
        out["why"] = "no Executing load of the xmit at xmit_signal"; return out
    xsn = xs[-1][3]; out["xmit_seq"] = xsn
    st = [s for s in stl_by_sn.get(xsn, []) if s["tick"] == xmit_signal]
    out["stl"] = st[-1] if st else None
    out["gem5_untainted"] = bool(st and st[-1]["tainted"] == 0 and st[-1]["spec"] == 1)
    # replay renames: final (last) rename block per sn that survived; producer lookup per consumer
    history = []          # (sn, cls, phys) dest renames, squash-pruned
    blk_of = {}           # sn -> block (last processed)
    producer = {}         # (consumer sn, src index) -> producer sn or None
    for kind, b in blocks:
        if kind == "squash":
            history = [h for h in history if h[0] <= b]; continue
        sn = b["sn"]
        for k, (cls, phys) in enumerate(b["srcs"]):
            prod = next((h[0] for h in reversed(history) if h[1] == cls and h[2] == phys and h[0] < sn), None)
            producer[(sn, k)] = prod
        blk_of[sn] = b
        for cls, phys, flat in b["dests"]:
            history.append((sn, cls, phys))
    if xsn not in blk_of:
        out["why"] = "xmit rename block not found"; return out
    # backward slice
    sl, stack = set(), [xsn]
    while stack:
        s = stack.pop()
        if s in sl or s not in blk_of:
            continue
        sl.add(s)
        for k in range(len(blk_of[s]["srcs"])):
            p = producer.get((s, k))
            if p is not None:
                stack.append(p)
    out["slice"] = sorted(sl)
    out["parse_ok"] = not any(blk_of[s]["garbled"] for s in sl)
    # unresolved forced branches at the signal
    held = []
    for pc, seqs in (br_events or {}).items():
        for q, d in seqs.items():
            if d.get("resolve_hold") and (not d.get("resolve_visible") or d["resolve_visible"] > xmit_signal):
                held.append(int(q))
    bmin = min(held) if held else None
    origins = []
    for s in sl:
        if s == xsn or s not in loads or bmin is None or s <= bmin:
            continue
        if any(x["spec"] == 1 for x in stl_by_sn.get(s, [])):
            origins.append(s)
    out["origins"] = sorted(origins); out["held_branch_seqs"] = sorted(held)

    def src_t(tmap, s, k):
        p = producer.get((s, k))
        if p is None or p not in tmap:
            return False
        return tmap[p].get(tuple(blk_of[s]["srcs"][k]), False)

    def replay(skip16):
        """STT rename rule (rename.cc:714-720) over the slice, in program (sn) order, per destination register:
        a speculative-origin load taints its dests; any other instruction taints its dests iff a source is
        tainted; with skip16 a dest that is IntRegClass flat 16 is never tainted (taint_tracker.cc:59)."""
        tmap = {}
        for s in sorted(sl):
            if s == xsn:
                continue
            b = blk_of[s]
            t = (s in origins) or any(src_t(tmap, s, k) for k in range(len(b["srcs"])))
            tmap[s] = {(cls, phys): (t and not (skip16 and cls == "IntRegClass" and flat == 16))
                       for cls, phys, flat in b["dests"]}
        return any(src_t(tmap, xsn, k) for k in range(len(blk_of[xsn]["srcs"]))), tmap

    with_rule, _ = replay(True)
    without_rule, t_wo = replay(False)
    out["sim_with_rule"] = with_rule; out["sim_without_rule"] = without_rule
    out["via16"] = sorted(s for s in sl if s != xsn and any(cls == "IntRegClass" and flat == 16 for cls, phys, flat in blk_of[s]["dests"])
                          and any(v for (cls, phys), v in t_wo.get(s, {}).items() if cls == "IntRegClass" and phys == 16))
    return out


def one(args):
    stem, grid, mode, testset, config, keep = args
    import spt_taint_probe as P
    r = P.probe_one((f"{stem}:{grid}", f"{testset}/{mode}", config, True))
    rec = dict(stem=stem, mode=mode, grid=grid, reproduced=bool(r.get("reproduced")), error=r.get("error"),
               xmit_pc=r.get("xmit_pc"), xmit_signal=r.get("xmit_signal"))
    wd = r.get("workdir")
    try:
        if wd and r.get("xmit_pc") and r.get("xmit_signal"):
            rec.update(analyse(Path(wd) / "m5out" / "pipeview.txt", r["xmit_pc"], r["xmit_signal"], r.get("br_events")))
            st = Path(wd) / "m5out" / "stats.txt"
            m = re.search(r"^system\.cpu\.taint_tracker\.allowlistedTaintsFromTT\s+(\d+)", st.read_text(), re.M) if st.exists() else None
            rec["allowlistedTaintsFromTT"] = int(m.group(1)) if m else None
            rec["no_reveal"] = rec["allowlistedTaintsFromTT"] == 0
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    finally:
        if wd and not keep:
            w = Path(wd)
            shutil.rmtree(w.parent if w.name == "m5out" else w, ignore_errors=True)
        elif wd:
            rec["workdir"] = wd
    rec["signature"] = bool(rec.get("reproduced") and rec.get("gem5_untainted") and rec.get("sim_with_rule") is False
                            and rec.get("sim_without_rule") and rec.get("via16") and rec.get("no_reveal") and rec.get("parse_ok"))
    return rec


def rename_config(config, outdir):
    import pipeline
    cfg = pipeline.load_config(Path(config))
    fl = list(cfg["gem5"].get("debug_flags", ["O3PipeView", "LSQUnit"]))
    for need in ("O3PipeView", "LSQUnit", "Rename"):
        if need not in fl:
            fl.append(need)
    cfg["gem5"]["debug_flags"] = fl
    p = Path(outdir) / "cfg_with_rename.json"
    p.write_text(json.dumps(cfg, indent=1))
    return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True); ap.add_argument("--config", required=True)
    ap.add_argument("--testset", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=8); ap.add_argument("--keep", action="store_true")
    ap.add_argument("--only", nargs="*", help="restrict to <mode>/<stem> keys")
    a = ap.parse_args()
    camp = Path(a.campaign).resolve()
    todo = {}
    for f in sorted(glob.glob(str(camp / "*" / "_sweep_raw" / "*.json"))):
        mode = Path(f).parts[-3]; g = int(f.split("_grid")[1][:4])
        d = json.loads(Path(f).read_text()); d = d if isinstance(d, list) else d.get("results", [])
        for r in d:
            if r.get("issued_in_window") and r.get("xmit_kind", "ld") == "ld":
                if a.only and f"{mode}/{r['name']}" not in a.only:
                    continue
                k = (mode, r["name"]); todo[k] = min(todo.get(k, g), g)
    cfg = rename_config(a.config, Path(a.out).resolve().parent)
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one, [(s, g, m, a.testset, cfg, a.keep) for (m, s), g in sorted(todo.items())]))
    json.dump({f"{r['mode']}/{r['stem']}": r for r in res}, open(a.out, "w"), indent=1)
    print(f"{len(res)} ld hits; reproduced {sum(r['reproduced'] for r in res)}; "
          f"gem5_untainted {sum(bool(r.get('gem5_untainted')) for r in res)}; "
          f"full R-SA-12 signature {sum(r['signature'] for r in res)}")


if __name__ == "__main__":
    main()
