#!/usr/bin/env python3
"""build_spt_queries.py -- write the Alloy query copies for the ULTIMATE SPT draft (SPT agent, 2026-11-09).

Usage:  python3 build_spt_queries.py            (writes queries/spt_*.als next to this script)
Run:    bash run_spt_queries.sh <file.als> <timeout_s> [models <limit>]   (one java, shared lock)

Every query file = proposed/ultimate/SPT_6_u.als with
  * `fact tag_xm {` turned into `pred tag_xm_u {` (so facts-only shape queries are not forced to
    flag xm under u; generation queries add `tag_xm_u` explicitly, as the production run does),
  * the production `run gen_lit` removed,
  * the v2 and v3 defense semantics appended as renamed aux functions (*_v2, *_v3; text copied
    from SPT_6_oneLP_v2.als:375-396 and proposed/SPT_6_oneLP_v3.als), so a query can ask how each
    model judges the SAME instance,
  * shape predicates + labelled commands (a6RunAll prints `CMD <label> SAT|UNSAT <ms>`;
    labels starting with count_ are enumerated).
Nothing under STAGE1_alloy/models/ except this directory is written.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
U = HERE.parent / "SPT_6_u.als"
SCOPE = "for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"
RUN_GEN = "run gen_lit {\n  gen_useful_litmus\n} " + SCOPE + "\n"

AUX = r"""
// ============================================================================================
// ---- query aux (build_spt_queries.py): v2 and v3 semantics on the same instance ----
fun hpp_v2[p: PTag->univ]: Operand {o_p[p] - ((Inreg + Inaddr) - i_p[p].outreg.(rf_p[p]))}
fun prop_v2[p:PTag->univ,i:Instruction,o:Operand] : Operand {
	o
	- (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p]))
	- (i & ((Otherns + Otherxs) - inreg.Inreg)).outreg
	- (i & ((Otherns + Otherxs) - inreg.o)).outreg
	- ((i.inreg + i.inaddr) & (Operand - o).(rf_p[p]))
	- (i & Loads & inmem.( ((Stores - inreg.o) & inreg.Inreg).outmem.(rf_p[p]) )).(outreg + inmem)
}
fun prop_v3[p:PTag->univ,i:Instruction,o:Operand] : Operand {
	o
	- (let d = (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) | d + (d & Loads.outreg).(~(ddi_p[p])))
	- (i & ((Otherns + Otherxs) - inreg.Inreg)).outreg
	- (i & ((Otherns + Otherxs) - inreg.o)).outreg
	- ((i.inreg + i.inaddr) & (Operand - o).(rf_p[p]))
	- (i & Loads & inmem.( ((Stores - inreg.o) & inreg.Inreg).outmem.(rf_p[p]) )).(outreg + inmem)
}
fun lcp_v2[p: PTag->univ] : Operand {
	prop_v2[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v2[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v2[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v2[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v2[p,f[p].(spo_p[p]).(spo_p[p]),
	prop_v2[p,f[p].(spo_p[p]),
	prop_v2[p,f[p],hpp_v2[p]]]]]]]]
}
fun lcp_v3[p: PTag->univ] : Operand {
	prop_v3[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v3[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v3[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v3[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
	prop_v3[p,f[p].(spo_p[p]).(spo_p[p]),
	prop_v3[p,f[p].(spo_p[p]),
	prop_v3[p,f[p],hpp_v2[p]]]]]]]]
}
fun flag_v2[p: PTag->univ] : Operand { (lcp_v2[p] & speculative_xmit_p[p]) + (lcp_v2[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
fun flag_v3[p: PTag->univ] : Operand { (lcp_v3[p] & speculative_xmit_p[p]) + (lcp_v3[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
fun flag_u[p: PTag->univ] : Operand { (last_committed_protset_p[p] & speculative_xmit_p[p]) + (last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
pred secure_v2[p: PTag->univ] { no flag_v2[p] }
pred gul_v2 {
  not secure_v2[no_p]
  all i: (unresolved - first_uncommitted) | secure_v2[RR->i]
  secure_v2[RC->first_uncommitted + RR->first_uncommitted]
  all s: State | secure_v2[RS->s]
}
pred useful_u  { gen_useful_litmus and tag_xm_u }
// gen_useful_litmus WITHOUT the RS (state-minimality) clause: is near-miss untaint context pruned only by RS?
pred useful_u_noRS { not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
  tag_xm_u }
pred useful_v2 { gul_v2 and (some flag_v2[no_p] & xm.operands) }
pred fl_u  { some flag_u[no_p]  & xm.operands }
pred fl_v2 { some flag_v2[no_p] & xm.operands }
pred fl_v3 { some flag_v3[no_p] & xm.operands }

// convergence of the [u-1] fixpoint: one more step changes nothing
fun spt_public7_p[p: PTag->univ] : Operand { spt_step_p[p, spt_public_p[p]] }
fun spt_public5_p[p: PTag->univ] : Operand {
	spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_close_p[p, spt_public0_p[p]]]]]]] }
fun spt_public4_p[p: PTag->univ] : Operand {
	spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_close_p[p, spt_public0_p[p]]]]]] }
