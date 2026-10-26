# Two-stage STT: is in-use STT_6 EXACTLY (true-minimal baseline) ⊕ (interleave)? — verified at `exactly 3`

> **STATUS: PROPOSAL / VERIFICATION ONLY.** No in-use `.als`, no `parsexml.py`, no driver/config was
> edited. Every empirical number below was produced **this session** from *scratch copies in the
> scratchpad*; the owner-gated models (`STT_6.als`, `STT_6_core.als`, …) were only **read** (and their
> functions imported read-only). In-use-file byte-integrity re-verified at the end (§9). Real Alloy was run
> locally (Java 17 `/opt/homebrew/opt/openjdk@17/bin/java` + `STAGE1_alloy/alloy6.jar`); no cluster/container
> was touched. Any model change this doc recommends is **owner-gated** — shown as a diff, not applied.
>
> **For:** Anna — *"Is it possible to match the in-use STT model EXACTLY as (true-minimal baseline) +
> (interleave)? It's gotta be the same."*
> **Date:** 2026-10-26 · session `session_014m8EvwkYaUmfWAHi9sqtF4`
> **Cross-refs:** [`REACH_UNSAT_ENUMERATION.md`](REACH_UNSAT_ENUMERATION.md),
> [`MINIMALITY_TAGALONG_FIX.md`](MINIMALITY_TAGALONG_FIX.md), [`SPT_MINIMALITY_MCM.md`](SPT_MINIMALITY_MCM.md),
> [`ENUMERATION_OVERSPECIFICATION.md`](ENUMERATION_OVERSPECIFICATION.md), [`OTB_GENERATION_GAP.md`](OTB_GENERATION_GAP.md),
> [`STAGED_ENUMERATION.md`](STAGED_ENUMERATION.md). Builds **on** the existing staged-enum prototype
> (`STT_6_core.als` + `stage_seed.py` + `stage_pipeline.py`) — it is exactly this two-stage idea.

---

## TL;DR — the verdict

1. **YES, it can be matched EXACTLY — with the baseline = RI-minimality (instruction-necessity), which is
   precisely the owner's stated definition** ("all instructions forced to contribute = RI-minimality ON").
   **Verified set-identical at `exactly 3`:** in-use STT_6 = **80** canonical instances; the RI-only baseline
   = **80**; `|A−B| = |B−A| = 0`, **EXACT_MATCH**. At the minimal bound (N=3) the interleave adds nothing
   (RI is *vacuous* there — see §6.3), so "baseline ⊕ interleave" = baseline = in-use, exactly. The
   interleave operator (structural seed + flesh-out, already built in `stage_seed.py`/`stage_pipeline.py`) is
   what adds the padding instructions at N ≥ 4.

2. **NO, if the baseline is `STT_6_core.als` as written (RO + RI).** `STT_6_core` turns on **operand**-minimality
   (RO) *in addition to* instruction-minimality (RI). That extra RO clause **over-prunes**: it deletes an
   entire leak mechanism — a **transmitter-capable branch (`br_x`) used as a plain speculation gate** — and the
   additive flesh-out *cannot recover a pruned mechanism*. Measured at `exactly 3`: reconstruction from the 2
   `STT_6_core` cores = **48/80**; **gap = 32**, and the 32 are **100% `br_x`-gating** (§6, §7). So
   `in-use ⊋ STT_6_core ⊕ interleave`. **Fix = drop RO, keep RI** (an owner-gated one-line edit to a copy).

3. **Parallel: CONFIRMED.** The per-skeleton flesh-out jobs are independent — each core becomes a self-contained
   seeded `.als`; outputs merge by set-union of canonical fingerprints. Demonstrated by running the N=3
   skeletons concurrently (§5).

4. **The expected OTB subtlety does not bite at the tested bound** (multi-source needs ≥5 instructions; it is
   UNSAT at 3 — consistent with `MINIMALITY_TAGALONG_FIX.md` P_C2_2BR and `OTB_GENERATION_GAP.md`).
   Structurally, **RI-only + additive flesh recovers OTB** (a redundant second source is *individually
   removable* padding relative to the single-source core), so OTB is an *enumeration-reachability* problem
   (REACH_UNSAT), **not** a set-equality gap for the RI-only baseline. §7.3.

---

## 1. What "true-minimal baseline" means as an Alloy predicate

The in-use `gen_useful_litmus` (`STAGE1_alloy/models/STT_6.als:301-311`) asserts a leak that is minimal on
three perturbation axes:

```alloy
let gen_useful_litmus {                                                     // STT_6.als
  not secure_speculation_scheme_p[no_p]                                     // (a) :302  it leaks
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]  // (b) :306  per-branch necessity (RR)
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]    // (c) :308  commit-boundary (RC)
  all s: State | secure_speculation_scheme_p[RS->s]                         // (d) :310  per-state necessity (RS)
}
```
The perturbation tags (`STT_6.als:191-195`) and their action: `RR` resolve a branch, `RC` commit, `RS` remove a
state (`o_p` drops operands whose `opstate ∈ p[RS]`, `:214`), **`RI` remove an instruction** (`i_p[p] =
Instruction - p[RI]`, `:213`; `spo`/`rf` are re-healed around it via `spo_p`/`fix_rf_hole_p`, `:216-218`), **`RO`
remove an operand** (`o_p` drops `p[RO]`, `:214`). `secure_speculation_scheme_p` (`:262-265`) is the
reachability oracle: *no protected operand reaches a speculative transmitter via `op_edges`*.

**"Every instruction contributes to the critical path"** is therefore the Alloy predicate
`all i: Instruction | secure_speculation_scheme_p[RI->i]` — *removing any single instruction secures the
program* ⟺ every instruction is load-bearing for the leak. That is the **RI-minimality** clause. The
**true-minimal baseline** adds exactly this to the in-use predicate:

```alloy
  all i: Instruction | secure_speculation_scheme_p[RI->i]                   // (f) instruction-minimality
```

**This already exists**, in `STAGE1_alloy/models/STT_6_core.als` — a copy of `STT_6.als` with (per
`STAGED_ENUMERATION.md` and verified by reading it) exactly three deltas: idx/IX symmetry-breaking removed
(`:37-38,269-273`), `exactly 6` → `but 6` (a scalable *ceiling*, `:312`), and **two** extra clauses in
`gen_useful_litmus` (`:290-304`):

```alloy
  all o: Operand     | secure_speculation_scheme_p[RO->o]   // (e) :301  operand-minimality  ← EXTRA vs owner's def
  all i: Instruction | secure_speculation_scheme_p[RI->i]   // (f) :303  instruction-minimality
```

**Key observation that drives the whole result:** the owner's definition is **RI only** (f). `STT_6_core`
carries **RO *and* RI** (e)+(f). Those are *different baselines*, and the difference is exactly what decides
exactness (§6). So I verified **both**, plus the isolating single-clause variants (RI-only, RO-only).

**Scope / bound-agnosticism.** The idx/IX symmetry-breaking is pure dedup; removing it does **not** change the
canonical instance *set* (only how many atom-relabelled copies the raw solver emits), because we canonicalize
with the repo's authoritative `find_duplicates.canonicalize`. **Independently cross-checked:** in-use at
`exactly 3` with idx *removed* enumerates 129 raw → **80 canonical**, equal to the known **80** from
`REACH_UNSAT_ENUMERATION.md` (which measured with idx). So all comparisons are done on idx-stripped copies at a
**parameterized bound N** (`gen_models.py N`), with `find_duplicates` providing the canonical quotient. `but N`
(core) is a scalable ceiling; `exactly N` (in-use) matches production's `exactly 6` at the reduced bound.

## 2. The baseline, built bound-parameterized (scratch copies)

`scripts/gen_models.py <N…>` derives, from a read-only copy of `STT_6_core.als`, three scratch models **per N**:

