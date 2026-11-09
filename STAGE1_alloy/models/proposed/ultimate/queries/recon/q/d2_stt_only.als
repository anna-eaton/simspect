// =============================================================================
// STT_6_u.als -- ULTIMATE STT draft (STT agent, 2026-11-09). DRAFT, NOT APPROVED.
// New file, derived from STT_6.als (sha256 7a6ac4c0a098c4dc0e24a4a1bbf867f1266c491b64bdd356026ec017d5b4198c, unchanged) by
// proposed/ultimate/queries/stt/make_stt_u.py. Every line that differs from STT_6.als carries
// a `-- [u-n]` tag; everything else is byte-identical.
//   [u-0] this header.
//   [u-1] SKELETON (4 places, the same Operand form the approved SPT_6_oneLP_v2.als uses):
//         the protection set is a set of OPERANDS, not States, so `a`,
//         `last_committed_protset_p`, `secure_speculation_scheme_p` and `tag_xm` drop the
//         .(~opstate) lift. Needed because a State-typed set cannot protect one load's read of
//         word A and not another's (audit R-1, the one UNSOUND clause found 2026-11-08).
//   [u-2] clause 1 (speculation contract): STT-Spectre visibility point, unchanged from
//         STT_6.als:325; the other flavors are listed next to it as one-line selectors.
//   [u-3] flavor facts: none in this (spectre) flavor.
//   [u-4] clause 2 sources: the memory read of every UNSAFE load (instance-based taint).
//   [u-5] clause 2 propagation: identity (no program-order untaint; forward taint is the
//         skeleton's ^op_edges closure, untaint is the contract).
//   [u-6] clause 3 (leakage function): unchanged from STT_6.als:328.
// Semantically [u-1]+[u-4]+[u-5] = proposed/STT_6_v2.als (model-fixes, 2026-11-08).
// Evidence and decisions: the STT agent's final report (2026-11-09); queries in
// proposed/ultimate/queries/stt/ (runs.log).
// =============================================================================


/*********************************************************************************
 *
CLEAN MODEL WITH KIND-FIELD REFACTORING

Instruction is a single concrete sig with a `kind: one InstrType` field
instead of abstract + subsigs.  This lets util/ordering[Instruction] work,
enabling in-model symmetry breaking that eliminates duplicate instances.

 */

-- util/ordering[Instruction] as IOrd  -- Alloy 6: pre-binding fails in complex models

/*********************************************************************************
 * Basic execution model
 */

sig rBool {} // resolved
sig cBool {} // committed
sig tBool {} // transmitter - if flagged this is the bad spec transmitter

// state sigs
abstract sig State {}
sig Mem_s extends State {}
sig Reg_s extends State {}

// instruction kind tags (one sig = exactly one atom each)
abstract sig InstrType {}
one sig TLoad    extends InstrType {} // load from memory
one sig TStore   extends InstrType {} // store to memory
one sig TBranchn extends InstrType {} // ctrl/br op, doesnt xmit
one sig TBranchx extends InstrType {} // ctrl/br op, xmits
one sig TOthern  extends InstrType {} // ALU/reg->reg, doesnt xmit
one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits

// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)
one sig IX0 {} -- spo position 0 (first)å
one sig IX1 {} -- spo position 1
one sig IX2 {} -- spo position 2
one sig IX3 {} -- spo position 2
one sig IX4 {} -- spo position 2
one sig IX5 {} -- spo position 2

// single concrete instruction sig
sig Instruction {
	kind: one InstrType,
	idx: one (IX0 + IX1 + IX2 + IX3 + IX4 + IX5),  -- bijection to fixed position atoms

	spo: lone Instruction,

	// state elements define what goes in and out of each instr
	inreg: set Inreg,
	inaddr: set Inaddr, // only relevant for loads and stores
	outreg: set Outreg,
	inmem: set Inmem,
	outmem: set Outmem,

	// boolean variables showing state of instr
	isresolved: lone rBool,
	iscommitted: lone cBool,
	isxm: lone tBool,
}

