# Design Decisions

Cross-stage invariants and rationale that aren't obvious from the code alone.

## Invariant: xmit branches are always resolved (STT_6)

In every instance Alloy emits for STT_6, the transmitter (`xm`) instruction, **when it is a branch (`TBranchx`)**, has `isresolved = true`.

Empirical check (`testsets/STT_6/xml`, 30,000 instances sampled):

| xm kind | resolved | unresolved |
|---|---|---|
| `br_x` | 9,995 | **0** |
| `ld`   | (n/a)    | (n/a)      |

### Why this should hold (semantic argument)

For a branch to *xmit*, the leaked operand is its input register (`leakage_function = Loads.inaddr + Branchxs.inreg`, see `STT_6.als:315`). For that input read to count as "speculative", the branch must lie in the speculation contract — `speculation_contract_p = uncommitted & has_unresolved_brs_p` (STT_6.als:312). `has_unresolved_brs_p` requires *some* earlier unresolved branch in spo.

A branch can't initiate its own speculation: the protset propagation that defines `speculative_xmit_p` flows through `prot_set_propagation_p` starting at the first instruction and stepping along `spo`. For the xm branch's inreg to land in `last_committed_protset` *because* of the xm branch itself, that branch's own input read would have to predate its own unresolved status — a contradiction. So the speculation window the xm reads from must be opened by an *earlier* unresolved branch; the xm itself ends up resolved.

This is **not stated as an explicit `fact`** in `STT_6.als`. It emerges from the combination of `speculation_contract_p`, `prot_set_propagation_p`, and the `tag_xm` overlap requirement. The empirical sample (30k instances, 0 counter-examples) is the practical guarantee.

### Where the code depends on this invariant

`STAGE2_compilation/parsexml.py:pass2_5_specify_branches` injects a synthetic fall-through NOP after an xmit branch when the next list entry is also a branch (so that the speculative fall-through path has something to fetch). The NOP is assigned `pc = br_pc + 1`. Because pass1 numbers PCs as `enumerate(order)`, the *next* instruction in the list already has `pc = br_pc + 1` — so the injected NOP would deterministically duplicate a PC, and `pass5_emit_llvm` would emit two `bb_<pc>:` labels → LLVM parse error.

The code only reaches the NOP-insertion branch for **unresolved** xm branches (resolved branches `continue` at parsexml.py:737). Since every xm branch in STT_6 is resolved, the buggy path is unreachable. The 8.4% of STT_6 instances that have an xm branch immediately followed by another branch all have the xm *resolved*, so they take the `correctly_not_taken` path which doesn't insert a NOP.

### What to do if you change the model

If a future Alloy model relaxes constraints such that an xm Branchx can be unresolved (e.g., a different speculation contract, a relaxed `tag_xm`, a new defense model with weaker resolution requirements):

1. Re-run the empirical scan (`xm_branch_unresolved` counter from the audit notes) on the new testset.
2. If non-zero counts appear, fix `pass2_5_specify_branches` before generating LLVM. Options:
   - Skip NOP insertion when `instructions[idx+1].pc == br_pc + 1` (the next instruction already serves as something-to-fetch on the fall-through path).
   - Renumber PCs after NOP insertion and rewrite all `bb_<pc>` targets accordingly (invasive — needs a sweep over `branch_annotations` of every prior branch).
3. The misleading comment at parsexml.py:824 (`"Not needed: we use explicit pc values everywhere"`) is wrong in that case; remove it as part of the fix.

Related: audit item #14 (now resolved as "documented dormant bug").
