#!/usr/bin/env python3
# Usage: python3 mk_mf_queries.py            -> writes queries/mf/<name>.als + queries/mf/RUNLIST.tsv
"""mk_mf_queries.py -- builds every validation query of the model-fixes session (2026-11-08) as a scratch
copy of a model (never written into STAGE1_alloy/models/). Each query = model text with `run gen_lit` body
replaced by `gen_useful_litmus and q` (gen) or `q` alone (facts only), plus aux definitions appended.
RUNLIST.tsv: name, limit, timeout_s, expectation. Run each with ../runq_mf.sh (one Java at a time).
Results are recorded in wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes"."""
import re
from pathlib import Path
HERE = Path(__file__).resolve().parent
Q = HERE / "queries" / "mf"
M = HERE.parents[2] / "STAGE1_alloy" / "models"
NEEDLE = "run gen_lit {\n  gen_useful_litmus\n}"

def model(name):
    for d in (M, M / "proposed", M / "proposed_twophase"):
        if (d / name).exists():
            return (d / name).read_text()
    raise FileNotFoundError(name)

def frag(n): return (Q / n).read_text()

def build(name, base, q, gen, aux=(), scope=None):
    t = model(base)
    assert t.count(NEEDLE) == 1, (base, "needle")
    t = t.replace(NEEDLE, "run gen_lit {\n  " + ("gen_useful_litmus\n  " if gen else "") + "q\n}")
    if scope:
        t = re.sub(r"(run gen_lit \{\n  (?:gen_useful_litmus\n  )?q\n\}) for [^\n]*", r"\1 " + scope, t)
    t += f"\n\n// ---- scratch query {name} (model-fixes 2026-11-08; base {base}; {'with gen_useful_litmus' if gen else 'facts only'}) ----\n"
    for a in aux:
        t += (frag(a) if a.endswith(".alsfrag") else a) + "\n"
    t += q + "\n"
    (Q / f"{name}.als").write_text(t)

RUN = []
def add(name, base, q, gen, limit, to, expect, aux=(), scope=None):
    build(name, base, q, gen, aux, scope); RUN.append((name, limit, to, expect))

QR1A = (HERE / "queries" / "qr1a.pred").read_text()
QR1C = (HERE / "queries" / "qr1c.pred").read_text()

# ---- Recon aux: the Recon_6_v2 defense renamed *_r (for use inside an STT_6_v2 copy)
rv2 = model("Recon_6_v2.als")
rev = rv2[rv2.index("fun revealed_p["):rv2.index("// [v2-2] instance-based protection (as STT_6_v2.als) minus")]
AUX_RECON = ("// ---- aux: the NEW Recon_6_v2.als defense, renamed *_r\n" + rev.replace("revealed_p", "revealed_r") +
  "fun hpp_r[p: PTag->univ] : Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_r[p]}\n"
  "fun flag_r[p: PTag->univ] : Operand { (hpp_r[p] & speculative_xmit_p[p]) + (hpp_r[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }\n"
  "pred secure_r[p: PTag->univ] { no flag_r[p] }\npred tag_r { some flag_r[no_p] & xm.operands }\n"
  "pred gul_r {\n  not secure_r[no_p]\n  all i: (unresolved - first_uncommitted) | secure_r[RR->i]\n"
  "  secure_r[RC->first_uncommitted + RR->first_uncommitted]\n  all s: State | secure_r[RS->s]\n}\n")

