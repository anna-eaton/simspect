/*********************************************************************************
 * STT_6_u defense block (STT agent, 2026-11-09) in the SKELETON_u interface. DRAFT, NOT APPROVED.
 * Same semantics as proposed/ultimate/STT_6_u.als (which carries the full citations); only the
 * spelling is adapted to SKELETON_u (perturbed fields, flagged_p = protset.*prot_flow).
 * FLAVOR = spectre. The stl flavor is blocks/STT_6_u_stl.block.als (selector line + 2 facts).
 * Sources: yu-2019-stt.pdf p5 Sec. 6.1, p6 Sec. 6.2-6.3, p7 Sec. 6.4.1, p9 Sec. 7.1;
 * defense_src/stt_e3283b9 rob_impl.hh:489-495, 518-520, 709-724, 809-813; base_dyn_inst.hh:675-676.
 */
// (1) speculation contract: Spectre VP = every older control-flow instruction resolved   -- [u-2]
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
// (2) seed: the memory read of every UNSAFE load (instance-based; "If a load is unsafe, its output is
//     always tainted", p6)                                                                 -- [u-4]
fun hardware_protection_policy[p: PTag->univ] : Operand {spec_loads_p[p].(inmem_p[p])}
// (2) step: identity. Untaint is the contract (a value is tainted iff some load in its backward data
//     cone is unsafe = its youngest root of taint is before the VP); no declassification, no reveal. -- [u-5]
fun prot_set_propagation_p[p: PTag->univ, i: Instruction, o: Operand] : Operand {o}
// (2) flow: every rf + ddi edge (output tainted if any input is tainted, p6 Sec. 6.2)
fun prot_flow_p[p: PTag->univ] : Operand->Operand {op_edges_p[p]}
// (3) leakage function: load address (explicit) + transmitting branch predicate (implicit); unchanged -- [u-6]
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
