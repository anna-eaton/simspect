#!/usr/bin/env python3
"""make_queries_stt.py -- builds the STT ultimate-model validation queries (STT agent, 2026-11-09).

Each query file = a scratch COPY of a model (never written into STAGE1_alloy/models outside
proposed/ultimate/queries/stt/) with its `run gen_lit` command replaced by several named commands
(../a6RunAll runs every command; runq_stt.sh takes the Mac-wide Alloy lock). Files:
  q_sem.als   base STT_6_u.als, fact tag_xm demoted to a pred (facts-only queries range over every
              6-instruction program): YRoT equivalence (Y*), hand-built unprotect shapes (U*), mono (M*)
  q_gen.als   base STT_6_u.als as is (tag_xm stays a fact): shapes under minimality, gained/lost (D*)
  q_lostc.als base STT_6_u.als: the lost-completeness query (long; run last)
  q_stl.als   base STT_6_u_stl.als (tag_xm demoted): STL flavor sanity + the R-1 analog for STL
  q_core.als  counts of the RI cores at small scopes (u, u_stl, and the approved STT_6_stl_core for scale)
Expected results are in each command's label comment and in EXPECT below; runs.log records actuals.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ULT = HERE.parents[1]
MODELS = ULT.parents[1]
NEEDLE_RE = re.compile(r"run gen_lit \{\n  gen_useful_litmus\n\} for [^\n]*\n")
SCOPE6 = "for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"
TAGXM = "fact tag_xm { \n"

# ---------------------------------------------------------------- aux definitions
AUX_COMMON = r"""
// ======== aux (STT agent 2026-11-09) ========
fun Brs : Instruction { Branchxs + Branchns }
// the model's flagged set (= what secure_speculation_scheme_p forbids)
fun m_flag[p: PTag->univ] : Operand { (last_committed_protset_p[p] & speculative_xmit_p[p]) + (last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
// ---- independent YRoT reference semantics (paper Sec. 6.2 + Sec. 7.1): the roots of an operand x are
// the loads whose OUTPUT reaches x over rf and the ddi of NON-load instructions (a load's output taint is
// decided by the load alone, p6: "If a load is unsafe, its output is always tainted"); x is tainted iff
// some root is unsafe (= its youngest root has not reached the VP, since VPs are reached in order, p5).
fun y_flow[p: PTag->univ] : Operand -> Operand { rf_p[p] + ((Instruction - Loads).operands <: ddi_p[p]) }
// x has an unsafe root  <=>  x is reachable over y_flow from the output of some unsafe load (closed form, no comprehension)
fun y_flag[p: PTag->univ] : Operand { ((Loads & i_p[p] & speculation_contract_p[p]).outreg & o_p[p]).*(y_flow[p]) & speculative_xmit_p[p] }
// ---- the OLD STT_6.als defense (location-based fold, STT_6.als:326-332), renamed *_old
fun hpp_old : State {Mem_s}
fun prop_old[p:PTag->univ,i:Instruction,s:State] : State { s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate }
fun a_old[p:PTag->univ,i:Instruction,s:State] : State { prop_old[p,i,s] }
fun lcp_old[p: PTag->univ] : State {
	a_old[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	a_old[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	a_old[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	a_old[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
	a_old[p,f[p].(spo_p[p]).(spo_p[p]),
	a_old[p,f[p].(spo_p[p]),
	a_old[p,f[p],hpp_old]]]]]]]
}
fun flag_old[p: PTag->univ] : Operand { (lcp_old[p].(~opstate) & speculative_xmit_p[p]) + (lcp_old[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p]) }
pred secure_old[p: PTag->univ] { no flag_old[p] }
pred tag_old { some flag_old[no_p] & xm.operands }
pred gul_old {
  not secure_old[no_p]
  all i: (unresolved - first_uncommitted) | secure_old[RR->i]
  secure_old[RC->first_uncommitted + RR->first_uncommitted]
  all s: State | secure_old[RS->s]
}
// ---- R-1 witness under perturbation p (model-fixes aux_r1w.alsfrag, verbatim logic): a non-speculative
// load l1 and a speculative load l3 read the same Mem_s, and l3's read reaches a speculative transmitter
// operand in xs.
pred r1w[p: PTag->univ, xs: set Operand] { some l1, l3: Loads & i_p[p] |
  l1 in no_unresolved_brs_bf_or_is_p[p] and l3 in speculation_contract_p[p] and
  some (l3.inmem & o_p[p]) and (l3.inmem & o_p[p]).opstate in l1.inmem.opstate and
  some ((l3.inmem & o_p[p]).(^(op_edges_p[p])) & speculative_xmit_p[p] & xs) }
"""

AUX_SHAPES = r"""
// ---- hand-built shapes (the unprotect behaviour to check against the paper) ----
// U1 (audit R-1): committed l1 reads word A; unresolved branch b; speculative re-load l2 of A feeds xm's address.
pred u1_shape { some disj l1, b, l2, t: Instruction |
  l1 in Loads & committed and b in Brs & unresolved and l2 in Loads and t in Loads & xm
  and b in l1.^spo and l2 in b.^spo and t in l2.^spo
  and some l1.inmem and some l2.inmem and l2.inmem.opstate = l1.inmem.opstate
  and no rf.(l2.inmem) and (l2.inmem -> l2.outreg) in ddi   // as model-fixes QR1a: l2 reads memory, no store forwards into it
  and some (l2.outreg.rf & t.inaddr) }
// U2: untaint at the VP in a NON-minimal snapshot: b0 resolved but uncommitted, l after b0 with no unresolved
// branch before it (so l is SAFE although uncommitted), then unresolved b1, then xm whose address is l's output.
pred u2_shape[after_b1: Int] { some disj b0, l, b1, t: Instruction |
  b0 in Brs & resolved & uncommitted and l in Loads & uncommitted and b1 in Brs & unresolved and t in Loads & xm
  and l in b0.^spo and t in b1.^spo and t in l.^spo
  and (after_b1 = 1 => l in b1.^spo else (b1 in l.^spo and no (Brs & unresolved & l.^(~spo))))
  and some l.inmem and some (l.outreg.rf & t.inaddr) }
// U3: union / youngest root (the OTB shape): an ALU x merges a SAFE load ls (after resolved b0, before
// unresolved b1) and an UNSAFE load lp (after b1); x feeds xm's address.
pred u3_shape[with_lp: Int] { some disj b0, ls, b1, lp, x, t: Instruction |
  b0 in Brs & resolved & uncommitted and ls in Loads & uncommitted and b1 in Brs & unresolved
  and lp in Loads and x in Otherns + Otherxs and t in Loads & xm
  and ls in b0.^spo and b1 in ls.^spo and lp in b1.^spo and x in lp.^spo and t in x.^spo
  and no (Brs & unresolved & ls.^(~spo))
  and some ls.inmem and some lp.inmem and some (ls.outreg.rf & x.inreg) and some (x.outreg.rf & t.inaddr)
  and (with_lp = 1 => some (lp.outreg.rf & x.inreg) else x.inreg.(~rf) in ls.outreg) }
// U4: store-to-load forwarding from a COMMITTED store with no data source: the forwarded value is
// still tainted because the load is unsafe (paper p6).
pred u4_shape { some disj st, b, l, t: Instruction |
  st in Stores & committed and b in Brs & unresolved and l in Loads and t in Loads & xm
  and b in st.^spo and l in b.^spo and t in l.^spo
  and some (st.outmem.rf & l.inmem) and some (l.outreg.rf & t.inaddr) and no st.inreg.(~rf) }
// U5: an ALU after the branch whose inputs come only from committed instructions (or nowhere) feeds xm.
pred u5_shape { some disj b, x, t: Instruction |
  b in Brs & unresolved and x in Otherns + Otherxs and t in Loads & xm and x in b.^spo and t in x.^spo
  and some (x.outreg.rf & t.inaddr) and x.inreg.(~rf) in committed.outs and t.inaddr.(~rf) in x.outreg }
// U7: a transmitting branch whose predicate comes from an unsafe load (spec=1) or only from committed
// instructions (spec=0).
pred u7_shape[spec: Int] { some disj b, l, bx: Instruction |
  b in Brs & unresolved and l in Loads and bx in Branchxs & xm and bx in b.^spo and bx in l.^spo
  and some l.inmem and some (l.outreg.rf & bx.inreg)
  and (spec = 1 => l in b.^spo else (l in committed and bx.inreg.(~rf) in committed.outs)) }
// U8: a store whose ADDRESS is tainted; nothing else transmits.
pred u8_shape { some disj b, l, st: Instruction |
  b in Brs & unresolved and l in Loads and st in Stores and l in b.^spo and st in l.^spo
  and some l.inmem and some (l.outreg.rf & st.inaddr) }
// lost witness (hand-built from the argument in the report): committed l1 reads A; b; l2 reads M; st writes
// l2's value to A; l4 re-reads A (forwarded); xm = ld [l4]. Old STT_6: A is unprotected (l1), so M looks
// necessary; STT_6_u: l4's own read is a source, so M/l2/st are not necessary.
pred lost_shape { some disj l1, b, l2, st, l4, t: Instruction |
  l1 in Loads & committed and b in Branchns & unresolved and l2 in Loads and st in Stores and l4 in Loads and t in Loads & xm
  and b in l1.spo and l2 in b.spo and st in l2.spo and l4 in st.spo and t in l4.spo
  and some l1.inmem and l4.inmem.opstate = l1.inmem.opstate and st.outmem.opstate = l1.inmem.opstate
  and l2.inmem.opstate != l1.inmem.opstate
  and some (l2.outreg.rf & st.inreg) and some (st.outmem.rf & l4.inmem) and some (l4.outreg.rf & t.inaddr) }
"""


def base(name, demote_tag):
    t = (ULT / name).read_text() if (ULT / name).exists() else (MODELS / name).read_text()
    assert len(NEEDLE_RE.findall(t)) == 1, name
    t = NEEDLE_RE.sub("", t)
    if demote_tag:
        assert t.count(TAGXM) == 1
        t = t.replace(TAGXM, "pred tag_xm_demoted { \n")   # facts-only queries range over every program
    return t


def write(fname, text, cmds):
    out = text + AUX_COMMON + AUX_SHAPES + "\n// ======== commands ========\n"
    for label, body, scope in cmds:
        out += f"run {label} {{ {body} }} {scope}\n"
    (HERE / fname).write_text(out)
    print("wrote", HERE / fname, len(cmds), "commands")


S6 = SCOPE6
# ---------------------------------------------------------------- q_sem (facts only, tag_xm demoted)
SEM = [
    ("sanity_facts", "some xm", S6),
    # YRoT equivalence
    ("Y1_model_flags_only_yrot_taint__UNSAT", "some (m_flag[no_p] - y_flag[no_p])", S6),
    ("Y2_yrot_taint_flagged_when_every_unsafe_load_reads_mem__UNSAT",
     "(all l: Loads & speculation_contract_p[no_p] | some l.inmem) and some (y_flag[no_p] - m_flag[no_p])", S6),
    ("Y3_gap_unsafe_load_without_Inmem__SAT", "some (y_flag[no_p] - m_flag[no_p])", S6),
    ("Y1_RS_all_perturbations__UNSAT", "some s: State | some (m_flag[RS->s] - y_flag[RS->s])", S6),
    # monotonicity old STT_6 -> u (every operand old flags, u flags), per perturbation family
    ("M0_old_subset_u_nop__UNSAT", "some (flag_old[no_p] - m_flag[no_p])", S6),
    ("M1_old_subset_u_RS__UNSAT", "some s: State | some (flag_old[RS->s] - m_flag[RS->s])", S6),
    ("M2_old_subset_u_RR__UNSAT", "some i: Instruction | some (flag_old[RR->i] - m_flag[RR->i])", S6),
    ("M3_old_subset_u_RCRR__UNSAT", "some (flag_old[RC->first_uncommitted + RR->first_uncommitted] - m_flag[RC->first_uncommitted + RR->first_uncommitted])", S6),
    # hand-built unprotect shapes
    ("U1_R1_reload_flagged_u__SAT", "u1_shape and some (m_flag[no_p] & xm.operands)", S6),
    ("U1_R1_reload_flagged_old__UNSAT", "u1_shape and some (flag_old[no_p] & xm.operands)", S6),
    ("U2_safe_uncommitted_load_untainted__UNSAT", "u2_shape[0] and some (m_flag[no_p] & xm.inaddr)", S6),
    ("U2c_same_load_after_b1_tainted__SAT", "u2_shape[1] and some (m_flag[no_p] & xm.inaddr)", S6),
    ("U3_union_safe_plus_unsafe_tainted__SAT", "u3_shape[1] and some (m_flag[no_p] & xm.inaddr)", S6),
    ("U3b_safe_root_only_untainted__UNSAT", "u3_shape[0] and some (m_flag[no_p] & xm.inaddr)", S6),
    ("U4_forward_from_committed_store_tainted__SAT", "u4_shape and some (m_flag[no_p] & xm.inaddr)", S6),
    ("U5_alu_on_committed_values_untainted__UNSAT", "u5_shape and some (m_flag[no_p] & xm.inaddr)", S6),
    ("U7_brx_unsafe_predicate_flagged__SAT", "u7_shape[1] and some (m_flag[no_p] & xm.inreg)", S6),
    ("U7b_brx_committed_predicate_unflagged__UNSAT", "u7_shape[0] and some (m_flag[no_p] & xm.inreg)", S6),
    ("U8_tainted_store_address_is_not_a_leak__SAT", "u8_shape and secure_speculation_scheme_p[no_p]", S6),
    # non-vacuity controls for every UNSAT shape query above (the shape itself must exist)
    ("X2_u2_shape0_exists__SAT", "u2_shape[0]", S6),
    ("X3_u3_shape0_exists__SAT", "u3_shape[0]", S6),
    ("X5_u5_shape_exists__SAT", "u5_shape", S6),
    ("X7_u7_shape0_exists__SAT", "u7_shape[0]", S6),
]
# ---------------------------------------------------------------- q_gen (tag_xm is a fact)
GEN = [
    ("gen_lit_u__SAT", "gen_useful_litmus", S6),
    ("U1g_R1_reload_generated__SAT", "gen_useful_litmus and u1_shape", S6),
    ("U4g_forward_from_committed_store_generated__info", "gen_useful_litmus and u4_shape", S6),
    ("U7g_brx_generated__SAT", "gen_useful_litmus and u7_shape[1]", S6),
    # structure lemmas of the flat STT generator (explain why S4 / A3c / OTB contexts never appear)
    ("L1_nonbranch_unresolved__UNSAT", "gen_useful_litmus and some (unresolved - Brs)", S6),
    ("L2_more_than_one_source__UNSAT", "gen_useful_litmus and unresolved != first_uncommitted", S6),
    ("L3_xm_branch_unresolved__UNSAT", "gen_useful_litmus and some (xm & Branchxs & unresolved)", S6),
    ("L4_committed_load_exists__SAT", "gen_useful_litmus and some (committed & Loads)", S6),
    ("D1_gained_without_R1_on_xm__UNSAT", "gen_useful_litmus and not (gul_old and tag_old) and not r1w[no_p, xm.operands]", S6),
    ("D2w_lost_handbuilt__SAT", "lost_shape and gul_old and tag_old and not gen_useful_litmus", S6),
    # (unpinned D2 'lost any' dropped for economy: model-fixes t1_lost found none in 1500 s; D2w pins one)
]
LOSTC = [
    ("D2c_lost_without_RS_R1_artifact__UNSAT",
     "gul_old and tag_old and not gen_useful_litmus and not (some s: State | secure_old[RS->s] and not secure_speculation_scheme_p[RS->s] and r1w[RS->s, Operand])", S6),
]
# ---------------------------------------------------------------- q_stl (STL flavor, tag_xm demoted)
AUX_STL = r"""
// old STT_6_stl.als defense (location-based; STT_6_stl.als:369-371) renamed *_ostl
fun nus_ostl[p: PTag->univ] : Instruction { i_p[p] - u_store_shadow_p[p] }
fun prop_ostl[p:PTag->univ,i:Instruction,s:State] : State { s - (Loads & nus_ostl[p] & i).inmem.opstate }
fun lcp_ostl[p: PTag->univ] : State {
	prop_ostl[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_ostl[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_ostl[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_ostl[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_ostl[p,f[p].(spo_p[p]).(spo_p[p]),
	prop_ostl[p,f[p].(spo_p[p]),
	prop_ostl[p,f[p],Mem_s]]]]]]]
}
fun flag_ostl[p: PTag->univ] : Operand { (lcp_ostl[p].(~opstate) & speculative_xmit_p[p]) + (lcp_ostl[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p]) }
// S1: the STL analog of R-1: committed l1 reads A; store s (address unresolved) writes A; the bypassing load l
// reads A (stale value) and feeds xm's address.
pred s1_shape { some disj l1, s, l, t: Instruction |
  l1 in Loads & committed and s in Stores & unresolved and l in Loads and t in Loads & xm
  and s in l1.^spo and l in s.^spo and t in l.^spo
  and some l1.inmem and some l.inmem and l.inmem.opstate = l1.inmem.opstate and s.outmem.opstate = l1.inmem.opstate
  and some (l.outreg.rf & t.inaddr) }
"""
STL = [
    ("stl_sanity_facts", "some xm", S6),
    ("S1_stale_value_of_committed_word_flagged_u__SAT", "s1_shape and some (m_flag[no_p] & xm.inaddr)", S6),
    ("S1_same_flagged_old_STT_6_stl__UNSAT", "s1_shape and some (flag_ostl[no_p] & xm.inaddr)", S6),
    ("Y1_stl_model_flags_only_yrot__UNSAT", "some (m_flag[no_p] - y_flag[no_p])", S6),
]
STL_GEN = [
    ("gen_lit_u_stl__SAT", "gen_useful_litmus", S6),
    ("S1g_generated__SAT", "gen_useful_litmus and s1_shape", S6),
]


def core_cmds(prefix):
    return [(f"count_{prefix}_but{k}", "gen_useful_litmus", f"for 9 but {k} Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool") for k in (3, 4)]


def main():
    write("q_sem.als", base("STT_6_u.als", True), SEM)
    write("q_gen.als", base("STT_6_u.als", False), GEN)
    write("q_lostc.als", base("STT_6_u.als", False), LOSTC)
    t = base("STT_6_u_stl.als", True) + AUX_STL
    write("q_stl.als", t, STL)
    t = base("STT_6_u_stl.als", False) + AUX_STL
    write("q_stl_gen.als", t, STL_GEN)
    # cores: the core files have scope "but 6"; strip their run command and count at but 3 / but 4
    core_re = re.compile(r"run gen_lit \{\n  gen_useful_litmus\n\} for 9 but 6 Instruction[^\n]*\n")
    for name, path in (("u_core", ULT / "STT_6_u_core_ri.als"), ("u_stl_core", ULT / "STT_6_u_stl_core_ri.als"),
                       ("stl_core_approved", MODELS / "proposed_twophase" / "STT_6_stl_core.als")):
        t = path.read_text()
        assert len(core_re.findall(t)) == 1, path
        t = core_re.sub("", t)
        out = t + "\n// ======== commands (STT agent 2026-11-09) ========\n"
        for label, body, scope in core_cmds(name):
            out += f"run {label} {{ {body} }} {scope}\n"
        (HERE / f"q_core_{name}.als").write_text(out)
        print("wrote", HERE / f"q_core_{name}.als")


if __name__ == "__main__":
    main()