# ---- SPT aux: a whole defense fold (v2 or v3) renamed with a suffix, for use inside the other copy
def spt_aux(src, sfx):
    t = model(src)
    blk = t[t.index("fun prot_set_propagation_p["):]
    blk = blk[:blk.index("\n}\n") + 3]
    lcp = t[t.index("fun last_committed_protset_p["):t.index("fun has_unresolved_brs_p")]
    out = f"// ---- aux: the {src} protection fold, renamed *_{sfx}\n"
    out += blk.replace("prot_set_propagation_p", f"prop_{sfx}")
    out += f"fun a_{sfx}[p:PTag->univ,i:Instruction,o:Operand] : Operand {{prop_{sfx}[p,i,o]}}\n"
    out += lcp.replace("last_committed_protset_p", f"lcp_{sfx}").replace("a[p,", f"a_{sfx}[p,")
    out += (f"fun flag_{sfx}[p: PTag->univ] : Operand {{ (lcp_{sfx}[p] & speculative_xmit_p[p]) + (lcp_{sfx}[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }}\n"
            f"pred secure_{sfx}[p: PTag->univ] {{ no flag_{sfx}[p] }}\npred tag_{sfx} {{ some flag_{sfx}[no_p] & xm.operands }}\n"
            f"pred gul_{sfx} {{\n  not secure_{sfx}[no_p]\n  all i: (unresolved - first_uncommitted) | secure_{sfx}[RR->i]\n"
            f"  secure_{sfx}[RC->first_uncommitted + RR->first_uncommitted]\n  all s: State | secure_{sfx}[RS->s]\n}}\n")
    return out
AUX_V2, AUX_V3 = spt_aux("SPT_6_oneLP_v2.als", "v2"), spt_aux("SPT_6_oneLP_v3.als", "v3")

def mono(a, b):   # some perturbation gen uses (or no_p) where a says secure and b does not
    return (f"pred q {{ (secure_{a}[no_p] and not secure_{b}[no_p]) or (some i: Instruction | secure_{a}[RR->i] and not secure_{b}[RR->i])\n"
            f"  or (secure_{a}[RC->first_uncommitted + RR->first_uncommitted] and not secure_{b}[RC->first_uncommitted + RR->first_uncommitted])\n"
            f"  or (some s: State | secure_{a}[RS->s] and not secure_{b}[RS->s]) }}")

# ======================= Task 1: STT_6 -> STT_6_v2 (and the QR1 pair on both v2 models) =======================
for b in ("STT_6_v2", "Recon_6_v2"):
    add(f"t1_qr1a_{b}", b + ".als", QR1A, False, 1, 600, "SAT (was UNSAT on STT_6/Recon_6)")
    add(f"t1_qr1c_{b}", b + ".als", QR1C.replace("// QR1c (control): same as QR1a but l1 reads a DIFFERENT location.\n", "// QR1c (control): same as QR1a but l1 reads a DIFFERENT location.\n"), False, 1, 600, "SAT (control)")
    add(f"t1_qr1a_{b}_gen", b + ".als", QR1A, True, 1, 900, "info (with minimality)")
    add(f"t1_qr1c_{b}_gen", b + ".als", QR1C, True, 1, 900, "info (with minimality)")
add("t1_mono_on_newfacts", "STT_6_v2.als", mono("new", "old"), False, 1, 1800, "UNSAT (old flags subset of new, every perturbation)", ("aux_stt_old.alsfrag", "aux_stt_new.alsfrag"))
add("t1_mono_on_oldfacts", "STT_6.als", mono("new", "old"), False, 1, 1800, "UNSAT", ("aux_stt_old.alsfrag", "aux_stt_new.alsfrag"))
add("t1_gained", "STT_6_v2.als", "pred q { not (gul_old and tag_old) }", True, 300, 1800, "SAT: sample to classify", ("aux_stt_old.alsfrag",))
add("t1_gained_complete", "STT_6_v2.als", "pred q { not tag_old and not r1w[no_p, xm.operands] }", False, 1, 1800, "UNSAT: every gained instance has an R-1 witness on xm",
    ("aux_stt_old.alsfrag", "aux_stt_new.alsfrag", "aux_r1w.alsfrag"))
add("t1_lost", "STT_6.als", "pred q { not (gul_new and tag_new) }", True, 300, 2400, "SAT or UNSAT: sample to classify", ("aux_stt_new.alsfrag",))
add("t1_lost_complete", "STT_6.als", "pred q { pert_any_r1 }", False, 1, 1800, "UNSAT: every lost instance is lost through an R-1 witness under a perturbation",
    ("aux_stt_old.alsfrag", "aux_stt_new.alsfrag", "aux_r1w.alsfrag"))

# ======================= Task 2: ReCon reveal (a)-(d) =======================
PAIR = "ld2 in committed and some (ld1.outreg.rf & ld2.inaddr)"
L3 = ("l3 in speculation_contract_p[no_p] and some ld1.inmem and ld1.inmem.opstate = l3.inmem.opstate and\n"
      "    l3.inmem -> l3.outreg in ddi and xm in Loads and some (l3.outreg.rf & xm.inaddr)")
