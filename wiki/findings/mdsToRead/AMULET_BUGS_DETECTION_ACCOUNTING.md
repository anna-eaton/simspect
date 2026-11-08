# AMuLeT bugs × SimSpect detection — full accounting, strategies, and why-not

**For:** Anna · **Date:** 2026-06-08 · session `5:invisispec` (autonomous)
**Purpose:** for EVERY bug AMuLeT reports in the four defenses, either detect it with our
pipeline+watchers (and show it) or give the **precise reason our formulation can't** — even
with all the new tools (Ruby, rebuild permission, small caches, ProtocolTrace watchers).
Companion to `INVISISun PEC_UV1_CONFIRMED.md`, `docs/COMPOUND_TRANSMISSION_CRITERION.md`,
`docs/AMULET_VS_SIMSPECT_SCOPE.md`.

## ⚡ CURRENT (2026-11-08, hooks-v2 session): what we learned running the AMuLeT defenses through SimSpect hooks v2

This section supersedes the June material below for InvisiSpec, CleanupSpec and SpecLFB. The June numbers came from DPRINTF checkers on the old STT_6 testset. Everything here comes from the SimSpect hook lines (`wiki/design/SIMSPECT_HOOKS.md`) scored by `STAGE3_gem5/check_footprint.py` + `specs/leakage/<defense>.json`. Durable log entries are under `claudelog.md` 2026-11-07/08 `hooks-v2*`; open decisions are in `URGENT_TODO.md`.

### 1. What the hooks are, and how a verdict is made on these builds

- **The hooks.** Hooks v2 are print-only lines (`O3PipeView:simspect:…`) for every cache, buffer, TLB, LSQ, ROB and branch event, plus each defense's own decisions:
  - InvisiSpec: spec-buffer fills and releases, expose/validate;
  - SpecLFB: per-load unsafe flags;
  - CleanupSpec: cleanup requests, skips, restores and one `cleanup_done` per squash.
- **Verification.** On 10 cases the hooks were verified against reference binaries with the same non-print code: identical sim ticks and identical pipeline records.
- **InvisiSpec crash fixed.** A half-finished hook converted the cache-level ID on L1 hits, causing `Invalid range for type MachineType`. Fixed by `simspectLvlOf` in `Sequencer.cc`.
- **How a verdict is made.** On these builds the STT_6 testset is only the stimulus. The verdict comes from the hook lines: a footprint in a protected structure by any squashed load, inside the speculative window. The model's transmitter does not decide it (D2); per-hit attribution says whether the leaking load is the transmitter.
- **Structures are chosen only from what each paper claims to protect.** Each claim is quoted in the criterion JSON; nothing is added or removed to hit or avoid a bug.
  - **InvisiSpec:** the data-cache hierarchy (L1D, L2, directory: occupancy, replacement, coherence) and the D-TLB (§III-B p3). Not the I-cache/ITLB (fn. 2 p3). Not MSHRs: "contention on other resources, such as MSHRs … considered out of scope in this paper" (§VII p10).
  - **SpecLFB:** L1D + L2 presence (§1 p632, §7 p640). Not TLB or port contention (§4 p635), and not hits (§9 p643).
  - **CleanupSpec:** L1D + L2 presence (§2.1 p3). L2 victims and replacement state are by design (§1 p2). The directory is not observed: in this MESI_Two_Level build it is capacity-free `DirectoryMemory` (`MESI_Two_Level-dir.sm:30`), so it never evicts, and its only replacement event mirrors an L2 eviction (`:72,:518`). Reason recorded in `cleanupspec.json` `why_not_observed`.
  - **Not checked now (Anna 2026-11-08):** timing channels (unXpec cleanup latency, UV2 contention), since each is a different side channel.

### 2. Every AMuLeT bug, by layer