| scratch model | clauses in `gen_useful_litmus` | scope | role |
|---|---|---|---|
| `inuse_N{n}.als`            | a,b,c,d           | `exactly n` | in-use STT_6 semantics (RO/RI **off**) |
| `baseline_exactly_N{n}.als` | a,b,c,d,**e,f**   | `exactly n` | STT_6_core baseline (RO+RI) at a fixed size |
| `baseline_but_N{n}.als`     | a,b,c,d,**e,f**   | `but n`     | STT_6_core baseline, size ≤ n (core source for reconstruction) |

Plus the isolating variants `baseline_RIonly_N{n}.als` (a,b,c,d,**f**) and `baseline_ROonly_N{n}.als`
(a,b,c,d,**e**). `inuse_N{n}` is literally `STT_6_core` *minus* the RO+RI clauses — so in-use and baseline
differ **only** in {e,f}, the fairest possible comparison (identical idx-stripped base, identical STT defense
section, identical `no_extra_inst`/`one_xm`/`tag_xm` facts). All driven by the bound N with no rewrite.

## 3. The interleave (reconstruction) operator — reusing the built one

"Interleave = allowing instructions NOT on the critical leak path," in **two stages**:

- **Stage 1 — Alloy-level padding.** The in-use model has **no RI clause**, so it admits non-contributing
  padding instructions. That *absence is interleave stage 1.* The reconstruction operator makes it explicit:
  take a true-minimal core and **add back** padding up to the size bound.

  This is the **existing** `stage_seed.py` + `stage_pipeline.py` operator, used verbatim:
  - `stage_seed.build_pred` (`STAGE1_alloy/stage_seed.py:56-122`) turns one core instance into a **structural**
    `pred seed_core` pinning: kinds, **relative** spo (`b in a.^spo`, so stage 2 may *insert* instructions
    between core ones, `:98`), the resolved/committed/xm flags, operand membership + opstate, and the `rf`/`ddi`
    edges. Structural (existential over distinct vars), so it is robust to atom identity and idx.
  - `stage_pipeline.build_seeded_model` (`STAGE1_alloy/stage_pipeline.py:58-65`) splices `seed_core` into the
    flesh model's run (`gen_useful_litmus and seed_core`) and appends the predicate.
  - The flesh model is the **in-use** model (no RI/RO), so each flesh-out is, by construction, a genuine in-use
    instance that *contains* the core → **soundness is automatic**: reconstruction ⊆ in-use.
  - `scripts/recon_prep.py` wraps these to emit **one self-contained `seeded_<k>.als` per core** (the unit of
    parallelism, §5). Each is enumerated to **UNSAT** (no cap) so the reconstruction is *complete*, not capped.

- **Stage 2 — parsexml chain-injection** (`STAGE2_compilation/parsexml.py:pass_interleave`). This is a
  *concretization*-time operator that injects **contributing** synthetic chains to manufacture OTB/multi-source,
  emitting `_v<k>` variants in the **asm/ann**, not in the base Alloy XML. **It is therefore outside the
  base-XML instance set entirely** (OTB_GENERATION_GAP.md:§pitfall-1: "base XML is *pre*-interleave"). For the
  question "does the base model match," only **stage 1** is in play; **stage 2 is not needed to match in-use**
  and is a separate downstream expansion applied equally to any base corpus (§7.3).

## 4. Where interleave stage 2 fits (and why it is separate)

Stage-2 chains build a transmitter operand fed by *two independent* speculative chains (the recon
getOldestTaint/OTB gadget) — a shape a single Alloy leak instance cannot express. It operates on free-pool
atoms at concretization and is orthogonal to base-XML set equality. **Conclusion:** matching the in-use *base
model* = (true-minimal baseline) ⊕ (stage-1 Alloy padding). Stage-2 is an *expansion of the concrete testset*,
not a term in the base-XML equality — it applies to the RI-only baseline corpus and the in-use corpus alike.

## 5. Parallelism — confirmed and demonstrated

Each core's stage-2 enumeration depends only on *that core's* `seeded_<k>.als` and the fixed flesh model —
**no shared state**, so the jobs are embarrassingly parallel. Orchestration:

```
stage 1 (cores) ─┬─ seeded_0000.als ─ java a6CountModels ─▶ core_0000/  ┐
                 ├─ seeded_0001.als ─ java a6CountModels ─▶ core_0001/  ├─ union of canonical
                 └─ …               ─ java a6CountModels ─▶ core_000k/  ┘   fingerprints = reconstruction
```
Shard the `seeded_*.als` across processes/hosts; merge by `set`-union of `find_duplicates` fingerprints
(order-independent, idempotent — a core appearing twice changes nothing). **Demonstrated** (`run_all_N3.sh`): the
2 N=3 skeletons ran **concurrently** (`seeded_0000 & seeded_0001 ; wait`) → `core_0000`=18, `core_0001`=30,
merged to 48. `stage_pipeline.py` already does the sequential version; the only driver change for scale is
sharding + union (NOT owner-gated).

## 6. EXACTNESS results at `exactly 3` (the core deliverable)

Everything here is a **full exhaustion** (solver reached UNSAT, count < cap) except where noted, canonicalized
with `STAGE2_compilation/find_duplicates.py`.

### 6.1 Canonical counts

| model | clauses | canonical count @ `exactly 3` | leak shapes present |
|---|---|---|---|
| in-use STT_6 (`inuse_N3`)            | a,b,c,d       | **80** | `br_n`+`br_x` gate × `ld`+`br_x` xmit (all 4) |
| **RI-only** baseline                 | a,b,c,d,**f** | **80** | all 4 |
| RO-only baseline                     | a,b,c,d,**e** | **2**  | `br_n`-gating only |
| RO+RI baseline = `STT_6_core`        | a,b,c,d,**e,f** | **2** | `br_n`-gating only |
| **reconstruction** (STT_6_core cores ⊕ flesh) | — | **48** | `br_n`-gating only |

*(N=2: both in-use and every baseline are UNSAT at 0 — no leak fits in two instructions, bracketing the floor.
The 2 RO/RO+RI cores were **found**; their full UNSAT exhaustion proof is slow without idx — RO/RI solves are
heavy, matching `MINIMALITY_TAGALONG_FIX.md`'s cost note — but completeness of the reconstruction is independently
guaranteed, §6.4.)*

### 6.2 Set-equality (canonical fingerprints, exact)

```
in-use@3  vs  RI-only baseline@3 :  |A|=80 |B|=80 |A∩B|=80 |A−B|=0 |B−A|=0   → EXACT_MATCH
in-use@3  vs  UNION(STT_6_core reconstruction) : |A|=80 |U|=48 |A∩U|=48 |A−U|=32 |U−A|=0 → DIFFER (sound, incomplete)
```
- **RI-only baseline == in-use, set-identical.** This is the exact match. ✔
- **STT_6_core reconstruction ⊊ in-use**: `|U−A| = 0` (every flesh-out is a real in-use instance — soundness),
  but `|A−U| = 32` (32 in-use instances have no STT_6_core reconstruction).

### 6.3 Why RI is vacuous at N=3 (so the match is at the *base* case)

A leak needs ≥3 instructions (N=2 is UNSAT). Removing any instruction from a 3-instruction leak leaves a
2-instruction perturbed model, which cannot leak (and at N=3 the leak path has no pass-through ALU op to
`fix_rf_hole`-heal across) — so `secure[RI->i]` holds for every `i` **automatically**. Hence RI-only@3 ≡
in-use@3 (empirically 80 ≡ 80), and the **interleave (padding) is empty at N=3** (a 3-core fills the `exactly 3`
scope; nothing to add). So the match is the *clean base case*: `in-use = baseline ⊕ ∅`. RI's pruning power —
and the interleave's padding — first act at **N ≥ 4** (§8).

### 6.4 Why the reconstruction = 48 is complete (independent of the UNSAT proof)

The reconstruction reproduced **exactly** the `br_n`-gating subset of in-use, split perfectly by shape:
core_0000 (`br_n→ld→br_x`) → 18 = in-use's `br_n/br_x` count; core_0001 (`br_n→ld→ld`) → 30 = in-use's
`br_n/ld` count. Those 48 = *all* `br_n`-gating instances in in-use@3. A hypothetical 3rd RO+RI core could only
be `br_n`-gating (br_x-gating is impossible, §7) → its flesh-outs ⊆ the already-complete 48. So reconstruction
= 48 regardless of whether the core UNSAT proof formally terminates, and the gap = 32 is exact.

