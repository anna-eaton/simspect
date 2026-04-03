"""
batch_generate.py — Run the SimSpect pipeline on a folder of Alloy XML instances.

Usage:
    python3 batch_generate.py <input_dir> [--out <output_dir>] [--pattern <glob>]

For each matching XML file the script:
  1. Runs passes 1-5 of the parsexml pipeline.
  2. Writes <stem>.ll  (LLVM IR) to the output directory.
  3. Writes <stem>.ann.json (branch annotations) to the output directory.

Bifurcation on branch mode (mispredict_not_taken vs mispredict_taken) is
structured for easy addition later: see RUN_MODES and the per-mode subdirectory
logic below.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

# Make sure parsexml is importable from the same directory as this script.
sys.path.insert(0, str(Path(__file__).parent))

import importlib as _importlib

def _load_parser(kind: bool):
    mod = _importlib.import_module("parsexml_kind" if kind else "parsexml")
    return (
        mod.parse_alloy_xml,
        mod.pass1_specify_state_a,
        mod.pass2_specify_instructions,
        mod.pass2_5_specify_branches,
        mod.pass3_assign_operands,
        mod.pass4_ssa,
        mod.pass5_emit_llvm,
        mod.emit_branch_annotations,
    )

# defaults (overridden by --kind at runtime)
from parsexml import (
    parse_alloy_xml,
    pass1_specify_state_a,
    pass2_specify_instructions,
    pass2_5_specify_branches,
    pass3_assign_operands,
    pass4_ssa,
    pass5_emit_llvm,
    emit_branch_annotations,
)


# ---------------------------------------------------------------------------
# Branch modes
# When bifurcation is enabled, add "mispredict_taken" here.
# Each mode gets its own subdirectory inside the output folder.
# ---------------------------------------------------------------------------
RUN_MODES: list[str] = [
    "mispredict_not_taken",
    # "mispredict_taken",   # uncomment when pass2_5 supports it
]


def run_pipeline(xml_text: str, stem: str, out_dir: Path, mode: str,
                 _fns=None) -> None:
    """Run the full pipeline for one XML file and one branch mode."""
    (parse_alloy_xml, pass1_specify_state_a, pass2_specify_instructions,
     pass2_5_specify_branches, pass3_assign_operands, pass4_ssa,
     pass5_emit_llvm, emit_branch_annotations) = _fns
    inst = parse_alloy_xml(xml_text)
    r1   = pass1_specify_state_a(inst,   write_out=False)
    r2   = pass2_specify_instructions(r1, write_out=False)
    r25  = pass2_5_specify_branches(r2,   write_out=False)
    r3   = pass3_assign_operands(r25,     write_out=False)
    r4   = pass4_ssa(r3,                  write_out=False)

    ll_path  = out_dir / f"{stem}.ll"
    ann_path = out_dir / f"{stem}.ann.json"

    pass5_emit_llvm(r4, func_name=stem, out_path=str(ll_path),  write_out=True)
    emit_branch_annotations(r4,         out_path=str(ann_path), write_out=True)


def has_unresolved_branch(xml_text: str, parse_fn, pass1_fn) -> bool:
    """Return True if the instance contains at least one unresolved branch."""
    inst = parse_fn(xml_text)
    r1   = pass1_fn(inst, write_out=False)
    return any(
        i["kind"] in ("br_n", "br_x") and not i.get("resolved", False)
        for i in r1["instructions"]
    )


def process_folder(
    input_dir: Path,
    output_dir: Path,
    pattern: str,
    modes: list[str],
    kind: bool = False,
    filter_unresolved_branch: bool = False,
    limit: int = 0,
) -> None:
    _fns = _load_parser(kind)
    parse_fn, pass1_fn = _fns[0], _fns[1]
    xml_files = sorted(input_dir.glob(pattern))

    if not xml_files:
        print(f"No files matching '{pattern}' found in {input_dir}")
        return

    if filter_unresolved_branch:
        xml_files = [f for f in xml_files
                     if has_unresolved_branch(f.read_text(encoding="utf-8"), parse_fn, pass1_fn)]
        print(f"After filter: {len(xml_files)} file(s) with an unresolved branch.")
    else:
        print(f"Found {len(xml_files)} file(s) in {input_dir}")

    if limit > 0:
        xml_files = xml_files[:limit]
        print(f"Limiting to first {limit} file(s).")

    ok = err = 0

    for xml_path in xml_files:
        stem = xml_path.stem  # e.g. "inst-000006"
        xml_text = xml_path.read_text(encoding="utf-8")

        for mode in modes:
            # Each mode gets its own subdirectory; skip subdir if only one mode.
            if len(modes) == 1:
                mode_dir = output_dir
            else:
                mode_dir = output_dir / mode
            mode_dir.mkdir(parents=True, exist_ok=True)

            try:
                run_pipeline(xml_text, stem, mode_dir, mode, _fns=_fns)  # type: ignore[call-arg]
                print(f"  [ok]  {xml_path.name}  ({mode})")
                ok += 1
            except NotImplementedError as exc:
                print(f"  [skip] {xml_path.name}  ({mode}): {exc}")
                err += 1
            except Exception:
                print(f"  [err]  {xml_path.name}  ({mode}):")
                traceback.print_exc()
                err += 1

    total = ok + err
    print(f"\nDone: {ok}/{total} succeeded, {err}/{total} failed/skipped.")
    print(f"Output written to: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-generate LLVM IR from Alloy XML instances."
    )
    parser.add_argument(
        "input_dir",
        help="Directory containing inst-*.xml files.",
    )
    parser.add_argument(
        "--out",
        dest="output_dir",
        default=None,
        help="Output directory (default: <input_dir>-llvm).",
    )
    parser.add_argument(
        "--pattern",
        default="inst-*.xml",
        help="Glob pattern for input files (default: inst-*.xml).",
    )
    parser.add_argument(
        "--kind", action="store_true",
        help="Use parsexml_kind.py (for kind-field Alloy model output).",
    )
    parser.add_argument(
        "--unresolved-branch", action="store_true",
        help="Only process instances that contain at least one unresolved branch.",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Stop after processing this many files (0 = no limit).",
    )
    args = parser.parse_args()

    input_dir  = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_dir.parent / (input_dir.name + "-llvm")

    if not input_dir.is_dir():
        print(f"Error: input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    process_folder(input_dir, output_dir, args.pattern, RUN_MODES,
                   kind=args.kind,
                   filter_unresolved_branch=args.unresolved_branch,
                   limit=args.limit)


if __name__ == "__main__":
    main()
