# Figure (d): table of instrumentations in concretization

*Plan and source of truth for minifig (d). Written 2026-11-02 from a read of the working tree. Every cell of the figure is listed below with the file:line it comes from. Line numbers are working-tree files; `parsexml.py` = `STAGE2_compilation/parsexml.py`, `gem5_common.py` = `STAGE3_gem5/gem5_common.py`. `parsexml.py`, `gem5_common.py` and `pipeline.py` all have uncommitted changes (`git diff --stat`: 65 / 408 / 18 lines); the derived branch force and the execution-validity gate exist only in the uncommitted `gem5_common.py` and are not on cafe2 until `make sync`.*

## Files

- Draft standalone: `paper_figures/drafts/_standalone_instrtable.tex`, preview `paper_figures/drafts/_standalone_instrtable-1.png` (300 dpi, `pdftoppm -png -r 300 -singlefile`). Rendered size **507.4 × 305.4 pt** (full text width is 516 pt; text height is 672 pt, so it takes about 45% of a page).
- Follows `paper_figures/plans/VISUAL_LANGUAGE.md`: `\documentclass[tikz,border=1pt]{standalone}`, no font family inside the picture (newtx only in the preview), body `\footnotesize`, notes `\scriptsize\itshape`, bold only on the "Stage 2:" / "Stage 3:" header prefixes, black on white, no gray (nothing in this table is defense-specific), default 0.4 pt lines, sharp-corner boxes, `>=latex`, a `TUNING KNOBS` block, hyphenation off in nodes, typewriter only for literal asm (`movq $1`, `xorq`, `testq`+`jz`, `nop`, `orq $1`, `mfence`, `-O2`).
- Anna's sketch (2026-11-02, item d): columns "Exec graph → Program (how we instrument, in STLF?)", rows "S, L", "Br^unres", "Br^res", "FNC / LC", "…"; margin notes "e.g. (MS) Pred NT ← say cases we do", "+ stalls we add", "<graph format?>", and "Need ALL concr weird info like timing + SP inst." I read "in STLF" as the S, L row's program cell ("how we instrument it for store-to-load forwarding"), not as a column title.

## Layout choice: full text width

Full width (`table*`/`figure*`, ≤ 516 pt). The sketch asks for every odd concretization detail per exec-graph element, and the code splits each element's handling across three places that the reader has to keep apart (Stage 2 codegen, the Stage 2 annotation, the Stage 3 harness), plus which cases are actually generated. That is five columns. At one column (252 pt) the four text columns would be about 50 pt wide each, so most cells would run 8-12 lines and the table would be taller than a column page. Dropping columns to fit one column would lose exactly the "where does this happen" split the figure is for. At full width every cell is 1-5 lines.

Columns: **Exec. graph** (glyph + row name) | **Cases generated** | **Stage 2: program** | **Stage 2: annotation** | **Stage 3: gem5 harness**. Rows: store + aliasing load, unresolved branch, resolved branch, commit boundary (the four in the sketch), then target transmitter and every instruction (the "…" row, carrying the remaining odd details). A one-line legend under the table explains the glyphs.

## Graph format for the exec-graph column (sketch: "<graph format?>")

Each glyph is a fragment drawn in figure (a)'s execution-graph syntax (`paper_figures/drafts/_standalone_execgraphsyntax.tex`): an instruction is a sharp-corner box holding its type name (Store, Load, Branch); program order is top to bottom with no edge drawn (figure (a) draws spo as row order, so a plain arrow would read as rf); rf is a solid arrow labeled *rf*; flags are the math-italic letters $r$ (resolved), $c$ (committed), $t$ (target transmitter) written right of the box, the same letters figure (a) uses as its flag-column heads. An empty box means "any instruction". lc / fnc are written left of their boxes, where figure (a) writes I0, I1, I2. Each glyph shows only the flags its row is about, so a Branch or Store without $r$ is unresolved. A glyph is at most two boxes; that is all any row needs.

| Row | Glyph |
|---|---|
| store + aliasing load | Store above Load, rf arrow between them, no $r$ on Store |
| unresolved branch | Branch (no $r$) above an empty box |
| resolved branch | Branch $r$ above an empty box |
| commit boundary | box $c$ labeled lc above a box without $c$ labeled fnc |
| target transmitter | one box with $t$ |
| every instruction | one empty box |

"Branch" covers both Branch_n and a Branch_x that is not the target transmitter: `pass2_5_specify_branches` keys on the `xm` flag, not on the kind (`parsexml.py:731` loops over `_BRANCH_KINDS = {"br_n","br_x"}` at 636; the xmit override is `if is_xm` at 754).

