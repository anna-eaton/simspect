// =============================================================================
// [STAGE-1 CORE DRAFT — UNAPPROVED, do not use for production testsets]
// Derived from SPT_6_u.als (sha256 76f36f68d4f74bcb25f3b316ad46e2b7c212e2f4e58b8292bcda4e75c315fc96) by
// STAGE1_alloy/models/proposed_twophase/derive_core.py --minimality rori, then RO/RI commented
// (SPT's own minimality = the conservative core, Anna 2026-11-08) by make_spt_u.py --core.
// Same three changes as the STT_6_core.als prototype: idx/IX symmetry-breaking
// removed, minimality (e) RO + (f) RI added to gen_useful_litmus, scope 'exactly 6'
// -> 'but 6' Instruction. Everything else (skeleton, source facts, defense
// block) is byte-identical to SPT_6_u.als. Stage 1.5 = SPT_6_u.als itself +
// stage_seed.py seed (stage_pipeline.py). Review: wiki/design/TWO_PHASE_MODELS.md
// =============================================================================
// =============================================================================
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
// =============================================================================
// SPT_6_oneLP_v2.als — consolidated SPT model for the final batch (2026-11-08,
// resolve-hooks session, at Anna's request). DRAFT until Anna signs off.
// Derived from SPT_6_oneLP.als (sha256 713d0904d91aa9cb5a25a33c1e60ae1156a38caea0d9c1173d4a7959aa898809), which is kept unchanged.
// Exactly four changes, each marked [v2]; every other line is byte-identical:
//   [v2-1] skeleton sync: fact rf_from_most_recent_writer, verbatim from
//          STT_6.als:161-170 (68% of the SPT_6_oneLP testset read a register
//          past a newer writer, so the program differed from the instance).
//   [v2-2] perturbation-aware protection seed (simspect-c8 / twophase-spt,
//          audited): identical at no_p, a subset under every perturbation, so
//          no instance of the old model is lost; fixes RS/RO/RI minimality.
//   [v2-3] gen_useful_litmus base clause = the skeleton's
//          `not secure_speculation_scheme_p[no_p]` (>= 1 insecure transmitter)
//          instead of `one_insecure_speculation_scheme_p[no_p]` (exactly 1).
//   [v2-4] declassification removes only the transmitted value (backward over
//          rf), not its whole rf+ddi backward cone; SPT's own backward rules
//          (paper Sec. 6 "Untaint rules": MOV, invertible ADD) untaint less
//          than the old cone, so the old rule under-protected.
// Review + evidence: wiki/state/ALLOY_MODEL_CHANGES.md (2026-11-08) and
// wiki/design/MANIFEST_BRIEF_SPT_v2.md.
// =============================================================================


/*********************************************************************************
 *
CLEAN MODEL WITH KIND-FIELD REFACTORING

Instruction is a single concrete sig with a `kind: one InstrType` field
instead of abstract + subsigs.  This lets util/ordering[Instruction] work,
enabling in-model symmetry breaking that eliminates duplicate instances.

 */

-- util/ordering[Instruction] as IOrd  -- Alloy 6: pre-binding fails in complex models

/*********************************************************************************
 * Basic execution model
 */

sig rBool {} // resolved
sig cBool {} // committed
sig tBool {} // transmitter - if flagged this is the bad spec transmitter

// state sigs
abstract sig State {}
sig Mem_s extends State {}
sig Reg_s extends State {}

// instruction kind tags (one sig = exactly one atom each)
abstract sig InstrType {}
one sig TLoad    extends InstrType {} // load from memory
one sig TStore   extends InstrType {} // store to memory
one sig TBranchn extends InstrType {} // ctrl/br op, doesnt xmit
one sig TBranchx extends InstrType {} // ctrl/br op, xmits
one sig TOthern  extends InstrType {} // ALU/reg->reg, doesnt xmit
one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits

// [STAGE-1 CORE] idx/IX symmetry-breaking REMOVED (ordering rules stripped per
// staged-enum design) so cores are not pinned to a fixed length/positions.

// single concrete instruction sig
sig Instruction {
	kind: one InstrType,

	spo: lone Instruction,

	// state elements define what goes in and out of each instr
	inreg: set Inreg,
	inaddr: set Inaddr, // only relevant for loads and stores
	outreg: set Outreg,
	inmem: set Inmem,
	outmem: set Outmem,

	// boolean variables showing state of instr
	isresolved: lone rBool,
	iscommitted: lone cBool,
	isxm: lone tBool,
}

// boolean state sets
fun committed : Instruction {iscommitted.cBool}
fun resolved : Instruction {isresolved.rBool}
fun xm : Instruction {isxm.tBool}

// kind-based instruction sets (replaces subsig membership)
fun Loads    : Instruction { kind.TLoad    }
fun Stores   : Instruction { kind.TStore   }
fun Branchns : Instruction { kind.TBranchn }
fun Branchxs : Instruction { kind.TBranchx }
fun Otherns  : Instruction { kind.TOthern  }
fun Otherxs  : Instruction { kind.TOtherx  }

// operands s.t. we can have operand->operand dependency graphs
abstract sig Operand {
	opstate: one State,
	rf: set Operand,
	ddi: set Operand,
}

sig Inreg extends Operand {}
sig Inaddr extends Operand {}
sig Inmem extends Operand {}
sig Outreg extends Operand {}
sig Outmem extends Operand {}

fun ins : Instruction -> Operand {inreg+inmem+inaddr}
fun outs : Instruction -> Operand {outreg+outmem}
fun operands : Instruction -> Operand {ins+outs}

/*********************************************************************************
 * Constraints
 */
// there are no other operands that arent of instructions
fact no_extra_ops {no (Operand - Instruction.operands)}

fact no_extra_State {no State - Operand.opstate}

// all instructions have operands (so we dont have to relax instructions)
// fact no_extra_Instructions {no Instruction - operands.Operand}

// each operand only belongs to one instruction
fact limited_instr_per_op {all o: Operand | #(o.(~operands)) = 1}

// make the operands have the right flavor state
fact ir_s {no (Inreg.opstate & Mem_s)}
fact ia_s {no (Inaddr.opstate & Mem_s)}
fact im_s {no (Inmem.opstate & Reg_s)}
fact or_s {no (Outreg.opstate & Mem_s)}
fact om_s {no (Outmem.opstate & Reg_s)}

// constrain what kinds of operands each instruction has
fact ld_ops   {no Loads.(inreg+outmem)}                          // load takes addr and mem and modifies reg
fact str_ops  {no Stores.(inmem+outreg)}                         // store takes addr and reg and modifies mem
fact other_ops {no (Otherns+Otherxs).(inaddr+inmem+outmem)}     // other is some nonmem instr
fact br_ops   {no (Branchns+Branchxs).(inaddr+inmem+outmem+outreg)} // branch is some control (no output)

fact limited_inregs {all i: Instruction | #(i.inreg) <= 2}
fact limited_inaddrs {all i: Instruction | #(i.inaddr) <= 1}
fact limited_inmems {all i: Instruction | #(i.inmem) <= 1}
fact limited_ins {all i: Instruction | #(i.ins) <= 2}
fact limited_outs {all i: Instruction | #(i.(outreg+outmem)) <= 1}

/** constrain the spo relation */
fact spo_acyclic { acyclic[spo] }
fact spo_prior { all i: Instruction | lone i.(~spo) }
fact spo_total { total[spo, Instruction] }

/** constrain the boolean instr states */
fact committed_resolved {committed in resolved}
fun uncommitted : Instruction {Instruction - committed}
fun unresolved : Instruction {Instruction - resolved}
fact committed_last {no ^(spo :>uncommitted).^(spo :> committed) and (no uncommitted <: ^spo :> committed)}
fun last_committed : Instruction {(committed <: spo :> uncommitted).uncommitted}
fun first_uncommitted : Instruction {(some committed) => committed.(committed <: spo :> uncommitted) else first_instr}

fun no_unresolved_brs : Instruction {
	Instruction - (uncommitted & (Branchxs+Branchns)).(^(spo))
}
fun no_unresolved_mem : Instruction {
	Instruction - (uncommitted & (Loads+Stores)).(^(spo))
}

fun first_instr : Instruction {Instruction - Instruction.spo}



/*********************************************************************************
 * GL-IFT-ish ddi edges, + rf edges
 */
fact constrainddi {no ddi - (~ins).outs}
fact constrainrf {rf in (Instruction.outs -> Instruction.ins)}
fact one_entering_rf {all o: Operand | lone rf.o}
fact unidirectional_rf {acyclic[(operands).rf.(~operands) + spo]}
fact same_state_rf {no ((~opstate).rf.opstate - iden)}

// [v2-1] [Option A] rf must read from the MOST-RECENT writer of the state:
// forbid another writer of the same state spo-between an rf producer and its use.
fact rf_from_most_recent_writer {
  all prod: Instruction.outs, use: prod.rf |
    no other: (Instruction.outs - prod) |
        other.opstate = prod.opstate
        and (prod.(~operands))  -> (other.(~operands)) in ^spo
        and (other.(~operands)) -> (use.(~operands))   in ^spo
}

fact ld_ddi    {no (Loads.operands <: ddi) - (Inmem->Outreg)}
fact str_ddi   {no (Stores.operands <: ddi) - (Inreg->Outmem)}
fact other_ddi {no ((Otherns+Otherxs).operands <: ddi) - (Inreg->Outreg)}
fact br_ddi    {no ((Branchxs+Branchns).operands <: ddi)}

/*********************************************************************************
 * Alloy shortcuts
 */
pred irreflexive[rel: Instruction->Instruction]       { no iden & rel }
pred acyclic[rel: Instruction->Instruction]           { irreflexive[^rel] }
pred total[rel: Instruction->Instruction, bag: Instruction] {
  all disj e0, e1: bag | e0->e1 in ^rel + ~(^rel)
  acyclic[rel]
}


/*********************************************************************************
 * Perturbations
 */
abstract sig PTag {}
one sig RO extends PTag {} // remove operand
one sig RC extends PTag {} // make instruction committed when it previously wasnt
one sig RR extends PTag {} // make instruction resolved when it previously wasnt
one sig RI extends PTag {} // remove instruction
one sig RS extends PTag {} // remove state
fun no_p : PTag->univ {
  (PTag->univ) - (PTag->univ)
}


/*********************************************************************************
 * Perturbed model
 */
fun committed_p[p: PTag->univ] : Instruction {committed + p[RC] - p[RI]}
fun uncommitted_p[p: PTag->univ] : Instruction {uncommitted - p[RC] - p[RI]}
fun resolved_p[p: PTag->univ] : Instruction {resolved + p[RR] - p[RI]}
fun unresolved_p[p: PTag->univ] : Instruction {unresolved - p[RR] - p[RI]}
fun last_committed_p[p: PTag->univ] : Instruction { ((committed_p[p]) <: spo :> (uncommitted_p[p])).(uncommitted_p[p])}
fun first_uncommitted_p[p: PTag->univ] : Instruction {committed_p[p].(committed_p[p] <: spo :> uncommitted_p[p])}

fact committed_in_resolved {no (unresolved & committed)} // make sure all committed instructions are resolved

fun i_p[p: PTag->univ] : Instruction {Instruction - p[RI]}
fun o_p[p: PTag->univ] : Operand {i_p[p].operands :> (Operand - p[RO] - opstate.(p[RS]))}

fun spo_p[p : PTag->univ] : Instruction->Instruction {spo.(iden :> (p[RI])).spo + (i_p[p] <: spo :> i_p[p])}

fun fix_rf_hole_p[p : PTag->univ] : Operand -> Operand {(opstate.Reg_s<:(rf.(ddi:>(p[RI].operands)).rf):>opstate.Reg_s) + (opstate.Mem_s<:(rf.(ddi:>(p[RI].operands)).rf):>opstate.Mem_s)}

fun rf_p[p : PTag->univ] : Operand -> Operand {o_p[p]<:rf:>o_p[p] + fix_rf_hole_p[p]}
fun ddi_p[p : PTag->univ] : Operand -> Operand {o_p[p]<:ddi:>o_p[p]}

fun op_edges_p[p: PTag->univ] : Operand -> Operand {rf_p[p] + ddi_p[p]}

fun f[p: PTag->univ] : Instruction {(i_p[p]) - (i_p[p]).(spo_p[p])}

fun leakage_function_p[p: PTag->univ] : Operand {leakage_function & o_p[p]}

fun speculative_xmit_p[p: PTag->univ] : Operand {leakage_function_p[p] <: speculation_contract_p[p].operands}
fun nonspeculative_xmit_p[p: PTag->univ] : Operand {leakage_function_p[p] <: (Instruction.operands - speculation_contract_p[p].operands)}

//fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand {prot_set_propagation_p[p,i,prot_set_propagation_p[p,i,prot_set_propagation_p[p,i,o]]]}
fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand {prot_set_propagation_p[p,i,o]}

fun last_committed_protset_p[p: PTag->univ] : Operand {
		a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]),
			a[p,f[p].(spo_p[p]),
				a[p,f[p],hardware_protection_policy[p]] // [v2-2]
			]
	]
]]]]
}

