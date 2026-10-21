# Compound load-transmission criterion: every structure a speculative load must not touch

*2026-06-03 · session `5:invisispec`. Design/exploration doc — enumerates, per
defense build, every microarchitectural structure that constitutes the load
"transmitter mechanism," the exact gem5 hook site, and the trace signal to detect
a speculative-load touch. Goal: replace the narrow "cache-line install" signal
with a **compound** criterion that flags a USL perturbing ANY shared µarch state
while unsafe. Companion to `docs/AMULET_VS_SIMSPECT_SCOPE.md`.*

## 1. Principle

A load is a transmitter not only via the cache line it installs, but via **every
observable microarchitectural state change its access causes**. A
"make-speculative-loads-invisible" defense (InvisiSpec, SpecLFB) is supposed to
keep an unsafe speculative load (USL) from perturbing ANY of these until it is
safe; an undo defense (CleanupSpec) is supposed to perfectly restore them on
squash. So the compound criterion is:

> While the transmitter load is unsafe/speculative (in the window
> `lc_retire < t < fnc_retire`, guarding branches unresolved), did it cause an
> observable change to ANY structure on the transmission surface below — outside
> the one buffer the defense designates as its safe holding place?

Each structure maps to a known AMuLeT bug class, which is why a compound criterion
(not just cache-install) is what catches them:

| Structure on the transmission surface | AMuLeT bug |
|---|---|
| L1D **tag array** (line installed) | core Spectre-v1 (SpecLFB UV6) |
| L1D **replacement/LRU** state (updated even on a *hit*) | replacement-state channel |
| L1D **eviction** of a victim line | **InvisiSpec UV1** (spec-load eviction) |
| **MSHR / TBE** occupancy (allocated on a miss) | **InvisiSpec UV2** (single-thread interference) |
| L2 tag / LRU / **eviction** | (same classes, one level down) |
| **Directory / coherence** sharer/owner state | cross-core coherence channel |
| **D-TLB** entry installed | **STT KV3** (tainted store → TLB) |
| **L1I** state (spec instruction fetch) | **InvisiSpec KV1** |
| Prefetcher state / triggered prefetch | spec-prefetch channel |
| Bus / port / queue **contention** (timing) | interference (needs pressure) |

The "safe holding place" the defense is allowed to use (and which is NOT a leak):
- **InvisiSpec:** the Speculative Buffer (SB) — in the LSQ, `specBuf` (lsq_unit).
- **SpecLFB:** the Line-Fill-Buffer (LFB) — `isLFB_RF()` requests, `LFBLatency`.
- **CleanupSpec:** the L1/L2 itself, *provided* the install+any eviction is fully
  undone on squash (the cleanup table + rollback). For CleanupSpec the criterion
  flips: a touch is fine; **un-restored residue after squash** is the leak.

## ⚠ 2.0 PREREQUISITE: InvisiSpec/CleanupSpec MUST run with `--ruby` (found 2026-06-06)

