"""
compile_annotate.py — Compile an LLVM IR litmus test to x86-64 and update its
annotation file with real x86 byte offsets for all Alloy instructions.

Usage:
    python3 compile_annotate.py <stem.ll> [--out-dir <dir>]

Produces:
    <stem>.s          — x86-64 assembly
    <stem>.o          — ELF object file
    <stem>.ann.json   — updated annotation with x86 offsets for branches + xmit

Strategy:
  pass5_emit_llvm embeds a global asm label  __litmus_{stem}_pcN  at the
  start of each Alloy instruction.  After compiling to .o, `nm` resolves
  each label to its byte offset within the function, giving an exact
  Alloy-pc → x86-offset map.

  For branch annotations the offset of the conditional j* instruction is
  derived from the disassembly (it's the first j* at or after the pc marker),
  along with its fallthrough and taken targets.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

COND_JUMPS = {"je", "jne", "jl", "jle", "jg", "jge",
              "jb", "jbe", "ja", "jae", "jo", "jno", "js", "jns", "jp", "jnp"}


def compile_to_x86(ll_path: Path, out_dir: Path) -> tuple[Path, Path]:
    """Compile .ll → .s and .o for x86-64. Returns (s_path, o_path)."""
    s_path = out_dir / (ll_path.stem + ".s")
    o_path = out_dir / (ll_path.stem + ".o")
    for flag, out in [("-S", s_path), ("-c", o_path)]:
        r = subprocess.run(
            ["clang-15", "--target=x86_64-unknown-linux-gnu", "-O0",
             flag, str(ll_path), "-o", str(out)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(1)
    return s_path, o_path


def commit_offsets_from_nm(o_path: Path, stem: str) -> dict[str, int]:
    """
    Run nm on the object file and extract __litmus_{stem}_last_committed and
    __litmus_{stem}_first_noncommitted symbols.
    Returns {"last_committed": offset, "first_noncommitted": offset} for whichever exist.
    These labels are baked into the instruction's inline asm, so they survive
    insertion of new instructions around them.
    """
    safe = stem.replace("-", "_").replace(".", "_")
    targets = {
        f"__litmus_{safe}_last_committed":    "last_committed",
        f"__litmus_{safe}_first_noncommitted": "first_noncommitted",
    }
    r = subprocess.run(["nm", "--defined-only", str(o_path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(1)
    result: dict[str, int] = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        name = parts[-1]
        if name in targets:
            try:
                result[targets[name]] = int(parts[0], 16)
            except ValueError:
                pass
    return result


def pc_offsets_from_nm(o_path: Path, stem: str) -> dict[int, int]:
    """
    Run nm on the object file and extract __litmus_{safe_stem}_pcN symbols.
    Returns {alloy_pc: byte_offset}.
    """
    safe = stem.replace("-", "_").replace(".", "_")
    prefix = f"__litmus_{safe}_pc"

    r = subprocess.run(["nm", "--defined-only", str(o_path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(1)

    pc_map: dict[int, int] = {}
    # nm output: "<value> <type> <name>" or "<value> <size> <type> <name>"
    for line in r.stdout.splitlines():
        parts = line.split()
        name = parts[-1]
        if name.startswith(prefix):
            try:
                pc  = int(name[len(prefix):])
                val = int(parts[0], 16)
                pc_map[pc] = val
            except ValueError:
                pass
    return pc_map


def disassemble_instrs(o_path: Path) -> list[tuple[int, str, str]]:
    """Return list of (byte_offset, mnemonic, operand) from objdump."""
    r = subprocess.run(
        ["llvm-objdump-15", "--disassemble",
         "--triple=x86_64-unknown-linux-gnu", str(o_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(1)

    line_re = re.compile(r"^\s+([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*(\w+)\s*(.*)")
    instrs: list[tuple[int, str, str]] = []
    for line in r.stdout.splitlines():
        m = line_re.match(line)
        if m:
            instrs.append((int(m.group(1), 16), m.group(2).lower(), m.group(3).strip()))
    return instrs


def find_branch_at_pc(pc_offset: int, instrs: list[tuple[int, str, str]]) -> dict | None:
    """
    Find the first conditional j* instruction at or after pc_offset.
    Returns dict with offset, mnemonic, fallthrough_offset, taken_offset.
    """
    for i, (off, mnem, operand) in enumerate(instrs):
        if off < pc_offset:
            continue
        if mnem in COND_JUMPS:
            fallthrough = instrs[i + 1][0] if i + 1 < len(instrs) else None
            target_m = re.search(r"0x([0-9a-f]+)", operand)
            taken = int(target_m.group(1), 16) if target_m else None
            return {"offset": off, "mnemonic": mnem,
                    "fallthrough_offset": fallthrough, "taken_offset": taken}
    return None


def update_annotations(ann_path: Path, pc_map: dict[int, int],
                        instrs: list[tuple[int, str, str]],
                        commit_offsets: dict[str, int] | None = None) -> dict:
    ann = json.loads(ann_path.read_text())

    # --- branch annotations ---
    for entry in ann.get("annotations", []):
        alloy_pc = entry.get("branch_pc")
        if alloy_pc is None or alloy_pc not in pc_map:
            continue
        pc_offset = pc_map[alloy_pc]
        entry["x86_pc_offset"]     = pc_offset
        entry["x86_pc_offset_hex"] = hex(pc_offset)

        br = find_branch_at_pc(pc_offset, instrs)
        if br:
            entry["x86_branch_offset"]      = br["offset"]
            entry["x86_branch_offset_hex"]  = hex(br["offset"])
            entry["x86_mnemonic"]           = br["mnemonic"]
            if entry.get("mode") == "mispredict_not_taken":
                entry["x86_btb_predicted_offset"]     = br["fallthrough_offset"]
                entry["x86_btb_predicted_offset_hex"] = (
                    hex(br["fallthrough_offset"]) if br["fallthrough_offset"] is not None else None)
                entry["x86_actual_target_offset"]     = br["taken_offset"]
                entry["x86_actual_target_offset_hex"] = (
                    hex(br["taken_offset"]) if br["taken_offset"] is not None else None)
            else:
                entry["x86_fallthrough_offset"] = br["fallthrough_offset"]
                entry["x86_taken_offset"]       = br["taken_offset"]

    # --- xmit annotation ---
    xmit = ann.get("xmit")
    if xmit is not None:
        alloy_pc = xmit.get("pc")
        if alloy_pc is not None and alloy_pc in pc_map:
            xmit["x86_offset"]     = pc_map[alloy_pc]
            xmit["x86_offset_hex"] = hex(pc_map[alloy_pc])

    # --- commit boundary annotations ---
    cb = ann.get("commit_boundary")
    if cb is not None and commit_offsets:
        for key in ("last_committed", "first_noncommitted"):
            entry = cb.get(key)
            if entry is not None and key in commit_offsets:
                entry["x86_offset"]     = commit_offsets[key]
                entry["x86_offset_hex"] = hex(commit_offsets[key])

    return ann


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile LLVM IR litmus test to x86-64 and update annotations with real x86 offsets."
    )
    parser.add_argument("ll_file", help="Path to the .ll file")
    parser.add_argument("--out-dir", default=None,
                        help="Output directory (default: same as .ll file)")
    args = parser.parse_args()

    ll_path  = Path(args.ll_file).resolve()
    out_dir  = Path(args.out_dir).resolve() if args.out_dir else ll_path.parent
    ann_path = ll_path.with_suffix(".ann.json")

    for p in (ll_path, ann_path):
        if not p.exists():
            print(f"Error: {p} not found", file=sys.stderr); sys.exit(1)

    print(f"Compiling {ll_path.name} → x86-64 ...")
    s_path, o_path = compile_to_x86(ll_path, out_dir)
    print(f"  wrote {s_path.name}, {o_path.name}")

    pc_map = pc_offsets_from_nm(o_path, ll_path.stem)
    print(f"  pc markers found: {sorted(pc_map.items())}")

    commit_offsets = commit_offsets_from_nm(o_path, ll_path.stem)
    if commit_offsets:
        print(f"  commit boundary labels found: {commit_offsets}")

    instrs = disassemble_instrs(o_path)
    ann = update_annotations(ann_path, pc_map, instrs, commit_offsets)

    out_ann = out_dir / ann_path.name
    out_ann.write_text(json.dumps(ann, indent=2) + "\n")
    print(f"  updated annotation → {out_ann.name}")
    print(json.dumps(ann, indent=2))


if __name__ == "__main__":
    main()