pred conv_ok[p: PTag->univ] { spt_public7_p[p] = spt_public_p[p] }
pred conv_all { conv_ok[no_p] and (all i: Instruction | conv_ok[RR->i]) and
  conv_ok[RC->first_uncommitted + RR->first_uncommitted] and (all s: State | conv_ok[RS->s]) }

// ---- shapes (no_p, unperturbed). rd[c, j]: operand set c is non-empty and every member reads j's output
// (a bare `c in j.outreg.rf` is vacuously true for an empty c, which made the first round's shapes vacuous)
pred rd[c: set Operand, j: Instruction] { some c and c in j.outreg.rf }
fun nsp : Instruction { Instruction - speculation_contract_p[no_p] }   // non-speculative (VP reached)
fun sp  : Instruction { speculation_contract_p[no_p] }
// T1 (audit S-1): xm and a non-speculative load t read the SAME register, produced by a memory-reading load l
pred t1_core[l, t: Instruction] { l in Loads and t in Loads - xm and xm in Loads & sp and t in nsp
  and some l.inmem and (l.inmem -> l.outreg) in ddi and rd[t.inaddr, l] and rd[xm.inaddr, l] }
pred t1  { some l, t: Instruction | t1_core[l, t] }
// T1b (v3 residual): as T1, the producer load reads a value a store wrote (Outmem -rf-> Inmem)
pred t1b { some l, t: Instruction, s: Stores | t1_core[l, t] and some s.outmem and l.inmem in s.outmem.rf }
// T2 (S-2 / P3): xm's address = ALU o2 of ALU o1 whose inputs are initial registers (constants)
pred t2 { xm in Loads & sp and some disj o1, o2: Otherns + Otherxs |
  rd[xm.inaddr, o2] and rd[o2.inreg, o1] and no rf.(o1.inreg) }
// T3 (backward, paper p613 rule 2): i = x + c, x from a load, c an initial register, i's output is the
// address of a non-speculative load t (declassified); xm reads x
pred t3_core[l, i, t: Instruction] { xm in Loads & sp and l in Loads and some l.inmem and (l.inmem->l.outreg) in ddi
  and i in Otherns and #(i.inreg) = 2 and some (i.inreg & l.outreg.rf) and some (i.inreg - l.outreg.rf)
  and no rf.(i.inreg - l.outreg.rf) and t in Loads - xm and t in nsp and rd[t.inaddr, i] and rd[xm.inaddr, l] }
pred t3_inv    { some l, i, t: Instruction | t3_core[l, i, t] and i in InvOp }
pred t3_noninv { some l, i, t: Instruction | t3_core[l, i, t] and i not in InvOp }
// T3two: as T3 with BOTH inputs from loads: the rule must NOT fire (two tainted inputs)
pred t3_two { some l, l2, i, t: Instruction | xm in Loads & sp and l in Loads and l2 in Loads - l
  and i in InvOp and #(i.inreg) = 2 and some (i.inreg & l.outreg.rf) and some (i.inreg & l2.outreg.rf)
  and t in Loads - xm and t in nsp and rd[t.inaddr, i] and rd[xm.inaddr, l] }