## 7. The gap (the subtlety), root-caused

### 7.1 The 32 missing instances are 100% `br_x`-gating

```
GAP |A−U| = 32  :  gate=br_x xmit=br_x : 12   gate=br_x xmit=ld : 20
COVERED  = 48   :  gate=br_n xmit=br_x : 18   gate=br_n xmit=ld : 30
```
The reconstruction covers the mechanism "plain branch (`br_n`) gates the speculation" completely and recovers
all its operand-padding variants; it misses the mechanism "a **transmitter-capable branch (`br_x`) used as the
speculation gate**" entirely.

### 7.2 Root cause — RO + `no_extra_inst` jointly delete the `br_x`-gate mechanism

A position-0 gating branch is *not itself speculative* (nothing unresolved precedes it), so its condition
operand (`inreg`) is **leak-irrelevant**. Consequences under each clause:
- **RO-minimality** (`secure[RO->o]` for all o) **rejects** any instance carrying that leak-irrelevant `inreg`
  (removing it does not secure ⇒ `secure[RO->inreg]` is false ⇒ clause violated).
- **`no_extra_inst`** (`no ((Instruction-Branchns) - operands.Operand)`, `STT_6.als:313` / `STT_6_core.als:306`)
  **forbids** a non-`Branchn` instruction with *zero* operands. A `br_x` has no outputs (`br_ops`), so its only
  possible operand is that `inreg`.
- Together: a `br_x` gate must have an `inreg` (no_extra_inst) but must *not* (RO-min) ⇒ **no RO-minimal
  `br_x`-gate core exists.** Only `br_n` (exempt from `no_extra_inst`) can be an operand-free gate. **Confirmed
  empirically:** RO-only@3 = 2, both `br_n`-gating.
- The additive flesh-out pins the gate kind (`br_n`) and can add operands/instructions but **cannot upgrade a
  `br_n` gate to a `br_x`** (a *kind* change). So a mechanism RO deleted is unrecoverable by padding. **This is
  the whole gap.**

RI alone does **not** cause this: `br_x`-gating instances *are* RI-minimal (removing the gate secures; its
inreg stays, no RO), so the RI-only baseline keeps all 4 shapes → EXACT (§6.2). **RO is the sole culprit**;
STT_6_core's extra operand-minimality is what breaks exactness.

### 7.3 OTB / multi-source — not a gap here, and recoverable in principle

Absolute RI-minimality *does* exclude a 2-source (OTB) merge from the **baseline** (dropping one source still
leaks via the other ⇒ the source is not RI-necessary) — the collapse `SPT_MINIMALITY_MCM.md` and the task warn
about. **But** that same "each source is *individually removable*" is exactly what makes the second source
**valid stage-1 padding**: seed the single-source RI-core, and the additive flesh (in-use, no RI) can add the
second source back as a non-contributing instruction. So **RI-only ⊕ flesh recovers OTB** — it is not a
set-equality gap. Two caveats: (i) at the tested bound it is **moot** — the 2-source shape needs ≥5 instructions
and is UNSAT at 3 (consistent with `MINIMALITY_TAGALONG_FIX.md` P_C2_2BR = UNSAT at 6 for the 2-*branch* form,
and `OTB_GENERATION_GAP.md`); (ii) *reaching* those paddings is the enumeration-order/cap problem owned by
`REACH_UNSAT_ENUMERATION.md` + the diversity driver — a completeness issue, separate from set equality.

## 8. Bound-agnostic generalization (N ≥ 4) — what scales, and the honest limit

The whole mechanism is parameterized by N (`gen_models.py N`, `run_all_N{n}.sh`); at **N = 4** the interleave
first genuinely adds a padding instruction (size-3 core + 1 non-contributing instr) and the RI reduction first
bites. **But exact set-equality is NOT locally computable at N = 4**, because neither side exhausts to UNSAT in a
local budget. Measured **floors** (not complete):

