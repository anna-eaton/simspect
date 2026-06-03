# SimSpect — Recent Work Recap

*Compiled 2026-06-03 from `claudelog.md`, `claudenotes.md`, `results.md`, and the memory index.
A self-contained summary of the major things worked on lately: bugs found, what we learned,
design decisions, and the internal pipeline updates we had to make. Each item points to the
durable record so you can re-verify.*

---

## 1. The bugs we found (real vs. artifact)

Color key (from `bug/BUGS.md` / `BUG_TAXONOMY.md`): 🔴 real target/gem5 bug · 🟠 checker FP ·
🟡 pipeline/harness · 🔵 model (Alloy) · ⚪ config/timing artifact.

### Confirmed REAL bugs

- **🔴 STT VP↔squash race (load channel)** — *the headline real finding.* STT (and SPT) untaint a
  transmitter at the branch **visibility point** (`isPrevBrsResolved`/`isPrevInstsCompleted` =
  *executed*, not *committed*). On a mispredict the branch becomes `readyToCommit` at resolve, but
  the squash takes extra cycle(s) to propagate; in that gap the wrong-path tainted load untaints,
  re-issues, and touches cache **before the squash drains it**. Root-caused by `designconsultant`
  (`results/experiments/slow_comm_squash1/diagnostics/stt_vp_squash_race.md`, ex `inst-047231`).
  - **Driver = `commitToIEWDelay` (≥2–3), NOT `squashWidth`.** Does **not** leak at gem5 stock
    timing (commitToIEWDelay=1). The IQ/LSQ flush is one-shot/unbounded in gem5, so wrong-path depth
    can't widen the gap — only the commit→IEW redirect latency can. **No pure-stock PoC exists on
    this gem5**; minimal PoC = stock + commitToIEWDelay=3. Plausibly *more* realizable on real
    silicon (bounded squash bandwidth, multi-cycle redirect) — open question whether "multi-cycle
    commit→squash CPU" is in scope.
  - The same race is the only genuine **SPT** load signal (~3807 genuine after model-bug buckets
    removed) and is **slow-comm-only** there too (0/230 at stock se.py).
  - Filed: `bug/stt_slowcomm_vp_squash_race/`, diag `diag_stt_vp_squash_race.py` (aligned to
    check_ld's data-obtained gate).

- **🔴 recon STL/SLF taint bypass** — `inst-014912`: a store-to-load-forwarded tainted spec load
  marks ready-in-ROB (@2682500) before its squash (@2683500), returning data before the STT taint
  check, **without ever sending a cache packet**. The one real leak among 184 Recon_6 ld hits (the
  other 183 are check_ld FPs). Filed: `bug/recon_SLF_stlf_bypass/`.

- **🔴 STT implicit-channel defense is structurally broken** (`results.md`, the original writeup).
  Three sub-bugs in `cwfletcher/stt`:
  1. `hasImplicitFlow` is computed every cycle but **never feeds `isArgsTainted`** (rob_impl.hh
     `compute_taint`) → `--implicit_channel=1` has zero effect.
  2. Even if fixed, `implicit_flow` only fires when a prior *control* inst has `hasExplicitFlow` —
     but the mispredicted branch that opens the window usually has untainted operands.
  3. Pending-squash race (younger untainted + older tainted branch same cycle) — fixed only on
     `master` (Mosier 18e304f), absent from `updates`/Amulet artifact.
  → STT's only working mechanism is the **explicit** load `fenceDelay`; branch transmitters whose
  operands lack an explicit dataflow to a spec load are undefended.

- **🔴 SpecLFB UV6 (first-spec-load-unprotected)** — the one AMuLeT bug *in SimSpect's scope*.
  SpecLFB leaves the first speculative load unprotected (`isCUSL=1` but `isUnsafe=0`, AMuLeT Fig.8
  exemption). **68/300 access cache in-window.** Verdict went through three corrections and landed
  on **DEMONSTRATED**: the xmit is an indexed load `movq (%base,%index),%dst` whose `%index` comes
  from an earlier *speculative* load — a real tainted-address gadget. The runtime address is fixed
  `0x3580` only because the index *value* is 0 (zero-init buffer), NOT because the operand is
  constant. (See §"What we corrected" — the "const-addr FP" verdict was wrong.)

### Pipeline / codegen bugs we fixed

- **🟡 Duplicate-PC label codegen bug** (`parsexml.py`) — the branch-xmit rework injected a
  fall-through NOP at `br_pc+1` without renumbering; when the xmit branch was followed by another
  branch, both emitted the same `_pc<N>` label → assembler aborts → **~6% of br_x tests silently
  dropped**. AUDIT #14 had wrongly called this "dormant." **Fixed** (inject NOP only when the xmit
  branch is truly last). Requires regen from llvm onward for STT_6 / STT_6_interleave / SPT_6_oneLP
  to recover the dropped tests.

