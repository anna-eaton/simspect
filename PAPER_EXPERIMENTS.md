# Paper experiments — validating the window & sweep-parameter choices

*Purpose: the methodology section that justifies SimSpect's leak-window definition and its
sweep/stall knobs. A reviewer will ask "why these parameters — would your conclusions change
under different ones?" This doc is the experiment plan that answers that, using the bugs we have
already root-caused as a labeled oracle.*

*Sibling doc: `EXPERIMENTS.md` is a **result** (the release↔squash fragility-threshold finding).
This doc is the **validation** of the harness those results were produced with. Don't conflate.*

---

## 0. What we are validating (and what counts as success)

**Scope: the three STALL knobs only.** The leak *window* itself is the Alloy model's contract —
settled, not under test here. What needs justifying to a reviewer is the choice of the micro-arch
**stall times** we impose in gem5 to probe each test:

| Knob | Config key | What it stalls |
|---|---|---|
| **resolved** *s_R* | `sweep.points` | a branch that has **resolved** |
| **unresolved** *s_U* | `sweep.unresolved_stall_cycles` / `sweep.unresolved_points` | a branch still **unresolved** |
| **fnc** | `gem5.fnc_commit_stall_cycles` | the commit at the fnc (speculation-boundary) instruction |

**Validation question:** are our leak/no-leak conclusions *stable in a regime*, or do they hinge on one
magic value of these stalls? **Success** = a **plateau/knee** in the leak metric vs each stall knob, with
the chosen operating point sitting in the stable regime (or the knob reported as a swept variable, not a
silently-fixed choice) — demonstrated against the labeled anchors below.

**This is a sensitivity study against a labeled oracle — NOT tuning.** Per CLAUDE.md we never tune
params to hit/avoid a bug. We report the curves as-is; the params are justified by the *shape* of the
curve, not by picking the value that gives the answer we want.

---

## 1. The oracle: labeled anchor cases

The "known bugs" are ground truth **only because we have already root-caused them** (real leak /
checker false-positive / true negative). That label is the oracle the sweep is measured against.
Each anchor must be **included deterministically** in the sample (named, never left to random draw).

| Corpus / build | Anchor stem(s) | Label | Source |
|---|---|---|---|
| Recon_6 — `/work/gem5-recon-modded` sch 2/3 | `inst-014912` (SLF) | **REAL leak** (completes-in-ROB before squash, no cache packet) | `project_stt_load_leak_cause`; claudelog 22:45 |
| same | the 183 load→load (delay_unit bounce) | **check_ld FALSE POSITIVE** | same |
| same | branch hits | **check_br FALSE POSITIVE** | `project_stt_branch_leak_cause` |
| STT_6 slow-comm — `/work/stt` | VP-squash-race set incl. `inst-047231` | **REAL, param-driven** (exposed at `commitToIEWDelay` ≥ 2–3; hidden at stock 1; livelock ≥ 5) | `project_slow_comm_experiment`; `results/experiments/slow_comm_squash1/diagnostics/` |
| SPT_6_oneLP Fence — `/work/gem5-spt` | whole corpus | **TRUE NEGATIVE** (zero-init prologue untaints → no taint source) | `project_spt_onelp_zeroinit_untaint` |
| SPT_6_full — `/work/gem5-spt` | 43 OtherLoad (STLF-untaint) | **FALSE POSITIVE** | `project_spt_load_diagnosis` |

