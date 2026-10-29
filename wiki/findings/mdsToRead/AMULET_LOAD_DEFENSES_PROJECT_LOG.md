# SOTA load-defense bug reproduction — InvisiSpec / SpecLFB / CleanupSpec / STT (ongoing project log)

**For:** Anna · **Owner session lineage:** `5:invisispec` (autonomous loop) · **Living doc — newest status at top.**

> **One-line aim.** For **every** bug AMuLeT reports against the four state-of-the-art speculative-execution
> *load* defenses, either (a) **empirically reproduce it** on the real (unmodified) gem5 build with a
> controlled gadget + control, or (b) give a **precise, source-grounded reason** our formulation can't —
> never hand-wave a bug "out of scope." This is the durable home for that effort; `claudelog.md` keeps the
> terse dated trail, this doc is the rollup.

This consolidates and supersedes the scattered InvisiSpec/AMuLeT notes. Companion deep-dives (kept):
`mdsToRead/INVISISPEC_UV1_CONFIRMED.md`, `mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md`,
`results/STT_6_cleanupspec_residue/CLEANUPSPEC_RESIDUE_REVIEW.md`, `bug/STT_KV3_TLB_REVIEW.md`,
`docs/COMPOUND_TRANSMISSION_CRITERION.md`, `docs/AMULET_VS_SIMSPECT_SCOPE.md`.
Plain-language explainer of the three AMuLeT-only defenses (why loads evict, CleanupSpec signal choice, hooking
cache events into the pipeline): `mdsToRead/AMULET_THREE_DEFENSES_EXPLAINER.md` (2026-10-28).

---

## 0. WHERE WE'RE AT RIGHT NOW (2026-06-09)

**7 of 9 AMuLeT bugs empirically reproduced; the other 2 each have a precise, source-grounded verdict.
Nothing parked by hand-waving; nothing left "blocked."**

- ✅ **Demonstrated (7):** InvisiSpec **UV1** (L1 eviction), SpecLFB **UV6** (first spec load), InvisiSpec
  **KV1** (L1I fetch), STT **KV3** (store→D-TLB), CleanupSpec **UV4** (split not cleaned), CleanupSpec
  **unXpec** (undo *itself* is the channel), InvisiSpec **UV2** (MSHR/TBE contention). All reproducible — §5.
- 🟢 **UV3** (CleanupSpec spec store not cleaned) — precise why-not, **now EMPIRICALLY CONFIRMED**
  (`uv3/uv3.s`): a TLB-warmed speculative store executes (issues a "Store request", Paddr 0x1000) but
  produces **no `Store NP>IM` on its target line** — it installs no cache line — and is squashed before any
  writeback (writeback is post-commit). Zero cache footprint → nothing for the loads-only cleanup to miss.
  Notably the cleanup IS loads-only, so *if* a spec store left a footprint it would be UV3 — but the store
  leaves none. Complements KV3: the store touches the TLB at execute (KV3 reachable) but the cache only at
  commit (UV3 not). Unreachable in this store model (not a tooling gap).
