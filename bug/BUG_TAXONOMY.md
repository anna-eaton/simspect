# SimSpect bug taxonomy — by root-cause LAYER (the drill-down)

Companion to [`BUGS.md`](BUGS.md). `BUGS.md` indexes findings **by gem5 build**; this file indexes the
**same findings by the layer the bug actually lives in** — which is the question that matters when you
look at a hit and ask *"is this a real target bug, or is it my model / my checker / my codegen lying to
me?"* Every row points back to the proof (a `claudelog.md` entry, a `mdsToRead/` doc, a results
`diagnostics/`, or a `bug/<id>/` example) so this stays a thin, navigable index.

## The frame (why a "hit" is not automatically a bug)

SimSpect produces a **hit** when **gem5 lets through a test the Alloy model says is disallowed** (the
model is conservative, so gem5-permits-what-model-forbids is the only interesting direction — CLAUDE.md).
A hit can be any of **five** things, and they live in four different layers of the system:

| layer | what a hit there really means | is it the research signal? |
|---|---|---|
| **TARGET** (gem5 defense) | the defense genuinely exposed a speculative transmitter | ✅ **YES — the signal** |
| **CHECKER** (Stage 3 `check_*`) | the checker mis-scored a non-leak as a leak (or vice-versa) | ❌ measurement bug |
| **ALLOY** (Stage 1 model) | the model over-flagged a value as secret, OR concretization wired a program the model never reasoned about | ❌ false alarm / unrealizable test |
| **PIPELINE** (Stage 2 codegen / harness / config) | a codegen/config defect dropped, corrupted, or mis-ran the test | ❌ artifact |

