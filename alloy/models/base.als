/*********************************************************************************
 *
 * BASE EXECUTION MODEL
 *
 * Defense-agnostic, length-agnostic.
 * Open this module to define a defense on top.
 *
 * Does NOT contain:
 *   - Defense-specific definitions (leakage_function, speculation_contract_p,
 *     hardware_protection_policy, prot_set_propagation_p, secure_speculation_scheme_p)
 *   - Length-specific definitions (InstrPos atoms, idx_matches_spo, run command)
 *
 ********************************************************************************/

sig rBool {} -- resolved token  (presence = resolved)
sig cBool {} -- committed token (presence = committed)

abstract sig State {}
sig Mem_s extends State {}
sig Reg_s extends State {}

-- instruction kind tags
abstract sig InstrType {}
one sig TLoad    extends InstrType {}
one sig TStore   extends InstrType {}
one sig TBranchn extends InstrType {}
one sig TBranchx extends InstrType {}
one sig TOthern  extends InstrType {}
one sig TOtherx  extends InstrType {}

-- proxy sig for symmetry-breaking index;
-- concrete atoms (IX0, IX1, ...) defined in the per-length module
abstract sig InstrPos {}

sig Instruction {
	kind: one InstrType,
	idx:  one InstrPos,   -- bijection to position atoms; constrained per-length

	spo: lone Instruction,

	inreg:  set Inreg,
	inaddr: set Inaddr,
	outreg: set Outreg,
	inmem:  set Inmem,
	outmem: set Outmem,

	isresolved:  lone rBool,
	iscommitted: lone cBool,
}

fun committed : Instruction { iscommitted.cBool }
fun resolved  : Instruction { isresolved.rBool  }

fun Loads    : Instruction { kind.TLoad    }
fun Stores   : Instruction { kind.TStore   }
fun Branchns : Instruction { kind.TBranchn }
fun Branchxs : Instruction { kind.TBranchx }
fun Otherns  : Instruction { kind.TOthern  }
fun Otherxs  : Instruction { kind.TOtherx  }

abstract sig Operand {
	opstate: one State,
	rf:  set Operand,
	ddi: set Operand,
}

sig Inreg  extends Operand {}
sig Inaddr extends Operand {}
sig Inmem  extends Operand {}
sig Outreg extends Operand {}
sig Outmem extends Operand {}

fun ins      : Instruction -> Operand { inreg + inmem + inaddr }
fun outs     : Instruction -> Operand { outreg + outmem }
fun operands : Instruction -> Operand { ins + outs }

/*********************************************************************************
 * Structural constraints
 */

