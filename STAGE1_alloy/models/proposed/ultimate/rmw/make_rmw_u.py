#!/usr/bin/env python3
"""Derive STAGE1_alloy/models/proposed/ultimate/STT_6_rmw_u.als from STT_6.als (already run 2026-11-09;
the draft exists, so re-running refuses unless it is deleted first).

Every edit is an exact-once anchored replacement (refuses otherwise), so the
draft is STT_6.als byte-for-byte outside the [RMW-U] hunks. Writes a NEW file
only; refuses to overwrite an existing output.
"""
import hashlib
import sys
from pathlib import Path

REPO = Path("/Users/annaeaton/Documents/stanford/trippel/simspect")
SRC = REPO / "STAGE1_alloy/models/STT_6.als"
DST = REPO / "STAGE1_alloy/models/proposed/ultimate/STT_6_rmw_u.als"
SRC_SHA = "7a6ac4c0a098c4dc0e24a4a1bbf867f1266c491b64bdd356026ec017d5b4198c"

text = SRC.read_text()
sha = hashlib.sha256(text.encode()).hexdigest()
if sha != SRC_SHA:
    sys.exit(f"refusing: STT_6.als sha {sha} != expected {SRC_SHA}")


def rep(old, new, what):
    global text
    n = text.count(old)
    if n != 1:
        sys.exit(f"refusing: anchor '{what}' found {n} times")
    text = text.replace(old, new)


HEADER = """/*********************************************************************************
 *
STT_6_rmw_u -- STT_6 + an x86 read-modify-write (RMW) instruction kind.
DRAFT, NOT APPROVED (2026-11-09, rmw agent). New file; derived from STT_6.als
(sha256 7a6ac4c0...) by make_rmw_u.py, which applies exact-once anchored edits only.
Every change is tagged [RMW-U] and is one of:
  (S) SKELETON PATCH: kind-generic, to be pasted verbatim into every family
      (STT, ReCon, SPT, STL). With no RMW atoms every (S) line reduces to the
      STT_6 line it replaces, so old kinds behave identically.
  (D) DEFENSE CLASSIFICATION: the only edits inside the three-clause defense
      block (where an RMW sits in leakage_function / prot_set_propagation_p).
  (R) RUN PIN: one fact, rmw_pin. Delete it to get the unpinned superset.
Supersedes the RMW half of proposed/STT_6_rmwjmp.als. Differences from that draft:
no TJump kind (RJ-1 option b: a jump is a relabelled resolved operand-less
br_n, so it belongs in Stage 2); the redundant limited_rmw_ins fact is dropped;
the pin is a fact so that the run block keeps the exact text
`run gen_lit {\\n  gen_useful_litmus\\n}` that derive_core.py (Stage 1) and
stage_pipeline.build_seeded_model (Stage 1.5) anchor on.
The new kind, TRmw: x86 `orq|addq %src,(mem)` / `$imm,(mem)`, which gem5 runs as
ldst (a load micro-op with store intent) + ALU + st on ONE address
(gem5 x86 microcode OR_M_R / ADD_M_R: ldst t1; op t1,t1,reg; st t1).
Never lock/xchg forms: gem5 marks ldstl nonSpec (ldstop.isa Ldstl nonSpec=True).

CLEAN MODEL WITH KIND-FIELD REFACTORING

Instruction is a single concrete sig with a `kind: one InstrType` field
instead of abstract + subsigs.  This lets util/ordering[Instruction] work,
enabling in-model symmetry breaking that eliminates duplicate instances.

 */"""

rep("""/*********************************************************************************
 *
CLEAN MODEL WITH KIND-FIELD REFACTORING

Instruction is a single concrete sig with a `kind: one InstrType` field
instead of abstract + subsigs.  This lets util/ordering[Instruction] work,
enabling in-model symmetry breaking that eliminates duplicate instances.

 */""", HEADER, "header")

rep("one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits\n",
    "one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits\n"
    "one sig TRmw     extends InstrType {} // [RMW-U](S) read-modify-write: ldst + alu + st on one address\n",
    "TOtherx sig")

rep("fun Otherxs  : Instruction { kind.TOtherx  }\n",
    "fun Otherxs  : Instruction { kind.TOtherx  }\n"
    "fun Rmws     : Instruction { kind.TRmw     } // [RMW-U](S)\n",
    "Otherxs fun")