NOST = "(no s: Stores | s.outmem.opstate = l3.inmem.opstate and ld1 -> s in ^spo and s -> l3 in ^spo)"
QA = f"// (a) direct committed pair LD1->LD2 reveals LD1's word; speculative re-load l3 of that word feeds xm; no store to it in between\npred q {{ some disj ld1, ld2, l3: Loads |\n    {PAIR} and\n    {L3} and\n    {NOST} }}"
def QB(extra, doc):
    return (f"// (b{doc}) as (a) but a store to the word lies spo-between LD1 and l3{extra[1]}\npred q {{ some disj ld1, ld2, l3: Loads | some s: Stores |\n    {PAIR} and\n    {L3} and\n"
            f"    s.outmem.opstate = l3.inmem.opstate and ld1 -> s in ^spo and s -> l3 in ^spo{extra[0]} }}")
QC = (f"// (c) LD1 -> ALU -> LD2 (committed): not a direct pair, so no reveal; l3 re-loads LD1's word and feeds xm\npred q {{ some disj ld1, ld2, l3: Loads | some o: Otherns + Otherxs |\n"
      f"    ld2 in committed and some (ld1.outreg.rf & o.inreg) and some (o.outreg.rf & ld2.inaddr) and\n    {L3} and\n    {NOST} }}")
add("t2a_recon", "Recon_6_v2.als", QA, False, 1, 1200, "UNSAT (revealed read is not flagged)")
add("t2a_stt_control", "STT_6_v2.als", QA, False, 1, 600, "SAT (STT has no reveal)")
add("t2a_stt_control_gen", "STT_6_v2.als", QA, True, 1, 900, "info")
add("t2b_recon_any", "Recon_6_v2.als", QB(("", ""), ""), False, 1, 600, "SAT")
add("t2b1_recon_committed_store", "Recon_6_v2.als", QB((" and s in committed and ld2 -> s in ^spo", ", the store COMMITTED after LD2 (conceal, paper 4.4.1)"), "1"), False, 1, 600, "SAT")
add("t2b2_recon_inflight_store", "Recon_6_v2.als", QB((" and s not in committed", ", the store not committed (forwards concealed data, paper 4.4.2)"), "2"), False, 1, 600, "SAT")
add("t2b3_recon_stale_store", "Recon_6_v2.als", QB((" and s -> ld2 in ^spo", ", the store between LD1 and LD2 (R-SA-2 stale reveal in gem5)"), "3"), False, 1, 600, "SAT")
add("t2b_recon_any_gen", "Recon_6_v2.als", QB(("", ""), ""), True, 1, 1200, "info")
add("t2c_recon", "Recon_6_v2.als", QC, False, 1, 600, "SAT (ALU between: no reveal)")
add("t2c_recon_gen", "Recon_6_v2.als", QC, True, 1, 1200, "info")
add("t2d1_protset_differs", "Recon_6_v2.als", "pred q { some (hpp_new[no_p] - hardware_protection_policy[no_p]) }", False, 1, 600, "SAT (QR2 analogue: was UNSAT)", ("aux_stt_new.alsfrag",))
add("t2d2_recon_only", "Recon_6_v2.als", "pred q { not gul_new }", True, 300, 1800, "SAT: Recon-useful, not STT_6_v2-useful", ("aux_stt_new.alsfrag",))
add("t2d3_stt_only", "STT_6_v2.als", "pred q { not (gul_r and tag_r) }", True, 300, 1800, "SAT: STT_6_v2-useful, not Recon-useful", (AUX_RECON,))

