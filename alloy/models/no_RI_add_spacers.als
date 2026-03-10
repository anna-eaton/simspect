

/*********************************************************************************
 \* 

CLEAN MODEL WITHOUT RELAXATION FOR DEMO


Roadmap:
- specify the requirements of the defense as predicates (on the perturbed model)
- define the execution model (instrs, state, and relations) (NOW EXTERNAL TO THIS FILE)
- build out dependency tracking in model
- constrain sets
- dependency tracking 2 (w/ perturbations)
- constrain sets 2 (w/ perturbations)
- constrain search space
- func to do perturbations, assert predicate under no_p and then not under all p
- generate litmus tests (NOW EXTERNAL)

 */

/*********************************************************************************
 * Basic execution model
 */

sig rBool {} // resolved
sig cBool {} // committed

// state sigs
abstract sig State {}     
sig Mem_s extends State {}
sig Reg_s extends State {}

// instruction sigs
abstract sig Instruction {	

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

	// state privacy store
	// we need two because we want to have each RI perturbation redefine its set
	//input_protset_s: set State,
	// output_protset_s: set State,
	//input_protset_p: set Instruction -> set State, // with this instruction removed
	// output_protset_p: set Instruction -> set State, // with this instruction removed
}

// specific types of instructions
sig Load extends Instruction {}
sig Store extends Instruction {}
sig Branchn extends Instruction {} // Ctrl/br op, doesnt xmit
sig Branchx extends Instruction {} // Ctrl/br op, xmits
sig Othern extends Instruction {} // ALU op or reg->reg op, doesnt xmit (could be unnecessary and added as spacing in stage 2)
sig Otherx extends Instruction {} // ALU op or reg->reg op, xmits 

// input and output operands
//fun ins : Instruction->State {inreg+inaddr+inmem}
//fun outs : Instruction->State {outreg+outmem}

// boolean state sets
fun committed : Instruction {iscommitted.cBool}
fun resolved : Instruction {isresolved.rBool}

