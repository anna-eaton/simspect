#!/usr/bin/env python3
"""make_spt_u.py -- build the ULTIMATE SPT draft from the approved SPT_6_oneLP_v2.als.

DRAFT TOOLING (2026-11-09, ultimate-models / SPT agent). Output is an UNAPPROVED draft.

What it does (and nothing else):
  * reads STAGE1_alloy/models/SPT_6_oneLP_v2.als and refuses unless its sha256 is the
    approved one (acb1f2e2...), so a drifted base cannot silently produce a wrong draft;
  * prepends the [u] header;
  * replaces the defense block (from the "Specific defense model" banner to EOF) by the
    [u] SPT block below. Every skeleton line above the banner is copied byte for byte.
  * writes STAGE1_alloy/models/proposed/ultimate/SPT_6_u.als (or the path given).

Usage:  python3 make_spt_u.py [--out PATH]
Then the conservative Stage-1 core:  python3 make_spt_u.py --core   (writes SPT_6_u_core.als via
proposed_twophase/derive_core.py --minimality rori, then comments the RO/RI clauses exactly as
SPT_6_oneLP_v2_core_conservative.als does = SPT's own minimality, Anna 2026-11-08).
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parent.parent                     # STAGE1_alloy/models
BASE = MODELS / "SPT_6_oneLP_v2.als"
BASE_SHA = "acb1f2e21e5e6c3b98e7dfd8eec71bc9d9282578303626655334768addb61e8d"
BANNER = ("/*********************************************************************************\n"
          " * Specific defense model STT (non-spec on commit)\n"
          " */\n")

HEADER = """// =============================================================================
// SPT_6_u.als -- ULTIMATE SPT draft (2026-11-09, ultimate-models / SPT agent). DRAFT, NOT APPROVED.
// = SPT_6_oneLP_v2.als (sha256 acb1f2e21e5e6c3b98e7dfd8eec71bc9d9282578303626655334768addb61e8d,
//   unchanged) with ONLY the defense block replaced; every skeleton line is byte-identical to v2
//   (built by proposed/ultimate/make_spt_u.py, anchor- and hash-checked). Changes, each marked [u-n]:
//   [u-1] clause 2 rewritten as SPT's CONVERGED taint (paper p613 sec 6.6 "Convergence"): all data
//         tainted unless a rule proves it public; rules iterated to a fixpoint (6 steps, convergence
//         checked by query qconv). The protection set handed to the skeleton is the set of TAINTED
//         TRANSMITTER OPERANDS; transmitter operands have no outgoing rf/ddi edge, so the skeleton's
//         transitive `^op_edges` term is vacuous by construction (no skeleton edit = audit S-1
//         "Option B" without touching secure_speculation_scheme_p / tag_xm). Fixes S-1 (all forms,
//         incl. the store-fed residual of v3) and S-2/P3 (no one-step lag).
//   [u-2] declassification = the ADDRESS operands of non-speculative loads and stores only
//         (gem5 cpu.cc:2133-2207 untaintMemTransmit / setAddrTaint; untaintOtherTransmit is a no-op
//         with moreTransmitInsts=0, cpu.cc:2212-2222; on x86 a jcc's operands are flags, and test/cmp
//         have no backward rule, paper p613 sec 6.6). v2 also declassified br_x predicates (audit B1).
//         ALT line kept commented (DECIDE).
//   [u-3] backward untaint (paper p613 sec 6.6 rules 1-2; gem5 rob_impl.hh:853-880) on a new SPT-only
//         op class `InvOp` (subset sig in the defense block): Stage 2 MUST emit an InvOp as
//         movq (1 input) or movq+addq/subq (2 inputs), and every other ALU as an op on which SPT has
//         no backward rule. Fixes S-5 (backward untaint was unreachable in the model).
//   [u-4] store-to-load untaint both ways (paper p613 sec 6.7 rules 1-2), gated by STLPublic
//         (load address and every store address from S up to L public) and by "the store is still
//         in the SQ" (S uncommitted; gem5 lsq_unit_impl.hh:1371-1409, lsq_unit.hh:630-659). Fixes S-3.
//   [u-5] forward untaint over ALL register inputs of an ALU, to the fixpoint (paper p613 sec 6.6;
//         gem5 rob_impl.hh:797-801). Loads are never forward-untainted.
//   [u-6] initial registers (a register input with no producer) are public: Stage 2 sets them with
//         a load-immediate (paper p612 sec 6.5; same semantics as v2-2's seed, now stated directly).
// Review + evidence: the SPT agent's report (ultimate-models round); queries in
// proposed/ultimate/queries/ (run_spt_queries.sh, log spt_queries.log).
// =============================================================================
"""

BLOCK = r"""/*********************************************************************************
 * Specific defense model SPT (Choudhary et al., "Speculative Privacy Tracking", MICRO'21)
 * [u] ULTIMATE DRAFT -- see the header. Paper cites: choudhary-2021-spt.pdf, printed page =
 * PDF page + 606. gem5 cites: gem5-spt @ 0d2be0f, src/cpu/o3/ (local copy
 * ~/Documents/stanford/trippel/defense_src/spt_0d2be0f/), E11 flags --scheme=SpectreSafeFence
 * --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3, shadow L1 off.
 *
 * SPT's taint (p612 sec 6.3): "all program data (memory and architectural registers) starts off as
 * tainted"; loads' outputs are "always (conservatively) tainted"; data becomes public only by
 * declassification ("the operands of transmitters/branches are untainted when the instruction
 * becomes non-speculative") and by the untaint rules of sec 6.5-6.8, applied until convergence
 * (p613 sec 6.6). So clause 2 computes the PUBLIC set U (least fixpoint of the rules) and protects
 * every transmitter operand outside U.
 */