**Triage order is mandatory and cheap→expensive** (mirrors `bucket_hits.py`): rule out ALLOY artifacts
(pure XML) → CHECKER artifacts (needs gem5) → only then is a surviving hit a candidate **TARGET** bug.
Never promote a hit to "real defense bug" until it has cleared every disqualifier under a **faithful,
stall-injected** rerun (the campaign's exact `run_config.jsonc` — see CLAUDE.md "Reproducing a hit").

Legend — **layer/verdict:** 🔴 real target/defense bug · 🟠 checker artifact · 🔵 alloy
model/concretization/enumeration · 🟡 pipeline/codegen/tooling · ⚪ config/testset realizability (not a
bug) · ⚫ generic gem5 quirk (scheme-independent, out of scope).
**Status:** ✅ verified · 🛠 fixed · ⏳ open / owner-gated · 📝 source-audited (read-only, not yet
reproduced from generator output).

---

# LAYER A — bugs in the TARGETS (the research signal)

These are real weaknesses in the defenses under test. This is what SimSpect exists to find.

## A1. 🔴📝 Recon OTB — `getOldestTaint` keeps the WRONG (oldest) taint source
- **Build:** `/work/gem5-recon[-modded]`, `--scheme=2` (STT). **Layer:** target (taint tracker).
- **Signature:** an ALU op with two tainted sources (one older, resolving first; one younger, still
  speculative). `TaintTracker::getOldestTaint` picks the **oldest** seqNum and stores only that as the
  dest's taint; when the older source's branch resolves, `freeTaints()` drops the dest taint even though
  the younger source is still speculative → the transmitter reads an "untainted" secret-dependent address.
- **Root cause:** `src/cpu/o3/secure_scheme/taint_tracker.cc` — `getOldestTaint()` (119-131) picks lowest
  seqNum; `propagateTaints()` (108-116) stores only that single source; `freeTaints()` (134-155) frees on
  non-speculative. Fix = track **youngest**, or track **all** sources and free only when all resolve.
- **Verdict / status:** REAL defense bug, demonstrated **hand-crafted** (`oldest_taint_bug/debug_out/
  inst-oldest-taint-bug.s`, pipeview shows the xmit `ic` = issued+completed in the spec window). Full
  writeup `reconresults.md` Bug 1.
- **⚠️ Caught by SimSpect?** **No — the generator never emits the gadget.** See **C3 (OTB generation
  gap)**: the precursor `ld→other→xm` is legal but absent from the capped enumeration. So this real target
  bug is currently only provable by hand; the model can't exercise it without a forcing predicate.

## A2. 🔴✅ Recon SLF — store-to-load forwarding bypasses the STT taint check
- **Build:** `/work/gem5-recon-modded`, `--scheme=2` (STT). **Layer:** target (LSQ). **Example:**
  [`bug/recon_SLF_stlf_bypass/`](recon_SLF_stlf_bypass/) (`inst-014912`).
- **Signature:** a tainted *speculative* load whose address is speculative, with a prior store to the
  same address. The LSQ `read()` STLF path forwards the store data and returns `NoFault` **before** the
  STT taint check fires → the load is marked **ready-within-ROB (completes)** inside the speculative
  window, ~1000 ticks before its squash, **with no cache packet**.
- **Root cause:** `src/cpu/o3/lsq_unit.cc` — STLF path returns `NoFault` at ~line 2030, before the STT
  taint check at ~2090; `WritebackEvent::process()` (194-212) checks the `Delay` scheme but **not** STT.
  `reconresults.md` Bug 2.
- **Verdict / status:** REAL defense bug. **Both** hand-crafted (`STL_bug/inst-008297.s`) **and caught
  live from generator output** — `inst-014912` in `results/Recon_6__20260602_122016` is the **only**
  confirmed real leak among that run's 184 ld hits (the other 183 are the **B1** checker FP). Verified
  `4a:reconHitDiag`; trace in `bug/recon_SLF_stlf_bypass/trace_excerpt_sn600.txt`.
- **Key lesson (drove the B1 fix):** the correct leak criterion is **"data obtained / completes before
  squash while tainted+spec," NOT "sent a cache packet."** An SLF load leaks *without* touching cache, so
  a cache-reach test misses it. This is now the `check_ld` `store_forward`/data-obtained gate (B1).

## A3. 🔴📝 STT implicit-channel branch defense is structurally non-functional
- **Build:** `/work/stt` (cwfletcher/stt) + Amulet STT_AE. **Layer:** target (ROB taint logic).
  Three independent defects, writeup `results.md`:
  - **A3a — `hasImplicitFlow` is computed but never used.** `rob_impl.hh:compute_taint()` calls
    `implicit_flow()` (sets `hasImplicitFlow`) but feeds **only** `hasExplicitFlow` into `isArgsTainted`.
    So `--implicit_channel=1` turns on the computation + the `commit_impl.hh:934-954` squash-delay, but
    the delay's guard `isArgsTainted()` is always false for an implicitly-tainted branch → **zero effect.**
  - **A3b — even if A3a were fixed, `implicit_flow()` only fires when a *previous control inst* already
    has `hasExplicitFlow`.** The mispredicting branch that opens the window usually has untainted
    operands (e.g. `movq $1,%rdx; testq; je` — immediate), so implicit flow never propagates into the
    window. (`inst-007572_v0`: xmit branch depends on `%rdx` from an immediate, independent of the
    speculative load that taints `%rax`.)
  - **A3c — pending-squash race** (younger untainted + older tainted branch mispredict in the same cycle
    → secret-dependent squash signal). Fixed in `master` only (N. Mosier, `18e304f`); **absent** in the
    `updates` branch and the Amulet artifact.
- **Verdict / status:** REAL defense gap — `--implicit_channel=1` does **not** protect branch
  transmitters; the **only** working STT gate is `lsq_unit_impl.hh` load `fenceDelay(isArgsTainted())`
  (explicit channel). Source-audited across master/updates/Amulet + the `l1d_assoc` 4-hit cross-build
  diff. **Caveat:** the *dynamic* gem5 hits that first looked like this (`STT_6 br_x`) turned out to be
  the **B2** checker FP — STT's branch defense actually held under the sweep stall. So A3 is a real
  *source-level* gap, but it has **not** yet been demonstrated as a live generated-test leak; the live
  br_x "leaks" were the checker. Reconcile via a two-value differential before publishing as a live hit.

## A4. 🔴✅ STT visibility-point ↔ squash-drain race (timing-regime dependent)
- **Build:** `/work/stt`, `--scheme=2`. **Layer:** target (design-level race). **Example:**
  [`bug/stt_slowcomm_vp_squash_race/`](stt_slowcomm_vp_squash_race/) (`inst-047231`).
- **Signature:** a wrong-path tainted **load→load** xmit. STT roots load taint in
  `isAccess() && !isUnsquashable()` (`rob_impl.hh` compute_taint 812-814) and sets
  `isUnsquashable ⟺ isPrevBrsResolved()` (updateVisibleState 519-520). The instant the controlling
  mispredict **resolves**, `isPrevBrsResolved` propagates to the *younger wrong-path* insts → producer
  becomes unsquashable → dest-taint drops → xmit address untainted → xmit re-issues and **touches the
  cache in the gap before the squash drains the LSQ.** STT clears taint at the visibility point without
  excluding instructions that are themselves about to be squashed.
- **Driver (rigorously isolated):** the resolution→squash gap = **`commitToIEWDelay`** (commit→IEW
  squash-propagation latency), **not `squashWidth`** (which bounds only the ROB unwind, not the one-shot
  LSQ/IQ flush). Leaks at `commitToIEWDelay ≳ 3`; **does NOT leak at stock gem5 timing**
  (`commitToIEWDelay=1`, verified 0/1200 bare-stock). No zero-stretch PoC exists on this gem5; minimal
  PoC = stock + `commitToIEWDelay=3`.
- **Ruled out (this is what makes it a real-target verdict):** check_ld FP (cache-reach = real packet),
  model over-approx (XML 231/231 `addr_from_load`), `fnc`-commit-stall hook (identical on/off), squashWidth
  (leaks at realistic 8), concretization, BTB-force hook. Provenance: `claudelog` 2026-06-02 08:30 / 09:30
  / 10:15; diagnostic `diag_stt_vp_squash_race.py` (186/187 attributed).
- **Verdict / status:** REAL design-level race, **exposed only under raised redirect latency** (plausibly
  more realistic than gem5's optimistic default-1; real HW also has bounded squash bandwidth gem5 idealizes
  as one-shot). Real-world *exploitability* is open (gadgets are shallow ≤6 insts). The same race class
  reappears on **SPT Fence** (A5).

## A5. 🔴⏳ SPT Fence — same VP↔squash race (no *independent* SPT bug confirmed)
- **Build:** `/work/gem5-spt`, `--scheme=2`→`SpectreSafeFence` (DDIFT). **Layer:** target (same class as A4).
- **Signature:** the "Fence leaks pre-squash" open case. Gate is `lsq_unit_impl.hh:1180`
  `fenceDelay = isAddrTainted()`; untaint at the visibility point. Shape pc0 = mispredict branch (no
  committed predecessor) → pc1 = speculative load (taints rax) → pc2 = xmit (address tainted → genuinely
  fenced). At branch resolution the fence lifts, the wrong-path xmit sends a cache packet **~2 cycles
  before** the squash drains → **983 post-mispredict-producer survivors** send a real packet pre-squash
  (80/80 sampled). Slow-comm widens the gap; some stems still race at stock.
- **History (important — two wrong turns corrected):** first mis-attributed to "zero-init prologue
  untaints all shadowL1" (`claudelog` 22:40) — **WRONG** (shadowL1 is OFF in these runs; taint is
  speculation-independent at `rob_impl.hh:240`). Corrected `claudelog` 23:30: it's the **A4 VP↔squash
  race**, not memory untaint and not a realizability gap.
