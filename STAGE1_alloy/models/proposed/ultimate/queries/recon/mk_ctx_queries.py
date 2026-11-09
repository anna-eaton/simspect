#!/usr/bin/env python3
"""mk_ctx_queries.py -- EXPLORATORY (recon agent, 2026-11-09): a second-order ("un-protection context") minimality
for Stage-1 cores, tested on SKELETON_u.als + blocks/Recon_6_u.block.als (spliced in memory; SKELETON_u's multi-RI
spo_p [sk-5] and rf bridge [sk-6] are exact, which double perturbations need). Writes q/x*.als and RUNLIST_ctx.tsv.

Why: a ReCon reveal only ever REMOVES a leak, so plain RI/RS-minimality ("every element is necessary for the leak")
can never keep the LD1 -> LD2 pair, and no Stage-1 core exercises ReCon (model-fixes 2026-11-08: Recon RI cores =
STT RI cores). Context minimality also accepts an element e when e is the security context of a necessary
perturbation b: secure(I - b) but not secure(I - b - e). For the concealed-reveal test, b = the concealing store
(removing it lets the reveal apply) and e = LD1, LD2, the pair register. For a defense whose protection is monotone
under perturbation (STT: no un-protect mechanism) the extra disjunct can never hold, so it equals plain minimality.
Not a proposal to change any model: a DECIDE input (option (d) for "ReCon reveal unreachable from Stage 1").
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ULT = HERE.parents[1]
Q = HERE / "q"
Q.mkdir(exist_ok=True)
SKEL = (ULT / "SKELETON_u.als").read_text()
BLOCK = (ULT / "blocks" / "Recon_6_u.block.als").read_text()
STT_SEED = "fun hardware_protection_policy[p: PTag->univ] : Operand {spec_loads_p[p].(inmem_p[p])}"
RECON_SEED = "fun hardware_protection_policy[p: PTag->univ] : Operand {spec_loads_p[p].(inmem_p[p]) - revealed_p[p]}"
assert BLOCK.count(RECON_SEED) == 1
BLOCK_STT = BLOCK.replace(RECON_SEED, STT_SEED)   # the STT_6_u semantics (reveal functions left defined, unused)


def splice(block):
    lines = SKEL.split("\n")
    b = next(i for i, l in enumerate(lines) if l.strip() == "//@@DEFENSE-BEGIN")
    e = next(i for i, l in enumerate(lines) if l.strip() == "//@@DEFENSE-END")
    return "\n".join(lines[:b + 1] + block.rstrip("\n").split("\n") + lines[e:])


CTX = """
// ---- EXPLORATORY context minimality (recon agent 2026-11-09; see mk_ctx_queries.py) ----
// q is justified iff removing it makes the instance secure (plain minimality), or q is part of the security
// context of a perturbation b that does: secure(b) and not secure(b + q), b ranging over RI of one
// instruction and the commit-boundary perturbation.
pred just_ctx[q: PTag->univ] {
  secure_speculation_scheme_p[q]
  or (some j: Instruction | secure_speculation_scheme_p[RI->j] and not secure_speculation_scheme_p[RI->j + q])
  or (secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
      and not secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted + q])
}
pred gen_core_ctx {
  leaks
  min_RR[Instruction]
  min_RC
  all s: State | just_ctx[RS->s]
  all i: Instruction | just_ctx[RI->i]
}
fun pairC_q : Instruction -> Instruction { {ld1, ld2: Loads | ld2 in committed and some (ld1.outreg.rf & ld2.inaddr)} }
"""
RUN = []


def add(name, block, q, limit, to, expect, k=6):
    t = splice(block)
    old = "run gen_lit {\n  gen_useful_litmus\n} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"
    assert t.count(old) == 1
    t = t.replace(old, f"run gen_lit {{\n  q\n}} for 9 but {k} Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
    t += "\n" + CTX + q.strip() + "\n"
    (Q / f"{name}.als").write_text(t)
    RUN.append((name, limit, to, expect))


add("x0_core_plain_recon_b5", BLOCK, "pred q { gen_core and some pairC_q }", 1, 600,
    "UNSAT expected: no plain RI core contains a committed direct load pair (model-fixes: UNSAT at but 5 on v2)", k=5)
add("x1_ctx_core_recon_pair_b6", BLOCK, "pred q { gen_core_ctx and some pairC_q }", 5, 900,
    "SAT hoped: context-minimal ReCon cores with a committed load pair exist")
add("x1b_ctx_core_recon_pairctx_b5", BLOCK,
    "pred q { gen_core_ctx and some ld1, ld2: Loads | some (ld1.outreg.rf & ld2.inaddr) and ld1 in committed and (ld2 in committed or ld2 = first_uncommitted) }",
    3, 600, "SAT hoped: a context-minimal Stage-1 core (up to 5) containing a committed LD1 -> LD2 pair (d2 needs 5)", k=5)
add("x2_ctx_minus_plain_recon_b6", BLOCK, "pred q { gen_core_ctx and not gen_core }", 20, 900,
    "SAT hoped: the shapes context minimality adds (expect concealed / ALU-between / in-flight-LD2 near misses)")
add("x3_ctx_minus_plain_stt_b5", BLOCK_STT, "pred q { gen_core_ctx and not gen_core }", 1, 900,
    "UNSAT expected: for STT (monotone protection) context minimality = plain minimality", k=5)


def main():
    with open(HERE / "RUNLIST_ctx.tsv", "w") as f:
        for r in RUN:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"wrote {len(RUN)} queries; RUNLIST_ctx.tsv")


if __name__ == "__main__":
    main()
