# Claude Findings Log (big-picture, durable)

This is the **high-signal, append-only log** of things Claude sessions figured out that
future sessions (and the user) need to know. It is the counterpart to `claudenotes.md`:

- `claudenotes.md` = *ephemeral* "what I'm doing right now" scratchpad. Cleared/overwritten freely.
- `claudelog.md` (this file) = *durable* "what we learned / changed and why". **Append, don't delete.**

## What belongs here (write it as you discover it)

- **Bugs** found (concretization, parsexml/Stage-2 codegen, gem5 hooks, model expressivity) — with verdict (real gem5 bug vs. pipeline artifact) once known.
- **Changes** that affect other sessions or future runs (fixes to `parsexml.py`, hooks, configs, scripts).
- **Big-picture fixes / decisions** about pipeline structure or methodology.
- **Reasons a sweep had to be restarted / relaunched** (e.g. mid-run contamination, stale `.ll`, `--force` needed) and *which models/stages* are affected.
- **Cross-stage gotchas** newly discovered (candidates for promotion into `DESIGN.md` / `AUDIT.md`).

## What does NOT belong here

- Minute-by-minute "I'm running X now" status → `claudenotes.md`.
- Findings already captured in `DESIGN.md`, `AUDIT.md`, `results.md`, `reconresults.md`, or git history. Cross-reference instead of duplicating.

## Format

Newest at top. Every entry **dated** and signed with the session label you use in `claudenotes.md`:

```
## YYYY-MM-DD HH:MM — <session-label> — <one-line title>
<a few lines: what it is, evidence/where, verdict, and what action it implies (relaunch? report to user? promote to AUDIT?)>
```

Keep entries self-contained — point to the file/log/line that proves it so the next session can re-verify.

---

## 2026-06-02 04:30 — designconsultant — gem5 O3 livelocks at commitToIEWDelay ≥ 5 (generic, NOT STT / NOT a hook)
Setting up the "slow-comm" experiment (stretch IEW↔commit comms + squashWidth=1 on /work/stt to
widen the observable speculative window). **First config (iewToCommitDelay=commitToIEWDelay=15,
back/forwardComSize=25, squashWidth=1) does NOT terminate** — gem5 livelocks in commit (ROB stuck
"Trying to commit"; a single test ran to tick 3.05e9 vs ~3.0e6 baseline and produced a 2.5 GB
pipeview before I killed it). Bisected on testsets/STT_6/.../inst-047231 with `--abs-max-tick=5e7`:

- **`commitToIEWDelay` (backward wire, commit→IEW) is the culprit.** Livelocks at **≥5**; **≤4 is OK**.
- `iewToCommitDelay` (forward wire) is fine up to at least **30**. `squashWidth=1` alone is fine.
- Livelock reproduces with **scheme=0 (Unsafe, STT off)** AND with **fnc-commit-stall=0** → it is a
  **base-model timing-config limit of this gem5 O3 fork** (backward redirect round-trip doesn't
  converge), NOT the STT defense and NOT one of our SimSpect hooks.

**Verdict:** out of scope (not a hook, not a speculative leak, scheme-independent). Do **not** chase
as a research signal and do **not** "fix" gem5. Just respect the ceiling. Max terminating stretch
verified (all exit ~3.1e6): `iewToCommitDelay=30, commitToIEWDelay=4, backComSize=forwardComSize=40,
squashWidth=1` (also fwd15/bwd4/sq1). Stretching forward delay + squashWidth=1 barely changes total
runtime, so runs stay ~1–2 s.

**State / action:** Experiment LAUNCHED — 2 NEW `_sweep_watcher.py` (STT_6 pid 3945425,
STT_6_interleave pid 3945426) sweeping into results/experiments/slow_comm_squash1/ with the safe
config. Smoke (4 tests) terminated in ~1 s, all status=ok; inst-047231 flipped NO→hit vs baseline se.py.
Files: `/work/stt/configs/example/se_exp.py` (env-driven O3 overrides: SIMSPECT_{IEW_COMMIT,COMMIT_IEW}_DELAY,
SIMSPECT_{BACK,FWD}_COM_SIZE, SIMSPECT_SQUASH_WIDTH — additive, does NOT touch the in-use se.py);
`/work/stt/configs/example/se_slowcomm.py` (hardcoded — **still has the BROKEN 15/15/25/25/1**, must be
reset to the safe config before any run); `results/experiments/slow_comm_squash1/{STT_6,STT_6_interleave}/run_config.jsonc`
(point config_script at se_slowcomm.py, same binary — CPU delays are runtime params, no rebuild).
New experiment uses NEW watchers + NEW se variant only; existing watchers (all reference se.py) untouched.
Baselines to diff against: `results/STT_6_sttbuild`, `results/STT_6_interleave_sttbuild`.

