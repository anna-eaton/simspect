#!/usr/bin/env python3
"""jmprmw_pin.py -- census + pin filter for the jmp/RMW fanout corpus (2026-11-09, ultimate-stt; proposal, opt-in).

Anna (2026-11-08): "each generated test in that corpus has an RMW or a jmp". This tool checks that pin on
concretized tests WITHOUT touching parsexml, the tables or the testset: it reads each test's `.s` (x86 AT&T,
as written by the asm phase or by make_rmw_corpus.py) and its `.ann.json`, and classifies every litmus
instruction (the ones after a `__litmus_<stem>_pc<N>:` marker) by role:

  jmp_direct   `jmp <label>` (not `jmp *reg`)        -- from table branch_forms.jmp_direct (proposed/jmp_all.jsonc)
  call_direct  `call <sym>` (not `call *reg`)        -- no emitter yet (plan step J2)
  rmw          ALU op whose LAST operand is memory   -- `orq $0,(m)` (make_rmw_corpus), `orq/addq %r,(m)` (plan R1)
               (add/or/and/xor/sub/adc/sbb/inc/dec/not/neg, any width; never lock/xchg)

and by region: `committed` (at or before the `_last_committed` label), `spec` (at or after
`_first_noncommitted`), plus `xmit` when the instruction is at ann["xmit"]["pc"].

Usage:
  python3 jmprmw_pin.py <dir> [<dir> ...] [--out census.json] [--pin-list pinned_stems.txt] [--link-dst <new testset dir>]
--link-dst writes a NEW testset of symlinks, <dst>/<mode>/{asm,ann}/<stem>.{s,ann.json}, holding only the pinned tests
(mode = the path component naming a branch mode); testrun.py can consume it as its own --model. Refuses an existing dst.
<dir> is searched recursively for *.s; the annotation is <same dir>/<stem>.ann.json or <dir>/../ann/<stem>.ann.json.
Exit 0 always; the summary line says how many tests satisfy the pin. Plan + context:
wiki/state/ALLOY_MODEL_CHANGES.md, section "ultimate STT ... jmp/RMW fanout plan".
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RMW_OPS = re.compile(r"^(add|or|and|xor|sub|adc|sbb|inc|dec|not|neg)[bwlq]?$")
PC_LABEL = re.compile(r"^__litmus_(\w+?)_pc(\d+):")
LC_LABEL = re.compile(r"^__litmus_\w+_last_committed:")
FNC_LABEL = re.compile(r"^__litmus_\w+_first_noncommitted:")


def last_operand(ops: str) -> str:
    """Last top-level AT&T operand (commas inside a memory operand's parentheses do not split)."""
    depth, cut = 0, 0
    for k, ch in enumerate(ops):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            cut = k + 1
    return ops[cut:].strip()


def find_ann(s_path: Path):
    for cand in (s_path.with_suffix("").with_suffix(".ann.json"),
                 s_path.parent / (s_path.stem + ".ann.json"),
                 s_path.parent.parent / "ann" / (s_path.stem + ".ann.json")):
        if cand.exists():
            return cand
    return None


def classify(s_path: Path):
    ann_p = find_ann(s_path)
    ann = json.loads(ann_p.read_text()) if ann_p else {}
    xpc = (ann.get("xmit") or {}).get("pc")
    mode = next((c for c in s_path.parts if c.startswith(("mispredict_", "stl_bypass", "correctly_"))), "nomode")
    rec = {"stem": s_path.stem, "ann": bool(ann_p), "mode": mode, "s_path": str(s_path.resolve()),
           "ann_path": str(ann_p.resolve()) if ann_p else None, "xmit_kind": (ann.get("xmit") or {}).get("kind"),
           "hits": []}
    pc = None
    region = "committed"
    after_lc = False
    in_app = False                  # only litmus instructions (inline asm between #APP/#NO_APP) count;
    for raw in s_path.read_text().splitlines():   # compiler glue (block-layout jmp, jcc) never does
        line = raw.strip()
        if line.startswith("#APP"):
            in_app = True
            continue
        if line.startswith("#NO_APP"):
            in_app = False
            continue
        m = PC_LABEL.match(line)
        if m:
            pc = int(m.group(2))
            if after_lc:            # the first marker after the lc instruction's block
                region = "spec"
            continue
        if LC_LABEL.match(line):
            after_lc = True         # the lc instruction itself (next instruction) is still committed
            continue
        if FNC_LABEL.match(line):
            region = "spec"
            continue
        if pc is None or not in_app or not line or line.startswith(("#", ".", "/")) or line.endswith(":"):
            continue
        parts = line.split(None, 1)
        mnem, ops = parts[0], (parts[1] if len(parts) > 1 else "")
        role = None
        if mnem in ("jmp", "jmpq") and not ops.startswith("*"):
            role = "jmp_direct"
        elif mnem in ("call", "callq") and not ops.startswith("*"):
            role = "call_direct"
        elif RMW_OPS.match(mnem) and "(" in last_operand(ops):
            role = "rmw"
        if role:
            where = "xmit" if (xpc is not None and pc == xpc) else region
            rec["hits"].append({"pc": pc, "role": role, "region": where, "asm": line})
    rec["pinned"] = bool(rec["hits"])
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--pin-list")
    ap.add_argument("--link-dst")
    a = ap.parse_args()
    recs = [classify(p) for d in a.dirs for p in sorted(Path(d).rglob("*.s"))]
    roles = Counter(f"{h['role']}@{h['region']}" for r in recs for h in r["hits"])
    tests_by_role = Counter(k for r in recs for k in {f"{h['role']}@{h['region']}" for h in r["hits"]})
    summary = {"tests": len(recs), "pinned": sum(r["pinned"] for r in recs),
               "missing_ann": sum(not r["ann"] for r in recs),
               "instr_by_role_region": dict(roles), "tests_by_role_region": dict(tests_by_role)}
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": summary, "tests": recs}, indent=1))
    if a.pin_list:
        Path(a.pin_list).write_text("".join(f"{r['stem']}\n" for r in recs if r["pinned"]))
    if a.link_dst:
        dst = Path(a.link_dst)
        if dst.exists():
            sys.exit(f"refusing: {dst} exists")
        for r in recs:
            if r["pinned"] and r["ann_path"]:
                for sub, src, name in (("asm", r["s_path"], r["stem"] + ".s"),
                                       ("ann", r["ann_path"], r["stem"] + ".ann.json")):
                    d = dst / r["mode"] / sub
                    d.mkdir(parents=True, exist_ok=True)
                    (d / name).symlink_to(src)
        summary["linked_to"] = str(dst)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
