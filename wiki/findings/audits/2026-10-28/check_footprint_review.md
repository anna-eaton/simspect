# check_footprint.py adversarial review (2026-10-28)

**Scope.** `STAGE3_gem5/check_footprint.py`, the new `gem5_common.py` pieces (`parse_simspect_line`/`parse_simspect_events`, `parse_pipeview_by_seq`, the `process_one` `wants_trace` branch), and `pipeline.py:_checker_for` + `gem5.checker`/`criterion`/`criterion_actor` env handling (read-only `git diff`). Checked against `wiki/design/TRANSMISSION_CRITERIA_FORMAT.md` ("Criterion JSONs + checker"), `wiki/design/SIMSPECT_HOOKS.md`, and `specs/leakage/{invisispec,speclfb,cleanupspec}.json`. Audit only: no code, config or spec was edited.

**Unit tests.** `python3 STAGE3_gem5/tests/test_check_footprint.py` (pytest is not installed on the Mac; unittest runner used): 24 tests, all OK in 0.31 s.

**Scenario script.** Every scenario below was run against the real `evaluate_trace` using the test file's `Trace` builder: `/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/a48952ff-a51d-4ba4-8a56-a8d24cf0a128/scratchpad/scen.py` (scratch, not committed). The outputs quoted are from that run.

## Verdict up front

The default pipeline path (no `gem5.checker` key) is behavior-identical, and the `process_one` change cannot affect other checkers. The parsers are sound for well-formed traces. The predicates match the doc text, but there are **two classes of possible leak that the checker hides with `decided: true`** (findings 1 and 2), contrary to CLAUDE.md "never hide a possible leak" and to the doc's claim that the net-state cross-check catches attribution bugs. There is also one churn bookkeeping bug that the cross-check happens to catch (finding 3), and several lower-severity issues.

## Findings

### 1. HIGH: events with `seq=-` (or misattributed to a committed seq) are dropped silently, and the CleanupSpec cross-check cannot see them

`is_actor(None)` returns False (`check_footprint.py:217`), so every OBS event with `seq=-` is excluded from all three predicates. Nothing in the record counts them: `n_attributed_events` counts all attributed events, but there is no count or list of unattributed OBS events in W. SIMSPECT_HOOKS.md lists real sources of `seq=-` in observed structures: L2/DIR traffic from the per-line "most recent cause" map when no entry exists, prefetch fills, and misattribution "where a later request to the same line has already started" (which names a committed instruction instead of the squashed one).

The CleanupSpec net-state replay does not help. The reference replay drops only `actor_ids`, so a non-actor event (seq=- or committed seq) is kept in both replays and both agree. The doc's sentence "If this disagrees with the count, there is a pairing or attribution bug" is only true for pairing bugs; attribution errors fool the count and the replay identically.