// operands s.t. we can have operand->operand dependency graphs
abstract sig Operand {
	opstate: one State,
	rf: set Operand, // there is an rf edge leaving from this node
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
//fun ins : Operand {Instruction.(inreg+inmem+inaddr)}
//fun outs : Operand {Instruction.(outreg+outaddr)}
//fun operands : Operand {ins+outs}
// discuss choice to have Operands
/*********************************************************************************
 * Constraints
 */
// there are no other operands that arent of instructions
fact no_extra_ops {no (Operand - Instruction.operands)}

fact no_extra_State {no State - Operand.opstate}

// all instructions have operands (so we dont have to relax instructions) TODO
fact no_extra_Instructions {no Instruction - operands.Operand}

// each operand only belongs to one instruction
fact limited_instr_per_op {all o: Operand | #(o.(~operands)) = 1}

// make the operands have the right flavor state
fact ir_s {no (Inreg.opstate & Mem_s)}
fact ia_s {no (Inaddr.opstate & Mem_s)}
fact im_s {no (Inmem.opstate & Reg_s)}
fact or_s {no (Outreg.opstate & Mem_s)}
fact om_s {no (Outmem.opstate & Reg_s)}

///** constrain what kinds of operands each instruction has */ 
// i am limiting them a/l to set, not some, because perturbation should be able to take off useless operands
fact ld_ops {no Load.(inreg+outmem)} // load takes addr and mem and modifies reg
fact str_ops {no Store.(inmem+outreg)} // store takes addr and reg and modifies mem
fact other_ops {no (Othern+Otherx).(inaddr+inmem+outmem)} // other is some nonmem instr
fact br_ops {no (Branchn+Branchx).(inaddr+inmem+outmem+outreg)} // branch is some control (no output)

//fact limited_ops {all i: Instruction | #(i.(inreg+inaddr) <= 2}
// todo see if there are more particular input configurations to enforce
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
// make sure they are in order 
fact committed_resolved {committed in resolved}
// make sure that the retired instructions are contiguous and first in the chain - there is no non-retired followed by retired
fun uncommitted : Instruction {Instruction - committed}
fun unresolved : Instruction {Instruction - committed}
fact committed_last {no ^(spo :>uncommitted).^(spo :> committed)}
fun last_committed : Instruction {(committed <: spo :> uncommitted).uncommitted}
fun first_uncommitted : Instruction {committed.(committed <: spo :> uncommitted)}

//fact feedforward_protsets {((spo.Instruction)<:output_protset_s) = spo.input_protset_s} // check this but only for all but the last instruction's output, implicitly checks for all but the firsts input
//fun input_protset_s : Instruction -> State {(first_instr -> hardware_protection_policy) + (~spo).output_protset_s} 
// define feed forward across instructions, and first is from hpp, from static protsets

//
//fact first_protset_from_hpp {first_instr.input_protset_s = hardware_protection_policy}
//fact first_protset_from_hpp_p {
//  all i: Instruction | i.(first_instr.input_protset_p) = hardware_protection_policy
//}

fun no_unresolved_brs : Instruction {
	Instruction - (uncommitted & (Branchx+Branchn)).(^(spo))
}
fun no_unresolved_mem : Instruction {
	Instruction - (uncommitted & (Load+Store)).(^(spo))
}

fun first_instr : Instruction {Instruction - Instruction.spo}

//fun committed_protset : State {last_committed.output_protset_s}

/*********************************************************************************
 * GL-IFT-ish ddi edges, + rf edges
 *///
//fun ddi : Operand->Operand {(~ins).outs} // not yet constrained
//fun rf :  Operand->Operand {Instruction.outs->Instruction.ins} // not yet constrained
fact constrainddi {no ddi - (~ins).outs} // all ddi go from an in to an out on same instruction
fact constrainrf {rf in (Instruction.outs -> Instruction.ins)}
fact one_entering_rf {all o: Operand | lone rf.o} // you can only have one rf edge ending at an operand
fact unidirectional_rf {acyclic[(operands).rf.(~operands) + spo]} // rf goes with po
fact same_state_rf {no ((~opstate).rf.opstate - iden)} // all rf have same state element

fact ld_ddi {no (Load.operands <: ddi) - (Inmem->Outreg)}
fact str_ddi {no (Store.operands <: ddi) - (Inreg->Outmem)}
fact other_ddi {no ((Othern+Otherx).operands <: ddi) - (Inreg->Outreg)}
fact br_ddi {no ((Branchx+Branchn).operands <: ddi)}
// fr and co out for now, rf combined for Operand poc
// todo when to do i do b in a vs no b-a

/*********************************************************************************
 *=Alloy shortcuts=
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
// all 2-ary bc we are constraining the instructions and the states to have operands
abstract sig PTag {}
//one sig RIB extends PTag {} // remove boolean on the state, points to instr->boolean pair
// note: we deleted the boolean perturbations, and will just shift the boundary of the boolean by one.
// eg most recent resolved/committed will become unresolved/uncommitted and that's it.
// remove operands
//one sig RIA extends PTag {} // remove inaddr from instr when legal 
//one sig RIR extends PTag {} // remove inreg from instr when legal 
//one sig RIM extends PTag {} // remove inmem from instr when legal 
//one sig ROR extends PTag {} // remove outreg from instr when legal
//one sig ROM extends PTag {} // remove outmem from instr when legal
one sig RO extends PTag {} // remove operand
one sig RC extends PTag {} // MAKE NEW INSTRUCTION COMMITTED WHEN IT PREVIOUSLY WASNT
one sig RR extends PTag {} // MAKE NEW INSTRUCTION RESOLVED WHEN IT PREVIOUSLY WASNT
one sig RI extends PTag {} // remove instruction
one sig RS extends PTag {} // remove state
// no relaxations applied, constant used to generate the base model without perturbation
fun no_p : PTag->univ {
  (PTag->univ) - (PTag->univ) // nothin here :0
}


/*********************************************************************************
 * Perturbed model
 */
fun committed_p[p: PTag->univ] : Instruction {committed + p[RC] - p[RI]} // add the first uncommitted instruction to committed set
fun uncommitted_p[p: PTag->univ] : Instruction {uncommitted - p[RC] - p[RI]} // subtract the first unresolved from the resolved set
fun resolved_p[p: PTag->univ] : Instruction {resolved + p[RR] - p[RI]} // add the first unresolved to the resolved set
fun unresolved_p[p: PTag->univ] : Instruction {unresolved - p[RR] - p[RI]} // subtract the first unresolved from the resolved set
fun last_committed_p[p: PTag->univ] : Instruction { ((committed_p[p]) <: spo :> (uncommitted_p[p])).(uncommitted_p[p])} // recalculate 
fun first_uncommitted_p[p: PTag->univ] : Instruction {committed_p[p].(committed_p[p] <: spo :> uncommitted_p[p])}

fun i_p[p: PTag->univ] : Instruction {Instruction - p[RI]} // good instructions
fun o_p[p: PTag->univ] : Operand {i_p[p].operands :> (Operand - p[RO] - opstate.p[RS])} // good operands, remove ops and also ones that touch removed instructions

fun spo_p[p : PTag->univ] : Instruction->Instruction {spo.(iden :> (p[RI])).spo + (i_p[p] <: spo :> i_p[p])}
	// repaired SPO, fill the hole where the instruction removed was

fun fix_rf_hole_p[p : PTag->univ] : Operand -> Operand {(opstate.Reg_s<:(rf.(ddi:>(p[RI].operands)).rf):>opstate.Reg_s) + (opstate.Mem_s<:(rf.(ddi:>(p[RI].operands)).rf):>opstate.Mem_s)} 
    // if the state types are the same and we take out a crucial instruction, allow it to remove the holes
// todo you were figuring out how to do the ddi from 

fun rf_p[p : PTag->univ] : Operand -> Operand {o_p[p]<:rf:>o_p[p] + fix_rf_hole_p[p]}
    // only rf where the operand is in good operands, plus hole if the types are the same
fun ddi_p[p : PTag->univ] :  Operand -> Operand {o_p[p]<:ddi:>o_p[p]} // only ddi where the operand is in good operands (covers instruction in gi)

fun op_edges_p[p: PTag->univ] : Operand -> Operand {rf_p[p] + ddi_p[p]}

fun f[p: PTag->univ] : Instruction {(i_p[p]) - (i_p[p]).(spo_p[p])} //first instr

// perturbed - integrate the uncommittd checks into the quantification, leakage function only has to be perturbed
fun leakage_function_p[p: PTag->univ] : Operand {leakage_function - p[RO] - opstate.p[RS]}

fun speculative_xmit_p[p: PTag->univ] : Operand {leakage_function_p[p] <: speculation_contract_p[p].operands} // xmits where the xmit is speculative todo check this is correct // todo check assoc
//fun committed_protset_p[p: PTag->univ] : State {last_committed_p[p].output_protset_s}
//fun committed_protset_pr[p: PTag->univ] : State {last_committed_p[p].output_protset_p[p[RI]]}



// PROTSET PROPAGATION, depends on 

// define feedforward protsets with the removal of each instruction, then on RIs, index into the right protset in the end
//fact feedforward_protsets_p {
//  all i: Instruction | ((spo_p[RI->i].Instruction)<:output_protset_p[i]) = (spo_p[RI->i]).input_protset_p[i]
//}
//fun input_protset_p : Instruction -> Instruction -> State {(first_instr -> Instruction -> hardware_protection_policy) 
//+ (~spo).output_protset_p}
//fun input_protset_p : Instruction -> Instruction -> State {
//  (Instruction -> first_instr_p -> hardware_protection_policy)
//  
//  +
//  { j: Instruction, i: Instruction, s: State | 
//      i->s in (~(spo_p[RI->j])).output_protset_p[j]
//  }
//}
fun a[p:PTag->univ,i:Instruction,s:State] : State { prot_set_propagation_p[p,i,s]}
fun last_committed_protset_p[p: PTag->univ] : State {
//	a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
//		a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
			a[p,f[p].(spo_p[p]).(spo_p[p]),
				a[p,f[p].(spo_p[p]),
					a[p,f[p],hardware_protection_policy]
					
				]
		]
//		]
//	]
}


fun no_unresolved_brs_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted_p[p] & (Branchx+Branchn)).(^(spo_p[p]))
}
fun no_unresolved_mem_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted & (Load+Store)).(^(spo))
}


