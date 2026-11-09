// =============================================================================
// [STAGE-1 CORE DRAFT — UNAPPROVED, do not use for production testsets]
// Derived from Recon_6_v2.als (sha256 edda1bcc9a08b32ca3e27ba7f6e6495451fa58b7aa63b01f4b708925ced6a708) by
// STAGE1_alloy/models/proposed_twophase/derive_core.py --minimality ri.
// Same three changes as the STT_6_core.als prototype: idx/IX symmetry-breaking
// removed, minimality (f) RI only added to gen_useful_litmus, scope 'exactly 6'
// -> 'but 6' Instruction. Everything else (skeleton, source facts, defense
// block) is byte-identical to Recon_6_v2.als. Stage 1.5 = Recon_6_v2.als itself +
// stage_seed.py seed (stage_pipeline.py). Review: wiki/design/TWO_PHASE_MODELS.md
// =============================================================================
// =============================================================================
// Recon_6_v2.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).
// Derived from Recon_6.als (sha256 01252c82c6c0b75522e7c465b92b1c7e9631c94a9bd7a9fa6d7d7b8fc5ab8247), which is unchanged.
// Skeleton = STT_6_v2.als byte for byte; `diff STT_6_v2.als Recon_6_v2.als` is this
// header plus the ReCon defense block. Changes vs Recon_6.als, each marked:
//   [v2-1] fact rf_from_most_recent_writer, verbatim from STT_6.als:161-169 (audit R-3:
//          25.8% of Recon_6 instances read a register past a newer writer).
//   [v2-2] instance-based protection set (as STT_6_v2.als).
//   [v2-3] ReCon reveal rewritten: direct load pair (LD1.outreg -rf-> LD2.inaddr, no
//          instruction between), only once LD2 COMMITS, per word (Mem_s), concealed by any
//          store to the word between LD1 and the re-load; the reveal un-protects only the
//          re-load's memory read (ReCon §4.1, §4.3, §4.4, §5.1, §5.2, §5.4; gem5-recon
//          lsq_unit.cc:870-956, commit.cc:1033-1054, base.cc:1218-1223). Fixes R-1/R-2.
// Review + evidence: wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".
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

// [Option A] rf must read from the MOST-RECENT writer of the state:
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

fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand { prot_set_propagation_p[p,i,o]} // [v2-2] Operand-typed protection set
fun last_committed_protset_p[p: PTag->univ] : Operand { // [v2-2]
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
	// [v2-2] the protection set is a set of operands now, so no .(~opstate) lift (same form as SPT_6_oneLP_v2.als:287-296)
	(no (last_committed_protset_p[p] & speculative_xmit_p[p])) and
	(no last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p])
}

// make sure there is some overlap in the end btw xm and speculative xmit
//fact tag_xm {some xm & speculative_xmit_p[xm]}
fact one_xm {#(xm) = 1}
fact tag_xm { 
	// [v2-2] Operand-typed, as in secure_speculation_scheme_p
	(some (last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands)) or
	(some last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)
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
  not secure_speculation_scheme_p[no_p]

  //all i: resolved | secure_speculation_scheme_p[RR->i] or secure_speculation_scheme_p[RC->first_uncommitted]
  // resolution-min on all unresolved EXCEPT the boundary instr
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  // boundary instr (first_uncommitted): necessity tested by commit AND resolve together
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]

  all s: State | secure_speculation_scheme_p[RS->s]

  // [STAGE-1 CORE] (f) instruction-minimality: every instruction necessary (no removable instr)
  all i: Instruction | secure_speculation_scheme_p[RI->i]
}

fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake

// [STAGE-1 CORE] length restriction relaxed: 'exactly 6' -> 'up to 6' Instruction.
// RI-minimality keeps cores small; this is just the upper bound for the search.
run gen_lit {
  gen_useful_litmus
} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool


/*********************************************************************************
 * Specific defense model STT (non-spec on commit)
 */

//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])}
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
//fun hardware_protection_policy: State {Mem_s}
// [v2-3] ReCon reveal / conceal, per word (Mem_s) and per re-load instance. The memory read m of a
// load L3 is REVEALED iff some direct load pair LD1 -> LD2 has exposed m's word:
//   - LD1 reads the same word, and LD1 is spo-before L3;
//   - LD1's output register is LD2's address register over ONE rf edge, i.e. no instruction in
//     between (ReCon §4.3 "RECON limits its detection to only the leakage of load pairs with a
//     direct dependence"; gem5 lsq_unit.cc:872-880 matches LD2's renamed source to LD1's dest, and
//     commit.cc:1046-1054 drops the entry when any other instruction writes that register);
//   - LD2 has COMMITTED (§4.1 (2), §5.1 "detection in the commit stage", §5.2 "When the second load
//     (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as
//     revealed"; gem5 sends the Reveal from LSQUnit::commitLoad, lsq_unit.cc:870-918);
//   - no store writes the word spo-between LD1 and L3 (conceal: §4.4 "Once an address is revealed,
//     it is guaranteed to be safe as long as its contents do not change", §4.4.1 / §5.2 a committed
//     store clears the word's bit, gem5 base.cc:1218-1223; §4.4.2 a younger in-flight store forwards
//     concealed data). A store between LD1 and LD2 also conceals here: LD2 leaked the OLD value
//     (paper §4.4); gem5 re-reveals in that case (SOURCE_AUDIT_RECON.md R-SA-2), so such a test is
//     a leak in the model and exposes R-SA-2 when the reveal works.
// A revealed read is not a taint source (§5.4 "for STT, any load that receives a revealed value
// untaints its destination register"); everything else is exactly STT_6_v2.
fun revealed_p[p: PTag->univ] : Operand {
	{ m: Loads.inmem & o_p[p] | some ld1, ld2: Loads & i_p[p] |
		ld2 in committed_p[p]
		and some (ld1.outreg.(rf_p[p]) & ld2.inaddr)
		and m.opstate in (ld1.inmem & o_p[p]).opstate
		and ld1 -> m.(~inmem) in ^(spo_p[p])
		and (no s: Stores & i_p[p] | m.opstate in (s.outmem & o_p[p]).opstate
			and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
}
// [v2-2] instance-based protection (as STT_6_v2.als) minus the revealed reads [v2-3]
fun hardware_protection_policy[p: PTag->univ]: Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_p[p]}
// old (Recon_6.als:316-318), a no-op (audit QR2): Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p]))
// fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,o:Operand] : Operand {
	// [v2-2] nothing is ever de-protected in program order: the seed is already the final set
	// (old, location-based: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate, i.e. any
	//  non-speculative load made its whole LOCATION public, so a later speculative re-load of the same
	//  word was never a leak; audit R-1 / QR1a, STT-3 / Recon F2)
	o
}

