#!/usr/bin/env python3
"""
audit_commit_boundary.py — check that every test's lc/fnc is an Alloy instruction.

Usage:
    python3 STAGE2_compilation/audit_commit_boundary.py <testset-or-ann-dir> [...]

Scans every *.ann.json under the given dirs and reports tests whose
commit_boundary points at a synthetic instruction (atom starting with "_":
interleave chain steps "_chainK_stepJ", the "_xm_fallthrough_nop"). Such a
test was concretized before the 2026-10-29 fix and must be regenerated from
the llvm stage. Exit status 1 if any are found. Rule:
wiki/design/COMMIT_BOUNDARY.md.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


def _ll_atoms(ann_path: Path) -> dict[int, str]:
    """pc -> atom from the test's .ll (testsets/<m>/<mode>/llvm/<stem>.ll)."""
    stem = ann_path.name[: -len(".ann.json")]
    for ll in (ann_path.parent.parent / "llvm" / f"{stem}.ll",
               ann_path.with_name(f"{stem}.ll")):
        if ll.exists():
            out: dict[int, str] = {}
            for m in re.finditer(r"^\s*; pc=(\d+)\s+(\S+)", ll.read_text(), re.M):
                out[int(m.group(1))] = m.group(2)
            return out
    return {}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    counts: Counter = Counter()
    bad: list[str] = []
    for root in sys.argv[1:]:
        for ann_path in Path(root).rglob("*.ann.json"):
            counts["ann"] += 1
            try:
                cb = json.loads(ann_path.read_text()).get("commit_boundary", {})
            except (OSError, json.JSONDecodeError) as exc:
                counts["unreadable"] += 1
                print(f"unreadable: {ann_path}: {exc}", file=sys.stderr)
                continue
            ll_atoms = None
            for key in ("last_committed", "first_noncommitted"):
                entry = cb.get(key) or {}
                atom = entry.get("atom")
                if atom is None and "pc" in entry:
                    # compile_annotate.py dropped "atom" before 2026-10-29;
                    # recover it from the .ll's "; pc=N  <atom>  (...)" comments.
                    if ll_atoms is None:
                        ll_atoms = _ll_atoms(ann_path)
                    atom = ll_atoms.get(entry["pc"])
                if atom is None:
                    counts[f"{key}_absent_or_resolved"] += 1
                elif atom.startswith("_"):
                    counts[f"{key}_synthetic"] += 1
                    bad.append(f"{ann_path}  {key}={atom}")
    for line in bad[:50]:
        print(line)
    if len(bad) > 50:
        print(f"... {len(bad) - 50} more")
    print(dict(counts))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
