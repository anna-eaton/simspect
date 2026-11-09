/*********************************************************************************
 * STT_6_u defense block, FLAVOR = stl (STT agent, 2026-11-09), SKELETON_u interface. DRAFT.
 * = blocks/STT_6_u.block.als except the clause-1 selector (store-address shadow instead of
 * branch shadow) and two tagged contract side-condition facts. Recon-STT store shadows:
 * gem5-recon decode.cc:686-695 (insertStore), shadow_tracker.cc (freed on effAddrValid()).
 */
// (1) speculation contract: after an older store whose ADDRESS is unresolved                -- [u-2]
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_strs_p[p]}
// (1') side conditions (generation facts, evaluated on the unperturbed instance via no_p)    -- [u-3]
fact u_stl_no_branch_speculation {no (unresolved_p[no_p] & Branches)}
fact u_stl_alias_atom {
	all s: unresolved_p[no_p] & Stores | some l: uncommitted_p[no_p] & Loads |
		some (s.(outmem_p[no_p]).opstate & l.(inmem_p[no_p]).opstate) and s->l in ^(spo_p[no_p]) and l in xm + xm.^(~(spo_p[no_p]))
		and no s2: Stores - s | some (s2.(outmem_p[no_p]).opstate & s.(outmem_p[no_p]).opstate) and s->s2 in ^(spo_p[no_p]) and s2->l in ^(spo_p[no_p])
}
// (2) seed / step / flow: as the spectre flavor                                              -- [u-4] [u-5]
fun hardware_protection_policy[p: PTag->univ] : Operand {spec_loads_p[p].(inmem_p[p])}
fun prot_set_propagation_p[p: PTag->univ, i: Instruction, o: Operand] : Operand {o}
fun prot_flow_p[p: PTag->univ] : Operand->Operand {op_edges_p[p]}
// (3) leakage function: unchanged                                                            -- [u-6]
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
