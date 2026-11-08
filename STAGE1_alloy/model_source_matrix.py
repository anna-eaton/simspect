#!/usr/bin/env python3
"""Which speculation-source kinds does each Alloy model admit?

For every model x forcing predicate, writes a temp copy of the model with an extra
first `run` command = gen_useful_litmus + the predicate (a6CountModels runs the
first command), asks Alloy for up to --limit instances, and reports SAT/UNSAT.
The models themselves are never modified.

  python3 STAGE1_alloy/model_source_matrix.py models/STT_6.als models/proposed/STT_6_shadows.als ...
      [--limit 1] [--keep DIR] [--only br_only,str_only] [--jobs 6] [--timeout 1800]

--keep DIR saves each witness (inst-*.xml/.txt) under DIR/<model>/<pred>/.
Cells run in parallel and print as they finish; a cell past --timeout is TIMEOUT
(unknown, not UNSAT: UNSAT proofs are the slow ones).
"""
import argparse, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
UB = "(unresolved & (Branchxs+Branchns))"
US = "(unresolved & Stores)"
UL = "(unresolved & Loads)"
UO = "(unresolved & (Otherns+Otherxs))"
PREDS = {
    "any":        "",
    "br_only":    f"some {UB} and no ({US}+{UL}+{UO})",
    "str_only":   f"some {US} and no ({UB}+{UL}+{UO})",
    "br_and_str": f"some {UB} and some {US} and no ({UL}+{UO})",
    "ld_only":    f"some {UL} and no ({UB}+{US}+{UO})",
    "oth_only":   f"some {UO} and no ({UB}+{US}+{UL})",
    # a load at or before the xmit reads what an older unresolved store writes (STT_6_stl's alias fact)
    "str_alias":  f"some {US} and no ({UB}+{UL}+{UO}) and (some s: {US}, l: uncommitted & Loads | "
                  f"some (s.outmem.rf & l.inmem) and l in xm + xm.^(~spo))",
    "str_noalias": f"some {US} and no ({UB}+{UL}+{UO}) and (no s: {US}, l: uncommitted & Loads | "
                   f"some (s.outmem.rf & l.inmem) and l in xm + xm.^(~spo))",
    # atom-based alias (how parsexml pass2_6 pairs): every unresolved store has a younger load at or
    # before the xmit naming the same Mem_s, with no other store to it in between; rf not required
    "str_alias_atom": f"some {US} and no ({UB}+{UL}+{UO}) and (all s: {US} | some l: uncommitted & Loads | "
                      f"some (s.outmem.opstate & l.inmem.opstate) and s->l in ^spo and l in xm + xm.^(~spo) "
                      f"and no s2: Stores - s | some (s2.outmem.opstate & s.outmem.opstate) "
                      f"and s->s2 in ^spo and s2->l in ^spo)",
}
SCOPE = "for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"


def run_one(model: Path, pred: str, limit: int, keep: Path | None, timeout: int) -> tuple[str, int, float]:
    src = model.read_text()
    anchor = re.search(r"^run gen_lit", src, re.M)
    if not anchor:
        sys.exit(f"{model}: no `run gen_lit` command")
    body = "gen_useful_litmus" + (f"\n  {PREDS[pred]}" if PREDS[pred] else "")
    cmd = f"run chk_{pred} {{\n  {body}\n}} {SCOPE}\n\n"
    with tempfile.TemporaryDirectory() as td:
        tmp_model = Path(td) / model.name
        tmp_model.write_text(src[:anchor.start()] + cmd + src[anchor.start():])
        out = Path(td) / "out"
        out.mkdir()
        t0 = time.time()
        try:
            r = subprocess.run(["java", "-cp", "alloy6.jar:.", "a6CountModels", str(tmp_model), str(out), str(limit)],
                               cwd=HERE, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            n = len(list(out.glob("inst-*.xml")))
            return ("SAT" if n else "TIMEOUT"), n, time.time() - t0
        dt = time.time() - t0
        if r.returncode != 0:
            return f"ERROR: {r.stderr.strip()[-300:]}", 0, dt
        n = len(list(out.glob("inst-*.xml")))
        if keep and n:
            dst = keep / model.stem / pred
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(out, dst)
        return ("SAT" if n else "UNSAT"), n, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+", type=Path)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--keep", type=Path)
    ap.add_argument("--only", default=",".join(PREDS))
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()
    preds = a.only.split(",")
    models = [m if m.is_absolute() else (Path.cwd() / m) for m in a.models]
    res = {}
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(run_one, m, p, a.limit, a.keep, a.timeout): (m.stem, p) for m in models for p in preds}
        for fu in as_completed(futs):
            r, n, dt = fu.result()
            res[futs[fu]] = f"{r if a.limit == 1 else f'{r}:{n}'}({dt:.0f}s)"
            print(f"  {futs[fu][0]:22s} {futs[fu][1]:12s} {res[futs[fu]]}", flush=True)
    print(f"{'model':22s} " + " ".join(f"{p:>12s}" for p in preds))
    for m in models:
        print(f"{m.stem:22s} " + " ".join(f"{res[(m.stem, p)]:>12s}" for p in preds))


if __name__ == "__main__":
    main()
