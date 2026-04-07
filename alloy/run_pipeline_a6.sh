#!/usr/bin/env bash
# run_pipeline_a6.sh — Full pipeline using Alloy 6, everything after XML batched
#
# Usage: bash run_pipeline_a6.sh [BATCH_SIZE] [JOBS]
#   BATCH_SIZE : files per batch for LLVM/compile/gem5 (default: 1000)
#   JOBS       : parallel gem5 jobs per batch (default: 8)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BATCH="${1:-1000}"
JOBS="${2:-8}"
CAP=100000
MODEL="models/STT_4.als"
BASE="alloy-out/STT_4_a6"
XML_DIR="$BASE/xml"
LLVM_DIR="$BASE/llvm"
ASM_DIR="$BASE/asm"
HITS="$BASE/window-hits.txt"
RESULTS="$BASE/window-results.json"

mkdir -p "$XML_DIR" "$LLVM_DIR" "$ASM_DIR"
[ -f "$HITS" ]    || touch "$HITS"
[ -f "$RESULTS" ] || echo "[]" > "$RESULTS"

echo "========================================"
echo "  SimSpect pipeline (Alloy 6)"
echo "  model=$MODEL  batch=$BATCH  jobs=$JOBS"
echo "========================================"

# ── Step 1: Generate ALL XML ─────────────────────────────────────────────────
EXISTING=$(find "$XML_DIR" -maxdepth 1 -name 'inst-*.xml' | wc -l)
echo ""
echo "── Step 1: XML generation ──"
if [ "$EXISTING" -eq 0 ]; then
    java -cp alloy6.jar:. a6CountModels "$MODEL" "$XML_DIR" "$CAP" 2>&1 | tee "$BASE/countmodels.log"
else
    echo "   Already have $EXISTING XML files, skipping."
fi
TOTAL=$(find "$XML_DIR" -maxdepth 1 -name 'inst-*.xml' | wc -l)
echo "   Total XML instances: $TOTAL"

# ── Steps 2-4: LLVM → asm → gem5, all in batches of BATCH ───────────────────
echo ""
echo "── Steps 2-4: Batched LLVM → asm → gem5 (batch=$BATCH, jobs=$JOBS) ──"
python3 - "$BATCH" "$JOBS" <<'PYEOF'
import subprocess, sys, json, os, shutil, tempfile
from pathlib import Path

BATCH = int(sys.argv[1])
JOBS  = int(sys.argv[2])

xml_dir  = Path("alloy-out/STT_4_a6/xml")
llvm_dir = Path("alloy-out/STT_4_a6/llvm")
asm_dir  = Path("alloy-out/STT_4_a6/asm")
hits_f   = Path("alloy-out/STT_4_a6/window-hits.txt")
res_f    = Path("alloy-out/STT_4_a6/window-results.json")

xml_files     = sorted(xml_dir.glob("inst-*.xml"))
total_batches = (len(xml_files) + BATCH - 1) // BATCH
already_done  = {r["name"] for r in json.loads(res_f.read_text())}
cum_hits = cum_total = 0

print(f"  {len(xml_files)} XML files → {total_batches} batches of {BATCH}", flush=True)

for bn, start in enumerate(range(0, len(xml_files), BATCH), 1):
    batch = xml_files[start : start + BATCH]
    stems = [f.stem for f in batch]
    print(f"\n=== Batch {bn}/{total_batches}  ({batch[0].stem} … {batch[-1].stem}) ===", flush=True)

    # -- [2] LLVM IR --
    todo_xml = [f for f in batch if not (llvm_dir / (f.stem + ".ll")).exists()]
    if todo_xml:
        print(f"  [2] LLVM IR: {len(todo_xml)} to generate ...", flush=True)
        tmp_xml = Path(tempfile.mkdtemp(prefix="batch_xml_"))
        for f in todo_xml:
            shutil.copy(f, tmp_xml / f.name)
        subprocess.run(
            ["python3", "batch_generate.py", str(tmp_xml),
             "--out", str(llvm_dir), "--kind"],
            text=True, check=False
        )
        shutil.rmtree(tmp_xml, ignore_errors=True)
        done = sum(1 for s in stems if (llvm_dir / (s + ".ll")).exists())
        print(f"    {done}/{len(batch)} .ll files ready", flush=True)
    else:
        print(f"  [2] LLVM IR: all done, skipping.", flush=True)

    # -- [3] Compile x86 --
    todo_ll = [llvm_dir / (s + ".ll") for s in stems
               if (llvm_dir / (s + ".ll")).exists()
               and not (asm_dir / (s + ".s")).exists()]
    if todo_ll:
        print(f"  [3] x86 asm: compiling {len(todo_ll)} ...", flush=True)
        ok = err = 0
        for ll in todo_ll:
            r = subprocess.run(
                ["python3", "compile_annotate.py", str(ll), "--out-dir", str(asm_dir)],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                ok += 1
            else:
                err += 1
                print(f"    [err] {ll.name}: {r.stderr.strip()[:120]}", flush=True)
        print(f"    compiled={ok}  errors={err}", flush=True)
    else:
        print(f"  [3] x86 asm: all done, skipping.", flush=True)

    # -- [4] gem5 window check --
    to_test = [s for s in stems
               if s not in already_done
               and (asm_dir / (s + ".s")).exists()
               and (asm_dir / (s + ".ann.json")).exists()]
    if not to_test:
        print(f"  [4] gem5: all already tested, skipping.", flush=True)
        continue

    print(f"  [4] gem5: running {len(to_test)} tests ...", flush=True)
    tmp_asm = Path(tempfile.mkdtemp(prefix="gem5_batch_"))
    for s in to_test:
        shutil.copy(asm_dir / (s + ".s"),        tmp_asm / (s + ".s"))
        shutil.copy(asm_dir / (s + ".ann.json"), tmp_asm / (s + ".ann.json"))

    batch_res_f = Path(f"alloy-out/STT_4_a6/batch_{bn:04d}_results.json")
    subprocess.run(
        ["python3", "/tests/run_helpers/pipeline_window.py", str(tmp_asm),
         "--jobs", str(JOBS), "--out", str(batch_res_f)],
        text=True, check=False
    )
    shutil.rmtree(tmp_asm, ignore_errors=True)

    if not batch_res_f.exists():
        print(f"  [4] gem5 failed for batch {bn}", flush=True)
        continue

    batch_results = json.loads(batch_res_f.read_text())
    batch_hits = [r["name"] for r in batch_results if r.get("issued_in_window") is True]
    batch_errs = sum(1 for r in batch_results if r["status"] != "ok")

    if batch_hits:
        with hits_f.open("a") as f:
            f.write("\n".join(batch_hits) + "\n")

    existing = json.loads(res_f.read_text())
    existing.extend(batch_results)
    res_f.write_text(json.dumps(existing, indent=2))
    already_done.update(r["name"] for r in batch_results)

    cum_hits  += len(batch_hits)
    cum_total += len(batch_results)
    print(f"    hits={len(batch_hits)}  errors={batch_errs}", flush=True)
    print(f"  >> cumulative: {cum_hits} hits / {cum_total} tested", flush=True)

print(f"\n========================================")
print(f"  DONE  total={cum_total}  hits={cum_hits}")
print(f"  Hits    : alloy-out/STT_4_a6/window-hits.txt")
print(f"  Results : alloy-out/STT_4_a6/window-results.json")
PYEOF

echo ""
echo "========================================"
echo "  Pipeline complete."
echo "========================================"
