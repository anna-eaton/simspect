# Staged STT build: RI-minimal baseline, operands PINNED, stage 2 strictly contains the skeleton

**Design (Anna, 2026-10-30).** Two phases, replication first. The staged STT build is:
- **Stage 1 (baseline):** enumerate minimal leak **skeletons** with **RI-minimality only** (operand-minimality RO **off**). Each skeleton has **concrete, pinned operands** — no operand freedom, no blank/unspecified slots.
- **Stage 2:** a model that **strictly contains** a stage-1 skeleton — every skeleton instruction *and operand* (roles + `rf`/`ddi` edges) is **pinned by the seed and never relaxed** — and only **adds** interleave/padding structure around the fixed skeleton.

This supersedes an earlier draft of this doc that argued operands should be left free (RO-off "matches the target"). That was wrong per Anna's design: we **do not** rely on operand freedom; we **pin** operands and forbid relaxing them in stage 2. The RO-vs-RI conclusion below is unchanged; the operand-freedom framing is replaced.

Perfect bit-for-bit replication of current STT_6 is **not** the bar (Anna: "don't need perfect replication") — a clear, inspectable decomposition is. See the honest trade-off in the last section.

---

## Why RI-only and not RO+RI (unchanged — RO over-prunes)

From the real model (`STAGE1_alloy/models/STT_6.als:301-311`), the run block `gen_useful_litmus` minimizes on **RR** (per-branch resolution, non-boundary), **RC+RR** (boundary), and **RS** (per-state) — there is **no RO clause and no RI clause**. The staged baseline `STT_6_core.als` adds RO (`:301`) and RI (`:303`).

Adding **RO** to the baseline enumerates only leaks where *every operand is individually necessary* — a strict subset. Measured (`TWO_STAGE_STT_FEASIBILITY.md`): RO+RI reconstructs only **48/80** of the exhaustive N=3 set; the missing **32 are all `br_x`-gating**. Mechanism: a `br_x` used as a gate has a leak-irrelevant condition operand, so RO deletes it → the instance fails RO-minimality; combined with `no_extra_inst` (`STT_6.als:313`, which forbids a zero-operand `br_x`) **no RO-minimal `br_x`-gate can exist.** RI-only reconstructs **80/80**. So RO is wrong for replication — it is *more* minimal than the model we are reproducing, and it can only *shrink* the set, so it can never help coverage either. **RO is kept documented and brought back only if a concrete Phase-2 need ("most-minimal catalog") appears.**

## Your operand concern, answered by the design (pin, don't free)

The worry was: *won't RO-off leave overspecified operands and create duplicates, because stage 2 isn't pruning/pinning?* The design removes this **by construction**:

- **Operands are pinned, not free.** Stage-1 skeletons carry concrete operands; there are no blank slots to be filled nondeterministically later. So there is no operand overspecification to worry about within a skeleton.
- **Stage 2 contains the skeleton and does not relax it.** The seed pins every skeleton instruction and operand (roles + `rf`/`ddi`); stage 2 may only *add* structure (interleave/padding) around the fixed skeleton. It cannot re-open or re-assign the skeleton's operands.
- **Operand variety lives in Stage 1, not Stage 2.** Because stage 2 does not relax operands, any operand *variation* that STT_6 has must be enumerated as **distinct skeletons in stage 1** — not produced by stage-2 fleshing. This is exactly "no operand freedom in the second stage": the operand degrees of freedom are resolved up front, in the skeleton enumeration, where they are explicit and inspectable.
- **Cross-shard duplicates** (one full instance regenerated from two different skeletons) are removed by taking the **union on the canonical fingerprint** (operand *role* `(pc,slot)` + `rf`/`ddi` edges; atom-name-invariant) — the same dedup the single-stage model already relies on.

## No over-count is structurally possible (stage2 ⊆ STT_6)

Stage 2 is **STT_6 plus constraints** (the `seed_core` pin, plus the "operands pinned / not relaxed" requirement). Constraints only *shrink* a solution set. So every stage-2 solution is a valid STT_6 solution ⟹ the union over all skeletons **⊆ STT_6**. It is impossible for the build to emit an instance or operand STT_6 would not. The only way the two can differ is the other direction.

## The one open point: coverage (an under-count), at N≥4

Equality reduces to **coverage** (⊇): does every leaking STT_6 instance reduce to at least one **emitted** RI-minimal, operand-pinned skeleton, such that pinning that skeleton + adding structure regenerates it? If yes, equality holds. This is the N≥4 exactness that is **not yet proven** (N=3 is the trivial base: RI vacuous, interleave empty). The honest risk is a **missed** instance (under-count), never excess/duplicates. Your "something isn't pinned" instinct is right that there is an open question — it lands on coverage.

## How Phase 1 is verified

At a **small exhaustible bound** (STT_6 reaches real UNSAT, not the 100k cap — `REACH_UNSAT_ENUMERATION.md`): enumerate STT_6 → `A`; enumerate RI-only skeletons → seed+contain each into STT_6 → union by canonical fingerprint → `B`; check `A == B`, reporting `|B\A|` (must be 0 by stage2 ⊆ STT_6), `|A\B|` (coverage — the real test), and dupes-removed.

## Honest trade-off (why this is a design choice, not free)

Current STT_6 has RO **off** and **does** allow operand freedom (blank slots filled from the free pool at concretization — this is also how interleave/OTB hooks on). Pinning operands and forbidding stage-2 relaxation means the staged build's per-instance operand behavior is **more specified** than STT_6's, so the two are **not guaranteed bit-identical** — operand variety is recovered via *more skeletons* rather than via stage-2 fleshing. Anna accepts this for a clearer decomposition (replication is the goal, not bit-identity). If exact bit-parity with STT_6's operand-free enumeration is ever required, that is a separate, later question.
