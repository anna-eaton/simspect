/*********************************************************************************
 * Defines the specific defense within the model space!! 
 */
open model_overloaded

/*********************************************************************************
 * Specific defense model
 */

// EDIT THESE
//fun speculation_contract_p[p: PTag->univ->univ] : Instruction {i_p[p] - (retired.rBool)} // example : all retired instructions are non-spec
fun speculation_contract_p[p: PTag->univ->univ] : Instruction {i_p[p] - (retired.rBool+p[RIB].rBool)} // example : all retired instructions are non-spec
fun hardware_protection_policy_p[p: PTag->univ->univ] : State {Mem_s - uu[p][RS]} // example : all regs (TODO was this supposed to be mem)
//fun hardware_protection_policy_p[p: PTag->univ->univ] : State {Mem_s} // example : all regs (TODO was this supposed to be mem)
//fun leakage_function_p[p: PTag->univ] : Instruction -> State {xmit_p1[p]} // example : all transmitters
fun leakage_function_p[p: PTag->univ->univ] : Instruction -> State {xmit_p[p]} // example : all transmitters


// SHOULDN'T HAVE TO TOUCH HERE DOWN

/*********************************************************************************
 * Rest of model
 */

// fun speculatively_private_p[i:Instruction,p:PTag->univ] : State {
// 	// can handle up to 8 instrs (ewww disgusting don't even look)
// 	updep[updep[updep[updep[updep[updep[updep[updep[hardware_protection_policy_p[p],p,i,first_instr],p,i,first_instr.po],p,i,first_instr.po.po],p,i,first_instr.po.po.po],p,i,first_instr.po.po.po.po],p,i,first_instr.po.po.po.po.po],p,i,first_instr.po.po.po.po.po.po],p,i,first_instr.po.po.po.po.po.po.po]
// }
// TODO I really really hate this, would also like to clean up duplication asap
fun speculatively_private_p[i:Instruction,p:PTag->univ->univ] : State {
	// can handle up to 8 instrs (ewww disgusting don't even look)
	updep[updep[updep[updep[updep[updep[updep[updep[hardware_protection_policy_p[p],p,i,first_instr],p,i,first_instr.po],p,i,first_instr.po.po],p,i,first_instr.po.po.po],p,i,first_instr.po.po.po.po],p,i,first_instr.po.po.po.po.po],p,i,first_instr.po.po.po.po.po.po],p,i,first_instr.po.po.po.po.po.po.po]
}

// pred secure_speculation_scheme_p1[p: PTag->univ] {
//   (all i : speculation_contract_p[p] | no (speculatively_private_p[i,p] & i.(leakage_function_p[p])))
// }
pred secure_speculation_scheme_p[p: PTag->univ->univ] { 
  (all i : speculation_contract_p[p] | no (speculatively_private_p[i,p] & i.(leakage_function_p[p])))
}

// for visualization purposes make a set of privates at each instruction
fact {
	all i : Instruction |
		i.private_s = speculatively_private_p[i,no_p]
}

/*********************************************************************************
 * Perturbation function
 */
let gen_useful_litmus {
  not secure_speculation_scheme_p[no_p]

  // All events must be relevant
  // this means if removing the event changes nothing the overall trace is thrown out
  all i: Instruction | secure_speculation_scheme_p[lu[RI->i]]
  all s: State | secure_speculation_scheme_p[lu[RS->s]]
  all i: Instruction, s: State |
    (i -> s in inaddr) => secure_speculation_scheme_p[RIA->i->s]
  all i: Instruction, s: State |
    (i -> s in inreg) => secure_speculation_scheme_p[RIR->i->s]
  all i: Instruction, s: State |
    (i -> s in outreg) => secure_speculation_scheme_p[ROR->i->s]
  all i: Instruction, s: State |
    (i -> s in outmem) => secure_speculation_scheme_p[ROM->i->s]

  // right now this is just touching retired, can mess with other booleans later.
  all b: first_unretired | secure_speculation_scheme_p[RIB->b->rBool]
}


/*********************************************************************************
 * Run
 */

run gen_lit {
  gen_useful_litmus
} for 5 but exactly 3 Instruction

// whatever
// for 4 but 2 Instruction
// for 10 but exactly 2 State, exactly 2 Instruction
