# Transmission criteria: formal format (PROPOSAL, awaiting Anna)

**Status:** format accepted with changes, 2026-10-28 (see Decisions). **Criterion JSONs and the checker are built: see "Criterion JSONs + checker" at the end.** Hooks being built; criterion JSONs wait on the paper audit (`wiki/findings/mdsToRead/FOOTPRINT_DEFENSES_PAPER_AUDIT.md`). Covers InvisiSpec, SpecLFB, and CleanupSpec, the three footprint-hiding defenses. The per-defense protection scopes below are **placeholders from memory, unverified**: each must be filled from the defense's paper (quoted with its section) before any criterion JSON is final.

## Decisions (Anna, 2026-10-28)

- **Scope = exactly the caches the defense's paper says it protects.** Each criterion JSON also carries a note of which caches AMuLeT checks for that defense, kept separate from the scope.
- **Speculative definition: pinned.** For now `spec` stays what the tests realize (squashed, after the last committed instruction). The paper audit checks whether the STT_6 base model's speculation contract matches each paper before this is revisited.
- **Intra-window churn (old Q3): agreed.** CleanupSpec counts net presence changes: a speculative fill of a line followed by a speculative-caused eviction of the same line inside `W` cancels out.
- **Interface = strictly the pipeline output.** The hooks ("SimSpect hooks") print under the existing `O3PipeView` debug flag, so `--debug-flags=O3PipeView` alone gives the checker everything. Line form: `O3PipeView:simspect:<tick>:<struct>:<kind>:line=0x..:seq=..:pc=..:victim=..:cause=..:sq=..:id=..`. This replaces the separate `SimSpectCache` flag and `SSEV` line below. All three builds (InvisiSpec, SpecLFB, CleanupSpec) are rebuilt with the hooks each one needs. Hook details: `wiki/design/SIMSPECT_HOOKS.md`.

**Update 2026-10-28:** Layer 1 is built, with a different line format: events print under the existing `O3PipeView` flag as `O3PipeView:simspect:...` lines (no `SimSpectCache` flag, no `SSEV` prefix), because the only interface is the pipeline trace. The built format, sites, mapping and gaps are in [`SIMSPECT_HOOKS.md`](SIMSPECT_HOOKS.md); that page supersedes the Layer 1 section below.

## Why the current JSONs are wrong

- `specs/defense_units.json` gives InvisiSpec and CleanupSpec `leakage: stt.json`. That is STT's contract ("the transmitter executed in the window"). For these three defenses the transmitter is *allowed* to execute; what matters is its footprint in the structures the defense protects.
- `specs/leakage/speclfb.json` is a note ("first spec load unprotected"). It describes one bug, not a criterion.
- `specs/transmitter_criteria.json` is keyed by transmitter kind (`ld`/`br_x`/…). The footprint defenses need a criterion keyed by **defense**, stated over **cache events on lines**, not over one pipeview tick.
- `check_ld_cleanupspec.py` accepts any cleanup event as "cleaned", never checks victims, checks L1 only, and doesn't check the load was squashed (`AMULET_THREE_DEFENSES_EXPLAINER.md` §5).

## Layer 1: the event trace (what the rebuilt gem5 emits)

One new debug flag, `SimSpectCache`, prints one normalized line per event, interleaved with `O3PipeView` in the same trace:

```
<tick> SSEV <struct> <kind> line=<0xLINE> seq=<sn|-> pc=<0xPC|-> sq=<squash_id|-> cause=<event_id|-> victim=<0xLINE|-> id=<event_id>
```

