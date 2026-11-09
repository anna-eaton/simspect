#!/usr/bin/env python3
"""make_recon_u.py -- builds the "ultimate" ReCon drafts (2026-11-09, recon agent of session audit-fanout-1109).
DRAFT TOOLING; every output is an UNAPPROVED draft. Writes NEW files under STAGE1_alloy/models/proposed/ultimate/:

  Recon_6_u.als                = STT_6_u.als     (STT agent, flavor spectre) + the ReCon delta
  Recon_6_u_stl.als            = STT_6_u_stl.als (STT agent, flavor stl)     + the same ReCon delta
  blocks/Recon_6_u.block.als   = the same defense block in the SKELETON_u.als interface (skeleton agent)
  Recon_6_u_core_ri.als, Recon_6_u_stl_core_ri.als  (only with --cores: proposed_twophase/derive_core.py --minimality ri,
                                the tool the STT agent used for STT_6_u_core_ri.als / STT_6_u_stl_core_ri.als)

The ReCon delta is ONE added group of functions (recon_ld1_p, recon_concealer_p, revealed_p) and ONE changed line
(the clause-2 seed subtracts revealed_p), plus a header paragraph and the block title. So
  diff STT_6_u.als Recon_6_u.als          and          diff STT_6_u_stl.als Recon_6_u_stl.als
show only that. The STT agent's tags [u-0..u-6] (skeleton retyping, instance-based seed, identity propagation, ...)
are kept as they are; the ReCon delta is tagged [u-7] (reveal) and [u-8] (conceal). Relative to Recon_6.als every
changed line therefore carries a [u-n] tag (Recon_6.als = STT_6.als + a no-op reveal + the [p] at the seed call).

Each edit is an exact-once anchored replacement: a drifted source refuses instead of producing a wrong draft.
Sources are only read. Refuses to overwrite unless --force.
Usage:  python3 make_recon_u.py [--force] [--cores]
"""
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ULT = HERE.parents[1]                      # .../models/proposed/ultimate
MODELS = ULT.parents[1]                    # .../STAGE1_alloy/models
STT_U = ULT / "STT_6_u.als"
STT_U_STL = ULT / "STT_6_u_stl.als"
RECON = MODELS / "Recon_6.als"
DERIVE_CORE = MODELS / "proposed_twophase" / "derive_core.py"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def once(t, old, new, what):
    n = t.count(old)
    if n != 1:
        sys.exit(f"refusing: anchor '{what}' occurs {n} times (expected 1)")
    return t.replace(old, new)


TITLE_OLD = " * Specific defense model: STT, ultimate draft (STT_6_u)                       -- [u-2..u-6]\n"
TITLE_NEW = (" * Specific defense model: ReCon on STT = the STT_6_u block + the ReCon reveal delta  -- [u-2..u-8]\n"
             " * (the delta is clause 2 only: recon_ld1_p / recon_concealer_p / revealed_p, and the seed line)\n")

HPP_OLD = "fun hardware_protection_policy[p: PTag->univ]: Operand {(Loads & speculation_contract_p[p]).inmem & o_p[p]} -- [u-4]\n"