| set @ `exactly 4` | result | note |
|---|---|---|
| in-use STT_6 | ≥ **9,085** canonical (13,480 raw) | floor; not exhaustible — matches `REACH_UNSAT_ENUMERATION.md` (≥6,748, no UNSAT) |
| RO+RI baseline `but 4` | **2** cores in 200 s | the 2 size-3 cores; the **size-4** cores were *not reached* before the RO/RI UNSAT-proof timed out (heavy solves) |
| reconstruction (per core) | 5,000 each (cap hit, not UNSAT) | flesh-out of the 2 size-3 cores; capped |

So N=4 confirms only the *qualitative* scaling: the RO+RI **baseline stays tiny** (tractable) while **in-use
explodes** (the reduction is real), and the mechanism **runs and is sound by construction** (flesh model = in-use
⇒ every flesh-out ∈ in-use). It does **not** give a fresh exactness verdict. *(Caveat: "which instruction is the
gate" cannot be read off position-0 at N ≥ 4 — a padding instruction may precede the gate — so the N=3
`br_x`-gating gap characterization is **not** re-measured here; the clean gate=position-0 identity holds only at
N=3, where all 80 instances have the sole unresolved branch at position 0.)*

Structural generalization of the exactness argument (RI-only baseline):
- Every in-use@N instance, strip its individually-removable instructions → a ≤N RI-minimal core; seed + re-add
  that padding reproduces it. Soundness is automatic (flesh = in-use). Completeness holds while the reduction is
  unambiguous, which it is until multi-source first fits (~N≥5), and even then the redundant source re-enters as
  padding (§7.3). So RI-only ⊕ flesh is **expected** exact at every N, gated only by enumeration *reachability*
  (REACH_UNSAT) — but this is **argued, not verified** beyond N=3. *(A subtlety worth flagging for the N≥4 study:
  the N=3 `br_x`-gate gap may partly dissolve at higher N, since padding can insert a `br_x` before the `br_n`
  gate — a different, larger instance, not the 3-instruction one — so the gap's exact scope is itself bound-
  dependent and needs the exhaustible-at-higher-N tooling to pin down.)*

## 9. Verdict, and the pipeline plan

**Feasible?** Yes. The two-stage structure is real and already built (`STT_6_core.als` + `stage_seed.py` +
`stage_pipeline.py`).

