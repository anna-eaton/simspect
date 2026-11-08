#!/usr/bin/env python3
"""derive_core.py — derive a Stage-1 "core" model from a production Alloy model.

DRAFT TOOLING (2026-11-03, two-phase models task). Output drafts are UNAPPROVED:
they must not feed any production testset until Anna signs off
(wiki/design/TWO_PHASE_MODELS.md).

It applies, to a copy of <model>.als, exactly the three changes that the existing
prototype STAGE1_alloy/models/STT_6_core.als applies to STT_6.als (see
`diff -u STT_6.als STT_6_core.als` and wiki/findings/mdsToRead/STAGED_ENUMERATION.md
"Stage 1"), and nothing else:

  1. remove the idx/IX0..IX5 symmetry-breaking (sigs, the `idx` field, the
     idx_bijective / idx_surjective / lt_ix / idx_matches_spo block); spo
     program-order facts are kept;
  2. add the minimality clauses that Stage 1 turns on, at the end of
     gen_useful_litmus: (e) RO operand-minimality and (f) RI instruction-
     minimality (the prototype's choice; `--minimality ri` emits RI only, for the
     open RO-vs-RI-only decision, URGENT_TODO.md #2 / BIGFIG_FACT_AUDIT.md D4);
  3. relax the scope `exactly 6 Instruction` -> `6 Instruction` (up to 6).

Every other line (shared skeleton, model-specific source facts, and the
three-clause defense block) is copied byte for byte. Each anchor must occur
exactly once or the script refuses, so a drifted source model cannot silently
produce a wrong draft. The source .als is only read.

Usage:
  python3 derive_core.py <source.als> <out.als> [--minimality rori|ri]
"""
import argparse
import hashlib
import sys
from pathlib import Path

IX_BLOCK = """// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)
one sig IX0 {} -- spo position 0 (first)å
one sig IX1 {} -- spo position 1
one sig IX2 {} -- spo position 2
one sig IX3 {} -- spo position 2
one sig IX4 {} -- spo position 2
one sig IX5 {} -- spo position 2
"""
IX_REPL = """// [STAGE-1 CORE] idx/IX symmetry-breaking REMOVED (ordering rules stripped per
// staged-enum design) so cores are not pinned to a fixed length/positions.
"""

IDX_FIELD = "\tidx: one (IX0 + IX1 + IX2 + IX3 + IX4 + IX5),  -- bijection to fixed position atoms\n"

SYM_BLOCK = (
    "/*********************************************************************************\n"
    " * Symmetry breaking \u2014 works because Instruction is now a concrete sig\n"
    " */\n"
    "\n"
    "-- idx bijection: each instruction gets a unique fixed position atom\n"
    "fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }\n"
    "fact idx_surjective { (IX0 + IX1 + IX2 + IX3 + IX4 + IX5) = Instruction.idx }\n"
    "\n"
    "-- IX0 < IX1 < IX2 is a fixed static ordering (no atom permutations possible)\n"
    "pred lt_ix[a, b: univ] { (a=IX0 and b in IX1+IX2+IX3+IX4+IX5) \n"
    "\t\t\t\tor (a=IX1 and b in IX2+IX3+IX4+IX5)\n"
    "\t\t\t\tor (a=IX2 and b in IX3+IX4+IX5)\n"
    "\t\t\t\tor (a=IX3 and b in IX4+IX5)\n"
    "\t\t\t\tor (a=IX4 and b=IX5)\n"
    "\n"
    "}\n"
    "\n"
    "-- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third\n"
    "fact idx_matches_spo {\n"
    "\tall disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo\n"
    "}\n"
)
SYM_REPL = """/*********************************************************************************
 * [STAGE-1 CORE] Symmetry breaking (idx/IX ordering rules) REMOVED.
 * spo program-order facts (spo_acyclic/spo_prior/spo_total) are kept — they are
 * execution semantics, not symmetry-breaking. a6CountModels runs symmetry=80.
 */
"""

GEN_HEAD = "let gen_useful_litmus {\n"
RO_CLAUSE = """
  // [STAGE-1 CORE] (e) operand-minimality: every operand necessary (no removable operand)
  all o: Operand     | secure_speculation_scheme_p[RO->o]"""
RI_CLAUSE = """
  // [STAGE-1 CORE] (f) instruction-minimality: every instruction necessary (no removable instr)
  all i: Instruction | secure_speculation_scheme_p[RI->i]"""

SCOPE_OLD = "} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"
SCOPE_NEW = "} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"
RUN_OLD = "run gen_lit {\n  gen_useful_litmus\n" + SCOPE_OLD
RUN_NEW = ("// [STAGE-1 CORE] length restriction relaxed: 'exactly 6' -> 'up to 6' Instruction.\n"
           "// RI-minimality keeps cores small; this is just the upper bound for the search.\n"
           "run gen_lit {\n  gen_useful_litmus\n" + SCOPE_NEW)


def replace_once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        sys.exit(f"refusing: anchor '{what}' occurs {n} times (expected 1)")
    return text.replace(old, new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--minimality", choices=["rori", "ri"], default="rori")
    a = ap.parse_args()
    src = Path(a.source)
    raw = src.read_bytes()
    text = raw.decode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()

    text = replace_once(text, IX_BLOCK, IX_REPL, "IX sigs")
    text = replace_once(text, IDX_FIELD, "", "idx field")
    text = replace_once(text, SYM_BLOCK, SYM_REPL, "symmetry-breaking block")

    # (e)/(f): append before the closing brace of gen_useful_litmus
    if text.count(GEN_HEAD) != 1:
        sys.exit("refusing: gen_useful_litmus head not found exactly once")
    start = text.index(GEN_HEAD)
    end = text.index("\n}\n", start)
    body = text[start:end].rstrip("\n")
    add = (RO_CLAUSE if a.minimality == "rori" else "") + RI_CLAUSE
    text = text[:start] + body + "\n" + add + text[end:]

    text = replace_once(text, RUN_OLD, RUN_NEW, "run gen_lit scope")

    clauses = "(e) RO + (f) RI" if a.minimality == "rori" else "(f) RI only"
    header = (
        "// =============================================================================\n"
        f"// [STAGE-1 CORE DRAFT — UNAPPROVED, do not use for production testsets]\n"
        f"// Derived from {src.name} (sha256 {sha}) by\n"
        f"// STAGE1_alloy/models/proposed_twophase/derive_core.py --minimality {a.minimality}.\n"
        "// Same three changes as the STT_6_core.als prototype: idx/IX symmetry-breaking\n"
        f"// removed, minimality {clauses} added to gen_useful_litmus, scope 'exactly 6'\n"
        "// -> 'but 6' Instruction. Everything else (skeleton, source facts, defense\n"
        f"// block) is byte-identical to {src.name}. Stage 1.5 = {src.name} itself +\n"
        "// stage_seed.py seed (stage_pipeline.py). Review: wiki/design/TWO_PHASE_MODELS.md\n"
        "// =============================================================================\n"
    )
    Path(a.out).write_text(header + text, encoding="utf-8")
    print(f"wrote {a.out} from {src} (sha256 {sha[:16]}…, minimality={a.minimality})")


if __name__ == "__main__":
    main()
