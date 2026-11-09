#!/usr/bin/env python3
"""mk_queries.py -- builds the Alloy validation queries for the ReCon ultimate drafts (recon agent, 2026-11-09).
Each query = a copy of a model with its `run gen_lit` body replaced by `q` (facts only) or `gen_useful_litmus` + `q`
(with minimality), plus aux definitions appended. Writes q/<name>.als and RUNLIST.tsv (name, limit, timeout,
expectation). Run with ./run_queries.sh RUNLIST.tsv [regex] (one Java at a time; set ALLOY_LOCK to the shared lock dir).
Models are only read. Results: runs.log next to this script; written up in the recon agent's final report.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ULT = HERE.parents[1]
MODELS = ULT.parents[1]
Q = HERE / "q"
Q.mkdir(exist_ok=True)
NEEDLE = "run gen_lit {\n  gen_useful_litmus\n}"


def model(name):
    for d in (ULT, MODELS, MODELS / "proposed", MODELS / "proposed_twophase"):
        if (d / name).exists():
            return (d / name).read_text()
    raise FileNotFoundError(name)


# ---- shape vocabulary: raw relations at no_p, identical text in every base -------------------------------
SHAPES = """
// ---- recon agent shape vocabulary (2026-11-09): plain relations, the unperturbed program ----
fun pairC_q : Instruction -> Instruction { {ld1, ld2: Loads | ld2 in committed and some (ld1.outreg.rf & ld2.inaddr)} }
fun pairU_q : Instruction -> Instruction { {ld1, ld2: Loads | ld2 not in committed and some (ld1.outreg.rf & ld2.inaddr)} }
pred rereads_q[l3, ld1: Instruction] { some l3.inmem and some ld1.inmem and l3.inmem.opstate = ld1.inmem.opstate and ld1 -> l3 in ^spo }
pred feeds_ldxm_q[l3: Instruction] { xm in Loads and l3.inmem -> l3.outreg in ddi and some (l3.outreg.rf & xm.inaddr) }
pred st_between_q[w: State, a, b: Instruction, S: set Instruction] { some s: Stores & S | s.outmem.opstate = w and a -> s in ^spo and s -> b in ^spo }
pred no_st_to_q[w: State] { no s: Stores | s.outmem.opstate = w }
pred spec_q[l: Instruction] { l in speculation_contract_p[no_p] }
"""

# ---- defenses as renamed aux, so two semantics can be compared inside one file ---------------------------
GUL = """pred gul_{s} {{
  not secure_{s}[no_p]
  all i: (unresolved - first_uncommitted) | secure_{s}[RR->i]
  secure_{s}[RC->first_uncommitted + RR->first_uncommitted]
  all s: State | secure_{s}[RS->s]
}}
pred secure_{s}[p: PTag->univ] {{ no flag_{s}[p] }}
pred tag_{s} {{ some flag_{s}[no_p] & xm.operands }}
"""
AUX_RECON_U = """
// ---- aux: the Recon_6_u.als defense (STT_6_u seed minus [u-7]/[u-8] reveal), renamed *_r ----
fun ld1_r[p: PTag->univ] : Instruction { { ld1: Loads & i_p[p] | some ld2: Loads & committed_p[p] | some (ld1.outreg.(rf_p[p]) & ld2.inaddr) } }
fun conc_r[p: PTag->univ] : Instruction {Stores & i_p[p] & (resolved_p[p] + committed_p[p])}
fun rev_r[p: PTag->univ] : Operand {
	{ m: Loads.inmem & o_p[p] | some ld1: ld1_r[p] |
		m.opstate in (ld1.inmem & o_p[p]).opstate and ld1 -> m.(~inmem) in ^(spo_p[p])
		and (no s: conc_r[p] | m.opstate in (s.outmem & o_p[p]).opstate and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
}
fun hpp_r[p: PTag->univ] : Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - rev_r[p]}
fun flag_r[p: PTag->univ] : Operand { (hpp_r[p] & speculative_xmit_p[p]) + (hpp_r[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
""" + GUL.format(s="r")
AUX_RECON_ANYCONCEAL = """
// ---- aux: Recon_6_u with the v2 conceal rule (ANY store between conceals, no [u-8] exception), renamed *_v ----
fun ld1_v[p: PTag->univ] : Instruction { { ld1: Loads & i_p[p] | some ld2: Loads & committed_p[p] | some (ld1.outreg.(rf_p[p]) & ld2.inaddr) } }
fun rev_v[p: PTag->univ] : Operand {
	{ m: Loads.inmem & o_p[p] | some ld1: ld1_v[p] |
		m.opstate in (ld1.inmem & o_p[p]).opstate and ld1 -> m.(~inmem) in ^(spo_p[p])
		and (no s: Stores & i_p[p] | m.opstate in (s.outmem & o_p[p]).opstate and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
}
fun hpp_v[p: PTag->univ] : Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - rev_v[p]}
fun flag_v[p: PTag->univ] : Operand { (hpp_v[p] & speculative_xmit_p[p]) + (hpp_v[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
""" + GUL.format(s="v")
AUX_STT_U = """
// ---- aux: the STT_6_u.als defense (instance-based seed, identity propagation), renamed *_s ----
fun hpp_s[p: PTag->univ] : Operand {(Loads & speculation_contract_p[p]).inmem & o_p[p]}
fun flag_s[p: PTag->univ] : Operand { (hpp_s[p] & speculative_xmit_p[p]) + (hpp_s[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
""" + GUL.format(s="s")
AUX_RECON_OLD = """
// ---- aux: the OLD Recon_6.als defense (State-typed location fold + the no-op reveal, Recon_6.als:326-334), renamed *_o ----
fun hpp_o[p: PTag->univ] : State {Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p]))}
fun prop_o[p:PTag->univ,i:Instruction,s:State] : State { s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate }
fun lcp_o[p: PTag->univ] : State {
	prop_o[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_o[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_o[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_o[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_o[p,f[p].(spo_p[p]).(spo_p[p]),
	prop_o[p,f[p].(spo_p[p]),
	prop_o[p,f[p],hpp_o[p]]]]]]]]
}
fun flag_o[p: PTag->univ] : Operand { (lcp_o[p].(~opstate) & speculative_xmit_p[p]) + (lcp_o[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p]) }
""" + GUL.format(s="o")
FLAG_BASE = """
// ---- aux: the base model's own flagged set (Operand-typed skeleton) ----
fun flag_n[p: PTag->univ] : Operand { (last_committed_protset_p[p] & speculative_xmit_p[p]) + (last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
"""
R1W = """
// ---- aux: R-1 witness on xm: a non-speculative load and a speculative load read the same word, and the
// speculative read reaches a leak operand of xm over rf+ddi ----
pred r1w_q { some l1, l3: Loads | l1 not in speculation_contract_p[no_p] and l3 in speculation_contract_p[no_p]
  and some l3.inmem and l3.inmem.opstate in l1.inmem.opstate
  and some (l3.inmem.(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands) }
"""

RUN = []


def add(name, base, q, gen, limit, to, expect, aux=(), scope=None):
    t = model(base)
    assert t.count(NEEDLE) == 1, (base, "needle")
    t = t.replace(NEEDLE, "run gen_lit {\n  " + ("gen_useful_litmus\n  " if gen else "") + "q\n}")
    if scope:
        t, n = re.subn(r"(run gen_lit \{\n  (?:gen_useful_litmus\n  )?q\n\}) for [^\n]*", r"\1 " + scope, t)
        assert n == 1, (name, "scope")
    t += f"\n\n// ---- recon agent query {name} (2026-11-09; base {base}; {'with gen_useful_litmus' if gen else 'facts only'}) ----\n"
    t += SHAPES
    for a in aux:
        t += a + "\n"
    t += q.strip() + "\n"
    (Q / f"{name}.als").write_text(t)
    RUN.append((name, limit, to, expect))


R6U, S6U = "Recon_6_u.als", "STT_6_u.als"

# ---------------------------------------------------------------- (A) facts-only shape semantics (no minimality)
QA = """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and no_st_to_q[l3.inmem.opstate] and feeds_ldxm_q[l3] and no rf.(l3.inmem) }"""
add("fa_true_reveal", R6U, QA, False, 1, 300, "UNSAT: a committed direct pair reveals the word, xm fed only by the re-load is not flagged")
add("fa_true_reveal_STTu", S6U, QA, False, 1, 300, "SAT: STT flags the same shape (control)")
add("fb1_conceal_committed_store", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and st_between_q[l3.inmem.opstate, ld2, l3, committed] and feeds_ldxm_q[l3] }""", False, 1, 300,
    "SAT: a committed store after LD2 conceals (sec. 4.4.1)")
add("fb2_conceal_inflight_store", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and st_between_q[l3.inmem.opstate, ld2, l3, uncommitted & resolved] and feeds_ldxm_q[l3] }""", False, 1, 300,
    "SAT: an in-flight resolved store conceals (sec. 4.4.2)")
add("fb3_conceal_between_pair", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and st_between_q[l3.inmem.opstate, ld1, ld2, Instruction] and feeds_ldxm_q[l3] }""", False, 1, 300,
    "SAT: a store between LD1 and LD2 conceals (sec. 4.4; the R-SA-2 stale-reveal test)")
add("fb4_unresolved_store_no_conceal", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and st_between_q[l3.inmem.opstate, ld2, l3, unresolved]
  and (no s: Stores & resolved | s.outmem.opstate = l3.inmem.opstate)
  and feeds_ldxm_q[l3] and no rf.(l3.inmem) }""", False, 1, 300,
    "UNSAT: [u-8] an unresolved-address store does not conceal (the re-load may bypass it)")
add("fb4_unresolved_store_v2rule", S6U, """pred q { tag_v and not tag_r and some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and st_between_q[l3.inmem.opstate, ld2, l3, unresolved] and feeds_ldxm_q[l3] }""", False, 1, 300,
    "SAT: the Recon_6_v2 rule (any store conceals) flags this shape, [u-8] does not (facts-only difference)",
    aux=(AUX_RECON_ANYCONCEAL, AUX_RECON_U))
add("fc_alu_between_pair", R6U, """pred q { some ld1, ld2, l3: Loads, o: Otherns + Otherxs |
  some (ld1.outreg.rf & o.inreg) and some (o.outreg.rf & ld2.inaddr) and ld2 in committed
  and (no ld0: pairC_q.univ | rereads_q[l3, ld0])
  and spec_q[l3] and rereads_q[l3, ld1] and no_st_to_q[l3.inmem.opstate] and feeds_ldxm_q[l3] and no rf.(l3.inmem) }""",
    False, 1, 300, "SAT: LD1 -> ALU -> LD2 is no direct pair, no reveal (sec. 4.3)")
add("fd2_ld2_inflight", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairU_q and ld1 in committed and l3 != ld2 and (no ld0: pairC_q.univ | rereads_q[l3, ld0])
  and spec_q[l3] and rereads_q[l3, ld1] and no_st_to_q[l3.inmem.opstate] and feeds_ldxm_q[l3] and no rf.(l3.inmem) }""",
    False, 1, 300, "SAT: no reveal before LD2 commits (sec. 4.1, 5.1)")
QR1A = """pred q { some disj l1, l3: Loads |
  l1 not in speculation_contract_p[no_p] and l3 in speculation_contract_p[no_p] and
  some l1.inmem and l1.inmem.opstate = l3.inmem.opstate and
  no (l1.outreg.rf & Loads.inaddr) and no rf.(l3.inmem) and l3.inmem -> l3.outreg in ddi and
  xm in Loads and some (l3.outreg.rf & xm.inaddr) }"""
add("fr1_qr1a", R6U, QR1A, False, 1, 300, "SAT: audit R-1 fixed (Recon_6: UNSAT)")
add("fr1_qr1a_old", "Recon_6.als", QR1A, False, 1, 300, "UNSAT: reproduces audit QR1a on today's Recon_6 (with the rf fact)")
OTB_FULL = """pred q { some disj br_r, br_u: Branchxs + Branchns, disj l_inj, l_base: Loads, o: Otherns + Otherxs |
  br_r in resolved & uncommitted and br_u in unresolved
  and br_r -> l_inj in ^spo and l_inj -> br_u in ^spo and br_u -> l_base in ^spo
  and some l_inj.inmem and some l_base.inmem and l_inj.inmem -> l_inj.outreg in ddi and l_base.inmem -> l_base.outreg in ddi
  and some (l_inj.outreg.rf & o.inreg) and some (l_base.outreg.rf & o.inreg) and o.inreg -> o.outreg in ddi
  and xm in Loads and some (o.outreg.rf & xm.inaddr) }"""
add("fotb_full", R6U, OTB_FULL, False, 1, 300,
    "SAT: the full getOldestTaint gadget (older load under an early-resolved branch + speculative load -> ALU -> xm) is flagged")

# ---------------------------------------------------------------- (B) completeness vs the old Recon_6 at no_p (facts only)
add("fx_old_sub_new", "Recon_6.als", "pred q { some flag_o[no_p] - flag_r[no_p] }", False, 1, 900,
    "UNSAT: every operand the old Recon_6 flags, Recon_6_u flags too (old = location fold + no-op reveal)",
    aux=(AUX_RECON_OLD, AUX_RECON_U))
add("fx_new_minus_old_not_r1", R6U, "pred q { some (flag_n[no_p] - flag_o[no_p]) & xm.operands and not r1w_q }", False, 1, 900,
    "UNSAT: every transmitter Recon_6_u newly flags is an R-1 witness", aux=(AUX_RECON_OLD, FLAG_BASE, R1W))

# ---------------------------------------------------------------- (C) generation (with minimality)
add("g0_gen_sat", R6U, "pred q { }", True, 20, 600, "SAT at exactly 6 (first 20 instances)")
add("g1_d2_gen", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairU_q and ld2 = first_uncommitted and spec_q[l3] and rereads_q[l3, ld1] }""",
    True, 3, 600, "SAT: in-flight-LD2 tests are generated (ReCon-only)")
add("g2_r1_gen", R6U, QR1A, True, 3, 600, "SAT: R-1 shapes are generated")
add("g3_conceal_gen", R6U, """pred q { some ld1, ld2, l3: Loads | ld1 -> ld2 in pairC_q and spec_q[l3] and rereads_q[l3, ld1]
  and st_between_q[l3.inmem.opstate, ld1, l3, Instruction] }""", True, 3, 600, "SAT: concealed-reveal tests are generated")
add("g4_alu_pair_gen", R6U, """pred q { some ld1, ld2, l3: Loads, o: Otherns + Otherxs |
  some (ld1.outreg.rf & o.inreg) and some (o.outreg.rf & ld2.inaddr) and ld2 in committed
  and spec_q[l3] and rereads_q[l3, ld1] }""", True, 3, 600, "SAT: LD1 -> ALU -> LD2 near-miss tests are generated")
OTB_PRE = """pred q { some l: Loads, o: Otherns + Otherxs | spec_q[l] and some (l.outreg.rf & o.inreg)
  and (o.inreg & l.outreg.rf) -> o.outreg in ddi and xm in Loads and some (o.outreg.rf & xm.inaddr) and l.inmem -> l.outreg in ddi }"""
add("g5_otb_precursor_gen", R6U, OTB_PRE, True, 3, 600, "SAT: an ALU on the transmitter's address path (the OTB hook point)")
add("g6_otb_precursor_rb_gen", R6U, OTB_PRE.replace("pred q { some l: Loads,",
    "pred q { some rb: (Branchxs + Branchns) & resolved & uncommitted | rb -> (unresolved & (Branchxs + Branchns)) in ^spo and some l: Loads,"),
    True, 3, 600, "?: the OTB hook point plus an older uncommitted resolved branch (fanout_v2.otb eligibility)")
add("g7_otb_full_gen", R6U, OTB_FULL, True, 1, 600, "?: the full OTB gadget under minimality (expect UNSAT: the early branch and the second load are not necessary)")
add("g8_true_reveal_gen_STTu", S6U, QA, True, 1, 600, "SAT: STT generates the true-reveal shape (control for fa_true_reveal)")

PIN = """// ReCon reveal-context pin (a candidate Stage-1.5 / dedicated-corpus forcing predicate, DECIDE B2):
// some load pair (committed, in flight at the boundary, or through one ALU) whose LD1 word a speculative load re-reads
pred q { some ld1, l3: Loads | spec_q[l3] and rereads_q[l3, ld1] and (
    (some ld2: Loads | ld1 -> ld2 in pairC_q + pairU_q and (ld2 in committed or ld2 = first_uncommitted))
    or (some ld2: Loads & committed, o: Otherns + Otherxs | some (ld1.outreg.rf & o.inreg) and some (o.outreg.rf & ld2.inaddr))) }"""
add("g9_reveal_ctx_pin_gen", R6U, PIN, True, 200, 900, "SAT: sample of a ReCon reveal-context corpus; classify with show_inst.py --summary")

add("g10_unresolved_store_gen", R6U, "pred q { some Stores & unresolved }", True, 1, 300,
    "UNSAT expected: minimality never keeps an unresolved store in the spectre flavor, so [u-8] changes no generated instance")

# ---------------------------------------------------------------- (D) differentials (generation level, capped samples)
add("d1_recon_only", R6U, "pred q { not (gul_s and tag_s) }", True, 100, 600, "SAT: Recon_6_u-useful, not STT_6_u-useful (expect the d2 shape)", aux=(AUX_STT_U,))
add("d2_stt_only", S6U, "pred q { not (gul_r and tag_r) }", True, 100, 600, "SAT: STT_6_u-useful, not Recon_6_u-useful (expect true reveals)", aux=(AUX_RECON_U,))
add("d3_gained_vs_old", R6U, "pred q { not (gul_o and tag_o) }", True, 100, 600, "SAT: new vs old Recon_6 (expect R-1 and d2 shapes)", aux=(AUX_RECON_OLD,))
add("d4_lost_vs_old", "Recon_6.als", "pred q { not (gul_r and tag_r) }", True, 50, 900, "0 expected: old Recon_6-useful, not Recon_6_u-useful", aux=(AUX_RECON_U,))
add("d5_u8_vs_v2rule_gen", R6U, "pred q { not (gul_v and tag_v) }", True, 1, 900, "UNSAT expected: [u-8] changes no generated instance (proof in the report)", aux=(AUX_RECON_ANYCONCEAL,))

# ---------------------------------------------------------------- (E) Stage-1 core, STL flavor
add("c1_core_b3", "Recon_6_u_core_ri.als", "pred q { }", True, 1000, 900, "count at but 3 (Recon_6_v2_core_ri: 129)", scope="for 9 but 3 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
add("c2_core_b3_STTu", "STT_6_u_core_ri.als", "pred q { }", True, 1000, 900, "count at but 3 (control)", scope="for 9 but 3 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool")
add("s1_stl_gen_sat", "Recon_6_u_stl.als", "pred q { }", True, 20, 600, "SAT at exactly 6")
STL_BYP = """pred q { some ld1, ld2, l: Loads, s: Stores | ld1 -> ld2 in pairC_q and s in unresolved
  and ld2 -> s in ^spo and s -> l in ^spo and l in uncommitted and rereads_q[l, ld1] and s.outmem.opstate = l.inmem.opstate
  and (no s2: Stores & resolved | s2.outmem.opstate = l.inmem.opstate and ld1 -> s2 in ^spo and s2 -> l in ^spo)
  and feeds_ldxm_q[l] and no rf.(l.inmem) }"""
add("s2_stl_bypass_revealed", "Recon_6_u_stl.als", STL_BYP, False, 1, 300, "UNSAT: a bypassing load that reads the revealed pre-store value is not flagged (sec. 4.5.2 Table 1 case 1)")
add("s2_stl_bypass_revealed_STTu", "STT_6_u_stl.als", STL_BYP, False, 1, 300, "SAT: STT flags it (control)")
add("s3_stl_bypass_concealed", "Recon_6_u_stl.als", """pred q { some ld1, ld2, l: Loads, s, s1: Stores | ld1 -> ld2 in pairC_q and s in unresolved and s1 in committed
  and ld2 -> s1 in ^spo and s1 -> s in ^spo and s -> l in ^spo and l in uncommitted and rereads_q[l, ld1]
  and s.outmem.opstate = l.inmem.opstate and s1.outmem.opstate = l.inmem.opstate and feeds_ldxm_q[l] }""", False, 1, 300,
    "SAT: a committed store between the pair and the bypassed store conceals the stale value")


def main():
    with open(HERE / "RUNLIST.tsv", "w") as f:
        for r in RUN:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"wrote {len(RUN)} queries to {Q} and RUNLIST.tsv")


if __name__ == "__main__":
    main()
