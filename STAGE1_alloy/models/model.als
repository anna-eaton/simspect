module model

/*********************************************************************************
 \* 
Modified my memory model to incorportate the perturbation model as per Lustig paper

Roadmap:
- enumerate the perturbations we can do on the model
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
 * Perturbations
 */

abstract sig PTag {}

// basically just decimate any state there could be (i think this is all the options)
one sig RI extends PTag {} // remove instr
one sig RS extends PTag {} // remove state element (reg or mem)
one sig RB extends PTag {} // remove boolean on the state, points to instr->boolean pair
// remove operands (have to do them separate unfortunately)
one sig RA extends PTag {} // remove addrop from instr when legal 
one sig RD extends PTag {} // remove dataop from instr when legal 
one sig RR extends PTag {} // remove reg from instr when legal 
one sig RM extends PTag {} // remove mem from instr when legal

fun no_p : PTag->univ { // no_p - constant for no perturbation
  (PTag->univ) - (PTag->univ) // nothin here :0
}


/*********************************************************************************
 * Basic execution model
 */

//sig eBool {}
//sig hBool {}
sig rBool {}

// state sigs
abstract sig State {}     
sig Mem_s extends State {}
sig Reg_s extends State {}

// instruction sigs
// could include executed, faulted, mispredicted, resolved, handled pred, writeback, retired
// right now implements executed, handled_prediction, retired
abstract sig Instruction {	

	po: lone Instruction,

	// state elements define what goes in and out of each instr
	dataop: set Reg_s,
	addrop: set Reg_s,
	outreg: set Reg_s,
	outmem: set Mem_s,

	// boolean variables showing state of instr
//	executed: lone eBool,
//	handled_pred: lone hBool,
	retired: lone rBool,

	// state privacy store
	private_s: set State,
}

// specific types of instructions
sig Load extends Instruction {}
sig Store extends Instruction {}
sig Ctrl extends Instruction {}
sig Div extends Instruction {}
sig Other extends Instruction {}

/*********************************************************************************
 * Constraints
 */

/** constrain what kinds of operands each instruction has */ 
fact load_ops {no Load.dataop and no Load.outmem} // load takes addr and modifies reg, doesn't take data or modify memory
fact store_ops {no Store.outreg} // store takes data, addr and modifies mem, not reg
fact ctrl_ops {no Ctrl.outmem and no Ctrl.outreg} // ctrl takes maybe data and maybe addr op and modifies nothing
fact div_ops {no Div.outmem} // div takes data and maybe addr? TODO idk why i have it as taking addr. and modifies reg not mem 
// other can do whatever it wants
// TODO should i limit it to one outmem and outreg per instr? I think the relaxations might already handle that?
// wait actually i am limiting them all to set, not some, because perturbation should be able to take off stupid useless operands

