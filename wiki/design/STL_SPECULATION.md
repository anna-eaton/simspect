# Store-to-load (STL) speculation: model, concretization, gem5 hooks, window check

*Living doc, overwrite-in-place. Written 2026-10-28. Paper table row: [`SPEC_PRIMITIVE_INSTANCES.md`](SPEC_PRIMITIVE_INSTANCES.md) (h, i).*

## Status

| Piece | State |
|---|---|
| Model `STAGE1_alloy/models/STT_6_stl.als` | written (Anna approved new `.als` files), SAT, 500 instances enumerated locally in a few seconds |
| Concretization, branch mode `stl_bypass` | written + tested: 500/500 instances concretize and compile to x86; the existing modes are byte-identical before/after (120/120 STT_6 `.ll` + `.ann.json`) |
| Harness flags (`gem5.stl_*` → `SIMSPECT_STL_*` → `--stl-*`) | written; off unless a config sets `gem5.stl_ann_enable` |
| gem5 hooks `gem5-hooks/stl/` | written, anchors verified on upstream gem5 v22.0.0.2, **not built into any binary**, not compiled |
| Window checker | proposed below, not written |

## The primitive: a false-negative alias prediction

The store's address is unresolved when a younger load to the same address issues. The memory-dependence predictor says "no alias", so the load does not wait. It reads the stale value (the store's queue entry has no address yet, so the forwarding scan skips it), and its dependents, the transmitter among them, run on that value. When the store's address resolves, the LSQ sees that a younger load to the same address already executed (a memory-order violation) and squashes from that load. The window is load issue → that squash. This is Spectre v4 (speculative store bypass), and the analog of an unresolved, mispredicted branch: the bypass path only ever runs speculatively.

The false-positive direction (predict alias, addresses differ) opens no window in gem5: O3's store sets only make the load wait; there is no predictive forwarding. It is kept as a negative control (`--stl-alias-pred=alias`).

STT covers this only in its Futuristic threat model. STT p5: "In the Spectre model, an instruction has reached the visibility point if all older control-flow instructions have resolved. In the Futuristic model, an instruction has only reached this point if it cannot be squashed." STT §6.4.2 frames memory-dependence speculation as "simply a prediction of the store-to-load forwarding implicit branch". Source: `~/Documents/quail/sources/papers/yu-2019-stt.pdf`.

## Generation: `STT_6_stl.als`

A copy of `STT_6.als`, with changes only in the STL block and the defense block. `STT_6.als` is untouched. Every instance has an unresolved store S, a load L after it that reads S's `Mem_s`, and L's value flowing to the transmitter. In the 500 enumerated instances, 500/500 have the transmitter fed by a load of S's location, which the state-minimality clause (`all s: State | secure[RS->s]`) forces. 39/40 of a first sample have no committed instructions (S is the first non-committed).

```diff
+fun has_unresolved_strs_p[p: PTag->univ] : Instruction {
+	((unresolved_p[p] & Stores).(^(spo_p[p]))) // all the instructions that come after a store with an unresolved address
+}
+fun no_unresolved_strs_p[p: PTag->univ] : Instruction {
+	i_p[p] - has_unresolved_strs_p[p]
+}
+
+// control-flow speculation is off in this model
+fact stl_no_unresolved_branches {no (unresolved & (Branchxs+Branchns))}
+
+// true alias (the false-negative prediction): some load at or before the xmit
+// reads the memory state an older unresolved store writes (rf = most recent
+// writer, so no intervening store to that state)
+fact stl_alias_pair {
+	some s: unresolved & Stores, l: uncommitted & Loads |
+		some (s.outmem.rf & l.inmem) and l in xm + xm.^(~spo)
+}
 ...
-fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
+fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_strs_p[p]}
 ...
-	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate
+	s - (Loads & no_unresolved_strs_p[p] & i).inmem.opstate // loads with no unresolved-address store before them remove their inmem state from the protset
```

- **Speculation source.** `has_unresolved_strs_p` mirrors `has_unresolved_brs_p`: everything after a store whose address is unresolved (`isresolved` on a store = its address is known).
- **Contract.** Uncommitted and after an unresolved store, in place of after an unresolved branch.
- **Protset propagation.** A load with no unresolved store before it declassifies its location, mirroring the branch rule.
- **No control-flow speculation.** All branches are resolved, as asked. The transmitter branch keeps the existing xmit override in concretization: it is the observable, not the speculation source.
- **True alias.** The fact is the generation half of "false negative": without it, a load past an unresolved store is speculative under the contract but never squashed in gem5, and the value it reads is the architectural one.
- **Minimality.** The existing `all i: (unresolved - first_uncommitted) | secure[RR->i]` already ranges over stores, so every unresolved store must matter. Unresolved loads or ALU ops can't appear except as the boundary instruction.

