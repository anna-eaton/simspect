/*********************************************************************************
 * Specific defense model STT (non-spec on commit) — the STT_6.als defense block
 * (STT_6.als:320-332), ported to the SKELETON_u interface with the SAME semantics
 * (location-based protection; checked equal to STT_6.als under every perturbation
 * gen_useful_litmus / gen_core use: queries/q_sem_eq.als). Each line carries the
 * STT_6.als original as a comment. This is the plug-in demo block, not a proposal
 * for a new STT semantics (that is the STT agent's STT_6_u.als).
 */

// (1) speculation contract — unchanged
//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])}
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}

// (2) protection set
// seed. STT_6.als: fun hardware_protection_policy: State {Mem_s}
fun hardware_protection_policy[p: PTag->univ] : Operand {ops_of[Mem_s]}
// step. STT_6.als: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate
// (a load that reached its visibility point makes its whole LOCATION public;
//  nonspeculative_p = no_unresolved_brs_bf_or_is_p on loads, checked in q_sem_eq)
fun prot_set_propagation_p[p: PTag->univ, i: Instruction, o: Operand] : Operand {
	o - ops_of[(Loads & nonspeculative_p[p] & i).inmem.opstate]
}
// flow. STT_6.als: implicit (secure_speculation_scheme_p closes over ^(op_edges_p[p]))
fun prot_flow_p[p: PTag->univ] : Operand->Operand {op_edges_p[p]}

// (3) leakage function — unchanged
//fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