- **Verdict / status:** the 983 survivors = the same VP-squash race as STT (A4); **real-bug-vs-hook
  attribution OPEN**, routed to the STT-race root-cause track. The other ~3.5k slowcomm survivors are
  **pre-branch-producer** = harmless over-approx (address from a non-speculative load). No SPT-*specific*
  defense bug has been confirmed — the const-addr/STLF "leaks" were all C2/B1 artifacts (see C2, B1).

## A6. ⚫✅ gem5 O3 livelock at `commitToIEWDelay ≥ 5` (generic, NOT a defense bug)
- **Build:** `/work/stt` (and the timing ceiling differs per build). **Layer:** generic gem5 quirk.
- **Signature:** gem5 livelocks in commit (ROB stuck "Trying to commit"; runaway tick + multi-GB
  pipeview) when `commitToIEWDelay ≥ 5`. Reproduces at **scheme=0 (Unsafe)** and `fnc=0` → it is a
  base-model timing-config limit of this O3 fork, **not** STT, **not** a hook, **not** a leak.
- **Verdict / status:** out of scope; respect the ceiling (≤4). It is the upstream cause of the disk-full
  crashes via runaway pipeview — *that* tooling consequence is fixed under **D2**. `claudelog` 04:30.

---

# LAYER B — bugs in the CHECKERS (Stage 3 measurement)

