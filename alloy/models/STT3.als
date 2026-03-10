/*********************************************************************************
 *
 * STT DEFENSE — PROGRAM LENGTH 3
 *
 * Opens STT_def.als and adds 3-instruction-specific symmetry-breaking + run.
 *
 ********************************************************************************/

open STT_def

-- Fixed position atoms (one sig = no atom permutations)
one sig IX0 extends InstrPos {}  -- spo position 0 (first)
one sig IX1 extends InstrPos {}  -- spo position 1
one sig IX2 extends InstrPos {}  -- spo position 2 (last)

-- Static ordering: IX0 < IX1 < IX2
pred lt_ix[a, b: univ] {
	(a = IX0 and b in IX1 + IX2) or (a = IX1 and b = IX2)
}

-- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third
fact idx_matches_spo {
	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
}

-- every position atom is used (forces exactly 3 instructions)
fact idx_surjective { (IX0 + IX1 + IX2) = Instruction.idx }

run gen_lit {
	gen_useful_litmus
} for 5 but exactly 3 Instruction, exactly 1 rBool, exactly 1 cBool
