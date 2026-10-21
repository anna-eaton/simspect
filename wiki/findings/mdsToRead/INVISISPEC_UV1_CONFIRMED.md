# InvisiSpec UV1 (speculative L1 eviction) — CONFIRMED by a compound hardware-structure watcher

**For:** Anna · **Date:** 2026-06-08 · session `5:invisispec` (autonomous)
**TL;DR:** A new compound checker watches every µarch structure a speculative load can
touch (L1 tags/eviction/install, MSHR/TBE, L2, directory). Run against the **real Ruby
InvisiSpec defense**, it fires on **AMuLeT's InvisiSpec UV1 bug**: an unsafe speculative
load **evicts a live L1 line while its guarding branch is unresolved**. The AMuLeT patch
eliminates exactly these hits (29/30 → 0/30), proving the hits are UV1 and not an
artifact. This is a **real InvisiSpec implementation bug**, not a test-generation problem.

---

## 0. The prerequisite finding: InvisiSpec was being tested on the wrong memory model

InvisiSpec's cache-side defense (Spec-GetS invisibility, the Speculative Buffer, the
eviction logic) lives in the **Ruby MESI protocol** (`.sm` files). The SimSpect pipeline
appends `--caches` but **not `--ruby`**, so every prior InvisiSpec run used the **classic
cache model** where that defense is **inactive** (the `cache.cc:192` aborts seen earlier
were the classic cache; the Ruby `ProtocolTrace` is empty without `--ruby`). All results
in this report use **`--ruby`** — the real defense. (SpecLFB is unaffected; it's a
classic-cache build.)

## 1. The watcher — `STAGE3_gem5/check_ld_invisispec_compound.py`

Parses the Ruby `ProtocolTrace` (one line per L1/L2/dir controller transition) for the
transmitter load's full per-line footprint, and flags it touching **any forbidden
structure while speculative**:

| Watched structure | Signal | AMuLeT bug | Fired? |
|---|---|---|---|
| **L1 eviction** of a victim line | `L1_Replacement` coincident with the load's `SpecLoad` | **UV1** | **YES** |
| L1 line install | `SpecLoad` → present state | (deeper bug) | no |
| L1 LRU/MRU on a hit | (structurally absent — `h_spec_load_hit` omits `setMRU`) | — | no (correct) |
| **MSHR / TBE** occupancy | `SpecLoad NP/I→IX` (miss allocates a TBE) | **UV2** surface | YES (inherent) |
| L2 eviction | `L2_Replacement` coincident | — | no (lines resident in L2) |
| Directory state change | `SpecFetch` in window | — | no (lines resident) |

**Observation point (important):** the watcher fires on the **controller-transition event
itself** — the `L1_Replacement` the L1 cache controller performs *while handling the
speculative load* — i.e. at the **source** of the illegal µarch state change, the instant it
happens. It is **upstream of any architectural output / final-state**, and uses **no relational
(two-input / patch ON-vs-OFF) comparison** to detect. (For UV1 this is essential: the spec load
evicts to make room but then allocates no block — the eviction never propagates to the load's own
output, so the only way to see it is at the event.) Relational/differential testing is used
*only afterward* to confirm a flagged hit is specifically UV1 (§3b).

Speculative gate (corrected): a touch counts if it happens **after the last-committed
predecessor retires, while a guarding mispredict branch is unresolved, and before the
load's own squash**. (Earlier I wrongly used the classic `lc<t<fnc_retire` window; under
`--ruby` the invisible Spec-GetS is a slow memory access, so the touch lands *after*
`fnc_retire` yet still while speculative — `branches_unresolved` is the right gate.)

The build, checker, and launcher are reusable. `STAGE3_gem5/check_ld.py` is **unchanged**
(git-clean); the watcher is a new file. **No gem5 rebuild was needed** — `ProtocolTrace`
gives the full observability; the only knobs are config (`--ruby`, small L1D, the patch
flag).

## 2. Amplification — why a small L1D, and why it's legitimate

The const-addr litmus loads otherwise **hit** in L1 (the prologue zero-inits and
pre-warms their line), so the spec load touches nothing. AMuLeT amplifies the same way:
they shrank the L1D to 2 ways / 2 MSHRs so the bug fires in small programs. I use
**`--l1d_size=1kB --l1d_assoc=2`** so the working set overflows and the spec load misses
on a full set. The bug is **structural** (it fires in a full cache whenever the working
set exceeds L1); the small cache just makes the tiny tests exercise it. This is
amplification of a real bug, not tuning to manufacture a result.
(`--l1d_assoc=1` aborts in Ruby; 2-way is stable. `--L1_TBEs` is already `2` by default.)

## 3. Evidence

