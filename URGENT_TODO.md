# 🚨 URGENT TODO — needs Anna's call ASAP

*Shown on the status dashboard (linked from `STATUS.md`). The hot decisions blocking the active
Alloy two-stage / minimality workstream. Full backlog: [`TODO.md`](TODO.md).*
**Updated:** 2026-10-30

---

## 🟠 Footprint-defense audit decisions (2026-10-30, full detail in [`wiki/findings/audits/2026-10-28/APPROVALS.md`](wiki/findings/audits/2026-10-28/APPROVALS.md))

Section E (hook fixes) was approved 2026-10-30 and is in progress (hooks v2). Still open:

- [ ] DECIDE: R-1: treat Recon_6 results as "STT_6 minus A2" (the reveal at `Recon_6.als:316-318` is a no-op), pending a forcing-predicate SAT check?
- [ ] DECIDE: STT-1/STT-2/STT-3: add store-address-as-implicit-branch, mispredicted xmit branch, and per-instance untaint to `STT_6.als`?
- [ ] DECIDE: SPT-1/SPT-2/SPT-3: does the SPT oracle follow the paper's untaint algebra exactly (drop `^op_edges` re-taint, per-instruction backward rules, STLPublic gate)?
- [ ] DECIDE: B-1..B-5: cold/evict-set/split/second-page concretization for footprint testsets (run B-0 count first)?
- [ ] DECIDE: C-1..C-5: check_footprint semantics (undecided on `seq=-`, actor-issue window, loads only, missing record → undecided, CleanupSpec late installs)?
- [ ] DECIDE: D-1..D-4 scope, F-2..F-5 config values (L1D size, TBEs, needsTSO, CleanupSpec stall).

## ✅ #1 — OTB shape — DECIDED (Anna, 2026-10-30): (A) OTB = the interleave stage

**Decision:** Two stages; **OTB comes in the second (interleave) stage** — option (A). The true-minimal baseline stays single-source (OTB is *not* minimal); the interleave stage manufactures OTB by merging a second contributing tainted source into a minimal core's transmitter. Rationale: OTB's second source is redundant under the conservative OR/union taint oracle, so minimality structurally deletes it (0/300 two-load merges when an ALU is forced onto the xmit-address path); interleave is minimality's dual — it adds the redundant source back. Consequence: "net == in-use" carries OTB **only after interleave**, never in the baseline. Original framing + the A/B/C analysis kept below for reference.

## 🔴 #1 (original framing, for reference) — OTB shape: how should it be generated?

**What OTB is (the gadget).** recon's `getOldestTaint` leak. The transmitter's **address** is produced by
an ALU ("other") op that **merges the outputs of two distinct speculative tainted loads** `la`, `lb`, each
gated by a different branch — one resolving early, one late. recon frees the taint when the **oldest**
source resolves, even though the other source is **still speculative**, so the transmitter issues with a
still-secret-dependent address. (It should track the *youngest* source.)

```
  la = load(secretA)   under branch_A  (resolves first)  ─┐
                                                          ├─▶ other(ALU):  x = f(la, lb)  ──▶  xmit addr = x   (LEAK)
  lb = load(secretB)   under branch_B  (resolves later)  ─┘
  getOldestTaint frees x's taint when la resolves — but lb is still speculative
```
**Shape = 2 loads → 1 ALU → transmitter**, two branches, mixed resolve order.

**The issue — why it never generates on its own.** The leak predicate *does* flag it, but the enumeration
**cannot produce the 2-source merge**:
- Taint is **OR / union** → a *single* tainted load already makes the ALU output tainted and satisfies the
  leak. So **minimality minimizes the number of load-fed operands** and structurally drops the second load.
  Measured: forcing an ALU onto the xmit-address path → **0/300** give the 2-load merge (280 single-input,
  20 two-input-with-a-constant). (`OTB_GENERATION_GAP.md`; STATUS.md §bugsynth lines ~145-151.)
- Per-branch minimality likewise prunes the two-branch merge (resolving one branch leaves the other tainted
  → "not minimal").
- ⇒ **OTB cannot emerge from minimality-guided enumeration.** Today it is hand-forced via `otb_class`
  ("≥2 distinct loads feed the ALU").

**The decision for you — where does OTB live in the new two-stage design?**
- **(A) OTB = the *interleave* (contributing) stage.** ← recommended. The true-minimal baseline is
  single-source (correct — OTB is *not* minimal). The **interleave stage manufactures OTB** by adding a
  *second contributing tainted source* that merges into a minimal core's transmitter. Fits the two-stage
  plan cleanly and is exactly what `parsexml:pass_interleave` already does.
- **(B) OTB = a *distinct enumerated core*.** Treat the 2-source merge as its own leak *mechanism*
  ("minimal leak witness" Tier-1) and enumerate it directly — **but** no minimality predicate on the
  conservative `secure` oracle can separate a real OTB merge from a redundant co-gate (tag-along agent), so
  this still needs a dedicated structural predicate (≈ `otb_class`) = still "forced."
- **(C) Diversity enumeration.** Blocking clauses on the **#load-fed-operands** dimension (block
  "xmit-addr via 1 load" → force 2) surface it with no bug-specific predicate — more machinery.

**The crux question:** is OTB fundamentally an **interleave** phenomenon (add a 2nd source onto a minimal
core), or a **distinct minimal mechanism** we must enumerate? Your answer decides whether "net == in-use"
must carry OTB in the **baseline** or only **after interleave**.

Refs: `wiki/findings/mdsToRead/OTB_GENERATION_GAP.md`, `bugsynth/RECON_OLDEST_TAINT_BUG.md`,
`wiki/findings/mdsToRead/SPT_MINIMALITY_MCM.md`, STATUS.md §bugsynth.

---

## 🟠 #2 — Two-stage STT exactness: ✅ VERIFIED at exactly-3 (80=80) with an RI-only baseline — DECIDE: approve RI-only?
**Result (agent, real Alloy):** in-use STT_6 **==** (RI-minimality-only baseline) **⊕** interleave,
**set-identical 80==80** at the exhaustible bound. Parallel per-skeleton confirmed. So YES — it can be
exactly the same, *if the baseline uses RI-minimality only.*
**The catch + the decision:** `STT_6_core.als` as written also carries **operand-minimality (RO)**, which
over-prunes — it deletes the `br_x`-as-gate mechanism → reconstruction only 48/80 (sound but incomplete,
gap = 32, all `br_x`-gating). For an exact 1:1, **drop the RO clause (e) at `STT_6_core.als:301`, keep RI
(f) :303** (owner-gated; proposed on a copy, not applied). Trade-off: RO = compact baseline (2 cores) but a
*different, more-minimal* corpus; RI-only = exact but less compact at small N.
**Honest limit:** N=3 is the trivial base case (RI vacuous, interleave empty). The real test is N≥4, not
locally exhaustible — reduction is real + mechanism sound, but exactness at a *non-trivial* bound isn't
proven yet (needs the reach-UNSAT diversity driver / container compute).
**OTB (→ #1):** at N=3 OTB is moot; RI-only+flesh structurally *recovers* it (2nd source = removable
padding) ⇒ OTB is a **reachability** problem, supporting option **(A)** (OTB = interleave phenomenon).
Doc: `wiki/findings/mdsToRead/TWO_STAGE_STT_FEASIBILITY.md`.

## 🟠 #3 — Apply A1 (source-derived taint closure) BEFORE relaxing minimality?
Agents recommend yes — relaxing minimality on the current over-approximating protset would admit noisy
multi-branch shapes. If yes, **batch A1 + A2 + B2 + B3 into one `--force` regen** of STT_6 + SPT_6_oneLP so
the regen is paid once. Owner sign-off needed (`.als` edits). → `wiki/state/ALLOY_MODEL_CHANGES.md`.