A checker bug makes gem5 *look* like it leaked (or didn't) when it didn't (or did). These inflate/deflate
hit counts and are the first non-XML disqualifier for every load/branch hit.

## B1. 🟠🛠 `check_ld` scored at "Executing load", not at completion
- **Signature:** `check_ld` keyed the verdict on the LSQ **"Executing load"** tick (`lsq_unit.cc:725`,
  emitted at the *top* of `executeLoad`, before the defense decides to expose). A tainted load bounced
  into `delay_unit` (`lsq_unit.cc:2104`) and squashed **without completing** never accessed the cache —
  but was scored a leak anyway. Inflated recon/STT ld counts massively (**183 of 184** Recon_6 ld hits).
- **Fix (CHECKER, affects every load sweep):** `gem5_common.py:parse_lsq` now also captures `packet_tick`
  ("successfully sent out packet(s)") and `spec_read_tick` (both already in the LSQUnit trace → no extra
  gem5 run). `check_ld` ANDs a **data-obtained** gate on the window verdict: leak iff `reached_cache`
  **OR** `store_forward` (SLF completion, no packet). Dropped: delay_unit bounce, `spec_read_only`,
  `never_executed`. **Squash timing never gates** (a squashed load that obtained data still leaked).
- **Status:** FIXED (`claudelog` 22:45, owner-approved). Load hit counts **drop** on next run to genuine
  data-obtained cases — re-triage any load campaign that spans this change.
- **Lesson:** the correct bar came from **A2** (SLF completes without a packet) — "cache-reach is the bar"
  was itself a wrong intermediate conclusion, corrected here.

## B2. 🟠🛠 `check_br` keyed on the complete/resolve tick, not the squash/redirect tick
- **Signature:** STT (and any redirect-delaying defense) lets a tainted branch **resolve** in-window
  while **delaying its squash/redirect** out of the window ("made pending",
  `commit_impl.hh:934-954`, `stalledBranchMispredicts=2`). `check_br` tested the **resolve** tick
  (`xmit_complete`), which is in-window in both STT and Unsafe → **false positive.** This is what made the
  `STT_6 br_x` "leaks" look real (the now-superseded "real FLAGS-taint gem5 bug" claim).
- **Fix:** `gem5_common.py` always traces `Commit`, adds `parse_commit_squashes()` (pc→squash ticks),
  threads `squash_by_pc` into the checker; `check_br` keys `xmit_signal` on the xmit's **squash tick**
  (falls back to complete-tick only when no Commit trace). Validated: 5/5 STT FPs flip to no-hit; real
  Unsafe leaks still caught.
- **Status:** FIXED (`claudelog` 00:30; `mdsToRead/STT_BRANCH_LEAK_ROOTCAUSE.md`). br_x counts in the
  STT sttbuild/interleave runs were inflated by these FPs; re-run for true numbers.
- **Residual scope note:** `check_br` still does **not** enforce the `lc/fnc` window the way `check_ld`
  does (CLAUDE.md known gap) — it is sound for resolution-blocking defenses (STT load-fence, DoM) but
  would still need the squash-tick discipline for any future redirect-delaying defense.

## B3. 🟠🛠 `diag_ld_cache_reach.py` faithful-repro bug (dropped the sweep stalls)
- **Signature:** the cache-reach diagnostic re-ran gem5 with the **raw** annotation, omitting the sweep's
  `unresolved_stall_cycles=5000`. That stall is injected into the `.ann.json` by
  `pipeline._inject_stalls` (it lives in `sweep.*`, **not** an env var), so `_apply_config_env` missed it
  → the speculative window collapsed → every cache-reach rerun was invalid (and silently "confirmed" 0).
- **Fix:** `_apply_config_env` forwards `sweep.*` as `SIMSPECT_SWEEP_CFG`; `diagnose_one` rebuilds the
  grid and injects stalls per grid point, OR-ing `real_access`.
- **Status:** FIXED (`claudelog` 19:22). **Any prior cache-reach rerun that didn't inject sweep stalls is
  suspect — re-run with the fixed diag.** General rule: a by-hand rerun must mirror the campaign's full
  hook + stall state (CLAUDE.md "Reproducing a hit").

## B4. 🟠✅ The recon "OTB" classifier matches are NOT real OTB (abstract-opstate trap)
- **Signature:** `diag_recon_load_hits.py` flagged `inst-004271/4272/4273` as OTB, but in the concretized
  asm the spec load overwrites `%rax` and the `TOther` (`idivq`) output is dead → the xmit address is fed
  by a **single** spec load, not a committed+spec merge.
- **Root cause:** the classifier matched **shared abstract opstate**, which is **not** an `rf` (dataflow)
  edge — at concretization the last writer in program order wins. (Same trap is enumerated as a pitfall in
  `mdsToRead/OTB_GENERATION_GAP.md`.)
- **Status:** classifier false match (these 3 fell into the **B1** 183-FP bucket). Verified
  `4a:reconHitDiag`. A diagnostic that keys on shared opstate instead of `rf` will mis-bucket — always use
  the `rf` edge.

---

# LAYER C — bugs in ALLOY (Stage 1 model / concretization / enumeration)

These make the model either **over-flag** a benign value as secret (→ gem5 correctly doesn't leak →
spurious "hit") or **emit a test that doesn't realize the program the model reasoned about** (→ gem5 runs
something else). Both are owner-gated (`.als` edits need approval) and most imply a **from-XML** relaunch.