| bug | defense | in v2 trace? | checker flags it? | reached by STT_6 tests? | status |
|---|---|---|---|---|---|
| UV1 spec L1D eviction | InvisiSpec | yes (`L1D:evict req=specld` + `L2:coh` PUTX; gone with `--apply-spec-eviction-patch`) | yes, Spectre and Futuristic | yes: 2995 / 3000 tests (after the by_pc fix) | found |
| UV2 same-core MSHR interference | InvisiSpec | partly (MSHR `buf_fill` timing, no stall line) | no | not tested | **out of scope:** InvisiSpec §VII p10 |
| KV1 spec instruction fetch | InvisiSpec | yes (`L1I:fill` of the wrong-path line) | no | no | **out of scope:** InvisiSpec fn. 2 p3. Fetch events also carry no seq |
| UV3 spec store not cleaned | CleanupSpec | yes, through a read-modify-write (`req=st` fill, then `cleanup_skip why=nohitinfo`) | yes | no: STT_6 has 0 RMWs | needs RMW stimulus (decision V7) |
| UV4 split request not cleaned | CleanupSpec | yes (`cleanup_skip why=split`) | yes | yes: 38 tests (TBEs 8) | found |
| UV5 too much cleaning | CleanupSpec | yes (an older committed hit, then `cleanup_inv`) | **yes since 2026-11-08** (ownership rule, §3.4 p7) | not seen in the sample | caught by the checker on the demo |
| KV2 unXpec | CleanupSpec | yes (squash→`cleanup_done` 43 cycles after a miss vs 1 after a hit) | no | — | timing channel, not checked now |
| UV6 first spec load unprotected | SpecLFB | yes (`LSQ:unsafe unsafe=0 … lqhead=1`, then a fill) | yes | yes: 1143 / 1142 of 1500 tests per mode | found |
| walk-order (sticky PrevNoUnsafe) | SpecLFB | yes | yes | yes: 157 + 162 tests where it is the only cause | DECIDE: UV6 with a wider scope, or a separate bug? |
| **jmp-shadow (NEW, verified)** | SpecLFB | yes | yes | yes: 148 taken-mode tests | **real bug**; see §3 |
| KV3 spec store → D-TLB | STT | — | — | not targeted: our STT leakage function has load addresses and branch predicates, not store addresses | STT does not explicitly exclude stores (STT fn. 2 ties TLB protection to delaying loads); paper paragraph frames it as our model's choice |

### 3. New SpecLFB bug: jmp-shadow (review: `wiki/findings/bug/speclfb_jmp_shadow/README.md`)

- **The mechanism.** `ROB::updateSafeState` keeps one rolling `prevBrsResolved`. An unresolved conditional branch sets it false. A younger direct `jmp`/`call` then assigns it `isDirectCtrl && isUncondCtrl` = true (upstream `SpecLFB-gem5/src/cpu/o3/rob.cc:501`, the simple path that actually runs). That erases the older branch's shadow, so every later load skips CUSL and fills L1D/L2 speculatively.
- **Provenance.** The same code is in upstream `smallcute123/SpecLFB` and in AMuLeT's copy. DOLMA, which the comment cites, computes a per-instruction `isControlInducer` instead (`dolma/src/cpu/o3/rob_impl.hh:308-348`). So this is a porting bug.
- **Ruled out as our artifact:** it reproduces on a pristine build with zero SimSpect changes and a natural misprediction, using SpecLFB's native prints as the oracle.
- **Relational leak:** secrets 2/4/7 install different lines only with the jmp.
- **Variant matrix:**
  - leak: jmp, call+ret, call-pop, far jmp;
  - protected: a same-length nop, an indirect jmp, a conditional branch, ret, a jmp before the branch, a jmp after the transmitter.
- **Counterfactual:** a one-line fix removes it, and the UV6 path is unchanged.
- **Not in AMuLeT:** its Fig. 8b PoC contains a jmp, but AMuLeT attributes that leak to UV6.
- **Impact:** if/else joins and calls compile to direct jumps, so ordinary code substantially weakens the defense.

### 4. Other per-defense findings

- **SpecLFB.**
  - *Walk-order:* the ROB sees a load one cycle before the LQ (`renameToROBDelay=1` < `renameToIEWDelay=2`), and `PrevNoUnsafe` is never cleared. The native trace lines up exactly with the hook lines.
  - *LFB parking never happens in this build:* a HitUSL miss is refused at the port and replayed. So the "parks unsafe misses in the LFB" claim in `PROTECTION_SCOPE_TABLE.md` / `speclfb.json` is wrong for this build (correction pending approval).
  - *Old numbers:* "68/300" counted cache hits, which SpecLFB scopes out. The install-keyed rates are 86.7% / 96.8% at 1 kB L1D (D3).
- **CleanupSpec.**
  - *TBEs:* with `--L1_TBEs=2` (accidentally inherited from the tree default; AMuLeT 256, paper 64), 62% of STT_6 tests deadlock with or without cleanup, and the completed ones never run a cleanup. At 8 there are no errors.
  - *Ownership rule ("count as both", Anna 2026-11-08):*
    - a line a squashed load installed belongs to an older non-squashed access that hits it, so cleaning it is over_clean (UV5);
    - the squashed load's evicted victim must still be restored;
    - post-squash or squashed accesses never claim a line.
    - On the kept traces, the 2 earlier NEW hits (`inst-101824`, `inst-102050`) are now victim-only under_clean.
  - *Never fired:* `cleanup_wait`, `cleanup_drop_data`, `evict req=rollback` and `inv why=clusivity` did not fire in about 6100 runs.
