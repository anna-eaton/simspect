#!/usr/bin/env python3
"""
run.py — Custom pipeline for the getOldestTaint STT bug test.

Scenario (program order):
  PC 0  branch_outer   correctly NOT-taken, slow condition (cache-miss)
                        → creates speculation window so BOTH loads run
                          while they are still speculative
  PC 1  load_A → Ra    speculative under branch_outer's window → tainted
  PC 2  branch_inner   mispredicts NOT-taken (actually TAKEN), slow cond
  PC 3  load_B → Rb    speculative → tainted (different physical reg: rcx)
  PC 4  add Ra,Rb→Rc   getOldestTaint picks load_A (lower seqNum) → Rc
                        tainted with load_A, not load_B
  PC 5  load[Rc]→Rd    (xm transmitter) stalled by STT because rax tainted

Bug trigger:
  branch_outer resolves (correctly not-taken) → load_A commits
    → freeTaints() removes load_A's taint → rax no longer tainted
    → load[Rc] is no longer stalled → FIRES
  But load_B (rcx) is STILL speculative (branch_inner unresolved)!
  Rc = Ra + Rb depends on speculative Rb, yet STT allowed load[Rc] through.

Both branch conditions are evicted from cache in a single bulk clflush
before any target instructions execute, so both create wide (~200-300
cycle) speculation windows.
"""

import sys, json, subprocess, shutil, tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Use the patched copy of parsexml in this directory
sys.path.insert(0, str(Path(__file__).parent))
from parsexml_patched import (
    parse_alloy_xml,
    pass1_specify_state_a,
    pass2_specify_instructions,
    pass3_assign_operands,
    pass4_ssa,
    pass5_emit_llvm,
    emit_branch_annotations,
    _BRANCH_KINDS,
)

# Paths (use resolve() so relative __file__ works from any CWD)
HERE       = Path(__file__).resolve().parent
REPO_ROOT  = HERE.parent
XML_PATH   = REPO_ROOT / "alloy" / "alloy-out" / "all" / "xml" / "inst-oldest-taint-bug.xml"
OUT_DIR    = REPO_ROOT / "alloy" / "alloy-out" / "all" / "ll"
STAGE2     = REPO_ROOT / "STAGE2_compilation"
STEM       = "inst-oldest-taint-bug"
COMPILE_ANN = HERE / "compile_annotate_patched.py"


# ---------------------------------------------------------------------------
# Custom pass 2.5
# ---------------------------------------------------------------------------
def custom_pass25(pass2_result: Dict[str, Any]) -> Dict[str, Any]:
    """Annotate BOTH branches with slow-condition machinery.

    branch_outer (resolved=True, committed=True):
        mode = "correctly_not_taken"
        init_val = 0  → condition false → NOT taken (correct prediction)
        Creates speculation window for load_A AND load_B.

    branch_inner (resolved=False):
        mode = "mispredict_not_taken"
        init_val = 1  → condition true → TAKEN (BTB predicts fall-through → mispredict)
    """
    n = len(pass2_result["instructions"])
    instructions: List[Dict[str, Any]] = [dict(r) for r in pass2_result["instructions"]]
    needs_end_block = False

    for rec in instructions:
        if rec.get("kind") not in _BRANCH_KINDS:
            continue
        pc      = rec["pc"]
        next_pc = pc + 1
        ft      = f"bb_{next_pc}" if next_pc < n else "end_block"
        needs_end_block = True

        # Force conditional branch (in case pass2 chose br_uncond)
        if rec.get("concrete_instruction") == "br_uncond":
            rec["concrete_instruction"] = "br_cond"
            rec["llvm_op"] = "br i1"
            cands = rec.get("candidates", [])
            if "br_cond" not in cands:
                rec["candidates"] = cands + ["br_cond"]

        if rec.get("resolved", False):
            # branch_outer — correctly not-taken
            rec["branch_annotations"] = {
                "mode":               "correctly_not_taken",
                "condition_value":    False,
                "taken_target":       "end_block",  # never reached
                "fallthrough_target": ft,
                "btb_prediction":     "fall_through",
                "btb_predicted_pc":   next_pc,
            }
        else:
            # branch_inner — mispredicts not-taken
            rec["branch_annotations"] = {
                "mode":               "mispredict_not_taken",
                "condition_value":    True,
                "taken_target":       "end_block",
                "fallthrough_target": ft,
                "btb_prediction":     "fall_through",
                "btb_predicted_pc":   next_pc,
            }

    return {
        "instructions": instructions,
        "resource_usage": pass2_result["resource_usage"],
        "branch_mode":    "custom_oldest_taint_bug",
        "needs_end_block": needs_end_block,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline() -> None:
    print(f"=== getOldestTaint STT bug pipeline ===")
    print(f"XML : {XML_PATH}")
    print(f"OUT : {OUT_DIR}")

    xml_text = XML_PATH.read_text()
    inst     = parse_alloy_xml(xml_text)

    p1  = pass1_specify_state_a(inst, write_out=False)
    p2  = pass2_specify_instructions(p1,  write_out=False)
    p25 = custom_pass25(p2)
    p3  = pass3_assign_operands(p25, write_out=False)
    p4  = pass4_ssa(p3, write_out=False)

    print("\n--- locked_registers ---")
    for atom, phys in p4["locked_registers"].items():
        print(f"  {atom} → {phys}")
    print("--- ssa_init ---")
    for reg, name in p4["ssa_init"].items():
        print(f"  {reg}: {name}")
    print("--- branch annotations ---")
    for rec in p4["instructions"]:
        ba = rec.get("branch_annotations")
        if ba:
            print(f"  pc={rec['pc']} ({rec['instruction']}) mode={ba['mode']} "
                  f"ft={ba['fallthrough_target']} taken={ba['taken_target']}")

    # Pass 5: emit LLVM IR
    ir = pass5_emit_llvm(p4, func_name=STEM, write_out=False)

    # Write outputs
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ll_path  = OUT_DIR / f"{STEM}.ll"
    ann_path = OUT_DIR / f"{STEM}.ann.json"

    ll_path.write_text(ir + "\n")
    print(f"\nWrote {ll_path}")

    emit_branch_annotations(p4, out_path=str(ann_path), write_out=True)
    print(f"Wrote {ann_path}")

    print("\n--- LLVM IR ---")
    print(ir)

    # Compile and annotate
    print(f"\n=== compile_annotate.py ===")
    r = subprocess.run(
        [sys.executable, str(COMPILE_ANN),
         str(ll_path), "--out-dir", str(OUT_DIR), "--ann-dir", str(OUT_DIR)],
        capture_output=False,
    )
    if r.returncode != 0:
        print("compile_annotate.py failed", file=sys.stderr)
        sys.exit(r.returncode)


if __name__ == "__main__":
    run_pipeline()
