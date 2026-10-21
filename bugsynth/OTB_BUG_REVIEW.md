# Review: recon `getOldestTaint` (OTB) bug GENERATED from Alloy and HIT on /work/gem5-recon-modded

**For:** Anna. **Author:** autonomous `bugsynth` session, 2026-06-08. **Status:** ✅ reproduced (10/10 differential).
All work isolated under `/tests/simspect/bugsynth/`; the live pipeline/models/testsets/results and running
sweeps were never touched.

## Claim
A **general** SimSpect pipeline — Alloy → concretization → gem5 differential checker — that *synthesizes the
class* of recon's `getOldestTaint` (OTB) gadget and **confirms the leak on /work/gem5-recon-modded
(scheme 2 + `allow_leaked`)**. On a 10-gadget sample, **10/10 leak differentially**: the transmitter load
is released (issues + accesses cache) while a still-speculative load feeds its address — but **only when
the older contributing load resolves first** (a control where both resolve together holds the transmitter
correctly). That isolates exactly the `getOldestTaint` "track the OLDEST taint" bug
(`taint_tracker.cc:119` + `freeTaints:134`). Not a hand-written example: the gadget class is enumerated by
Alloy; 10 distinct instances leak.

## The gadget (what the model generates — `models/STT_6_otb2.als`)
```
ba   correctly-not-taken branch (resolves EARLY, no squash; held by resolve_stall)
  la   load_A  (older, under ba)
bb   mispredict branch (stays SPECULATIVE; large resolve_stall)
  lb   load_B  (younger, under bb)
  o    2-input ALU = f(la, lb)          ← both inputs rf-fed by distinct loads
  x    load, address = o                ← the transmitter (xmit)
```
`otb_class` forces: xmit-load address ← a **2-input ALU** whose **both** inputs are rf-fed by **distinct**
loads `la,lb`, with `la` under a resolved (correctly-not-taken) branch and `lb` under an unresolved
(mispredict) branch, `ba < la < bb < lb`. Generated **directly in Alloy** (no interleave). A relaxed driver
`gen_useful_otb` drops the base RR-branch-minimality (the 2-source merge is inherently non-minimal).

## Mechanism (verified in /work/gem5-recon-modded source)
`taint_tracker.cc:119 getOldestTaint` returns the source with the **lowest seqNum**; `propagateTaints:108`
stores only that single oldest source as the ALU dest's taint; `freeTaints:134` drops a taint when its
load `!isSpeculative()`. So: the ALU taint is pinned to `la` (older); when `la`'s branch (`ba`) resolves,
`la` becomes non-speculative → `freeTaints` clears the ALU dest taint → the xmit's address is treated
UNTAINTED and the load issues to cache — even though `lb` (younger, under the still-unresolved `bb`) is
speculative and actually feeds the address. Correct behaviour would track the YOUNGEST taint (resolves
last).

## Evidence (re-runnable)
```
cd /tests/simspect/bugsynth && python3 otb_check.py 30 2500 5000
# => 30/30 OTB gadgets LEAK differentially (default pipeline mispredict stall = 5000)
```
**Robust differential** — leak = the xmit is RELEASED (issues+completes+accesses cache) **earlier** under
OTB timing than under the control, by a clear margin, while `lb` is still speculative:
- **OTB timing** (la-branch stall 2500 → la resolves first; bb stall → lb stays speculative): the xmit
  issues at **3924500** (≈ la-resolve) and accesses cache, while `lb` is still speculative.
- **CONTROL** (both branches same stall → la & lb resolve together): the xmit is held until **5174500**
  (≈ lb-resolve) — released only when `lb` is no longer speculative ⇒ no leak.
- **Δrelease ≈ 1,250,000 ticks (2500 cycles)** consistently: the xmit is released early *specifically*
  because the OLDER `la` froze first (getOldestTaint), not because of `lb`.
**Robust across the timing band**: differential leak = 5/5 at every tested (la-branch, bb) ∈
{(500,5000),(2500,5000),(1500,7000),(2500,9000),(3500,12000)}; control = 0/5 throughout. Not a tuned point.
The leak appears **iff `la` resolves before `lb`** — the signature of oldest-taint tracking.
**Control**: the hand-crafted `oldest_taint_bug/debug_out/inst-oldest-taint-bug.s` also leaks on this build
(xmit issues + cache-touch before branch_inner resolves), confirming build + mechanism independently.

## How it was built (general; full log in `WALKTHROUGH.md` §2.1–2.11, esp. 2.10–2.11)
1. **Alloy** `STT_6_otb2.als` (`otb_class` 2-load→ALU→xmit + ba/bb ordering; relaxed `gen_useful_otb`).
2. **Concretization** unchanged for the gadget; `la` under correctly-not-taken, `lb` under mispredict.
3. **Critical pipeline fix** (`compile_annotate.py`, additive): recon-modded's `se.py` reads
   `branch_pc_addr_hex`/`x86_branch_offset_hex` (older ann schema), not `branch_addr_hex`. Our ann only had
   the latter → recon-modded **skipped every annotation → no resolve_stall → the mispredict branch squashed
   the gadget before it could execute** (this was the long-standing "xmit never issues"). Emitting the alias
   keys makes resolve-stall register on recon-modded (and keeps /work/stt working). After this, the gadget
   executes and the leak reproduces.
4. **Checker** `otb_check.py`: differential on the xmit release tick vs `lb`'s branch squash, OTB vs control.

## Validity matrix (scheme 0 vs 2 + protected control — the "doesn't cry wolf" check)
The same OTB gadget, xmit cache-access tick (= when it leaks):

| condition | xmit accesses cache | meaning |
|---|---|---|
| **scheme 0** (unsafe), OTB timing | **2677500** (immediate, right after the ALU) | no protection (baseline) |
| **scheme 2** (STT), OTB timing (la resolves first) | **3924500** (= la-resolve, *before* lb-resolve 7174500) | **BUG: getOldestTaint releases at the OLDER load → xmit accesses cache while lb still speculative** |
| **scheme 2** (STT), control (la & lb resolve together) | **7174500** (= lb-resolve) | **STT fully protects** (held until the younger load is non-speculative) |

This **refines** reconresults.md's "STT provided no additional protection": STT *does* protect in general
(control: holds the xmit from 2677500 → 7174500, i.e. until lb resolves) — the bug is **specifically** that
getOldestTaint frees the dest taint at the **older** la's resolution (3924500) rather than the younger lb's
(7174500), so the xmit accesses cache while lb is still speculative. The control (STT fully protecting the
same gadget when there's no OTB timing) is the decisive "the pipeline+checker don't cry wolf" evidence.

## Verdict
**Real bug.** Reproduced generally (30/30, robust across the timing band, fires at the default pipeline
stall). The reference hand-crafted test leaks identically. STT provides only **partial** protection here
(delayed to la-resolve) instead of full (lb-resolve). Correct fix (per reconresults.md): track the
**youngest** taint source, or free a dest taint only when **all** contributing sources are non-speculative.

## What's open / caveats
- The discriminating signal is the xmit **release/issue** tick (getOldestTaint untaints it); there is also a
  baseline ~2.6M-tick speculative "Executing load" present even in the control (an invisible spec read) —
  the checker keys on issue/complete, not that baseline touch, to avoid false positives.
- Timing band is set by stalls (la-branch < bb); the reference uses a slow cache-miss branch_inner instead.
  This is a *bug-class* timing (older-resolves-first), not fine-tuning to a specific instance.
- Owner decision: fold `STT_6_otb2.als` + the `compile_annotate.py` alias into mainline, or keep as a
  dedicated repro. No mainline `.als`/pipeline modified.