// boolean state sets
fun committed : Instruction {iscommitted.cBool}
fun resolved : Instruction {isresolved.rBool}
fun xm : Instruction {isxm.tBool}

// kind-based instruction sets (replaces subsig membership)
fun Loads    : Instruction { kind.TLoad    }
fun Stores   : Instruction { kind.TStore   }
fun Branchns : Instruction { kind.TBranchn }
fun Branchxs : Instruction { kind.TBranchx }
fun Otherns  : Instruction { kind.TOthern  }
fun Otherxs  : Instruction { kind.TOtherx  }

// operands s.t. we can have operand->operand dependency graphs
abstract sig Operand {
	opstate: one State,
	rf: set Operand,
	ddi: set Operand,
}

sig Inreg extends Operand {}
sig Inaddr extends Operand {}
sig Inmem extends Operand {}
sig Outreg extends Operand {}
sig Outmem extends Operand {}

fun ins : Instruction -> Operand {inreg+inmem+inaddr}
fun outs : Instruction -> Operand {outreg+outmem}
fun operands : Instruction -> Operand {ins+outs}

/*********************************************************************************
 * Constraints
 */
// there are no other operands that arent of instructions
fact no_extra_ops {no (Operand - Instruction.operands)}

fact no_extra_State {no State - Operand.opstate}

// all instructions have operands (so we dont have to relax instructions)
// fact no_extra_Instructions {no Instruction - operands.Operand}