Alternatives I did not use: circles with letters (my first draft; inconsistent with figure (a)'s boxes), the old paper style (`I0: branch_n` text rows with an r/c column, `tikz/alloyviolation.tex`; too wide for a table cell), filled dots like the pipeline figure's graph icon (can't show type or flags).

## Fact table (source of truth for every cell)

Each bullet gives the figure text (shortened) and its source. "Plan only" marks facts that are true and relevant but left out of the figure for space.

### Row 1: store, then aliasing load (S, L)

- **Cases generated:** predicted no alias, actually aliases (a false-negative alias prediction): `parsexml.py:986-990` (pass2_6 docstring: "The speculation primitive is a false-negative alias prediction"); `wiki/design/STL_SPECULATION.md` "The primitive". Own mode: only when `"stl_bypass"` is in `speculation.branch_modes` (`batch_generate.py:106-107` gate, per `wiki/design/CONCRETIZATION_PASSES.md` §1; `runconfigs/run_config_STT_6_stl.jsonc` `branch_modes: ["stl_bypass"]`). All branches resolved: pass2_5 raises on any unresolved non-xmit branch in this mode (`parsexml.py:709-719`); the model forbids them (`STT_6_stl.als` fact `stl_no_unresolved_branches`, quoted in STL_SPECULATION.md "Generation").
- *Plan only:* pairing rule. For each unresolved, non-synthetic store S, the bypass load L is the first uncommitted load after S that reads S's `Mem_s` before another store writes it; later loads of the same location are tagged `alias_load` (`parsexml.py:1015-1034`). Tags live on records, not PCs, because interleave renumbers later (`parsexml.py:1002-1003`). No unresolved store, no outmem, or no aliasing load raises and the test is skipped (`parsexml.py:1019-1020, 1028-1029, 1036-1037`).
- **Stage 2 program:** S and L share an 8-byte slot (when neither has a specified inaddr they use the same `mem_base` slot, `parsexml.py:1195-1201`); with an address register involved, S is re-emitted at L's runtime address, keeping S's own index register (`_stl_store_retargets`, `parsexml.py:1172-1222`; emitted at `parsexml.py:2185-2215`). Inline asm stops the compiler forwarding S to L (STL_SPECULATION.md "Concretization": "Loads and stores are already inline asm, so LLVM cannot fold the store→load"). *Plan only:* 487/500 instances need no retarget, 13/500 do (STL_SPECULATION.md "Concretization").
- **Stage 2 annotation:** `stl_annotations[]`, one entry per aliasing load: `{store_pc, load_pc, role: bypass|alias, mem_atom, mode: "stl_bypass"}` (`parsexml.py:2644-2657`); alias loads kept only if their runtime address equals S's (`_stl_alias_load_matches`, `parsexml.py:1225-1248`); `compile_annotate.py:286-291` adds absolute `store_addr` / `load_addr`.
- **Stage 3 harness:** STL-hooked build `/work/gem5-recon-stl` (`run_config_STT_6_stl.jsonc` `gem5.binary`). S's address generation held `gem5.stl_store_addr_stall_cycles` = 5000 cycles (`run_config_STT_6_stl.jsonc`; env bridge `pipeline.py:602-606`; flag `gem5_common.py:398-401`); mechanism: the annotated store goes back to the mem-dep replay list and is replayed N cycles after first issue (STL_SPECULATION.md "gem5 hooks" table). L's dependence prediction forced to no-alias (`gem5.stl_alias_pred: "no_alias"`); `alias` is the negative control, `off` = unmodified (same table). Window check not yet built: STL_SPECULATION.md Status table ("Window checker: proposed below, not written") and the config header comment ("check_ld/check_br verdicts are NOT meaningful for this testset").
- *Plan only:* hook controls on 60 tests: Unsafe + no_alias 28/28 load transmitters sent in the hold window, STT 0/28, alias 0/60 bypass (STL_SPECULATION.md "Hook test"). The override also applies when the setup `mfence` is still in flight (`via=barrier`), a hook bug the controls found (same section).

### Row 2: unresolved branch

- **Cases generated:** mispredicted not-taken (architecturally taken) and mispredicted taken (architecturally not taken), one per run mode (`parsexml.py:838-856` and `858-876`). Both modes are in every fixed config (`runconfigs/fixed_20261030/*.jsonc` `branch_modes: ["mispredict_not_taken","mispredict_taken"]`). Correctly predicted unresolved branches are not generated: pass2_5 has no such branch (`parsexml.py:639-925`); `wiki/design/SPEC_PRIMITIVE_INSTANCES.md` rows (e), (f) "no".
- **Stage 2 program:** non-xmit branches are forced to `br_cond` (`parsexml.py:789-794`). The condition is a constant in a pool register: `movq $1` when the architectural condition is true (not-taken mode), `xorq` when false (taken mode) (`parsexml.py:2480`), then `icmp ne` (2484). Not-taken mode: the taken edge is `end_block`, the fall-through is `bb_<pc+1>` (`parsexml.py:848-856`). Taken mode: the not-taken edge goes through an `ftbypass_<pc>` trampoline to `end_block`, so the architectural path skips the critical section (`parsexml.py:2485-2507`; reasons in the pass2_5 docstring, 663-673). So the next instruction runs only speculatively.
- **Stage 2 annotation:** `annotations[]` entry `{branch_pc, branch_atom, btb_forced_target_pc = pc+1, mode}` (`parsexml.py:2598-2607`); after interleave `btb_predicted_pc` is re-set to the new pc+1, which may be a chain step (`parsexml.py:1374-1389`). `compile_annotate.py:255-267` adds `branch_addr` (first conditional jump at or after the pc label, `find_branch_at_pc` 206-220) and `btb_forced_target_addr`.
- **Stage 3 harness, force:** on binaries with the resolve hooks (`binary_has_resolve_hooks`, `gem5_common.py:156-170`), `_branch_ann_for_se` replaces the forced target with the derived force: the x86 direction whose straight-line path reaches the label of pc+1, as target 1 (predict not-taken) or the jcc's own static target (`gem5_common.py:250-312, 338-359`; rule in `wiki/design/RESOLUTION_HOOKS.md` §2). Never forced to the label address.
- **Stage 3 harness, stall:** `resolve_stall_cycles = sweep.unresolved_stall_cycles` = 5000 (`pipeline.py:425-427`; value in all five `runconfigs/fixed_20261030/*.jsonc`). Only written on the sweep path (`pipeline.py:1068-1073`, `_materialise_grid_run` 471-495), which every fixed config uses (`sweep.enabled: true`). The hook holds the branch's release (setExecuted, instToCommit, squash broadcast) for N cycles after execute (RESOLUTION_HOOKS.md §1; `wiki/findings/bug/BRANCH_ANNOTATION_AND_FORCE.md` §4 "Stall placement").
- **Stage 3 harness, gate:** the model's unresolved branches must still be unresolved at the transmission, using the observed `resolve_visible` tick (`collect_unresolved_branches` skips `correctly_not_taken`, `gem5_common.py:867-901`; `check_branch_resolutions` 940; criteria in `check_ld.py:110-114`, `check_br.py:93-99`, `check_other.py:38-42`). Invalid unless mispredicted and held: `execution_validity` `window_opened` (oldest non-xmit unresolved branch mispredicted on its retired instance), `stall_applied`, `force_applied` (`gem5_common.py:1002-1068`); any False sets `status="invalid"` and `issued_in_window=False` (`gem5_common.py:1149-1182`).
- *Plan only:* a branch with no reachable label and no flags idiom gets `force: unknown` and no force at all (`gem5_common.py:284-285, 306-307, 346-351`). The release wakes the CPU (hook edit 4), without which long holds froze gem5 (RESOLUTION_HOOKS.md §1).

### Row 3: resolved branch

- **Cases generated:** correctly predicted not-taken only (`mode: "correctly_not_taken"`, `parsexml.py:796-819`). Resolved taken is not generated (no code path; SPEC_PRIMITIVE_INSTANCES.md row (a) "no").
- **Stage 2 program:** `br_cond` on a zeroed pool register (`xorq`, condition false, `parsexml.py:2480`): falls through to `bb_<pc+1>`, static target `end_block` never taken (`parsexml.py:811-818`). *Plan only:* when both edges are `end_block` (resolved branch at the last pc) an `ftbypass` trampoline keeps LLVM from folding the jump away (`parsexml.py:2508-2519`).
- **Stage 2 annotation:** same entry shape as row 2, `mode: "correctly_not_taken"` (`parsexml.py:2598-2607`).
- **Stage 3 harness, force:** derived force to the architectural direction (`want_arch` for `correctly_not_taken`, `gem5_common.py:281, 308-310`; RESOLUTION_HOOKS.md §2).
- **Stage 3 harness, stall:** per-branch resolution delay from the sweep grid, `sweep.points` = [0, 500, 2500] in every fixed config; the grid is the Cartesian product over the test's resolved branches, each grid point a separate gem5 run (`_grid_points`, `pipeline.py:363-401`; applied by `_inject_stalls`, 423-424). `max_grid` (random subsample) is unset in the fixed configs.
- **Stage 3 harness, gate:** invalid if it mispredicts on a retired instance (`resolved_correct`, `gem5_common.py:1029-1034`). *Plan only:* whether it resolved before the transmission is recorded as `criteria.resolved_before_signal`, deliberately not gated (RESOLUTION_HOOKS.md §3, "Whether to gate on this is Anna's call"). See Decisions.

### Row 4: commit boundary (lc / fnc)

- **Cases generated:** lc = last committed instruction; fnc = first instruction of the must-be-uncommitted suffix (for models without `isuncommitted`, the first uncommitted one); both skip synthetic records, so never an interleaved chain step or the padding `nop` (`commit_boundary`, `parsexml.py:1902-1931`; flags read in pass1, `parsexml.py:376-382, 448-451`; rule in `wiki/design/COMMIT_BOUNDARY.md` §1).
- **Stage 2 program:** global labels `__litmus_<stem>_last_committed` / `_first_noncommitted` on the same asm block as the instruction (`parsexml.py:2106-2108, 2134-2140`).
- **Stage 2 annotation:** `commit_boundary: {last_committed: {pc, atom}, first_noncommitted: {pc, atom}}` (`parsexml.py:2621-2643`); `compile_annotate.py:296-310` adds absolute addresses and moves the address to the jcc when the boundary instruction is a branch (plan only; cut from the figure for space).
- **Stage 3 harness:** window lc retired < transmission < fnc retires, measured from the trace, not forced (`check_ld.py:108-109`, `check_br.py:90-91`, `check_other.py:36-37`; lc that never retires disqualifies, `lc_retired`). Commit stall on fnc: `gem5.fnc_commit_stall_cycles` = 0 in all five fixed configs (`runconfigs/fixed_20261030/*.jsonc`); when > 0 it becomes `--fnc-commit-stall-pc/-cycles` (`pipeline.py:611-613`; `gem5_common.py:406-408`) and holds fnc at the ROB head (`wiki/design/METHODS_INSTRUMENTATION.md` §1.3). It is 150 in `run_config_STT_6.jsonc:37` and `run_config_STT_6_stl.jsonc` (see Decisions).

### Row 5: target transmitter ($t$)

- **Cases generated:** one per instance (`emit_branch_annotations` takes the first `xm` record, `parsexml.py:2609-2619`; the model fact `one_xm` per the comment at 2609-2610). Kinds: load, store, branch, and "other_x" = zero-skip multiply (`zsm`) or divide (`instruction_tables/instructions.jsonc` `other_x`).
- **Stage 2 program, branch:** always `br_bez` (`testq`+`jz`) whatever the Alloy resolved flag or run mode (`parsexml.py:754-779`); the condition is read from the Alloy inreg through a register-pinned `movq` so the load→branch taint chain survives (`parsexml.py:2405-2420`); architecturally the register is 0, so the branch is taken to `end_block` (`parsexml.py:2392-2397`, 2426-2427). A synthetic `nop` follows only when it is the last instruction (`parsexml.py:768-769, 880-904`).
- **Stage 2 program, divide:** a non-transmitter divide copies its divisor to `%rcx` and sets bit 0 (`orq $1`); the transmitter divide is left unguarded so a zero divisor faults (`parsexml.py:2334-2370`).
- **Stage 2 annotation:** `xmit: {pc, kind, atom}` (`parsexml.py:2611-2619`); the kind selects the checker (`pipeline.py:296-314`: ld → check_ld, br_x → check_br, other_x → check_other, else check_ld). `compile_annotate.py:270-281` points a branch transmitter's address at the jcc.
- **Stage 3 harness:** branch transmitter: `resolve_stall_cycles = 0` (`pipeline.py:419-421`) and the derived force sends it down the side reaching pc+1, so it mispredicts every run (`gem5_common.py:281`: mode `mispredict_not_taken` → not `want_arch`). A Divide-Error panic at the transmitter, after a mispredicted branch, is scored as a transmission (`classify_divide_panic`, `gem5_common.py:819-853`, called at 1194).

### Row 6: every instruction (the sketch's "…")

- **Cases generated:** all tests.
- **Stage 2 program:** one `asm sideeffect` block per instruction carrying the global label `__litmus_<stem>_pc<N>`, so nothing can sit between label and instruction (`parsexml.py:2128-2140`). Prologue: zero-initialized `mem_base` alloca (2071-2076), zeroed probe array when any load/store has a specified address register (2063-2085), live-in registers zeroed by inline asm (2087-2089), then `mfence` before the test region (2091-2096). Address operands index the probe array (`movq (probe, reg, 1)`, 2150-2165). Compiled with `clang-15 -O2`, because `-O0` spills pinned values across blocks (`compile_annotate.py:90-104`).
- **Stage 2 annotation:** `compile_annotate.py` reads the labels with `nm` and rewrites every PC key as an absolute x86 address (`compile_annotate.py:108-163, 223-312`).
- **Stage 3 harness:** no hook acts on ordinary instructions; transmission is measured from the existing O3PipeView, LSQUnit and Commit traces (`gem5_common.py:61, 375-376`: Commit is always added). *Plan only:* hooked builds also print `O3PipeView:simspect:...:BR:` resolution lines for branches (print-only, RESOLUTION_HOOKS.md §1).
- *Plan only (code note, not a decision):* the probe array is `[256 x i64]`, 2 KiB, 64-byte aligned (`parsexml.py:2081`; `_PROBE_MEM_BYTES = 256 * 8`, 1063), but the comment above it says "256 slots × 64 bytes (cache-line stride) = one cache line per possible byte value" (2079). With `movq (probe, secret, 1)` (byte stride) the code gives 4 distinct cache lines across secret values 0-255, not 256. Architecturally the secret is 0 in these tests, so it may not matter for the checkers, but the comment and the code disagree. I did not touch `parsexml.py`.

### Not instrumented (stated so the table's silence is not misread)

- An Alloy `resolved = false` on anything other than a branch (branch modes) or a store (`stl_bypass` mode) gets no instrumentation: pass2_5 only visits `_BRANCH_KINDS` (`parsexml.py:731`) and pass2_6 only `kind == "str"` (`parsexml.py:1016`). Minimality normally keeps such instructions out (STL_SPECULATION.md "Generation": "Unresolved loads or ALU ops can't appear except as the boundary instruction").
- Committed instructions are not forced to commit; commit is only measured (row 4).
- Register and memory assignment (reserved Alloy registers, the 3 codegen registers, free-pool chain state) is concretization but not instrumentation; it belongs in figure (c) (`wiki/design/CONCRETIZATION_PASSES.md` §2 pass3).

## What it replaces

| Existing figure | Verdict | Why |
|---|---|---|
| `tikz/sptable_v2.tex` (paper repo) and `paper_figures/spec_primitives/sptable_v2.tex` | **Subsumed** | Its rows (b), (c), (d), (g), (h), (i) are rows 3, 2, 2, 5, 1, 1 here; (a), (e), (f) are the "not generated" notes. The paper-repo copy still has the old STL direction (predict alias, actually no alias; `diff` against the local copy, lines 23-24) and uses red text, which the visual language disallows. |
| `tikz/sptable.tex` (original) | **Subsumed** | Earlier version of the same table. |
| `tikz/resolutiontiming_v2.tex` and `paper_figures/spec_primitives/resolutiontiming_v2.tex` | **Facts subsumed; visual is a decision** | Every value it shows (swept $d_i$ for resolved, fixed $D$ for unresolved, $d=0$ for the transmitter branch, store address held) is in rows 1-3 and 5. It adds a timeline of resolution order against the window, which the table does not draw, and it uses purple/teal, which the visual language disallows. The window itself is figure (e)'s job (sketch: "pipeline inspection graph … show a violation window"). |
| `tikz/resolutiontiming.tex` (I0-I5 example) | **Already obsolete** | Replaced by the v2 timeline (SPEC_PRIMITIVE_INSTANCES.md). |
| `tikz/statetable.tex` | **Not subsumed** | It says which stage specifies which instructions and operands (Alloy generation vs interleave vs concretization). That is figure (c)'s subject, not instrumentation. |

## Where the paper text disagrees with the code (paper text is read-only; for Anna)

1. `sections/pipeline.tex:46`: "For resolved branches … insert a skipped block of noops if they are taken". Code generates resolved branches only as correctly predicted not-taken (row 3).
2. `pipeline.tex:48` and `:86`: STL "only in the false positive direction … enforce that the load and store have different addresses". Code does the false-negative direction with the load and store at the same address (row 1; Anna's 2026-10-28 answer in SPEC_PRIMITIVE_INSTANCES.md "Open").
3. `pipeline.tex:86`: "runs are launched bare at $s_U = 0$" and "the commit-stall over {0, 150} cycles". The fixed configs use $s_U = 5000$ and commit stall 0 (rows 2, 4).
4. `pipeline.tex:86`: the BTB-forced target forces "the modeled mispredicted (taken) path". On hooked builds every annotated branch now gets a derived force in either direction, resolved branches included (rows 2, 3, 5).
5. `pipeline.tex:83`: the annotation carries "the resolution time of every speculation primitive". Stage 2 never writes timing; Stage 3 adds `resolve_stall_cycles` on the sweep path and the store hold comes from config (CONCRETIZATION_PASSES.md §4.3).
6. `pipeline.tex:57`: "all branches guarding the transmitter are still unresolved". The gate is the model's unresolved branches, measured at `resolve_visible` (row 2).
7. `pipeline.tex:88`: "the same nine source sites". The builds now also carry the resolve hooks (BR print lines, forced not-taken via target 1, release wakes the CPU) and, on gem5-recon-stl, the STL hooks.

Suggested caption (Anna pastes, if she wants it): "How concretization instruments each execution-graph element. Stage 2 emits the program and its annotation; the Stage 3 harness reads the annotation to force predictions, hold resolutions, and bound the window in which the target transmitter must transmit. Values are those of the evaluated campaigns."

## Decisions for Anna

- [ ] **DECIDE: what figure (d) replaces.** Options: (a) (d) replaces `sptable_v2` and `resolutiontiming_v2`; the window visual moves to figure (e); (b) (d) replaces only `sptable_v2` and the timeline stays as its own figure (redrawn without color); (c) keep both old figures and make (d) a smaller summary. *Recommendation:* (a). The table carries every timing value, and (e) already shows the window, so a third timing picture repeats it.
- [ ] **DECIDE: show the cases that are not generated?** Resolved taken and correctly predicted unresolved branches (old rows a, e, f) have no generator. Options: (a) keep the short italic "not generated" notes (current draft); (b) drop them from the figure and say it in prose; (c) build the generators. *Recommendation:* (a) for now. `pipeline.tex:46` claims "every case can induce leakage while the branch is unresolved, even if it is not ultimately mispredicted", and a reviewer will look for those cases.
- [ ] **DECIDE: is STL in the evaluation?** The STL window checker is not written and the only STL data is the 60-test hook check. Options: (a) keep row 1 with "window check not yet built" (current draft, honest for a draft); (b) keep row 1 without the note once the checker and a campaign exist; (c) drop row 1 and the STL prose. *Recommendation:* (b) if the STL campaign will be in the paper, else (c). A row that says "not yet built" should not ship.
- [ ] **DECIDE: which timing values the paper states.** The fixed configs (`runconfigs/fixed_20261030/`) use $s_U = 5000$, $s_R \in \{0, 500, 2500\}$, fnc commit stall 0; the paper prose says $s_U = 0$ and fnc stall {0, 150}; `run_config_STT_6_stl.jsonc` still has fnc stall 150. `METHODS_INSTRUMENTATION.md` §1.2 says 5000 masks leaks by pushing the transmitter past fnc's retire, but that predates the fnc-at-real-retire change. Options: (a) state the fixed-config values (current draft) and update the prose; (b) state the prose values and change the configs. *Recommendation:* (a), and set the STL config's fnc stall to 0 so every campaign matches. The fixed campaigns are only 2% validation samples so far, so confirm these are the values the final results will use. Evidence that the fnc stall matters: in fixed round 2, SPT_6_oneLP load near-misses (exactly one criterion false) are dominated by `before_fnc` with the fnc stall at 0 (4299 / 4960 records per mode; `claudelog.md` 2026-11-02 resolve-hooks entry).
- [ ] **DECIDE: gate on resolved branches resolving before the transmission?** Today `resolved_before_signal` is recorded but not gated (RESOLUTION_HOOKS.md §3 left it to you). The model says a resolved branch has resolved at the observation time, so gating would match the model; it would also drop runs at large $s_R$. The draft states the current behavior only in this plan, not in the figure.
- [ ] **DECIDE: rows 5 and 6.** Your sketch had four rows plus "…". The transmitter and every-instruction rows carry the remaining odd details (xmit `br_bez`, divide guard, probe array, `mfence`, labels, `-O2`) and cost about 90 pt of height. Options: (a) keep both (current draft, 305 pt); (b) keep row 5, fold row 6 into the caption (~260 pt); (c) drop both (~215 pt). *Recommendation:* (b) if page budget is tight, otherwise (a).
- [ ] **DECIDE: glyph format.** The draft uses figure (a)'s boxes and flag letters (section above). If figure (a)'s notation changes, these glyphs should follow it.
- Not a decision, a heads-up: the derived force and the validity gate (rows 2, 3, 5) live in uncommitted `gem5_common.py`, so the method the table describes is not yet on cafe2. → run `make sync` when ready (check `df -h /System/Volumes/Data` first).

## Stale docs noticed (not edited)

- `wiki/design/SPEC_PRIMITIVE_INSTANCES.md`: sweep values "dᵢ ∈ {0,10,25,50,100}" and "`sweep.enabled` is `false`" (the fixed configs use {0, 500, 2500}, enabled); "BTB override is only active in `mispredict_taken` mode" (superseded by the derived force on hooked builds); STL hooks "not yet built" (built 2026-10-30); line numbers (CONCRETIZATION_PASSES.md §7).
- `wiki/design/METHODS_INSTRUMENTATION.md` §1.1: the BTB force is "only applied in taken mode" (same supersession).
- Root `CLAUDE.md`: "`check_br.py` … does not enforce the `lc/fnc` window". It now does (`check_br.py:90-99`).

## v2 (2026-11-02): one column, about a third of the area

Anna's feedback on v1: "wow the instrumentation table is huge", "the visual language for the graph needs to match the other graph", "these generally need more margins". Later additions: each preview reserves blank space for its caption but does not render it; the caption text lives in its own file.

### Files

- Table body (what goes into the paper, wrapped in `{ }` so its local definitions don't leak): `paper_figures/drafts/instrtable_v2.tex`.
- Proposed caption text: `paper_figures/drafts/captions/instrtable_v2.tex`.
- Preview: `paper_figures/drafts/_standalone_instrtable_v2.tex` + `_standalone_instrtable_v2-1.png` (300 dpi, `pdftoppm -png -r 300 -singlefile`) + `.pdf`. `\documentclass[border={2pt 2pt 2pt 16pt}]{standalone}`: the 16 pt top border is blank space for the caption (IEEE tables put the caption above). v1 files untouched.
- It needs `tikz`, `booktabs` and `array`, all already in the paper preamble (`bare_conf_compsoc.tex:332-336`, read from the scratch clone).

### Size

- Table body: **251 × 189 pt**, one column (`\columnwidth` = 252 pt) = 47.4k pt², **31% of v1** (507 × 305 pt = 154.8k pt²).
- Proposed caption at 8 pt over 252 pt: 9 lines, 83 pt. Table plus caption is about 276 pt tall, so the caption is now the long part (see decisions).
- Preview page: 255 × 207 pt (table + 2 pt borders + 16 pt caption space).

### What changed

- **Size.** One column, five rows, three columns: Execution graph | Stage 2: program | Stage 3: gem5 harness. Cells are fragments, not sentences. The "every instruction" row, the "Cases generated" column and the "Stage 2: annotation" column are gone; their content moved to the row labels, the caption and suggested paper text (table below).
- **Font.** `\scriptsize` (7 pt) everywhere, as `VISUAL_LANGUAGE.md` requires. v1's body was `\footnotesize` (8 pt), which broke that rule.
- **Margins.** 8 pt between columns, 4 pt above and below every rule (booktabs `\aboverulesep`/`\belowrulesep`), 1.5 pt between a row name and its glyph. All are knobs in the body's `TUNING KNOBS` block.
- **Table, not picture.** v2 is a booktabs + array `tabular`, so it can sit in a `table` float with a "TABLE" caption like the paper's (parked) bug table (`sections/results.tex:21`); each exec-graph glyph is a small inline TikZ picture. The preview sets `\ttdefault` to `pcr`, the paper's Courier (`IEEEtran.cls:496`), so code widths match the paper.
- **Graph notation.** v1's boxes and r/c/t flag letters are gone (Anna: the r/c/t dot columns are "entirely unclear"). v2 uses the plainest form that can be made consistent across figures. **This column follows whatever notation the graph figures (a)-(c), (e) settle on; it is a placeholder.**
  - One line per instruction, in program order from top to bottom: a row-local lowercase id (`i0`, `i1`), then the kind in code font, then the flag as an italic word.
  - Kinds are the model's kind atoms without the `T` prefix (`STT_6.als:30-35`: `TLoad`, `TStore`, `TBranchn`, `TBranchx`, `TOthern`, `TOtherx`), spelled with an underscore (`Branch_n`) to match figure (a)'s subscripts.
  - Flags are the words resolved / unresolved, committed / uncommitted and xmit. The model's fields are `isresolved`, `iscommitted`, `isxm` (funs `resolved`, `committed`, `xm`, `STT_6.als:60-68`). "xmit" follows the brief; the model's own name is `xm`.
  - The commit-boundary row has no kind. lc and fnc sit in the kind slot as role names, as figure (e) writes "i0: lc".
  - rf is a solid arrow from i0 to i1 labeled *rf*, as in figures (a) and (c).
  - The row-5 glyph lists `Branch_x` *or* `Other_x`, the two xmit kinds that get extra instrumentation.

### Cell → fact table (every v2 cell traces to a bullet above)

| v2 row | Exec graph (name + glyph) | Stage 2 cell | Stage 3 cell |
|---|---|---|---|
| Store bypass | Row 1 "Cases generated" (the rf arrow is the aliasing; S unresolved) | Row 1 "Stage 2 program" (shared slot / retarget; inline asm stops forwarding) | Row 1 "Stage 3 harness" (S address held `stl_store_addr_stall_cycles` = 5000; `stl_alias_pred: "no_alias"`) |
| Unresolved branch, mispredicted either way | Row 2 "Cases generated" (both modes) | Row 2 "Stage 2 program" (constant condition; architectural path to `end_block`) | Row 2 "force" (derived force toward pc+1 = mispredict), "stall" (5000), "gate" (unresolved at transmission) |
| Resolved branch, not taken | Row 3 "Cases generated" (correctly predicted not-taken only) | Row 3 "Stage 2 program" (`xorq`, falls through) | Row 3 "force" (architectural = correct), "stall" (sweep {0, 500, 2500}, Cartesian product) |
| Commit boundary | Row 4 "Cases generated" (lc committed, fnc first of the uncommitted suffix) | Row 4 "Stage 2 program" (global labels; synthetic records skipped) | Row 4 "Stage 3 harness" (window measured; `fnc_commit_stall_cycles` = 0) |
| Target transmitter | Row 5 "Cases generated" (kinds) | Row 5 "branch" (`testq`+`jz` on the Alloy inreg, architecturally taken), "divide" (xmit divide unguarded) | Row 5 "Stage 3 harness" (mispredicts, `resolve_stall_cycles = 0`; divide panic scored) |

Wording notes: "Forced correct" = the derived force picks the architectural direction (`want_arch`). "Forced to mispredict" = the derived force sends the branch toward pc+1, the non-architectural side (`window_opened` checks the mispredict). "no commit stall" = `fnc_commit_stall_cycles` = 0 in the fixed configs.

### What was cut or moved, and where

| v1 content | Where it is in v2 |
|---|---|
| "Every instruction" row: inline-asm block per instruction with a global PC label; prologue zeroes memory and live-in registers, then `mfence` | Caption |
| Same row: no hook on ordinary instructions | Caption ("no other instruction is hooked") |
| Same row: probe array for address operands; clang `-O2`; transmission read from O3PipeView, LSQUnit, Commit traces | Suggested text (below) |
| Same row, annotation: labels resolved to x86 addresses | Suggested text (caption says the annotation carries each element's PC) |
| "Cases generated", store bypass: predicted no alias, actually aliases | Glyph (rf arrow = aliases) + Stage 3 "i1 forced to predict no alias" |
| "Cases generated", unresolved: mispredicted not-taken and taken | Row label "mispredicted either way" |
| "Cases generated", resolved: correctly predicted not-taken | Row label "not taken" + Stage 3 "Forced correct" |
| "Correctly predicted: not generated" / "Taken: not generated" | Caption |
| "Cases generated", commit boundary: definitions of lc and fnc | Caption + glyph flags |
| "Cases generated", xmit: one per test | Caption ("the test's one target transmitter") |
| "Cases generated", xmit kinds (load, store, branch, multiply, divide) | Glyph shows `Branch_x` / `Other_x`; full list in suggested text |
| "Stage 2: annotation" column, all rows | Caption: one sentence (PC, branch mode and predicted target, xmit kind) |
| "kind selects the checker" | Suggested text |
| Store bypass: "Own mode; all branches resolved"; "STL-hooked build" | Suggested text |
| Store bypass: with an address register, S re-addressed to L's runtime address | Stage 2 "share an address" (the outcome) + suggested text |
| Store bypass: "Window check not yet built" | Caption, as a bracketed draft note |
| Unresolved: `movq $1` / `xorq` | Suggested text |
| Unresolved: "invalid unless mispredicted and held"; resolved: "invalid if it mispredicts" | Caption ("invalid if a force or hold did not take effect") |
| Commit boundary: "measured, not forced"; "commit stall on fnc: 0 cycles" | Stage 3 "(measured); no commit stall" |
| xmit branch: `nop` after it if it is last | Suggested text |
| Divide: other divides get `orq $1` | Suggested text (the cell keeps "unguarded") |
| Footer legend for the box glyphs and r/c/t | Gone: flags are now words; the caption points to the graph notation figure |
| Branch rows also cover a non-xmit `Branch_x` | Suggested text |
| "Values are those of the evaluated campaigns" | Suggested text |

### Suggested paper text (Anna pastes; Claude does not edit paper text)

Every instruction is emitted as its own inline-asm block that carries a global PC label, so nothing can sit between the label and the instruction; the annotation rewrites each label as an x86 address. A prologue zeroes the memory slots, the probe array (when used) and the live-in registers, then runs \texttt{mfence}. Address operands index the probe array, and the program is compiled with clang \texttt{-O2}. Stage~3 adds no hook for ordinary instructions: it reads transmission from gem5's O3PipeView, LSQUnit and Commit traces, with the checker chosen by the xmit's kind (Load, Store, Branch\_x, or Other\_x, a zero-skip multiply or a divide). Branch conditions are constants (\texttt{movq \$1} or \texttt{xorq}), and a Branch\_x that is not the xmit is handled like a Branch\_n. A branch xmit that is the last instruction is followed by a \texttt{nop}; divides other than the xmit get \texttt{orq \$1} on their divisor so they cannot fault. Store bypass is its own run mode, with all branches resolved, on a gem5 build with store-bypass hooks; when an address register is involved, the store is re-emitted at the load's runtime address. All values are those of the evaluated campaigns.

(Sources: Row 6 and Rows 1, 2, 5 bullets above.)

### Open decisions (v2)

- [ ] **DECIDE: one graph notation for all the figures.** The current graph figures disagree with each other. (a) uses boxes, r/c/t dot columns, `I0` and roman kinds with subscripts. (c) uses `I0:`, lowercase typewriter `branch_n` and r/c letters. (e) uses `i0: lc`. So "match the other graph" can't be met until one notation is chosen. Options: (a) the v2 placeholder everywhere: lowercase ids, model kinds in code font, flags as words, rf/ddi arrows; (b) figure (a)'s boxes with flags written as words instead of dots; (c) whatever the shape-language design (`plans/BIGFIG_SHAPE_DESIGN.md`, if it lands) proposes. *Recommendation:* (a). It is the only form that fits a 7 pt table cell, and flags as words answer the "r/c/t is unclear" complaint. This table follows whichever you choose.
- [ ] **DECIDE: caption length.** The caption is 9 lines (83 pt), about 44% of the table's height. Options: (a) keep it; (b) move the "Every instruction…" and "Not generated…" sentences into the paper text, leaving about 5 lines; (c) also drop the draft note once the STL decision is made. *Recommendation:* (b) + (c). The table then reads with a short caption, and the text already describes concretization.
- [ ] **DECIDE: annotation in the cells or in the caption?** v2 moved the annotation column into one caption sentence. Putting short italic annotation fragments back at the end of each Stage 2 cell costs about 1 line in 4 of 5 rows (roughly 25-30 pt of table height). *Recommendation:* caption. Per element, the annotation is mostly just "its PC".
- [ ] **DECIDE: "mispredicted either way" / "not taken" labels.** The case labels are short. The full cases ("mispredicted not-taken and mispredicted taken, one per run mode"; "correctly predicted not-taken only") are only in this plan and the suggested text. OK, or should they be spelled out at the cost of a line each?
- Still open from v1: what (d) replaces; whether to show the not-generated cases (v2 keeps them in the caption); whether STL is in the evaluation (v2 carries the draft note in the caption); which timing values the paper states (v2 shows the fixed-config values: 5000, {0, 500, 2500}, no commit stall; the STL config still has fnc stall 150); whether to gate on `resolved_before_signal`. The v1 "rows 5 and 6" decision is settled by Anna's feedback: row 6 is in the caption. The v1 "glyph format" decision is replaced by the notation decision above.