fact limited_ops {all i: Instruction | #(i.dataop+i.addrop) <= 2}
fact limited_dataops {all i: Instruction | #(i.dataop) <= 2}
fact limited_outs {all i: Instruction | #(i.outreg) <= 1}
fact limited_outmems {all i: Instruction | #(i.outmem) <= 1}

/** constrain the po relation */
fact po_acyclic { acyclic[po] }									
fact po_prior { all i: Instruction | lone i.(~po) }	
//fact po_transitive { transitive[po] }			// TODO should i be doing this or should it just be a single ordering					
fact po_total { total[po, Instruction] }
// no escaping random instructions
//fact no_extras {Instruction = Load + Store + Ctrl + Div + Other} // this already comes from the abstract extends right

/** constrain the boolean instr states */
// make sure they are in order COMMENTED OUT RN BC JUST CARE ABT RETIRED
//fact handled_exec {handled_pred in executed}
//fact retired_exec {retired in executed}
//fact retired_handled {retired in handled_pred}
// make sure that the retired instructions are contiguous and first in the chain - there is no non-retired followed by retired
fact retired_last {no ^(po :>(Instruction - retired.rBool)).^(po :> (retired.rBool))}
fun last_retired : Instruction {(retired.rBool <: po :> (Instruction-retired.rBool)).(Instruction-retired.rBool)}
fun first_unretired : Instruction {(retired.rBool).(retired.rBool <: po :> (Instruction-retired.rBool))}

/*********************************************************************************
 * perturbed derived sets for dependency tracking
 */

// generate the dependency sets caused by each of the types of instructions (given an instruction)
// function to get the instructions before an instruction (including itself)

// helper - allowed state elements
fun s_p[p: PTag->univ] : State {State - p[RS]}

// loads depend out reg on addr op and ALL MEM LOCATIONS
fun load_dep_p1[i : Instruction, p: PTag->univ] : State -> State {s_p[p] <: (~(addrop)).(iden :> ((i & Load)-p[RI])).(outreg)+((Mem_s - p[RS]) -> ((i & Load) - p[RI]).(outreg)) :> s_p[p]} 
// stores depend mem loc on data op and addr op (did it differently but should do same thing)
fun store_dep_p1[i : Instruction, p: PTag->univ] : State -> State {s_p[p] <: ~(addrop+ dataop).(iden :> ((i & Store)-p[RI])).(outmem) :> s_p[p]}
// div depends outreg on dataop and addrop
fun div_dep_p1[i : Instruction, p: PTag->univ] : State -> State {s_p[p] <: ~(addrop+ dataop).(iden :> ((i & Div)-p[RI])).(outreg ) :> s_p[p]}
// other depends outreg and outmem on dataop and addrop
fun other_dep_p1[i : Instruction, p: PTag->univ] : State -> State {s_p[p] <: ~(addrop + dataop).(iden :> ((i & Other)-p[RI])).(outreg + outmem ) :> s_p[p]}

// loads depend out reg on addr op and ALL MEM LOCATIONS
fun load_dep_p2[i : Instruction, p: PTag->univ->univ] : State -> State {(~(addrop-p[RA])).(iden :> ((i & Load))).(outreg-p[RR])+((Mem_s ) -> ((i & Load) ).(outreg-p[RR]))} 
// stores depend mem loc on data op and addr op (did it differently but should do same thing)
fun store_dep_p2[i : Instruction, p: PTag->univ->univ] : State -> State {~(addrop-p[RA] + dataop-p[RD]).(iden :> ((i & Store))).(outmem-p[RM]) }
// div depends outreg on dataop and addrop
fun div_dep_p2[i : Instruction, p: PTag->univ->univ] : State -> State {~(addrop-p[RA] + dataop-p[RD]).(iden :> ((i & Div))).(outreg - p[RR]) }
// other depends outreg and outmem on dataop and addrop
fun other_dep_p2[i : Instruction, p: PTag->univ->univ] : State -> State {~(addrop + dataop-p[RA]-p[RD]).(iden :> ((i & Other))).(outreg + outmem - p[RR] - p[RM])}


fun dep_p1[i : Instruction, p: PTag->univ] : State -> State {(load_dep_p1[i,p] + store_dep_p1[i,p] + div_dep_p1[i,p] + other_dep_p1[i,p])}
fun dep_p2[i : Instruction, p: PTag->univ->univ] : State -> State {(load_dep_p2[i,p] + store_dep_p2[i,p] + div_dep_p2[i,p] + other_dep_p2[i,p])}

// generate the transmitter sets caused by each of the types of instructions
fun xmit_p1[p: PTag->univ] : Instruction -> State {i_p[p] <: (((Load+Store+Ctrl+Div) <: (addrop))+((Ctrl+Div) <: (dataop))) :> s_p[p]}
fun xmit_p2[p: PTag->univ->univ] : Instruction -> State {(((Load+Store+Ctrl+Div) <: (addrop-p[RA]))+((Ctrl+Div) <: (dataop-p[RD])))}
fun xmit : Instruction -> State {xmit_p1[no_p]}
/*********************************************************************************
 * Perturbed Constraints 
 */

/** constrain what kinds of operands each instruction has */
// I'm actually not going to change these for the perturbations because I don't care about the case where 
//it takes away an operand where there should be one, bc there could just be some other arbitrary state 
//element there and the relaxation would still serve its purpose, and we actually want a simpler model

/** constrain the po relation */
// helper - allowed instruction elements
fun i_p[p: PTag->univ] : Instruction {Instruction - p[RI]}

// fix the hole
fun po_p[p : PTag->univ] : Instruction->Instruction {po.(iden :> (p[RI])).po + (i_p[p] <: po :> i_p[p])}
		
// fact po_total { total[po, Instruction] } this won't change once i fix the hole
fun bef_p1[i : Instruction, p: PTag->univ] : Instruction {((^(po_p[p])).i)}
fun bef_p2[i : Instruction, p: PTag->univ->univ] : Instruction {((^(po)).i)}

/** constrain the boolean instr states */
// make sure they are in order
//fact handled_exec {handled_pred in executed}
//fact retired_exec {retired in executed}
//fact retired_handled {retired in handled_pred}
//TODO- make sure im only generating perturbations for which this is the case. otherwise they fail

// CONSTRAIN PRIVATE STATE
// first instruction doesn't get po pointing to it
fun first_instr_p1[p : PTag->univ] : Instruction {
	i_p[p] - ((i_p[p]).(po_p[p]))
}
// last instruction doesn't get po pointing from it
fun last_instr_p1[p : PTag->univ] : Instruction {
	i_p[p] - ((po_p[p]).(i_p[p]))
}

fact {some last_instr_p1[no_p] & Load}

fun first_instr : Instruction {
	Instruction - Instruction.po
}
// update dependencies
fun updep[s : State, p : PTag->univ, i : Instruction, i2 : Instruction] : State {
	some i2 and i2 in bef_p1[i,p] => (s-State.(dep_p1[i2,p])+s.(dep_p1[i2,p]))
	else s
}
// update dependencies
fun updep[s : State, p : PTag->univ->univ, i : Instruction, i2 : Instruction] : State {
	some i2 and i2 in bef_p2[i,p] => (s-State.(dep_p2[i2,p])+s.(dep_p2[i2,p]))
	else s
}


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
 * Constraints on search space
 */
// will add these as i encounter repetition
// each state is used by something? 
// each instruction has some state?