## 2026-06-02 02:40 — analysis-claude (inspectBrHitsGem5) — SPT const-addr ld "hits" = Alloy over-approximation (NOT real); conservative diagnostic added
The live SPT_6_oneLP_fence run (new checkers) has 0 br_x hits (check_br fix holds) but ~2800 ld hits.
Classified: **~99.9% are NOT real leaks.** Root cause (model-vs-gem5): `leakage_function=Loads.inaddr`
enumerates every load address as a candidate xmit, and Alloy's protection set counts ANY
*speculatively-produced* value as protected — so a load whose address is computed by a speculative ALU
op (`TOther`) reading only **constants** gets flagged. SPT correctly untaints it (taint flows only from
speculative LOADS), so it issues with a public address → gem5 "hit" but no leak. The 06-01 20:17
`.als` edit (`hardware_protection_policy - ((Inreg+Inaddr)-outreg.rf)`) only excluded Inaddr with NO rf
edge at all; these have a producer (the const-op), so they slipped through — that's why const-addr
"hits" persist despite the edit. Confirmed testset used the edited model (provenance .als matches).
**Diagnostic added** (per CLAUDE.md diagnostics/ convention, first one built):
`results/SPT_6_oneLP_fence__20260602_013615/diagnostics/diag_constaddr_load.py` (+README). Conservative
signature: ld xmit whose transitive address chain (excluding the xmit itself — handles
`movq (%rsi,%rax),%rax` dest/addr aliasing) has **no uncommitted load** → known const-addr artifact.
On this run: **2795 known (masked) / 3 unknown** (`inst-001746/004097/004532` = load→load, address from a
speculative load → potential real leaks, left for review). Cross-checked vs the gem5-side taint
analyzer: masked set is 100% const-addr, no tainted-addr load hidden.
**Proper model fix (pending owner approval, NOT done):** derive the protection set as a forward closure
from real secret SOURCES (speculative load/memory outputs) via data-dependency edges, with monotone
(union) taint — then constant/missing-operand ops are untainted automatically and can never untaint a
tainted input. Don't enumerate missing operands; don't use AND-semantics. The dup-PC Stage-2 bug and
the check_br fix (entries below) are separate.

## 2026-06-02 01:58 — runmanagernew — added recon-modded gem5 watchers for the STT testsets (now both STT builds in parallel)
Per user, also point the STT testsets at `/work/gem5-recon-modded` (the STT/Recon build; scheme 2 = STT,
`branch_ann_enable`, X86O3CPU, fnc-stall 150) using the existing `run_config_STT_6.jsonc` /
`run_config_STT_6_interleave.jsonc` (already wired to recon-modded). Smoke-passed (branch-ann + fnc-stall path
OK, type-sorted). Launched 2 more `testrun.py` watchers:
- STT_6 → `results/STT_6__<ts>/` (pid 4165134); STT_6_interleave → `results/STT_6_interleave__<ts>/` (4165135).
Now 5 gem5 watchers total: STT_6 + STT_6_interleave on BOTH `/work/stt` (`*_sttbuild__<ts>`) and
recon-modded (`STT_6__<ts>` / `STT_6_interleave__<ts>`), plus SPT_6_oneLP fence (`/work/gem5-spt`). Each
campaign `manifest.json` records `gem5_binary` to disambiguate the bare-named recon-modded dirs. Load ~55.

## 2026-06-02 01:45 — runmanagernew — killed the leftover SPT monolith (`pipeline.py all`) that was self-sweeping gem5
The legacy `pipeline.py all --model SPT_6_oneLP` (pid 3474228, launched 20:11 for xml) was never killed after
xml. `all` couples xml→llvm→asm→**gem5 self-sweep**, so once it finished xml(100k)+llvm it entered
`phase_asm_gem5_streaming` and was running a **second, redundant Fence gem5 sweep** (non-type-sorted, into
`results/SPT_6_oneLP/`) in parallel with the new fence `testrun` watcher — double gem5 load on the same testset.
Killed it + subtree. Also killed the SPT stage-2 `--follow` follower (1801844): SPT asm is done
(not_taken 96,943 / taken 95,991 of 100k; the ~3–4k gap = dup-PC dropped stems, `.ll`-without-`.s`), and
`--follow` never self-terminates so it was busy-spinning re-failing the buggy `.ll`. **SPT now = follower-free
producer-complete + only the fence `testrun` watcher doing gem5.** Leftover redundant self-sweep
(`results/SPT_6_oneLP/`, ~6k partial recs, non-type-sorted) left in place pending user call (discard/keep).
Lesson: `pipeline.py all` is the monolith — for the split workflow use `testsetgen.py` (gen) + `testrun.py`
(gem5); don't leave an `all` running or it self-sweeps.

