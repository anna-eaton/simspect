#!/usr/bin/env bash
# run_full_pipeline.sh — End-to-end: Alloy XML → LLVM IR → x86 asm → gem5 window check
#
# Usage:
#   bash run_full_pipeline.sh [JOBS]
#   JOBS : parallel gem5 jobs (default: 8)
#
# Generates ALL instances the model produces (hard cap: 100000).
#
# Output:
#   alloy-out/all/xml/                — Alloy XML instances
#   alloy-out/all/llvm/               — LLVM IR + .ann.json
#   alloy-out/all/asm/                — .s, .o, updated .ann.json
#   alloy-out/all/window-results.json — full gem5 results per test
#   alloy-out/all/window-hits.txt     — tests where xmit issued in speculative window

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

JOBS="${1:-8}"
CAP=100000

MODEL="models/STT_4.als"
OUT_BASE="alloy-out/all"
XML_DIR="$OUT_BASE/xml"
LLVM_DIR="$OUT_BASE/llvm"
ASM_DIR="$OUT_BASE/asm"
RESULTS="$OUT_BASE/window-results.json"
HITS="$OUT_BASE/window-hits.txt"

mkdir -p "$XML_DIR" "$LLVM_DIR" "$ASM_DIR"

echo "========================================"
echo "  SimSpect full pipeline"
echo "  model  : $MODEL"
echo "  cap    : $CAP"
echo "  jobs   : $JOBS"
echo "========================================"

# ── Step 1: Generate XML instances ──────────────────────────────────────────
EXISTING_XML=$(find "$XML_DIR" -maxdepth 1 -name 'inst-*.xml' 2>/dev/null | wc -l)
echo ""
echo "── Step 1: Alloy XML generation ──"
echo "   Already have $EXISTING_XML XML files."

if [ "$EXISTING_XML" -eq 0 ]; then
    echo "   Running CountModels (cap=$CAP) ..."
    java -cp alloy4.2.jar:. CountModels "$MODEL" "$XML_DIR" "$CAP" 2>&1 | tee "$OUT_BASE/countmodels.log"
else
    echo "   Skipping (already generated)."
fi

TOTAL_XML=$(find "$XML_DIR" -maxdepth 1 -name 'inst-*.xml' | wc -l)
echo "   Total XML instances: $TOTAL_XML"

# ── Step 2: XML → LLVM IR ────────────────────────────────────────────────────
echo ""
echo "── Step 2: XML → LLVM IR ──"
python3 batch_generate.py "$XML_DIR" --out "$LLVM_DIR" --kind 2>&1 | tee "$OUT_BASE/batch_generate.log"
TOTAL_LL=$(find "$LLVM_DIR" -maxdepth 1 -name '*.ll' | wc -l)
echo "   Total .ll files: $TOTAL_LL"

# ── Step 3: LLVM IR → x86 asm (skip already compiled) ───────────────────────
echo ""
echo "── Step 3: LLVM IR → x86 asm ──"
python3 - <<'PYEOF' 2>&1 | tee "$OUT_BASE/compile.log"
import subprocess
from pathlib import Path

ll_dir  = Path("alloy-out/all/llvm")
asm_dir = Path("alloy-out/all/asm")
asm_dir.mkdir(exist_ok=True)

ll_files = sorted(ll_dir.glob("*.ll"))
ok = skip = err = 0

for ll in ll_files:
    if (asm_dir / (ll.stem + ".s")).exists():
        skip += 1
        continue
    r = subprocess.run(
        ["python3", "compile_annotate.py", str(ll), "--out-dir", str(asm_dir)],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        ok += 1
    else:
        err += 1
        print(f"  [err] {ll.name}: {r.stderr.strip()[:200]}", flush=True)
    done = ok + skip
    if done % 500 == 0 and done > 0:
        print(f"  {done}/{len(ll_files)}  compiled={ok}  skipped={skip}  errors={err}", flush=True)

print(f"Done: compiled={ok}  skipped={skip}  errors={err}  total={len(ll_files)}")
PYEOF

TOTAL_ASM=$(find "$ASM_DIR" -maxdepth 1 -name '*.s' | wc -l)
echo "   Total .s files: $TOTAL_ASM"

# ── Step 4: gem5 window check ────────────────────────────────────────────────
echo ""
echo "── Step 4: gem5 window check (scheme=2, jobs=$JOBS) ──"
python3 /tests/run_helpers/pipeline_window.py "$ASM_DIR" \
    --jobs "$JOBS" \
    --out "$RESULTS" \
    2>&1 | tee "$OUT_BASE/gem5.log"

# ── Step 5: Extract hits ─────────────────────────────────────────────────────
echo ""
echo "── Step 5: Results ──"
python3 - <<PYEOF
import json
from pathlib import Path

results = json.loads(Path("$RESULTS").read_text())
hits   = [r["name"] for r in results if r.get("issued_in_window") is True]
errors = [r["name"] for r in results if r.get("status") != "ok"]

Path("$HITS").write_text("\n".join(hits) + "\n" if hits else "")

print(f"  Total tests run  : {len(results)}")
print(f"  Window hits      : {len(hits)}")
print(f"  No hit           : {len(results) - len(hits) - len(errors)}")
print(f"  Errors           : {len(errors)}")
print(f"  Hits written to  : $HITS")
PYEOF

echo ""
echo "========================================"
echo "  Pipeline complete."
echo "  Results : $RESULTS"
echo "  Hits    : $HITS"
echo "========================================"