fact no_extra_ops          { no (Operand - Instruction.operands) }
fact no_extra_State        { no State - Operand.opstate }
fact no_extra_Instructions { no Instruction - operands.Operand }
fact limited_instr_per_op  { all o: Operand | #(o.(~operands)) = 1 }

fact ir_s { no (Inreg.opstate  & Mem_s) }
fact ia_s { no (Inaddr.opstate & Mem_s) }
fact im_s { no (Inmem.opstate  & Reg_s) }
fact or_s { no (Outreg.opstate & Mem_s) }
fact om_s { no (Outmem.opstate & Reg_s) }

fact ld_ops    { no Loads.(inreg+outmem) }
fact str_ops   { no Stores.(inmem+outreg) }
fact other_ops { no (Otherns+Otherxs).(inaddr+inmem+outmem) }
fact br_ops    { no (Branchns+Branchxs).(inaddr+inmem+outmem+outreg) }

fact limited_inregs  { all i: Instruction | #(i.inreg)           <= 2 }
fact limited_inaddrs { all i: Instruction | #(i.inaddr)          <= 1 }
fact limited_inmems  { all i: Instruction | #(i.inmem)           <= 1 }
fact limited_ins     { all i: Instruction | #(i.ins)             <= 2 }
fact limited_outs    { all i: Instruction | #(i.(outreg+outmem)) <= 1 }

fact spo_acyclic { acyclic[spo] }
fact spo_prior   { all i: Instruction | lone i.(~spo) }
fact spo_total   { total[spo, Instruction] }

fact committed_resolved { committed in resolved }
fun uncommitted  : Instruction { Instruction - committed }
fun unresolved   : Instruction { Instruction - committed }
fact committed_last   { no ^(spo :> uncommitted).^(spo :> committed) }
fun last_committed    : Instruction { (committed <: spo :> uncommitted).uncommitted }
fun first_uncommitted : Instruction { committed.(committed <: spo :> uncommitted) }

fun no_unresolved_brs : Instruction {
	Instruction - (uncommitted & (Branchxs+Branchns)).(^spo)
}
fun no_unresolved_mem : Instruction {
	Instruction - (uncommitted & (Loads+Stores)).(^spo)
}

fun first_instr : Instruction { Instruction - Instruction.spo }

fact constrainddi      { no ddi - (~ins).outs }
fact constrainrf       { rf in (Instruction.outs -> Instruction.ins) }
fact one_entering_rf   { all o: Operand | lone rf.o }
fact unidirectional_rf { acyclic[(operands).rf.(~operands) + spo] }
fact same_state_rf     { no ((~opstate).rf.opstate - iden) }

fact ld_ddi    { no (Loads.operands              <: ddi) - (Inmem->Outreg) }
fact str_ddi   { no (Stores.operands             <: ddi) - (Inreg->Outmem) }
fact other_ddi { no ((Otherns+Otherxs).operands  <: ddi) - (Inreg->Outreg) }
fact br_ddi    { no ((Branchxs+Branchns).operands <: ddi) }

pred irreflexive[rel: Instruction->Instruction] { no iden & rel }
pred acyclic[rel: Instruction->Instruction]     { irreflexive[^rel] }
pred total[rel: Instruction->Instruction, bag: Instruction] {
	all disj e0, e1: bag | e0->e1 in ^rel + ~(^rel)
	acyclic[rel]
}

/*********************************************************************************
 * Perturbations
 */

abstract sig PTag {}
one sig RO extends PTag {} -- remove operand
one sig RC extends PTag {} -- make instruction committed when it previously wasn't
one sig RR extends PTag {} -- make instruction resolved when it previously wasn't
one sig RI extends PTag {} -- remove instruction
one sig RS extends PTag {} -- remove state

fun no_p : PTag->univ { (PTag->univ) - (PTag->univ) }

fun committed_p[p: PTag->univ]        : Instruction { committed   + p[RC] - p[RI] }
fun uncommitted_p[p: PTag->univ]      : Instruction { uncommitted - p[RC] - p[RI] }
fun resolved_p[p: PTag->univ]         : Instruction { resolved    + p[RR] - p[RI] }
fun unresolved_p[p: PTag->univ]       : Instruction { unresolved  - p[RR] - p[RI] }
fun last_committed_p[p: PTag->univ]   : Instruction {
	((committed_p[p]) <: spo :> (uncommitted_p[p])).(uncommitted_p[p])
}
fun first_uncommitted_p[p: PTag->univ] : Instruction {
	committed_p[p].(committed_p[p] <: spo :> uncommitted_p[p])
}

fun i_p[p: PTag->univ] : Instruction { Instruction - p[RI] }
fun o_p[p: PTag->univ] : Operand {
	i_p[p].operands :> (Operand - p[RO] - opstate.(p[RS]))
}

fun spo_p[p: PTag->univ] : Instruction->Instruction {
	spo.(iden :> (p[RI])).spo + (i_p[p] <: spo :> i_p[p])
}

fun fix_rf_hole_p[p: PTag->univ] : Operand->Operand {
	(opstate.Reg_s <: (rf.(ddi :> (p[RI].operands)).rf) :> opstate.Reg_s) +
	(opstate.Mem_s <: (rf.(ddi :> (p[RI].operands)).rf) :> opstate.Mem_s)
}

fun rf_p[p: PTag->univ]  : Operand->Operand { o_p[p]<:rf:>o_p[p]  + fix_rf_hole_p[p] }
fun ddi_p[p: PTag->univ] : Operand->Operand { o_p[p]<:ddi:>o_p[p] }

fun op_edges_p[p: PTag->univ] : Operand->Operand { rf_p[p] + ddi_p[p] }

fun f[p: PTag->univ] : Instruction { i_p[p] - i_p[p].(spo_p[p]) }

fun no_unresolved_brs_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted_p[p] & (Branchxs+Branchns)).(^(spo_p[p]))
}
fun no_unresolved_mem_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted & (Loads+Stores)).(^spo)
}

/*********************************************************************************
 * Symmetry breaking (partial) — idx bijection enforced here;
 * idx_matches_spo and lt_ix are defined per-length module.
 */

fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }
