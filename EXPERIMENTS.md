# Experiment plan — defense fragility to the "release ↔ squash" race (+ coincidence sweeps)

*Author: designconsultant session, 2026-06-02. Audience: the run-manager session + Anna.*
*Source finding this generalizes: `results/experiments/slow_comm_squash1/diagnostics/stt_vp_squash_race.md`
and claudelog 2026-06-02 09:30.*

---

## 0. TL;DR — what to run

On **2 builds, 3 scheme settings**, run a **bare** (no resolve-stall) sweep of the
**`commitToIEWDelay`** knob and report, per defense, the **smallest `commitToIEWDelay` at which it starts
leaking** (its "fragility threshold"). Reuse all the slow-comm tooling.

| # | build | scheme / variant | testset | expectation |
|---|-------|------------------|---------|-------------|
| 1 | `/work/gem5-recon-modded` (X86O3CPU) | `--scheme=3` (**DoM**) | `STT_6` | leaks above some threshold |
| 2 | `/work/gem5-spt` (DerivO3CPU) | `SpectreSafeInvisibleSpec` | `SPT_6_full` (or `_oneLP`) | leaks; threshold maybe higher |
| 3 (control) | `/work/gem5-spt` | `SpectreSafeFence` (`--scheme=2`) | same as #2 | **0 leaks at every value** |

The Fence control is what makes the positive results credible (proves it's release-mechanism-specific,
not a checker/harness artifact). This is "a couple experiments on a couple builds."

---

## 1. Why — the takeaways that set this strategy

From root-causing the STT load→load leak (a wrong-path tainted load touches the cache in the gap between
its branch resolving and the squash draining):

1. **The big `unresolved_stall` (5000) regime MASKS leaks — it is not the default to trust.** It shoves
   the transmitter past the `(lc_retire, fnc_retire)` window, so resolution-time leaks vanish. The STT
   baseline's "0 hits" was *entirely* this masking. → **Sweep BARE (short/zero res + unres timing).**
   This validates the "shorter res/unres timing" instinct: short timing is where the leaks are.

2. **The leak is a "release ↔ squash" race, and that's defense-agnostic.** Every spec defense has a point
   where it *releases* protection: STT → branch resolved (`isPrevBrsResolved`); InvisibleSpec/DoM → a
   visibility point; Fence → never (hard barrier). There is a race between that release and the squash of
   the wrong-path instruction; the transmitter slips through the gap. STT is just the first instance.

3. **The axis that exposes the race is communication/redirect latency — NOT execution width.** On STT,
   `squashWidth` and the forward delay did nothing; the backward **`commitToIEWDelay`** (how long the
   squash takes to propagate commit→IEW) was the whole story. Stock (1 cyc) hides it; ≥2–3 exposes it.
   So the knob to sweep is squash/redirect propagation latency, and **each defense's threshold on it is a
   robustness metric you can compare across builds.**

4. **It does NOT show at stock gem5 timing**, and we ruled out the alternatives, so a positive result is a
   real defense weakness (timing-regime-dependent), not noise: not a check_ld false positive (cache-reach
   diagnostic), not a model over-approximation (xml-shape: 231/231 `addr_from_load`), not the
   `fnc-commit-stall` hook (leak identical on/off), not `squashWidth`, not concretization.

---

## 2. The experiment template ("fragility threshold" sweep)