- **🟡 Pipeview disk-blowup / disk-full crashes** — `run_gem5` ran with no timeout and no tick cap;
  a livelocked/runaway run appended 65–127 GB to one pipeview file, and killed gem5 children
  reparented to PID 1 and kept writing to the *unlinked* file (so `rm` freed nothing). **Fix =
  timeout + tick cap + orphan-proofing**, harness-only. (`project_pipeview_space_blowup`.)

### Checker (false-positive) findings

- **🟠 check_ld over-counted** — it scored at the "Executing load" tick (request dispatch), so loads
  bounced into the STT delay_unit and squashed without obtaining data were flagged as leaks.
  **Fixed:** added the **data-obtained gate** (a load leaks only if `reached_cache` OR `store_forward`
  i.e. executed-no-packet but reached pipeview `complete`; squash never gates). This is now the
  canonical leak test, documented in `CLAUDE.md` "Leak criteria." Most recon "ld hits" were FPs.

- **🟠 check_br over-counts** — no taint/secrecy gate, and `branches_unresolved` is vacuously true
  for br_x (the xmit is the only mispredict). It flags any redirect in the window regardless of
  whether the branch is still a secret-dependent transmitter. Recommended fix: a taint-at-redirect
  gate (branch analog of data-obtained). STT branch "leaks" were check_br FPs (see below).

### Model (Alloy) bugs — owner-approved fixes

- **🔵 SPT_6_oneLP.als protset propagation (line 353)** — de-protection of a consumer whose rf-source
  left the protset only covered `inreg`; loads transmit via `inaddr` and have no inreg, so a
  speculative load-address transmitter of an already-non-speculatively-leaked value was never
  dropped. **Fix:** `i.inreg` → `(i.inreg + i.inaddr)`. Differential Alloy verified bug-shape
  SAT→UNSAT, normal gen + race shape preserved. **Same gap still in SPT_6_full / SPT_6 /
  oneLP_noSTLF** (not fixed; owner call). Regen needed to take effect.

- **🔵 SPT leakage_function += Stores.inaddr** — all stores can now be flagged as transmitters
  (feeds both speculative and non-speculative xmit). ~36% of generated tests now have a store xmit.

---

## 2. Things that turned out NOT to be bugs (artifacts / FPs)

- **STT branch ("br_x") "leaks" are NOT real** — went through several reversals; final verdict
  (controlled matrix): the 46 "leaks" are caused by the **fnc-commit-stall HOOK**, not STT
  (scheme STT == Unsafe byte-identical; fnc-stall=150→46/46 leak, fnc-stall=0→0/46). The hook pins
  `fnc` at the commit head → ROB can't drain → wrong-path re-speculation (gadget ret/RAS) re-redirects
  the xmit in the artificially-held window. ⚪ instrumentation artifact. **0 real STT branch leaks.**
  ⚠️ Open caveat: the load race uses the same fnc-stall=150 — should be re-checked at fnc0.

- **SPT branch leaks = 0** — 661/677 have a non-speculative (architectural) condition = model
  over-approximation; the 16 spec-load candidates are wrong-path **retq/loop re-speculation** (xmit
  branch never commits, re-fetched after the controlling mispredict already resolved). Diag
  `diag_branch_wrongpath_respec.py` buckets 597/677.

- **const-addr / untainted-address loads** — the dominant load FP class across recon/STT/SPT/SpecLFB:
  the model marks a load protected but its concretized address is an untainted constant (prologue
  zero-init), so the defense correctly lets it touch cache. Bucketed by `diag_constaddr_load`.