DELTA_DOC = """// ---- ReCon delta (Aimoniotis et al., MICRO'23; ~/Documents/quail/sources/papers/aimoniotis-2023-recon.pdf, an ACM
// HTML print without page numbers, cited by section). gem5 = the authors' tree ~/Downloads/dockerrecon/gem5-recon/src
// (cafe2 /work/gem5-recon* lines run ~11-15 higher; SOURCE_AUDIT_RECON.md). ReCon sits on the Kaxiras-group STT
// ("Recon-STT"): a load is speculative if decoded under a branch or store shadow (decode.cc:686-695, shadow_tracker.cc
// freeSpecInsts), its destination is tainted (rename.cc:713-718), taint follows the OLDEST tainted source
// (taint_tracker.cc:108-131), tainted loads and branches are held (lsq_unit.cc:2079-2090, inst_queue.cc:1450-1456).
// ReCon changes one thing: "values that previously have been made public" are not potential secrets (sec. 3.1), and a
// value is made public only by a committed direct-dependence load pair (sec. 4.1-4.3, 5.1). Nothing else is relaxed.
// [u-7] (i) LOAD PAIR. LD1 -> LD2 is a pair iff LD1's output register IS LD2's address register, one rf edge with no
//   instruction in between ("RECON limits its detection to only the leakage of load pairs with a direct dependence",
//   sec. 4.3), and LD2 has COMMITTED ("marks this value as revealed when the second load commits", sec. 4.1; "we opt
//   for implementing load-pair detection in the commit stage", sec. 5.1). gem5: LD1's load-pair-table entry is written
//   at LD1's commit (lsq_unit.cc:942-959; skipped if LD1's own read was already revealed), LD2's commit checks its
//   renamed sources src1 then src0 against the table and sends a Reveal for LD1's address (lsq_unit.cc:869-925), and a
//   committing non-load that writes the register clears the entry (commit.cc:1033-1052). LD1 committed follows from
//   LD2 committed (commit is a program-order prefix; rf goes forward in spo). Perturbation-aware (RC on the boundary
//   LD2 creates the pair; RI of an ALU between LD1 and LD2 bridges the rf hole and so creates it too).
//   DECIDE (Anna, B1): sec. 5.1 puts the security bound at LD2's visibility point, commit is what ReCon implements; to
//   reveal at the VP replace `ld2: Loads & committed_p[p]` by `ld2: Loads & i_p[p] - speculation_contract_p[p]`.
fun recon_ld1_p[p: PTag->univ] : Instruction { -- [u-7] the LD1 of every committed direct load pair
	{ ld1: Loads & i_p[p] | some ld2: Loads & committed_p[p] | some (ld1.outreg.(rf_p[p]) & ld2.inaddr) }
}
// [u-8] (ii) CONCEAL. "Once an address is revealed, it is guaranteed to be safe as long as its contents do not change"
//   (sec. 4.4); a performed store conceals (4.4.1); "a load always receives concealed data from store forwarding"
//   (4.4.2); "upon the commit of a store instruction, the bit of the corresponding word is cleared" (5.2). gem5: a
//   store's write clears the word's bit (mem/cache/base.cc:1210-1222); a forwarded load gets no cache response, so no
//   reveal bit (and taint_tracker.cc:143 also requires !stlForw). A store to the word that sits in program order
//   between LD1 and the re-load conceals it wherever it is relative to LD2: a store between LD1 and LD2 changes the
//   contents LD2 leaked, so the new value was never revealed (gem5 re-reveals it anyway: audit R-SA-2, which a test of
//   that shape exposes on a build whose reveal works). EXCEPT a store whose ADDRESS is unresolved: the re-load may
//   bypass it and read the pre-store, revealed value, which ReCon may use (sec. 4.5.2, Table 1 case 1). With the
//   spectre contract RR-minimality never keeps an unresolved store, so the exception changes no generated instance
//   there; it is what makes the stl flavor right, and it matters for facts-only queries and the post-hoc checker.
fun recon_concealer_p[p: PTag->univ] : Instruction {Stores & i_p[p] & (resolved_p[p] + committed_p[p])} -- [u-8]
// [u-7] (iii) REVEALED READS. The memory read m of a load L3 is revealed iff some pair's LD1 read m's word before L3
//   and no concealer writes that word between LD1 and L3. A revealed read is not a taint source: "for STT, any load
//   that receives a revealed value untaints its destination register" (sec. 5.4). gem5: the cache returns the word's
//   bit with the data (base.cc:478-487, lsq_unit.cc:182-185), and freeTaints erases every taint whose source is that
//   load once it completed, its own sources are untainted and it was not store-forwarded (taint_tracker.cc:138-150).
//   Per word = per Mem_s (sec. 5.2: one bit per 8-byte word; widths and alignment are not modelled, R-SA-3/4). The
//   model is a snapshot, so "revealed" means MAY be untainted: gem5 untaints L3 only if L3's cache access returns after
//   the Reveal reached L1 (updateRevealedTaints, the only retroactive path, has no caller). Treating such a read as
//   public never makes the model flag what ReCon may allow; reveal TIMING is a Stage-2/harness matter (DECIDE B4).
fun revealed_p[p: PTag->univ] : Operand { -- [u-7]
	{ m: Loads.inmem & o_p[p] | some ld1: recon_ld1_p[p] |
		m.opstate in (ld1.inmem & o_p[p]).opstate
		and ld1 -> m.(~inmem) in ^(spo_p[p])
		and (no s: recon_concealer_p[p] | m.opstate in (s.outmem & o_p[p]).opstate
			and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
}
// clause-2 seed = the STT sources [u-4] minus the revealed reads [u-7]. Replaces Recon_6.als:326-328, a no-op (audit
// QR2: Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p])), transitive through ALUs,
// keyed on LD2 being merely non-speculative, never concealing; and the STT fold had already made the word public).
"""
HPP_NEW = "fun hardware_protection_policy[p: PTag->univ]: Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_p[p]} -- [u-4][u-7]\n"

HEADER = """// =============================================================================
// {name} -- ULTIMATE ReCon draft{flavor}. DRAFT, NOT APPROVED (2026-11-09, recon agent,          -- [u-7][u-8]
// session audit-fanout-1109). New file; no existing .als was touched. Built by
// proposed/ultimate/queries/recon/make_recon_u.py as
//   {base} (sha256 {base_sha})  +  the ReCon delta below.
// ReCon = the STT model + ONE delta in clause 2, so `diff {base} {name}` shows only this paragraph,
// the block title, the [u-7]/[u-8] functions and the seed line:
//   [u-7] REVEAL: a direct load pair LD1 -> LD2 (LD1's output register is LD2's address register, one rf
//         edge) whose LD2 has COMMITTED reveals LD1's word; a later load's read of that word is then not a
//         taint source (ReCon sec. 4.1, 4.3, 5.1, 5.2, 5.4). Fixes audit R-2 / R-SA-10 (old clause a no-op).
//   [u-8] CONCEAL: a store to the word between LD1 and the re-load cancels the reveal (sec. 4.4), unless the
//         store's address is unresolved (the re-load may bypass it, sec. 4.5.2).
// Relative to Recon_6.als (sha256 {recon_sha}; it already has rf_from_most_recent_writer, applied
// 2026-11-09 with Anna's authorization): the STT agent's [u-0..u-6] below (Operand-typed protection set in 4
// skeleton places, instance-based seed = audit R-1 fix, identity propagation) + [u-7]/[u-8]. One comment line
// differs untagged: "// fun leakage_function" -> "//fun leakage_function", inherited from STT_6.als.
// The base file's own header follows unchanged.
// =============================================================================
"""