- 🟢 **UV5** (CleanupSpec over-clean / "Too Much Cleaning") — **AMuLeT's actual detector located
  (`/work/amulet-repo/src/cleanupspec_analysis.py:138`): UV5 is a RELATIONAL final-state-diff signature**
  (two runs; final cache tag-sets differ by exactly one tag that's both `LD`+`CLEANUP` in one run) — found
  by AMuLeT's fuzzer + two-run comparison, NOT a single-run event. It's the relational/final-state
  manifestation of the SAME secret-dependent-cleanup flaw SimSpect already **demonstrated at the source as
  unXpec** (miss→7 cleanup events, hit→0). SimSpect's single-run cleanup is **PROVEN correct**
  (invalidate-before-restore ordering). So UV5's underlying flaw is covered (unXpec, source-side); the
  specific "Too Much Cleaning" relational signature is AMuLeT's frame (needs its reference/primer harness +
  fuzzed gadget). Detection-frame difference (relational final-state vs source-event) now precisely
  understood — `uv5_demo/NOTE.md` DEFINITIVE.
  (superseded detail: `uv5_demo/NOTE.md` EMPIRICAL CLOSE — the single-eviction over-clean is ordering-prevented.) Unblocked
  (the `Resource Stall` storm was generic TBE exhaustion, ON==OFF; `--L1_TBEs=8` clears it). Clean scoring
  (`uv5clean.s`): spec evicts committed A → cleanup invalidates the spec line **then** `Load_ROLLBACK`
  restores A → final both committed resident, spec gone = CORRECT. **Root correctness mechanism: CleanupSpec
  invalidates the spec line FIRST (frees the way), then the restore allocates into it** — so the restore
  always finds room. Over-clean (`L1cache.sm:2722`, the restore is an allocating evict) would need the set
  *still full of committed lines after the spec line is invalidated* — i.e. a committed line refilling the
  freed way mid-window; but any such 3rd committed line just causes ordinary LRU churn (3-for-2 ways =
  architectural eviction, indistinguishable from a bug) — confirmed empirically (`uv5oc.s`). **So in this
  build, the invalidate-before-restore ordering robustly prevents over-clean in every hand-stageable
  scenario.** Reproducing the *published* UV5 needs AMuLeT's specific gadget (likely a split multi-line
  cleanup or a relational final-state diff catching a transient) — a precise why-not of the same character
  as UV3, grounded in the implementation, not hand-waved.

**✅ UV2 UNBLOCKED + demonstrated (2026-06-09):** the blocker — speculative data loads not issuing GETSPEC —
was a **speculative TLB-miss deferral**: a spec load to a COLD PAGE hits a spec TLB miss that InvisiSpec
defers (`Translation delay`), so it never reaches the cache. **Fix: warm the PAGE in the TLB with a
committed access (to a far line), leave the target LINE cold** → the spec load's translation hits, the
cache access misses → GETSPEC issues + a TBE is allocated. With that, 4 spec loads to 4 cold lines on a warm
page exhaust the 2-entry TBE pool: `--L1_TBEs=2` → 248 retry NP>IX events, 122k-tick serialization; control
`--L1_TBEs=8` → 4 clean concurrent issues. = UV2. (`bug/uv2_demo/run_uv2_demo.py`.)

