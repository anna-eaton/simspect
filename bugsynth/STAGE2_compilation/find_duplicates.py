"""
find_duplicates.py — Find structurally identical pass-1 outputs across a folder.

Usage:
    python3 find_duplicates.py <input_dir> [--pattern inst-*.xml]

Runs pass 1 on every matching XML file in memory, computes a canonical
fingerprint for each (normalizing Alloy atom names so that structurally
equivalent instances match regardless of atom numbering), then groups and
prints files that share a fingerprint.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Hashable, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))


def canonicalize(result: Dict[str, Any], inst: Any = None) -> Tuple:
    """
    Return a hashable canonical fingerprint for a pass-1 result.

    Alloy assigns atom names (Reg_s$0, Mem_s$1, …) arbitrarily across
    instances.  We normalize them by assigning short canonical IDs
    ("r0", "r1", … for register states; "m0", "m1", … for memory states)
    in order of first appearance while walking instructions in PC order.

    If inst (raw parse_alloy_xml result) is provided, DDI and RF edges are
    also included in the fingerprint using canonical (pc, slot) identifiers.
    """
    reg_canon: Dict[str, str] = {}
    mem_canon: Dict[str, str] = {}

    def canon_state(raw: str | None) -> str | None:
        if raw is None:
            return None
        if raw.startswith("Reg_s"):
            if raw not in reg_canon:
                reg_canon[raw] = f"r{len(reg_canon)}"
            return reg_canon[raw]
        if raw.startswith("Mem_s"):
            if raw not in mem_canon:
                mem_canon[raw] = f"m{len(mem_canon)}"
            return mem_canon[raw]
        return raw  # fallback: keep as-is

    # Build atom → canonical (pc, slot_name) map for DDI/RF canonicalization
    atom_to_slot: Dict[str, Tuple] = {}
    instr_fingerprints: List[Tuple] = []
    for rec in result["instructions"]:
        slot_parts: List[Tuple] = []
        for slot_type, slot_list in rec["slots"].items():
            for entry in slot_list:
                slot_parts.append((slot_type, canon_state(entry.get("physical"))))
                if entry.get("operand_atom"):
                    atom_to_slot[entry["operand_atom"]] = (rec["pc"], entry["slot"])
        instr_fingerprints.append((
            rec["kind"],
            rec["resolved"],
            rec["committed"],
            tuple(slot_parts),
        ))

    # Include DDI and RF edges as canonical (src_slot, dst_slot) pairs
    ddi_fp: Tuple = ()
    rf_fp: Tuple = ()
    if inst is not None:
        ddi_fp = tuple(sorted(
            (atom_to_slot[s], atom_to_slot[d])
            for s, d in inst.fields.get("ddi", [])
            if s in atom_to_slot and d in atom_to_slot
        ))
        rf_fp = tuple(sorted(
            (atom_to_slot[s], atom_to_slot[d])
            for s, d in inst.fields.get("rf", [])
            if s in atom_to_slot and d in atom_to_slot
        ))

    ru = result["resource_usage"]
    return (
        tuple(instr_fingerprints),
        ru["register_count"],
        ru["memory_count"],
        ddi_fp,
        rf_fp,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find structurally identical pass-1 outputs."
    )
    parser.add_argument("input_dir")
    parser.add_argument("--pattern", default="inst-*.xml")
    parser.add_argument("--kind", action="store_true",
                        help="Use parsexml_kind.py (for kind-field Alloy model output)")
    args = parser.parse_args()

    if args.kind:
        from parsexml_kind import parse_alloy_xml, pass1_specify_state_a
    else:
        from parsexml import parse_alloy_xml, pass1_specify_state_a

    input_dir = Path(args.input_dir).resolve()
    xml_files = sorted(input_dir.glob(args.pattern))

    if not xml_files:
        print(f"No files matching '{args.pattern}' in {input_dir}")
        sys.exit(0)

    print(f"Scanning {len(xml_files)} file(s)…\n")

    groups: Dict[Hashable, List[str]] = defaultdict(list)
    errors: List[str] = []

    for xml_path in xml_files:
        try:
            xml_text = xml_path.read_text(encoding="utf-8")
            inst = parse_alloy_xml(xml_text)
            r1 = pass1_specify_state_a(inst, write_out=False)
            fp = canonicalize(r1, inst)
            groups[fp].append(xml_path.name)
        except Exception as exc:
            errors.append(f"  {xml_path.name}: {exc}")

    duplicates = {fp: names for fp, names in groups.items() if len(names) > 1}
    unique     = {fp: names for fp, names in groups.items() if len(names) == 1}

    if duplicates:
        print(f"Found {len(duplicates)} duplicate group(s):\n")
        for i, names in enumerate(duplicates.values(), 1):
            print(f"  Group {i} ({len(names)} files):")
            for n in names:
                print(f"    {n}")

        # Print the XML of the first two files in the first duplicate group.
        first_pair = next(iter(duplicates.values()))[:2]
        for name in first_pair:
            xml_text = (input_dir / name).read_text(encoding="utf-8")
            print(f"\n{'='*60}")
            print(f"  {name}")
            print('='*60)
            # print(xml_text)
        sys.exit(0)
    else:
        print("No duplicates found.")

    print(f"\n{len(unique)} unique instance(s), {sum(len(v) for v in duplicates.values())} file(s) in duplicate groups.")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(e)


if __name__ == "__main__":
    main()