pred secure_speculation_scheme_p[p: PTag->univ] {
	(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and //handled by the fact that speculative xmit will be cleaned of p Operands
	(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p]) // remove p operands from dependency chain
}

//pred secure_speculation_scheme_pr[p: PTag->univ] {
//	(no (committed_protset_pr[p].(~opstate) & speculative_xmit_p[p])) and //handled by the fact that speculative xmit will be cleaned of p Operands
//	(no committed_protset_pr[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p]) // remove p operands from dependency chain
//}

/*********************************************************************************
 * Run
 */
let gen_useful_litmus {
  not secure_speculation_scheme_p[no_p]
  all o: Operand | secure_speculation_scheme_p[RO->o]
  
  // all i: Instruction | secure_speculation_scheme_p[RI->i]

  // only one of the following two statements can be on, depend on the execution contract 
  all i: resolved | secure_speculation_scheme_p[RR->i]
  // secure_speculation_scheme_p[RC->first_uncommitted]

  all s: State | secure_speculation_scheme_p[RS->s]
}

// make sure there are no instructions without operands
fact no_extra_inst {no (Instruction - operands.Operand)}


run gen_lit {
  gen_useful_litmus
} for 5 // but exactly 3 Instruction

// whatever
// for 4 but 2 Instruction
// for 10 but exactly 2 State, exactly 2 Instruction


/*********************************************************************************
 * Specific defense model STT (non-spec on commit)
 */

// everything must depend on _p classes