// (1) speculation contract -- unchanged from v2: uncommitted and behind an unresolved branch
//     (paper p609 sec 2.2.1 Spectre model; gem5 rob_impl.hh:533-561 isPrevBrsResolved -> unsquashable).
//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])}
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}

// (3) leakage function -- unchanged from v2: load/store addresses and transmitting-branch predicates
//     (moreTransmitInsts=0: lsq_unit_impl.hh:1140-1284 delays loads/stores on a tainted address;
//     commit_impl.hh:943-945 Lazy delays a tainted mispredicted branch's squash).
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg+Stores.inaddr}

// (2) protection set [u-1]: the tainted transmitter operands of the (perturbed) program.
// was (v2): fun hardware_protection_policy[p: PTag->univ]: Operand {o_p[p] - ((Inreg + Inaddr) - i_p[p].outreg.(rf_p[p]))}
fun hardware_protection_policy[p: PTag->univ]: Operand { leakage_function_p[p] - spt_public_p[p] } // [u-1]
// [u-1] the skeleton's 7-step fold carries the set through unchanged: SPT's untaint is not a
// program-order pass (p613: "untainting of a register by instruction I can cause instructions
// both younger and older than I to untaint registers"), so the fixpoint below replaces it.
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,o:Operand] : Operand { o } // [u-1]

/* ---- SPT untaint algebra (all perturbation-aware: o_p, i_p, rf_p, spo_p, uncommitted_p) ---- */

// [u-1] one physical register = one taint: an Outreg and every register input it rf-feeds
// (rf_from_most_recent_writer makes rf the register's real dataflow; RI bridges via fix_rf_hole_p).
// gem5 keeps taint per physical register (base_dyn_inst_impl.hh:450-475 setArgsIdxTaint ->
// cpu->setPartialTaint), so untainting one reader untaints the producer and every other reader.
fun spt_reg_rf_p[p: PTag->univ] : Operand->Operand { Outreg <: rf_p[p] }
fun spt_close_p[p: PTag->univ, u: Operand] : Operand { u.*(spt_reg_rf_p[p] + ~(spt_reg_rf_p[p])) }

// base public set
fun spt_public0_p[p: PTag->univ] : Operand {
	// [u-6] initial registers: a register input with no producer reads a Stage-2 load-immediate
	// (parsexml ssa_init `movq $imm`), which SPT untaints (p612 sec 6.5; rob_impl.hh:246-249).
	(((Inreg + Inaddr) & o_p[p]) - Operand.(spt_reg_rf_p[p]))
	// [u-2] declassification: the address of every non-speculative load/store (p612 sec 6.3,
	// p613 sec 6.6; gem5 lsq_unit_impl.hh:1189-1209,1268-1280 -> cpu.cc:2133-2207 setAddrTaint(false)).
	+ (nonspeculative_xmit_p[p] & (Loads + Stores).inaddr)
	// [u-2 ALT, DECIDE B1] the paper's ISA-abstract reading also declassifies branch predicates:
	// + (nonspeculative_xmit_p[p] & Branchxs.inreg)
}

