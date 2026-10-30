#!/usr/bin/env python3
"""
hook_audit.py — check that each SimSpect gem5 hook really changes the pipeline.

For every test, runs gem5 several times on the same binary, switching one hook
at a time, and compares the O3PipeView + Commit traces:

    none        no --branch-ann-file, no fnc stall              (baseline)
    raw_S       the test's .ann.json exactly as compile_annotate writes it
                (branch_addr only, no branch_pc_addr alias), unresolved stall S
    ann_0       aliased annotation, every stall 0                (BTB force only)
    ann_S       aliased, unresolved branches stalled S cycles    (resolve stall)
    ann_R       aliased, resolved branches stalled S cycles      (resolved stall)
    fnc_F       no annotation, fnc commit stall F cycles         (fnc stall)

Checks (each one PASS / FAIL / NA per test, with the measured numbers):

    registered_ann     ann_S: config.ini annotationBranchPCs lists every annotated branch
    registered_raw     raw_S: same, for the un-aliased file (the loader-key question)
    raw_equals_ann     raw_S trace == ann_S trace  (raw format fully honoured)
    force_taken        mispredict_taken branches: no squash in `none`, squash in `ann_0`
    force_noop_nt      not-taken-only tests: ann_0 trace == none trace (no-op registration)
    resolved_correct   no mispredict squash at any correctly_not_taken PC, in every variant
    stall_shift        oldest mispredicted unresolved branch: squash and ready-in-ROB
                       tick move by S cycles (ann_S vs ann_0)
    resolved_stall     each resolved branch's ready-in-ROB tick moves by S cycles (ann_R vs ann_0)
    fnc_shift          fnc retire tick moves by >= F cycles (fnc_F vs none)
    br_events          (builds with the BR resolve lines) every stalled branch has a
                       resolve_hold line and its release/visible ticks match the trace

The "ready within ROB" tick is the Commit-flag line printed right before
setCanCommit() in markCompletedInsts on every build (wiki/design/
RESOLUTION_HOOKS_SURVEY.md §B): the point each defense treats as "resolved".

Usage (inside the gem5_dev container):
    python3 STAGE3_gem5/hook_audit.py --build stt --testset testsets/STT_6 \
        --n 6 --jobs 16 --out hook_audit_stt.json
    python3 STAGE3_gem5/hook_audit.py --build all ...
Builds are defined in BUILDS below (binary / se.py / cpu / extra_args copied
from the campaign run_config.jsonc files). Design: wiki/design/HOOK_AUDIT.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gem5_common import (_func_base_addr, build_binary, parse_commit_squashes,  # noqa: E402
                         parse_pipeview_by_seq, parse_simspect_events,
                         parse_ticks_per_cycle)

# binary, se.py, cpu, extra args: copied from each build's campaign run_config.jsonc
# (cafe2 /tests/simspect/results/*/run_config.jsonc, read 2026-10-30).
_AM = "/work/amulet/amulet-gem5-"
BUILDS = {
    "gem5-recon-modded": dict(
        bin="/work/gem5-recon-modded/build/X86/gem5.opt",
        se="/work/gem5-recon-modded/configs/example/se.py", cpu="X86O3CPU", extra=[]),
    "stt": dict(bin="/work/stt/build/X86/gem5.opt",
                se="/work/stt/configs/example/se.py", cpu="DerivO3CPU", extra=[]),
    "stt-dbg": dict(bin="/work/stt-dbg/build/X86/gem5.opt",
                    se="/work/stt-dbg/configs/example/se.py", cpu="DerivO3CPU", extra=[]),
    "gem5-spt": dict(
        bin="/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt",
        se="/work/gem5-spt/configs/example/se.py", cpu="DerivO3CPU",
        extra=["--applyDDIFT=1", "--fwdUntaint=1", "--bwdUntaint=1",
               "--configImpFlow=Lazy", "--scheme=SpectreSafeFence"]),
    "amulet-InvisiSpec": dict(
        bin=_AM + "InvisiSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt",
        se=_AM + "InvisiSpec_AE-v1.1/configs/example/se.py", cpu="DerivO3CPU",
        extra=["--ruby", "--scheme=SpectreSafeInvisibleSpec", "--needsTSO=1",
               "--allowSpecBuffHit=1", "--l1d_size=1kB", "--l1d_assoc=2",
               "--l1i_size=32kB", "--l1i_assoc=4", "--l2_size=2MB", "--l2_assoc=16",
               "--L1_TBEs=2", "--L2_TBEs=2", "--DC_TBEs=2"]),
    "amulet-CleanupSpec": dict(
        bin=_AM + "CleanupSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt",
        se=_AM + "CleanupSpec_AE-v1.1/configs/example/se.py", cpu="DerivO3CPU",
        extra=["--ruby", "--scheme_invisispec=UnsafeBaseline",
               "--scheme_cleanupcache=Cleanup_FOR_L1L2", "--needsTSO=0",
               "--l1d_size=2kB", "--l1d_assoc=4", "--l1i_size=32kB", "--l1i_assoc=4",
               "--l2_size=2MB", "--l2_assoc=16", "--L1_TBEs=2", "--L2_TBEs=2",
               "--DC_TBEs=2", "--abs-max-tick=3000000000"]),
    "amulet-SpecLFB": dict(
        bin=_AM + "SpecLFB_AE-v1.1/build/X86/gem5.opt",
        se=_AM + "SpecLFB_AE-v1.1/configs/example/se.py", cpu="DerivO3CPU",
        extra=["--scheme=Speclfb", "--l2cache", "--l1d_size=1kB", "--l1d_assoc=2",
               "--l1i_size=32kB", "--l1i_assoc=8", "--l2_size=2MB", "--l2_assoc=16"]),
    "amulet-STT": dict(bin=_AM + "STT_AE-v1.1/build/X86/gem5.opt",
                       se=_AM + "STT_AE-v1.1/configs/example/se.py", cpu="DerivO3CPU",
                       extra=[]),
}

DBG_FLAGS = "O3PipeView,Commit"
TOL_CYCLES = 3          # allowed slack on a measured shift, in cycles

_READY_RE = re.compile(
    r"^\s*(\d+):\s+system\.cpu\.commit:.*Marking PC \(?(0x[0-9a-f]+)=>.*\[sn:(\d+)\] ready")


def _gem5_cmd(build: dict, outdir: Path, binary: Path, ann_file: Path | None,
              base: int | None, fnc_pc: int | None, fnc_cycles: int,
              scheme: int) -> list:
    # Mirrors gem5_common.run_gem5 (same flag order, --caches, --scheme then extra).
    cmd = [build["bin"], f"--outdir={outdir}", f"--debug-flags={DBG_FLAGS}",
           "--debug-file=trace.txt", build["se"], f"--cmd={binary}",
           f"--cpu-type={build['cpu']}", "--caches", f"--scheme={scheme}",
           "--abs-max-tick=100000000000"]
    if ann_file is not None:
        cmd.append(f"--branch-ann-file={ann_file}")
        if base is not None:
            cmd.append(f"--branch-ann-base={hex(base)}")
    if fnc_pc is not None and fnc_cycles > 0:
        cmd += [f"--fnc-commit-stall-pc={hex(fnc_pc)}",
                f"--fnc-commit-stall-cycles={fnc_cycles}"]
    return cmd + list(build["extra"])


def _config_ini_hooks(outdir: Path) -> dict:
    """The hook params gem5 actually instantiated, from m5out/config.ini."""
    out = {}
    text = (outdir / "config.ini").read_text()
    for key in ("annotationBranchPCs", "annotationForcedTargets",
                "annotationResolveStallCycles", "fncCommitStallPC",
                "fncCommitStallCycles"):
        m = re.search(rf"^{key}=(.*)$", text, re.M)
        out[key] = m.group(1).split() if m else None
    return out


def _parse_ready(trace: Path) -> dict:
    """pc -> sorted ticks of 'Marking PC ... ready within ROB' (one per micro-op)."""
    by_pc: dict = {}
    with open(trace) as f:
        for line in f:
            m = _READY_RE.match(line)
            if m:
                by_pc.setdefault(int(m.group(2), 16), []).append(int(m.group(1)))
    return {pc: sorted(t) for pc, t in by_pc.items()}


def _run_variant(build: dict, workdir: Path, name: str, binary: Path,
                 ann: dict | None, base: int | None, fnc_pc: int | None,
                 fnc_cycles: int, scheme: int, timeout: int) -> dict:
    vdir = workdir / name
    vdir.mkdir()
    ann_file = None
    if ann is not None:
        ann_file = vdir / "ann.json"
        ann_file.write_text(json.dumps(ann, indent=1))
    cmd = _gem5_cmd(build, vdir / "m5out", binary, ann_file, base, fnc_pc,
                    fnc_cycles, scheme)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       cwd=str(Path(build["bin"]).parents[2]))
    res = dict(cmd=" ".join(cmd), rc=p.returncode)
    if p.returncode != 0:
        res["error"] = next((ln for ln in p.stderr.splitlines()
                             if ln.startswith(("panic:", "fatal:"))), p.stderr[-400:])
        return res
    trace = vdir / "m5out" / "trace.txt"
    res["hooks"] = _config_ini_hooks(vdir / "m5out")
    res["tpc"] = parse_ticks_per_cycle(vdir / "m5out")
    seqs = parse_pipeview_by_seq(trace)
    res["pipeview"] = sorted((r["seq"], r["pc"], r["upc"], r["fetch"], r["decode"],
                              r["rename"], r["dispatch"], r["issue"], r["complete"],
                              r["retire"]) for r in seqs.values())
    res["squash"] = {hex(k): v for k, v in parse_commit_squashes(trace).items()}
    res["ready"] = {hex(k): v for k, v in _parse_ready(trace).items()}
    res["br_events"] = [e for e in parse_simspect_events(trace) if e["struct"] == "BR"]
    # Fingerprint of everything except the simspect lines, to prove a rebuild
    # that only adds print lines leaves the pipeline unchanged.
    res["sha"] = hashlib.sha256(json.dumps(
        [res["pipeview"], res["squash"], res["ready"]]).encode()).hexdigest()[:16]
    retire_by_pc: dict = {}
    for r in seqs.values():
        if r["retire"] > 0:
            retire_by_pc.setdefault(hex(r["pc"]), []).append(r["retire"])
    res["retire"] = retire_by_pc
    return res


def _with_stalls(ann: dict, alias: bool, unresolved_s: int, resolved_s: int) -> dict:
    out = json.loads(json.dumps(ann))
    xmit_pc = out.get("xmit", {}).get("pc")
    for e in out.get("annotations", []):
        if alias and "branch_addr" in e:
            e["branch_pc_addr"] = e["branch_addr"]
            e["branch_pc_addr_hex"] = hex(int(e["branch_addr"]))
        if e.get("branch_pc") == xmit_pc:
            e["resolve_stall_cycles"] = 0        # as pipeline._inject_stalls
        elif e.get("mode") == "correctly_not_taken":
            e["resolve_stall_cycles"] = resolved_s
        else:
            e["resolve_stall_cycles"] = unresolved_s
    return out


def _check(cond, **kw) -> dict:
    return dict(result="PASS" if cond else "FAIL", **kw)


def _na(why: str) -> dict:
    return dict(result="NA", why=why)


def audit_one(build_name: str, s_path: str, ann_path: str, S: int, F: int,
              scheme: int, timeout: int, keep: bool) -> dict:
    build = BUILDS[build_name]
    s_path, ann_path = Path(s_path), Path(ann_path)
    stem = s_path.stem
    workdir = Path(tempfile.mkdtemp(prefix=f"hookaudit_{stem}_"))
    rec = dict(build=build_name, test=stem, s=str(s_path), S=S, F=F, checks={})
    try:
        ann = json.loads(ann_path.read_text())
        binary = build_binary(s_path, workdir)
        base = _func_base_addr(binary, stem)
        xmit_pc = ann.get("xmit", {}).get("pc")
        fnc = (ann.get("commit_boundary") or {}).get("first_noncommitted") or {}
        fnc_pc = fnc.get("addr")
        brs = [dict(alloy_pc=e["branch_pc"], addr=int(e["branch_addr"]),
                    mode=e.get("mode"), is_xmit=e["branch_pc"] == xmit_pc)
               for e in ann.get("annotations", []) if "branch_addr" in e]
        rec["branches"] = brs
        rec["fnc_addr"] = hex(fnc_pc) if fnc_pc else None
        V = {}
        run = lambda n, a, fp=None, fc=0: _run_variant(  # noqa: E731
            build, workdir, n, binary, a, base, fp, fc, scheme, timeout)
        V["none"] = run("none", None)
        V["raw_S"] = run("raw_S", _with_stalls(ann, False, S, 0))
        V["ann_0"] = run("ann_0", _with_stalls(ann, True, 0, 0))
        V["ann_S"] = run("ann_S", _with_stalls(ann, True, S, 0))
        V["ann_R"] = run("ann_R", _with_stalls(ann, True, 0, S))
        V["fnc_F"] = run("fnc_F", None, fnc_pc, F) if fnc_pc else None
        errs = {k: v["error"] for k, v in V.items() if v and v.get("rc")}
        if errs:
            rec["status"] = "error"
            rec["errors"] = errs
            return rec
        tpc = V["none"]["tpc"]
        C = rec["checks"]
        want = sorted(str(b["addr"]) for b in brs)

        def regd(v):
            return sorted(V[v]["hooks"].get("annotationBranchPCs") or [])
        C["registered_ann"] = _check(regd("ann_S") == want, got=regd("ann_S"), want=want)
        C["registered_raw"] = _check(regd("raw_S") == want, got=regd("raw_S"), want=want)
        C["raw_equals_ann"] = _check(V["raw_S"]["pipeview"] == V["ann_S"]["pipeview"])
        C["raw_equals_none"] = dict(result="INFO",
                                    value=V["raw_S"]["pipeview"] == V["none"]["pipeview"])

        def sq(v, addr):
            return V[v]["squash"].get(hex(addr), [])

        def ready(v, addr):
            t = V[v]["ready"].get(hex(addr), [])
            return max(t) if t else None

        taken = [b for b in brs if b["mode"] == "mispredict_taken"]
        if taken:
            # The force must leave a mispredict at the branch. If `none` already
            # mispredicts there, the code layout put the critical section on the
            # fall-through path and the force is redundant (reported, not a fail).
            C["force_taken"] = _check(
                all(sq("ann_0", b["addr"]) for b in taken),
                detail=[dict(addr=hex(b["addr"]), none=sq("none", b["addr"]),
                             ann_0=sq("ann_0", b["addr"]),
                             redundant=bool(sq("none", b["addr"]))) for b in taken])
            C["force_noop_nt"] = _na("test has a mispredict_taken branch")
        else:
            C["force_taken"] = _na("no mispredict_taken branch")
            C["force_noop_nt"] = _check(V["ann_0"]["pipeview"] == V["none"]["pipeview"])

        resolved = [b for b in brs if b["mode"] == "correctly_not_taken"]
        if resolved:
            bad = [dict(variant=v, addr=hex(b["addr"]), squash=sq(v, b["addr"]))
                   for v in V if V[v] for b in resolved if sq(v, b["addr"])]
            C["resolved_correct"] = _check(not bad, bad=bad)
        else:
            C["resolved_correct"] = _na("no resolved branch")

        # Oldest non-xmit mispredicting branch: the one whose stall must show.
        unres = sorted((b for b in brs if b["mode"] != "correctly_not_taken"
                        and not b["is_xmit"]), key=lambda b: b["addr"])
        mis = [b for b in unres if sq("ann_0", b["addr"])]
        if mis:
            b = mis[0]
            d_sq = (min(sq("ann_S", b["addr"]) or [0]) - min(sq("ann_0", b["addr"]))) / tpc
            r0, rS = ready("ann_0", b["addr"]), ready("ann_S", b["addr"])
            d_rd = (rS - r0) / tpc if r0 and rS else None
            C["stall_shift"] = _check(
                abs(d_sq - S) <= TOL_CYCLES and d_rd is not None and abs(d_rd - S) <= TOL_CYCLES,
                addr=hex(b["addr"]), squash_shift_cycles=d_sq, ready_shift_cycles=d_rd)
            draw = (min(sq("raw_S", b["addr"]) or [0]) - min(sq("ann_0", b["addr"]))) / tpc
            C["raw_stall_shift"] = _check(abs(draw - S) <= TOL_CYCLES,
                                          squash_shift_cycles=draw)
        else:
            C["stall_shift"] = _na("no non-xmit unresolved branch mispredicted in ann_0")
            C["raw_stall_shift"] = _na("as stall_shift")

        # Resolved branches younger than the oldest mispredicting branch are on its
        # wrong path: squashed before they resolve, so their stall cannot show.
        first_mis = mis[0]["addr"] if mis else None
        on_path = [b for b in resolved if first_mis is None or b["addr"] < first_mis]
        if on_path:
            det, ok = [], True
            for b in on_path:
                r0, rR = ready("ann_0", b["addr"]), ready("ann_R", b["addr"])
                d = (rR - r0) / tpc if r0 and rR else None
                ret = bool(V["ann_R"]["retire"].get(hex(b["addr"])))
                det.append(dict(addr=hex(b["addr"]), ready_shift_cycles=d, retired=ret))
                ok &= d is not None and abs(d - S) <= TOL_CYCLES and ret
            C["resolved_stall"] = _check(ok, detail=det)
        elif resolved:
            C["resolved_stall"] = _na("every resolved branch is on the wrong path")
        else:
            C["resolved_stall"] = _na("no resolved branch")

        if V["fnc_F"]:
            r0 = max(V["none"]["retire"].get(hex(fnc_pc), [0]))
            rF = max(V["fnc_F"]["retire"].get(hex(fnc_pc), [0]))
            d = (rF - r0) / tpc if r0 and rF else None
            C["fnc_registered"] = _check(
                (V["fnc_F"]["hooks"].get("fncCommitStallPC") or [""])[0] == str(fnc_pc),
                got=V["fnc_F"]["hooks"].get("fncCommitStallPC"))
            C["fnc_shift"] = _check(d is not None and d >= F - TOL_CYCLES,
                                    retire_shift_cycles=d, none=r0, fnc_F=rF)
        else:
            C["fnc_shift"] = _na("no fnc")

        ev = V["ann_S"]["br_events"]
        if ev:
            holds = {e.get("pc") for e in ev if e["kind"] == "resolve_hold"}
            need = {b["addr"] for b in unres}
            fetched = {b["addr"] for b in unres if V["ann_S"]["ready"].get(hex(b["addr"]))
                       or sq("ann_S", b["addr"])}
            C["br_events"] = _check(fetched <= holds, holds=sorted(map(hex, holds)),
                                    need=sorted(map(hex, need)))
        else:
            C["br_events"] = _na("binary prints no BR resolve lines")

        rec["status"] = "ok"
        rec["summary"] = {k: v["result"] for k, v in C.items()}
        if keep:
            rec["variants"] = {k: {kk: vv for kk, vv in v.items() if kk != "pipeview"}
                               for k, v in V.items() if v}
        return rec
    except Exception as e:  # noqa: BLE001 — report, never hide
        rec["status"] = "error"
        rec["errors"] = {"harness": repr(e)}
        return rec
    finally:
        if keep:
            rec["workdir"] = str(workdir)
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def pick_tests(testset: Path, n: int, seed: int) -> list:
    """n tests per mode, preferring ones with a resolved and an unresolved branch."""
    picked = []
    for mode_dir in sorted(p for p in testset.iterdir() if (p / "ann").is_dir()):
        anns = sorted((mode_dir / "ann").glob("*.ann.json"))
        rng = random.Random(zlib.crc32(f"{seed}:{mode_dir.name}".encode()))
        rng.shuffle(anns)
        before, has_res, rest = [], [], []
        for a in anns[: 80 * n]:
            stem = a.name[: -len(".ann.json")]
            s = mode_dir / "asm" / f"{stem}.s"
            if not s.exists():
                continue
            d = json.loads(a.read_text())
            xpc = d.get("xmit", {}).get("pc")
            es = d.get("annotations", [])
            res = [e["branch_pc"] for e in es if e.get("mode") == "correctly_not_taken"]
            unr = [e["branch_pc"] for e in es if e.get("mode") != "correctly_not_taken"
                   and e["branch_pc"] != xpc]
            if res and unr and min(res) < min(unr):
                before.append((s, a))     # resolved branch on the correct path
            elif res:
                has_res.append((s, a))
            else:
                rest.append((s, a))
        k = (n + 1) // 2
        sel = before[:k] + has_res[: n - len(before[:k])]
        picked += (sel + rest)[:n]
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--build", required=True, help="build name or 'all'")
    ap.add_argument("--testset", required=True, type=Path)
    ap.add_argument("--n", type=int, default=6, help="tests per branch mode")
    ap.add_argument("--S", type=int, default=200, help="resolve stall cycles")
    ap.add_argument("--F", type=int, default=150, help="fnc commit stall cycles")
    ap.add_argument("--scheme", type=int, default=2)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--keep", action="store_true", help="keep workdirs + variant detail")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    builds = list(BUILDS) if a.build == "all" else a.build.split(",")
    tests = pick_tests(a.testset, a.n, a.seed)
    jobs = [(b, str(s), str(an)) for b in builds for s, an in tests]
    print(f"[hook_audit] {len(builds)} builds x {len(tests)} tests = {len(jobs)} audits",
          flush=True)
    recs = []
    with ProcessPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(audit_one, b, s, an, a.S, a.F, a.scheme, a.timeout, a.keep)
                for b, s, an in jobs]
        for f in as_completed(futs):
            r = f.result()
            recs.append(r)
            print(f"[hook_audit] {r['build']:20s} {r['test']:28s} {r['status']:5s} "
                  f"{r.get('summary') or r.get('errors')}", flush=True)
    recs.sort(key=lambda r: (r["build"], r["test"]))
    table: dict = {}
    for r in recs:
        for k, v in (r.get("summary") or {}).items():
            table.setdefault(r["build"], {}).setdefault(k, {}).setdefault(v, 0)
            table[r["build"]][k][v] += 1
        if r["status"] == "error":
            table.setdefault(r["build"], {}).setdefault("_errors", 0)
            table[r["build"]]["_errors"] += 1
    a.out.write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()},
                                     table=table, records=recs), indent=1))
    print(json.dumps(table, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
