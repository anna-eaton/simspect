#!/usr/bin/env python3
"""make_v2_models.py — builds the three model-fixes drafts (2026-11-08, session model-fixes) from the
approved/current models by exact, asserted string replacements (each anchor must occur exactly once).
Writes NEW files only:  STAGE1_alloy/models/proposed/{STT_6_v2,Recon_6_v2,SPT_6_oneLP_v3}.als
Refuses to overwrite an existing output unless --force. Source models are only read.
Usage: python3 make_v2_models.py [--force]
Review: wiki/state/ALLOY_MODEL_CHANGES.md, section "2026-11-08 — model-fixes"."""
import hashlib, sys
from pathlib import Path
M = Path(__file__).resolve().parents[3] / "STAGE1_alloy" / "models"
force = "--force" in sys.argv

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rep(t, old, new, tag):
    n = t.count(old)
    assert n == 1, f"{tag}: anchor occurs {n} times"
    return t.replace(old, new)
def write(name, text):
    out = M / "proposed" / name
    if out.exists() and not force:
        sys.exit(f"refusing to overwrite {out} (use --force)")
    out.write_text(text); print("wrote", out, sha(out)[:12])

# ---------------------------------------------------------------- shared: State -> Operand protection set
def operand_skeleton(t, tag):
    t = rep(t, "fun a[p:PTag->univ,i:Instruction,s:State] : State { prot_set_propagation_p[p,i,s]}\nfun last_committed_protset_p[p: PTag->univ] : State {",
              "fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand { prot_set_propagation_p[p,i,o]} // [v2-2] Operand-typed protection set\nfun last_committed_protset_p[p: PTag->univ] : Operand { // [v2-2]", tag + " a/lcp")
    t = rep(t, "\t(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and\n\t(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p])",
              "\t// [v2-2] the protection set is a set of operands now, so no .(~opstate) lift (same form as SPT_6_oneLP_v2.als:287-296)\n\t(no (last_committed_protset_p[p] & speculative_xmit_p[p])) and\n\t(no last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p])", tag + " secure")
    t = rep(t, "\t(some (last_committed_protset_p[no_p].(~opstate) & speculative_xmit_p[no_p] & xm.operands)) or\n\t(some last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)",
              "\t// [v2-2] Operand-typed, as in secure_speculation_scheme_p\n\t(some (last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands)) or\n\t(some last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)", tag + " tag_xm")
    return t

STT_SEED_OLD = """fun hardware_protection_policy: State {Mem_s}
//fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}"""
STT_PROP_OLD = """fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	// s - (Loads & committed_p[p] & i).inaddr.opstate // committed loads remove their inaddr from the protset
	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
}"""
PROP_NEW = """fun prot_set_propagation_p[p:PTag->univ,i:Instruction,o:Operand] : Operand {
	// [v2-2] nothing is ever de-protected in program order: the seed is already the final set
	// (old, location-based: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate, i.e. any
	//  non-speculative load made its whole LOCATION public, so a later speculative re-load of the same
	//  word was never a leak; audit R-1 / QR1a, STT-3 / Recon F2)
	o
}"""
STT_SEED_NEW = """//fun hardware_protection_policy: State {Mem_s}
// [v2-2] instance-based protection: the memory read of every SPECULATIVE load is a taint source,
// whatever any other load did to the same location. STT (yu-2019-stt.pdf p6): "If a load is unsafe,
// its output is always tainted"; the taint reaches the load's output over its Inmem->Outreg ddi edge.
fun hardware_protection_policy[p: PTag->univ]: Operand {(Loads & speculation_contract_p[p]).inmem & o_p[p]}
//fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}"""