To check against the papers (Anna, 2026-10-28: "we will have to read the papers again"): whether STT's Futuristic contract marks every instruction after an unresolved store as unsafe (what this encodes), or only loads that may alias it.

## Concretization: branch mode `stl_bypass`

Turned on only by putting `"stl_bypass"` in `speculation.branch_modes` (or `batch_generate.py --mode stl_bypass`). The other modes never call the new code. Output goes to its own per-mode tree, `testsets/<model>/stl_bypass/`, so it is a parallel pipeline.

- `pass2_5_specify_branches` accepts the mode and refuses an instance with an unresolved non-xmit branch (STT_6 XMLs are rejected, 3/3 tried). Resolved branches become `correctly_not_taken` exactly as before.
- New `pass2_6_specify_stl` pairs each unresolved store S with its bypass load L: the first uncommitted load after S that reads S's `Mem_s` before another store writes it (the model's most-recent-writer rule). Pairs are tags on the instruction records, because `pass_interleave` renumbers PCs. A missing pair raises, so the test is skipped and logged.
- **Making the alias real at runtime.** A load or store with a specified `inaddr` is emitted as `probe_mem + reg` and ignores its `Mem_s` slot, so model-level aliasing isn't guaranteed. When neither S nor L has `inaddr`, they share the `mem_base` slot and nothing changes (487/500). Otherwise (13/500) S is re-emitted at L's runtime address, relative to L's base and keeping S's own index register: `movq src, D(base, r_S, 1)` or `movq src, D(base)`. D comes from a small architectural evaluator over the straight-line program (`_stl_arch_values`). It mirrors the emitted asm, evaluates twice to check L's address doesn't depend on the re-targeted store, and raises on anything it can't evaluate exactly. Loads and stores are already inline asm, so LLVM cannot fold the store→load.
- `.ann.json` gains `"stl_annotations": [{store_pc, load_pc, mem_atom, mode}]`, and `compile_annotate.py` adds absolute `store_addr` / `load_addr` (the pc marker sits on the `movq` itself).

## gem5 hooks (`gem5-hooks/stl/`)

`apply_stl_hooks.py <gem5_root> [--dry-run]` inserts both hooks by anchor string, not line number (Recon's o3 files are heavily modified). It is idempotent (marker `SimSpect-STL`), writes nothing unless every anchor matches exactly once, and saves originals as `<file>.pre-stl`. `stl_hooks_vs_gem5_v22.0.0.2.diff` is the reference diff from applying it to upstream gem5 v22.0.0.2, which is the version whose `iew.cc` line numbers match Recon's (`recon-modded_src.diff` hunks at `iew.cc:1247`).

| Flag | Hook | Where |
|---|---|---|
| `--stl-ann-file <ann.json>` | supplies the (store_addr, load_addr) pairs | `configs/example/se.py` → CPU params |
| `--stl-store-stall-cycles N` | **store address-generation hold.** An annotated store is sent back to the mem-dep replay list (`IEW::rescheduleMemInst`, the LSQ's own path for a load it can't execute yet) instead of computing its address, and an event replays it N cycles after it first issued. An early replay re-defers it. | `cpu/o3/iew.{hh,cc}` |
| `--stl-alias-pred {no_alias,alias,off}` | **prediction override** for the annotated loads: `no_alias` ignores the store-set answer (false negative, the primitive); `alias` primes the store set at the store's insert, so the load waits (false-positive control); `off` = unmodified | `cpu/o3/mem_dep_unit.{hh,cc}` |

Why the existing pieces weren't reused: the recon-modded store "resolve stall" placeholder (`iew.cc` ~1247) fires *after* `executeStore`, so the address is already known. The unwired `AnnotatedStoreSet` (`store_set_annot.cc`) primes the store set in the load's `checkInst`, after the store has already been inserted into the LFST without a set ID, so the forced dependence would miss the first dynamic instance.

Print-only trace lines, under the existing `O3PipeView` flag in the [`SIMSPECT_HOOKS.md`](SIMSPECT_HOOKS.md) format:

```
O3PipeView:simspect:<tick>:STL:stl_hold:line=-:seq=<S sn>:pc=<S pc>:victim=-:cause=-:sq=-:id=-
O3PipeView:simspect:<tick>:STL:stl_release:line=-:seq=<S sn>:pc=<S pc>:...        # hold over; S computes its address now
O3PipeView:simspect:<tick>:STL:pred_no_alias:line=-:seq=<L sn>:pc=<L pc>:...:cause=<dep sn>
O3PipeView:simspect:<tick>:STL:mem_order_squash:line=-:seq=<L sn>:pc=<L pc>:...:cause=<S sn>   # every violation, annotated or not
```

Harness: run config `gem5.stl_ann_enable`, `gem5.stl_store_addr_stall_cycles`, `gem5.stl_alias_pred` → `pipeline._build_gem5_env` → `SIMSPECT_STL_*` → `gem5_common.run_gem5` appends `--stl-ann-file=<test>.ann.json --stl-store-stall-cycles=N --stl-alias-pred=X`. Example config: `runconfigs/run_config_STT_6_stl.jsonc`. Its D = 5000 mirrors `sweep.unresolved_stall_cycles` in `run_config_STT_6.jsonc`.

## Proposed window check (not built)

Per test: S, L and the xmit X are known by address from the ann. All times come from one pipeview trace (`O3PipeView` + `LSQUnit`).

1. **The primitive fired: validity gates.** If any gate fails, the test is `stl_invalid` with the reason, counted neither as leak nor as no-leak.
   - `stl_hold` for S's first dynamic instance (else the hooks aren't in this binary).
   - With `no_alias`, a `pred_no_alias` line for L.
   - L's first dynamic instance executes (LSQUnit "Executing load") before `stl_release`: the bypass happened.
   - Its fate isn't `store_forward`.
   - A `mem_order_squash` with `seq` = that L instance and `cause` = S: the alias was real. No squash means a concretization bug.
