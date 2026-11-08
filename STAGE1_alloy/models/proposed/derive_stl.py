#!/usr/bin/env python3
"""derive_stl.py — derive the STL (store-to-load speculation) variant of a main Alloy model.

DRAFT TOOLING (2026-11-08, stl-spec session). Output drafts are UNAPPROVED: they go
in STAGE1_alloy/models/proposed/ (the pipeline does not read it) until Anna signs off.

Applies to a copy of <model>.als exactly the changes that turned STT_6.als into the
approved STT_6_stl.als, and nothing else:

  1. a header paragraph (after the "CLEAN MODEL ..." title line);
  2. the "STL speculation source" block after no_unresolved_mem_p:
     has_unresolved_strs_p / no_unresolved_strs_p, fact stl_no_unresolved_branches
     (control-flow speculation off), and the true-alias fact:
       --alias rf   = STT_6_stl's stl_alias_pair verbatim (an rf edge store->load;
                      "no store in between" comes from rf_from_most_recent_writer,
                      which only the STT_6 family has)
       --alias atom = (default) every unresolved store has a younger uncommitted load,
                      at or before the xmit, naming the same Mem_s, with no other
                      store to it in between; rf not required. Superset of rf, the
                      rule parsexml pass2_6_specify_stl pairs by, and self-contained.
  3. speculation contract: has_unresolved_brs_p -> has_unresolved_strs_p;
  4. protection-set propagation: the STT-style de-protection line
     `s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate` -> no_unresolved_strs_p,
     if the model has it (SPT_6_oneLP has no branch-keyed de-protection; skipped).

hardware_protection_policy and leakage_function are untouched. Each anchor must occur
exactly once (step 4: once or not at all) or the script refuses. The source is only read.

Usage:
  python3 derive_stl.py <source.als> <out.als> [--alias atom|rf]
"""
import argparse
import hashlib
import sys
from pathlib import Path

TITLE = "CLEAN MODEL WITH KIND-FIELD REFACTORING\n\n"

MEM_FUN = "fun no_unresolved_mem_p[p: PTag->univ] : Instruction {\n\ti_p[p] - (uncommitted & (Loads+Stores)).(^(spo))\n}\n"

SOURCE_BLOCK = """
/*********************************************************************************
 * STL speculation source (as in STT_6_stl; mirrors has_unresolved_brs_p)
 * A store's isresolved flag means "its address is resolved".
 */
fun has_unresolved_strs_p[p: PTag->univ] : Instruction {
	((unresolved_p[p] & Stores).(^(spo_p[p]))) // all the instructions that come after a store with an unresolved address
}
fun no_unresolved_strs_p[p: PTag->univ] : Instruction {
	i_p[p] - has_unresolved_strs_p[p]
}

// control-flow speculation is off in this model
fact stl_no_unresolved_branches {no (unresolved & (Branchxs+Branchns))}
"""

ALIAS_RF = """
// true alias (the false-negative prediction): some load at or before the xmit
// reads the memory state an older unresolved store writes (rf = most recent
// writer, so no intervening store to that state)
fact stl_alias_pair {
	some s: unresolved & Stores, l: uncommitted & Loads |
		some (s.outmem.rf & l.inmem) and l in xm + xm.^(~spo)
}
"""

ALIAS_ATOM = """
// true alias (the false-negative prediction), atom-based: every unresolved store has
// a younger uncommitted load, at or before the xmit, naming the same Mem_s, with no
// other store to it in between. rf not required (the bypassing load reads the stale
// value, not the store's); this is how parsexml pass2_6_specify_stl pairs them.
fact stl_alias_atom {
	all s: unresolved & Stores | some l: uncommitted & Loads |
		some (s.outmem.opstate & l.inmem.opstate) and s->l in ^spo and l in xm + xm.^(~spo)
		and no s2: Stores - s | some (s2.outmem.opstate & s.outmem.opstate) and s->s2 in ^spo and s2->l in ^spo
}
"""

CONTRACT_OLD = "\nfun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}\n"
CONTRACT_NEW = ("\n// main-model (branch) contract, kept for reference:\n"
                "//fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}\n"
                "fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_strs_p[p]}\n")

PROT_OLD = "\ts - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)"
PROT_NEW = ("\t// main-model (branch) version: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate\n"
            "\ts - (Loads & no_unresolved_strs_p[p] & i).inmem.opstate // loads with no unresolved-address store before them remove their inmem state from the protset")


def replace_once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        sys.exit(f"refusing: anchor '{what}' occurs {n} times (expected 1)")
    return text.replace(old, new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--alias", choices=["atom", "rf"], default="atom")
    a = ap.parse_args()
    src = Path(a.source)
    raw = src.read_bytes()
    text = raw.decode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    out_stem = Path(a.out).stem

    text = replace_once(text, MEM_FUN, MEM_FUN + SOURCE_BLOCK + (ALIAS_ATOM if a.alias == "atom" else ALIAS_RF),
                        "no_unresolved_mem_p")
    text = replace_once(text, CONTRACT_OLD, CONTRACT_NEW, "speculation_contract_p (branch contract)")
    n_prot = text.count(PROT_OLD)
    if n_prot > 1:
        sys.exit(f"refusing: protset anchor occurs {n_prot} times")
    if n_prot == 1:
        text = text.replace(PROT_OLD, PROT_NEW)
    header = (
        f"{out_stem} — store-to-load (memory-dependence) speculation ONLY, on {src.stem}'s defense.\n"
        f"DRAFT, NOT APPROVED (2026-11-08). Derived from {src.name} (sha256 {sha[:16]}...) by\n"
        f"STAGE1_alloy/models/proposed/derive_stl.py --alias {a.alias}: the same changes that\n"
        "turned STT_6.als into the approved STT_6_stl.als, nothing else.\n"
        "  - speculation source = an older store whose ADDRESS is unresolved; every branch resolved.\n"
        "  - the instance must contain a TRUE alias (see the alias fact below).\n"
        f"  - protection-set propagation: {'branch-keyed de-protection switched to stores' if n_prot else 'no branch-keyed de-protection in this model; unchanged'}.\n"
        "  - hardware_protection_policy and leakage_function unchanged.\n"
        "Concretize with branch mode \"stl_bypass\". See wiki/design/STL_SPECULATION.md.\n\n"
    )
    text = replace_once(text, TITLE, TITLE.rstrip("\n") + "\n" + header, "title line")
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"wrote {a.out} from {src.name} (sha256 {sha[:16]}..., alias={a.alias}, protset {'switched' if n_prot else 'unchanged'})")


if __name__ == "__main__":
    main()
