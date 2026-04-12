module generated_model

/*********************************************************************************
 \* 
AUTO GENERATED TEMPLATE!! DO NOT EDIT BY HAND. INSTEAD EDIT model_template.als and syntax.jsonc
THIS IS THE TEMPLATE THAT TAKES SYNTAX.JSON AND MAKES AN EXECUTION MODEL

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

fun no_p : PTag->univ->univ { // no_p - constant for no perturbation
  (PTag->univ->univ) - (PTag->univ->univ) // nothin here :0
}

/*********************************************************************************
 * Basic execution model
 */

//sig eBool {} // executed
//sig hBool {} // handled_pred
sig rBool {} // retired

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
{% for ins in instructions %}
sig {{ins}} extends Instruction {}
{% endfor %}


/*********************************************************************************
 * Constraints
 */

// auto generated: DO NOT EDIT BY HAND
// enforces allowed operands per instruction type

{% for inst, allowed in operand_constraints.items() %}
fact {{inst | lower}}_ops {
  {% for op in all_operands %}
    {% if op not in allowed %}
      no {{inst}}.{{op}}
    {% endif %}
  {% endfor %}
}
{% endfor %}


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
fun s_p[p: PTag->univ->univ] : State {State - uu[p][RS]}

// loads depend out reg on addr op and ALL MEM LOCATIONS
fun load_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: (~(addrop-p[RA])).(iden :> ((i & Load)-uu[p][RI])).(outreg-p[RR])+((Mem_s - uu[p][RS]) -> ((i & Load) - uu[p][RI]).(outreg-p[RR])) :> s_p[p]} 
// stores depend mem loc on data op and addr op (did it differently but should do same thing)
fun store_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: ~(addrop-p[RA]+ dataop-p[RD]).(iden :> ((i & Store)-uu[p][RI])).(outmem-p[RM]) :> s_p[p]}
// div depends outreg on dataop and addrop
fun div_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: ~(addrop-p[RA] + dataop-p[RD]).(iden :> ((i & Div)-uu[p][RI])).(outreg - p[RR]) :> s_p[p]}
// other depends outreg and outmem on dataop and addrop
fun other_dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {s_p[p] <: ~(addrop + dataop-p[RA]-p[RD]).(iden :> ((i & Other)-uu[p][RI])).(outreg + outmem  - p[RR] - p[RM]) :> s_p[p]}

fun dep_p[i : Instruction, p: PTag->univ->univ] : State -> State {(load_dep_p[i,p] + store_dep_p[i,p] + div_dep_p[i,p] + other_dep_p[i,p])}

// generate the transmitter sets caused by each of the types of instructions
fun xmit_p[p: PTag->univ->univ] : Instruction -> State {i_p[p] <: (((Load+Store+Ctrl+Div) <: (addrop-p[RA]))+((Ctrl+Div) <: (dataop-p[RD]))) :> s_p[p]}
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