- **InvisiSpec.**
  - *D-1:* the DTLB replacement-on-hit deviation is in every hit. The paper claims D-TLB protection, so it is a genuine deviation, bucketed separately (D-1).
  - *Who leaks (D2):* in 802 of 2883 UV1 hits only non-transmitter loads leak, mostly the wrong-path epilogue `POP_R`.
  - *Window (C-2):* `inst-031760` has a real UV1 eviction just before the window opens, behind a late-committing lc load.

### 5. RMW instructions (`wiki/design/VOCAB_TABLES.md` "RMW agent findings")

- **Protection:** a speculative RMW's load half (`ldst`) is protected like a plain load on InvisiSpec, SpecLFB, STT and Recon-STT. Only CleanupSpec skips the undo, which is UV3; it is in scope because CleanupSpec assumes RFOs are non-speculative (p8 §4).
- **Never speculative:** `lock`/`xchg` (`ldstl nonSpec`).
- **Why we generate none:** pass 5 emits each ld/str as separate inline asm, and STT_6 has no ld→op→str chain.
- **Options (V7):** the recommended one is (d), a value-neutral RMW as an opt-in ld-transmitter variant.
- **Untested hypothesis:** a speculative GETX invalidating another core's copy needs a 2-core test.

### 6. Configurations vs AMuLeT (`wiki/findings/audits/2026-10-28/full_configs.md`, last section)

- **No build matched AMuLeT.**
  - *AMuLeT's defaults:* 32kB/8 L1D, 256 TBEs, a 2GHz clock and `--access-backing-store`. It shrank structures only for InvisiSpec-Patched (§4.5.1 Table 6: 2-way L1D, 2 MSHRs).
  - *Ours:* shrunk caches (1kB/2 or 2kB/4) on all footprint defenses.
- **Decisions (Anna 2026-11-08).**
  - Keep shrinking for footprint runs (`runconfigs/footprint/`; CleanupSpec `--L1_TBEs=8`).
  - Use AMuLeT's exact flags for every AMuLeT comparison and all timing (`runconfigs/amulet_parity/`, all four AMuLeT builds).
  - Two STTs: `/work/stt` for SimSpect's STT results, and amulet-STT only for AMuLeT comparisons.
- **amulet-STT glue fixed.** Its `se.py` now honours `--threat_model`/`--needsTSO`/`--STT`/`--implicit_channel` (`gem5-hooks/amulet-STT/se_py_threatmodel_glue_20261108.diff`; smoke-tested Futuristic + TSO).
- **Remaining harness differences** (no AMuLeT equivalent, stated in the paper notes): the forced branch prediction, the 5000-cycle resolve stall, a cold cache per test, and a one-run footprint verdict instead of AMuLeT's 140-input relational one.
- **Still open:** InvisiSpec TSO/spec-buffer-hit, clock and predictor for the footprint arm; the "configuration of record" for the paper.

### 7. Checker and parser fixes made

- **`check_footprint` by_pc (2026-11-08).** The checker re-parsed the trace and dropped the Commit-trace lc retire fill. That wrongly disqualified 114/3000 InvisiSpec tests per scheme and 202 CleanupSpec records. Fixed and tested.
- **Glued debug-print residue (`gem5_common._unglue`).** CleanupSpec `lsq_unit.hh:1257` (`\n.`) and `RubyPort.cc:272` (`\n `) glue text onto the next line, which made a hook line drop. Every parser now strips it; fixture parses are unchanged.
- **Ownership rule** (§4 above).
- **Deployment:** all deployed to the cafe2 harness `/tests/simspect_fixed_20261030/` (2026-11-08, md5-verified). Footprint tests pass 37/37 on both machines.

### 8. Hook gaps (none blocks a finding; full list in `SIMSPECT_HOOKS.md` "Gaps found by the first STT_6 runs")

- Ruby resource/protocol stalls print nothing (`StateMachine.py` ~1273-1295).
- Instruction fetches have no seq.
- `cleanup_drop` has no seq/sq.
- An RMW read prints `req=st`.
- SpecLFB's `prevBrsResolved`, `PrevStoreResolved` and `SpeclfbStalled` changes are not printed directly.

### 9. Where everything is

- **cafe2 runs:** `/tests/simspect_fixed_20261030/results/STT_6_{invisispec_v2hooks_spectre,invisispec_v2hooks_futuristic,cleanupspec_v2hooks,speclfb_v2hooks}__20261107/` (READMEs; pipeviews of every hit).
- **Probes:**
  - `/work/amulet/jmpshadow_probe/`: pristine and counterfactual builds, about 2 GB each, deletable after review;
  - `/work/amulet/rmw_probe/`;
  - upstream clones in `/work/amulet/upstream/`.