InvisiSpec's and CleanupSpec's defenses live entirely in the **Ruby MESI protocol**
(`.sm` files: Spec-GetS, the SB↔Ruby fill, the `apply_spec_eviction_patch`,
CleanupSpec's CleanupTable/rollback). The SimSpect pipeline (`gem5_common.run_gem5`)
appends `--caches` but **not `--ruby`**, so every prior InvisiSpec/CleanupSpec run
used the **CLASSIC cache model** (`cache.cc`) — the Ruby defense was **inactive**
(the `cache.cc:192 hasRespData` aborts were the classic cache; `ProtocolTrace` is
empty without `--ruby`). Only the **CPU/LSQ-side** logic (readSpec, SB, isUnsafe,
expose) ran; the cache-side invisibility did not. **Verified:** adding `--ruby`
lights up the Ruby protocol (`SpecLoad M>M …` etc., 1476 ProtocolTrace lines);
`--caches --ruby` coexist fine (se.py's `if options.ruby:` takes Ruby).
**Implication:** the earlier InvisiSpec results (0 leaks, expose-in-window) were on
the wrong memory model and don't test InvisiSpec's real cache defense. SpecLFB is
unaffected (it's a classic-cache `build/X86`, no Ruby). The compound checker and its
launcher force `--ruby`.

**Status:** `STAGE3_gem5/check_ld_invisispec_compound.py` + launcher
`results/STT_6_invisispec_compound/run_invisispec_compound.py` are BUILT and
validated (real ProtocolTrace parse; synthetic miss+evict → `l1_eviction`+
`tbe_mshr_alloc`; live `--ruby` run = 0 forbidden touches, `invisible_spec_hit` on
the const-hit corpus, no classic aborts). `check_ld.py` untouched.

## 2. Observation backbone

- **Ruby builds (InvisiSpec, CleanupSpec, both `X86_MESI_Two_Level`):**
  `--debug-flags=ProtocolTrace` (confirmed compiled in both) emits one line per
  controller transition: `<tick> <machine> <node> <addr> <curState>><nextState> <event> …`
  (`AbstractController` / `Sequencer.cc:581,834`). This gives the **full per-line,
  per-controller footprint** of the spec access (L1, L2, dir): every event
  (`SpecLoad`, `L1_Replacement`, `L2_Replacement`, `SpecFetch`, TBE alloc) on the
  spec line AND on any victim line, with ticks. Add `RubySlicc` for the action-level
  DPRINTFs (e.g. the `DataBlk` reads). Keep `LSQUnit`+`O3PipeView` for the window
  bounds and the load's sn/PC.
- **Classic build (SpecLFB, `X86`):** `--debug-flags=Cache` emits per-addr
  `access for <Cmd> [a:b] hit/miss`, `Block addr 0x.. moving from .. to ..`
  (install), `evictBlock`; `Speclfb` for the USL classification; the LSQUnit
  `Doing memory access`/`Inserting`/`squashed` for the load lifecycle. MSHR
  allocation is in `base.cc:allocateMissBuffer`.

Attribution: the spec load's **own line** address is in the LSQUnit
"Attempting load request … Paddr" line; its **eviction victim** is the line that
`L1_Replacement`/`evictBlock` fires on in the same controller cycle as the
`SpecLoad`/`unsafeReq` (Ruby: same tick + the victim = `cacheProbe(spec_line)`).

----

## 3. InvisiSpec (Ruby MESI_Two_Level) — hook table

Build: `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1`. The spec read is
`RubyRequestType:SPEC_LD` → `GETSPEC` (Spec-GetS); data returns to the SB in the
LSQ, NOT to L1. Surface is exercised on a **miss** (a spec *hit* is clean — see LRU
row).

| Structure | Touched by USL? | Hook site | Trace signal |
|---|---|---|---|
| L1D tag (install) | **No** by design — miss path uses `iw_allocateTBEWithoutCacheEntry` (no block) | `MESI_Two_Level-L1cache.sm:1229-1233` (`{NP,I},SpecLoad→IX`) | ProtocolTrace: `SpecLoad` with NO `oo_allocateL1DCacheBlock` |
| L1D LRU/MRU | **No** — `h_spec_load_hit` omits `setMRU` (normal `h_load_hit` has `L1Dcache.setMRU`) | `L1cache.sm` `h_spec_load_hit` (≈998) vs `h_load_hit:994` | absence of `setMRU` on a `SpecLoad` hit |
| **L1D eviction** | **YES iff patch OFF** (UV1) | `L1cache.sm:514` (`cacheAvail \|\| (SPEC_LD && apply_spec_eviction_patch)`) → else `L1_Replacement` | ProtocolTrace: an `L1_Replacement` on victim coincident with a `SpecLoad` |
| **L1 TBE/MSHR** | **YES, always** (inherent) | `L1cache.sm:1230` `iw_allocateTBEWithoutCacheEntry` | ProtocolTrace: `SpecLoad→IX` (TBE allocated); occupancy = UV2 surface |
| L2 tag / **eviction** | YES iff patch OFF | `L2cache.sm:386` (same patch on `GETSPEC`) → `L2_Replacement` | ProtocolTrace (L2): `L1_GETSPEC` coincident `L2_Replacement` |
| L2 spec-requestor record | YES (transient) | `L2cache.sm:144` `L1_GetSPEC_IDs` in the L2 TBE | ProtocolTrace (L2) |
| Directory sharer/owner | **No** — transient `I→II→I`, data sent w/o adding sharer | `dir.sm:494` `transition(I,SpecFetch,II)`, `:500,518` | ProtocolTrace (dir): `SpecFetch`, returns to `I`. ⚠ authors' `// Is it secure?` (`dir.sm:499`) — transient `II` is observable to a racing request |
| D-TLB | TODO — CPU-side translation before Ruby | lsq read path / TLB walker | (not yet mapped; see §6) |
| L1I | KV1 — acknowledged unprotected | I-cache controller path | ProtocolTrace (L1I) |

**Toggle:** `apply_spec_eviction_patch := "True"` (default = patched) in
`L1cache.sm:40` / `L2cache.sm:34`, wired from `--apply_spec_eviction_patch`
(`configs/ruby/MESI_Two_Level.py:101,153`). Set **False** to reproduce UV1.

----

## 4. SpecLFB (classic cache, newer gem5) — hook table

Build: `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1`. USL is delayed/LFB-routed via
`isUnsafe` (`isCUSL/isMUSL && isReallyUnsafe`); the fill rides the LFB
(`isLFB_RF()`, `LFBLatency`). Safe holding place = LFB.

| Structure | Touched by USL? | Hook site | Trace signal |
|---|---|---|---|
| L1D tag (install) | the leak when unprotected (UV6) | `cache.cc` `handleFill`→`base.cc allocateBlock`/`tags->insertBlock` | `Cache`: `Block addr 0x.. moving from  to …` (install) |
| L1D LRU | on access/hit | tags `accessBlock`/`moveToHead` | `Cache`: `access … hit` |
| **L1D eviction** | on install to full set | `cache.cc:181,999` `evictBlock`; `base.cc allocateBlock` victim | `Cache`: `evictBlock` / `Block … being updated` on victim |
| **MSHR** | miss allocates | `cache.cc:353` / `base.cc:270` `allocateMissBuffer` | MSHR alloc DPRINTF; occupancy |
| Write buffer | store path | `cache.cc:222,229,344` `allocateWriteBuffer` | — |
| **LFB (safe place)** | the legit hold | `cache.cc:806-892` `isLFB_RF()` ⇒ `LFBLatency`; `req->setLFB_RF` | `Speclfb`: refill/`isLFB_RF` |
| USL classification | gate | `lsq_unit.cc:228` (`simulateScheme=="Speclfb"`), `:478/536/621` `isSpeclfbStalled`; `base/unsafe_insqueue` ROB-mask | `Speclfb`: `Initiating Translation … isCUSL/isUnsafe/isreallyUnsafe` |
| D-TLB | translation | `SingleDataRequest` translate path | `Speclfb`/`Squashed`: `Attempting load request … Paddr/Vaddr` |

**Caveat to verify at instrumentation time:** whether `isLFB_RF` only changes
*latency* (cache.cc:806-892 only touches `completion_time`) or also *withholds the
L1 install*. If the install still happens (just slower), an unprotected-vs-protected
load differ only in latency — re-confirm `handleFill`/`insertBlock` is gated on
unsafe. The compound checker should key on the **`Block … moving to`** install line
(real tag change), gated by `isUnsafe`.

----

## 5. CleanupSpec (Ruby MESI_Two_Level) — hook table (criterion FLIPS)

Build: `/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1`. CleanupSpec **allows** spec
installs/evictions and **undoes** them on squash via a CleanupTable + rollback. So
a touch is expected; the **leak is un-restored residue after the cleanup**. The
compound criterion here = "after squash + cleanup completes, does the final L1/L2
state differ from the pre-speculation baseline?"

| Structure / event | Hook site | Trace signal |
|---|---|---|
| Spec install (allowed) | `L1cache.sm` `SpecLoad` install path; `L1_Replacement_OnInstall:115` | ProtocolTrace |
| **Evicted victim recorded for rollback** | `inst->EvictedLineAddrL1` (lsq); `L1cache.sm` Cleanup states `:140-164` | LSQUnit `***LoadReturned… EvictedLineAddrL1:%#x` |
| Cleanup metadata (L1Hit/L2Hit/L2Miss) | `Sequencer.cc:479,569,627,680` `setL1Hit`; `lsq_unit_impl.hh:142-156` `setL1HitCC` | LSQUnit `L1-Hit/L2-Hit/L2-Miss` fields |
| **UV3 gap: store cleanup metadata missing** | `Sequencer.cc writeCallback:443` lacks the `setL1Hit`/cleanup-meta the `readCallback:548` path sets | compare write vs read callback meta |
| Cleanup/rollback execution | `issueCleanupRequest`/`processCleanup` (`lsq_unit_impl.hh:118`); Cleanup transitions `Inv_CLEANUP/Rollback/InvL2_CLEANUP` | ProtocolTrace cleanup events |
| **Residue = the leak (UV3/4/5)** | final L1/L2 tags after `Done_CLEANUP` | ProtocolTrace end-state vs baseline; or a final-cache snapshot |

So CleanupSpec needs a **differential / final-state** observer (like AMuLeT), not
just an in-window event — it's the post-squash residue that matters. UV4 (split
requests not cleaned) and UV5 (cleanup over-evicts a non-spec line) are both
final-state diffs.

----

## 6. Implementation plan for the compound checker

1. **parse extension (additive, per build, in `gem5_common.parse_lsq` or a sibling
   `parse_ruby`):** from `ProtocolTrace`/`Cache`, build per-line event lists keyed
   by tick: `{spec_load, l1_install, l1_evict(victim), l2_evict, tbe_alloc,
   dir_specfetch, lru_update}`. Tie to the transmitter via the load's Paddr (own
   line) and the coincident victim line. All regexes build-specific ⇒ no-op on
   others (same discipline as `expose_tick`/`memaccess_tick`).
2. **compound checker `check_ld_compound.py`:** for the transmitter, in the spec
   window, emit a per-structure verdict vector + an overall `touched_forbidden`
   (any of: eviction, L1 install for an InvisiSpec USL, LRU on a USL hit, L2 evict,
   dir state change). Exclude the defense's safe place (SB/LFB). For CleanupSpec,
   switch to the residue diff.
3. **outcome taxonomy** (per structure) so a hit says *which* structure leaked —
   `evicted_victim_in_window`, `mshr_occupied_in_window`, `l1_installed_unprotected`,
   `lru_touched_on_spec_hit`, `l2_evicted`, `dir_state_changed`, `tlb_installed`,
   `clean_residue_after_squash`.
4. **contention vs presence:** MSHR/TBE occupancy and bus contention are *inherent*
   to any non-blocking spec load — they leak only under **pressure** (AMuLeT used
   2 MSHRs / 2-way L1D). Flag them but tag `needs_pressure`; optionally add a
   small-structure config (reduce MSHRs/ways) to make them fire, mirroring AMuLeT.
5. **window + taint gate stays:** a structure touch counts only if (a) in the spec
   window with guarding branches unresolved, and (b) — for a *demonstrable* leak vs
   a dataflow signal — the touched address/victim depends on the tainted operand
   (the dataflow signal from `SPECLFB_UV6_REVIEW.md`; const-vs-tainted is the
   data-taint axis, orthogonal to which-structure).

## 7. Open questions / things to verify before trusting it

- **InvisiSpec dir `// Is it secure?` (`dir.sm:499`):** the transient `II` state is
  observable to a racing request to the same line — a potential coherence/timing
  channel not covered by "sharer state unchanged." Worth a targeted probe.
- **SpecLFB LFB install-gating** (§4 caveat): confirm `handleFill` is actually
  withheld for `isUnsafe`, not just latency-delayed.
- **MSHR/TBE inherency:** decide whether occupancy itself is "a touch it shouldn't"
  or only contention-under-pressure (the honest framing for UV2).
- **D-TLB** for InvisiSpec loads: not yet mapped to a site; the STT KV3 bug is a
  *store*→TLB, but a spec *load* also walks/installs TLB entries — map the
  CPU-side translation install for completeness.
- **CleanupSpec** needs a final-state/differential observer; the in-window event
  stream alone won't show un-restored residue.

Pointers: InvisiSpec `MESI_Two_Level-L1cache.sm:514,1229,994`; `-L2cache.sm:386`;
`-dir.sm:494,499`. SpecLFB `cache.cc:806-892,999`, `base.cc:270`,
`base/unsafe_insqueue`. CleanupSpec `Sequencer.cc:443/548`, `lsq_unit_impl.hh:142`,
`L1cache.sm:140-164`. Memory: `project_invisispec`, `project_speclfb`,
`reference_gem5_build_hooks`.