# ---- the same block in the SKELETON_u.als interface (perturbed field hooks; passes derive_core_u.py lint) ----
BLOCK = """/*********************************************************************************
 * Specific defense model: ReCon on STT (Spectre contract) for SKELETON_u.als   -- recon agent, 2026-11-09
 * = the STT_6_u.als block in the SKELETON_u interface + the ReCon delta [u-7]/[u-8], same semantics as
 *   proposed/ultimate/Recon_6_u.als (generated by queries/recon/make_recon_u.py; sources cited there).
 */
// (1) speculation contract (STT-Spectre; STT_6_u [u-2])
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
// (2) protection set
// [u-7] load pair: LD1's output register is LD2's address register (one rf edge), LD2 committed
fun recon_ld1_p[p: PTag->univ] : Instruction {
	{ ld1: Loads & i_p[p] | some ld2: Loads & committed_p[p] | some (ld1.(outreg_p[p]).(rf_p[p]) & ld2.(inaddr_p[p])) }
}
// [u-8] concealers: stores whose address is resolved (or that committed)
fun recon_concealer_p[p: PTag->univ] : Instruction {Stores & i_p[p] & (resolved_p[p] + committed_p[p])}
// [u-7] revealed reads: a later read of a pair's LD1 word with no concealer writing it in between
fun revealed_p[p: PTag->univ] : Operand {
	{ m: (Loads & i_p[p]).(inmem_p[p]) | some ld1: recon_ld1_p[p] |
		m.opstate in ld1.(inmem_p[p]).opstate
		and ld1 -> m.~(inmem_p[p]) in ^(spo_p[p])
		and (no s: recon_concealer_p[p] | m.opstate in s.(outmem_p[p]).opstate
			and ld1 -> s in ^(spo_p[p]) and s -> m.~(inmem_p[p]) in ^(spo_p[p])) }
}
// seed: the memory read of every speculative load (STT_6_u [u-4]) minus the revealed reads [u-7]
fun hardware_protection_policy[p: PTag->univ] : Operand {spec_loads_p[p].(inmem_p[p]) - revealed_p[p]}
// step: identity (STT_6_u [u-5])
fun prot_set_propagation_p[p: PTag->univ, i: Instruction, o: Operand] : Operand { o }
// flow: taint follows rf + ddi (STT_6_u: the ^op_edges closure)
fun prot_flow_p[p: PTag->univ] : Operand->Operand {op_edges_p[p]}
// (3) leakage function (STT_6_u [u-6])
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
"""


def build(base, name, flavor):
    t = base.read_text()
    t = once(t, TITLE_OLD, TITLE_NEW, "block title")
    t = once(t, HPP_OLD, DELTA_DOC + HPP_NEW, "seed line")
    hdr = (HEADER.replace("{name}", name).replace("{flavor}", flavor).replace("{base}", base.name)
           .replace("{base_sha}", sha(base)).replace("{recon_sha}", sha(RECON)))
    return hdr + t


def write(path, text, force):
    if path.exists() and not force:
        sys.exit(f"refusing to overwrite {path} (use --force)")
    path.write_text(text, encoding="utf-8")
    print("wrote", path, sha(path)[:12])


def main():
    force = "--force" in sys.argv
    for p in (STT_U, STT_U_STL, RECON):
        if not p.exists():
            sys.exit(f"missing source {p}")
    write(ULT / "Recon_6_u.als", build(STT_U, "Recon_6_u.als", ""), force)
    write(ULT / "Recon_6_u_stl.als", build(STT_U_STL, "Recon_6_u_stl.als", ", FLAVOR = stl (store-address shadow only)"), force)
    write(ULT / "blocks" / "Recon_6_u.block.als", BLOCK, force)
    if "--cores" in sys.argv:
        for flat, core in (("Recon_6_u.als", "Recon_6_u_core_ri.als"), ("Recon_6_u_stl.als", "Recon_6_u_stl_core_ri.als")):
            out = ULT / core
            if out.exists() and not force:
                sys.exit(f"refusing to overwrite {out} (use --force)")
            subprocess.run([sys.executable, str(DERIVE_CORE), str(ULT / flat), str(out), "--minimality", "ri"], check=True)


if __name__ == "__main__":
    main()
