#!/usr/bin/env python3
"""verify_simspect_hooks.py — run one litmus test with ONLY --debug-flags=O3PipeView
and check the SimSpect hook lines (O3PipeView:simspect:...) appear and join to
instruction seqNums; optionally diff against a pre-hook binary to show the hooks
change nothing (identical non-simspect O3PipeView lines + identical sim ticks).

Runs inside the gem5_dev container (needs STAGE3_gem5/gem5_common.py for the
litmus build). Doc: wiki/design/SIMSPECT_HOOKS.md ("How to verify").

  python3 verify_simspect_hooks.py --bin <gem5.opt> --se <se.py> --s t.s --ann t.ann.json \
      --out <dir> [--stall 5000] [--extra "--ruby --scheme=..."] [--ref-bin <pre-hook gem5.opt>]

Writes <out>/{new,ref}/pipeview.txt + m5out, and <out>/summary.json. Prints a
summary; exits nonzero if no simspect lines, a join failure, or a ref mismatch.
"""
import argparse, collections, json, os, re, shlex, subprocess, sys
from pathlib import Path

REPO = Path(os.environ.get("SIMSPECT_REPO", "/tests/simspect"))
sys.path.insert(0, str(REPO / "STAGE3_gem5"))
import gem5_common as gc  # noqa: E402  (build_binary, _func_base_addr)


def inject_stalls(ann, stall):
    """Same rule as the demo launchers: hold mispredicted branches unresolved."""
    xmit_pc = ann.get("xmit", {}).get("pc")
    for e in ann.get("annotations", []):
        pc = e.get("branch_pc")
        if pc is None:
            continue
        if pc == xmit_pc:
            e["resolve_stall_cycles"] = 0
        elif e.get("mode") in ("mispredict_not_taken", "mispredict_taken"):
            e["resolve_stall_cycles"] = stall
        else:
            e["resolve_stall_cycles"] = 0
    return ann


def run(binary_gem5, se, test_bin, ann, extra, outdir, branch_ann=True, caches=True):
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [str(binary_gem5), f"--outdir={outdir}", "--debug-flags=O3PipeView",
           "--debug-file=pipeview.txt", str(se), f"--cmd={test_bin}",
           "--cpu-type=DerivO3CPU"]
    if caches:
        cmd.append("--caches")
    cmd.append("--scheme=2")
    if branch_ann and ann is not None:
        cmd.append(f"--branch-ann-file={ann}")
        base = gc._func_base_addr(test_bin, test_bin.stem)
        if base is not None:
            cmd.append(f"--branch-ann-base={hex(base)}")
    cmd += extra
    (outdir / "cmd.txt").write_text(" ".join(shlex.quote(c) for c in cmd) + "\n")
    p = subprocess.run(cmd, cwd=str(Path(se).parents[2]), capture_output=True,
                       text=True, timeout=600)
    (outdir / "stdout.txt").write_text(p.stdout)
    (outdir / "stderr.txt").write_text(p.stderr)
    if p.returncode != 0:
        sys.exit(f"gem5 failed rc={p.returncode}; see {outdir}/stderr.txt")
    return outdir / "pipeview.txt"


def sim_ticks(outdir):
    # old gem5: sim_ticks ; newer gem5 (SpecLFB base): simTicks
    m = re.search(r"^(?:sim_ticks|simTicks)\s+(\d+)", (outdir / "stats.txt").read_text(), re.M)
    return int(m.group(1)) if m else None


def summarize(trace):
    kinds = collections.Counter()
    fetch_seqs = set()
    ev_seqs = collections.Counter()
    examples = {}
    with open(trace) as f:
        for line in f:
            if line.startswith("O3PipeView:fetch:"):
                fetch_seqs.add(int(line.split(":")[5]))
            elif line.startswith("O3PipeView:simspect:"):
                p = line.rstrip("\n").split(":")
                st, kind = p[3], p[4]
                kinds[f"{st}:{kind}"] += 1
                examples.setdefault(f"{st}:{kind}", line.rstrip("\n"))
                f_ = dict(x.split("=", 1) for x in p[5:])
                if f_["seq"] != "-" and kind != "squash" and kind != "cleanup_done":
                    ev_seqs[int(f_["seq"])] += 1
    joined = sum(c for s, c in ev_seqs.items() if s in fetch_seqs)
    total = sum(ev_seqs.values())
    unjoined = sorted(s for s in ev_seqs if s not in fetch_seqs)
    return dict(kinds=dict(sorted(kinds.items())), examples=examples,
                attributed_events=total, joined_events=joined,
                unjoined_seqs=unjoined[:50], n_fetch_seqs=len(fetch_seqs))


def non_simspect(trace):
    with open(trace) as f:
        return [l for l in f if l.startswith("O3PipeView:")
                and not l.startswith("O3PipeView:simspect:")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--ref-bin")
    ap.add_argument("--se", required=True)
    ap.add_argument("--s", required=True)
    ap.add_argument("--ann")
    ap.add_argument("--stall", type=int, default=5000)
    ap.add_argument("--extra", default="")
    ap.add_argument("--no-caches", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    build = out / "build"
    build.mkdir(exist_ok=True)
    test_bin = gc.build_binary(Path(a.s), build)
    ann = None
    if a.ann:
        d = inject_stalls(json.loads(Path(a.ann).read_text()), a.stall)
        ann = out / "staged.ann.json"
        ann.write_text(json.dumps(d, indent=2))
    extra = shlex.split(a.extra)
    tr = run(a.bin, a.se, test_bin, ann, extra, out / "new", caches=not a.no_caches)
    summ = summarize(tr)
    summ["sim_ticks_new"] = sim_ticks(out / "new")
    ok = bool(summ["kinds"]) and summ["joined_events"] > 0
    if a.ref_bin:
        trr = run(a.ref_bin, a.se, test_bin, ann, extra, out / "ref", caches=not a.no_caches)
        summ["sim_ticks_ref"] = sim_ticks(out / "ref")
        nn, rr = non_simspect(tr), non_simspect(trr)
        summ["ref_ref_has_simspect"] = any(
            l.startswith("O3PipeView:simspect:") for l in open(trr))
        summ["non_simspect_lines_new"] = len(nn)
        summ["non_simspect_lines_ref"] = len(rr)
        summ["non_simspect_identical"] = (nn == rr)
        summ["parse_pipeview_identical"] = (gc.parse_pipeview(tr) == gc.parse_pipeview(trr))
        ok = ok and summ["non_simspect_identical"] and \
            summ["sim_ticks_new"] == summ["sim_ticks_ref"] and summ["parse_pipeview_identical"]
    summ["ok"] = ok
    (out / "summary.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps({k: v for k, v in summ.items() if k != "examples"}, indent=2))
    for k, v in summ["examples"].items():
        print("  e.g.", v)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