## C1. 🔵⏳ `rf` is not pinned to the most-recent writer → register-state clobber (concretization)
- **Where:** `same_state_rf` + friends, lines 156-159 (shared by **17 models**:
  `grep -l "fact same_state_rf" STAGE1_alloy/models/*.als`). Full analysis `mdsToRead/ALLOY_RF_LASTWRITER_BUG.md`.
- **Signature:** `rf` only requires producer/consumer to **share a state**; nothing forbids a state from
  having **two writers** or forbids an `rf` edge from reading **past** a newer same-state write. After
  concretization (one state → one register) the newer write **clobbers** the register → the consumer
  reads the wrong value → **the program that runs is not the program the model reasoned about.**
- **Pervasiveness:** 90% of base XML collapse to a single `Reg_s`; **58.6%** (2344/4000 sampled) carry ≥1
  clobbered rf edge → the **majority** of the testset has unrealizable register dataflow that
  concretization silently rewrites. Accounts for **13/19** of the SPT_6_oneLP `reached_cache` load→load
  "hits" (the other 6 are a separate signal — do not fold them in).
- **Verdict / status:** concretization bug (Stage-1 `rf` lacks a most-recent-writer invariant) —
  **not parsexml, not gem5.** Fix = **Option A** `rf_from_most_recent_writer` (validated SAT on a copy,
  150/150 enumerate, 0 clobbers). **NOT applied — owner-gated, 17 models, full from-XML regen.** Prior ld
  results on these testsets are broadly contaminated, not edge-case.

## C2. 🔵⏳ Protection-set over-approximation — "produced under speculation" ≠ "secret" (const-addr)
- **Where:** `SPT_6_oneLP.als`/`SPT_6.als` — `leakage_function` (339) enumerates *every* load address;
  `hardware_protection_policy` (337) seeds the protset with **~all operands**; propagation (222-236) then
  marks **any speculatively-produced value protected** — even a register written by a speculative ALU op
  reading only **constants**. Full proposal `mdsToRead/POTENTIAL_MODEL_FIX_constaddr_taint.md`.
- **Signature:** ~**99.9%** of SPT `ld` "hits" are constant-address loads. gem5/SPT correctly untaints
  them (DDIFT taint flows only from speculative **loads/memory**, not "produced under speculation"), so
  the load issues with a public address → gem5 "hit", no leak.
- **Verdict / status:** model over-approximation. Root mismatch: Alloy treats *produced-under-speculation*
  as secret; SPT/STT treat only *derived-from-a-speculative-load/memory* as secret. **Proper fix** = make
  the protset a **forward closure from real sources** (`Loads.outreg` + read memory) with **monotone
  (union)** taint, so constants fall out automatically and load outputs stay tainted. **NOT applied
  (owner-gated)** — currently **masked** by `diagnostics/diag_constaddr_load.py` (2795 known / 3 left
  NEW on `SPT_6_oneLP_fence`). ⚠️ Note: const-addr (C2) is **separate** from the rf-clobber (C1); the
  doc explicitly warns not to conflate them — re-measure each independently after any fix.
- **Scope rule (per CLAUDE.md diagnostics):** the const-addr diag is **testset-specific** — it propagates
  only to runs on that same testset, never across the name family.

## C3. 🔵⏳ OTB generation gap — the model CAN make the gadget but the capped enumeration never does
- **Where:** STT_6 / interleave enumeration. Full doc `mdsToRead/OTB_GENERATION_GAP.md`.
- **Signature:** the OTB precursor `ld → other → xm` (needed to exercise the real **A1** target bug) is
  **absent** from the default 100k enumeration — every `ld` xmit address is fed by an `rf` edge **directly
  from a single load** (66,512/66,512 stale; re-confirmed 0/2000 fresh). **But forcing it is immediately
  SAT** (`pred otb_shape { some x:Loads | (x in xm) and (some o:(Otherns+Otherxs) | some (o.outreg &
  rf.(x.inaddr))) }`).