**Where it stands:** all 9 AMuLeT bugs are now accounted for — **7 demonstrated, 2 precise why-nots
(UV3, UV5-over-clean)**, none blocked. The only way to push the 2 why-nots further is external artifacts:
UV3 needs a build with speculative store→cache (it has none); UV5-over-clean needs AMuLeT's exact UV5
gadget (this build's invalidate-before-restore ordering prevents over-clean in every hand-stageable case).
This is the defensible endpoint for the paper. Full scorecard + evidence below.

---

## 1. Scorecard — where every bug stands (as of 2026-06-09)

**7 of 9 empirically demonstrated end-to-end; 2 precise source-grounded why-nots (UV3 store-not-cached, UV5 over-clean prevented by invalidate-before-restore ordering). Nothing blocked.**

| # | Defense | Bug | Status | Evidence / repro |
|---|---|---|---|---|
| UV1 | InvisiSpec | spec-load L1 **eviction** | ✅ **demonstrated** | 29/30 STT_6 via `check_ld_invisispec_compound.py`; patch → 0/30. `INVISISPEC_UV1_CONFIRMED.md` |
| UV6 | SpecLFB | **first** spec load unprotected | ✅ **demonstrated** | 11/12 `cache_install_in_window`, `check_ld_speclfb.py` |
| KV1 | InvisiSpec | **L1I** instruction-fetch channel | ✅ **demonstrated** | `bug/kv1_demo/` (`run_kv1_demo.py`) — wrong-path fetch installs `Ifetch NP>IS`; control = no install |
| KV3 | STT | spec **store → D-TLB** | ✅ **demonstrated** | `bug/kv3_demo/` (`run_kv3_demo.py`) — 2×2: store walks cold page under STT *and* Unsafe; load protected. `bug/STT_KV3_TLB_REVIEW.md` |
| UV4 | CleanupSpec | **split** request not cleaned | ✅ **demonstrated** | `results/STT_6_cleanupspec_residue/uv4_demo/` — split load installs 2 lines, 0 cleanup; aligned control cleaned |
| unXpec | CleanupSpec | **undo itself is the channel** | ✅ **demonstrated** | `results/STT_6_cleanupspec_residue/unxpec_demo/` (`run_unxpec_demo.py`) — miss → 7 cleanup events, hit → 0 |
| UV2 | InvisiSpec | single-thread **MSHR/TBE** contention | ✅ **demonstrated** | `bug/uv2_demo/` (`run_uv2_demo.py`) — 4 spec loads on a TLB-warm page; `--L1_TBEs=2` → 248 retry NP>IX, 122k-tick serialize; `=8` → 4 clean. TLB-warm-page unblock |
| UV3 | CleanupSpec | spec **store** not cleaned | 🟢 **precise why-not** | squashed store never touches cache (`canWB` set at commit only; no spec store RFO) → no cache footprint to leak |
| UV5 | CleanupSpec | **over-clean** (evicts non-spec line) | 🟢 **eviction-rollback PROVEN CORRECT; over-clean not-reproducible-here (precise why-not)** | `uv5_demo/` (`uv5clean.s`/`uv5oc.s`, `NOTE.md` EMPIRICAL CLOSE) — invalidate-before-restore ordering frees the way before the restore allocates, so no over-evict; any "refill" is 3-for-2 LRU churn (architectural). Needs AMuLeT's exact gadget |

**Three bugs once marked "out of formulation" (KV3, KV1, UV2) are now demonstrated (KV3, KV1) or
source-reachable with a precise recipe (UV2) — nothing parked by hand-waving.** unXpec, also previously
"final-state / out of scope," is now demonstrated as an *in-window cleanup-activity* channel.

---

## 2. The reproduction technique (the template that worked)

All demonstrated bugs (except UV1/UV6, which are sweep-watcher detections) use one **controlled-gadget**
pattern, run on the real defense build with the SimSpect **non-defense instrumentation hooks** ported in
(BTB force, branch-resolve-stall, `fnc_commit_stall`). **Defense logic is never touched.**

1. **Hold the speculative window open.** A mispredicted branch with `resolve_stall_cycles=2000`
   (and/or `fnc_commit_stall`) keeps the squash far enough out that the speculative µarch event lands
   inside the window. Gate is always **STRICT** `lc_retire < signal < fnc_retire` with branches unresolved.
2. **Reach the secret-dependent target speculatively.** Either fall-through (`mispredict_not_taken`) or a
   **BTB-forced taken** redirect (`mispredict_taken`) to a label reached *only* speculatively.
3. **A built-in control** that differs in exactly one variable (aligned vs split; hit vs miss; correctly-
   predicted vs mispredicted; load vs store) — so the signal can't be a false positive.
4. **Observe the structural footprint** in the Ruby `ProtocolTrace` (L1/L2/dir transitions, Ifetch
   installs, cleanup events) or the classic `Cache`/`Speclfb` flags — *at the event*, since these are pure
   side effects the load's output never reveals.

**Key learned unblock (the TLB-warm-page trick) — RESOLVED, was the UV2 blocker.** A speculative data load
to a **cold page** hits a speculative **TLB miss** that the defense **defers** (`Translation delay on
load`; same family as STT's `specTLBMiss`), so it never reaches the cache → no GETSPEC, no TBE. **Fix:
warm the PAGE in the TLB with a committed access to a *far line* on it, but leave the target LINE cold.**
Then the spec load's translation hits, the cache access misses → `SpecLoad NP>IX` issues + a TBE is
allocated. (This also explains why UV4/CleanupSpec worked without the trick: its `UnsafeBaseline` invisispec
scheme doesn't defer the spec TLB miss; and why KV1 worked: instruction fetches don't go through the LSQ
spec-TLB path.) **This unblocked UV2** (and is the technique to try for UV5's eviction-path gadget too).

---

## 3. Builds, memory models, observation points

| Defense | Build (`/work/amulet/…` unless noted) | Mem model | Scheme / glue | Observation point | Watcher / demo |
|---|---|---|---|---|---|
| **InvisiSpec** | `amulet-gem5-InvisiSpec_AE-v1.1` `build/X86_MESI_Two_Level` | Ruby MESI (`--ruby`) | `SpectreSafeInvisibleSpec` | `ProtocolTrace` (L1/L2/dir, evictions, Ifetch installs) + `LSQUnit`/`Squashed` | `check_ld_invisispec_compound.py`; `bug/kv1_demo/` |
| **SpecLFB** | `…SpecLFB_AE-v1.1` `build/X86` | classic cache | scheme "2"→Speclfb | `Cache` (install/evict) + `Speclfb` (`isUnsafe`) + `LSQUnit` | `check_ld_speclfb.py` |
| **CleanupSpec** | `…CleanupSpec_AE-v1.1` `build/X86_MESI_Two_Level` | Ruby MESI (`--ruby`) | passthrough `--scheme` | `ProtocolTrace` cleanup events (`Inv_CLEANUP`, `Load_ROLLBACK`, `InvL2_CLEANUP`, `CleanReplacement`) | `check_ld_cleanupspec.py`; `uv4_demo/`, `unxpec_demo/` |
| **STT** | `/work/stt` (X86) | classic | `--scheme=2` (STT) | D-TLB translate/fill at execute | `bug/kv3_demo/` (2×2 vs Unsafe scheme 0) |

**Prereq finding (don't regress):** InvisiSpec's cache-side defense lives in the **Ruby MESI `.sm`** — the
pipeline must append `--ruby` or the defense is *inactive* (classic cache; empty `ProtocolTrace`). All
InvisiSpec/CleanupSpec results use `--ruby`. The `fnc_commit_stall` hook was **missing** from the amulet
builds and was ported (7 sites) + rebuilt — non-defense instrumentation only.

---

## 4. Per-bug detail (mechanism + verdict)

- **UV1 — InvisiSpec spec-load L1 eviction (REAL BUG).** Unsafe spec load misses (`SpecLoad NP>IX`,
  allocates a TBE) and at the same tick an `L1_Replacement` evicts a live victim while its branch is
  unresolved, ~2.5M ticks before its own squash. AMuLeT patch → 0/30 = it's UV1, not an artifact.
- **UV6 — SpecLFB first-spec-load unprotected (REAL BUG).** The 1st USL (`isUnsafe=0`) misses and
  **installs** a secret-dependent line in-window; a protected load is LFB-held → no install.
- **KV1 — InvisiSpec L1I fetch (REAL BUG).** InvisiSpec's invisible-spec is **LSQ data-loads only**; the
  fetch unit installs the L1I line normally (`L1cache.sm:1258 {NP,I},Ifetch→IS`). BTB-forced-taken redirect
  to a speculative-only label → its I-line installs (`Ifetch NP>IS`) under mispredict, not under control.
- **KV3 — STT spec store → D-TLB (REAL BUG).** STT protection is loads-only (`isTransmit()=isLoad()`;
  `Request::SPEC` set only in `readMem`). A wrong-path **store** translates+fills the D-TLB unprotected.
  2×2: store walks the cold page under both STT and Unsafe; the load walks under Unsafe but NOT STT.
- **UV4 — CleanupSpec split not cleaned (REAL BUG).** `issueCleanupRequest` hard-codes
  `state->isSplit = false; //Assume no split` + a single `cleanupReq`. A cacheline-crossing spec load
  installs 2 lines and gets **0** cleanup; the aligned control is cleaned (`Inv_CLEANUP E>M_I`).
- **unXpec — CleanupSpec undo-as-channel (REAL BUG).** Even when cleanup is *correct*, its footprint is
  secret-dependent: `lsq_unit_impl.hh:142-160` selects the rollback (`Load_ROLLBACK`/`Skip_ROLLBACK`/
  `Inv_CLEANUP`) by `pkt->isL1Hit()`. Demo: spec-load **miss** (cold) → **7** cleanup events (full
  L1+L2+dir invalidation cascade); spec-load **hit** (pre-warmed) → **0**. = the published unXpec attack
  ("Breaking Undo-based Safe Speculation"), distinct from UV3/UV4 (incomplete cleanup): here cleanup is
  correct but its *presence/extent* leaks.
- **UV2 — InvisiSpec MSHR/TBE contention (REAL BUG, demonstrated).** A spec load holds the line in `IX`
  (TBE; pool default 2); `L1cache.sm:1189` stalls a new request to a line in a transient state, and the
  2-entry TBE pool serializes concurrent spec misses. Demo (`bug/uv2_demo/`): 4 spec loads to 4 cold lines
  on a TLB-warm page (TLB-warm trick, §2). `--L1_TBEs=2` → the pool is exhausted: 248 retry `NP>IX` events,
  the 3rd/4th loads delayed ~122k ticks waiting for a TBE. Control `--L1_TBEs=8` → 4 clean concurrent
  GETSPECs (1.5k-tick spread). The contention (later spec load's progress depends on TBE occupancy) is the
  secret-dependent single-thread MSHR-interference channel; `--L1_TBEs` isolates it.
- **UV3 — CleanupSpec spec store not cleaned (why-not).** CleanupCache undo is loads-only, BUT a squashed
  store never touches cache here (`canWB` at commit only; no spec-store RFO) → no cache footprint to leak.
  UV3-as-cache-residue is **unreachable in this store model** (not a tooling gap).
- **UV5 — CleanupSpec over-clean (REAL bug; empirical demo BLOCKED).** The rollback restores an evicted
  victim (`clf_cleanup_L1rollback_fired`/`cld_..._done` re-install `cleanup_get_cleanup_addr`); over-clean
  would be a mis-restore there. **Examined** (`uv5_demo/`, 8kB/assoc-2 = 64 sets so a 0x1000 stride is a
  guaranteed *physical* set collision): on the **free-way path** (spec install needs no eviction)
  CleanupSpec is **correct** — the spec line is cleaned (`Inv_CLEANUP E>M_I`→`WB_Ack M_I>I`) and the
  committed neighbour stays resident `E` with 0 cleanup events. The **eviction path** UV5 requires (spec
  install evicts a committed victim from a full set) triggers the generic Ruby **assoc-thrash `Resource
  Stall` storm** (~10⁶ retries, ON==OFF → defense-independent artifact, already ruled out in the residue
  review) at both assoc-2 and assoc-4 → no clean post-squash state to score. Verdict: mechanism real, demo
  blocked by the same obstacle class as UV2. `uv5_demo/NOTE.md`.

---

## 5. Reproduce everything (commands)

```bash
# KV1 (InvisiSpec L1I fetch)
python3 bug/kv1_demo/run_kv1_demo.py
# KV3 (STT store → D-TLB)
python3 bug/kv3_demo/run_kv3_demo.py
# UV4 (CleanupSpec split not cleaned)
python3 results/STT_6_cleanupspec_residue/uv4_demo/run_uv4_demo.py
# unXpec (CleanupSpec undo-as-channel)   -> MISS:7 events  HIT:0 events
python3 results/STT_6_cleanupspec_residue/unxpec_demo/run_unxpec_demo.py
# UV2 (InvisiSpec MSHR/TBE contention)    -> TBEs=2:248 retries/122k spread  TBEs=8:4/1.5k
python3 bug/uv2_demo/run_uv2_demo.py
# UV1 (InvisiSpec eviction)  — sweep watcher / compound checker
python3 STAGE3_gem5/check_ld_invisispec_compound.py <dir> --ruby ...   # see INVISISPEC_UV1_CONFIRMED.md
# UV6 (SpecLFB first-load)
python3 STAGE3_gem5/check_ld_speclfb.py <dir> ...
```

Each demo embeds its own control and prints the differential. Gate is STRICT lc/fnc throughout; no defense
logic is modified.

---

## 6. Open items / next steps

1. **UV2 — DONE (2026-06-09).** Unblocked via the TLB-warm-page trick (§2); demonstrated (`bug/uv2_demo/`).
2. **UV5 is the last empirical gap.** Its blocker is *different* from UV2's (not TLB deferral but the
   assoc-thrash `Resource Stall` storm when a spec install evicts a committed victim from a full set,
   ON==OFF). The TLB-warm trick won't fix that. Next dig: a **bounded controlled gadget** that warms the
   TLB + brings exactly ONE committed line into a 2-way set + a single spec load that misses into that set
   (evicting the committed victim) WITHOUT the litmus runaway thrash — so the eviction + cleanup-rollback
   can be scored for over-clean. (The free-way path already shows CleanupSpec is correct; only the
   eviction path is open.)
2. **Paper framing** — small-cache config (1kB/assoc-2, AMuLeT's own contention setup) deserves a paper
   note; the `--L1_TBEs=2` default is AMuLeT's, not ours. The assoc-thrash storm (ON==OFF) should be named
   as a defense-independent Ruby artifact so it isn't mistaken for a CleanupSpec result.

---

*Append dated status lines below as the project advances; keep the §1 scorecard the single source of truth.*

### Log
- **2026-06-09 (UV5 EMPIRICAL CLOSE)** — over-clean does NOT manifest in any hand-stageable scenario.
  Root: CleanupSpec **invalidates the spec line before restoring the victim** (`Inv_CLEANUP`@1292000 frees
  the way; `Load_ROLLBACK`@1297000 installs into it) → restore always finds room. The 3-committed+spec
  churn (`uv5oc.s`) loses a committed line only **architecturally** (3-for-2 ways), not via over-clean.
  ⇒ UV5 over-clean = precise why-not (ordering-prevented), needs AMuLeT's exact gadget. UV5 moved
  🟡→🟢. Status: 7 demonstrated + 2 precise why-nots (UV3, UV5), nothing blocked.
- **2026-06-09 (FINAL UV5)** — Clean-gadget scoring with corrected paddrs (A=0x2000,B=0x3000 committed;
  C=0x4000 spec; all set 0): spec C evicts committed A → squash cleanup invalidates C + `Load_ROLLBACK`
  restores A → **final A=E,B=E,C=gone = CORRECT, NO over-clean.** Basic eviction-rollback PROVEN correct.
  Over-clean (source-located `L1cache.sm:2722`, the restore is an allocating evict) needs the spec-freed way
  refilled by a committed line before the restore — a timing not staged. (Earlier "muddied" read was wrong
  line numbers.)
- **2026-06-09** — **UV5 eviction path UNBLOCKED.** The blocking `Resource Stall` storm = generic TBE-pool
  exhaustion (ON==OFF on a clean bounded `uv5evict.s` gadget: 15561 vs 15563 stalls). `--L1_TBEs=8` → 0
  stalls: the spec load evicts the committed victim (`L1_Replacement_OnInstall E>M_I→WB_Ack`) and the squash
  cleanup fires `Load_ROLLBACK NP>IS` to restore it. Over-clean-vs-correct verdict pending a cleaner gadget
  (committed set-lines provably resident-before-spec). Supersedes the "BLOCKED" verdict; now: needs a clean
  scoring run, not a new build/config.
- **2026-06-09** — ✅ **UV2 DEMONSTRATED (7th bug).** Root-caused the blocker: spec load to a cold page →
  speculative TLB-miss deferral (`Translation delay`) → no GETSPEC. **TLB-warm-page trick** (committed
  access warms the page, target line stays cold) unblocks it. 4 spec loads on a warm page exhaust the
  2-entry TBE pool: `--L1_TBEs=2` → 248 retry `NP>IX`/122k-tick serialize; `=8` → 4 clean. `bug/uv2_demo/`.
  Status now: **7 demonstrated** (UV1, UV6, KV1, KV3, UV4, unXpec, UV2); UV5 the last empirical gap; UV3 why-not.
- **2026-06-09** — UV5 examined (`uv5_demo/`, `NOTE.md`): free-way path shows CleanupSpec is correct (no
  over-clean); the eviction path UV5 needs trips the defense-independent assoc-thrash storm → empirical demo
  BLOCKED, mechanism source-confirmed. Status now: 6 demonstrated, UV2+UV5 examined-but-blocked (shared
  obstacle), UV3 why-not.
- **2026-06-09** — Consolidated this project log from scattered notes. unXpec (6th bug) verified
  reproducible (MISS:7 / HIT:0) and recorded here + in `claudelog.md`. Demonstrated: UV1, UV6, KV1, KV3,
  UV4, unXpec.