**Exact at `exactly 3` (and the mechanism for any N)?**
- **Baseline = RI-minimality (owner's definition): EXACT** (80 = 80, set-identical). "It's gotta be the same" —
  it *is* the same, when the baseline is RI-only. ✔
- **Baseline = `STT_6_core` as written (RO+RI): NOT exact** — 48/80; gap = 32 `br_x`-gating, deleted by the
  extra RO clause (§7.2) and unrecoverable by additive padding.

**The gap, and does stage-2 close it?** The gap is **not** stage-2's to close — it is caused by RO-minimality
in the *baseline*, at the base case, with OTB absent at this scope. Stage-2 (contributing chains) is a separate
concretization expansion. The gap closes by **removing RO from the baseline** (use RI-only).

**Parallel?** Confirmed — per-skeleton jobs independent; merge by fingerprint union (§5).

**What it takes to make this the real pipeline:**
- **Driver / orchestration (NOT owner-gated):** (1) parameterize the bound (done: `gen_models.py`); (2) shard
  `seeded_*.als` across processes + merge by fingerprint union (thin wrapper over `stage_pipeline.py`); (3)
  enumerate each stage to **UNSAT** rather than a cap (so "complete," per `REACH_UNSAT_ENUMERATION.md`); pair
  with the diversity driver for reachability of rare cores. The idx-stripped scope reduction is driver-generated
  throwaway (tooling), as here.
- **Owner-gated (`.als`) — the one real decision:** the true-minimal baseline for **exact** reconstruction is
  **RI-only**. `STT_6_core.als` must have clause **(e) `all o: Operand | secure[RO->o]` (`:301`) removed**
  (keep (f) RI, `:303`). *Proposed diff (apply to a copy, owner sign-off required):*
  ```diff
  --- STT_6_core.als  (gen_useful_litmus)
  -  // (e) operand-minimality: every operand necessary (no removable operand)
  -  all o: Operand     | secure_speculation_scheme_p[RO->o]
     // (f) instruction-minimality: every instruction necessary (no removable instr)
     all i: Instruction | secure_speculation_scheme_p[RI->i]
  ```
- **Trade-off to decide (owner):** RO is what gave `STT_6_core` its dramatic reduction (2 cores). Dropping it
  makes the baseline **exact** but, at small N, **large** (RI is vacuous at N=3 → 80 "cores" = in-use itself;
  the reduction appears only at N ≥ 4 where RI prunes padding). So:
  - **If the goal is to *reproduce* the in-use corpus** from a minimal core set ⊕ interleave → **RI-only**
    (exact; reduction grows with N).
  - **If the goal is a *compact coverage* corpus** (the original `STAGED_ENUMERATION.md` intent) → **RO+RI is
    fine, but it is a DIFFERENT, strictly-more-minimal testset**, not a 1:1 reconstruction of in-use (it drops
    the `br_x`-as-gate mechanism). That is a legitimate choice — just not "the same."

## 10. Scratch artifacts (all under the session scratchpad; nothing in the repo except this doc)

Root: `…/scratchpad/two_stage_stt/`
- `scripts/gen_models.py` — bound-parameterized scratch-model generator (RI-only / RO-only / RO+RI / in-use).
- `scripts/fp.py` — canonical fingerprint sets + exact set `count`/`diff`/`union-diff` (reuses
  `find_duplicates.canonicalize` + `parsexml` read-only).
- `scripts/recon_prep.py` — the interleave operator as per-core seeded `.als` (reuses `stage_seed.build_pred` +
  `stage_pipeline.build_seeded_model`).
- `scripts/run_all_N3.sh`, `scripts/run_all_N4.sh` — parallel reconstruction + baseline variants per bound.
- `models/` — `inuse_N{2..6}.als`, `baseline_{exactly,but,RIonly,ROonly}_N{…}.als`.
- `out/` — enumerations. **N=3 (exhausted/exact):** `inuse_N3` (80), `baseline_exactly_N3` +
  `baseline_ROonly_N3_quick` (2 cores), `baseline_RIonly_N3_quick` (80), `recon_N3/core_000{0,1}` (18+30=48),
  `recon_N3_seeded/`. **N=4 (floors only, not exhausted):** `baseline_but_N4` (2 cores in budget),
  `inuse_N4` (≥9,085 canonical), `recon_N4/core_000{0,1}` (capped 5,000 each), `recon_N4_seeded/`.
- `logs/` — run logs (`run_all_N3.log`, `run_all_N4.log`).

**Reproduce:** `python3 scripts/gen_models.py 3`; `java -cp <alloy6.jar:STAGE1_alloy> a6CountModels
models/inuse_N3.als out/inuse_N3 100000`; `python3 scripts/recon_prep.py out/baseline_exactly_N3
models/inuse_N3.als out/recon_N3_seeded`; enumerate each `seeded_*.als`; then `python3 scripts/fp.py diff
out/inuse_N3 out/baseline_RIonly_N3_quick` and `… union-diff out/inuse_N3 -- out/recon_N3/core_0000
out/recon_N3/core_0001`.

**In-use-file integrity (re-verified at close — PASS):** `STT_6.als`, `STT_6_core.als`, `STT_6_multisource.als`,
`parsexml.py`, `stage_seed.py`, `stage_pipeline.py`, `a6CountModels.java`, `find_duplicates.py` — **SHA-256 and
mtime byte-identical to session start** (`STT_6.als` = `7a6ac4c0…`, `STT_6_core.als` = `d1fd8a64…`; nothing
under `STAGE1_alloy/models/` modified today). Only reads + read-only function imports were performed; every model
change was made on a scratch **copy**.
