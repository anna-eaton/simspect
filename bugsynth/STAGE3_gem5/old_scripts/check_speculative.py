#!/usr/bin/env python3
"""
Parse an O3PipeView trace and report whether instructions in a given
PC range were executed speculatively (fetched but squashed / not retired).

Usage:
    python3 check_speculative.py <pipeview.txt> [--pcs 0x40104c 0x401051 ...]

If --pcs is not given it defaults to the bb_1 block of inst-000003:
    0x40104c  mov -0x10(%rsp),%rax
    0x401051  mov %rax,%rax
    0x401054  mov -0x18(%rsp),%rax
    0x401059  mov %rax,-0x8(%rsp)
"""

import sys
import argparse
from collections import defaultdict

# ── default bb_1 PCs ────────────────────────────────────────────────────────
BB1_PCS = {0x40104c, 0x401051, 0x401054, 0x401059}


def parse_trace(path):
    """
    Returns a list of dicts, one per instruction (all micro-ops included).
    Each dict has keys: fetch, decode, rename, dispatch, issue, complete,
    retire, pc, upc, seq, disasm.
    A tick value of 0 means that stage was never reached (squashed).
    """
    instructions = []
    current = None

    with open(path) as f:
        for line in f:
            line = line.rstrip()
            if not line.startswith("O3PipeView:"):
                continue
            parts = line.split(":")
            stage = parts[1]

            if stage == "fetch":
                # fetch:<tick>:<pc>:<upc>:<seq>:<disasm>
                tick   = int(parts[2])
                pc     = int(parts[3], 16)
                upc    = int(parts[4])
                seq    = int(parts[5])
                disasm = parts[6].strip() if len(parts) > 6 else ""
                current = dict(fetch=tick, decode=0, rename=0, dispatch=0,
                               issue=0, complete=0, retire=0,
                               pc=pc, upc=upc, seq=seq, disasm=disasm)
                instructions.append(current)

            elif stage in ("decode", "rename", "dispatch", "issue", "complete"):
                if current is not None:
                    current[stage] = int(parts[2])

            elif stage == "retire":
                if current is not None:
                    current["retire"] = int(parts[2])
                    current = None   # record complete

    return instructions


def classify(instr):
    """Return 'committed', 'squashed', or 'in-flight'."""
    if instr["retire"] > 0:
        return "committed"
    if instr["fetch"] > 0:
        return "squashed"
    return "in-flight"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tracefile")
    ap.add_argument("--pcs", nargs="*", type=lambda x: int(x, 16),
                    default=None,
                    help="hex PCs to watch (default: bb_1 of inst-000003)")
    args = ap.parse_args()

    watch_pcs = set(args.pcs) if args.pcs is not None else BB1_PCS

    instrs = parse_trace(args.tracefile)

    # ── per-PC summary ───────────────────────────────────────────────────────
    by_pc = defaultdict(list)
    for i in instrs:
        if i["pc"] in watch_pcs:
            by_pc[i["pc"]].append(i)

    print(f"Watching {len(watch_pcs)} PC(s) in trace ({len(instrs)} total records)\n")

    any_speculative = False
    for pc in sorted(watch_pcs):
        records = by_pc[pc]
        if not records:
            print(f"  0x{pc:08x}  — never fetched")
            continue
        for r in records:
            status = classify(r)
            if status == "squashed":
                any_speculative = True
            flag = " *** SPECULATIVE (squashed)" if status == "squashed" else ""
            print(f"  0x{r['pc']:08x}.{r['upc']}  seq={r['seq']:4d}  "
                  f"fetch={r['fetch']:8d}  retire={r['retire']:8d}  "
                  f"[{status}]  {r['disasm']}{flag}")

    print()
    if any_speculative:
        print("RESULT: bb_1 instructions were FETCHED SPECULATIVELY and squashed.")
        print("        The branch mispredicted (predicted not-taken, actually taken).")
    else:
        # check if committed or never fetched
        fetched = any(by_pc[pc] for pc in watch_pcs)
        if fetched:
            print("RESULT: bb_1 instructions were committed — branch went not-taken.")
        else:
            print("RESULT: bb_1 instructions were NEVER FETCHED.")
            print("        The branch predictor correctly predicted taken; bb_1 was skipped entirely.")


if __name__ == "__main__":
    main()
