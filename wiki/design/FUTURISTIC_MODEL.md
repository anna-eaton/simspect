# STT Futuristic model (`STT_6_futuristic.als`)

*Living doc. Written 2026-10-30 by the `stl-spec` session. Model status: written, SAT, **not yet reviewed by Anna**, no concretization mode, not run on gem5.*

## Three threat models, three builds

| Threat model | An instruction is safe (past the visibility point) when | Build that implements it | Model |
|---|---|---|---|
| Spectre | every older control-flow instruction has resolved (STT p5) | `/work/stt --threatModel=Spectre` (`isPrevBrsResolved`), the harness default (`gem5-hooks/stt/se_exp.py:332`) | `STT_6.als` |
| Control + store shadows | every older conditional branch has resolved **and** every older store has its address | `gem5-recon`, `gem5-recon-modded`, `gem5-recon-stl` scheme 2 (Recon paper Sec. 3, 6; `decode.cc:686-695`, `shadow_tracker.cc`) | `STT_6` ∪ `STT_6_stl` (no single file yet) |
| Futuristic | it "cannot be squashed" (STT p5): every older instruction has completed without a fault | `/work/stt --threatModel=Futuristic` (`isPrevInstsCompleted`, `rob_impl.hh:493-512`, used at `lsq_unit_impl.hh:1017`) | `STT_6_futuristic.als` |

InvisiSpec (Sec. IV, Table I) lists Futuristic's squash sources: exceptions, control-flow mispredictions, store-load alias, load-load alias, memory-consistency violations, and interrupts (which the hardware defers, Sec. V-D). A load is safe at the ROB head or once it is "preceded in the ROB only by instructions that cannot be squashed". Sources: `~/Documents/quail/sources/papers/yu-2019-stt.pdf` p5, `yan-2018-invisispec.pdf` Sec. IV.

## Is it "done on commit"?

Not quite. The visibility point is **completion** of every older instruction, not commit. `/work/stt` computes `prevInstsComplete` over the ROB: an older instruction that isn't `readyToCommit() & isLoadSafeToCommit()`, has a fault, or is squashed clears it. A barrier or non-speculative instruction also clears it. The commit-based variant (`isPrevInstsCommitted`, i.e. ROB head) is present in the STT source but commented out (`rob_impl.hh:516`). It is in the model as a commented-out alternative contract.

## The model diff (vs `STT_6.als`)

Everything else is byte-identical to `STT_6.als`.

```
+fun has_unresolved_any_p[p: PTag->univ] : Instruction {
+	(unresolved_p[p].(^(spo_p[p])))   // after some instruction that has not completed
+}
+fun no_unresolved_any_p[p: PTag->univ] : Instruction {
+	i_p[p] - has_unresolved_any_p[p]
+}
-fun speculation_contract_p[p] {uncommitted_p[p] & has_unresolved_brs_p[p]}
+fun speculation_contract_p[p] {uncommitted_p[p] & has_unresolved_any_p[p]}
-	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate
+	s - (Loads & no_unresolved_any_p[p] & i).inmem.opstate
```

`isresolved` now means "completed: can no longer squash younger instructions" for every kind. For a branch that is its direction resolving; for a store, its address; for a load, its data returning without a fault; for an ALU op, executing without a fault. Resolution-minimality (`all i: unresolved - first_uncommitted | secure[RR->i]`) is unchanged, so the unresolved instructions in an instance are exactly the ones whose shadow is needed.

## First enumeration (500 instances, 7 s)

Speculation source kind per instance: unresolved `other` with xmit flag 409, `other` without 34, branch 33, load 22, store 2. No instance has more than one source kind. 429/500 have no committed instruction. This mix comes from the enumeration order under the cap, not from a model limit (same caveat as `OTB_GENERATION_GAP.md`). Typical shape: `othx!U ld brx*X brn brn brn`, i.e. a slow ALU op, then a load whose value feeds the transmitting branch. Analysis script: `gem5-hooks/stl/alloy_shape.py <xml_dir>` (reads Alloy's `.txt` dumps).

## Decisions for Anna (also in `URGENT_TODO.md`)

1. **Visibility point: completed vs committed.** Completed matches `/work/stt` and InvisiSpec's "speculative non-squashable". Committed (ROB head) is stricter and simpler. Recommendation: completed (as written).
2. **Squash sources: any kind vs branch + store only.** Any kind is Futuristic proper. Branch + store is what the Recon builds protect: that is a separate model (`STT_6_shadows`) and the one their STT results should be judged against. Recommendation: keep this file as Futuristic, and also make `STT_6_shadows` for the Recon builds.
3. **Concretization.** A non-branch, non-store source (an ALU op, a load) has to be held incomplete in gem5 for the window to exist: either a new completion-hold hook by PC (like the STL store hold), or naturally slow instructions (a chain of `div`s, a cache-missing load). No mode is built yet. Recommendation: the hook, because it gives a known window length, the same as the branch and store holds.
4. **Run against `/work/stt` with `threatModel = Futuristic`.** The harness pins Spectre today. Futuristic results on the Recon builds would be "leaks" by design.