### 3a. The watcher indicates the bug STANDALONE (this is the detector, not a differential)
A **single run** of the default (unpatched, as-shipped) InvisiSpec build, `--ruby`, L1D=1kB/2,
over 30 STT_6 `mispredict_not_taken` ld tests: **29/30 → `touched_forbidden:l1_eviction`** (1
`no_spec_read`). Each hit, on its own, is a bug indication — a speculative load evicting a live
L1 line is forbidden under an "invisible speculation" defense; the watcher flags it from one
trace with no comparison. This is the intended use: the hooks/watchers point at the bug *before*
any relational testing.

### 3b. Differential — CONFIRMATION ONLY that the standalone hit is specifically UV1
(Not the detection method.) Re-running the same tests **patch ON** (`--apply-spec-eviction-patch`,
the AMuLeT fix): **0/30 forbidden**; the same 29 become `spec_miss_tbe_only` (still miss + allocate
a TBE, but no longer evict). The patch changes only the `SPEC_LD` eviction path
(`MESI_Two_Level-L1cache.sm:514`), so its removing exactly the watcher's hits confirms they are UV1.

### 3b. Per-hit mechanism (representative)
`inst-000216`: xmit spec load line `0x3580`. At tick **3194000** it does `SpecLoad NP>IX`
(misses, allocates a TBE) and **at the same tick** an `L1_Replacement` evicts victim line
**`0x3980`** (state `M>M_I` — a *present, modified* line is thrown out). The guarding
branch is unresolved at 3194000; the load is squashed only at **5681000** (~2.5M ticks
later). So a wrong-path speculative load removed a live L1 line — observable to an attacker
via the now-missing line, and it leaks the spec load's (address-derived) conflict set.
Consistent across hits (`inst-000131`: line `0x35c0` evicts `0x39c0` @3190000; etc.).

### 3c. Generalization
STT-interleave (`testsets/STT_6_interleave`, 14 ld tests): **10/14 `l1_eviction`**, 1
`invisible_spec_hit` (a spec load that hit → touched nothing, correctly clean), 3
`no_spec_read`. So UV1 fires on both corpora, and the watcher discriminates (it does *not*
blindly flag every load).

## 4. Verdict

- **InvisiSpec UV1 = CONFIRMED real bug**, reproduced and caught by the compound watcher;
  matches AMuLeT's finding exactly (patch eliminates it). **Not** a test-gen artifact —
  the generator produces valid speculative loads; the flaw is in InvisiSpec's Ruby cache
  controller; the small cache is standard amplification.
- **UV2 surface present**: every spec miss occupies an MSHR/TBE (`spec_miss_tbe_only`),
  with `--L1_TBEs=2` by default — the single-thread MSHR-interference surface. Reported as
  `needs_pressure` (it's inherent to any non-blocking spec load; a *leak* only under
  contention, which the default 2-TBE config provides).

## 5. Honest caveats / scope
- **Exploitability vs structural touch:** in these tests the spec load's index value is 0
  (zero-init buffer), so the evicted *victim* is a fixed address — the eviction is not yet
  a *secret-dependent* (demonstrable) leak. But the load's address operand **is** tainted
  (`base + speculative_index`), and the watcher's job is to catch the *forbidden
  speculative structural touch* (the eviction), which it does. Making the victim
  secret-dependent is the same zero-init-input stimulus gap noted for SpecLFB UV6 — an
  exploitability question, orthogonal to "did the speculative load evict."
- **L2/dir watchers didn't fire** because the evicted lines stay resident in the (larger)
  L2 — no L2 eviction or memory/dir fetch. Shrinking L2 would exercise the lower-level
  prongs; UV1 (L1) is the headline AMuLeT bug and is confirmed.
- **Store-buffer prong** not yet added: InvisiSpec's SB is the *allowed* holding place;
  store-queue forwarding to a USL is by-design (paper §V), not an AMuLeT bug. Noted for
  completeness.

## 6. Reproduce
```bash
# UV1 fires (unpatched, amplified):
python3 results/STT_6_invisispec_compound/run_invisispec_compound.py \
    --n 30 --jobs 4 --modes mispredict_not_taken            # → ~29/30 touched_forbidden:l1_eviction
# control — the AMuLeT fix removes them:
python3 results/STT_6_invisispec_compound/run_invisispec_compound.py \
    --n 30 --jobs 4 --modes mispredict_not_taken --patch-on  # → 0 forbidden, all spec_miss_tbe_only
```
Checker: `STAGE3_gem5/check_ld_invisispec_compound.py`. Design: `docs/COMPOUND_TRANSMISSION_CRITERION.md`.
Bug site: `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1/src/mem/protocol/MESI_Two_Level-L1cache.sm:514`.