- `struct`: `L1D`, `L1I`, `L2`, `LLC`, `DIR`, plus the defenses' own buffers (`SB` for InvisiSpec's speculative buffer, `LFB` for SpecLFB). Only structures in a defense's `observation.structures` matter for its criterion, but the hook prints all of them so one trace serves any criterion.
- `line`: the physical line address (paddr >> 6 << 6). Every event is tagged by line.
- `seq`: the seqNum of the dynamic instruction that caused the event, carried on the request. This is what lets us tie a fill to *the squashed load* rather than guess from same-tick coincidence. (Needs checking per build that the Ruby/classic request carries the seqNum through; if it doesn't, the hook threads it.)
- `cause` / `victim`: an eviction names the fill that caused it (`cause`) and the line it removed (`victim`), so a victim is attributable to the speculative fill that pushed it out.
- `sq`: for cleanup events, which squash they belong to.

Event kinds (closed list; the hook emits exactly these):

| kind | meaning |
|---|---|
| `fill` | line allocated into `struct` (any miss fill, prefetch fill, or install-on-expose) |
| `evict` | line removed by replacement (`victim=` set, `cause=` the fill) |
| `inv` | line removed by coherence invalidation |
| `coh` | coherence state change without presence change (e.g. M→S downgrade) |
| `repl_touch` | replacement-state update (LRU bits) on a hit |
| `buf_fill` / `buf_release` | entry into / out of `SB` or `LFB` |
| `expose` / `validate` | InvisiSpec's visibility-point re-access |
| `cleanup_inv` | CleanupSpec invalidates a spec-installed line (`Inv_CLEANUP`, `InvL2_CLEANUP`) |
| `cleanup_restore` | CleanupSpec re-installs an evicted victim (`Load_ROLLBACK`) |
| `cleanup_skip` | CleanupSpec decided no undo was needed (`Skip_ROLLBACK`, L1-hit path) |
| `cleanup_drop` | cleanup request dropped or in-flight-cancelled (`Drop_Load_Cleanup_Inflight`, `Inflight_CLEANUP_reqs`) |
| `cleanup_done` | CleanupSpec finished all undo work for squash `sq` (the quiescence point) |
| `squash` | the core squashed from `seq` onward, `sq` = new squash id |

These are print-only hooks (DPRINTFs at the existing transition points). No defense logic changes. Each is recorded in `specs/gem5_hooks.json` as an `observation`-category source hook.

## Layer 2: the criterion JSON (one per defense, `specs/leakage/<defense>.json`)

```jsonc
{
  "schema": "simspect.transmission_criterion/v1",
  "defense": "CleanupSpec",
  "builds": ["amulet-cleanupspec"],
  "source": {                                   // provenance: every scope claim is quoted
    "paper": "quail/sources/papers/<file>.pdf",
    "claims": [{"section": "§…", "quote": "…", "supports": "observation.structures"}]
  },
  "observation": {                              // what the defense claims to hide = what we check
    "structures": ["L1D", "L2"],
    "granularity": "line",
    "state": ["presence"]                       // presence | coherence | replacement
  },
  "actors": {                                   // which instructions count as speculative
    "spec": "squashed(i) ∧ lc_seq < i.seq"     // or the paper's own unsafe definition
  },
  "window": {
    "footprint": {"from": "lc_retire", "to": "fnc_retire", "branches_unresolved": true},
    "undo":      {"from": "squash(sq)", "to": "cleanup_done(sq) | sim_end"}   // CleanupSpec only
  },
  "terms":  { … named event sets, see below … },
  "leak":   "…predicate over terms…",
  "not_covered": ["unXpec: cleanup size is secret-dependent; relational, needs a run pair"]
}
```

`terms` and `leak` use a small fixed vocabulary so the checker is generic (one checker reads any criterion JSON):

- `E(kind, struct∈OBS)` is the set of events of that kind in observed structures.
- `by(e) ∈ spec`: the event's `seq` is a speculative actor.
- `in(e, window.footprint)`, `in(e, window.undo)`.
- `#{…}` is a count, grouped `per (struct, line)`.

## The three criteria, stated

Let `OBS` be the defense's observed structures, `W = (lc_retire, fnc_retire)` with branches unresolved, and `spec` the defense's speculative instructions.

**InvisiSpec.** A speculative load may fill only `SB`. Leak iff some event in an observed structure is caused by a speculative instruction inside the window:

`leak ⇔ ∃ e ∈ E({fill, evict, inv, coh}, OBS) : by(e) ∈ spec ∧ e.tick ∈ W`

(`repl_touch` is included only if the paper claims replacement state is hidden. This is a paper question.)

**SpecLFB.** Same form. The defense holds an unsafe load in the `LFB` instead of filling L1D, so `buf_fill` on `LFB` is allowed and only `OBS` events count:

`leak ⇔ ∃ e ∈ E({fill, evict}, OBS) : by(e) ∈ spec ∧ e.tick ∈ W`

`spec` here is the paper's "unsafe" definition, not SpecLFB's own `isUnsafe` flag; UV6 is exactly that flag being wrong.

**CleanupSpec.** Speculative fills are allowed. The leak is the gap between what speculation did and what cleanup undid, per line. The footprint must happen in `W`, but the undo may happen after it, up to `cleanup_done` for that squash. This is the only one of the three where events outside the window count.

For each `(s, ℓ) ∈ OBS × lines`:

- `installed(s,ℓ) = #{ e ∈ E(fill, s) : e.line=ℓ ∧ by(e) ∈ spec ∧ e.tick ∈ W }`
- `invalidated(s,ℓ) = #{ e ∈ E(cleanup_inv, s) : e.line=ℓ ∧ e.tick ∈ undo }`
- `evicted(s,ℓ) = #{ e ∈ E(evict, s) : e.victim=ℓ ∧ by(cause(e)) ∈ spec ∧ e.tick ∈ W }`
- `restored(s,ℓ) = #{ e ∈ E(cleanup_restore, s) : e.line=ℓ ∧ e.tick ∈ undo }`

`leak ⇔ ∃ (s,ℓ) : installed − invalidated ≠ 0 ∨ evicted − restored ≠ 0`

A positive difference is too little cleanup (UV4, UV3). A negative difference is too much (UV5). `cleanup_skip` and `cleanup_drop` count toward neither term: a skipped or dropped undo leaves the footprint uncleaned. They are reported alongside the result so you can see why.

**Cross-check (also emitted, not the criterion):** replay `fill`/`evict`/`inv`/`cleanup_*` to get each observed structure's line set at `lc_retire` and at `cleanup_done`. Every difference must be explained by committed instructions. If this disagrees with the count, there is a pairing or attribution bug in the hook or the checker, and the result is flagged instead of decided.

## Open questions for Anna

1. **Protection scope per paper.** Which structures (L1D only? L1D+L2? LLC? directory?) and which state (presence only, or also coherence and replacement state) does each paper claim? I'll fetch the three papers into `quail/sources/papers/` and fill `source.claims` with quotes. My memory says InvisiSpec covers the whole cache hierarchy plus coherence, SpecLFB covers L1D, and CleanupSpec covers L1+L2 presence with randomization in place of LRU rollback. All of that is unverified.
2. **`spec` definition.** Should it be "squashed and after the last commit" (what our tests realize), or the paper's own threat model (InvisiSpec has Spectre and Futuristic variants)?
3. **CleanupSpec intra-window churn.** If a speculative fill of ℓ is itself evicted by a later speculative fill before squash, cleanup has nothing to invalidate. Under pure counting that looks like too little cleanup. Proposal: count net presence changes (a fill followed by a spec-caused evict of the same line inside `W` cancels out).
4. **The unified hook.** Is one `SSEV` line format across Ruby and classic builds acceptable, versus parsing each build's native `ProtocolTrace`/`Cache` output? The unified hook is cleaner and gives true seqNum attribution, but it means rebuilding all three builds.

## Criterion JSONs + checker (built 2026-10-28)

**Status:** implemented. Criteria `specs/leakage/invisispec.json`, `specs/leakage/speclfb.json`, `specs/leakage/cleanupspec.json` (schema `simspect.transmission_criterion/v1`), one generic checker `STAGE3_gem5/check_footprint.py`, parser `gem5_common.parse_simspect_events` / `parse_pipeview_by_seq` (additive), tests `STAGE3_gem5/tests/test_check_footprint.py`. Scope per Anna's 2026-10-28 decisions: each criterion covers exactly what its paper says it protects, with every claim quoted with its page in `source.claims` (taken from `FOOTPRINT_DEFENSES_PAPER_AUDIT.md` §2-§4 and §7, and re-checked against the PDF text in `~/Documents/quail/sources/papers/`). The line format is the one in [`SIMSPECT_HOOKS.md`](SIMSPECT_HOOKS.md), which supersedes Layer 1 above.

**Fields of a criterion JSON.** `source.claims` (section, page, quote, which field it supports); `observation` (`structures` = OBS, `granularity`, `state`, `allowed_structures`/`allowed_kinds` = the defense's own buffers, `ignored_structures`, CleanupSpec `by_design`); `actors` (`modes` with a formal `text` and a fixed `impl` id, `default`, `select_by_scheme`); `window` (`footprint`, plus `visibility` for InvisiSpec and `undo` for CleanupSpec); `terms`; `leak` (`form` + `text`); CleanupSpec also `undo_obligations`, `balance_scope`, `cross_check`; `not_covered` (limits of what we can observe or generate); `out_of_scope` (what the paper scopes out, each quoted and tagged "scoping problem of the defense, not an implementation bug we catch"); `amulet_checks` (what AMuLeT observes, informational only, never read by the predicate). `speclfb.json` keeps its old one-line content under `_superseded_note`.

**Actors and windows.** `spec` (`impl: squashed_after_lc`, pinned): the event's `seq` never retired, is younger than a `ROB:squash` seq and was allocated before that squash (seqs are monotone, so "allocated by tick t" = seq ≤ the largest seq seen by t; this also covers in-flight squashed loads that have no fetch record), and is younger than the last committed instruction. Its window `W` is check_ld's: `lc_retire < tick < fnc_retire` (0 → ∞, no lc → no lower bound) with every annotated unresolved branch still unresolved (`check_branch_resolutions`). `futuristic` (InvisiSpec only, `impl: before_visibility_point`): any instruction `i`, and an event counts iff `tick < vp(i)`, with `vp(i)` = the earlier of i's first `expose`/`validate` and the tick i reached the ROB head (latest retire of an older retired instruction); never-exposed, never-retired instructions have `vp = ∞`. This follows InvisiSpec p4/p5 ("a USL reaches its visibility point only when: (i) it is not speculative anymore because it is at the head of the ROB, or (ii) it is still speculative but cannot be squashed anymore. At that point, the hardware issues a validation or an exposure"). The mode is picked from the last `--scheme=<Name>` in `extra_args` via `actors.select_by_scheme` (`FuturisticSafeInvisibleSpec` → `futuristic`), or forced by run config `gem5.criterion_actor`.

**The three predicates as implemented.**

- InvisiSpec (`form: exists`): `leak ⇔ ∃ e ∈ E({fill, evict, inv, coh, repl_touch}, {L1D, L2, DIR, DTLB}) : actor(e) ∧ e ∈ window(mode)`. `SB`/`LLCSB` buffers and `expose`/`validate` are allowed; MSHR/TBE buffers, L1I and ITLB are ignored (out of scope).
- SpecLFB (`form: exists`): `leak ⇔ ∃ e ∈ E({fill, evict}, {L1D, L2}) : spec(e.seq) ∧ e ∈ W`. `LFB` buffer events are allowed; `repl_touch` is excluded (hits and replacement metadata are out of scope, §9 p643).
- CleanupSpec (`form: per_line_balance`): for each `(s, ℓ)` in `{L1D, L2}` × lines, `d_install = installed − churn − invalidated` and, for L1D only, `d_victim = evicted − churn − restored` (L2 victims are benign by design). `installed`/`evicted` count actor `fill`s (key `line`) and `evict`s (key `victim`) over the whole run, so cleanup of an actor's out-of-window footprint still pairs; `invalidated`/`restored` count `cleanup_inv`/`cleanup_restore` whose `sq` is a squash at or after the last committed instruction. Churn: an actor evict whose victim is a still-live actor install cancels both. `cleanup_skip`/`cleanup_drop` never count as undo (listed in `skip_drop`). Two cleanup side effects are excluded from the count (the L2/DIR fill of a line just restored, and an L1D evict inside an undo window whose `cause` matches no fill). `under_clean ⇔ d > 0` with at least one of that line's footprint events in `W`; `over_clean ⇔ d < 0` with the cleanup belonging to a window squash. `leak ⇔ ∃ (s, ℓ) : under_clean ∨ over_clean`. Out-of-window imbalances are reported, not counted.

**CleanupSpec net-state cross-check.** The checker replays `fill`, `evict`, `inv`, `cleanup_inv`, `cleanup_restore` per structure to the end of the run twice: actual (actor L2 victim removals skipped) and reference (all actor footprint, cleanup and side-effect events dropped, i.e. "as if the transient loads did not access the cache", CleanupSpec p2). Each `(s, ℓ)` that differs is a net leak unless all its actor footprint is outside `W`. If the set of leaking `(s, ℓ)` differs from the count's, the record gets `inconsistent: true`, `decided: false`, and `issued_in_window = count ∨ net`, so a possible leak is never hidden.

**Records.** Every record keeps the `process_one` fields plus `issued_in_window` (= `leak`), `terms_fired`, `offending` (struct, line, event ids, seqs; Futuristic also `vp` with its basis), `footprint_outside_window`, `actor_mode`, `scheme_name`, `lc_seq`, join stats (`n_unjoined_seqs`), and for CleanupSpec `per_line` (installed / invalidated / evicted / restored / churn / d), `skip_drop`, `cleanup_side_effects`, `net_state`, `inconsistent`. A trace with no simspect lines (a pre-hook binary) gives `status: warn`, `issued_in_window: null`.

**Pipeline hookup.** Run config `gem5.checker: "check_footprint.py"` + `gem5.criterion: "specs/leakage/<defense>.json"` (optional `gem5.criterion_actor`) sends every test to the footprint checker (`pipeline.py:_checker_for`; `_build_gem5_env` exports `SIMSPECT_CRITERION` / `SIMSPECT_CRITERION_ACTOR`). Without those keys the per-kind table is used as before. Commands: [`wiki/state/COMMANDS.md`](../state/COMMANDS.md).

**Verified on real hooked traces** (copied from cafe2 `/work/amulet/simspect_hooks_verify/`, now fixtures in `STAGE3_gem5/tests/fixtures/`): InvisiSpec UV1 (`inv_uv1`) leak (L1D evicts of 0x39c0/0x3980/0x3b40 by squashed loads 576/573/566); SpecLFB UV6 shape (`lfb_uv6x`) leak (L1D + L2 fills 0x2000, 0x2100 by seqs 28, 29); CleanupSpec `cln_uv5clean` no leak (L1D 0x4000 installed 1 / invalidated 1, victim 0x3000 evicted 1 / restored 1, L2 0x4000 1 / 1; replay agrees); CleanupSpec UV4 split (`cln_uv4split`) leak (L1D and L2 0x1000, 0x1040 installed with `cleanup_skip` and no `cleanup_inv`; replay agrees); InvisiSpec Futuristic (`inv_fut`) leak.

**Open for Anna.** (1) In both InvisiSpec traces, squashed (and, under Futuristic, committed pre-visibility) loads produce `DTLB:repl_touch` and `L2:coh`/`DIR:coh` events. The paper claims D-TLB replacement state and coherence state (p3, p5, p9), so these count as leaks under the agreed scope. They may be real deviations or attribution artifacts (TLB attribution = most recent translate; L2/DIR seq = per-line most-recent-cause map). They need triage before campaign hit counts are read. (2) The Futuristic `vp` misses case (ii) when a load becomes non-squashable before it issues, since no expose is emitted then. Such a load would be flagged. (3) The CleanupSpec balance counts late (post-squash) installs by squashed loads (paper p6, EpochID), and its `under_clean` gate still requires a footprint event in `W`.