# ======================= Task 4: SPT v3 =======================
Q1 = (HERE / "queries" / "q1.pred").read_text()
add("t4_q1_v2", "SPT_6_oneLP_v2.als", Q1, True, 1, 900, "SAT (audit: 7 s)")
add("t4_q1_v3", "SPT_6_oneLP_v3.als", Q1, True, 1, 1800, "UNSAT hoped")
add("t4_q1_v3_nofwd", "SPT_6_oneLP_v3.als", Q1.replace("a3 not in last_committed_protset_p[no_p]", "a3 not in last_committed_protset_p[no_p] and no rf.(prod.inmem)"), True, 1, 1800, "UNSAT")
add("t4_q1_v3_facts", "SPT_6_oneLP_v3.als", Q1, False, 1, 1800, "info (facts only)")
REAL = "pred realisable { some l: Loads | some l.inmem and l.inmem in (xm.operands & leakage_function).^(~(rf + ddi)) }\n"
S1 = "pred s1shape { some l: Loads | some (l.outreg.rf & nonspeculative_xmit_p[no_p]) }\n"
add("t4_mono", "SPT_6_oneLP_v3.als", mono("v2", "v3"), False, 1, 2400, "UNSAT (v3 flags subset of v2, every perturbation)", (AUX_V2, AUX_V3))
add("t4_lost", "SPT_6_oneLP_v2.als", REAL + "pred q { realisable and not (gul_v3 and tag_v3) }", True, 300, 2400, "SAT: the S-1 false positives v3 removes", (AUX_V3,))
add("t4_lost_complete", "SPT_6_oneLP_v2.als", REAL + S1 + "pred q { realisable and (secure_v3[no_p] or not tag_v3) and not s1shape }", False, 1, 2400, "UNSAT: v3 un-flags only where a load's value is transmitted non-speculatively", (AUX_V3,))
add("t4_gained", "SPT_6_oneLP_v3.als", "pred q { not (gul_v2 and tag_v2) }", True, 100, 1800, "SAT/UNSAT: instances v3 adds", (AUX_V2,))

with open(Q / "RUNLIST.tsv", "w") as f:
    for r in RUN: f.write("\t".join(map(str, r)) + "\n")
print(len(RUN), "queries written to", Q)

# ======================= Stage-1 cores (RI-only) and the rf-fact patches (second list) =======================
RUN2 = []
def add2(name, base, q, gen, limit, to, expect, aux=(), scope=None):
    build(name, base, q, gen, aux, scope); RUN2.append((name, limit, to, expect))
CORE_TRUE = "pred q { some Instruction }"
for c in ("STT_6_v2_core_ri", "Recon_6_v2_core_ri", "SPT_6_oneLP_v3_core_ri", "STT_6_core_ri", "SPT_6_oneLP_v2_core_ri"):
    add2(f"c_{c}_b3", c + ".als", CORE_TRUE, True, 5000, 1800, "count at but 3",
         scope="for 9 but 3 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
for c in ("STT_6_v2_core_ri", "Recon_6_v2_core_ri"):
    add2(f"c_{c}_b4", c + ".als", CORE_TRUE, True, 5000, 1800, "count at but 4",
         scope="for 9 but 4 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
RI_NEW = "pred core_new { gul_new and tag_new and (all i: Instruction | secure_new[RI->i]) }\n"
RI_R = "pred core_r { gul_r and tag_r and (all i: Instruction | secure_r[RI->i]) }\n"
add2("c_recon_core_committed_load_b5", "Recon_6_v2_core_ri.als", "pred q { some Loads & committed }", True, 1, 2400, "UNSAT: no committed load in any Recon RI core, so no reveal",
     scope="for 9 but 5 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
add2("c_recon_not_stt_core_b5", "Recon_6_v2_core_ri.als", RI_NEW + "pred q { not core_new }", True, 1, 2400, "UNSAT: every Recon RI core is an STT_6_v2 RI core",
     ("aux_stt_new.alsfrag",), scope="for 9 but 5 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
add2("c_stt_not_recon_core_b5", "STT_6_v2_core_ri.als", RI_R + "pred q { not core_r }", True, 1, 2400, "UNSAT: every STT_6_v2 RI core is a Recon RI core",
     (AUX_RECON,), scope="for 9 but 5 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
RFP = HERE.parents[2] / "results" / "model_fixes_20261108" / "rf_patched"
for f in sorted(RFP.glob("*.als")):
    RUN2.append(("RFP:" + str(f), 3, 600, "SAT (patched copy parses and has instances)"))
with open(Q / "RUNLIST2.tsv", "w") as f:
    for r in RUN2: f.write("\t".join(map(str, r)) + "\n")
print(len(RUN2), "second-list entries")
