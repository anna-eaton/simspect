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

**Scope of the fix (narrow — read this first):** the bug is **only** that values with NO load/memory
in their data-flow (i.e. constants — including a speculative ALU op fed only by immediates) are being
marked protected. **Load outputs must stay tainted.** This is the SPT-correct rule and the key
difference from STT:
- A **load's output (outreg) is tainted** — and stays tainted. A *committed* load only gets its
  **inaddr** (address operand) untainted (the address is non-speculative); its loaded *value* stays
  tainted, because that value could be a **non-speculative secret** (SPT's scope is broader than STT —
  STT untaints a load output at its visibility point, SPT does **not**).
- The **only** ways a load's output legitimately leaves the protset: (a) **STLF from a store whose
  data is untainted** (clause 5), or (b) it's genuinely a **constant** (no memory read anywhere in its
  data-flow). "Safe / committed / before-the-branch" is **NOT** a valid reason — do not add one.

So define the taint set as a **forward closure with monotone (union) semantics** whose sources are
**load outputs (`Loads.outreg`) and memory reads** — NOT "all operands," and NOT gated on
commit/speculation status:

1. **Sources** = `Loads.outreg` (every load's output) + read memory. (Plus the last-committed
   protected memory if modeled.)
2. **Propagation** = forward closure over data-dep edges (`ddi`, `rf`): an operand is protected iff it
   has an incoming edge from an already-protected operand.
3. **Union, never AND:** an op's output is protected iff **≥1** input is protected.

### Consequences
- A constant-producing op (no input operands, or all-immediate inputs) has **no** load/memory in its
  data-flow → its output is **untainted automatically** (this removes the const-addr false positives).
- A **load output is always a source → always tainted** — so load→load address chains stay protected
  (NOT untainted by this fix). Correct per SPT.
- Untaint is only via clause-5 STLF-from-untainted-store (kept) — not via safety/commit.

---

## 3. Where to change it (anchors — verify before editing)

| line | current | change |
|---|---|---|
| 337 | `hardware_protection_policy = Instruction.operands - ((Inreg+Inaddr) - outreg.rf)` | seed = **all** `Loads.outreg` + read memory (NOT gated on commit/speculation), not "all operands". Constants/const-ALU outputs fall out (no load in their cone); load outputs stay in |
| 222-236 | `a[]` / `last_committed_protset_p` propagation over `op_edges` | keep the forward closure, but seed it from step-1 sources; ensure union semantics |
| 268-272 | `one_insecure_speculation_scheme_p` = `protset & speculative_xmit` | unchanged in shape; it becomes correct once `protset` is source-derived |
| 339 | `leakage_function = Loads.inaddr + Branchxs.inreg` | optional: leave (still enumerate all addresses), the closure will exclude const-addr ones; or additionally require the inaddr to be closure-reachable |
| 350 (oneLP only) | STLF subtraction hack | becomes redundant once taint is source-derived (STLF-from-constant naturally untainted) — can likely be removed |

---

## 4. Validation criterion

After the change, re-enumerate `SPT_6_oneLP` and confirm:
- **Only the const-ALU-address hits drop out** (address derived purely from constants / no load in its
  cone). Those were the over-approximation.
- **Load→load hits STAY enumerated** — any xmit whose address chain reaches a `Loads.outreg` is still
  protected (a load output is tainted, regardless of commit/branch position). These are the genuine
  signal, NOT over-approximation. (Earlier drafts of this doc wrongly tried to untaint "safe /
  pre-branch" loads — that rule is deleted; it is not SPT-sound.)
- Untaint of a load output happens ONLY via clause-5 STLF-from-untainted-store. br_x / other unchanged.

---

## 5. Caveats
- Don't touch `.als` without owner sign-off (per project rules).
- Regen is from Stage 1 (Alloy) — full re-enumeration of the testset. The user's current preference is
  to **mask** via the diagnostic rather than regen; this doc is the durable record of the *real* fix
  for when regen is on the table.
- This is independent of: the duplicate-PC Stage-2 codegen bug (relaunch-scoping) and the `check_br`
  squash-tick fix (checker). See `claudelog.md`.

---

## 6. SPT taint semantics (the rule — get this right)

**A load's output (outreg) is tainted, and stays tainted.** It is NOT untainted by being safe,
committed, or before/after a branch. The only legitimate untaint of a load output is **STLF from a
store whose data is untainted** (clause 5). A *committed* load gets only its **inaddr** untainted (the
address is non-speculative); the loaded value stays tainted because it could be a non-speculative
secret — that is SPT's broader scope vs STT (STT untaints a load output at its visibility point; SPT
does not, and the STT-style `- (Loads & no_unresolved_brs_bf_or_is_p[p]).inmem` rule was deliberately
removed from the model for that reason).

**Constants are the only over-approximation here.** A value with NO load/memory anywhere in its
data-flow (a const ALU op fed by immediates) should never be tainted; that is the const-addr bug (§1–§2).

### 6a. Re-bucketing of the 34 SPT_6_oneLP_fence undiagnosed ld hits (CORRECTED)
- **15 = STLF, no cache packet** → `check_ld` false positive (xmit store-forwards, no cache line). For
  these, the relevant SPT question is whether the forwarding store's data is untainted (clause-5 legit
  untaint) — separate from the leak question (no cache line was brought in either way).
- **19 = `reached_cache`** (real cache packet, NOT fenced), xmit address fed by a **load output**.
  Per the rule above, that address is **tainted** and the model is **correct to protect it** (taint
  semantics stand — do NOT untaint it). BUT verified in gem5 (19/19, 2026-06-02), these are **NOT real
  leaks** — see §6c. The model-correct protection and the gem5-sound non-leak are **orthogonal axes**:
  the model rightly protects a tainted load→load address; gem5 rightly doesn't leak because the line is
  **architecturally pre-exposed by a committed load** (and the harness value is 0 → address constant).
  (This supersedes the earlier "19 = real model-vs-gem5 discrepancies / genuine signal" line, which
  over-claimed: the cache packet is real, but it is subsumed by an architectural access, so no *new*
  information leaks.)

### 6b. DELETED (wrong): the "untaint a safe / pre-branch / under-no-unresolved-branch load" idea
Any rule that removes a load output from the protset based on the load being safe / committed /
before-the-branch is **not SPT-sound** and is removed from this doc. Do not reintroduce it. Load
outputs leave the protset only via STLF-from-untainted-store or by being a genuine constant.

### 6c. Open: why does gem5/SPT not fence the 19 `reached_cache` load→load addresses?
The producing load's output should be tainted ⇒ the xmit's address tainted ⇒ SPT should fence the
xmit. It didn't (`taintedforwLoads=0`, real packet sent). Candidate causes to confirm with an SPT
taint-state debug flag on `/work/gem5-spt`: (a) `--fwdUntaint`/`--bwdUntaint` clearing the producer's
taint once it's resolved (an SPT untaint relaxation — is it sound?), (b) a real gem5 SPT
taint-propagation bug, or (c) STLF untaint reaching the address chain. Note: the loaded *value* here is
0 (zeroed-stack harness) so the address is effectively constant → likely no real *secret* exfiltrated,
but the **gem5-untaints-a-protected-load-output behavior is the real finding** regardless of the
constant value. Mirror analysis: STT slow-comm load→load (claudelog 08:30) — there the access is also
real and squash-tick is not a disqualifier.