## 2026-06-02 01:36 — runmanagernew — restarted all gem5 watchers on the new (branch-fix) checkers, results now type-sorted
Per user: the checker scripts were updated 06-02 ~00:57–01:03 (`check_br.py`/`check_ld.py`/`check_other.py`/
`gem5_common.py` — esp. analysis-claude's check_br false-positive fix in the 00:30 entry below). Killed the 3
live `_sweep_watcher.py` watchers (STT_6_sttbuild 3473035, STT_6_interleave_sttbuild 3473036, SPT_6_oneLP_fence
3474229) + their gem5 subtrees only (other sessions' gem5 left alone). **Archived their pre-fix cumulative
results → `results/prebranchfixResults/`** (STT_6 34k, interleave 33k, SPT fence ~20k, invispec; old
non-type-sorted `_sweep_watcher` output). Relaunched the 3 via **`testrun.py`** (new checkers picked up
automatically; results split **by transmitter kind** into `results/<name>__<ts>/<mode>/<kind>/`). Smoke
confirmed new check_br is stricter (same gadget: old `br_x 1/1` → new `0/1`). invispec NOT relaunched
(fence-only, per 20:17 decision). Generators (SPT follower 1801844, legacy all 3474228, STT_6_interleave gen
3473033) untouched. **STT_6 gen finished**: 93,901/100,000 asm per mode, 6,099 (~6%) dropped by the dup-PC bug
(recoverable subset = `.ll` w/o `.s`).

## 2026-06-02 00:30 — analysis-claude (inspectBrHitsGem5) — CORRECTION + FIX: STT br_x hits are check_br false positives (NOT a gem5 leak); STT branch defense works
**Supersedes my 2026-06-01 23:22 entry below** ("STT branch leaks are REAL gem5 bugs"). That verdict was
WRONG — it came from running the gadget under gem5 with the **base ann (no resolve-stall)**, so the
speculative load never executed and the branch looked untainted (`stalledBranchMispredicts=0`).
The resolve-stall that opens the window is injected by the sweep (`pipeline.py:_inject_stalls`:
mispredict→5000, correctly_not_taken→grid[0,500,2500], xmit→0), not baked into the base ann.
**With the stall applied (real-sweep condition):** the load executes, taints `%rax`, and STT DOES
defend — the xmit branch is `made pending` (`stalledBranchMispredicts=2`; Commit log:
`(Lazy) A branch mispredicInst PC (0x401070=>...) is made pending`). Its redirect is delayed to
≈window-close. So there is **no in-window leak**; STT’s branch implicit-channel works.
**Root bug = `check_br`**: it keyed the verdict on the branch’s *resolve/complete* tick
(`xmit_complete`, in-window in both STT and unsafe) instead of the *squash/redirect* tick. STT delays
the redirect, not the resolve → false positive (exactly the complete-tick-vs-squash-tick gap flagged
in my 23:30 entry — now confirmed as the actual cause).
**FIX (applied, STAGE3_gem5/):** `gem5_common.py` now always traces `Commit`, adds
`parse_commit_squashes()` (pc→squash-broadcast ticks), and threads `squash_by_pc` into `check_fn`;
`check_br.py` keys `xmit_signal` on the xmit’s squash tick (no in-window squash ⇒ no hit), with a
fallback to the old complete-tick behaviour when no Commit trace exists; `check_ld.py`/`check_other.py`
accept+ignore the new arg.
**Validation (faithful sweep grid):** STT scheme=2 — all 5 reproduced br_x OLD-hits flip to NEW no-hit,
0/15 NEW hits. UNSAFE scheme=0 — inst-000009/000017/000027/000041 still NEW-HIT (real leaks caught);
inst-000002 (xmit never broadcasts a squash) correctly no-hit in both (was an OLD false positive).
**Impact:** br_x hit counts in STT_6_sttbuild / interleave are inflated by these false positives;
re-run with the fixed checker to get true numbers (likely ~0 under STT). **Checker bug — does NOT
change testset relaunch scope** (unlike the dup-PC Stage-2 bug). Full writeup: `STT_BRANCH_LEAK_ROOTCAUSE.md`
(rewritten with the corrected conclusion + "superseded claims").

## 2026-06-01 23:40 — opus-claude — Deep audit: PC numbering is correct across all existing testsets (read-only, no bug)
Audited PC-numbering integrity over ~96k tests across 11 testsets (STT_3/5, SPT_6, SPT_6_full, _otb_search_c1/c2,
_otb_alloy_probe, _verify_ld_taken, STL_bug, OTB, SMOKE) — both branch_modes, interleave `_vN` variants, all xmit
kinds (ld/br_x/other_x). Invariants checked per test by cross-referencing each `.ann.json` against the actual
`__litmus_<stem>_pcN:` labels in its `.s`: (1) no duplicate PC labels, (2) labels contiguous 0..max, (3) xmit.pc,
(4) every branch_pc, (5) btb_forced_target_pc (∈ labels or == end_block), (6) commit_boundary pcs all land on real
labels, (7) resolved addr/offset strictly monotonic with PC. **All clean.** Verdict: pass1 contiguous numbering, the
interleave renumber+target-remap (`parsexml.py:1056-1085`), and the post-fix NOP-last append are all self-consistent;
`compile_annotate.py` resolves PCs from `nm` ground truth.
Two non-PC notes: (a) two annotation schemas coexist — old relative `x86_*_offset` (STT_3/5, _otb_*, _verify_ld_taken,
STL_bug, OTB, SMOKE) vs new absolute `addr`/`func_base_addr` (SPT_6, SPT_6_full); both fully resolved (flag only if a
consumer assumes one schema). (b) `STL_bug/inst-000637-no-store` has a real PC gap (pc=3 removed) + stale
btb_forced_target_pc=3, but it's a hand-crafted debug variant (no source XML), not generator output. Could not audit
the post-22:50-fix regen output (SPT_6_oneLP/STT_6/STT_6_interleave have 0 resolved anns yet); the one inst-000001 I
regenerated by hand was clean.

## 2026-06-01 23:30 — analysis-claude (inspectBrHitsGem5) — check_br scope: sound for resolution-blocking defenses, NOT redirect-delaying ones
Methodology note for interpreting `br_x` hits. `check_br.py` flags a hit on: xmit branch *resolves/completes*
in `(lc_retire, fnc_retire)` AND fall-through never retired (squashed) AND other branches unresolved. That is
a correct detector of "secret-dependent branch resolved speculatively" — and it's keyed on the branch's
**complete tick**, NOT the squash/redirect-propagation tick.
- ✅ Correct for defenses that PREVENT speculative resolution / fence inputs (STT load-fence, DoM). Borne out:
  tainted-addr loads 0% hit.
- ⚠️ Would FALSE-POSITIVE for a defense that lets the branch resolve but DELAYS the squash broadcast (STT's
  intended branch implicit-channel): branch still completes in-window + wrong-path fall-through still never
  retires → still flagged, even if the redirect was pushed out of the window. To be airtight there, check the
  actual squash tick (when fall-through micro-ops are killed), not `xmit_complete`.
- Does NOT change the current STT verdict (branch delay is fully non-functional, redirect genuinely in-window),
  and the verdict doesn't rely on check_br anyway (`stalledBranchMispredicts=0` is gem5's own counter).
- Secret-dependence is CONFIRMED structurally (unbroken `load→mov→testq→jCC` chain) and by STT's own tagging
  (`rob_impl.hh:812-814` taints every speculative load dest). Not yet confirmed by a dynamic two-value
  differential (litmus loads 0 from zeroed mem) — dependency not in doubt, but that test would close all doubt.
  Detail in `STT_BRANCH_LEAK_ROOTCAUSE.md` §4a/§4b. CLAUDE.md:130's "known gap" note is partly stale (window IS
  enforced now; real residual gap = complete-tick vs squash-tick).

