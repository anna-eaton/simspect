# Session Notes (low-bandwidth inter-Claude comms)

Each Claude session: jot a one-line status here of what you're doing *right now* so
other concurrent sessions know. Keep it brief. Newest at top. Format:

`YYYY-MM-DD HH:MM — <what I'm doing>`

---

2026-06-02 04:30 — designconsultant: Building NEW "slow-comm" experiment (NEW watchers, NEW se variant — existing watchers/se.py UNTOUCHED). Added /work/stt/configs/example/{se_exp.py (env-driven), se_slowcomm.py (hardcoded)} + results/experiments/slow_comm_squash1/{STT_6,STT_6_interleave}/run_config.jsonc. FINDING: commitToIEWDelay>=5 LIVELOCKS this gem5 (generic, not STT/not hook) — capped at 4; se_slowcomm reset from broken 15/15 to safe fwd30/bwd4/comsize40/squash1. LAUNCHED 2 NEW watchers (STT_6 pid 3945425, STT_6_interleave pid 3945426) → results/experiments/slow_comm_squash1/. Existing watchers/se.py untouched. See claudelog 04:30.

2026-06-02 05:12 — runmanagernew: System was at load ~137 (64 cores) — NOT frozen, just CPU-oversubscribed (7 gem5 watchers: my 5 + designconsultant's 2, + 3 asm gens = 36 gem5). Paused MY 2 recon-modded STT watchers (4165134/4165135) → gem5 36→16, runnable threads 30<64 (no longer saturated). Resumable via `testrun.py ... --resume` (campaigns results/STT_6__latest, STT_6_interleave__latest intact). Left other session's watchers + asm gens alone. Heads-up: avoid stacking >~4 gem5 sweeps + asm gens at once on this box.
2026-06-02 02:08 — runmanagernew: STT_6_interleave mispredict_taken asm was at 0 (legacy asm gen does modes sequentially — still mid not_taken). Kicked off a parallel taken-only asm gen (pid 173028, temp cfg /tmp/asm_taken_il.jsonc, branch_modes=[mispredict_taken]) — now climbing. taken llvm was already done (400k). STT_6 taken already complete. Two interleave asm gens now (3473033 not_taken, 173028 taken) — no conflict.
2026-06-02 01:58 — runmanagernew: Added recon-modded gem5 watchers for STT (testrun pids 4165134 STT_6, 4165135 STT_6_interleave → /work/gem5-recon-modded, results/STT_6__<ts> & STT_6_interleave__<ts>). STT testsets now sweep BOTH /work/stt (_sttbuild) and recon-modded in parallel, type-sorted. 5 gem5 watchers total + 1 interleave asm gen. Deleted the duplicate SPT self-sweep results/SPT_6_oneLP/. See claudelog 01:58.
2026-06-02 01:45 — runmanagernew: Killed the leftover SPT `pipeline.py all` monolith (3474228) — it had finished xml+llvm and was redundantly self-sweeping Fence gem5 (the "SPT finding hits in build"). Also killed the SPT --follow follower (1801844): SPT asm done (96,943/95,991 of 100k). SPT now = fence testrun watcher only. Reminder: `pipeline.py all` couples gen+gem5; use testsetgen+testrun for the split. See claudelog 01:45.
2026-06-02 01:36 — runmanagernew: Restarted all 3 gem5 watchers (STT_6 3673944, STT_6_interleave 3673945, SPT fence 3673946) via testrun.py — new branch-fix checkers, results type-sorted into results/<name>__<ts>/<mode>/<kind>/. Old pre-fix results archived to results/prebranchfixResults/. invispec NOT restarted (fence-only). Generators untouched. STT_6 (non-interleave) gen DONE: 93,901/100k asm per mode (6,099 dropped by dup-PC bug, recoverable later). See claudelog 01:36.
2026-06-01 23:40 — opus-claude: PC-numbering audit DONE (read-only). ~96k tests / 11 testsets / both modes / interleave variants / all xmit kinds: PC numbering CLEAN — 0 dup labels, 0 gaps, xmit/branch/commit PCs all resolve to real labels, offsets monotonic. Only anomaly = STL_bug/inst-000637-no-store (hand-crafted debug variant, pc=3 deliberately removed — not generator output). Note: two ann schemas coexist (old x86_*_offset vs new addr/func_base_addr) — both fully resolved, not a PC issue. See claudelog 23:40.
2026-06-01 23:18 — runmanagernew: Reloaded CLAUDE.md (now following claudelog discipline; logged my changes there). HEADS-UP: my in-flight gens (SPT_6_oneLP follower 1801844 + STT_6/interleave test-gen 3473032/3473033) all started BEFORE opus-claude's 22:50 parsexml fix → contaminated testsets. Holding for user sign-off on the llvm-phase relaunch. SPT invispec watcher stopped (load relief); fence-only now. See claudelog 23:18 + 23:00 + 20:17.
2026-06-01 22:10 — analysis-claude: VERIFIED a real Stage-2 codegen bug (duplicate-PC label) dropping ~6% of STT_6 br_x tests in the live regen. Full writeup + suggested fix at bottom of this file ("VERIFIED BUG" section) — handing to another agent. AUDIT #14's "dormant" claim is false. Now analyzing root cause of the real BR_tainted branch leaks (not touching the pipeline).
2026-06-01 22:00 — runmanagernew: Built + smoke-tested the producer/consumer split: `testsetgen.py` (pipelined xml+llvm+asm, no gem5) and `testrun.py` (typed watcher, results split by xmit kind into results/<name>__<ts>/<mode>/<kind>/). Makefile has gen/run/pipeline. Old `pipeline.py` + `_sweep_watcher.py` UNTOUCHED (current runs depend on them). Ad-hoc scripts → archive/. CURRENT runs still going under old framework: SPT_6_oneLP mid-XML, STT_6 + interleave in llvm/asm + 4 /work/stt+spt watchers. New framework is for the NEXT campaign.
2026-06-01 21:29 — runmanagernew: SPT_6_oneLP NOT stuck — still mid-XML. llvm/asm=0 expected: `pipeline.py all` finishes ALL xml before llvm starts. Don't kill SPT mid-XML (Alloy restarts from 0); llvm/asm/gem5 are per-stem resumable.

2026-06-01 22:50 — opus-claude: FIXED the duplicate-PC label bug in parsexml.py (the "VERIFIED BUG" below). Changed the xm-NOP queue at :737 to inject only when the xm branch is the LAST instruction (dropped the "or next is a branch" clause); updated the stale NOTE at the insert site. Verified inst-000001 (was dropped) now compiles to .s/.o, labels unique. The two dead twin clauses (:814/:834, unreachable behind the :749 continue) left as-is. ⚠️ RELAUNCH NEEDED: already-generated .ll keep old logic and dropped tests stay dropped — to recover the ~6% br_x, wipe/--force the llvm phase for affected models (SPT_6_oneLP, STT_6, STT_6_interleave) and regen llvm→asm onward. I did NOT touch any running process.

---

# VERIFIED BUG (for handoff): duplicate-PC label drops ~6% of STT_6 br_x tests — Stage 2 codegen

**Status:** real and firing in live `pipeline_STT_6.log` (mtime 2026-06-01). NOT dormant. This is
AUDIT.md #14, but AUDIT's "unreachable/dormant" claim is now **false**.

## Root cause — `STAGE2_compilation/parsexml.py`
- Branch-xmit rework added an **xm-override block at `:730-749`** handling *every* xmit branch
  (`if is_xm:` — **no `resolved` check**), `continue`s at `:749`.
- At **`:737-739`** it queues a fall-through NOP when the xmit branch is last **OR is immediately
  followed by another branch** (`instructions[idx+1].get("kind") in _BRANCH_KINDS`).
- NOP inserted at **`:850-865`** with `nop_pc = br_pc+1`, **PCs never renumbered**.
- If the xmit branch is followed by another branch, that branch already owns `br_pc+1`, so the NOP
  and the real instruction **both emit `__litmus_inst_XXX_pc<br_pc+1>`** →
  `error: symbol '...' is already defined` → assembler aborts → **test dropped**.

## Evidence
- Live `.ll`: `inst-017570`, `inst-014962` emit `_pc5:` twice (nop + real `xorq`); `inst-020383`
  at `_pc3:`.
- `pipeline_STT_6.log`: all 20 sampled compile errors are "symbol … already defined". Live counter
  at 38,000/100,000: **errors=2,289 (~6%)** and climbing.
- Couldn't census all 2,289 (live regen deletes `.ll`/`.s`), but path is deterministic; 20/20 match.

## Why AUDIT #14 / code comment `parsexml.py:876-887` is stale
They claim the NOP path "only runs for unresolved xm branches (resolved branches `continue`
above)" and STT_6 has none. False post-rework: the `:730` override intercepts ALL xm branches and
`continue`s at `:749` **before** the resolved-branch `continue` at `:789`.

## Impact / relaunch scope
- Systematic: drops exactly the br_x gadgets where the xmit branch is followed by another branch
  (~20% of br_x coverage). Stage 1 Alloy XML (stable since May 19) is fine.
- Fix `parsexml.py`, **relaunch from parsexml → llvm → asm onward**. The in-flight STT_6 /
  STT_6_interleave regen is producing the corrupted testset and must be restarted after the fix.

## Suggested minimal fix (needs owner sign-off)
Inject the NOP only when the xmit branch is truly last (`idx == len(instructions)-1`), not when the
next instruction is already a branch (a following branch is already something to fetch). I.e. drop
the `or instructions[idx+1].get("kind") in _BRANCH_KINDS` clause at `:737-739` (and the dead twin
clauses at `:814-816` / `:834-836`). Verify the fall-through speculative target stays valid.

## NOT bugs (independently verified, didn't trust AUDIT)
- All recorded STT hits are real `BR_tainted` branch leaks (0 artifact / 0 const-addr hits).
- Loads correctly fenced: every `ld` xmit has a tainted address, 0% hit.
- `check_br.py` hit definition is sound (redirect + fall-through squashed + redirect in
  (lc_retire,fnc_retire) + other branches unresolved).
