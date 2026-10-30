# Why lc/fnc were recomputed after interleaving (git archaeology, 2026-10-30)

**Verdict.** Nobody changed the boundary code to recompute it after interleave. The lc/fnc code in `pass5_emit_llvm` and `emit_branch_annotations` was written on 2026-04-03, about seven weeks before `pass_interleave` existed. It is byte-identical from then until the 2026-10-29 fix. It was correct when written, because every record came from the Alloy instance. When `pass_interleave` was added on 2026-05-27 it went between pass2.5 and pass3, and gave its chain steps `committed: False`. It was not wired into the boundary code. The design note for the interleave stub had said downstream passes should "treat the synthetic records like any other other_n", so nothing downstream checked for them. The `synthetic` flag predates interleave, but before the fix nothing used it to skip boundary selection. No doc or log before 2026-10-28/29 says lc/fnc stay pinned to Alloy instructions under interleave. The first written statement of that rule is the fix itself (`wiki/design/COMMIT_BOUNDARY.md`).

Method: read-only `git log -S`, `git show`, `git grep` across all 59 commits (`git log --all`). The cafe2 copy has the same 59 commits and the same `-S pass_interleave` result, so the Mac history is complete for this question. All commits are authored `anna-eaton <acbeaton@stanford.edu>`. Most are bulk syncs, so a commit's date is when the code was synced, not when it was written. Commit messages do not name sessions.

## 1. The boundary code: written 2026-04-03, never changed until the fix

- First appears in **`3cb6f39` (2026-04-03 12:22 -0700, "alloy and stuff")**, in `alloy/parsexml_kind.py`. That diff adds these lines (`+` lines 105-135 and 366-367 of `git show 3cb6f39 -- alloy/parsexml_kind.py`). No earlier commit (`ec45866`, `6518da0`, `feadbde`) has `first_noncommitted`, `last_committed` or `commit_boundary` in any `.py`.
- pass5 block, as of `3cb6f39:alloy/parsexml_kind.py:1212-1221`:

```python
    # ---- Commit boundary PCs ----
    last_committed_pc: Optional[int] = None
    first_noncommitted_pc: Optional[int] = None
    for rec in instructions:
        if rec.get("committed", False):
            last_committed_pc = rec["pc"]
    for rec in instructions:
        if not rec.get("committed", False):
            first_noncommitted_pc = rec["pc"]
            break
```

- `emit_branch_annotations` block, as of `3cb6f39:alloy/parsexml_kind.py:1503-1512`:

```python
    # Collect commit boundary (last committed / first noncommitted instruction).
    last_committed: Optional[Dict[str, Any]] = None
    first_noncommitted: Optional[Dict[str, Any]] = None
    for rec in result["instructions"]:
        if rec.get("committed", False):
            last_committed = {"pc": rec["pc"], "atom": rec["instruction"]}
    for rec in result["instructions"]:
        if not rec.get("committed", False):
            first_noncommitted = {"pc": rec["pc"], "atom": rec["instruction"]}
            break
```

- Lineage of the file: `alloy/parsexml_kind.py` (3cb6f39) → moved to `STAGE2_compilation/parsexml_kind.py` (`60993f2`, 2026-04-12, "file reorg") → renamed to `STAGE2_compilation/parsexml.py` (`dd36e15`, 2026-04-21, "oldest taint bug etc"). The old `alloy/parsexml.py` (moved to `old/` in 60993f2) never had this code.
- I hashed both blocks (comment plus the next 9 lines) at `3cb6f39`, `faf0d9a` (interleave added), `ddde854` (last commit before the fix) and `ddde854:bugsynth/STAGE2_compilation/parsexml.py`. The hashes match at every commit (`e0a702db…` for pass5, `6f952a8a…` for the annotation). Only line numbers moved, e.g. pass5 at `ddde854:STAGE2_compilation/parsexml.py:2034-2037` and the annotation at `:2556-2559`.
- So the code was correct for what existed then. On 2026-04-03 every record was an Alloy instruction, and commit is an in-order prefix in the model (`STT_6.als:137`, per the 2026-10-29 claudelog entry). So "first record with committed=False" was the model's fnc.

## 2. pass_interleave: added 2026-05-27, into a pipeline that took the boundary from whatever list it got