## 2026-06-01 23:22 — analysis-claude (inspectBrHitsGem5) — STT branch leaks are REAL gem5 bugs (taint never reaches branches through FLAGS)
Verdict for STT_6 `br_x` hits (verified by running `/work/stt/build/X86/gem5.opt` on individual gadgets,
NOT trusting AUDIT): **real gem5 leaks**, not pipeline/model artifacts.
- All STT hits are `BR_tainted` (branch condition data-dependent on a speculative load); all `ld` xmits
  are tainted-addr and 0% hit (load fence works). Loads protected, branches not.
- STT's branch implicit-channel defense IS on (`se.py:334 implicitChannel=scheme==2`) and exists
  (`commit_impl.hh:934-954` delays a mispredicted branch's squash while `instCausingSquash->isArgsTainted()`).
  It never fires: `stalledBranchMispredicts=0`, zero "made pending" in trace → the tainted branch redirects
  inside the window → leak.
- Cause: `isArgsTainted` is set only from `hasExplicitFlow` (`rob_impl.hh:809`). That explicit-flow taint
  propagates through INTEGER regs (so tainted load *addresses* fence via the SAME flag, `lsq_unit_impl.hh:1013`)
  but does NOT reach conditional branches — the chain `load→mov→testq→jCC` runs through the x86 condition-code
  /FLAGS register and the taint isn't carried across that hop.
- **Action: report-only.** gem5 STT taint-tracking bug → fix domain is gem5, **does NOT change relaunch scope**
  (unlike the dup-PC codegen bug below). Left unpatched per "don't touch gem5 except hooks". Full writeup:
  `STT_BRANCH_LEAK_ROOTCAUSE.md`. Open (needs instrumented build): exact failing link = CC-register
  `argProducer` match (`rob_impl.hh:228-236`) vs multi-hop ordering in `compute_taint`.

## 2026-06-01 23:18 — runmanagernew — in-flight generation predates opus-claude's 22:50 parsexml fix → contaminated
The running generators all started BEFORE the 22:50 parsexml fix below, so their testsets are a MIX
of old-(buggy)-logic and new-logic `.ll`/`.s` (the exact mid-run contamination `DESIGN.md` warns of):
- SPT_6_oneLP stage-2 follower (`testsetgen.py --follow`, pid 1801844) + the legacy `pipeline.py all`
  (pid 3474228) still enumerating xml.
- STT_6 + STT_6_interleave test-gen (pids 3473032/3473033) in asm.
**Action:** matches opus-claude's relaunch note — after the fix, wipe/`--force` the **llvm** phase for
SPT_6_oneLP / STT_6 / STT_6_interleave and regen llvm→asm onward. Pending user sign-off (do NOT have
the running gens silently produce a half-fixed testset). The 4 gem5 watchers consuming these will need
their cumulative results discarded for the affected br_x stems too.

## 2026-06-01 23:00 — runmanagernew — added streaming producer/consumer framework (testsetgen.py / testrun.py)
New `testsetgen.py` (producer: xml+llvm+asm pipelined via a bg xml thread; `--follow` attaches to an
externally-running xml producer) and `testrun.py` (consumer: a *copy* of `_sweep_watcher.py` that
splits gem5 results **by transmitter kind** into `results/<name>__<ts>/<mode>/<kind>/` + timestamped
campaign + `latest` symlink + manifest). Makefile gains `gen`/`run`/`pipeline`. **`pipeline.py` and
`_sweep_watcher.py` are unchanged** (in-flight legacy runs depend on them). Both smoke-tested e2e.
Ad-hoc launch scripts (incl. `run_sweep.sh`) moved to `archive/`. See CLAUDE.md "Pipelined run".

## 2026-06-01 20:17 — runmanagernew — relaunched SPT_6_oneLP fresh from edited .als; old results archived
Per user, edited `SPT_6_oneLP.als:337` (the `hardware_protection_policy` seed) to also untaint
`Inaddr` operands with no incoming `rf` edge — fixes the model/gem5 mismatch where constant-address
loads were tagged as transmitters but gem5/SPT correctly untaints them (was ~99% spurious ld "leaks").
**Restart reason = model fix:** wiped `testsets/SPT_6_oneLP` and relaunched from Alloy. Old results
(95,941 recs/run, fence+invispec) preserved in `results/_archive_SPT_6_oneLP_20260601_201714/`.
Stopped the SPT invispec watcher (load relief); keeping only `SpectreSafeFence` — the delay/fence
substrate is the closer match to SPT-the-paper's described protection (the SPT-ness is the
`applyDDIFT`+`fwd/bwdUntaint`+`configImpFlow=Lazy` flags, not the scheme name).

## 2026-06-01 22:50 — opus-claude — FIXED parsexml duplicate-PC label bug (~6% br_x tests dropped)
Root cause: the xm-branch NOP-injection queue in `parsexml.py` (~:737) injected a NOP both when the
xm branch was last *and* when the next instruction was a branch, duplicating a PC label → compile
failure, so ~6% of STT_6 `br_x` tests were silently dropped. Fix: inject only when the xm branch is the
last instruction. Verified `inst-000001` (previously dropped) now compiles; labels unique. AUDIT #14's
"dormant" claim was wrong — this was firing live in `pipeline_STT_6.log`.
**Relaunch needed:** already-generated `.ll` keep the old logic; wipe/`--force` the **llvm** phase for
**SPT_6_oneLP, STT_6, STT_6_interleave** and regen llvm→asm onward to recover the dropped br_x tests.
Full handoff writeup in `claudenotes.md` ("VERIFIED BUG" section).