- **SPT "Fence leaks pre-squash"** — first mis-diagnosed as memory-untaint (shadowL1 — which is
  actually OFF), then as a zero-init realizability gap; **corrected** to the VP↔squash race (real
  mechanism) split from a harmless untainted-address over-approximation. Slow-comm-only.

- **`error` rows in sweeps** = incomplete sweep grid (a grid point's check output never written
  because the invocation hung), not a leak or gem5 bug.

- **rf-clobber / shared-opstate** — the single-Reg_s collapse makes blank operands collide onto the
  xmit's value (a sibling transmitter), a model/concretization artifact, not a leak.

---

## 3. What we learned (methodology / big-picture)

- **The canonical leak test** is the **data-obtained gate**, not cache-reach: in-window is necessary
  but not sufficient; a load leaks iff it obtained data (`reached_cache` OR `store_forward`/SLF
  complete). Squash timing **never** disqualifies. Every diagnostic re-deciding real-leak-vs-FP must
  reuse `check_ld._xmit_cache_fate` + pipeview `complete`.

- **Dataflow attribution must follow the executed/data-obtained dynamic instance**, not max-seqNum or
  "PC ever squashed." PC reuse across wrong/correct paths creates multiple dynamic instances per PC;
  matching the wrong one produced several false bug calls.

- **The VP↔squash race needs ONE mispredicted resolve racing its own squash propagation**, not two
  unresolved branches. The coincidence sweep (Run B) gets 0 hits because it holds the mispredict
  unresolved and uses stock commitToIEWDelay=1 — it never opens the race window.

- **AMuLeT vs SimSpect scope** — AMuLeT's bugs are mostly **collateral shared-µarch-resource** leaks
  (InvisiSpec L1D eviction, MSHR interference, I-cache, STT store→TLB) living in the Ruby controllers,
  invisible to O3PipeView+LSQUnit and needing cache-*occupancy* stimulus Alloy can't generate. **Only
  SpecLFB UV6 is in SimSpect's scope.** SimSpect's complementary niche = targeted transmitter-window
  timing races (the VP↔squash class). `docs/AMULET_VS_SIMSPECT_SCOPE.md`.

- **AMuLeT A/B efficiency comparison (measured):** (A) SimSpect first UV6 @ test #6 / 23% density vs
  AMuLeT @ #39 / 3.3% → **~6.5× fewer tests, ~7× denser targeting.** (B) Per-test *gem5* time is
  comparable (SimSpect hostSeconds 0.092 vs AMuLeT m5.simulate 0.057); the earlier "~40× slower" was
  entirely the O3PipeView measurement trace + fresh-boot-per-test (harness/instrumentation), not
  simulation. Complementary: SimSpect wins targeting, AMuLeT supplies the input-differential footprint.

- **STT taint stage** — taints at COMMIT (`rob->compute_taint`, unconditional each tick, not starved
  by the fnc-stall), not rename. Ruled out a "transmit-before-taint" window: fence is recomputed every
  IEW tick before loads issue, and taint is set eagerly on the static access bit at dispatch. ⚪
  inefficient but not a correctness hole. Only real hole stays the VP↔squash race.

- **The testsets are STALE** — STT_6 / STT_6_interleave XML was generated pre-effective-RS clause:
  40% no-op padding, 8.6× redundancy, only **2 leak dataflows** vs **45** from the current model.
  REGEN recommended for ~22× more leak-topology coverage. (`project_stale_stt_testsets`.)

- **OTB / getOldestTaint gadget** (ld→other→xm, two-chain merge) is **absent** from default
  enumeration but **legal** (SAT when forced with `otb_shape` predicate) — a `max_instances`
  cap/ordering artifact, NOT a model limit. Needs a forcing predicate + interleave. Never infer "the
  model can't" from "absent in the capped enumeration." `mdsToRead/OTB_GENERATION_GAP.md`.

---

## 4. Design decisions & internal pipeline updates

- **Producer/consumer split** — `testsetgen.py` (pipelined xml+llvm+asm, no gem5) + `testrun.py`
  (typed watcher, results split by xmit kind into `results/<name>__<ts>/<mode>/<kind>/`). Legacy
  `pipeline.py all` and `_sweep_watcher.py` left untouched. Lets every stage stream.