- **Root cause:** a **`max_instances` cap + enumeration-order artifact**, NOT a model/minimality limit.
  `gen_useful_litmus` minimizes only via `RR`/`RS` (resolve branch / remove state) — **never** `RI`/`RO`
  — so extra ops and unspecified operands are allowed; the leak is simply satisfied by the *simpler*
  direct `load→xmit` shape, which fills the cap first. (`Otherxs.inreg` is also commented out at model
  line 315 → no `other_x` transmitters either.)
- **Verdict / status:** enumeration gap. **To exercise the A1 target bug from the generator** you need a
  dedicated OTB testset = the `otb_shape` forcing predicate + `interleave.enabled` (owner-gated `.als`/
  config change). **Pitfall (documented):** never infer "the model can't" from "absent in the capped
  enumeration" — force the shape with a predicate and run Alloy. Base XML is *pre*-interleave; shared
  opstate ≠ rf edge; x86 SIB/`lea` parsing traps all produced wrong answers here.

## C4. 🔵⏳ Stale STT testsets — generated before the `RS` minimality clause was effective
- **Where:** `testsets/STT_6/xml`, `testsets/STT_6_interleave/xml` (generated 2026-05-19 02:44).
- **Signature:** the XML predates the `gen_useful_litmus` clause `all s: State |
  secure_speculation_scheme_p[RS->s]` ("every state must be necessary"). Result: **40% isolated no-op
  `other` ops, 8.6× redundancy, only 2 distinct leak dataflows** (`load→xmit.inaddr`,
  `load→branchx.inreg`). The current model (RS active) gives **0% isolated, 1.4×, 45 dataflows** — proven
  by toggling the RS line (0%↔38% isolated).
- **Verdict / status:** testset-generation staleness (the tests aren't *wrong* — they satisfy the old
  contract — but cover only **2 of ~45** leak topologies → the STT sweeps are massively under-covering).
  **REGEN recommended** (from-XML). The earlier "WIN1 / require-interaction" proposal and the 9.1× bloat
  numbers were computed on this stale set and are **redundant** with RS — do **not** add WIN1.
  gem5-behavior findings on the specific tests run remain valid. `claudelog` 2026-06-02 (reconbugs).

---

# LAYER D — bugs in the PIPELINE / Stage-2 codegen / harness / config

Build-agnostic SimSpect defects: they drop, corrupt, mis-run, or mis-account tests.

## D1. 🟡🛠 dup-PC codegen bug (parsexml Stage 2) — ~6% of br_x tests fail to compile
- **Signature:** the xm-branch NOP-injection queue (`parsexml.py:~737`) injected a fall-through NOP both
  when the xmit branch was **last** *and* when the **next instruction was also a branch**, assigning the
  NOP `pc = br_pc+1` — which the following branch already owns → duplicate `bb_<pc>:` label →
  `symbol already defined` → the test is silently **dropped** (`inst-017570/014962/020383`, etc.).
