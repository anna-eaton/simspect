/*********************************************************************************
 *
 * STT DEFENSE LAYER
 *
 * Opens base.als and adds STT (committed + speculate-past) defense definitions.
 * "STT" here: speculates only when uncommitted AND no older unresolved branch/mem.
 *
 * Opens this module in a per-length file to get a runnable model.
 *
 * Does NOT contain:
 *   - InstrPos atoms (IX0, IX1, ...) — defined per-length
 *   - lt_ix, idx_matches_spo, idx_surjective — defined per-length
 *   - run command — defined per-length
 *
 ********************************************************************************/

open base

/*********************************************************************************
 * STT defense definitions
 */

fun leakage_function : Operand {
	Loads.inaddr + (Branchxs + Otherxs).inreg
}

fun hardware_protection_policy : State { Mem_s }

fun speculation_contract_p[p: PTag->univ] : Instruction {
	uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])
}

fun prot_set_propagation_p[p: PTag->univ, i: Instruction, s: State] : State {
	s - (Loads & committed_p[p] & i).inaddr.opstate
}

/*********************************************************************************
 * Derived perturbed quantities
 */

fun leakage_function_p[p: PTag->univ] : Operand {
	leakage_function & o_p[p]
}

fun speculative_xmit_p[p: PTag->univ] : Operand {
	leakage_function_p[p] <: speculation_contract_p[p].operands
}

fun a[p: PTag->univ, i: Instruction, s: State] : State {
	prot_set_propagation_p[p, i, s]
}

-- 5-level chain: valid for n ≤ 5 (extra levels are no-ops when instruction set is exhausted)
fun last_committed_protset_p[p: PTag->univ] : State {
	a[p, f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
		a[p, f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
			a[p, f[p].(spo_p[p]).(spo_p[p]),
				a[p, f[p].(spo_p[p]),
					a[p, f[p], hardware_protection_policy]
				]
			]
		]
	]
}

pred secure_speculation_scheme_p[p: PTag->univ] {
	(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and
	(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p])
}

/*********************************************************************************
 * Litmus test generation predicate
 */

pred gen_useful_litmus {
	not secure_speculation_scheme_p[no_p]

	all i: resolved | secure_speculation_scheme_p[RR->i] or secure_speculation_scheme_p[RC->first_uncommitted]

	all s: State | secure_speculation_scheme_p[RS->s]
}
