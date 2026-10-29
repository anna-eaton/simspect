# Speculation-primitive instances (paper §Concretization: Table `tab:sptable` + Fig. `fig:resolutiontiming`)

*Living doc, overwrite-in-place. Written 2026-10-28 while rebuilding the paper's speculation-primitive table and resolution-timing figure. LaTeX + preview: [`paper_figures/spec_primitives/`](../../paper_figures/spec_primitives/).*

**Uploaded 2026-10-28** to the paper repo [`anna-eaton/test-paper`](https://github.com/anna-eaton/test-paper) as new files `tikz/sptable_v2.tex` + `tikz/resolutiontiming_v2.tex` (+ `_standalone_*_v2.tex` / `-1.png` previews), commit `5b6c7fa`. Copies here in `paper_figures/spec_primitives/`. Verified to compile inside `bare_conf_compsoc.tex` with no errors; uses only packages the paper already loads (no `multirow`). To use them, Anna changes `sections/pipeline.tex` lines 47 and 49 (`\input{tikz/sptable}` → `sptable_v2`, `\input{tikz/resolutiontiming}` → `resolutiontiming_v2`).

The table merges Anna's case set (the filled-in `tikz/sptable.tex` in the paper repo) with what the code does, one row per instance. "Generated?" is what `parsexml.py` currently emits.

| | Primitive | Predicted | Actual | Concretized program | Resolve delay | Generated? |
|---|---|---|---|---|---|---|
| (a) | Resolved branch | taken | taken | jump past inserted noops | swept dᵢ ∈ {0,10,25,50,100}, before t_o | **no** |
| (b) | Resolved branch | not taken | not taken | fall through, target = end block | swept dᵢ | yes, `correctly_not_taken` (`parsexml.py:772`) |
| (c) | Unresolved branch | taken | not taken (mispred.) | jump past inserted noops | fixed D = 5000, past t_o | yes, `mispredict_taken` (`parsexml.py:834`) — but code speculates into the next block and the architectural fall-through goes to `end_block` via a trampoline, not a noop skip |
| (d) | Unresolved branch | not taken | taken (mispred.) | fall through, target = end block | fixed D | yes, `mispredict_not_taken` (default) |
| (e) | Unresolved branch | taken | taken | jump past inserted noops | fixed D | **no** |
| (f) | Unresolved branch | not taken | not taken | fall through, target = end block | fixed D | **no** |
| (g) | Transmitter branch | not taken | taken (mispred.) | fall through, target = end block | 0 | yes (`parsexml.py:716`; `pipeline.py` `_inject_stalls`) |
| (h) | Load after an unresolved store | no alias | aliases (mispred., false negative) | load reads the same address an older store writes; the store's address is held unresolved, so the load bypasses it and reads the stale value until the memory-order squash | — | yes, branch mode `stl_bypass` (model `STT_6_stl.als` + `parsexml.py:pass2_6_specify_stl`); gem5 hooks written (`gem5-hooks/stl/`), not yet built. Design: [`STL_SPECULATION.md`](STL_SPECULATION.md) |
| (i) | Unresolved store | — | — | store address generation held | fixed D (`gem5.stl_store_addr_stall_cycles`) | yes, with (h) (`--stl-store-stall-cycles`) |

The BTB override is only active in `mispredict_taken` mode; not-taken predictions are the cold predictor's default (`METHODS_INSTRUMENTATION.md` §1.1). Stall values from `run_config.jsonc` `sweep` (currently `enabled: false`).

## Resolution-timing figure (new)

The new figure is a timeline in cycles, one lane per instance (colors and t_o match the paper's checker-window Fig.): two resolved branches whose swept dᵢ reorder their "resolved" broadcasts before t_obs; unresolved branches held past the window by D; the xmit branch at d = 0; the store address held unresolved. The shaded band is the check window (last-committed retire → first-non-committed retire, per `run_config.jsonc` `pipeline.check`) in which the target transmitter must transmit. It replaces the I0–I5 example, which mixed program order and time.

## Where the paper prose disagrees with the code

1. Prose says resolved *taken* branches get a skipped noop block. Code only produces resolved branches as correctly-not-taken. Table follows code.
2. Prose implies BTB values are passed for every branch; in fact the override is only active in `mispredict_taken` mode.
3. Row (g) (xmit branches, stall 0) isn't mentioned in the prose.
4. Rows (a), (e), (f) aren't generated. Row (h) is generated since 2026-10-28 (`stl_bypass` mode), in the false-negative direction; the earlier table said false positive (predict alias, actually no alias), which only makes the load wait and opens no window. The paper-repo copy `tikz/sptable_v2.tex` (commit `5b6c7fa`) still has the old direction; the local copy here is fixed.
5. `sweep.enabled` is `false` in the current `run_config.jsonc`.

## Open (also in `state/OPEN.md`)

- ~~Is (h) generated anywhere?~~ Answered 2026-10-28: it is now, via `stl_bypass` (Anna asked for it). Keep it in the paper if it's in the evaluation.
- ~~(h) direction?~~ Answered 2026-10-28 (Anna): false negative. Predict no alias, actually alias; the window is load issue → memory-order squash when the held store resolves. The false-positive direction (`--stl-alias-pred=alias`) is the negative control.
- Rows (a), (e), (f) (correctly predicted taken / unresolved-but-correct): build them, or keep them in the table as design intent?

## Suggested paper prose

> The model's resolved and committed flags describe the instance at an observation time $t_o$; concretization must reproduce that state. Table~\ref{tab:sptable} lists every speculation primitive we instantiate. Resolved branches (a, b) are concretized as correctly predicted, and we sweep the delay $d_i$ between a branch learning its direction and broadcasting ``resolved'', so multiple branches resolve in every order before $t_o$ (Fig.~\ref{fig:resolutiontiming}). Unresolved branches (c–f) and are held for a fixed stall $D$ that outlasts $t_o$, and transmitter branches (g) are never stalled. For data flow (h, i), the load reads the same address as an earlier store whose address generation is held unresolved, and the memory-dependence predictor is forced to predict no alias, so the load bypasses the store and reads the stale value until the store resolves and the memory-order violation squashes it. The directives passed to gem5 are the forced BTB target for taken-mode branches, each primitive's resolve delay, and the (store, load) PC pairs with the store's address hold.
