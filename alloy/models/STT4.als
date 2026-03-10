/*********************************************************************************
 *
 * STT DEFENSE — PROGRAM LENGTH 4
 *
 * Opens STT_def.als and adds 4-instruction-specific symmetry-breaking + run.
 *
 ********************************************************************************/

open STT_def

-- Fixed position atoms (one sig = no atom permutations)
one sig IX0 extends InstrPos {}  -- spo position 0 (first)
one sig IX1 extends InstrPos {}  -- spo position 1
one sig IX2 extends InstrPos {}  -- spo position 2
one sig IX3 extends InstrPos {}  -- spo position 3 (last)

-- Static ordering: IX0 < IX1 < IX2 < IX3
pred lt_ix[a, b: univ] {
	(a = IX0 and b in IX1 + IX2 + IX3) or
	(a = IX1 and b in IX2 + IX3) or
	(a = IX2 and b = IX3)
}

-- idx rank mirrors spo rank
fact idx_matches_spo {
	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
}

-- every position atom is used (forces exactly 4 instructions)
fact idx_surjective { (IX0 + IX1 + IX2 + IX3) = Instruction.idx }

run gen_lit {
	gen_useful_litmus
} for 7 but exactly 4 Instruction, exactly 1 rBool, exactly 1 cBool