// [u-5] forward untaint: an ALU whose present register inputs are all public has a public output
// (p613 sec 6.6 "if all of the instruction's operands are untainted, then its output register becomes
// untainted"; gem5 rob_impl.hh:797-801 `!isMemTransmit() && !argsTainted`). An ALU with no register
// input is a load-immediate (p612 sec 6.5). Loads are excluded (their output is untainted only via
// sec 6.7/6.8), as in gem5 (isMemTransmit).
fun spt_fwd_p[p: PTag->univ, u: Operand] : Operand {
	(((Otherns + Otherxs) & i_p[p]) - inreg.(o_p[p] - u)).outreg & o_p[p]
}

// [u-3] backward untaint on invertible ops: output public and all but one input public -> the
// remaining input public (p613 sec 6.6 rule 2; rule 1 MOV = the 1-input case). gem5 rob_impl.hh:855-880:
// add/addi/adc/adci/sub/subi/sbb/sbbi with numTaintedSrcRegs()==1, and mov src 1.
fun spt_bwd_p[p: PTag->univ, u: Operand] : Operand {
	{ i: InvOp & i_p[p] | some (i.outreg & o_p[p] & u) and lone ((i.inreg & o_p[p]) - u) }.inreg & o_p[p]
}

// [u-4] STLPublic(S, L) (p613 sec 6.7): L's address is public and every store from S (inclusive) up
// to L has a public address (gem5 lsq_unit.hh:630-659 isSTLPublic walks the SQ from the forwarding
// store to the load). A missing address operand is a Stage-2 constant (public).
pred spt_stl_public_p[p: PTag->univ, u: Operand, s, l: Instruction] {
	(l.inaddr & o_p[p]) in u
	((Stores & i_p[p] & s.*(spo_p[p]) & (^(spo_p[p])).l).inaddr & o_p[p]) in u
}
// [u-4] forwarding pairs whose taint gem5 syncs: S's memory output rf-feeds L's memory input and
// STLPublic holds. Timing gate (DECIDE): S uncommitted, i.e. still in the SQ for the whole window
// (the sync needs the store not completed and the load not committed, lsq_unit_impl.hh:1302-1305,
// 1371-1375); a committed store may already be written back, and then L reads tainted L1 data.
// [u-4 ALT] drop `& uncommitted_p[p]` (forwarding from a committed store that has not drained).
fun spt_stl_pairs_p[p: PTag->univ, u: Operand] : Instruction->Instruction {
	{ s: Stores & i_p[p] & uncommitted_p[p], l: Loads & i_p[p] |
		some ((s.outmem & o_p[p]).(rf_p[p]) & l.inmem & o_p[p]) and spt_stl_public_p[p, u, s, l] }
}
// [u-4] gem5 sets both the load's destination taint and the store's data taint to their AND
// (lsq_unit_impl.hh:1388-1400), i.e. rule 1 (store data public -> load output public) and rule 2
// (load output public -> store data public). A store with no data operand is emitted as a
// store-immediate (parsexml.py:2712-2716,2730-2733 `movq $0, ...`; gem5 limm + st), so its data is
// public, consistent with [u-6]. (v2 required a data operand, which keeps such loads tainted.)
fun spt_stl_p[p: PTag->univ, u: Operand] : Operand {
	let pr = spt_stl_pairs_p[p, u] |
	  ({ l: Instruction | some s: pr.l | (s.inreg & o_p[p]) in u }.outreg & o_p[p])
	+ ({ s: Instruction | some l: s.pr | some (l.outreg & o_p[p] & u) }.inreg & o_p[p])
}

