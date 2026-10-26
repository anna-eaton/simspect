# TODO — active workstream (Anna)

*Shown on the status dashboard (linked from `STATUS.md`). What's actively being worked on right now.
Hot/blocking decisions are split out into [`URGENT_TODO.md`](URGENT_TODO.md). Older brain-dump TODOs
live in STATUS.md §"Anna's personal TODO notes". Canonical questions-for-Anna: `wiki/state/OPEN.md`.*
**Updated:** 2026-10-26

---

## 🧩 Alloy two-stage decomposition (true-minimal + interleave) — the core active effort
Goal: factor the in-use model as **true-minimal baseline + interleave**, make the baseline **complete
(exhaustive to UNSAT)**, keep the net **identical**, **bound-agnostic / scalable** (one bound now).
STT first, then SPT. Interleave has **two stages**: (1) Alloy-level padding (no RI-minimality → non-
contributing instrs), (2) parsexml contributing chains (manufactures OTB/multi-source).

- [ ] **STT: verify (STT_6_core baseline exhausted to UNSAT) + interleave == in-use STT_6 EXACTLY** at one
  bound; bound-parameterized, parallel-per-skeleton design. *(agent building — on the existing staged-enum
  prototype: `STT_6_core.als` with `but 6`, `stage_seed.py`, `stage_pipeline.py`, `STAGED_ENUMERATION.md`.)*
- [ ] **Parallel Alloy over skeletons** — each skeleton's Stage-2 run is independent → shard across
  processes. Feasible; being built into the orchestration.
- [ ] **Then SPT** — repeat the decomposition for `SPT_6_oneLP` (note SPT interleave is currently OFF;
  "it's gotta be the same").
- [ ] **Decision (→ URGENT #2):** is "same up to OTB-via-interleave" acceptable as "the same"?

## 🎯 Reach UNSAT (don't cut off at the cap)
- [ ] Adopt the **staged-bounds + core-quotient** scheme: exhaust to real UNSAT at each small bound, and
  over the leak-core quotient at larger bounds; cap only *padding*. Emit a `reached_unsat` marker.
  Driver work (`a6DiverseModels.java` → incremental/blocking) — NOT owner-gated. → `REACH_UNSAT_ENUMERATION.md`.
- Fact established: we have **never** reached UNSAT for STT/SPT (always the 100k cap); full `exactly 6`
  is not exhaustible (~10⁶–10⁸).

## 📐 Minimality definition
- [ ] **Adopt "minimal leak witness"** (path, not cycle; two-tier: mechanism cores + no-padding within a
  core). → `SPT_MINIMALITY_MCM.md`.
- [ ] **Tag-along fix:** replace per-branch individual-necessity with **per-element necessity (C2)**:
  `all i: (unresolved - first_uncommitted) | not secure_speculation_scheme_p[RR->(unresolved - i)]`.
  At scope 6, ≥2 unresolved branches is UNSAT → the fix buys tag-along pruning + canonicalization now;
  multi-branch needs larger scope + interleave. → `MINIMALITY_TAGALONG_FIX.md`.
- [ ] **SPT relax/not-relax:** relax **branches** (to irredundancy), **keep per-state** necessity
  (branches compose into gadgets; locations are padding). → `SPT_MINIMALITY_MCM.md`.
- [ ] **Benchmark** C2 enumeration throughput before 100k-scale adoption (it's materially slower).

## 🧬 OTB / multi-source (→ URGENT #1 for the shape decision)
- [ ] Decide OTB's home (interleave stage vs distinct core vs diversity). Two *distinct* problems:
  **multi-branch** (UNSAT at scope 6 → needs IX6+ scope + C2 predicate) vs **multi-source dataflow merge**
  (enumeration gap → diversity driver B1 / interleave). → `OTB_GENERATION_GAP.md`, `ENUMERATION_OVERSPECIFICATION.md`.

## ✍️ Pending `.als` edits (owner-gated — sign-off per change) → `wiki/state/ALLOY_MODEL_CHANGES.md`
- [ ] **A1** source-derived taint closure (kills const-addr + no_hold FPs).
- [ ] **A2** `rf_from_most_recent_writer` — ⚠️ reconcile: STATUS.md says this is **owner-approved and
  already in STT_6** (L163-169), pending `SPT_6_oneLP` + `Recon_6`. Update ALLOY_MODEL_CHANGES.md A2.
- [ ] **B1–B5** coverage (diversity driver, joint/irredundant minimality, RI-minimality, variable length,
  extended transmitter vocabulary).
- [ ] **Batch** A1+A2+B2+B3 into ONE `--force` regen of STT_6 + SPT_6_oneLP; re-sweep; re-triage (the
  const-addr/no_hold/clobber diagnostics should bucket 0).

## 📝 Paper write-up list → `wiki/results/TO_WRITEUP_PAPER.md`
- [ ] Item 1: **MCM litmus-test count vs. SimSpect's count** (cycle- vs path-based minimality; our
  comparable is #leak-mechanisms, not #tests). Confirm MCM suite figures against real sources first.

## 🧰 Infra (carried)
- [ ] Container zombie cleanup (31 defunct, parented to `sleep infinity` PID 1 → clear with
  `docker restart gem5_dev` when nothing's running). *(discussed; not yet done.)*
- [ ] Deploy: dashboard code + specs + timing records still uncommitted — needs `make sync` + `make dash`
  (git = Anna's authorization).