// T3spec: as T3 (InvOp) but the reader t of i's output is SPECULATIVE: no declassification, no untaint
pred t3_spec { some l, i, t: Instruction | xm in Loads & sp and l in Loads and i in InvOp
  and some (i.inreg & l.outreg.rf) and no rf.(i.inreg - l.outreg.rf) and t in (Loads + Stores) - xm and t in sp
  and rd[t.inaddr, i] and rd[xm.inaddr, l] }
// T3c (paper Fig. 4(c), forward after declassification): i1 (load-fed) is declassified by t;
// i3 = i1 + c feeds xm
pred t3c { some i1, i3, t: Instruction | xm in Loads & sp and t in Loads - xm and t in nsp
  and i1 in Otherns + Otherxs and i3 in (Otherns + Otherxs) - i1 and some (i1.inreg & Loads.outreg.rf)
  and rd[t.inaddr, i1] and #(i3.inreg) = 2 and some (i3.inreg & i1.outreg.rf)
  and no rf.(i3.inreg - i1.outreg.rf) and rd[xm.inaddr, i3] }
// T4 (STL, paper p613 sec 6.7): store s with public data and public address forwards to load l, xm reads l
pred t4_core[s, l: Instruction] { xm in Loads & sp and s in Stores and l in Loads - xm
  and some l.inmem and l.inmem in s.outmem.rf and some s.inreg and no rf.(s.inreg) and no rf.(s.inaddr)
  and no rf.(l.inaddr) and rd[xm.inaddr, l] }
pred t4_pass { some s, l: Instruction | t4_core[s, l] and s in uncommitted and
  no s2: Stores - s | s2 in s.^spo and l in s2.^spo and some rf.(s2.inaddr) }
pred t4_gate { some s, l, s2, l3: Instruction | t4_core[s, l] and s in uncommitted and s2 in Stores - s
  and s2 in s.^spo and l in s2.^spo and l3 in Loads and rd[s2.inaddr, l3] }
pred t4_comm { some s, l: Instruction | t4_core[s, l] and s in committed and
  no s2: Stores - s | s2 in s.^spo and l in s2.^spo and some rf.(s2.inaddr) }
// T4bwd (rule 2): l1's value is stored by s and re-loaded by l; a non-speculative t transmits l's
// output (declassified) -> s's data -> l1's output public; xm reads l1
pred t4_bwd { some l1, s, l, t: Instruction | xm in Loads & sp and l1 in Loads and some l1.inmem
  and s in Stores & uncommitted and rd[s.inreg, l1] and no rf.(s.inaddr)
  and l in Loads and some l.inmem and l.inmem in s.outmem.rf and no rf.(l.inaddr)
  and t in Loads - xm and t in nsp and rd[t.inaddr, l] and rd[xm.inaddr, l1]
  and (no s2: Stores - s | s2 in s.^spo and l in s2.^spo) }
// T5 (audit B1): a non-speculative br_x tests the value xm transmits
pred t5 { some l, b: Instruction | xm in Loads & sp and l in Loads and b in Branchxs & nsp
  and rd[b.inreg, l] and rd[xm.inaddr, l] }
pred t5n { some l, b: Instruction | xm in Loads & sp and l in Loads and no l.inmem and b in Branchxs & nsp
  and rd[b.inreg, l] and rd[xm.inaddr, l] }
// A2 probe shape: a NON-invertible ALU's output is declassified and xm reads its input
pred a2probe { some l, i, t: Instruction | xm in Loads & sp and l in Loads and i in (Otherns + Otherxs) - InvOp
  and some (i.inreg & l.outreg.rf) and t in (Loads + Stores) - xm and t in nsp and rd[t.inaddr, i]
  and rd[xm.inaddr, l] }