// one parallel application of every rule (gem5 applies them every cycle to every in-flight
// instruction, rob_impl.hh:751-990; the untaint queue width freeParam=3 only slows convergence).
fun spt_step_p[p: PTag->univ, u: Operand] : Operand {
	spt_close_p[p, u + spt_fwd_p[p, u] + spt_bwd_p[p, u] + spt_stl_p[p, u]]
}
// [u-1] the converged public set: 6 steps reach the fixpoint at <= 6 instructions (query qconv:
// one more step changes nothing, under no_p and every perturbation gen_useful_litmus uses).
fun spt_public_p[p: PTag->univ] : Operand {
	spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_step_p[p, spt_step_p[p,
		spt_close_p[p, spt_public0_p[p]]]]]]]]
}

/* ---- [u-3] SPT op class: which ALUs SPT's backward rule applies to (Stage-2 contract) ----
 * InvOp = an ALU that Stage 2 MUST emit as an op gem5-spt backward-untaints and the paper calls
 * invertible: 1 register input -> `movq in0, out` (gem5 microop mov); 2 inputs -> `movq in0, out;
 * addq in1, out` (or subq) (microops mov + add/sub, no flags read). Every ALU NOT in InvOp MUST be
 * emitted as an op SPT has no backward rule for (imulq, idivq, andq, orq; cmov_rr = the A2 probe).
 * The class is canonical: an ALU is in InvOp only if its output can ever be untainted from below,
 * i.e. it reaches a load/store address or a store's data over rf and InvOp steps; elsewhere the
 * class cannot change any verdict, so allowing it would only duplicate instances.
 */
sig InvOp in Instruction {} // [u-3]
fact spt_invop_class { // [u-3]
	InvOp in Otherns
	all i: InvOp | some i.inreg and some i.outreg
	all i: InvOp | some (i.outreg.^(rf + (~inreg :> InvOp).outreg) & ((Loads + Stores).inaddr + Stores.inreg))
}
"""


def build(out: Path) -> None:
    raw = BASE.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != BASE_SHA:
        sys.exit(f"refusing: {BASE} sha256 {sha} != approved {BASE_SHA}")
    text = raw.decode("utf-8")
    if text.count(BANNER) != 1:
        sys.exit("refusing: defense-block banner not found exactly once")
    skel = text[: text.index(BANNER)]
    out.write_text(HEADER + skel + BLOCK, encoding="utf-8")
    print(f"wrote {out} (skeleton = v2 bytes 0..{len(skel.encode())})")


def build_core(src: Path, out: Path) -> None:
    derive = MODELS / "proposed_twophase" / "derive_core.py"
    tmp = out.with_suffix(".rori.tmp")
    subprocess.run([sys.executable, str(derive), str(src), str(tmp), "--minimality", "rori"], check=True)
    t = tmp.read_text(encoding="utf-8")
    ro = ("  // [STAGE-1 CORE] (e) operand-minimality: every operand necessary (no removable operand)\n"
          "  all o: Operand     | secure_speculation_scheme_p[RO->o]")
    ri = ("  // [STAGE-1 CORE] (f) instruction-minimality: every instruction necessary (no removable instr)\n"
          "  all i: Instruction | secure_speculation_scheme_p[RI->i]")
    cons = "  // [SPT CONSERVATIVE, as SPT_6_oneLP_core_conservative.als, Anna-approved 2026-11-08] disabled: over-generate instead.\n"
    for old, line in ((ro, "all o: Operand     | secure_speculation_scheme_p[RO->o]"),
                      (ri, "all i: Instruction | secure_speculation_scheme_p[RI->i]")):
        if t.count(old) != 1:
            sys.exit("refusing: RO/RI clause not found exactly once")
        head = old.split("\n")[0]
        t = t.replace(old, head + "\n" + cons + "  // " + line)
    t = t.replace("derive_core.py --minimality rori.", "derive_core.py --minimality rori, then RO/RI commented\n"
                  "// (SPT's own minimality = the conservative core, Anna 2026-11-08) by make_spt_u.py --core.", 1)
    out.write_text(t, encoding="utf-8")
    tmp.unlink()
    print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "SPT_6_u.als"))
    ap.add_argument("--core", action="store_true", help="also derive SPT_6_u_core.als (conservative)")
    a = ap.parse_args()
    out = Path(a.out)
    build(out)
    if a.core:
        build_core(out, HERE / "SPT_6_u_core.als")


if __name__ == "__main__":
    main()
