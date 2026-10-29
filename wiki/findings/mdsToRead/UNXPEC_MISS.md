# Why the CleanupSpec criterion misses unXpec, and what to figure out

**For:** Anna · **Written:** 2026-10-28 · **Status:** open investigation. Sources: `AMULET_LOAD_DEFENSES_PROJECT_LOG.md` (unXpec bullet, demo), `AMULET_THREE_DEFENSES_EXPLAINER.md` §5, `AMULET_BUGS_DETECTION_ACCOUNTING.md` §0–§1, `wiki/design/TRANSMISSION_CRITERIA_FORMAT.md`. The unXpec, CleanupSpec, and AMuLeT papers have **not** been read for this note; claims about them are marked unverified.

## The claim

The CleanupSpec criterion we agreed on (per line: installed − invalidated ≠ 0, or evicted − restored ≠ 0) cannot flag unXpec. unXpec is not a cleanup that is wrong. It is a cleanup that is **correct but secret-dependent in how much work it does**, so it shows up only in time, which the criterion does not look at.

## Worked example (the existing demo)

`results/STT_6_cleanupspec_residue/unxpec_demo/run_unxpec_demo.py` (on cafe2) runs one gadget two ways. The mechanism is `lsq_unit_impl.hh:142-160`, which picks the undo path from `pkt->isL1Hit()`.

| case | speculative load | footprint | cleanup events | installed − invalidated | evicted − restored | criterion says |
|---|---|---|---|---|---|---|
| miss (cold line) | fills L1/L2 | 1 install (+ victim if set full) | 7 (L1 + L2 + directory invalidation cascade) | 0 | 0 | no leak |
| hit (pre-warmed) | hits | none | 0 | 0 | 0 | no leak |

Both runs end with a correctly restored cache, so the count is zero both times. The difference between the two (7 events vs 0, and the squash-to-resume time that follows) is the channel. The attacker times the recovery, not the cache contents.

## Why each check we have misses it

- **STT-style criterion** ("transmitter executed in window"): flags every CleanupSpec test, because CleanupSpec lets speculative loads run by design. That isn't detection; it's noise.
- **Footprint-count criterion** (the agreed format): checks that the undo restored the *state*. unXpec's observable is the undo's *duration*. Restoring state correctly does not make the duration secret-independent.
- **Final-state diff** (the proposed cross-check, and AMuLeT's final-tag-set comparison as we understood it): same blind spot. The final states of the two cases are identical.
- **Single-run by construction:** a single run sees only one secret value. "7 cleanup events" is not wrong on its own; it is wrong only because the other secret value would give 0. Calling it a leak needs either a second run or an explicit claim that the alternative exists.

## Inconsistency in our own docs (fix once the papers are read)

`AMULET_BUGS_DETECTION_ACCOUNTING.md` §0 describes unXpec as "leftover spec-installed addresses" and files it under the final-state class. The demo and the project log describe it as "the undo itself is the channel", where the cleanup is correct but its extent leaks. These are different bugs. The second matches the demo; the first may be AMuLeT's paraphrase. The unXpec paper settles it.

## What to figure out

**Items 1–3 are answered (with paper quotes and code lines) in [`FOOTPRINT_DEFENSES_PAPER_AUDIT.md` §4b](FOOTPRINT_DEFENSES_PAPER_AUDIT.md).** Short version: (1) unXpec times rollback latency with rdtscp in the same thread; invalidation alone is enough. (2) CleanupSpec claims cleanup "does not practically leak" but leaves constant-time cleanup as future work (p8). (3) AMuLeT's unXpec (KV2) is the timing channel showing up as a final-state **L1I** difference, flagged by `cleanupspec_analysis.py:100`. It is not L1D residue.

1. **What unXpec actually observes.** Fetch the unXpec paper (HPCA 2022, "unXpec: Breaking Undo-based Safe Speculation"; title and venue from memory, unverified) into `quail/sources/papers/`. Write down its exact observable (rollback latency? which timer? which levels' cleanup?) and its gadget.
2. **What AMuLeT detected and how.** In the AMuLeT paper and `/work/amulet-repo`: is "unXpec" in their results the timing channel or residue? Which trace or comparison caught it?
3. **Is it in CleanupSpec's own scope?** Per the rule "exactly what the paper protects": does the CleanupSpec paper claim cleanup is constant-time or otherwise timing-safe (in scope, so a bug), or does it leave cleanup timing out (outside its contract, so a known limitation, not a criterion violation)? This decides whether unXpec belongs in the CleanupSpec criterion at all.
4. **If it is in scope, pick a formulation.** Candidates, all readable from the SimSpect hook trace (`squash`, `cleanup_*`, `cleanup_done`, plus pipeview retire ticks):
   - **(a) Cleanup work as an observable (single run).** Treat `cleanup_done(sq) − squash(sq)` and the cleanup event count as an observation, like a cache line. Leak iff that work is nonzero *and* is caused by a speculative load whose address is secret (tainted). The implicit assumption is that some other secret value would hit and cost 0. That holds only if the concretization can make the alternative a hit, so check item 5.
   - **(b) Relational pair.** Run each test twice, with the secret-dependent line cold vs warm, and compare cleanup work or squash-to-resume time. This is the faithful version, but in SimSpect's framing it is confirmation, not detection (`AMULET_VS_SIMSPECT_SCOPE.md`).
   - **(c) Committed-path delay.** Leak iff cleanup delays the retire tick of the first correct-path instruction after the squash (visible in pipeview), and the delay is attributable to a speculative footprint. This is closer to what an attacker measures. It needs to know whether this build stalls the core during cleanup.
5. **Do our testsets even reach the hit/miss split?** Our litmus tests start cold, so every speculative load misses and every test does cleanup. Without a test where the speculative line could be warm, there is no hit counterpart. Check whether any STT_6 concretization pre-warms the speculative load's line. If none does, (a) is unfalsifiable on our tests and (b) needs a warm-variant generator.
6. **Hooks:** confirm the new CleanupSpec SimSpect hooks emit `squash` with its tick and `cleanup_done` per squash id, which (a) to (c) all need (`wiki/design/SIMSPECT_HOOKS.md` once written).

## Recommendation (pending 1–3)

If the CleanupSpec paper puts cleanup timing in scope, add (a) as a second term in the CleanupSpec criterion (`leak_timing`), kept separate from the count term so a hit says which kind it is. Use (b) on (a)'s hits as confirmation. If the paper leaves it out of scope, record unXpec in the criterion JSON's `not_covered` with the quote, and keep the demo as the evidence that the limitation is real.

## Answers to items 1–3 (paper audit, 2026-10-28)

From `FOOTPRINT_DEFENSES_PAPER_AUDIT.md` §4b, which quotes the papers saved in `quail/sources/papers/` (`li-2022-unxpec`, `saileshwar-2019-cleanupspec`, `fu-2025-amulet`):

1. **unXpec's observable** is rollback latency, timed with `rdtscp` in the same thread (HPCA 2022). Invalidation alone gives a 22–32 cycle difference. This supports candidate (c), committed-path delay, as the faithful single-run reading.
2. **CleanupSpec's scope:** the paper says cleanup "does not practically leak" but leaves constant-time cleanup to future work (p8). That is a borderline claim: in scope only if Anna reads "does not practically leak" as a protection claim. **Anna decides.**
3. **AMuLeT's unXpec (KV2)** is the timing channel, which shows up as different final **L1I** tags (`cleanupspec_analysis.py:100`), not leftover L1D lines. `AMULET_BUGS_DETECTION_ACCOUNTING.md` §0's "leftover spec-installed addresses" is therefore wrong.
