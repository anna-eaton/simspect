#!/usr/bin/env python3
"""
categorize_hits.py — Categorize hit XMLs by transmitter pattern.

Usage:
    python3 categorize_hits.py --hits-dir <analysis-hit-folder> --xml-dir <xml-folder>

Categories:
    SLF        — xmit is TLoad; a prior TStore shares the same address state element
    LL         — xmit is TLoad; its address comes from a TOther whose two inreg
                 states are sourced from (a) an unresolved TLoad and (b) a resolved TLoad
    OtherLoad  — xmit is TLoad, not SLF or LL
    BR         — xmit is TBranchx
    Other      — anything else

All detection works purely from the XML (no ann.json).
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def ix_num(label: str) -> int:
    try:
        return int(label.replace("IX", "").split("$")[0])
    except Exception:
        return 999


def parse_xml(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    inst_el = root.find("instance")
    if inst_el is None:
        return None

    fields: dict[str, list] = {}
    for field in inst_el.findall("field"):
        name = field.get("label", "")
        pairs = []
        for tup in field.findall("tuple"):
            atoms = [a.get("label") for a in tup.findall("atom")]
            pairs.append(tuple(atoms))
        fields[name] = pairs

    def fmap(fname):
        return {a: b for a, b in fields.get(fname, [])}

    def fmulti(fname):
        d = {}
        for a, b in fields.get(fname, []):
            d.setdefault(a, []).append(b)
        return d

    def fset(fname):
        return {a for a, _ in fields.get(fname, [])}

    opstate     = fmap("opstate")
    kind        = fmap("kind")
    idx         = fmap("idx")
    isxm        = fset("isxm")
    isresolved  = fset("isresolved")
    inaddr_map  = fmulti("inaddr")   # instr → [Inaddr$N, ...]
    inmem_map   = fmulti("inmem")    # instr → [Inmem$N, ...]
    outmem_map  = fmulti("outmem")   # instr → [Outmem$N, ...]
    outreg_map  = fmulti("outreg")   # instr → [Outreg$N, ...]
    inreg_map   = fmulti("inreg")    # instr → [Inreg$N, ...]

    instructions = list(kind.keys())

    def pos(instr):
        return ix_num(idx.get(instr, "IX999$0"))

    def addr_states(instr):
        """State elements used as memory ADDRESS by this instruction."""
        ops = inaddr_map.get(instr, [])
        return {opstate[op] for op in ops if op in opstate}

    def inmem_states(instr):
        """State elements read from memory by this instruction."""
        ops = inmem_map.get(instr, [])
        return {opstate[op] for op in ops if op in opstate}

    def outmem_states(instr):
        """State elements written to memory by this instruction."""
        ops = outmem_map.get(instr, [])
        return {opstate[op] for op in ops if op in opstate}

    def outreg_states(instr):
        """State elements produced in output registers by this instruction."""
        ops = outreg_map.get(instr, [])
        return {opstate[op] for op in ops if op in opstate}

    def inreg_states(instr):
        """State elements consumed as register inputs by this instruction."""
        ops = inreg_map.get(instr, [])
        return {opstate[op] for op in ops if op in opstate}

    return dict(
        instructions=instructions,
        kind=kind, idx=idx, pos=pos,
        isxm=isxm, isresolved=isresolved,
        addr_states=addr_states,
        inmem_states=inmem_states,
        outmem_states=outmem_states,
        outreg_states=outreg_states,
        inreg_states=inreg_states,
    )


def categorize(d: dict) -> str:
    instructions = d["instructions"]
    kind         = d["kind"]
    pos          = d["pos"]
    isxm         = d["isxm"]
    isresolved   = d["isresolved"]

    xmits = [i for i in instructions if i in isxm]
    if not xmits:
        return "Other"

    xmit = xmits[0]
    xmit_kind = kind.get(xmit, "?").split("$")[0]

    # ── BR ────────────────────────────────────────────────────────────────────
    if xmit_kind == "TBranchx":
        return "BR"

    # ── Load xmit ─────────────────────────────────────────────────────────────
    if xmit_kind == "TLoad":
        xmit_pos     = pos(xmit)
        xmit_addr_st = d["addr_states"](xmit)
        xmit_mem_st  = d["inmem_states"](xmit)

        prior = [i for i in instructions if pos(i) < xmit_pos]

        # ── SLF check ─────────────────────────────────────────────────────────
        # A prior TStore uses the same address state element as the xmit load.
        # Also check outmem/inmem match as a fallback.
        for instr in prior:
            if kind.get(instr, "").split("$")[0] != "TStore":
                continue
            store_addr_st = d["addr_states"](instr)
            if xmit_addr_st & store_addr_st:
                return "SLF"
            store_out_st = d["outmem_states"](instr)
            if xmit_mem_st & store_out_st:
                return "SLF"

        # ── LL check ──────────────────────────────────────────────────────────
        # xmit's address state matches a TOther's outreg state; that TOther's
        # inreg states include one from an unresolved TLoad and one from a
        # resolved TLoad.
        if xmit_addr_st:
            # Build lookup: state → instructions that produce it via outreg
            state_to_producer = defaultdict(list)
            for instr in instructions:
                for st in d["outreg_states"](instr):
                    state_to_producer[st].append(instr)

            for addr_state in xmit_addr_st:
                for producer in state_to_producer.get(addr_state, []):
                    if kind.get(producer, "").split("$")[0] not in ("TOthern", "TOtherx"):
                        continue
                    # Found a TOther that computes the xmit's address
                    tother_in_states = d["inreg_states"](producer)
                    has_unresolved_load = False
                    has_resolved_load   = False
                    for st in tother_in_states:
                        for src in state_to_producer.get(st, []):
                            src_kind = kind.get(src, "").split("$")[0]
                            if src_kind == "TLoad":
                                if src in isresolved:
                                    has_resolved_load = True
                                else:
                                    has_unresolved_load = True
                    if has_unresolved_load and has_resolved_load:
                        return "LL"

        return "OtherLoad"

    # ── Other ─────────────────────────────────────────────────────────────────
    return "Other"


def main():
    ap = argparse.ArgumentParser(description="Categorize hit XMLs by transmitter pattern")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--hits-dir",   type=Path,
                     help="Folder of hit .txt files (stems used to find XMLs)")
    grp.add_argument("--stems-file", type=Path,
                     help="Plain text file with one stem per line")
    ap.add_argument("--xml-dir",  required=True, type=Path,
                    help="Folder containing inst-XXXXXX.xml files")
    ap.add_argument("--verbose",  action="store_true")
    args = ap.parse_args()

    xml_dir = args.xml_dir.resolve()

    if args.hits_dir:
        hits_dir = args.hits_dir.resolve()
        stems = sorted(f.stem for f in hits_dir.glob("*.txt"))
        if not stems:
            sys.exit(f"error: no .txt files found in {hits_dir}")
    else:
        stems = sorted(l.strip() for l in args.stems_file.read_text().splitlines()
                       if l.strip() and not l.startswith("#"))
        if not stems:
            sys.exit(f"error: no stems in {args.stems_file}")

    counts = defaultdict(int)
    by_category: dict[str, list[str]] = defaultdict(list)
    errors = []

    for stem in stems:
        xml_path = xml_dir / (stem + ".xml")
        if not xml_path.exists():
            errors.append(f"missing XML: {stem}")
            continue
        try:
            d = parse_xml(xml_path)
            if d is None:
                errors.append(f"parse error: {stem}")
                continue
            cat = categorize(d)
        except Exception as e:
            errors.append(f"{stem}: {e}")
            cat = "Error"

        counts[cat] += 1
        by_category[cat].append(stem)
        if args.verbose:
            print(f"  {stem}  →  {cat}")

    total = sum(counts.values())
    label = args.hits_dir.name if args.hits_dir else args.stems_file.stem
    print(f"\nResults ({total} hits in {label}):")
    for cat in ["SLF", "LL", "OtherLoad", "BR", "Other", "Error"]:
        n = counts.get(cat, 0)
        if n:
            print(f"  {cat:<12} {n:>5}  ({100*n/total:.1f}%)")

    if errors:
        print(f"\nErrors/missing ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e}")

    if args.verbose or True:
        print()
        for cat in ["SLF", "LL", "OtherLoad", "BR", "Other"]:
            items = by_category.get(cat, [])
            if items:
                preview = ", ".join(items[:5])
                more = f"  ... +{len(items)-5} more" if len(items) > 5 else ""
                print(f"  {cat}: {preview}{more}")


if __name__ == "__main__":
    main()
