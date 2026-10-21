

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

// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)
one sig IX0 {} -- spo position 0 (first)å
one sig IX1 {} -- spo position 1
one sig IX2 {} -- spo position 2
one sig IX3 {} -- spo position 2
one sig IX4 {} -- spo position 2
one sig IX5 {} -- spo position 2

// single concrete instruction sig
sig Instruction {
	kind: one InstrType,
	idx: one (IX0 + IX1 + IX2 + IX3 + IX4 + IX5),  -- bijection to fixed position atoms

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

fun a[p:PTag->univ,i:Instruction,s:State] : State { prot_set_propagation_p[p,i,s]}
fun last_committed_protset_p[p: PTag->univ] : State {
		a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]),
			a[p,f[p].(spo_p[p]),
				a[p,f[p],hardware_protection_policy]
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
	(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and
	(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p])
}

// make sure there is some overlap in the end btw xm and speculative xmit
//fact tag_xm {some xm & speculative_xmit_p[xm]}
fact one_xm {#(xm) = 1}

// ===== Pending-squash channel (nmosier two-branch coincidence) =====
// Operands carrying a protected/secret value: the protected memory operand + everything
// forward-reachable over data edges (rf+ddi). This is the EXPLICIT-dataflow taint set.
fun tainted_operands_p[p: PTag->univ] : Operand {
  last_committed_protset_p[p].(~opstate)
  + last_committed_protset_p[p].(~opstate).(^(op_edges_p[p]))
}
// Its projection to STATES (registers/mem cells that hold a tainted value).
fun tainted_states_p[p: PTag->univ] : State { tainted_operands_p[p].opstate }

// bo: GENUINELY tainted condition — its inreg is rf/ddi-reachable from a speculative load
// (explicit dataflow), so it concretizes to actually read the secret. (acyclic rf+spo ⇒ the
// producing load precedes bo; protset ⇒ that load is speculative / not commit-cleared.)
pred branch_cond_tainted_p[p: PTag->univ, b: Instruction] {
  some (b.inreg & tainted_operands_p[p])
}
// by: untainted condition at the STATE level — excludes BOTH rf-fed taint AND the shared-opstate
// clobber (an inreg with no rf but the same register state as a tainted value would still read it).
pred branch_cond_untainted_p[p: PTag->univ, b: Instruction] {
  no (b.inreg.opstate & tainted_states_p[p])
}
// NEW insecurity channel the data-flow model misses: an OLDER tainted unresolved branch
// (bo = the secret) and a YOUNGER untainted unresolved branch (by = xm = the observable)
// both mispredict. gem5-STT squashes from the OLDEST mispredict (instCausingSquash,
// iew_impl.hh:487) and DELAYS that squash when its args are tainted (commit_impl.hh:936),
// so by's redirect timing leaks bo's (secret) direction. secure_speculation_scheme_p calls
// this SECURE because by is untainted — that data-flow blind spot is the gap this closes.
pred pending_squash_insecure_p[p: PTag->univ] {
  some bo: (Branchxs+Branchns) & unresolved_p[p], by: Branchxs & unresolved_p[p] |
      bo != by
      and (bo -> by) in ^(spo_p[p])              // bo strictly OLDER (precedes by in program order)
      and branch_cond_tainted_p[p, bo]           // older branch tainted  (the secret)
      and branch_cond_untainted_p[p, by]         // younger branch untainted (the observable)
      and by in xm                               // the younger untainted branch is the transmitter
}

/*********************************************************************************
 * Symmetry breaking — works because Instruction is now a concrete sig
 */

-- idx bijection: each instruction gets a unique fixed position atom
fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }
fact idx_surjective { (IX0 + IX1 + IX2 + IX3 + IX4 + IX5) = Instruction.idx }

-- IX0 < IX1 < IX2 is a fixed static ordering (no atom permutations possible)
pred lt_ix[a, b: univ] { (a=IX0 and b in IX1+IX2+IX3+IX4+IX5) 
				or (a=IX1 and b in IX2+IX3+IX4+IX5)
				or (a=IX2 and b in IX3+IX4+IX5)
				or (a=IX3 and b in IX4+IX5)
				or (a=IX4 and b=IX5)

}

-- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third
fact idx_matches_spo {
	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
}


/*********************************************************************************
 * Run
 */
// Pending-squash litmus generator: emit the two-mispredict, mixed-taint shape.
let gen_useful_litmus_ps {
  pending_squash_insecure_p[no_p]
  // resolution-minimality: resolving EITHER unresolved branch kills the channel,
  // so exactly the two load-bearing branches (bo, by) stay unresolved — no redundant ones.
  all i: (unresolved & (Branchxs+Branchns)) | not pending_squash_insecure_p[RR->i]
}

fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake

run gen_lit_ps {
  gen_useful_litmus_ps
} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool


/*********************************************************************************
 * Specific defense model STT (non-spec on commit)
 */

//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])}
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
fun hardware_protection_policy: State {Mem_s}
//fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	// s - (Loads & committed_p[p] & i).inaddr.opstate // committed loads remove their inaddr from the protset
	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
}

