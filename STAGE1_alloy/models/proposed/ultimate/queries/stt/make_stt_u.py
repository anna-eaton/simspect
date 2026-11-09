#!/usr/bin/env python3
"""make_stt_u.py -- build the ULTIMATE STT drafts from STAGE1_alloy/models/STT_6.als (STT agent, 2026-11-09).

Writes (new files only, all under STAGE1_alloy/models/proposed/ultimate/):
  STT_6_u.als      flavor = spectre (STT-Spectre, /work/stt, /work/stt-master; eval row E3)
  STT_6_u_stl.als  flavor = stl     (store-address shadow only; Recon-STT STL runs on gem5-recon-stl)
Every edit is an exact-once anchored replacement (the script refuses if an anchor is missing or
repeated), so `diff STT_6.als STT_6_u.als` shows only the [u-n] tagged lines, and
`diff STT_6_u.als STT_6_u_stl.als` shows only the header line, the clause-1 selector line and the
flavor-fact block. STT_6.als is only read; its sha256 is checked first.
Usage: python3 make_stt_u.py            (re-runnable; overwrites only the two files above)
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ULT = HERE.parents[1]                      # .../models/proposed/ultimate
MODELS = ULT.parents[1]                    # .../STAGE1_alloy/models
SRC = MODELS / "STT_6.als"
SRC_SHA = "7a6ac4c0a098c4dc0e24a4a1bbf867f1266c491b64bdd356026ec017d5b4198c"


def once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        sys.exit(f"refusing: anchor '{what}' occurs {n} times (expected 1)")
    return text.replace(old, new)


HEADER = """// =============================================================================
// STT_6_u.als -- ULTIMATE STT draft (STT agent, 2026-11-09). DRAFT, NOT APPROVED.
// New file, derived from STT_6.als (sha256 {sha}, unchanged) by
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
"""

DEFENSE_OLD_HEAD = """/*********************************************************************************
 * Specific defense model STT (non-spec on commit)
 */
"""

DEFENSE_NEW = """/*********************************************************************************
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
"""

# ---- stl flavor (derived from STT_6_u.als) ----
SEL_SPECTRE = "fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]} -- [u-2] FLAVOR = spectre\n"
SEL_STL = "fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & u_store_shadow_p[p]} -- [u-2] FLAVOR = stl\n"
FACTS_SPECTRE = """// [u-3] flavor facts: none (spectre). The stl flavor adds u_stl_no_branch_speculation and
// u_stl_alias_atom (a true store->load alias, atom-based, as parsexml pass2_6_specify_stl pairs them).
"""
FACTS_STL = """// [u-3] flavor facts (stl). Control-flow speculation is off, and every unresolved-address store
// has a TRUE alias: a younger uncommitted load at or before xm names the same Mem_s with no other
// store to it in between (atom-based, = proposed/Recon_6_stl.als stl_alias_atom; rf not required,
// the bypassing load reads the stale value). This is how parsexml pass2_6_specify_stl pairs them.
fact u_stl_no_branch_speculation {no (unresolved & (Branchxs+Branchns))} -- [u-3]
fact u_stl_alias_atom { -- [u-3]
	all s: unresolved & Stores | some l: uncommitted & Loads |
		some (s.outmem.opstate & l.inmem.opstate) and s->l in ^spo and l in xm + xm.^(~spo)
		and no s2: Stores - s | some (s2.outmem.opstate & s.outmem.opstate) and s->s2 in ^spo and s2->l in ^spo
}
"""


def build():
    raw = SRC.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != SRC_SHA:
        sys.exit(f"refusing: {SRC} sha256 {sha} != expected {SRC_SHA}")
    t = raw.decode("utf-8")
    t = once(t, "fun a[p:PTag->univ,i:Instruction,s:State] : State { prot_set_propagation_p[p,i,s]}\n",
             "fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand { prot_set_propagation_p[p,i,o]} -- [u-1] Operand-typed protection set\n", "fun a")
    t = once(t, "fun last_committed_protset_p[p: PTag->univ] : State {\n",
             "fun last_committed_protset_p[p: PTag->univ] : Operand { -- [u-1]\n", "lcp head")
    t = once(t, "\t\t\t\ta[p,f[p],hardware_protection_policy]\n",
             "\t\t\t\ta[p,f[p],hardware_protection_policy[p]] -- [u-1]\n", "lcp seed")
    t = once(t, "\t(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and\n"
                "\t(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p])\n",
             "\t(no (last_committed_protset_p[p] & speculative_xmit_p[p])) and -- [u-1] no .(~opstate) lift\n"
             "\t(no last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p]) -- [u-1]\n", "secure")
    t = once(t, "\t(some (last_committed_protset_p[no_p].(~opstate) & speculative_xmit_p[no_p] & xm.operands)) or\n"
                "\t(some last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)\n",
             "\t(some (last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands)) or -- [u-1]\n"
             "\t(some last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands) -- [u-1]\n", "tag_xm")
    i = t.index(DEFENSE_OLD_HEAD)
    if t.count(DEFENSE_OLD_HEAD) != 1:
        sys.exit("refusing: defense block head not unique")
    t = t[:i] + DEFENSE_NEW
    spectre = HEADER.format(sha=sha) + t
    stl = spectre.replace("// STT_6_u.als -- ULTIMATE STT draft", "// STT_6_u_stl.als -- ULTIMATE STT draft, FLAVOR = stl (store-address shadow only; = STT_6_u.als except\n"
                          "// the clause-1 selector line and the [u-3] flavor facts). Header of the spectre file follows:\n"
                          "// STT_6_u.als -- ULTIMATE STT draft", 1)
    stl = once(stl, SEL_SPECTRE, SEL_STL, "selector")
    stl = once(stl, FACTS_SPECTRE, FACTS_STL, "flavor facts")
    for name, txt in (("STT_6_u.als", spectre), ("STT_6_u_stl.als", stl)):
        p = ULT / name
        p.write_text(txt, encoding="utf-8")
        print(f"wrote {p} sha256 {hashlib.sha256(txt.encode()).hexdigest()}")


if __name__ == "__main__":
    build()