- **Paper:** three proposed paragraphs as `\reviewnote` in ISCA-27 `sections/discussion.tex` (checked guarantees and scope, STT and stores, structure sizes). Uncommitted.


> ## ⚡ UPDATE 2026-06-08 (cont.) — gate un-cheated; fnc-stall hook ported; 2 bugs strict-confirmed; CleanupSpec reclassified
> 1. **Gate cheat reverted.** I had widened the lc/fnc upper bound (`OR branches_unresolved`) to fit the
>    late eviction — that was tuning the model gate and is **reverted**. Both checkers use the STRICT
>    window `lc_retire < t < fnc_retire AND branches unresolved`.
> 2. **Real fix = the `fnc-commit-stall` hook** (a standard SimSpect window-widener that holds the
>    first-noncommitted insn at the ROB head; recon/STT use it at 150 cycles). The amulet builds LACKED
>    it. I **ported it (7 sites) + rebuilt** the InvisiSpec (`X86_MESI_Two_Level`) and SpecLFB (`X86`)
>    builds — **non-defense instrumentation only, no defense logic touched.**
> 3. **Strict-window confirmation:** with `fnc_commit_stall_cycles=150`, **InvisiSpec UV1 = 11/12** and
>    **SpecLFB UV6 = 11/12** in the STRICT lc/fnc window (the hook moves fnc_retire out so the slow
>    Ruby/small-cache touch lands inside the window — the *physical* window widened, the *gate* untouched).
> 4. **CleanupSpec RECLASSIFIED (answering "where does the residue come from?"):** the post-squash residue
>    traces to a hookable **in-window event** — `L1_Replacement_OnInstall` (the spec load/store installing
>    a line). It becomes a leak when the **post-squash cleanup** (`Inv_CLEANUP`/`Load_ROLLBACK`/`InvL2_CLEANUP`,
>    all ProtocolTrace-visible) is MISSING (UV3/UV4) or OVER-evicts a non-spec line (UV5). So CleanupSpec is
>    **detectable by event correlation** (in-window install + squash + missing/over cleanup) — NOT a
>    final-state diff, NOT relational. This **supersedes** the "❌ out of scope" rows below for UV3/4/5.
>    Watcher not yet built (needs the CleanupSpec build + --ruby + the fnc-stall hook + the
>    install↔cleanup-event correlator), but the detection path is now identified.

