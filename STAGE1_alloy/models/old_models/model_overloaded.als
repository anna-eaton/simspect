module model_overloaded

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

// top relaxations are unary, instruction or state
// basically just decimate any state there could be (i think this is all the options)
one sig RI extends PTag {} // remove instr
one sig RS extends PTag {} // remove state element (reg or mem)

// everything below here is 2-ary thing attached to the tag
one sig RIB extends PTag {} // remove boolean on the state, points to instr->boolean pair
// remove operands
one sig RIA extends PTag {} // remove inaddr from instr when legal 
one sig RIR extends PTag {} // remove inreg from instr when legal 
one sig RIM extends PTag {} // remove inmem from instr when legal 
one sig ROR extends PTag {} // remove outreg from instr when legal
one sig ROM extends PTag {} // remove outmem from instr when legal

// no relaxations applied, constant used to generate the base model without perturbation
fun no_p : PTag->univ->univ {
  (PTag->univ->univ) - (PTag->univ->univ) // nothin here :0
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
	inreg: set Reg_s,
	inaddr: set Reg_s,
	outreg: set Reg_s,
	inmem: set Mem_s,
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
fact load_ops {no Load.inreg and no Load.outmem} // load takes addr and modifies reg, doesn't take data or modify memory
fact store_ops {no Store.outreg} // store takes data, addr and modifies mem, not reg
fact ctrl_ops {no Ctrl.outmem and no Ctrl.outreg} // ctrl takes maybe data and maybe addr op and modifies nothing
fact div_ops {no Div.outmem} // div takes data and maybe addr? TODO idk why i have it as taking addr. and modifies reg not mem 
// other can do whatever it wants
// TODO should i limit it to one outmem and outreg per instr? I think the relaxations might already handle that?
// wait actually i am limiting them all to set, not some, because perturbation should be able to take off stupid useless operands

fact limited_ops {all i: Instruction | #(i.inreg+i.inaddr) <= 2}
fact limited_inregs {all i: Instruction | #(i.inreg) <= 2}
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
fun s_p[p: PTag->univ->univ] : State {State - uu[p][RS]}

// loads depend out reg on addr op and ALL MEM LOCATIONS
fun load_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: (~(inaddr-p[RIA])).(iden :> ((i & Load)-uu[p][RI])).(outreg-p[ROR])+((Mem_s - uu[p][RS]) -> ((i & Load) - uu[p][RI]).(outreg-p[ROR])) :> s_p[p]} 
// stores depend mem loc on data op and addr op (did it differently but should do same thing)
fun store_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: ~(inaddr-p[RIA]+ inreg-p[RIR]).(iden :> ((i & Store)-uu[p][RI])).(outmem-p[ROM]) :> s_p[p]}
// div depends outreg on inreg and inaddr
fun div_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: ~(inaddr-p[RIA] + inreg-p[RIR]).(iden :> ((i & Div)-uu[p][RI])).(outreg - p[ROR]) :> s_p[p]}
// other depends outreg and outmem on inreg and inaddr
fun other_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: ~(inaddr + inreg-p[RIA]-p[RIR]).(iden :> ((i & Other)-uu[p][RI])).(outreg + outmem  - p[ROR] - p[ROM]) :> s_p[p]}

fun dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {(load_dep_p[i,p] + store_dep_p[i,p] + div_dep_p[i,p] + other_dep_p[i,p])}

// generate the transmitter sets caused by each of the types of instructions
fun xmit_p[p: PTag->univ->univ] : Instruction -> State {i_p[p] <: (((Load+Store+Ctrl+Div) <: (inaddr-p[RIA]))+((Ctrl+Div) <: (inreg-p[RIR]))) :> s_p[p]}
fun xmit : Instruction -> State {xmit_p[no_p]}

/*********************************************************************************
 * Perturbed Constraints 
 */

/** constrain what kinds of operands each instruction has */
// I'm actually not going to change these for the perturbations because I don't care about the case where 
//it takes away an operand where there should be one, bc there could just be some other arbitrary state 
//element there and the relaxation would still serve its purpose, and we actually want a simpler model

/** constrain the po relation */
// helper - allowed instruction elements
fun i_p[p: PTag->univ->univ] : Instruction {Instruction - uu[p][RI]}

// fix the hole
fun po_p[p : PTag->univ->univ] : Instruction->Instruction {po.(iden :> (uu[p][RI])).po + (i_p[p] <: po :> i_p[p])}
		
// fact po_total { total[po, Instruction] } this won't change once i fix the hole
fun bef_p[i : Instruction, p: PTag->univ->univ] : Instruction {((^(po_p[p])).i)}

/** constrain the boolean instr states */
// make sure they are in order
//fact handled_exec {handled_pred in executed}
//fact retired_exec {retired in executed}
//fact retired_handled {retired in handled_pred}
//TODO- make sure im only generating perturbations for which this is the case. otherwise they fail

// CONSTRAIN PRIVATE STATE
// first instruction doesn't get po pointing to it
fun first_instr_p[p : PTag->univ->univ] : Instruction {
	i_p[p] - ((i_p[p]).(po_p[p]))
}
// last instruction doesn't get po pointing from it
fun last_instr_p[p : PTag->univ->univ] : Instruction {
	i_p[p] - ((po_p[p]).(i_p[p]))
}

fact {some last_instr_p[no_p] & Load}

fun first_instr : Instruction {
	Instruction - Instruction.po
}

// update dependencies
fun updep[s : State, p : PTag->univ->univ, i : Instruction, i2 : Instruction] : State {
	some i2 and i2 in bef_p[i,p] => (s-State.(dep_p[i2,p])+s.(dep_p[i2,p]))
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
 * Helper functions to overload the unary relaxations so we can relax both sets and edges
 */
// unary: p : PTag -> univ
// lift unary
fun lu[p: PTag->univ] : PTag->univ->univ {
    p -> univ               // produces ternary relation
}
// unpack unary
fun uu[q: PTag->univ->univ] : PTag->univ {
    // project away the last column
    PTag->univ & q.univ     // or equivalently: q.univ
}


/*********************************************************************************
 * Constraints on search space
 */
// will add these as i encounter repetition
// each state is used by something? 
// each instruction has some state?

