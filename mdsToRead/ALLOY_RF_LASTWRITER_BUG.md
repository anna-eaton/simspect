# Alloy bug — `rf` is not constrained to the *most-recent* writer of a state

**Status:** DIAGNOSIS. Model edit needs owner approval — this doc is the durable write-up, no `.als`
was touched.
**Model:** `STAGE1_alloy/models/SPT_6_oneLP.als` (almost certainly the other SPT/STT models too — same
`rf` facts).
**One-line:** `rf` only requires a producer and consumer to **share a state** (`same_state_rf`); it does
**not** require the producer to be the *most-recent* writer of that state, and nothing forbids a state
from having **two writers**. So the solver can route an rf edge from an *older* writer **past a newer
writer of the same state**. After concretization (one state → one register) the newer write **clobbers**
the register, the consumer reads the wrong value, and the program that actually runs is not the program
the model reasoned about.

---

## 1. What you thought was enforced vs. what is enforced

You expected: *"rf comes from the most-recent writer only"* (≈ "each state sig gets its own thing").
The facts that actually exist (`SPT_6_oneLP.als:156–159`):

| fact | line | what it actually says | does it give last-writer? |
|---|---|---|---|
| `constrainrf` | 156 | `rf ⊆ outs → ins` (edges go output→input) | no |
| `one_entering_rf` | 157 | each consumer has **≤1** producer (`lone rf.o`) | no — one producer, but says nothing about *which* |
| `unidirectional_rf` | 158 | `rf`+`spo` acyclic → producer is *earlier* than consumer | no — earlier, but **any** earlier, not the latest |
| `same_state_rf` | 159 | producer.opstate **=** consumer.opstate (same register/mem state) | **no** — this is the one that's easy to mistake for last-writer, but it only pins the edge to a *shared* state; it permits **multiple writers** of that state and lets `rf` pick any of them |

There is **no** fact of the form "no other writer of the same state lies between the rf-producer and
its consumer", and **no** "each state has a single writer". I grepped the whole model for
`rf`/`spo`/`writ`/`recent`/`last`/`between`/`opstate` — lines 156–159 are the complete set of `rf`
constraints. So *last-writer is simply absent.*

Why `same_state_rf` is **not** last-writer: it constrains each rf **edge** to be same-state, but says
nothing **across** edges or about **other writers**. Two independent rf chains may share one state, and a
chain's producer need only be *some* same-state output that is *earlier* — even if a *different*
same-state output is written in between.