The mix matters: we need **real leaks** (to prove the window/params don't *suppress* truth),
**false positives** (to prove they don't *manufacture* leaks), and **true negatives** (a corpus where
the honest answer is zero — the credibility control, same role the Fence control plays in `EXPERIMENTS.md`).

---

## 2. The sample (per corpus)

**Stratified, not pure-random:**

1. **Anchor set** — every labeled stem from §1 for that corpus, by name. These are the oracle.
2. **Background sample** — a random *seeded* draw (e.g. 300–600 stems) for the distribution, so the
   aggregate hit-rate curve is representative and the anchors aren't the only thing moving.

Small on purpose: the point is the param axes, not corpus coverage. Reuse `sweep.max_grid`'s seeded
sub-sampler so the draw is reproducible and quotable in the paper.

---

## 3. The parameter axes (the three stalls)

Sweep **one knob at a time around the operating point** (clean curves), *and* run the full grid via
`max_grid` subsampling (interactions). Known semantics:

| Knob | Config key | Role | Known facts to respect |
|---|---|---|---|
| resolved *s_R* | `sweep.points` | stall on a **resolved** branch | already a list; primary axis. Dense+short probes resolution coincidence |
| unresolved *s_U* | `sweep.unresolved_stall_cycles` / `sweep.unresolved_points` | stall on **still-unresolved** branches | **`5000` MASKS leaks** — shoves the transmitter past `fnc_retire`; NOT a trustworthy default. Sweep small→large to *show* the masking. |
| fnc | `gem5.fnc_commit_stall_cycles` (150) | stall the fnc-boundary commit (widens the window) | leak verdict for the STT race was identical on/off — include to **prove** results don't hinge on it |

Ranges (starting point, refine after first curve): `s_R ∈ {0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 500, 2500}`,
`s_U ∈ {0, 50, 250, 1000, 5000}`, `fnc ∈ {0, 75, 150, 300}`.

*(Aside — the `commitToIEWDelay` comm-latency axis is a **separate** experiment: the release↔squash
fragility threshold in `EXPERIMENTS.md`, running now under `results/experiments/paper_fragility/`. Not one
of the three stall knobs; kept out of this doc.)*

---

## 4. Metric & outputs

For each `(anchor-or-sample stem) × (param point)` record:
- the **verdict** (`issued_in_window` leak / no-leak) **and** the diagnostic bucket (which `diag_*.py`,
  or `NEW`) — so a flip is attributable, not just counted;
- for ld: the cache-reach / completes-before-squash refinement (the *faithful* leak bar), not just the
  raw checker hit.

Produce, per corpus:
- **Per-anchor curve** — verdict vs each knob. The claim each curve supports:
  - real-leak anchor: leaks across a **range** (robust), not one point → conclusion isn't a param artifact;
  - FP anchor: stays non-leak (or stays bucketed) across the range → params don't inject spurious leaks;
  - TN corpus: flat zero across the range → credibility control holds.
- **Aggregate** hit-rate vs knob for the background sample → locate the **plateau/knee**; justify the
  operating point as sitting in the stable regime (or report the knob as a swept variable).

---

## 5. Protocol (faithfulness rules — from CLAUDE.md)

1. **Baseline each anchor under its *own original campaign config first*** (the "run it EXACTLY as the
   config did" rule: right `binary`/`scheme`/`extra_args` + full hook state — BTB force, the proper
   stalls). Confirm it reproduces its known label *before* varying anything. Then change **one knob at a
   time** off that faithful baseline.
2. **Anchors are included by name**, never random-sampled away.
3. **Report curves as-is.** A knob that flips an anchor is a finding (e.g. masking at `s_U=5000`), not a
   value to avoid. No tuning to hit/avoid.
4. **Respect hard bounds**: `commitToIEWDelay ≥ 5` livelocks — cap at 4.
5. Run on the **sandbox / experiment dirs**, never the live `testsets/`/`results/` watchers.

---

## 6. What to actually run (reuses existing tooling)

- Sample + grid: the `sweep.points` / `unresolved_points` / `max_grid` keys already in `pipeline.py`
  (`_grid_points`/`_enumerate_grid_for_corpus`) — no new sweep engine needed.
- Slow-comm axis: the existing `/work/stt` `se_slowcomm.py` / env-driven `se_exp.py` + `run_sample.py`.
- Per-kind, attributed outputs: `testrun.py` into `results/experiments/paper_validation/<corpus>/…`,
  then each folder's `diagnostics/bucket_hits.py` for the bucket column.
- One results dir per corpus under `results/experiments/paper_validation/`, with its own
  `run_config.jsonc` (faithful campaign config + the swept keys).

---

## 7. Open decisions (need owner input before launching)

- **Corpora to include** — all four anchored corpora (Recon_6, STT_6 slow-comm, SPT_6_oneLP, SPT_6_full),
  or a subset for v1?
- **Background sample size** per corpus (300 / 600 / other).
- Use the fresh **200k sandbox testsets** (`testsets_latest/`) as the corpus source, or the existing
  campaign testsets?