HDR_STT = """// =============================================================================
// STT_6_v2.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).
// Derived from STT_6.als (sha256 {sha}), which is unchanged.
// Changes, each marked [v2-n]; every other line is byte-identical to STT_6.als:
//   [v2-2] instance-based protection set (defense clauses 2+3 of the block, plus the
//          State->Operand retyping of the four skeleton lines that read the set:
//          a, last_committed_protset_p, secure_speculation_scheme_p, tag_xm; same
//          Operand form SPT_6_oneLP_v2.als already uses). Seeds = the Inmem of every
//          speculative load; propagation = identity. Fixes audit R-1 (QR1a UNSAT).
//   ([v2-1] rf_from_most_recent_writer is already in STT_6.als.)
// Review + evidence: wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".
// =============================================================================
"""
HDR_RECON = """// =============================================================================
// Recon_6_v2.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).
// Derived from Recon_6.als (sha256 {sha}), which is unchanged.
// Skeleton = STT_6_v2.als byte for byte; `diff STT_6_v2.als Recon_6_v2.als` is this
// header plus the ReCon defense block. Changes vs Recon_6.als, each marked:
//   [v2-1] fact rf_from_most_recent_writer, verbatim from STT_6.als:161-169 (audit R-3:
//          25.8% of Recon_6 instances read a register past a newer writer).
//   [v2-2] instance-based protection set (as STT_6_v2.als).
//   [v2-3] ReCon reveal rewritten: direct load pair (LD1.outreg -rf-> LD2.inaddr, no
//          instruction between), only once LD2 COMMITS, per word (Mem_s), concealed by any
//          store to the word between LD1 and the re-load; the reveal un-protects only the
//          re-load's memory read (ReCon §4.1, §4.3, §4.4, §5.1, §5.2, §5.4; gem5-recon
//          lsq_unit.cc:870-956, commit.cc:1033-1054, base.cc:1218-1223). Fixes R-1/R-2.
// Review + evidence: wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".
// =============================================================================
"""
RECON_BLOCK_NEW = """//fun hardware_protection_policy: State {Mem_s}
// [v2-3] ReCon reveal / conceal, per word (Mem_s) and per re-load instance. The memory read m of a
// load L3 is REVEALED iff some direct load pair LD1 -> LD2 has exposed m's word:
//   - LD1 reads the same word, and LD1 is spo-before L3;
//   - LD1's output register is LD2's address register over ONE rf edge, i.e. no instruction in
//     between (ReCon §4.3 "RECON limits its detection to only the leakage of load pairs with a
//     direct dependence"; gem5 lsq_unit.cc:872-880 matches LD2's renamed source to LD1's dest, and
//     commit.cc:1046-1054 drops the entry when any other instruction writes that register);
//   - LD2 has COMMITTED (§4.1 (2), §5.1 "detection in the commit stage", §5.2 "When the second load
//     (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as
//     revealed"; gem5 sends the Reveal from LSQUnit::commitLoad, lsq_unit.cc:870-918);
//   - no store writes the word spo-between LD1 and L3 (conceal: §4.4 "Once an address is revealed,
//     it is guaranteed to be safe as long as its contents do not change", §4.4.1 / §5.2 a committed
//     store clears the word's bit, gem5 base.cc:1218-1223; §4.4.2 a younger in-flight store forwards
//     concealed data). A store between LD1 and LD2 also conceals here: LD2 leaked the OLD value
//     (paper §4.4); gem5 re-reveals in that case (SOURCE_AUDIT_RECON.md R-SA-2), so such a test is
//     a leak in the model and exposes R-SA-2 when the reveal works.
// A revealed read is not a taint source (§5.4 "for STT, any load that receives a revealed value
// untaints its destination register"); everything else is exactly STT_6_v2.
fun revealed_p[p: PTag->univ] : Operand {
	{ m: Loads.inmem & o_p[p] | some ld1, ld2: Loads & i_p[p] |
		ld2 in committed_p[p]
		and some (ld1.outreg.(rf_p[p]) & ld2.inaddr)
		and m.opstate in (ld1.inmem & o_p[p]).opstate
		and ld1 -> m.(~inmem) in ^(spo_p[p])
		and (no s: Stores & i_p[p] | m.opstate in (s.outmem & o_p[p]).opstate
			and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
}
// [v2-2] instance-based protection (as STT_6_v2.als) minus the revealed reads [v2-3]
fun hardware_protection_policy[p: PTag->univ]: Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_p[p]}
// old (Recon_6.als:316-318), a no-op (audit QR2): Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p]))
// fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}"""