(If instead each write were forced to a **fresh** state — "each state sig gets its own thing" — then
`same_state_rf` + `one_entering_rf` *would* imply last-writer, because a consumer's state would have
exactly one writer and no clobber could exist. That single-writer invariant is the thing that's missing.)

**`one_entering_rf` is *not* that invariant — they live on different axes.** `one_entering_rf` counts
**rf edges into a consumer** (`rf.o` = producers of `o`; `lone` ⇒ each *read* names ≤1 writer). The
missing rule is about **outputs sharing a `Reg_s`** (how many *writes* land on one register), which `rf`
never mentions. In inst-008554 both hold at once:
- `Inaddr$0` (pc2) has exactly one producer `Outreg$0` (idiv) — `one_entering_rf` ✔
- `Inaddr$1` (xmit) has exactly one producer `Outreg$1` (load) — `one_entering_rf` ✔
- yet `opstate` puts **both** `Outreg$0` and `Outreg$1` on `Reg_s$0` → **two writers of one state**.
`one_entering_rf` is satisfied because the two writers feed two *different* consumers via two separate
edges; it never inspects `opstate`, so it cannot notice the register is double-written. What it does not
guarantee is that the single producer a read names is the **most-recent** writer of the shared register —
pc2 names the idiv, but the load writes the same `Reg_s$0` later (still before pc2), so on one physical
register pc2 reads the load. Slogan: `one_entering_rf` = "one writer **per read**"; the missing rule =
"the named writer is the **latest** writer of that register."

---

## 2. The concrete instance (`inst-008554`, SPT_6_oneLP)

The whole 6-instruction gadget uses **one** register state, `Reg_s$0`, and **all four** register operands
map to it:

```
opstate:  Outreg$0 -> Reg_s$0      Inaddr$0 -> Reg_s$0
          Outreg$1 -> Reg_s$0      Inaddr$1 -> Reg_s$0
```

Program order (`spo`, = `idx` order; `idx_matches_spo` line 304):

```
 pos0  Instruction$5  TOtherx (committed)   writes Outreg$0  ──rf──▶ Inaddr$0  (pos2 pc2)     CHAIN A
 pos1  Instruction$4  TLoad   (uncommitted) writes Outreg$1  ──rf──▶ Inaddr$1  (pos5 xmit)    CHAIN B
 pos2  Instruction$3  TLoad   (the "pc2" intermediate load)  reads  Inaddr$0
 pos3  Instruction$2  TBranchn
 pos4  Instruction$1  TBranchn
 pos5  Instruction$0  TLoad   (xmit)                         reads  Inaddr$1
```

Two **independent** rf chains, both on `Reg_s$0`:
- **A:** `Outreg$0` (idiv, pos0) → `Inaddr$0` (pc2, pos2)
- **B:** `Outreg$1` (load, pos1) → `Inaddr$1` (xmit, pos5)

The rf edge **A** (`idiv@pos0 → pc2@pos2`) is the violation: the **load@pos1 writes the same state
`Reg_s$0`** and sits *between* pos0 and pos2. The most-recent writer of `Reg_s$0` before pc2 is the
**load (pos1)**, not the idiv (pos0) — but `rf` points pc2 at the idiv anyway. The model allows it
because no fact forbids the intervening same-state write.

---

## 3. Why it produces a wrong result downstream

Concretization is faithful and simple: **one state → one register**, here `Reg_s$0 → %rax`
(`idivq` also hard-requires `%rax`). So in the emitted `.ll`/`.s`:

```
pc0 idiv ... ; movq %rax, <out>        ; Outreg$0  (idiv result)  -> %rax
pc1 movq (%rsi), %rax                  ; Outreg$1  (load result)  -> %rax   ← CLOBBERS %rax
pc2 movq (%rsi,%rax), %r8              ; reads %rax  → gets the LOAD, not the idiv  (rf-A broken)
pc5 movq (%rsi,%rax), %r15  (xmit)     ; reads %rax  → the load     (rf-B, intended)
```

`%rax_2 = load` is passed as the index to **both** pc2 and the xmit in the IR — pc2 was supposed to read
`%rax_1 = idiv`. The Alloy rf edge A is silently dropped.

Consequence chain:
1. pc2 now reads the **secret** (the load value), not the benign idiv value.
2. pc2 is **architectural** in gem5 (it precedes the real mispredict branches), so it **commits** and its
   secret-dependent cache access architecturally transmits the secret.
3. gem5's `untaintMemTransmit` (SPT VP-untaint, per **physical register**) clears `%rax`'s taint when pc2
   reaches its visibility point; the speculative xmit shares `%rax`, so it is **no longer fenced** →
   `reached_cache`.
4. The model, reasoning about the *intended* program (pc2←idiv, xmit←load, distinct), flags the xmit as
   an insecure speculative transmitter. gem5, running the *concretized* program (pc2←load), sees the
   secret already transmitted architecturally and does not fence. **Discrepancy = this bug, not a real
   leak.**

**Ground-truth evidence (not inference):** planting a sentinel at pc1's load source (`40(%rsp)`: 0→0x100)
moved **both** pc2's (committed) and the xmit's cache lines `0x35c0 → 0x36c0`. So pc2 really reads the
load's value, and the xmit's address really is secret-dependent — exactly the clobber above. (`%rax`
taint is stored per **physical** register: `base_dyn_inst_impl.hh:416/450 → cpu->readPartialTaint /
setPartialTaint`; the VP-untaint is `cpu.cc:2135`, called from `lsq_unit_impl.hh:1207`. `--disableUntaint=1`
fences it; `--fwdUntaint=0 --bwdUntaint=0` does not — so it is the VP rule.)

---

## 4. How pervasive (this is not one stem)

Two measures, distinct — don't conflate:
- **Single-register collapse:** 800/800 sampled base XMLs have exactly one `Reg_s`; 721/800 (90%) have
  that state written by ≥2 outputs (collision-*capable*). This is the structural setting.
- **Actual clobber (the bug):** an rf edge that reads *past* a newer same-state write. A 4,000-XML random
  sample of the existing testset: **2,344/4,000 = 58.6%** carry ≥1 clobbered rf edge. So **the majority of
  the testset has unrealizable register dataflow** that concretization silently rewrites.

Of the 19 `reached_cache` ld "hits" in `results/SPT_6_oneLP_fence__20260602_013615`, **13/19 are
clobber-shaped** (this bug). The other **6/19 are NOT clobber-shaped** — they are a *separate*,
still-unexplained signal and must not be folded into this bug.

**Correction to an earlier draft:** do **not** claim this bug also explains the bulk "const-addr" ld
artifacts. Those are the *separate* protection-set over-approximation documented in
`POTENTIAL_MODEL_FIX_constaddr_taint.md` (address fed by a const ALU op, no load). The single-register
collapse may co-occur, but the clobber bug specifically accounts for the **load→load `reached_cache`**
subset (13/19 here), not the const-addr bucket. Re-measure both independently after a fix.

Why exactly one `Reg_s`: nothing forces more. `same_state_rf` lets all register operands share a state,
`no_extra_State` (101) forbids unused states, and Alloy/​symmetry-breaking returns the most compact model
— so the solver uses a single register and the 100k enumeration fills up with these.

---

## 5. Fix — Option A (chosen: it's how real hardware behaves; reuse is legal, a read sees the latest write)

For every rf edge, forbid an intervening same-state writer:

```alloy
fact rf_from_most_recent_writer {
  all prod: Instruction.outs, use: prod.rf |
    no other: (Instruction.outs - prod) |
        other.opstate = prod.opstate
        and (prod.(~operands))  -> (other.(~operands)) in ^spo   // prod  before other
        and (other.(~operands)) -> (use.(~operands))   in ^spo   // other before use
}
```
Preserves register reuse where it's harmless (a dead write with no rf edge is still allowed); only kills
edges that read *past* a newer same-state write. Because `other` ranges over all `outs` and the test is on
`opstate`, it covers **memory** too (an intervening store clobbering a load's store-forward), not just
registers.

**Validated on a copy (no real `.als` touched):**
- Inserted the fact into a copy of `SPT_6_oneLP.als`; `a6CountModels` still **SAT** — 150/150 instances
  enumerate, so the fact doesn't starve the model.
- Clobber scan: **patched = 0/150** clobbered rf edges vs **original = 1/150** in the same first-150
  batch. (The fact is the exact logical negation of the clobber, so elimination is guaranteed; the run
  just confirms the encoding parses and constrains as intended.)

*(Rejected alternative — Option B, single-writer-per-state `all s: State | lone (Instruction.outs &
opstate.s)`: simpler but forbids **all** register reuse, which is unrepresentative of real code. Owner
chose A.)*

**Scope:** the buggy rf facts (`same_state_rf` + friends, no last-writer) are shared by **17 models** —
all `STT_*`, `SPT_6*`, `Recon_6`, etc. (`grep -l "fact same_state_rf" STAGE1_alloy/models/*.als`). The fix
belongs in every model that enumerates a testset in use. Each is a Stage-1 change ⇒ **regen the whole
testset from Alloy (`xml` onward)** — widest relaunch scope. ~58.6% of the SPT_6_oneLP testset is
clobber-shaped, so prior ld results on these testsets are broadly contaminated, not edge-case.

*(`o.(~operands)` is the owning instruction; `^spo` is strict program-order-after. Verify in the analyzer
before committing to all 17.)*

---

## 6. Attribution

- **Not parsexml** — it faithfully maps one Alloy state to one register; given the instance, `%rax` for
  both writers is correct.
- **Not gem5** — it correctly runs the concretized program and `untaintMemTransmit` is sound for *that*
  program (pc2 genuinely transmits the secret architecturally).
- **Stage-1 `.als`**: `rf` lacks a most-recent-writer / single-writer-per-state invariant, so the solver
  emits instances whose register dataflow is unrealizable, and concretization silently rewrites it.

Supersedes the "19 = real model-vs-gem5 discrepancies / genuine signal" line in
`POTENTIAL_MODEL_FIX_constaddr_taint.md §6a/§6c` — these are **not** real leaks; they are this rf bug.