fun has_unresolved_brs_p[p: PTag->univ] : Instruction {
	((unresolved_p[p] & (Branchxs+Branchns)).(^(spo_p[p]))) // all the instructions that come after a speculative branch
}
// all the instructions minus the ones with unresolved branches earlier on
fun no_unresolved_brs_p[p: PTag->univ] : Instruction {
	// i_p[p] - (uncommitted_p[p] & (Branchxs+Branchns)).(^(spo_p[p]))
	i_p[p] - has_unresolved_brs_p[p]
}

fun no_unresolved_brs_bf_or_is_p[p: PTag->univ] : Instruction {
	no_unresolved_brs_p[p] - (unresolved_p[p] & (Branchxs+Branchns)) // there are no unresolvd brs bf and it isnt itself an unresolved br
}

fun no_unresolved_mem_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted & (Loads+Stores)).(^(spo))
}

pred secure_speculation_scheme_p[p: PTag->univ] {
	no ( 
	(
	(last_committed_protset_p[p] & speculative_xmit_p[p]) +
	(last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p])
	) 
//	- (
//	(last_committed_protset_p[p] & nonspeculative_xmit_p[p]) +
//	(last_committed_protset_p[p].(^(op_edges_p[p])) & nonspeculative_xmit_p[p])
//	) 
	)
}

pred one_insecure_speculation_scheme_p[p: PTag->univ] {
	one (
	(last_committed_protset_p[p] & speculative_xmit_p[p]) +
	(last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p])
	)
}

// make sure there is some overlap in the end btw xm and speculative xmit
//fact tag_xm {some xm & speculative_xmit_p[xm]}
fact one_xm {#(xm) = 1}
fact tag_xm { 
	some ( ((last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands) +
	(last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands))) 
//- 
//	((last_committed_protset_p[no_p] & nonspeculative_xmit_p[no_p] & xm.operands) +
	//(last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & nonspeculative_xmit_p[no_p] & xm.operands)))
}	

/*********************************************************************************
 * [STAGE-1 CORE] Symmetry breaking (idx/IX ordering rules) REMOVED.
 * spo program-order facts (spo_acyclic/spo_prior/spo_total) are kept — they are
 * execution semantics, not symmetry-breaking. a6CountModels runs symmetry=80.
 */


/*********************************************************************************
 * Run
 */
let gen_useful_litmus {
  //not secure_speculation_scheme_p[no_p]
  //one_insecure_speculation_scheme_p[no_p]
  not secure_speculation_scheme_p[no_p] // [v2-3] skeleton form (STT_6.als), >= 1 insecure transmitter

  //all i: resolved | secure_speculation_scheme_p[RR->i] or secure_speculation_scheme_p[RC->first_uncommitted]
  // resolution-min on all unresolved EXCEPT the boundary instr
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  // boundary instr (first_uncommitted): necessity tested by commit AND resolve together
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]

  all s: State | secure_speculation_scheme_p[RS->s]

  // [STAGE-1 CORE] (e) operand-minimality: every operand necessary (no removable operand)
  // [SPT CONSERVATIVE, as SPT_6_oneLP_core_conservative.als, Anna-approved 2026-11-08] disabled: over-generate instead.
  // all o: Operand     | secure_speculation_scheme_p[RO->o]
  // [STAGE-1 CORE] (f) instruction-minimality: every instruction necessary (no removable instr)
  // [SPT CONSERVATIVE, as SPT_6_oneLP_core_conservative.als, Anna-approved 2026-11-08] disabled: over-generate instead.
  // all i: Instruction | secure_speculation_scheme_p[RI->i]
}

fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake

// [STAGE-1 CORE] length restriction relaxed: 'exactly 6' -> 'up to 6' Instruction.
// RI-minimality keeps cores small; this is just the upper bound for the search.
run gen_lit {
  gen_useful_litmus
} for 9 but 5 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool


/*********************************************************************************
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