- **Sweep extension (gated, backward-compatible)** — `pipeline.py` `_grid_points`/`_inject_stalls`
  gained optional `sweep.unresolved_points` (sweep `s_U`) and `sweep.max_grid` (seeded sub-sample of
  the Cartesian blow-up). Absent keys = identical legacy behavior.

- **New se.py variants** — `se_slowcomm.py` (hardcoded iewToCommitDelay=30 / commitToIEWDelay=4 /
  comSize=40 / squashWidth=1) and `se_exp.py` (env-driven) on both /work/stt and /work/gem5-spt, for
  the slow-comm and fragility/stall sweeps. **commitToIEWDelay≥5 livelocks gem5** (generic, not the
  hook) → capped at 4.

- **Diagnostics convention** — each results folder carries `diagnostics/` with super-specific,
  one-cause-each `diag_*.py` + a bug `.md`, auto-discovered by `bucket_hits.py`. **Disqualifiers
  (XML artifacts → gem5 non-cache FPs) run before real-bug diagnoses**, so leftover = `NEW` =
  pure-bug candidates. Causes propagate only to their true scope (testset-specific vs build-specific),
  never blanket across a name family.

- **Bug catalog** — repo-root `bug/` with `BUGS.md` (by build), `BUG_TAXONOMY.md` (by root-cause
  layer: target/checker/alloy/pipeline), and verified example folders with provenance.

- **AMuLeT defenses instrumented** — SpecLFB, InvisiSpec, CleanupSpec, SPT-Fence builds wired through
  SimSpect (scheme glue, `--branch-ann-base` hex fix, per-build LSQ trace parsing, dedicated checkers
  `check_ld_speclfb.py` / `check_ld_invisispec.py`). InvisiSpec ld run = 0 leaks (defense holds);
  CleanupSpec out of scope (post-squash cache-state differential).

- **Repo housekeeping** — top-level `run_config_*.jsonc` moved to `runconfigs/` (per-results configs
  left in place); ad-hoc scripts archived.

- **Deliverable for the paper** — `PAPER_RESULTS.md` (findings by defense), `paper_figures/` (~21
  reproducible PNGs + TikZ source), 3 methods docs (`METHODS_LEAKAGE_KNOBS` / `_CONCRETIZATION` /
  `_INSTRUMENTATION`).

---

## 5. Corrections worth remembering (where an earlier verdict was wrong)

- **SpecLFB UV6**: "const-addr FP / 0 demonstrable leak" → **WRONG**. The xmit address is tainted
  (indexed load fed by a spec load); the 68 ARE valid UV6 hits. ⚠️ `PAPER_RESULTS.md` baked the wrong
  verdict and was then updated. Lesson: check the gadget asm (addr = base+index) before calling a load
  hit const-addr; a zero-*valued* tainted index looks constant at runtime but the operand is tainted.

- **STT br_x**: cycled through "check_br window-gap FP" → "real VP-squash race at stock" → **final:
  fnc-stall hook artifact**. Reasoning was wrong twice; the controlled scheme×fnc×se matrix settled it.

- **SPT "Fence leaks pre-squash"**: "memory untaint / zero-init realizability gap" → **WRONG**
  (shadowL1 is OFF). Correct = VP↔squash race.

- **SPT no_hold**: "harmless over-approximation / realizability gap" → **superseded** by fixable model
  bugs (the inaddr/protset and store-leakage fixes).

---

## 6. Still open / TODO

- REGEN STT_6 / STT_6_interleave / SPT_6_oneLP from the fixed models (owner call) + re-bucket.
- Propagate the 2 SPT model fixes to SPT_6_full / SPT_6 / oneLP_noSTLF.
- Re-check the STT **load** race at fnc0 + STT-vs-Unsafe diff (it currently runs with fnc-stall=150,
  same variable that turned out to manufacture the branch "leaks").
- `check_br` window/taint-at-redirect fix (checker fix, not a diagnostic).
- A secret-addressed, cache-missing load gadget testset to turn the SpecLFB UV6 *signal* into a
  concrete secret-recovery PoC.
</content>
</invoke>
