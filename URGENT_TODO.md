# 🚨 URGENT TODO — needs Anna's call ASAP

*Shown on the status dashboard (linked from `STATUS.md`). The hot decisions blocking the active
Alloy two-stage / minimality workstream. Full backlog: [`TODO.md`](TODO.md).*
**Updated:** 2026-11-02

---

## 📄 Paper figures (2026-11-02) → plans in [`paper_figures/plans/`](paper_figures/plans/)

- [ ] DECIDE: Alloy models do NOT share one verbatim skeleton: fact `rf_from_most_recent_writer` (`STT_6.als:161-169`) is in the STT_6 family (STT_6, _stl, _interleave, _futuristic, _commitsplit, _core, _multisource, STT_all) but absent from Recon_6, SPT_6, SPT_6_full, SPT_6_oneLP(_noSTLF), STT_6_pincommit, STT_6_modified_protset; `specs/alloy_models.json:43,58,63` claims otherwise. Align the models (an .als change → your sign-off) or qualify any "same skeleton + defense block" claim in the paper?
- [ ] DECIDE: pipeline figure fact audit (`paper_figures/plans/BIGFIG_FACT_AUDIT.md`, 8 decisions D1–D8). Biggest: should the figure show the two-stage design (Stage 1.5 = unwired STT prototype that no reported result used) or the flat enumeration the results came from? Also: drop "exhaustive" (never reached UNSAT), drop the transmission→harness arrow (no runtime link), say that the footprint defenses reuse STT_6, and shade "build + config".
- [ ] DECIDE: probe array: `parsexml.py:2079` comment says 256 slots × 64 B (cache-line stride) but the code is `[256 x i64]` (`_PROBE_MEM_BYTES = 256*8`, :1063) indexed at byte stride (`movq ($1,$2,1)`, :2152), so byte values 0–255 hit only 4 lines. Checkers don't use line identity, so results shouldn't change. Fix the comment, or change the stride (parsexml change → regen)?
- [ ] DECIDE: fig (d) instrumentation table: which timing values the paper states (fixed configs s_U=5000, s_R∈{0,500,2500}, fnc stall 0 vs prose s_U=0, fnc {0,150}); whether it replaces `sptable_v2` + `resolutiontiming_v2`; keep the STL row only once the STL window checker + campaign exist. Details: `paper_figures/plans/fig_d_instrtable.md`.
- [ ] DECIDE: InvisiSpec footprint checker (`STAGE3_gem5/check_footprint.py`, `specs/leakage/invisispec.json`) counts a footprint from ANY squashed load younger than lc inside the window, not only the target transmitter (in fixture `inv_uv1` seqs 566/573/576 all leave footprints; earliest is seq 566 at cycle 16). Paper + figures frame the signal as the transmitter's. Restrict to the xmit, or reframe the criterion in the paper? Also: present footprint criterion (fig e draft) vs the old expose-tick criterion still described at `pipeline.tex:63`. Details: `paper_figures/plans/fig_e_checkerwindow.md`.
- [x] DECIDED 2026-11-02 (Anna): fig (c) interleave may show Stage 2 (concretization) interleaving, as long as the paper says so; redraw as the Stage 2 round and fix the caption. Still open: confirm the reg0 rf correction. Details: `paper_figures/plans/fig_c_interleave.md`.
- [ ] DECIDE: fig (b) relaxation: merge old Fig 2 (`fig:ddi-rf`) into the new one-program relaxation figure (recommended; saves ~350pt), and OK to use stale-testset instance `testsets/STT_6/xml/inst-047231.xml` (it violates the current STT_6 minimality rules, which is why it shows redundancy)? Details: `paper_figures/plans/fig_b_relaxation.md`.
- [ ] DECIDE: fig (a) execution-graph syntax: TikZ figure with example graph (recommended) vs inline table; adopt its notation for all graph figures (restyle fig:ddi-rf, fig:four-panes, fig:interleave)? Details: `paper_figures/plans/fig_a_execgraphsyntax.md`.


## 🚩 Fixed harness (2026-10-30 / 11-02) → [`wiki/findings/bug/BRANCH_ANNOTATION_AND_FORCE.md`](wiki/findings/bug/BRANCH_ANNOTATION_AND_FORCE.md)

- [ ] DECIDE: gate on `criteria.resolved_before_signal` (a leak must happen after every resolved branch actually resolved) or keep it reported only? Today it is reported only, so it never removes a hit. Recommendation: keep it reported until we see how many hits it would remove.
- [ ] DECIDE: review `STAGE1_alloy/models/STT_6_commitsplit.als` (diff vs STT_6 in the 2026-10-30 session; a 20k/mode candidate testset is already generated and ran 0 hits on /work/stt).
- [ ] DECIDE: amulet-InvisiSpec panics on every run (`Invalid range for type MachineType`) since the 10-30 rebuild picked up the stalled hooks-v2 Ruby edits. Roll the binary back to `gem5.opt.simspect-hooks-v1-resolve-20261030`, or finish hooks-v2 first?
- [ ] DECIDE: which round-2 hits to triage first: SPT br_x (28 | 22 tests, new since annotations load on gem5-spt), SPT ld (336 | 264, includes the known const-addr artifact), or the 7 recon-modded ld tests?
- [ ] Anna: `scripts/archive_results_pre_resolve_hooks.sh --delete` in the container (zip verified; originals still there).

## 🚩 Threat model + Futuristic model (2026-10-30) → [`wiki/design/FUTURISTIC_MODEL.md`](wiki/design/FUTURISTIC_MODEL.md)

- [ ] DECIDE: review `STAGE1_alloy/models/STT_6_futuristic.als` (new copy of STT_6; contract = uncommitted & after any not-yet-completed instruction). Visibility point = all older **completed** (as /work/stt does) or all older **committed** (ROB head)? Recommendation: completed.
- [ ] DECIDE: also make `STT_6_shadows.als` (branch + store sources only), the model matching what the Recon builds actually protect? Recommendation: yes. Their STT results should be judged against it, not against Spectre-only STT_6.
- [ ] DECIDE: how to hold a non-branch, non-store source incomplete in gem5 for Futuristic tests: a completion-hold hook by PC, or naturally slow instructions (div chain, cache miss)? Recommendation: the hook.
- [ ] DECIDE: names for the two STTs in results and the paper: **STT-Spectre** (`/work/stt`) vs **Recon-STT** (`gem5-recon*` scheme 2), or something else? Also whether to read amulet-STT's code to place it. Evidence: `wiki/design/STT_VS_RECON_STT.md`.
- [ ] DECIDE: fix the check_ld gate on Recon builds (add the `Memory request … was sent` line to `parse_lsq`) and re-score past recon results? → [`wiki/findings/bug/recon_cache_reach_gate/README.md`](wiki/findings/bug/recon_cache_reach_gate/README.md). Recommendation: yes; it's additive.
- [ ] DECIDE: `stl_bypass` now annotates every load of the held store's location, not only the first (it changed the alias control from leaky to clean). OK as the semantics, "the predictor says no-alias for every true alias"?

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