2. **Which X counts.** Only X's *first* dynamic instance: younger than S, at or after L's first instance, and squashed by that `mem_order_squash`. After the squash, L and X re-execute with the right value, and that replay is architectural. That differs from the branch checkers, which match the xmit by PC.
3. **Window.** `t(stl_hold) ≤ signal < t(stl_release)` is the strict contract bound: X transmits while S's address is unresolved. Also record `signal < t(mem_order_squash)`, the transient bound; the two differ by a cycle or two. Don't reuse the branch window `lc_retire < signal < fnc_retire`. There is usually no committed instruction (no `lc`). `fnc` = S retires after the squash and the commit stall, so the replayed X would land in-window: a false positive.
4. **Signal and gate per transmitter kind.**
   - For `ld`, unchanged: the LSQ "Executing load" tick plus the data-obtained gate (`check_ld._xmit_cache_fate` + pipeview `complete`), keyed by X's instance seq, not by PC.
   - For `br_x`, the redirect tick check_br already uses, now with the window enforced (closing check_br's known gap for these tests).
   - Implement this as one shared `stl_window(trace, ann)` in `gem5_common.py` that `check_ld` / `check_br` call when `ann` has `stl_annotations`, not as a new checker family.
5. **Controls, run before reading any STT hit.**
   - Unsafe baseline (scheme 0) + `no_alias`: nearly every valid test should leak, which shows the primitive works.
   - Any scheme + `alias`: L waits for S, no squash, so 0 leaks. A hit here is a checker bug.
   - Hold sweep, e.g. D ∈ {0, 50, 500, 5000}: at D = 0 the bypass should mostly vanish.
6. **Bucketing.** `stl_invalid` reasons become an error-bucketing diagnostic in the run's `diagnostics/`, per the diagnostics rules.

## Open

- **Which build gets the hooks first, and how?** `/work/gem5-recon-modded` is the STT_6 build (scheme 2 = STT), but other sessions run sweeps on that binary. Build a copy (e.g. `/work/gem5-recon-stl`) or rebuild in place? The flags are inert without `--stl-ann-file`, so behavior is unchanged for other runs either way. Nothing has been applied or built.
- **Threat model.** Under STT's Spectre model these loads are outside the defense, so every hit is expected by construction (scoping, `SCOPE_VS_IMPLEMENTATION.md`). Which threat model does the recon-modded scheme-2 STT run in, and does it treat a load past an unresolved-address store as unsafe? `gem5-hooks/stt/se_exp.py:332` pins `/work/stt` to `threatModel = 'Spectre'`. Needs reading the Recon/STT source on cafe2 and the papers.
- **Contract granularity.** Is "everything after an unresolved store" right for STT Futuristic, or only loads that may alias it? See Generation.
- **Other defenses.** SPT and Recon versions (`SPT_6_*_stl.als`, `Recon_6_stl.als`) follow the same three edits once STT is settled; the hooks port by re-running `apply_stl_hooks.py` on each tree.