// each operand only belongs to one instruction
fact limited_instr_per_op {all o: Operand | #(o.(~operands)) = 1}

// make the operands have the right flavor state
fact ir_s {no (Inreg.opstate & Mem_s)}
fact ia_s {no (Inaddr.opstate & Mem_s)}
fact im_s {no (Inmem.opstate & Reg_s)}
fact or_s {no (Outreg.opstate & Mem_s)}
fact om_s {no (Outmem.opstate & Reg_s)}

// constrain what kinds of operands each instruction has
fact ld_ops   {no Loads.(inreg+outmem)}                          // load takes addr and mem and modifies reg
fact str_ops  {no Stores.(inmem+outreg)}                         // store takes addr and reg and modifies mem
fact other_ops {no (Otherns+Otherxs).(inaddr+inmem+outmem)}     // other is some nonmem instr
fact br_ops   {no (Branchns+Branchxs).(inaddr+inmem+outmem+outreg)} // branch is some control (no output)

fact limited_inregs {all i: Instruction | #(i.inreg) <= 2}
fact limited_inaddrs {all i: Instruction | #(i.inaddr) <= 1}
fact limited_inmems {all i: Instruction | #(i.inmem) <= 1}
fact limited_ins {all i: Instruction | #(i.ins) <= 2}
fact limited_outs {all i: Instruction | #(i.(outreg+outmem)) <= 1}

/** constrain the spo relation */
fact spo_acyclic { acyclic[spo] }
fact spo_prior { all i: Instruction | lone i.(~spo) }
fact spo_total { total[spo, Instruction] }

/** constrain the boolean instr states */
fact committed_resolved {committed in resolved}
fun uncommitted : Instruction {Instruction - committed}
fun unresolved : Instruction {Instruction - resolved}
fact committed_last {no ^(spo :>uncommitted).^(spo :> committed) and (no uncommitted <: ^spo :> committed)}
fun last_committed : Instruction {(committed <: spo :> uncommitted).uncommitted}
fun first_uncommitted : Instruction {(some committed) => committed.(committed <: spo :> uncommitted) else first_instr}

fun no_unresolved_brs : Instruction {
	Instruction - (uncommitted & (Branchxs+Branchns)).(^(spo))
}
fun no_unresolved_mem : Instruction {
	Instruction - (uncommitted & (Loads+Stores)).(^(spo))
}

fun first_instr : Instruction {Instruction - Instruction.spo}



/*********************************************************************************
 * GL-IFT-ish ddi edges, + rf edges
 */
fact constrainddi {no ddi - (~ins).outs}
fact constrainrf {rf in (Instruction.outs -> Instruction.ins)}
fact one_entering_rf {all o: Operand | lone rf.o}
fact unidirectional_rf {acyclic[(operands).rf.(~operands) + spo]}
fact same_state_rf {no ((~opstate).rf.opstate - iden)}

// [Option A] rf must read from the MOST-RECENT writer of the state:
// forbid another writer of the same state spo-between an rf producer and its use.
fact rf_from_most_recent_writer {
  all prod: Instruction.outs, use: prod.rf |
    no other: (Instruction.outs - prod) |
        other.opstate = prod.opstate
        and (prod.(~operands))  -> (other.(~operands)) in ^spo
        and (other.(~operands)) -> (use.(~operands))   in ^spo
}

fact ld_ddi    {no (Loads.operands <: ddi) - (Inmem->Outreg)}
fact str_ddi   {no (Stores.operands <: ddi) - (Inreg->Outmem)}
fact other_ddi {no ((Otherns+Otherxs).operands <: ddi) - (Inreg->Outreg)}
fact br_ddi    {no ((Branchxs+Branchns).operands <: ddi)}

/*********************************************************************************
 * Alloy shortcuts
 */
pred irreflexive[rel: Instruction->Instruction]       { no iden & rel }
pred acyclic[rel: Instruction->Instruction]           { irreflexive[^rel] }
pred total[rel: Instruction->Instruction, bag: Instruction] {
  all disj e0, e1: bag | e0->e1 in ^rel + ~(^rel)
  acyclic[rel]
}


/*********************************************************************************
 * Perturbations
 */
abstract sig PTag {}
one sig RO extends PTag {} // remove operand
one sig RC extends PTag {} // make instruction committed when it previously wasnt
one sig RR extends PTag {} // make instruction resolved when it previously wasnt
one sig RI extends PTag {} // remove instruction
one sig RS extends PTag {} // remove state
fun no_p : PTag->univ {
  (PTag->univ) - (PTag->univ)
}


/*********************************************************************************
 * Perturbed model
 */
fun committed_p[p: PTag->univ] : Instruction {committed + p[RC] - p[RI]}
fun uncommitted_p[p: PTag->univ] : Instruction {uncommitted - p[RC] - p[RI]}
fun resolved_p[p: PTag->univ] : Instruction {resolved + p[RR] - p[RI]}
fun unresolved_p[p: PTag->univ] : Instruction {unresolved - p[RR] - p[RI]}
fun last_committed_p[p: PTag->univ] : Instruction { ((committed_p[p]) <: spo :> (uncommitted_p[p])).(uncommitted_p[p])}
fun first_uncommitted_p[p: PTag->univ] : Instruction {committed_p[p].(committed_p[p] <: spo :> uncommitted_p[p])}

fact committed_in_resolved {no (unresolved & committed)} // make sure all committed instructions are resolved

fun i_p[p: PTag->univ] : Instruction {Instruction - p[RI]}
fun o_p[p: PTag->univ] : Operand {i_p[p].operands :> (Operand - p[RO] - opstate.(p[RS]))}

fun spo_p[p : PTag->univ] : Instruction->Instruction {spo.(iden :> (p[RI])).spo + (i_p[p] <: spo :> i_p[p])}

fun fix_rf_hole_p[p : PTag->univ] : Operand -> Operand {(opstate.Reg_s<:(rf.(ddi:>(p[RI].operands)).rf):>opstate.Reg_s) + (opstate.Mem_s<:(rf.(ddi:>(p[RI].operands)).rf):>opstate.Mem_s)}

fun rf_p[p : PTag->univ] : Operand -> Operand {o_p[p]<:rf:>o_p[p] + fix_rf_hole_p[p]}
fun ddi_p[p : PTag->univ] : Operand -> Operand {o_p[p]<:ddi:>o_p[p]}

fun op_edges_p[p: PTag->univ] : Operand -> Operand {rf_p[p] + ddi_p[p]}

fun f[p: PTag->univ] : Instruction {(i_p[p]) - (i_p[p]).(spo_p[p])}

fun leakage_function_p[p: PTag->univ] : Operand {leakage_function & o_p[p]}

fun speculative_xmit_p[p: PTag->univ] : Operand {leakage_function_p[p] <: speculation_contract_p[p].operands}

fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand { prot_set_propagation_p[p,i,o]} -- [u-1] Operand-typed protection set
fun last_committed_protset_p[p: PTag->univ] : Operand { -- [u-1]
		a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
a[p,f[p].(spo_p[p]).(spo_p[p]),
			a[p,f[p].(spo_p[p]),
				a[p,f[p],hardware_protection_policy[p]] -- [u-1]
			]
	]
]]]]
}

fun has_unresolved_brs_p[p: PTag->univ] : Instruction {
	((unresolved_p[p] & (Branchxs+Branchns)).(^(spo_p[p]))) // all the instructions that come after a speculative branch
}
// all the instructions minus the ones with unresolved branches earlier on
fun no_unresolved_brs_p[p: PTag->univ] : Instruction {
	// i_p[p] - (uncommitted_p[p] & (Branchxs+Branchns)).(^(spo_p[p]))
	i_p[p] - has_unresolved_brs_p[p]
}

fun no_unresolved_brs_bf_or_is_p[p: PTag->univ] : Instruction {
	no_unresolved_brs_p[p] - (unresolved_p[p] & (Branchxs+Branchns)) // there are no unresolvd brs bf and it isnt itself an unresolved br
}

fun no_unresolved_mem_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted & (Loads+Stores)).(^(spo))
}