"""

SH = "\n// ---- commands ----\n"


def base_text() -> str:
    t = U.read_text(encoding="utf-8")
    tag = "\nfact tag_xm { \n"
    assert t.count(tag) == 1 and t.count(RUN_GEN) == 1, "anchors"
    return t.replace(tag, "\npred tag_xm_u { \n").replace(RUN_GEN, "")


def cmds(pairs):
    return SH + "".join(f"run {lab} {{ {body} }} {SCOPE}\n" for lab, body in pairs)


A = [  # facts only (no minimality), targeted rule firing -- part 1: declassification + backward
    ("t1_u", "t1 and fl_u"), ("t1_v2", "t1 and fl_v2"), ("t1b_u", "t1b and fl_u"), ("t1b_v3", "t1b and fl_v3"),
    ("t3inv_u", "t3_inv and fl_u"), ("t3inv_v2", "t3_inv and fl_v2"), ("t3noninv_u", "t3_noninv and fl_u"),
    ("t3two_u", "t3_two and fl_u"), ("t3c_u", "t3c and fl_u"), ("t3c_v2", "t3c and fl_v2"),
]
A2 = [  # part 2: STL, branch predicates, speculative reader, convergence
    ("t4pass_u", "t4_pass and fl_u"), ("t4pass_v2", "t4_pass and fl_v2"), ("t4gate_u", "t4_gate and fl_u"),
    ("t4bwd_u", "t4_bwd and fl_u"), ("t4bwd_v2", "t4_bwd and fl_v2"), ("t4comm_u", "t4_comm and fl_u"),
    ("t5n_u", "t5n and fl_u"), ("t5n_v2", "t5n and fl_v2"), ("t3spec_u", "t3_spec and fl_u"),
    ("conv_nop", "not conv_ok[no_p]"),
]
B = [  # with the production generation predicate (gen_useful_litmus + tag_xm_u); conv_facts/g_sat ran in round 1
    ("g_t1", "useful_u and t1"), ("g_t3two", "useful_u and t3_two"), ("gnoRS_t3two", "useful_u_noRS and t3_two"),
    ("g_a2probe", "useful_u and a2probe"), ("gnoRS_a2probe", "useful_u_noRS and a2probe"),
]


CORE_SCOPE = "} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"


def core_copies() -> None:
    """Stage-1 core size probes: the conservative core (SPT's own minimality) and, for comparison with
    the non-converging v2 RI-only Stage 1, an RI-only core derived the same way (derive_core --minimality ri)."""
    import subprocess, sys, tempfile
    cons = (HERE.parent / "SPT_6_u_core.als").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        ri_path = Path(td) / "SPT_6_u_core_ri.als"
        subprocess.run([sys.executable, str(HERE.parent.parent.parent / "proposed_twophase" / "derive_core.py"),
                        str(U), str(ri_path), "--minimality", "ri"], check=True, capture_output=True)
        ri = ri_path.read_text(encoding="utf-8")
    for src, tag in ((cons, "ucons"), (ri, "uri")):
        assert src.count(CORE_SCOPE) == 1, "core scope anchor"
        for n in (3, 4, 5):
            t = src.replace(CORE_SCOPE, CORE_SCOPE.replace("but 6 Instruction", f"but {n} Instruction"))
            path = HERE / f"spt_D_{tag}_b{n}.als"
            if not (path.exists() and path.read_text(encoding="utf-8") == t):
                path.write_text(t, encoding="utf-8")
                print("wrote", path)


def main() -> None:
    t = base_text() + AUX
    files = {
        "spt_A_shapes.als": cmds(A),
        "spt_A2_shapes.als": cmds(A2),
        "spt_E_conv.als": cmds([("conv_nop", "not conv_ok[no_p]")]),
        "spt_B_gen.als": cmds(B),
        # differential dumps (a6CountModels runs the FIRST command only)
        "spt_C_lost.als": cmds([("lost", "useful_v2 and not useful_u and no InvOp")]),
        "spt_C_gained.als": cmds([("gained", "useful_u and not useful_v2 and no InvOp")]),
        "spt_C_sample_u.als": cmds([("sample_u", "useful_u")]),
    }
    for name, c in files.items():
        path = HERE / name
        if path.exists() and path.read_text(encoding="utf-8") == t + c:
            print("unchanged", path)
            continue
        path.write_text(t + c, encoding="utf-8")
        print("wrote", path)
    core_copies()


if __name__ == "__main__":
    main()