//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p]}
//fun hardware_protection_policy: State {Mem_s} 
//fun leakage_function : Operand {Load.inaddr+(Branchx+Otherx).inreg} // this one is perturbed later
//fact prot_set_propagation_p {
//	((uncommitted + (committed  - Load)) <: input_protset_s = (uncommitted  + (committed  - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
// only propagate for committed instructions
//fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	// committed loads unprotect their inaddress and everything else is the same
//	s - (Load&committed_p[p]&i).inaddr.opstate
//}


/*********************************************************************************
 * Specific defense model STT (non-spec on no older unresolved br)
 */

// everything must depend on _p classes

//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p]}
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & no_unresolved_brs_p[p]}
fun hardware_protection_policy: State {Mem_s} 
fun leakage_function : Operand {Load.inaddr+(Branchx+Otherx).inreg} // this one is perturbed later
//fact prot_set_propagation_p {
//	((uncommitted + (committed  - Load)) <: input_protset_s = (uncommitted  + (committed  - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
// only propagate for committed instructions
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	// committed loads unprotect their inaddress and everything else is the same
	s - (Load&committed_p[p]&i).inaddr.opstate
}



/*********************************************************************************
 * Specific defense model STT (non-spec on no older unresolved br)
 */

//fun speculation_contract_p[p: PTag->univ] : Instruction {Instruction - committed - no_unresolved_brs} // example : all retired instructions are non-spec
//fun hardware_protection_policy : State {Mem_s} 
//fun leakage_function : Operand {Load.inaddr+(Branchx+Otherx).inreg} // STT all transmitters, generic
//fact prot_set_propagation {
//	((uncommitted + (committed - Load)) <: input_protset_s = (uncommitted + (committed - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
//
//

/*********************************************************************************
 * Specific defense model SpecShield-ERP
 */
//
//fun speculation_contract_p[p: PTag->univ] : Instruction {Instruction - committed - no_unresolved_brs - no_unresolved_mem } // example : all retired instructions are non-spec
//fun hardware_protection_policy : State {Mem_s} 
//fun leakage_function : Operand {(Load+Store).inaddr+(Store+Branchx+Otherx).inreg} // STT all transmitters, generic
//fact prot_set_propagation {
//	((uncommitted + (committed - Load)) <: input_protset_s = (uncommitted + (committed - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}

/*********************************************************************************
 * Specific defense model SpecShield-ERP+
 */
//
//fun speculation_contract_p[p: PTag->univ] : Instruction {Instruction - committed - no_unresolved_brs - no_unresolved_mem } // example : all retired instructions are non-spec
//fun hardware_protection_policy : State {Mem_s} 
//fun leakage_function : Operand {(Load+Store).inaddr+(Branchx).inreg} // STT all transmitters, generic
//fact prot_set_propagation {
//	((uncommitted + (committed - Load)) <: input_protset_s = (uncommitted + (committed - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
/*********************************************************************************
 * Specific defense model NDA-S (fix spec contract)
 */
//
//fun speculation_contract_p[p: PTag->univ] : Instruction {Instruction - committed - no_unresolved_brs - no_unresolved_mem } // example : all retired instructions are non-spec
//fun hardware_protection_policy : State {Mem_s + Reg_s} 
//fun leakage_function : Operand {(Load+Store).inaddr+(Store+Branchx+Otherx).inreg} // STT all transmitters, generic
//fact prot_set_propagation {
//	((uncommitted + (committed - Load)) <: input_protset_s = (uncommitted + (committed - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
/*********************************************************************************
 * Specific defense model NDA-P (fix spec contract)
 */
//
//fun speculation_contract_p[p: PTag->univ] : Instruction {Instruction - committed - no_unresolved_brs - no_unresolved_mem } // example : all retired instructions are non-spec
//fun hardware_protection_policy : State {Mem_s} 
//fun leakage_function : Operand {(Load+Store).inaddr+(Store+Branchx+Otherx).inreg} // STT all transmitters, generic
//fact prot_set_propagation {
//	((uncommitted + (committed - Load)) <: input_protset_s = (uncommitted + (committed - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
/*********************************************************************************
 * Specific defense model SPT in progress
 */
//
//fun speculation_contract : Instruction {Instruction - committed - no_unresolved_brs - no_unresolved_mem } // example : all retired instructions are non-spec
//fun hardware_protection_policy : State {Mem_s} 
//fun leakage_function : Operand {(Load+Store).inaddr+(Store+Branchx+Otherx).inreg} // STT all transmitters, generic
//fact prot_set_propagation {
//	((uncommitted + (committed - Load)) <: input_protset_s = (uncommitted + (committed - Load)) <: output_protset_s) and 
//	all i : (committed & Load) | i.output_protset_s = i.input_protset_s - i.inaddr.opstate
//}