pred secure_speculation_scheme_p[p: PTag->univ] {
	(no (last_committed_protset_p[p] & speculative_xmit_p[p])) and -- [u-1] no .(~opstate) lift
	(no last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) -- [u-1]
}

// make sure there is some overlap in the end btw xm and speculative xmit
//fact tag_xm {some xm & speculative_xmit_p[xm]}
fact one_xm {#(xm) = 1}
fact tag_xm { 
	(some (last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands)) or -- [u-1]
	(some last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands) -- [u-1]
}

/*********************************************************************************
 * Symmetry breaking — works because Instruction is now a concrete sig
 */

-- idx bijection: each instruction gets a unique fixed position atom
fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }
fact idx_surjective { (IX0 + IX1 + IX2 + IX3 + IX4 + IX5) = Instruction.idx }

-- IX0 < IX1 < IX2 is a fixed static ordering (no atom permutations possible)
pred lt_ix[a, b: univ] { (a=IX0 and b in IX1+IX2+IX3+IX4+IX5) 
				or (a=IX1 and b in IX2+IX3+IX4+IX5)
				or (a=IX2 and b in IX3+IX4+IX5)
				or (a=IX3 and b in IX4+IX5)
				or (a=IX4 and b=IX5)

}

-- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third
fact idx_matches_spo {
	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
}


/*********************************************************************************
 * Run
 */
let gen_useful_litmus {
  not secure_speculation_scheme_p[no_p]

  //all i: resolved | secure_speculation_scheme_p[RR->i] or secure_speculation_scheme_p[RC->first_uncommitted]
  // resolution-min on all unresolved EXCEPT the boundary instr
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  // boundary instr (first_uncommitted): necessity tested by commit AND resolve together
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]

  all s: State | secure_speculation_scheme_p[RS->s]
}

fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake

run gen_lit {
  gen_useful_litmus
  q
} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool


/*********************************************************************************
 * Specific defense model: STT, ultimate draft (STT_6_u)                       -- [u-2..u-6]
 * Sources read 2026-11-09: paper ~/Documents/quail/sources/papers/yu-2019-stt.pdf (Yu et al.,
 * MICRO'19); code ~/Documents/stanford/trippel/defense_src/stt_e3283b9/src (= /work/stt;
 * /work/stt-master @5bf4110 differs only in iew_impl.hh, the 18e304f pending-squash fix).
 * STT in one line: every load is an access instruction; while it is UNSAFE (before its
 * visibility point) its output is tainted; taint follows every register/memory data flow;
 * a value is untainted as soon as its youngest root of taint reaches the visibility point;
 * a transmitter (a load's address, a branch's predicate) must not act on tainted data.
 */