Concrete failure (scenario S4): squashed load seq 12 fills L1D 0x80 in W; the eviction it causes (victim 0x3000, `cause` = that fill's id) prints with `seq=-` (or with a committed seq 5). Cleanup invalidates 0x80 but never restores 0x3000 (a real UV3-class under-clean). Result for both variants: `leak: False, issued_in_window: False, decided: True, inconsistent: False`. Hidden.

Concrete failure (scenario S2, InvisiSpec): an `L1D:fill` with `seq=-` at tick 2000, inside W, gives `leak: False, decided: True`, and the record has no field mentioning it.

Suggested (needs Anna's decision, since it touches predicate semantics): (a) always emit `n_unattributed_obs_in_window` plus a short list in every record; (b) for an `evict` with `seq=-`, fall back to the `cause` link's fill seq, which is exactly the doc's original `by(cause(e))` definition (TRANSMISSION_CRITERIA_FORMAT.md Layer 2 `evicted`); (c) mark the record `decided: false` when unattributed OBS events exist in W, so they are surfaced rather than counted as no-leak.

### 2. HIGH (semantic): the window gates the event tick, so a squashed load's late footprint is never a leak in the `exists` form

`actor_event_in_window` uses `in_W(ev["tick"])` (`check_footprint.py:225-228`). A footprint event that lands after the branch resolves (or after `fnc_retire`) is reported only in `footprint_outside_window`, even when its actor is a squashed load. For footprint defenses the leak is the state left behind, so a squashed in-flight load whose response fills L1D after the squash is the defense failing, not a non-event. This is the analogue of the check_ld rule "squash timing NEVER gates (a load that obtained data then got squashed still leaked)".

Concrete failure (S1, SpecLFB): squashed seq 12 fills L1D 0x40 at tick 6000 (after `fnc_retire` 5000, squash at 3000): `leak: False`. S1b: fill at 2800, after the branch's resolution `prop_tick` 2500 but before the squash: `leak: False`. Realistic when the miss latency is longer than the configured unresolved stall. CleanupSpec has the same gap on the `under_clean` gate (doc open item 3). Suggested: gate on the actor's issue being in W (seq's `issue` tick from `parse_pipeview_by_seq`, or the first event of that seq), not on each event's tick. This is a criterion change, so it needs Anna's decision; until then, results should be read together with `footprint_outside_window`.

### 3. MEDIUM: churn pairs with stale `live` entries (caught only by the cross-check)

`live[(s, ℓ)]` is cleared only by `cleanup_inv` (`:366`). A non-actor `evict` of ℓ or a coherence `inv` of ℓ leaves the actor fill "live". A later actor evict of a refilled committed copy of ℓ is then cancelled as churn instead of counted as `evicted`.

Concrete failure (S3): seq 12 fills 0x40 (W); committed seq 5 evicts 0x40, then refills it; squashed seq 13's fill of 0x80 evicts 0x40 (the committed copy); cleanup never restores 0x40. Per-line: `0x40 installed 1, churn 1, evicted 0, d_install 0, d_victim 0`, so the count says no leak. The replay disagrees, so the record ends `leak: False, issued_in_window: True, decided: False, inconsistent: True`. Not hidden, but `terms_fired` is empty and the cause is misreported as a checker inconsistency. Fix: pop `live[(s, victim)]` on every evict and clear on every `inv`, actor or not.

### 4. MEDIUM: the actor set has no instruction-kind filter

`parse_pipeview_by_seq` drops the disassembly, so loads, stores and ALU ops are all actors. In `spec` mode a squashed store's `DTLB` fill or `repl_touch` counts as an InvisiSpec leak. In `futuristic` mode every instruction not at the ROB head is an actor, so a committed store's or load's DTLB `repl_touch` at translation counts. Scenario S5, verified: a retired instruction (seq 21, any kind) has a `DTLB:repl_touch` at tick 900, while the older seq 20 retires at 1000. Result: `leak: True, terms_fired: ['footprint']`. InvisiSpec's USL definition covers loads. Whether the paper's D-TLB claim covers stores needs checking against the paper; I did not verify this from the source. At minimum, the offending groups should carry `pc`/disasm so triage can see whether the offender is the litmus test's `xmit` (`_group` keeps seqs but not PCs). Note: `xmit_pc` is passed to `check_footprint` and never used, so a hit can come from any wrong-path instruction, not the model's transmitter.

### 5. LOW: smaller predicate and window issues

- `window_sqs` uses `a <= fnc_retire` (inclusive) while `in_W` is strict `<`, and it does not apply `branches_unresolved` (`:335`). This is harmless in practice but inconsistent with the doc.
- The `under_clean` gate `foot_inw` (`:382`) mixes the install and victim terms. If a line's in-W event is a properly restored victim and its uncleaned install is out of W, it is flagged. This errs toward over-reporting.
- The side-effect rule excludes an L1D evict whose `cause` has no fill inside any undo window. If that rollback-space replacement evicts a spec-installed line, the line looks uncleaned and the result is a false `under_clean` (flagged inconsistent).
- With an `undo` window that never sees `cleanup_done`, the window extends to `sim_end`. That is correct, but any later unrelated `cleanup_*` with `sq=-` attaches to the first open window by tick (`undo_sq_of` fallback).
- The actor mode silently falls back to `default` (`spec`) when the scheme name is numeric, e.g. `--scheme=3`, or unknown. A Futuristic run configured by number would be evaluated as Spectre. The chosen mode is recorded (`actor_mode`, `scheme_name`), so it is visible.
- Futuristic `vp` case (ii) is missing (already in the doc's open item 2).

### 6. Parse robustness: OK, with notes

- `parse_simspect_line` raises on a malformed field, and `process_one`'s `except Exception` turns that into `status: error` for the test. It does not crash the batch, and no line is dropped silently. A trace truncated mid-line (timeout or disk safety net) either errors or, if cut inside a hex value such as `line=0x3d`, parses as a wrong address. That affects one event only.
- `int(v, 0)` rejects leading-zero decimals. gem5 prints none, so this is fine.
- `parse_pipeview_by_seq` drops a record whose fetch seq field fails to parse (`cur=None`). A retired instruction can then look unretired, so its events could be counted as speculative: a false positive, never a hidden leak.
- A squashed in-flight load with no fetch record is handled correctly when it has any event before the squash, or when any younger record exists (`max_seq_by` uses event ticks plus fetch ticks). Corner case: if the load's only events come after the squash and no younger instruction was recorded before the squash, `squash_of` returns None and its footprint is dropped. This is rare.
- Sort `(tick, id)` restores fill-before-evict at equal ticks, since a fill id is lower than its evict id (`inv_uv1`: cause 1458, evict id 1459).
- `run_batch` uses `ThreadPoolExecutor`, so the module globals `_CRIT`/`_ACTOR_OVERRIDE` are shared. There is no spawn/forkserver hazard.

### 7. Default path and other checkers: unchanged

- `_checker_for(gem5_cfg, kind)` returns `_KIND_TO_CHECKER.get(kind, _DEFAULT_CHECKER)` when `gem5.checker` is absent or falsy. `gem5_cfg` is bound in all four call sites (`pipeline.py:712, 830, 1087`, used at 749/930/962/1111). The new `_build_gem5_env` blocks are all gated on their keys.
- `process_one` calls the old 8-argument signature unless `check_fn.wants_trace` is truthy, and only `check_footprint` sets it. The trace is read before the `finally` rmtree.
- Minor config pitfalls: `gem5.criterion` without `gem5.checker` is silently ignored (check_ld runs). A `checker` given with a path prefix, e.g. `STAGE3_gem5/check_footprint.py`, would double-prefix (`stage3 / script`) and also skip the missing-criterion guard, which compares the literal `"check_footprint.py"`.
- A pre-hook binary gives `status: warn, issued_in_window: None`. Sweep aggregation turns that into `issued_in_window: False, status: error` (`pipeline.py:524-546`), so it shows up as an error, not as a clean no-leak.
- Side effect (build-level, not this diff): on hooked builds, every checker's trace now carries simspect lines, so traces are larger and the disk safety-net limit may need rechecking.

## Open for Anna

1. Should unattributed OBS events in W make a record undecided (finding 1)? Should the evict actor fall back to `by(cause(e))`?
2. Should the window gate the actor's issue rather than each event's tick (finding 2)? That would make late post-squash fills count for InvisiSpec and SpecLFB.
3. Should actors be loads only (finding 4)? This needs the paper text on whether stores' D-TLB effects are covered.