- **Status:** FIXED (`opus-claude` 22:50) — inject only when the xmit branch is the last instruction.
  AUDIT #14 called this "dormant/unreachable"; it was **firing live**. **Relaunch:** already-generated
  `.ll` keep the old logic → wipe/`--force` the **llvm** phase for SPT_6_oneLP / STT_6 / STT_6_interleave
  and regen llvm→asm onward. (Cross-stage invariant it depended on: `DESIGN.md` "xmit branches are always
  resolved in STT_6".)

## D2. 🟡🛠 pipeview space blowup — unbounded/orphaned gem5 → disk-full crashes
- **Signature:** `gem5_common.py:run_gem5` ran gem5 with **no timeout and no tick cap**. A
  runaway/livelocked run (see **A6**) appended unboundedly to its single `--debug-file` pipeview
  (`O3PipeView,LSQUnit,Commit`) → **65-127 GB/run**; ~10 in parallel filled the 1.8 TB volume. Killed
  sweeps left gem5 children **reparented to PID 1 still writing the unlinked pipeview**, so `rm` freed
  nothing.
- **Status:** FIXED (`6:spaceAudit`) — `_run_bounded()` adds a 120 s wall-clock timeout +
  `start_new_session`/process-group SIGKILL + `PR_SET_PDEATHSIG` (orphan-proof) + `--abs-max-tick=1e11`.
  Baked into `gem5_common` so every checker invocation gets it free. The pipeline already retained **zero**
  saved pipeviews — the blowup was the live in-flight trace.

## D3. 🟡🛠 `idivq` codegen with no nonzero guarantee → ~250k architectural divide-fault noise records
- **Signature (AUDIT #15):** unguarded `idivq` faulted architecturally (divisor zero-ness is itself a
  side channel); 97% of div faults were architectural (faulting PC before the mispredict), flooding
  `STT_6_sttbuild` with ~250k Divide-Error noise records.
- **Status:** RESOLVED — `parsexml.py:1905` routes the divisor through `%rcx` with `orq $$1,%rcx` **except
  for xm divs** (which keep the unguarded idiom so the fault can fire as a leak). `gem5_common.py`
  `classify_divide_panic` promotes a speculative xm-div fault to `status=ok, hit_kind="div_fault"`.
  Dormant until `leakage_function` widens to include `Otherxs.inreg` (commented out, line 315) — until
  then the value is the noise-eliminating codegen guard.

## D4. ⚪🛠 Amulet run was 100% errors reported as "0 hits" (config: Ruby build + `caches:true`)
- **Signature (AUDIT #1):** the Amulet artifact is a Ruby-only (`MESI_Two_Level`) build whose `se.py`
  already wires `cpu.icache_port`; `run_config` passed `caches:true` → `CacheConfig.config_cache` connects
  classic caches over the same port → `fatal: Port ... already connected`. All **41,373** `STT_all_amulet`
  records were `status="error"`, but the watcher logged "0 hits" — reads like "defense works." It produced
  **zero valid data points.**
- **Status:** config bug. Fix = `caches:false`, discard the error results, resume. ⚠️ **Methodology
  lesson:** an all-error run is indistinguishable from a clean run in the hit count — always check the
  `status` distribution, not just the hit total.

## D5. 🟡✅ Sweep-completeness "error" rows are a harness artifact, not a leak/bug
- **Signature:** `pipeline._aggregate_sweep_results` marks a stem `error` when its row is missing from ≥1
  of its `sweep_grid_size` grid points. The 348 `error` rows in `STT_6_interleave_sttbuild`
  mispredict_taken/ld are stems present+`ok` in grid pts 0/1 but absent from grid pt 2 (the heaviest
  stall) because that check_ld batch file was never written — the invocation hung ~09:18 (consistent with
  the **A6/D2** runaway risk).
- **Status:** harness artifact, **no hidden leak** in the two completed grid points; only *confirmable* by
  re-running grid pt 2 for those 348 stems. `claudelog` 23:10; `results.md` tail.

## D6. 🟡 Minor pipeline/tooling latent items (AUDIT — mostly read-only, low blast radius)
- **#17 O(N²) hits-copy loop** (`pipeline.py:910-914`) — re-walks all results + stats fs each batch
  (~5B ops at 100k). **#19** per-test JSON sidecars written even for non-hits (100k tiny files). **#16**
  non-streaming `pipeline.py gem5` bails if `window-results.json` exists and `--force` wipes everything
  (CLI users get burned; the watcher works around it). **#18** `save_provenance` archives only `parsexml`
  + `.als` + run config — misses `batch_generate.py`, `compile_annotate.py`, `instructions.jsonc` (a
  provenance replay could diverge). **#9** `check_ld.py`/`check_other.py` are functionally identical.
  **#21** `pass_interleave` branch-target remap vs `ftbypass_<pc>` trampolines — unverified edge case.
  None block correctness today; tracked in `AUDIT.md`.

## D7. ⏳ Open / unexplained: STT_all sttbuild 6-7× higher `mispredict_taken` hit rate (AUDIT #20)
- **Signature:** sttbuild taken-mode hits run 6-7× the not_taken rate, but **not** on recon-modded
  (STT_all_recon ≈ sttbuild STT_6 taken) → smells like a **per-build** taken-window behavior, not a model
  issue. Pre-dates the **B2** check_br fix, so part of it is likely inflated br_x FPs.
- **Status:** open — re-measure with the fixed checkers before trusting the asymmetry; if it survives, it
  is a build-behavior question, not a confirmed bug.

---

# Summary matrix

| ID | layer | title | verdict | status | proof |
|----|-------|-------|---------|--------|-------|
| A1 | target | recon OTB `getOldestTaint` wrong source | 🔴 real | 📝 hand-crafted (gen can't reach it → C3) | `reconresults.md` |
| A2 | target | recon SLF taint-check bypass | 🔴 real | ✅ live (`inst-014912`) | `bug/recon_SLF_stlf_bypass/` |
| A3 | target | STT implicit-channel branch defense dead | 🔴 real (source) | 📝 (live br_x was B2 FP) | `results.md` |
| A4 | target | STT VP↔squash race | 🔴 real | ✅ (timing-regime) | `bug/stt_slowcomm_vp_squash_race/` |
| A5 | target | SPT Fence = same VP↔squash race | 🔴 candidate | ⏳ attribution open | `claudelog` 23:30 |
| A6 | gem5 | livelock at commitToIEWDelay≥5 | ⚫ generic | ✅ (respect ceiling) | `claudelog` 04:30 |
| B1 | checker | check_ld scored at exec, not completion | 🟠 artifact | 🛠 fixed | `claudelog` 22:45 |
| B2 | checker | check_br scored resolve, not squash | 🟠 artifact | 🛠 fixed | `STT_BRANCH_LEAK_ROOTCAUSE.md` |
| B3 | checker | diag cache-reach dropped sweep stalls | 🟠 artifact | 🛠 fixed | `claudelog` 19:22 |
| B4 | checker | recon "OTB" classifier false matches | 🟠 artifact | ✅ (opstate≠rf) | `OTB_GENERATION_GAP.md` |
| C1 | alloy | rf not last-writer → reg clobber | 🔵 concretization | ⏳ owner-gated | `ALLOY_RF_LASTWRITER_BUG.md` |
| C2 | alloy | protset over-approx (const-addr) | 🔵 over-approx | ⏳ owner-gated (masked) | `POTENTIAL_MODEL_FIX_constaddr_taint.md` |
| C3 | alloy | OTB generation gap (cap artifact) | 🔵 enumeration | ⏳ needs forcing pred | `OTB_GENERATION_GAP.md` |
| C4 | alloy | stale pre-RS STT testsets | 🔵 staleness | ⏳ regen recommended | `claudelog` (reconbugs) |
| D1 | pipeline | dup-PC codegen drops ~6% br_x | 🟡 codegen | 🛠 fixed (relaunch) | `claudelog` 22:50 |
| D2 | pipeline | unbounded/orphan gem5 disk blowup | 🟡 tooling | 🛠 fixed | `claudelog` 6:spaceAudit |
| D3 | pipeline | idivq fault noise | 🟡 codegen | 🛠 resolved | AUDIT #15 |
| D4 | config | amulet caches:true → all-error "0 hits" | ⚪ config | 🛠 fix=caches:false | AUDIT #1 |
| D5 | pipeline | sweep-completeness error rows | 🟡 harness | ✅ not a bug | `claudelog` 23:10 |
| D6 | pipeline | minor latent tooling items | 🟡 | ⏳ tracked | AUDIT |
| D7 | open | STT_all taken 6-7× asymmetry | ⏳ unexplained | ⏳ remeasure post-B2 | AUDIT #20 |

## The big picture (what the four layers tell us)

- **Confirmed real target bugs (the deliverable):** **A2** (recon SLF, the only one caught *live* from
  generator output) and **A4** (STT VP↔squash race, timing-regime). **A1** (recon OTB) and **A3** (STT
  implicit channel) are real in the *source* but SimSpect can't yet exhibit them from generated tests —
  A1 because of the **C3** enumeration gap, A3 because the live br_x hits were the **B2** checker FP. **A5**
  (SPT) is the A4 race class, attribution open.
- **The model layer is the dominant source of *false* signal:** **C1** (58% of the testset has
  unrealizable dataflow) and **C2** (~99.9% of SPT ld hits) together explain the overwhelming majority of
  "hits" — they are over-approximation / concretization artifacts, not leaks. Both fixes are owner-gated
  and imply a from-XML regen. **C3/C4** mean the testset *under-covers* the real bugs (misses OTB, covers
  only 2/45 STT dataflows) — the model is simultaneously too permissive (over-flags) and too narrow
  (under-enumerates the gadgets that catch real bugs).
- **The checker layer was systematically over-counting** until **B1/B2** landed (load *and* branch hits
  were inflated by early-tick scoring); re-run any campaign that spans those fixes before trusting counts.
- **The pipeline layer is mostly fixed** (D1/D2/D3) but D1 implies an outstanding from-parsexml relaunch.

## Verification status (don't over-trust)

Independently verified in-session (`4a:reconHitDiag`): **A2, B1-mechanism, B3, B4**. Rigorously isolated
(`designconsultant`): **A4, A6**. Source-audited read-only (not reproduced from generator output):
**A1, A3, A5, C1-C3**. Tooling fixes verified by their own tests: **B1, B2, D1, D2**. Anything marked 📝
or ⏳ should clear a **faithful, stall-injected** rerun (campaign `run_config.jsonc` + full hook/stall
state) before being treated as settled — see CLAUDE.md "Reproducing a hit/bug by hand."