// ---- Clause 1: speculation contract (which instructions are unsafe) --------------------------
// [u-2] Spectre-model visibility point. Paper p5 Sec. 6.1: "In the Spectre model, an instruction
// has reached the visibility point if all older control-flow instructions have resolved".
// gem5: ROB::updateVisibleState clears prevBrsResolved at the first control instruction that is
// not readyToCommit, faulted or squashed (rob_impl.hh:489-495) and sets isUnsquashable =
// isPrevBrsResolved (rob_impl.hh:518-520). Anna 2026-11-08: a branch that has executed but whose
// squash is still pending counts as UNRESOLVED (gem5's readyToCommit shortcut is the A4/S4 bug).
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]} -- [u-2] FLAVOR = spectre
// Other flavors differ ONLY in the selector line above plus the flavor facts below; generate them
// with queries/stt/make_stt_u.py, never by hand:
//   stl        {uncommitted_p[p] & u_store_shadow_p[p]}  -- store-address shadow only (Recon-STT STL runs)
//   shadows    {uncommitted_p[p] & (has_unresolved_brs_p[p] + u_store_shadow_p[p])}  -- Recon-STT, E2
//              (gem5-recon decode.cc:686-695; with full minimality every instance has ONE source,
//              so shadows = spectre U stl and needs no separate testset)
//   futuristic {uncommitted_p[p] & unresolved_p[p].(^(spo_p[p]))}  -- PARKED (Anna 2026-11-07);
//              paper p5 "cannot be squashed", gem5 isPrevInstsCompleted (rob_impl.hh:518)
fun u_store_shadow_p[p: PTag->univ] : Instruction { -- [u-2] after an older store whose ADDRESS is unresolved
	(unresolved_p[p] & Stores).(^(spo_p[p]))
}
// [u-3] flavor facts: none (spectre). The stl flavor adds u_stl_no_branch_speculation and
// u_stl_alias_atom (a true store->load alias, atom-based, as parsexml pass2_6_specify_stl pairs them).

// ---- Clause 2: protection set = the tainted data ------------------------------------------------
// [u-4] SOURCES: the memory read (Inmem) of every unsafe load. Paper p5: "STT taints the output of
// any speculative access instruction"; p6 Sec. 6.2: "If a load is unsafe, its output is always
// tainted" (so a store-forwarded value is tainted too, and no taint is tracked in memory). gem5:
// isAccess() = isLoad() (cpu/base_dyn_inst.hh:675); compute_taint sets DestTainted for an access
// that is not unsquashable (rob_impl.hh:812-813). The taint reaches the load's Outreg over its
// Inmem->Outreg ddi edge. Instance-based: another load of the same word never untaints this one
// (fixes audit R-1). A speculative load with NO Inmem in the instance is not a source (kept, as in
// STT_6/STT_6_v2: the leaked secret is the value at a Mem_s, so RS-minimality keeps that Mem_s).
fun hardware_protection_policy[p: PTag->univ]: Operand {(Loads & speculation_contract_p[p]).inmem & o_p[p]} -- [u-4]
// [u-5] PROPAGATION along spo: identity. Forward taint ("an instruction's output register is tainted
// if any of its input registers are tainted", p6 Sec. 6.2; gem5 explicit_flow, rob_impl.hh:709-724,
// DestTainted = ArgsTainted, :809-811) is the skeleton's ^op_edges closure (rf + ddi, union
// semantics). UNTAINT ("when all the data dependencies of an instruction become untainted, the
// instruction's output is untainted", p6; YRoT p9 Sec. 7.1) needs no fold step: in this snapshot a
// value is tainted iff some load in its backward data cone is unsafe, which, because loads reach the
// VP in order (p5), is exactly "its youngest root of taint has not reached the VP". STT has no
// declassification and no reveal.
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,o:Operand] : Operand { o } -- [u-5]

