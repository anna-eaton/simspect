# Potential Model Fix — SPT/STT protection set over-approximates "speculatively produced" as "secret"

**Status:** PROPOSAL ONLY. Not applied — Alloy model edits need owner approval.
**Model:** `STAGE1_alloy/models/SPT_6_oneLP.als` (and `SPT_6.als`).
**Symptom:** ~99.9% of the SPT `ld` "hits" are constant-address loads that SPT correctly
untaints — false positives. See `mdsToRead/STT_BRANCH_LEAK_ROOTCAUSE.md` for the (separate) branch
checker bug; this file is about the **load / Alloy-model** over-approximation.

---

## 1. The bug, precisely

A load is flagged a leak (`one_insecure_speculation_scheme_p`, line 268) iff its **address operand**
is both a speculative transmitter (`speculative_xmit_p`) and in the **protection set**
(`last_committed_protset_p`). The protection set is the problem:

- `leakage_function` (line 339) = `Loads.inaddr + Branchxs.inreg` → **every** load address is a
  candidate transmitter, taint-agnostic.
- `hardware_protection_policy` (line 337) =
  `Instruction.operands - ((Inreg + Inaddr) - Instruction.outreg.rf)` → seeds the protection set with
  essentially **all operands**, only excluding `Inreg`/`Inaddr` that have *no rf edge at all*.
- `last_committed_protset_p` / `a[]` / `prot_set_propagation_p` (lines 222-236) propagate that seed
  forward over `op_edges = rf + ddi`.

Net effect: **any value produced under speculation ends up "protected" (treated as secret)** — even a
register written by a speculative ALU op (`TOther`) that reads only constants (no inputs at all).

### Concrete instance (`inst-000003`)
```
xmit  = Instruction$0  TLoad (uncommitted), address state = Reg_s$0
Reg_s$0 produced by Instruction$3 (TOther, SPEC) which reads NOTHING (constant)
```
gem5/SPT untaints `Reg_s$0` (no data path to a speculative load) → the load issues with a **public**
address → **not a leak**. Alloy flags it anyway. The 2026-06-01 `.als` edit only removed `Inaddr` with
*no rf edge*; this address *has* a producer (the const-op), so it slips through. That is why const-addr
"hits" persist after the edit, and why the testset (whose provenance `.als` matches the edited model)
still contains them.

**Root mismatch:** Alloy treats "produced under speculation" as secret; SPT/STT only treat "derived
(transitively, by data flow) from a speculative LOAD / memory read" as secret.

---

## 2. The fix (semantics)

Define the protection/taint set as a **forward data-flow closure from the real secret sources**, with
**monotone (union) semantics**:

1. **Sources** = outputs of speculative (uncommitted) loads / speculative memory reads — i.e. the
   operands that actually carry a secret brought in under misspeculation. (For STT/SPT this is the
   `outreg`/`inmem` of uncommitted `Loads`, plus the last-committed protected memory if modeled.)
2. **Propagation** = forward closure over data-dependency edges (`ddi` for register flow, `rf` for
   memory/STLF flow): an operand is protected iff it has an incoming edge from an already-protected
   operand.
3. **Union, never AND:** an instruction's output is protected iff **≥1** of its inputs is protected.

### Consequences (why this is the right shape)
- A constant-producing op (an op with **missing / no input operands**) is **not** a source and has no
  incoming protected edge → its output is **untainted automatically**. **No need to enumerate
  "unspecified" / missing operands** — they are simply absent from the edge relation.
- Monotone union guarantees a missing/untainted operand can **never untaint** a value that already has
  a tainted input. (The "missing operand accidentally clears taint" risk only exists under
  **AND**-semantics — do not use AND.)
- STLF-from-constant-store and pure-constant addresses both fall out as untainted, matching SPT.

So the fix is a change to the **seed + propagation definition**, not an operand-enumeration exercise.

---

## 3. Where to change it (anchors — verify before editing)

| line | current | change |
|---|---|---|
| 337 | `hardware_protection_policy = Instruction.operands - ((Inreg+Inaddr) - outreg.rf)` | replace the *seed* with the real secret sources only: speculative-load outputs (uncommitted `Loads.outreg` + their `inmem`), not "all operands" |
| 222-236 | `a[]` / `last_committed_protset_p` propagation over `op_edges` | keep the forward closure, but seed it from step-1 sources; ensure union semantics |
| 268-272 | `one_insecure_speculation_scheme_p` = `protset & speculative_xmit` | unchanged in shape; it becomes correct once `protset` is source-derived |
| 339 | `leakage_function = Loads.inaddr + Branchxs.inreg` | optional: leave (still enumerate all addresses), the closure will exclude const-addr ones; or additionally require the inaddr to be closure-reachable |
| 350 (oneLP only) | STLF subtraction hack | becomes redundant once taint is source-derived (STLF-from-constant naturally untainted) — can likely be removed |

---

## 4. Validation criterion

After the change, re-enumerate `SPT_6_oneLP` and confirm:
- The `diag_constaddr_load.py` **known** set drops to ~0 (const-addr loads are no longer enumerated as
  leaks at all).
- The 3 current LL cases (`inst-001746/004097/004532`, address from a *speculative load*) **remain**
  enumerated (they have a real taint source) — those are the genuine signal.
- br_x / other behavior unchanged.

A cheap pre-check before regen: the property "xmit address closure-reaches a speculative load" is
exactly what `diag_constaddr_load.py` already computes from the XML — the post-fix enumeration should
match its **unknown** set.

---

## 5. Caveats
- Don't touch `.als` without owner sign-off (per project rules).
- Regen is from Stage 1 (Alloy) — full re-enumeration of the testset. The user's current preference is
  to **mask** via the diagnostic rather than regen; this doc is the durable record of the *real* fix
  for when regen is on the table.
- This is independent of: the duplicate-PC Stage-2 codegen bug (relaunch-scoping) and the `check_br`
  squash-tick fix (checker). See `claudelog.md`.
</content>
