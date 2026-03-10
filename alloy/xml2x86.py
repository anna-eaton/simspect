#!/usr/bin/env python3
"""
batch_xml_to_x86.py

Walk a folder of Alloy XML instance files, convert each to LLVM IR (.ll),
then assemble to x86 object files (.o) (and optionally link to executables).

Assumes:
- You already have llvm_from_xml.py (the converter) in the same directory
  OR on PYTHONPATH, and it exposes:
    - parse_alloy_xml(xml_text: str) -> (your instance object)
    - emit_llvm_from_instance(inst, ...) -> str  (LLVM IR)

Toolchain requirements (installed on your machine):
- llc (LLVM static compiler) OR clang
- For pure assembly to x86 object: llc is simplest.
"""

from __future__ import annotations
import argparse
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

# Import your existing converter
# Adjust the import name/path if needed.
# import alloy.xml2llvm as xml2llvm
import xml2llvm

def run(cmd: list[str], *, cwd: Optional[Path] = None) -> None:
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def find_tool(name: str) -> Optional[str]:
    from shutil import which
    return which(name)


from shutil import which

def convert_one(
    xml_path: Path,
    out_dir: Path,
    *,
    triple: str,
    cpu: str,
    kind_override: Optional[Dict[str, str]] = None,
    op_map: Optional[Dict[str, str]] = None,
    default_const: int = 42,
    ret_policy: str = "last",
) -> tuple[Path, Path]:
    xml_text = xml_path.read_text(encoding="utf-8", errors="strict")
    inst = xml2llvm.parse_alloy_xml(xml_text)

    ll = xml2llvm.emit_llvm_from_instance(
        inst,
        kind_override=kind_override or {},
        op_map=op_map or {},
        default_const=default_const,
        ret_policy=ret_policy,
        init_regs_to_zero=True,
    )

    stem = xml_path.stem
    ll_path = out_dir / f"{stem}.ll"
    s_path = out_dir / f"{stem}.s"
    o_path = out_dir / f"{stem}.o"

    ll_path.write_text(ll, encoding="utf-8")

    llc = which("llc")
    clang = which("clang")

    if not llc:
        raise RuntimeError("`llc` not found. Install LLVM (brew install llvm) and ensure llc is on PATH.")

    # Best: llc emits a real object file for the target triple
    # Note: -mcpu is optional; llc accepts it for x86 but you can omit if it causes issues.
    cmd = ["llc", f"-mtriple={triple}", "-filetype=obj", str(ll_path), "-o", str(o_path)]
    if cpu:
        cmd.insert(2, f"-mcpu={cpu}")
    run(cmd)

    # If you want to inspect assembly too, also emit .s:
    run(["llc", f"-mtriple={triple}", "-filetype=asm", str(ll_path), "-o", str(s_path)])

    return ll_path, o_path



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xml_dir", type=Path, help="Folder containing Alloy XML instance files")
    ap.add_argument("--out", type=Path, default=Path("out_llvm"), help="Output folder")
    ap.add_argument("--glob", default="*.xml", help="Glob for XML files (default: *.xml)")

    # x86 target controls
    ap.add_argument("--triple", default="x86_64-unknown-linux-gnu",
                    help="LLVM target triple (default: x86_64-unknown-linux-gnu)")
    ap.add_argument("--cpu", default="x86-64", help="LLVM CPU (default: x86-64)")

    # Optional link step
    ap.add_argument("--link", action="store_true", help="Also link each .o into an executable")
    ap.add_argument("--cc", default="clang", help="C compiler to link with (default: clang)")

    # Optional: one combined binary
    ap.add_argument("--link-all", action="store_true", help="Link all objects into one binary")
    ap.add_argument("--bin-name", default="all_tests", help="Name for the combined binary")

    args = ap.parse_args()

    xml_dir: Path = args.xml_dir
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(xml_dir.glob(args.glob))
    if not xml_files:
        raise SystemExit(f"No files matched {args.glob} in {xml_dir}")

    # If you want per-instruction opcode choices from an external file,
    # load it here and pass op_map/kind_override into convert_one().
    kind_override: Dict[str, str] = {}
    op_map: Dict[str, str] = {}

    objects: list[Path] = []
    for p in xml_files:
        print(f"\n=== {p.name} ===")
        ll_path, o_path = convert_one(
            p, out_dir,
            triple=args.triple,
            cpu=args.cpu,
            kind_override=kind_override,
            op_map=op_map,
            default_const=42,
            ret_policy="last",
        )
        print(f"Wrote {ll_path.name} and {o_path.name}")
        objects.append(o_path)

        if args.link:
            exe = out_dir / p.stem
            cc = find_tool(args.cc) or args.cc
            # No libc needed if your IR doesn't call out; but easiest is normal link.
            run([cc, str(o_path), "-o", str(exe)])
            print(f"Linked {exe.name}")

    if args.link_all:
        exe = out_dir / args.bin_name
        cc = find_tool(args.cc) or args.cc
        run([cc, *map(str, objects), "-o", str(exe)])
        print(f"\nLinked combined binary: {exe}")

    print("\nDone.")


if __name__ == "__main__":
    main()