// ---- Clause 3: leakage function (what transmits) --------------------------------------------------
// [u-6] unchanged from STT_6.als:328. Explicit channel: a load's address (paper p5-6 Sec. 6.1/6.3,
// "for loads, delaying execution implies delaying the TLB lookup"; gem5 isTransmit() = isLoad(),
// base_dyn_inst.hh:676, held by fenceDelay(isArgsTainted), lsq_unit_impl.hh:1013). Implicit channel:
// a branch's predicate (p7 Sec. 6.4.1 "delaying the effects of branch resolution until the branch's
// predicate becomes untainted"; gem5 pending squash commit_impl.hh:934-952, deferred predictor
// update fetch_impl.hh:1021). NOT transmitters here, on purpose:
//   Stores.inaddr -- store-address leaks are known and do not count (Anna 2026-11-08; KV3/S2/S3).
//                    Paper alternative: + Stores.inaddr (Sec. 6.4.2 STL implicit branch).
//   Otherxs.inreg -- our configs run moreTransmitInsts=0 (int/FP div not delayed,
//                    base_dyn_inst_impl.hh:275-294). Alternative for moreTransmitInsts>=1: + Otherxs.inreg.
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg} -- [u-6]


// ---- recon agent query d2_stt_only (2026-11-09; base STT_6_u.als; with gen_useful_litmus) ----

// ---- recon agent shape vocabulary (2026-11-09): plain relations, the unperturbed program ----
fun pairC_q : Instruction -> Instruction { {ld1, ld2: Loads | ld2 in committed and some (ld1.outreg.rf & ld2.inaddr)} }
fun pairU_q : Instruction -> Instruction { {ld1, ld2: Loads | ld2 not in committed and some (ld1.outreg.rf & ld2.inaddr)} }
pred rereads_q[l3, ld1: Instruction] { some l3.inmem and some ld1.inmem and l3.inmem.opstate = ld1.inmem.opstate and ld1 -> l3 in ^spo }
pred feeds_ldxm_q[l3: Instruction] { xm in Loads and l3.inmem -> l3.outreg in ddi and some (l3.outreg.rf & xm.inaddr) }
pred st_between_q[w: State, a, b: Instruction, S: set Instruction] { some s: Stores & S | s.outmem.opstate = w and a -> s in ^spo and s -> b in ^spo }
pred no_st_to_q[w: State] { no s: Stores | s.outmem.opstate = w }
pred spec_q[l: Instruction] { l in speculation_contract_p[no_p] }

// ---- aux: the Recon_6_u.als defense (STT_6_u seed minus [u-7]/[u-8] reveal), renamed *_r ----
fun ld1_r[p: PTag->univ] : Instruction { { ld1: Loads & i_p[p] | some ld2: Loads & committed_p[p] | some (ld1.outreg.(rf_p[p]) & ld2.inaddr) } }
fun conc_r[p: PTag->univ] : Instruction {Stores & i_p[p] & (resolved_p[p] + committed_p[p])}
fun rev_r[p: PTag->univ] : Operand {
	{ m: Loads.inmem & o_p[p] | some ld1: ld1_r[p] |
		m.opstate in (ld1.inmem & o_p[p]).opstate and ld1 -> m.(~inmem) in ^(spo_p[p])
		and (no s: conc_r[p] | m.opstate in (s.outmem & o_p[p]).opstate and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
}
fun hpp_r[p: PTag->univ] : Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - rev_r[p]}
fun flag_r[p: PTag->univ] : Operand { (hpp_r[p] & speculative_xmit_p[p]) + (hpp_r[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) }
pred gul_r {
  not secure_r[no_p]
  all i: (unresolved - first_uncommitted) | secure_r[RR->i]
  secure_r[RC->first_uncommitted + RR->first_uncommitted]
  all s: State | secure_r[RS->s]
}
pred secure_r[p: PTag->univ] { no flag_r[p] }
pred tag_r { some flag_r[no_p] & xm.operands }

pred q { not (gul_r and tag_r) }