> ## ⚡ UPDATE 2026-06-08 (loop cont.) — CleanupSpec watcher built; 4 bugs source-traced; 2 "out of formulation" rows REVISED to REACHABLE
> Deep source-first mechanism checks (the efficient approach — confirm the bug in the defense's own code,
> then either reach it or give a precise why-not). Full write-ups: `bug/STT_KV3_TLB_REVIEW.md` +
> `results/STT_6_cleanupspec_residue/CLEANUPSPEC_RESIDUE_REVIEW.md`; durable detail in `claudelog.md`.
> 1. **CleanupSpec watcher BUILT + validated** (`STAGE3_gem5/check_ld_cleanupspec.py`, results dir +
>    launcher). On STT_6 ld the **defense WORKS** (0 residue; an apparent "3 RESIDUE" was a checker FP —
>    a spec *hit* on a committed line — caught by gem5 verification + fixed; footprint = miss/install, not
>    a clean hit). fnc-stall hook ported to the CleanupSpec build + passthrough `--scheme` glue added.
> 2. **CleanupSpec UV3 (spec store not cleaned) — precise WHY-NOT:** the CleanupCache undo is structurally
>    **loads-only** (no store-queue cleanup) = the precondition, BUT a **squashed store never touches cache**
>    here (`canWB` set at commit only; no spec store RFO) → no cache footprint to leak. UV3-as-cache-residue
>    **unreachable in this store model**.
> 3. **✅ CleanupSpec UV4 (split request not cleaned) — EMPIRICALLY DEMONSTRATED** (`results/STT_6_
>    cleanupspec_residue/uv4_demo/`). Source: `issueCleanupRequest` hard-codes `state->isSplit = false;
>    //Assume no split - TODO` + single `cleanupReq`. Controlled gadget (cold .bss buffer, guaranteed
>    line-crossing offset, mispredict held unresolved): non-split load → installed line CLEANED
>    (`Inv_CLEANUP E>M_I`); split load → **2 lines install, 0 cleanup = residue**. Control (aligned
>    cleaned) rules out FP. 4th bug demoed (UV1, UV6, KV3, UV4).
> 4. **CleanupSpec assoc-2 deadlock RULED OUT as a bug** (ON==OFF both deadlock = generic Ruby tiny-cache
>    artifact).
> 5. **🔴 STT KV3 (spec store → TLB) — REACHABLE, full chain source-verified (REVISES "out of formulation:
>    TLB observation"):** TLB skips fill only if `req->isSpec()` (`tlb.cc:340`); `Request::SPEC` is set
>    ONLY in `readMem` (`base_dyn_inst.hh:1162`, loads); `writeMem` never sets it → a spec store
>    page-walks+fills the TLB unprotected. Reachable (translation at execute, pre-commit) unlike UV3.
>    Needs: store-address transmitter (gating) + multi-page sandbox + TLB watcher.
> 6. **🔴 InvisiSpec UV2 (single-thread MSHR/line interference) — REACHABLE + source-observable (REVISES
>    "out of formulation: timing channel"):** a spec load holds the line in `IX` (TBE; pool default 2);
>    `L1cache.sm:1189` STALLS any new mandatory request to that line (`z_stallAndWaitMandatoryQueue`, a
>    ProtocolTrace event) → a victim's stall is secret-dependent. Detectable at the stall event (not a
>    timing diff). Needs: a victim-probe contention gadget + stall watcher.
> 7. **✅ InvisiSpec KV1 (L1I instruction-fetch channel) — EMPIRICALLY DEMONSTRATED** (`bug/kv1_demo/`).
>    InvisiSpec's invisible-spec is LSQ data-loads only; fetches install the L1I line normally
>    (`L1cache.sm:1258` `{NP,I},Ifetch→IS`; the fetch unit has no spec handling). Gadget: a branch forced
>    (BTB) to predict TAKEN to a far label reached only speculatively → that label's I-line installs
>    (`Ifetch NP>IS`) under the misprediction but NOT in the correctly-predicted control. = KV1.
> **CONSOLIDATED LIVING ROLLUP → `mdsToRead/AMULET_LOAD_DEFENSES_PROJECT_LOG.md`** (read it first; this
> doc is the deep accounting it cites).
> **Net (updated 2026-06-09):** **7 AMuLeT bugs now DEMONSTRATED end-to-end — UV1, UV6, STT KV3,
> CleanupSpec UV4, InvisiSpec KV1, CleanupSpec unXpec, and InvisiSpec UV2.** UV2 (`bug/uv2_demo/`) was
> unblocked via the **TLB-warm-page trick** (a committed access warms the page so the speculative TLB miss
> isn't deferred → the spec load issues its GETSPEC): 4 spec loads on a warm page exhaust the 2-entry TBE
> pool — `--L1_TBEs=2` → 248 retry `NP>IX`/122k-tick serialize, `=8` → 4 clean concurrent. **UV3-as-cache-
> residue** has a precise why-not (squashed stores never touch cache). **UV5** (over-clean) is the lone
> remaining empirical gap — examined, blocked on the defense-independent assoc-thrash storm when a spec
> install evicts a committed victim (different blocker from UV2; TLB-warm trick alone won't fix it; needs a
> bounded eviction gadget). **Nothing is ruled out of scope without a precise, source-grounded reason.**

---

## 0. Headline accounting (every AMuLeT bug)

| # | Defense | Bug | What it is | Detected by us? | If not — WHY (formulation gap) |
|---|---|---|---|---|---|
| UV1 | InvisiSpec | spec-load L1 **eviction** | a USL evicts a live L1 line | **✅ YES** (29/30) | — |
| UV2 | InvisiSpec | single-thread **MSHR interference** | spec load occupies an MSHR; a victim access's *timing* leaks | ⚠️ **SURFACE only** | the leak is a **timing/contention** signal (a *different* access stalls), not a structural-touch event. Our watcher sees the spec load occupy the TBE/MSHR; it does not observe a victim access's latency. Detecting the leak needs a **timing** observation, which our event-based criterion isn't. |
| KV1 | InvisiSpec | **L1I-cache** spec fetch | secret-dependent control flow → different I-cache fills | **❌ NO** | it's an **instruction-fetch** channel, not a load transmitter. Our generator emits ld/br/other *data* transmitters, not "spec-execution-path → I-cache" gadgets; our watchers observe the **D-side** (L1D/L2/dir), not I-fetch. (InvisiSpec also *acknowledges* L1I is unprotected.) |
| UV6 | SpecLFB | **first spec load unprotected** | the 1st USL in the LSQ isn't delayed → installs a secret-dependent line | **✅ YES** (11/12) | — |
| UV3 | CleanupSpec | spec **store** not cleaned | a spec store's install isn't undone on squash | **❌ NO** | (a) it's a **store** (our transmitters are loads); (b) CleanupSpec *intentionally installs* speculatively and **undoes on squash** — the bug is **post-squash RESIDUE**, a *final-state* property, not an in-window touch. Our watcher would flag every spec install (all by-design). |
| UV4 | CleanupSpec | split requests not cleaned | cacheline-crossing access not undone | **❌ NO** | same: post-squash residue (final-state diff), + a split-request specific path. |
| UV5 | CleanupSpec | **too much cleaning** | cleanup wrongly evicts a *non-spec* line | **❌ NO** | same: the leak is a difference in the **final** cache state (a non-spec line gone), not an in-window touch. |
| unXpec | CleanupSpec | known cleanup vuln | leftover spec-installed addresses | **❌ NO** | same final-state class. |
| KV3 | STT | spec **store → D-TLB** | a tainted spec store installs a D-TLB entry | **❌ NO** | needs (a) **store-address** transmitters (we generate load/branch), (b) **D-TLB** observation (not in our watchers), (c) a **multi-page** sandbox (ours is ~1 page). |

**Score: 2/9 detected (UV1, UV6); 7/9 outside our formulation, for the reasons above.**

## 1. The deep reason 7/9 are out of scope (one sentence each)

Our formulation = *"a speculative LOAD performs a forbidden TOUCH on a cache structure, IN the
speculative window, detected from a single run (no relational comparison)."* The 7 misses each
break one axis of that:

- **Transmitter type.** UV3 and KV3 are **stores**; KV1 is an **instruction fetch**. We generate
  load transmitters. (Fixable in the Alloy model + concretization — see §5.)
- **Observed structure.** KV1 = **L1I**, KV3 = **D-TLB**. Our watchers parse L1D/L2/dir
  (`ProtocolTrace`). (Fixable: add an I-cache / TLB watcher — needs the right debug flag or a
  rebuild-with-DPRINTF.)
- **Channel kind.** UV2 = a **timing/contention** leak (a victim access slows because the MSHR is
  occupied). Our criterion flags a *structural touch*, not a *timing difference*. (This one is the
  least natural fit — it's intrinsically a 2-access timing relation.)
- **In-window vs final-state.** CleanupSpec UV3/4/5/unXpec: the in-window install is **intended**;
  the bug is the **failed undo** = **post-squash residue**. That is inherently a **final-cache-state
  differential** — which, per your rule, is *confirmation*, not detection. So our detect-tool
  (single-run, in-window forbidden touch) **structurally cannot** be the primary detector for an
  **undo-based** defense; CleanupSpec needs a final-state observer (the AMuLeT method).

## 2. What we DID detect (empirical)

### UV1 — InvisiSpec spec-load L1 eviction ✅ (build `amulet-gem5-InvisiSpec_AE-v1.1`, `--ruby`)
Watcher `STAGE3_gem5/check_ld_invisispec_compound.py`. **29/30 STT_6 + 10/14 STT-interleave →
`touched_forbidden:l1_eviction`** on a single run of the default (unpatched) build. Mechanism: the
spec load misses (`SpecLoad NP>IX`, allocates a TBE) and at the *same tick* an `L1_Replacement`
evicts a present victim, while its guarding branch is unresolved and ~2.5M ticks before the load's
own squash. Confirmation (relational, not detection): `--apply-spec-eviction-patch` → **0/30**. Full
write-up: `INVISISPEC_UV1_CONFIRMED.md`.

### UV6 — SpecLFB first-spec-load unprotected ✅ (build `amulet-gem5-SpecLFB_AE-v1.1`, classic)
Watcher `STAGE3_gem5/check_ld_speclfb.py`. **11/12 → `cache_install_in_window`**: the load SpecLFB
left unprotected (`isUnsafe=0`) misses and **installs** a line in the speculative window. (Hits the
L1 *install*, the cache-state change; a protected load is LFB-held → no install.)

### UV2 surface — InvisiSpec MSHR/TBE ⚠️ (same build)
The watcher reports `spec_miss_tbe_only` / `needs_pressure.tbe_mshr_alloc=True`: every spec miss
occupies an MSHR/TBE, and `--L1_TBEs` defaults to **2** (already AMuLeT's contention config). This is
the *surface* of UV2; the *leak* (a victim access's stall) is a timing relation we don't observe (§1).

## 3. Observation points chosen per defense, and WHY

| Defense | Build | Memory model | Observation flag(s) | Leak signal (watcher) | Why this point |
|---|---|---|---|---|---|
| **InvisiSpec** | `…InvisiSpec_AE-v1.1` build/X86_MESI_Two_Level | **Ruby MESI** (`--ruby`) | `ProtocolTrace` (L1/L2/dir transitions) + `LSQUnit`+`Squashed` (window, load identity) | `L1_Replacement` coincident with the xmit `SpecLoad`, in the spec window | InvisiSpec's defense lives in the **Ruby `.sm`**; `ProtocolTrace` is the one place the per-line L1/L2/dir state changes (incl. evictions) are visible. The eviction is a *pure side-effect* (the load allocates no block), so it's only catchable **at the event**, never at the load's output. |
| **SpecLFB** | `…SpecLFB_AE-v1.1` build/X86 | classic cache | `Cache` (install/evict) + `Speclfb` (USL isUnsafe class) + `LSQUnit` | L1 **install** (`cache_fill_tick`, a miss) in the spec window, on an `isUnsafe=0` USL | SpecLFB is a **classic-cache** build; the `Cache` flag shows the real L1 fill/install (the cache-state change); the `Speclfb` flag gives the `isUnsafe` classification that distinguishes the UV6 unprotected load from an LFB-held one. |
| **CleanupSpec** | `…CleanupSpec_AE-v1.1` build/X86_MESI_Two_Level | **Ruby MESI** (`--ruby`) | would need **final L1/L2 tag snapshot** (post-squash) vs baseline | un-restored **residue** after cleanup | the bug is *failed undo*, a final-state property → the observation point is the **end-of-test cache state**, not an in-window event (see §1, §5). NOT yet built. |
| **STT** | `…STT_AE-v1.1` build/X86 | classic | would need **D-TLB** state + **store-address** transmitter | a tainted spec **store** installs a D-TLB entry | KV3's channel is the TLB and the transmitter is a store — neither is in our current watchers/model (see §5). NOT yet built. |

## 4. ⚠️ CACHE-SIZE CONSTRAINT — flag for the paper (Anna, write a section on this)

To make UV1/UV6 *fire* in our small litmus tests, I shrank the **L1D to `--l1d_size=1kB
--l1d_assoc=2`** (and `--L1_TBEs=2`, already the default). **This is a deliberate config change and
is flagged here.** Rationale (this is the paper-section material):
- Our litmus tests touch a tiny working set; with a default 64kB/8-way L1D, the spec load's
  (const-addr, prologue-pre-warmed) line **hits** → it touches nothing → no eviction/install to see.
- A small L1D makes the working set **overflow**, so the spec load **misses on a full set** and
  exercises the eviction/install — the exact structural bug.
- **This is AMuLeT's own method** (they used 2-way L1D / 2 MSHRs to amplify). The bug is
  **structural** (it occurs in a full cache whenever the working set exceeds L1); the small cache
  just lets a *small* program reach the full-set condition. So it is **amplification of a real bug,
  not tuning to manufacture one.** `--l1d_assoc=1` aborts in Ruby; 2-way is stable.
- **Paper angle:** "litmus-test microarchitectural defense testing needs a cache-pressure knob —
  small structures (few ways / few MSHRs) are required so a short test reaches the contention
  conditions under which conflict/eviction/interference bugs manifest." This is a methodology
  contribution worth its own paragraph (relate to AMuLeT §4.5.1 amplification).

## 5. What the pipeline must change to GENERATE the bugs that hit (per bug)

All generation should go through the usual `pipeline.py`/`testsetgen.py` structure (in a NEW testset
folder, not clobbering existing ones). What each currently-undetected bug needs:

- **UV1 / UV6 (detected):** no *generation* change needed — existing STT/interleave ld tests work.
  Only the **run config** needs: the right build, `--ruby` (InvisiSpec), small L1D, `ProtocolTrace`.
  To make the eviction *secret-dependent* (an exploitable, not just structural, hit): the load's
  index must be a non-zero secret (today it's 0 from the zero-init prologue) — a **concretization**
  change (seed a non-zero value into the speculatively-loaded location), same gap as SpecLFB UV6's
  victim-address.
- **UV2 (MSHR interference):** need a test with **two** speculative loads contending for the few
  MSHRs, plus a watcher that measures the **second** load's stall/latency (a timing observation).
  Generation: a 2-load gadget (the interleave model can express it); instrumentation: a
  per-access latency/MSHR-occupancy watcher (new; possibly a DPRINTF rebuild).
- **KV1 (I-cache):** need tests whose **speculative control flow** differs by input (so different
  instructions are fetched), and an **L1I** watcher. Generation: a control-flow-divergent gadget;
  instrumentation: an I-cache-fill watcher (`ProtocolTrace` already covers L1I lines — could reuse).
- **CleanupSpec UV3/4/5:** need (a) **store** transmitters (UV3) and **split**/reordered-load gadgets
  (UV4/UV5) in the model, and (b) a **final-cache-state observer** (snapshot L1/L2 tags at test end,
  compare to a no-speculation baseline) — this is a *relational/state-diff* checker, distinct from
  our in-window watcher. Generation: extend the Alloy model with store/split transmitters; pipeline:
  add a post-squash cache-snapshot stage.
- **KV3 (STT store→TLB):** need (a) a **store-address** transmitter in the Alloy model
  (`leakage_function` currently doesn't cover store-addr/Otherxs), (b) a **multi-page** sandbox so the
  TLB install is distinguishable, (c) a **D-TLB** watcher. Generation: model + concretization changes;
  instrumentation: a TLB-install watcher (debug flag or rebuild).

## 6. Strategies used (the toolbox, for reproducibility)

1. **Right build + memory model per defense** (§3) — InvisiSpec/CleanupSpec need `--ruby` (defense is
   in the Ruby `.sm`; classic caches run it INACTIVE — the earlier `cache.cc:192` aborts).
2. **`ProtocolTrace` (Ruby) / `Cache` (classic)** as the observation backbone — the watcher reads the
   controller-transition / cache-event stream and flags the forbidden structural touch **at the
   source event**, upstream of any output and with **no relational comparison** (detection).
3. **Speculative gate = the STRICT model lc/fnc window** `lc_retire < t < fnc_retire AND branches
   unresolved`. ⚠️ **CORRECTION:** I initially WIDENED the upper bound (`before_fnc OR
   branches_unresolved`) to make the slow eviction "fit" — that was **cheating the gate** (it is not
   tunable) and is **reverted**. With the strict gate, UV1 is **0/12** *as currently configured*,
   because `fnc` COMMITS EARLY (ann: lc=pc0, fnc=pc1, guarding branch=pc2 *after* fnc), closing the
   window (~fnc_retire 3.18M) before the slow Ruby Spec-GetS/eviction (~3.19M). **The real fix is the
   `fnc-commit-stall` hook** — the standard SimSpect window-widener that holds the first-noncommitted
   insn at the ROB head (recon/STT run it at `fnc_commit_stall_cycles=150`). The amulet builds were
   never given that hook (only BTB-force + resolve-stall were ported), so I ran InvisiSpec with `fnc=0`
   → window ~0. **Porting the hook (rebuild) → fnc held → the eviction lands in the STRICT window**
   (fnc_retire≈3.18M+75k=3.26M > 3.19M). This is the legitimate tool, NOT a gate hack. The watcher also
   reports a lc/fnc-OFF diagnostic (branch-resolution only) purely to MEASURE the gap, never to detect.
   **VERIFIED (2026-06-08):** ported the fnc-commit-stall hook to the InvisiSpec build + rebuilt;
   with `fnc_commit_stall_cycles=150` the STRICT lc/fnc gate gives **11/12** (== lc/fnc-OFF) — e.g.
   inst-000066 fnc_retire moved 3184000→**3259000**, so the eviction at 3194000 is now INSIDE
   lc(3175000)<t<fnc(3259000). The hook widened the physical window; the gate was untouched.
4. **Cache-pressure amplification** (§4) — small L1D so litmus tests reach the full-set condition.
5. **Relational testing ONLY to confirm** — `--apply-spec-eviction-patch` ON/OFF confirmed UV1
   (0 vs 29); it was *not* used to detect.

## 7. Check scripts (one per defense)
- **InvisiSpec:** `STAGE3_gem5/check_ld_invisispec_compound.py` (+ launcher
  `results/STT_6_invisispec_compound/run_invisispec_compound.py`).
- **SpecLFB:** `STAGE3_gem5/check_ld_speclfb.py` (+ `results/STT_6_speclfb/run_speclfb.py`).
- **CleanupSpec / STT:** not yet — need the final-state / TLB / store-transmitter additions in §5.
- Shared parse helpers in `STAGE3_gem5/gem5_common.py` (additive; build-specific regexes no-op
  elsewhere). `STAGE3_gem5/check_ld.py` (the original) is **unchanged**.

## 8. What I did NOT change
No defense logic; no `.sm`/C++ edits; **no gem5 rebuild** this session. Only config + debug flags +
the build's own `--apply-spec-eviction-patch` knob. The two checker edits this session were the
**lc/fnc-window fix** (kept lc/fnc, extended the upper bound) applied to `check_ld_invisispec_compound.py`
and `check_ld_speclfb.py`, plus the parallel lc/fnc-OFF verdict.