**Fixed:** bare (no resolve-stall), `squashWidth=8` (realistic), `iewToCommitDelay=1`, `backComSize=forwardComSize=10`.
**Swept:** `commitToIEWDelay ∈ {1, 2, 3, 4}`  (1 = stock control; do not exceed the build's livelock ceiling — see §4).
**Measured:** per value, the **real-cache-access leak count** in a random ld sample (cache-reach-confirmed).
**Result:** the curve `commitToIEWDelay → leak count`; the **threshold** = smallest value with leaks > the
stock(=1) baseline. Compare thresholds across the 3 defenses.

Why this metric is uniform across builds: the **cache-reach diagnostic** (`STAGE3_gem5/diag_ld_cache_reach.py`)
already classifies a hit as a *real visible cache access* (`reached_cache`) vs each defense's "hidden"
mode — recon's delay_unit bounce (`executed_no_packet`) and SPT's spec-buffer read (`spec_read_only`) are
both correctly counted as NON-leaks. So "count of `reached_cache`" is the right leak metric everywhere.

### Concrete run recipe (per build, per `commitToIEWDelay` value N)

```bash
# 1. one-time per build: create an additive env-driven config script (see §4 for the block)
#    /work/<build>/configs/example/se_exp.py   (copy of se.py + the SIMSPECT_* override block)

# 2. one-time per build: a bare run_config.jsonc that points config_script at se_exp.py,
#    sweep.enabled=false, the right binary / cpu_type / scheme / extra_args / testset model.

# 3. the sweep: export the knobs (se_exp.py reads them at gem5 runtime; run_sample passes env through)
for N in 1 2 3 4; do
  export SIMSPECT_SQUASH_WIDTH=8 SIMSPECT_IEW_COMMIT_DELAY=1 \
         SIMSPECT_COMMIT_IEW_DELAY=$N SIMSPECT_BACK_COM_SIZE=10 SIMSPECT_FWD_COM_SIZE=10
  python3 results/experiments/slow_comm_squash1/run_sample.py \
      --config <build-bare-run_config.jsonc> --model <testset> \
      --tag thr_bwd${N} --unresolved-stall 0 --per-mode 600 --jobs 12
done
# read each results/experiments/<...>/thr_bwd${N}/summary.json -> real_cache_hits ; threshold = first N>baseline
```

`run_sample.py` is reusable: it derives gem5 env from `--config`, samples `--model`'s ld tests, injects
`--unresolved-stall` (use 0 = bare), runs check_ld, then runs the cache-reach diagnostic on the hits and
writes `<tag>/summary.json`. (It currently lives under `slow_comm_squash1/` and writes under its own dir;
fine to reuse, or copy it into a per-build experiment dir.) The `SIMSPECT_COMMIT_IEW_DELAY` etc. exports
survive into the gem5 subprocess because `_build_gem5_env` doesn't overwrite them — verify once that
`se_exp.py` actually applied them (grep the m5out config.ini for `commitToIEWDelay`).

---

## 3. Optional second axis — coincidence (short res/unres), if there's budget

The single-branch race above already probes the resolution coincidence (transmitter acting the cycle the
branch resolves). To probe **two-branch** coincidence (a resolved and an unresolved branch resolving the
same cycle), add a **dense, SHORT** resolve-stall sweep — e.g. `sweep.points=[0,1,2,4,8,16,...]`,
`unresolved_stall_cycles` small (NOT 5000) — so resolutions land near each other. **Highest value on a
multi-branch / merge gadget (recon OTB / `getOldestTaint`).** ⚠️ Gated: the generator does not yet emit
the two-load→ALU→xmit merge shape (see claudelog reconbugs entries) — that's an `.als`/interleave change
and needs Anna's approval. Until then, defer the two-branch coincidence run.

---

## 4. Per-build setup details

**The env-driven override block** (paste into the build's `se_exp.py`, inside the per-cpu config loop,
after the scheme is configured — same place the STT one lives at `/work/stt/configs/example/se_exp.py`):

```python
import os as _os
def _envi(name):
    v = _os.environ.get(name)
    return int(v) if v not in (None, "") else None
for cpu in system.cpu:
    if _envi("SIMSPECT_IEW_COMMIT_DELAY") is not None: cpu.iewToCommitDelay = _envi("SIMSPECT_IEW_COMMIT_DELAY")
    if _envi("SIMSPECT_COMMIT_IEW_DELAY") is not None: cpu.commitToIEWDelay = _envi("SIMSPECT_COMMIT_IEW_DELAY")
    if _envi("SIMSPECT_BACK_COM_SIZE")    is not None: cpu.backComSize      = _envi("SIMSPECT_BACK_COM_SIZE")
    if _envi("SIMSPECT_FWD_COM_SIZE")     is not None: cpu.forwardComSize   = _envi("SIMSPECT_FWD_COM_SIZE")
    if _envi("SIMSPECT_SQUASH_WIDTH")     is not None: cpu.squashWidth      = _envi("SIMSPECT_SQUASH_WIDTH")
```

Rules (same as the STT experiment):
- **Additive only** — a NEW `se_exp.py` file; never edit the in-use `se.py` (other watchers reference it).
- **Runtime params, no rebuild** — same binary; `backComSize/forwardComSize` MUST exceed the delays
  (timebuffer depth) — that's why we set them to 10.
- **Livelock ceiling**: `/work/stt` livelocked at `commitToIEWDelay≥5` (generic, not the defense). Each
  build has its own ceiling — keep the sweep ≤ it; if a value hangs (no termination), drop it.

| build | binary | cpu_type | how to select the variant | testset model |
|-------|--------|----------|---------------------------|---------------|
| recon-modded | `/work/gem5-recon-modded/build/X86/gem5.opt` | `X86O3CPU` | `--scheme=3` (DoM); 1=Delay 2=STT 0=Unsafe | `STT_6` / `STT_6_interleave` |
| gem5-spt | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | `DerivO3CPU` | `extra_args=["--scheme=SpectreSafeInvisibleSpec"]`; Fence = `--scheme=2` | `SPT_6_full` / `SPT_6_oneLP` |

- recon-modded needs `branch_ann_enable: true` (it supports `--branch-ann-file`); keep the build's normal
  `fnc_commit_stall_cycles`. We verified the fnc hook doesn't drive the race on STT — sanity-check once
  per build (run threshold at `commitToIEWDelay`=ceiling with fnc on vs 0; expect identical) but don't
  belabor it.
- gem5-spt: confirm `SpectreSafeInvisibleSpec` is the intended invisible-spec variant for the build (check
  its `se.py` scheme map); the Fence control is the existing `--scheme=2` path.

---

## 5. Diagnostics to apply (reuse — don't re-derive)

1. **`STAGE3_gem5/diag_ld_cache_reach.py`** (build-agnostic) — separates real cache accesses
   (`reached_cache` = leak) from each defense's hidden/FP mode. **This is the leak metric.**
   `--config <run_config> --hits-from <window-results.json>`.
2. **`results/experiments/slow_comm_squash1/xml_shape.py`** — confirm the hits are model-protected
   load→load (`addr_from_load`) vs over-approximations. Model-level, testset-only (works for any STT-style
   testset; SPT testsets may differ — check).
3. **`results/experiments/slow_comm_squash1/diagnostics/diag_stt_vp_squash_race.py`** — the STT-specific
   attribution (real access + squashed + access ≥ branch-resolution). For DoM/InvisibleSpec, **adapt** the
   release-point check (their "release" isn't `isPrevBrsResolved`) into a per-build
   `diagnostics/diag_<defense>_release_race.py` — but only AFTER you've confirmed each defense's release
   point in source. For the first pass, the cache-reach leak-count curve is enough to get the threshold.

---

## 6. What a result looks like / how to read it

- **Threshold curve per defense**, e.g. STT(recon-modded scheme2): leaks at `commitToIEWDelay≥3`;
  DoM: leaks at `≥?`; InvisibleSpec: `≥?`; Fence: never. A lower threshold = more fragile defense.
- **Fence = 0 everywhere** is the expected control; if Fence leaks, something's wrong with the harness
  (investigate before trusting the others).
- A defense that leaks even at `commitToIEWDelay=1` (stock) would be a **stock-config** leak — much
  stronger; flag immediately.

---

## 7. Open questions to discuss (run-manager ↔ Anna)

- Budget: 3 settings × 4 `commitToIEWDelay` values × 1200-test sample. Box is CPU-saturated — stagger, or
  shrink `--per-mode`. OK to run sequentially?
- gem5-spt: exact InvisibleSpec variant string + whether `SPT_6_full` or `_oneLP` is the cleaner testset.
- Do we also want the Delay (recon scheme 1) and a real-STT (recon scheme 2) point, to rank the whole
  recon family in one sweep? (Cheap — same testset, just more scheme values.)
- Per-build livelock ceiling for `commitToIEWDelay` — confirm before the full sweep (one smoke run at the
  top value).
- Deferred two-branch coincidence: is the OTB merge-shape generator change (`.als`/interleave) worth
  prioritizing, given it's the richest coincidence target?