rep("fact br_ops   {no (Branchns+Branchxs).(inaddr+inmem+outmem+outreg)} // branch is some control (no output)\n",
    "fact br_ops   {no (Branchns+Branchxs).(inaddr+inmem+outmem+outreg)} // branch is some control (no output)\n"
    "// [RMW-U](S) RMW operand shape:\n"
    "//   inaddr lone: address register (blank = constant address in mem_base, as for ld/st)\n"
    "//   inmem  one : the load half (ldst) reads the location\n"
    "//   outmem one : the store half (st) writes the SAME location (same Mem_s atom)\n"
    "//   inreg  lone: the ALU source register (blank = immediate/zero source, value-neutral)\n"
    "//   outreg none: `op src,(mem)` writes no GPR (flags are not modelled for any kind)\n"
    "// inmem and outmem are required: without them an RMW would be a relabelled ld or st.\n"
    "fact rmw_ops   {no Rmws.outreg}\n"
    "fact rmw_mem   {all r: Rmws | one r.inmem and one r.outmem and r.inmem.opstate = r.outmem.opstate}\n"
    "fact rmw_inreg {all r: Rmws | lone r.inreg}\n",
    "br_ops")

rep("fact limited_ins {all i: Instruction | #(i.ins) <= 2}\n",
    "// [RMW-U](S) was: all i: Instruction | #(i.ins) <= 2. An RMW reads inaddr+inmem+inreg (up to 3);\n"
    "// its bound already follows from limited_inaddrs, rmw_mem and rmw_inreg.\n"
    "fact limited_ins {all i: Instruction - Rmws | #(i.ins) <= 2}\n",
    "limited_ins")

rep("""fun no_unresolved_mem : Instruction {
	Instruction - (uncommitted & (Loads+Stores)).(^(spo))
}""", """fun no_unresolved_mem : Instruction {
	Instruction - (uncommitted & (Loads+Stores+Rmws)).(^(spo)) // [RMW-U](S) an RMW is a memory op (helper unused today)
}""", "no_unresolved_mem")

rep("fact br_ddi    {no ((Branchxs+Branchns).operands <: ddi)}\n",
    "fact br_ddi    {no ((Branchxs+Branchns).operands <: ddi)}\n"
    "// [RMW-U](S) RMW data flow: loaded value and ALU source flow into the stored value; the\n"
    "// address flows nowhere (as in ld_ddi/str_ddi). Optional, like every other kind's ddi.\n"
    "fact rmw_ddi   {no (Rmws.operands <: ddi) - ((Inmem+Inreg)->Outmem)}\n",
    "br_ddi")

rep("""fun no_unresolved_mem_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted & (Loads+Stores)).(^(spo))
}""", """fun no_unresolved_mem_p[p: PTag->univ] : Instruction {
	i_p[p] - (uncommitted & (Loads+Stores+Rmws)).(^(spo)) // [RMW-U](S) (helper unused today)
}""", "no_unresolved_mem_p")

rep("""run gen_lit {
  gen_useful_litmus
} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
""", """// [RMW-U](R) the pin: every instance contains at least one RMW, so the enumeration
// never re-produces an STT_6 instance (STT_6 has no RMW kind). A fact rather than a
// run conjunct so that the run block below stays the exact text derive_core.py and
// stage_pipeline.build_seeded_model anchor on: the derived Stage-1 core inherits the
// pin (new cores = RMW cores), and Stage 1.5 fleshing of ANY core (old STT_6 cores
// included) must add an RMW (RJ-4). Delete this fact for the unpinned superset.
fact rmw_pin { some Rmws }

run gen_lit {
  gen_useful_litmus
} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
""", "run gen_lit")

rep("""fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	// s - (Loads & committed_p[p] & i).inaddr.opstate // committed loads remove their inaddr from the protset
	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
}""", """// STT_6 original: fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
// [RMW-U](D) an RMW transmits its address like a load: STT gem5 makes every load micro-op the
// access and the transmitter (isAccess()/isTransmit() = isLoad(), stt_e3283b9
// src/cpu/base_dyn_inst.hh:675-676) and ldst is a load micro-op (ldstop.isa defineMicroLoadOp
// 'Ldst'); STT p9 Sec.6.4 "loads and stores access memory only if their address argument is
// untainted". The store half adds nothing for STT (stores write the cache only at retirement,
// p5 Sec.6.1).
fun leakage_function : Operand {(Loads+Rmws).inaddr+(Branchxs).inreg}
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	// s - (Loads & committed_p[p] & i).inaddr.opstate // committed loads remove their inaddr from the protset
	// STT_6 original: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate
	// [RMW-U](D) a non-speculative RMW's load half declassifies its location exactly like a
	// non-speculative load (STT untaints an access's output at its visibility point).
	s - ((Loads+Rmws) & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
}""", "defense block")

if DST.exists():
    sys.exit(f"refusing: {DST} already exists")
DST.write_text(text)
print(f"wrote {DST} sha256 {hashlib.sha256(text.encode()).hexdigest()}")
