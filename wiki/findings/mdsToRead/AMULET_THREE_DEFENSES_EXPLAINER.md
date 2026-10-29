# AMuLeT bugs on InvisiSpec, SpecLFB, CleanupSpec — explainer

**For:** Anna · **Written:** 2026-10-28 · **Sources:** distilled from `AMULET_LOAD_DEFENSES_PROJECT_LOG.md` (scorecard), `AMULET_BUGS_DETECTION_ACCOUNTING.md`, `wiki/design/docs/COMPOUND_TRANSMISSION_CRITERION.md`, `wiki/design/docs/AMULET_VS_SIMSPECT_SCOPE.md`, and a read of `STAGE3_gem5/check_ld_cleanupspec.py`, `STAGE3_gem5/check_ld_invisispec_compound.py`, `STAGE3_gem5/gem5_common.py`, `pipeline.py`. No demos were re-run for this doc; the evidence is from the June `5:invisispec` sessions.

InvisiSpec, SpecLFB, and CleanupSpec are the three defenses only AMuLeT tests (STT is AMuLeT's fourth target, but SimSpect covers it too). All three **let the speculative load execute and then try to hide or undo its microarchitectural footprint**, unlike STT/SPT/Recon, which block the transmitter. So every bug below is a footprint that still shows: a structure they forgot, a case they skipped, or a mistake in the hiding itself.

## 1. Scorecard

6 of the 8 bugs on these three defenses are reproduced on the real (unmodified-defense) builds. The other 2 (CleanupSpec UV3, UV5) have source-grounded reasons they can't be reproduced on this build.

| Bug | Defense | What it is | Status | Evidence |
|---|---|---|---|---|
| UV1 | InvisiSpec | spec load evicts a live L1 line | ✅ real bug, demonstrated | 29/30 STT_6 via `check_ld_invisispec_compound.py`; `--apply-spec-eviction-patch` → 0/30. `INVISISPEC_UV1_CONFIRMED.md` |
| UV2 | InvisiSpec | MSHR/TBE contention | ✅ real bug, demonstrated | `bug/uv2_demo/`: `--L1_TBEs=2` → 248 retry `NP>IX`, ~122k-tick serialization; `=8` → 4 clean |
| KV1 | InvisiSpec | L1I fetch unprotected | ✅ known limitation, demonstrated | `bug/kv1_demo/`: wrong-path `Ifetch NP>IS`; correctly-predicted control installs nothing |
| UV6 | SpecLFB | first spec load unprotected | ✅ real bug, demonstrated | 11/12 `cache_install_in_window` via `check_ld_speclfb.py` |
| UV4 | CleanupSpec | split (line-crossing) load not cleaned | ✅ real bug, demonstrated | `results/STT_6_cleanupspec_residue/uv4_demo/`: split installs 2 lines, 0 cleanup; aligned control cleaned |
| unXpec | CleanupSpec | the undo itself is the channel | ✅ real bug, demonstrated | `unxpec_demo/`: miss → 7 cleanup events, hit → 0 |
| UV3 | CleanupSpec | spec store not cleaned | 🟢 can't reproduce on this build (source-grounded) | squashed store never touches the cache (`canWB` set at commit only; no spec RFO); `uv3.s` shows no `Store NP>IM` |
| UV5 | CleanupSpec | "Too Much Cleaning" (over-clean) | 🟢 can't reproduce on this build (source-grounded) | invalidate-before-restore ordering prevents it in every hand-built gadget (`uv5_demo/NOTE.md`); AMuLeT's detector is a two-run final-state diff |

## 2. Why loads evict

A cache is split into **sets**, and each set holds a fixed number of lines (**ways**). An address can only live in one set. On a load miss, the cache fetches the line and stores a copy (allocate-on-read), so loads fill the cache just like stores. If every way in that set is occupied, the replacement policy (LRU, random, …) picks a **victim**, evicts it (writing it back first if dirty), and the new line takes its place.

Which set fills, and which victim leaves, depends on the load's address. If that address is secret-derived, an attacker who later times their own lines (Prime+Probe) sees which one went missing, even though the squashed load never returned a value.

Litmus tests touch a tiny working set, so with a normal 64kB/8-way L1D every load hits and nothing evicts. The runs shrink the L1D to 1kB/2-way (AMuLeT's own setup) so sets fill up. That makes a real eviction behaviour show up in a short test rather than inventing one. This needs a paper note (`AMULET_BUGS_DETECTION_ACCOUNTING.md` §4). Ruby aborts at `--l1d_assoc=1`; CleanupSpec deadlocks at assoc-2 with a small L1D, so its runs use assoc ≥ 4.

## 3. Per defense

### InvisiSpec (Ruby MESI build, needs `--ruby`)

A speculative load reads into a hidden speculative buffer and should not install a cache line until it is safe (GETSPEC instead of a normal fetch). The defense lives in the Ruby `.sm` files; without `--ruby` it is inactive.

- **UV1:** a speculative miss (`SpecLoad NP>IX`) still triggers an `L1_Replacement` at the same tick, evicting a live victim while the branch is unresolved. The build's own `--apply-spec-eviction-patch` removes it, which is why it is a bug and not intended behaviour.
- **UV2:** a speculative miss holds a TBE (Ruby's MSHR; the pool defaults to 2). A new request to that line stalls (`L1cache.sm:1189`), and concurrent spec misses serialize on the pool, so other accesses' timing depends on what was speculatively loaded. The unblock was the TLB-warm-page trick: warm the page with a committed access to a different line, otherwise InvisiSpec defers the speculative TLB miss and the load never reaches the cache.
- **KV1:** InvisiSpec only hides LSQ data loads. Instruction fetch installs L1I lines normally (`L1cache.sm:1258`). A BTB-forced taken prediction to a speculative-only label installs that label's I-line.

### SpecLFB (classic-cache build)

Unsafe speculative loads are held in the line-fill buffer (LFB) instead of being installed.

- **UV6:** the first unsafe speculative load in the LSQ is classified `isUnsafe=0`, so it is not held. It misses and installs a line in the window (and can evict like a normal load), while later protected loads stay in the LFB.

### CleanupSpec (Ruby MESI build)

The opposite approach: speculative loads install normally, and on squash the defense undoes them, invalidating the speculative line (`Inv_CLEANUP`, `InvL2_CLEANUP`) and restoring the evicted victim (`Load_ROLLBACK`).

- **UV4:** `issueCleanupRequest` hard-codes `state->isSplit = false; //Assume no split - TODO` and sends one cleanup request, so a line-crossing load installs 2 lines and gets 0 cleanup.
- **unXpec:** even correct cleanup is secret-dependent. `lsq_unit_impl.hh:142-160` picks rollback vs skip by `pkt->isL1Hit()`, so a miss gives a 7-event invalidation cascade (L1, L2, directory) and a hit gives 0. The cleanup timing is the channel (the published unXpec attack).
- **UV3:** the undo only handles loads (`Sequencer.cc writeCallback:443` never records cleanup metadata), but a squashed store never reaches the cache on this build, so there is nothing to miss. Reproducing it needs a build where speculative stores write to the cache.
- **UV5:** in hand-built gadgets the rollback is correct: CleanupSpec invalidates the speculative line first (freeing the slot), then restores the victim into it, so the restore always has room. AMuLeT's detector (`/work/amulet-repo/src/cleanupspec_analysis.py:138`) compares the final cache tag sets of two runs. That is a relational, final-state view of the same secret-dependent-cleanup flaw unXpec shows. Reproducing their exact UV5 needs their fuzzed gadget and two-run harness.

## 4. What CleanupSpec does and does not undo

The undo works on **cache contents**: which lines are present in L1/L2.

Undone (from `COMPOUND_TRANSMISSION_CRITERION.md` §5):

- Lines installed by speculative loads → invalidated (`Inv_CLEANUP`, and `InvL2_CLEANUP` since the run config uses `--scheme_cleanupcache=Cleanup_FOR_L1L2`).
- Victims evicted by those installs → recorded in the LSQ (`EvictedLineAddrL1`) and restored by `Load_ROLLBACK`.
- Which undo is chosen depends on hit-level metadata from `Sequencer.cc` (`setL1Hit`, L2-hit/L2-miss). That choice is what makes unXpec possible.

Not undone on this build:

- Stores (UV3); line-crossing loads (UV4); the cleanup's own work and timing (unXpec).
- The TLB is a separate layer (STT KV3 shows translation happens at execute, outside any cache undo). Whether this CleanupSpec build lets a speculative load fill the D-TLB is **unchecked**.

Other state a speculative load changes, from the compound-criterion table: replacement/LRU bits (updated even on a hit), MSHR/TBE occupancy, directory/coherence state (another core's line downgraded M→S), TLB, L1I, prefetcher state, port and queue contention. Restoring line presence restores none of these.

**From memory, unverified:** I believe the CleanupSpec paper (Saileshwar & Qureshi, MICRO 2019) does not roll these back but designs around some of them (random replacement so LRU doesn't matter, a randomized L2, delaying speculative loads that would downgrade another core's coherence state), and does not cover TLB or prefetcher. Whether this AMuLeT build implements any of that is also unrecorded. To settle it: read the paper's threat-model section (save it to `quail/sources/papers/`) and grep the build on cafe2 for its replacement policy, coherence-downgrade handling, and spec TLB fills.

## 5. Which signal to use for CleanupSpec

For CleanupSpec, a line installed in the speculative window is **not** a leak; that is how the defense works. The leak is **what is still there, or wrongly changed, after the cleanup finishes**. The strict window `lc_retire < t < fnc_retire` (branches unresolved) still applies, but to **when the footprint happened**; the leak itself is judged after.

**Signal 1 — footprint not undone (UV4, UV3).** For every in-window speculative footprint, require the matching undo after the squash:

| Speculative footprint (in window) | Undo that must follow |
|---|---|
| A cold line is installed (a miss) | `Inv_CLEANUP` / `InvL2_CLEANUP` on that line |
| A committed victim is evicted to make room | `Load_ROLLBACK` re-installs that victim |
| A hit on a line already resident | nothing (no new footprint) |

A footprint with no matching undo is **residue**, the bug. It is a single-run check against the `ProtocolTrace` event log (`check_ld_cleanupspec.py:145-189`).

**Signal 2 — cleanup on a line speculation never touched (UV5).** An undo event that matches no speculative footprint, such as a rollback that evicts a committed line. Reported today as `orphan_cleanup_lines` (`check_ld_cleanupspec.py:172`).

**Signal 3 — the cleanup itself leaks (unXpec).** The cleanup is correct, but its size depends on the secret. One run can't show that: it needs a pair of runs (or a known baseline) that differ only in the secret, comparing cleanup count or squash-to-done time. That is relational, so in SimSpect's framing it is confirmation, not detection, which is why unXpec was shown with a hand-built hit-vs-miss gadget.

**Stronger single-run check (proposal, not built):** rebuild L1/L2 contents from `ProtocolTrace` at two points, just before the window opens and after the last cleanup event, and require every difference to come from committed instructions. That covers signals 1 and 2 without relying on per-event pairing being complete.

### Gaps in `check_ld_cleanupspec.py` (from reading `analyze_cleanup`; not yet fixed)

1. **Any cleanup event counts as "cleaned".** Line 161 accepts anything in `CLEANUP_EVENTS`, including `Skip_ROLLBACK`, `Inflight_CLEANUP_reqs`, `Drop_Load_Cleanup_Inflight`. A cleanup that started but was skipped or dropped would hide residue. It should require the right finishing event per footprint (install → invalidated; victim → rolled back).
2. **Evicted victims aren't checked.** It records install-event lines and misses but never checks that a victim got its `Load_ROLLBACK`. Open: does `L1_Replacement_OnInstall` report the victim's address or the new line's? Needs one look at a CleanupSpec trace on cafe2.
3. **Only L1 is checked.** It filters to `machine == "L1Cache"` (line 149), but the config runs `Cleanup_FOR_L1L2`, so L2 and directory footprints are never checked.
4. **It doesn't check the load was actually squashed.** If the path commits, no undo is owed, but this would currently be flagged as residue.
5. **The UV5 test is loose.** "Never load-accessed in this run" is not the same as "has no speculative footprint". It should be: a cleanup/rollback that matches no footprint from the table.

## 6. Hooking cache install/evict events into the pipeline

You usually don't need a C++ hook: gem5 already prints installs and evictions through debug flags, so it is a run-config change plus parsing, no rebuild.

**Step 1 — turn on the flag** in `gem5.debug_flags` in `run_config.jsonc`. `pipeline.py:551-566` turns the list into `SIMSPECT_GEM5_DBG_FLAG`; `gem5_common.py:157` adds `Commit` itself.

- **Ruby builds (InvisiSpec, CleanupSpec, SPT's MESI build):** `ProtocolTrace`, plus `--ruby` in `extra_args`. One line per controller transition: `<tick> <node> L1Cache <Event> <cur>><next> [<addr>, line <line>]`. Evictions are `L1_Replacement` / `L2_Replacement` (CleanupSpec: `L1_Replacement_OnInstall`); installs are transitions out of an empty state such as `NP>IS`; instruction fetches are `Ifetch NP>IS`.
- **Classic builds (SpecLFB, STT, recon):** `Cache`. It prints `system.cpu.dcache: access for ReadReq [..] hit|miss`; `gem5_common.parse_lsq` pairs the miss with the load as `cache_fill_tick` (`gem5_common.py:298-378`). The classic **eviction** message is unchecked: grep `DPRINTF(Cache` in that build's `src/mem/cache/` before writing a regex.

```jsonc
"gem5": {
  "debug_flags": ["O3PipeView", "LSQUnit", "Squashed", "ProtocolTrace"],
  "extra_args": ["--ruby", "--scheme=SpectreSafeInvisibleSpec", ...]
}
```

A real C++ hook is only needed if a build doesn't print the event at all. It must be a `DPRINTF` in the cache only, no defense-logic change; rebuild, back it up under `gem5-hooks/`, and record it in `specs/gem5_hooks.json`.

**Step 2 — parse and gate.** Existing code in `check_ld_invisispec_compound.py`: `parse_protocol_trace` (line 58) groups events by line, `parse_load_paddrs` (line 76) gets the transmitter's line from the LSQ trace, `_in_window` (line 89) is the strict window, and `analyze_compound` (line 93) ties an `L1_Replacement` to the transmitter by same-tick cause. For new checkers, move `parse_protocol_trace` / `parse_load_paddrs` into `gem5_common.py`. Keep only events tied to the transmitter (line address or same-tick cause), inside the window with branches unresolved. Never widen the gate.

**Step 3 — write it out.** Add fields like `install_tick`, `evict_tick`, `evicted_line`, `issued_in_window` to the per-test result. `window-results.json` keeps only `name`, `status`, `issued_in_window`; run the checker with `--out` to keep per-event timing.

**Step 4 — connect it to the pipeline (the gap).** The pipeline chooses the checker from a hard-coded table, `_KIND_TO_CHECKER` (`pipeline.py:294`), by transmitter kind only, so a run config can't say "use the InvisiSpec checker for this build". Defense checkers are run standalone through launchers in `results/<run>/` (e.g. `run_invisispec_compound.py`). Proposed fix: an optional `gem5.checker` key in `run_config.jsonc` that overrides the table where it is looked up (`pipeline.py:709, 890, 922`), so `make run` and the sweep watcher stream the cache-event checker like any other run. That is a pipeline change and needs a `wiki/state/COMMANDS.md` update.

## 7. Why these are AMuLeT-only

The full argument is in `wiki/design/docs/AMULET_VS_SIMSPECT_SCOPE.md`. SimSpect checks "did the transmitter fire in the window?". Footprint-hiding defenses let it fire on purpose, so that check would flag every test as true and intended; whether the defense works lives in the footprint, which SimSpect deliberately abstracts away. None of these bugs came out of the normal pipeline: each needed a hand-built gadget plus its own watcher (eviction, stall, I-fetch, cleanup-event correlator). The scope doc uses that as evidence for the boundary.

## 8. Open items

- [ ] Tighten `check_ld_cleanupspec.py` on the five gaps in §5 (first: look at one CleanupSpec trace to settle what `L1_Replacement_OnInstall` reports).
- [ ] Settle what CleanupSpec claims to protect (paper threat model + build grep), §4.
- [ ] Decide on the `gem5.checker` run-config override, §6.
- [ ] Stale text: `AMULET_LOAD_DEFENSES_PROJECT_LOG.md` §4 UV5 bullet still says "empirical demo BLOCKED" (superseded by its own scorecard); `AMULET_BUGS_DETECTION_ACCOUNTING.md` §0 still says "2/9 detected" (superseded by its update boxes).