# ---------------------------------------------------------------- STT_6_v2
src = M / "STT_6.als"; t = src.read_text()
t = operand_skeleton(t, "STT")
t = rep(t, "\t\t\t\ta[p,f[p],hardware_protection_policy]\n", "\t\t\t\ta[p,f[p],hardware_protection_policy[p]] // [v2-2]\n", "STT fold seed")
t = rep(t, STT_SEED_OLD, STT_SEED_NEW, "STT seed")
t = rep(t, STT_PROP_OLD, PROP_NEW, "STT prop")
stt_v2 = HDR_STT.replace("{sha}", sha(src)) + t
write("STT_6_v2.als", stt_v2)

# ---------------------------------------------------------------- Recon_6_v2 (= STT_6_v2 skeleton + ReCon block)
rsrc = M / "Recon_6.als"; r = rsrc.read_text()
RF = t[t.index("\n// [Option A] rf must read"):t.index("fact ld_ddi")]
assert RF.count("fact rf_from_most_recent_writer") == 1
r = rep(r, "fact same_state_rf {no ((~opstate).rf.opstate - iden)}\n", "fact same_state_rf {no ((~opstate).rf.opstate - iden)}\n" + RF.rstrip("\n") + "\n", "Recon rf")  # [v2-1], verbatim (unlabelled so the skeleton stays byte-identical to STT_6_v2)
r = operand_skeleton(r, "Recon")
r = rep(r, "\t\t\t\ta[p,f[p],hardware_protection_policy[p]]\n", "\t\t\t\ta[p,f[p],hardware_protection_policy[p]] // [v2-2]\n", "Recon fold seed")
r = rep(r, """fun hardware_protection_policy[p: PTag->univ]: State {Mem_s - 
(~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p])) // speculative loads backwards through dd to state
} // 
// fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}""", RECON_BLOCK_NEW, "Recon seed")
r = rep(r, STT_PROP_OLD, PROP_NEW, "Recon prop")
write("Recon_6_v2.als", HDR_RECON.replace("{sha}", sha(rsrc)) + r)

# ---------------------------------------------------------------- SPT_6_oneLP_v3 (audit S-1 Option A, one line)
ssrc = M / "SPT_6_oneLP_v2.als"; s = ssrc.read_text()
s = rep(s, "\t- (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) // [v2-4] the transmitted value and its producer only\n",
          "\t// - (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) // [v2-4] the transmitted value and its producer only\n"
          "\t// [v3-1] also declassify the producer LOAD's memory read (one ddi hop back from the declassified Outreg),\n"
          "\t// so the transitive ^op_edges term no longer re-flags the declassified value's other readers (audit S-1, Option A)\n"
          "\t- (let d = (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) | d + (d & Loads.outreg).(~(ddi_p[p])))\n", "SPT S-1")
s = rep(s, "// =============================================================================\n// SPT_6_oneLP_v2.als",
          "// =============================================================================\n"
          "// SPT_6_oneLP_v3.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).\n"
          "// = SPT_6_oneLP_v2.als (sha256 " + sha(ssrc) + ", unchanged) plus ONE change:\n"
          "//   [v3-1] declassification also removes the producer load's Inmem (audit S-1, Option A,\n"
          "//          wiki/findings/audits/2026-11-08/MODEL_AUDIT_SPT_RECON.md). Review: wiki/state/\n"
          "//          ALLOY_MODEL_CHANGES.md \"2026-11-08 — model-fixes\". The v2 header below is kept as is.\n"
          "// =============================================================================\n"
          "// SPT_6_oneLP_v2.als", "SPT hdr")
write("SPT_6_oneLP_v3.als", s)