- **Stub, `000f99e` (2026-04-24 18:47 +0000, "various updates").** `pass2_specify_instructions` gained an `additional_interleave` parameter that raised `NotImplementedError`. Its design comment (as of `11ff20f:STAGE2_compilation/parsexml.py:411-429`) lists what enabling it would need, and ends with: "downstream passes to treat the synthetic records like any other other_n (they should already, since the shape matches)". That comment is the explicit design reason the boundary code was never revisited: synthetic records were meant to look the same as Alloy records downstream.
- **Real pass, `faf0d9a` (2026-05-27 22:01 +0000, "updated lots of stuff", a cafe2 bulk sync: parsexml.py +513 lines, plus the new `run_config_STT_6_interleave.jsonc` and `STT_6_interleave.als` symlink).** It adds `def pass_interleave` (`faf0d9a:STAGE2_compilation/parsexml.py:907`), `_make_chain_step` with `"committed": False, ... "synthetic": True` (`:186-205`), and `batch_generate.py` runs the passes in this order: `pass2_5_specify_branches → pass_interleave → pass3_assign_operands → … → pass5_emit_llvm → emit_branch_annotations` (`faf0d9a:STAGE2_compilation/batch_generate.py:43-48`). The same diff removed the stub (`AUDIT.md` #4 in faf0d9a: "Real interleaving lives in `pass_interleave`"). The work itself is older than the commit: per that commit's `AUDIT.md`, the `STT_6_interleave.als` symlink dates from 2026-05-21, and per claudelog `testsets/STT_6_interleave/xml` was generated 2026-05-19. No claudelog entry records who wrote `pass_interleave` or when.
- `pass_interleave` knows where the model's boundary is. It computes it and then does not pass it on (`faf0d9a:…/parsexml.py:~966-1000`):

```python
    # Find first uncommitted instruction (chain steps go only in speculative region)
    first_uncommitted_idx = N
    for i, rec in enumerate(instructions):
        if not rec.get("committed", False):
            first_uncommitted_idx = i
            break
    ...
    # Sample L insertion positions within the [first_uncommitted_idx, N+L) window
    pool_size = uncommitted_count + L
    rel_positions: Set[int] = set(rng.sample(range(pool_size), min(L, pool_size))) if pool_size > 0 else set()
    new_instructions: List[Dict[str, Any]] = list(instructions[:first_uncommitted_idx])
    ...
    # Renumber PCs (synthetic and original alike — they're all in pc-order now).
```

- Relative position 0 can be sampled, so a chain step can land right before the model's fnc. The step has `committed: False`, so the unchanged loops in §1 pick it as fnc. lc is never affected because nothing is inserted before it. The faf0d9a diff did not touch either boundary block (same hashes). Interleave-aware code in that diff touches only pass3 (`is_synthetic` at `:1211`, for register-pool avoidance) and branch-target remapping. The faf0d9a `AUDIT.md` reviewed interleave's branch-target remap (#21) but not the boundary.

## 3. The `synthetic` flag predates interleave and was never used for the boundary

- Added in **`dd36e15` (2026-04-21)** for the `_xm_fallthrough_nop` injected by `pass2_5_specify_branches` (`dd36e15:STAGE2_compilation/parsexml.py:569-585`, with `"committed": False, "synthetic": True`). `documentation/docs/concretization.md:182` says: "Synthetic NOPs are marked `synthetic=True` so downstream passes can identify them." The NOP is inserted after an xm branch, which is after the boundary in practice, so it never became fnc. That is probably why skipping synthetic records in the boundary code never came up.
- Before the fix, `synthetic` is read only in pass3 (`is_synthetic`, mainline `ddde854:…/parsexml.py:1515`), in the STL pass (`:1006`, skips synthetic stores), and in bugsynth's `_otb_target_alias` (`ddde854:bugsynth/STAGE2_compilation/parsexml.py:381`, to find the base ALU). Nothing used it in lc/fnc selection. `git log -S commit_boundary -- '*.py'` hits only on the `ann["commit_boundary"]` dict key, never on a function, until the working-tree fix.

## 4. bugsynth fork

- `bugsynth/STAGE2_compilation/parsexml.py` first appears in `9338bea` (2026-10-20 23:44 +0000, "cafe2 June work: bugsynth, …"). Its two boundary blocks are identical to mainline (same hashes, `ddde854:bugsynth/…:1920-1923` and `:2411-2414`). The fork did not handle the boundary any differently.
- It does add a different placement for `interleave.otb_target` (`ddde854:bugsynth/…:1169-1184`): the chain is inserted right after the first uncommitted branch, at or after the model's fnc. That path happens to leave fnc on the Alloy instruction when fnc is that branch. This is a side effect of OTB placement, not a boundary rule. The default random-position path in the fork has the same bug (2838/8000 and 4264/8000 bad boundaries in cafe2 `_otb_search_c1/_c2`, per `wiki/design/COMMIT_BOUNDARY.md:11`). The uncommitted working tree adds a matching `commit_boundary()` to the fork ("Same rule as the mainline …").

## 5. Did any doc or log claim lc/fnc were pinned under interleave?

No. I grepped the pre-fix tree (`git grep ddde854 -- '*.md'`) and the current `claudelog.md`, `CLAUDE.md`, `wiki/`, `bugsynth/`, `STATUS.md` and `documentation/` for `first_noncommitted`, `last_committed`, `fnc`, `commit_boundary`, `interleave` and `synthetic`.

- `CLAUDE.md`'s chain-interleaving note and the `pass_interleave` docstring say chains go into "the uncommitted (speculative) region". Neither mentions lc/fnc.
- `documentation/docs/concretization.md:547` defines `commit_boundary` as "the boundary between committed and speculative instructions in program order". That describes the list, not the model, and it does not mention interleave.
- Many claudelog entries treat lc/fnc as "the model's window" (e.g. 2026-06-08 5:invisispec, "lc/fnc is fundamental"). None checks what lc/fnc are on interleaved variants.
- The first written mention of the problem is claudenotes `2026-10-28 commit-boundary-q`, then claudelog `2026-10-29 — commit-boundary-q`, Issue 1: "lc/fnc are then recomputed (`:1762-1769`), so a chain step can become fnc … How often this happens … has not been counted." Then claudelog `2026-10-29 — commit-boundary-fix` measured it (624/1600 = 39%) and wrote the rule into `wiki/design/COMMIT_BOUNDARY.md` §1.
- So the belief that lc/fnc "were always pinned" was an unwritten assumption, never a documented property of the code.

## 6. Timeline

| Date | Commit | Event |
|---|---|---|
| 2026-04-03 | `3cb6f39` | lc/fnc loops written in pass5 and emit_branch_annotations (`alloy/parsexml_kind.py`); correct because there are no synthetic records |
| 2026-04-12 | `60993f2` | file moved to `STAGE2_compilation/parsexml_kind.py` |
| 2026-04-21 | `dd36e15` | renamed to `parsexml.py`; `synthetic: True` introduced for `_xm_fallthrough_nop` |
| 2026-04-24 | `000f99e` | `additional_interleave` stub with the comment that downstream passes should treat synthetic records like any other |
| ~2026-05-19 to 05-27 | (uncommitted, cafe2) | interleave developed; STT_6_interleave testset generated |
| 2026-05-27 | `faf0d9a` | `pass_interleave` committed; chain steps `committed: False`; boundary code untouched |
| 2026-10-20 | `9338bea` | bugsynth fork synced; same boundary code; `otb_target` placement avoids the bug only on that path |
| 2026-10-28/29 | (logs) | commit-boundary-q finds the problem; commit-boundary-fix adds `commit_boundary()` (uncommitted working tree, mainline and bugsynth) |

## 7. Implication

Every interleaved testset generated from 2026-05-27 (and the pre-commit testsets from ~05-19) up to the 2026-10-29 fix may have fnc on a chain step. That covers STT_6_interleave, STT_all, `_otb_search_*` and bugsynth default-path variants. Results on those testsets used a synthetic fnc for the `--fnc-commit-stall-pc` hook and the `fnc_retire` window edge. Audit with `python3 STAGE2_compilation/audit_commit_boundary.py testsets/<model>` and regenerate from `llvm` (see `wiki/design/COMMIT_BOUNDARY.md`).
