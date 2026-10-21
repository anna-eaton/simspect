# SimSpect — the gem5 instrumentation layer (an overview)

*How SimSpect wires a stock secure-speculation gem5 build into the pipeline: what we add, what we
deliberately never touch, and **why each hook exists**. The governing rule from CLAUDE.md —
**"DO NOT mess with the gem5 on any front other than the hooks"** — is not a side note here; it is the
design constraint that shapes the entire layer. Canonical checklist: `reference_gem5_build_hooks`
(memory). Bridge code: `pipeline.py:_build_gem5_env`, `STAGE3_gem5/gem5_common.py`. Companions:
[`PAPER_RESULTS.md`](PAPER_RESULTS.md), [`METHODS_LEAKAGE_KNOBS.md`](METHODS_LEAKAGE_KNOBS.md),
[`METHODS_CONCRETIZATION.md`](METHODS_CONCRETIZATION.md).*

---

## 0. The instrumentation contract: realize and observe, never alter

gem5 is the **ground truth**. The whole point of the project is to learn whether a defense leaks, so
the instrumentation must never change *what the defense does* — only (a) make the **modeled
speculative scenario actually happen** in the pipeline, and (b) make the transmitter's behavior
**observable** in the trace. Everything we add falls into exactly one of three buckets, and none of
them is in the defense's taint/protection logic:

```
 A. CONTROL hooks   (C++ source)  — force the modeled mispredict; hold a branch unresolved; hold the
                                    speculation boundary at the ROB head.  → realize the scenario.
 B. CONFIG glue     (Python)      — declare the CLI flags + load the per-test annotation.  → wire A.
 C. OBSERVATION     (debug flags) — O3PipeView / LSQUnit / Commit traces the checkers parse.  → see it.
```

The discipline that makes this sound: **a CONTROL hook must be proven not to *cause* the result it
helped reveal.** That is why every campaign carries controls — the `fnc` stall on-vs-off (identical →
the fnc hook didn't manufacture the A4 race), the branch-annotation on-vs-off (byte-identical at
stock → the BTB hook didn't manufacture the branch redirect), and the `scheme=0` Unsafe baseline
(byte-identical → the hit is defense-specific). A hook that flips the verdict is reported as a finding
about the hook, not attributed to the defense (e.g. the 46 slow-comm br_x "leaks" that turned out to
be the fnc-stall hook, `claudelog` 2026-06-03 05:00).

---

## 1. The CONTROL hooks (C++ source) — three, and why each is needed

The Alloy model describes an *abstract* speculative scenario: "a branch mispredicts, opening a window;
a load executes speculatively inside it." A stock CPU won't necessarily realize that exact scenario
for a given litmus binary — the predictor might guess right, or the window might be too short to place
the transmitter. The three source hooks exist to make the modeled scenario **deterministic and
positioned**, without touching the defense.

### 1.1 BTB-forced target — *realize the modeled mispredict* (`mispredict_taken`)

- **What:** a per-branch override in the branch predictor — for an annotated branch PC, force the BTB
  target and `pred_taken=true` so the CPU speculates down the *modeled* wrong path
  (`bpred_unit.cc` predict-time override, sites §1–§2 below).
- **Why it exists:** in `mispredict_taken` mode the model needs the branch predicted *taken* when it
  should fall through. A stock predictor warming up on a tiny litmus test won't reliably do that, so
  the leak scenario wouldn't occur — not because the defense is safe, but because the speculation
  never happened. The hook makes the modeled misprediction happen on demand. It is **only** applied in
  `taken` mode (`not_taken`/`correctly_not_taken` annotations force target 0 = no override), so in the
  not-taken runs it is a verified no-op — which is what lets the branch-ann on-vs-off control be
  byte-identical there.
- **Boundary:** it changes the *prediction*, i.e. which path is speculated. It does **not** touch
  taint, the visibility point, or any protection decision — those still run exactly as the defense
  wrote them on the (now correctly mis-speculated) path.

### 1.2 Per-branch resolve-stall — *hold a branch unresolved to position the window*

- **What:** an optional per-branch delay (`annotationResolveStallCycles`) applied at branch resolution
  to postpone the squash broadcast.
- **Why it exists:** the speculative window is `(lc_retire, fnc_retire)`; whether a transmitter's
  action lands inside it depends on *when the controlling branch resolves*. The resolve-stall is the
  knob that slides the window edge relative to the transmitter so the modeled scenario (transmitter
  acts *while still speculative*) is realizable and reproducible. It is swept as `s_R`/`s_U`
  (`METHODS_LEAKAGE_KNOBS.md` Tier 6) — and the key discovered fact is that the *unresolved* stall at
  `5000` **masks** leaks by pushing the transmitter past `fnc_retire`, which is why runs go bare.
- **Boundary:** it delays a *redirect*, a timing event. It changes *when* squash propagates, not
  whether the defense protects — and the campaign reports it as a swept variable, never tuned.

### 1.3 fnc-commit-stall — *hold the speculation boundary at the ROB head*

- **What:** hold the `first_noncommitted` instruction (the speculation boundary) at the ROB head for
  `fncCommitStallCycles` (default 150) before letting it commit (sites §3–§7 below).
- **Why it exists:** it widens the speculative window deterministically by delaying the boundary's
  retirement, so a transmitter that would otherwise just miss the window can be observed. It is a
  *window-widener*, included so we can also run it **off (fnc=0)** and show the result is the same —
  the A4 race is identical with fnc=150 and fnc=0, which is the control that rules the hook out as the
  cause.
- **Boundary:** it stalls a *commit*, not the defense's taint clearing. (It is genuinely capable of
  *manufacturing* an artifact when it interacts with re-speculation — the 46 slow-comm br_x case — and
  that is exactly why the on/off control is mandatory, not optional.)

**What these three share:** they all act on **control/timing** — prediction, redirect latency, commit
pacing — never on the **defense's data path** (taint propagation, the visibility point, fence
decisions). That separation is the contract.

---

## 2. The CONFIG glue (Python, `configs/`) — declare and wire

Two config-side pieces turn the source hooks into something the pipeline can drive:

- **CLI flags** (`configs/common/Options.py`): `--branch-ann-file`, `--branch-ann-base`,
  `--fnc-commit-stall-pc`, `--fnc-commit-stall-cycles` (site §8).
- **Annotation loader + wiring** (`configs/example/se.py`, site §9): `load_branch_annotations(path,
  base)` reads the per-test `.ann.json`, resolves each branch PC (absolute `branch_addr` first, else
  function-relative offset `+ base` — *conflating these was a real bug fixed across all amulet
  builds*), and pushes `annotationBranchPCs / annotationForcedTargets / annotationResolveStallCycles`
  into each CPU's branch predictor; then sets `fncCommitStallPC/Cycles` (guarded `> 0` so a build
  missing the source hooks but carrying the flags doesn't fatal).

**Why the annotation drives it:** the leak metadata produced by Stage-2's `emit_branch_annotations`
(`METHODS_CONCRETIZATION.md` §2.8) is exactly what `se.py` needs to know *which* branch to force and
*how long* to stall — so the same file that tells the checker what to look for tells gem5 how to
reproduce the window. One artifact, both consumers.

---

## 3. The OBSERVATION layer (no source change) — the trace the checkers parse

The transmitter's behavior is read entirely from gem5's **existing** debug output — no instrumentation
of the cache or the defense is needed to *observe* a leak, only to *realize* the scenario. The run
emits `O3PipeView,LSQUnit` (and `Commit`, added for the B2 fix) to a single `--debug-file`, and
`gem5_common.py` parses it:

| parser (`gem5_common.py`) | reads | feeds |
|---|---|---|
| `parse_pipeview` | issue / complete / squash ticks per seqNum | the `complete`-tick half of the data-obtained gate |
| `parse_lsq` | LSQ `Executing load`, `packet_tick`, `spec_read_tick`, (SpecLFB) `memaccess_tick`, (InvisiSpec) `expose_tick` | the load checker's signal + cache-fate |
| `parse_commit_squashes` | pc → squash ticks | the B2 fix: `check_br` keys on the squash tick, not the resolve tick |
| `collect_unresolved_branches` / `check_branch_resolutions` | the annotation's branch list vs the trace | the "branches still unresolved" gate |

**Why observation needs no defense change:** the leak criterion is the *transmitter's own* action in
the window, and that action is already in the pipeline trace (a load's LSQ execute / cache packet, a
branch's redirect, a div fault). This is also the precise boundary of SimSpect's scope
(`PAPER_RESULTS.md` §3): collateral channels — evictions, MSHR, L1I, TLB — are *not* in this trace, so
they are out of scope without adding a different observer (e.g. an InvisiSpec checker keys on the
expose/validate packet, an SpecLFB checker on `memaccess` — but those are *checker* changes, allowed,
never gem5-source changes).

### The leak criteria the observation enables (where instrumentation meets measurement)

- **`check_ld`** — `signal` = the LSQ cache-touch tick, gated by **data-obtained** (the canonical "did
  it actually leak" test): in-window **and** (`reached_cache` OR `store_forward` — the SLF/complete
  caveat that A2 taught us). Squash timing **never** gates (a squashed load that obtained data still
  leaked). This gate is mandatory in any diagnostic re-deciding real-vs-FP — reuse
  `check_ld._xmit_cache_fate` + pipeview `complete`, never a trace-only cache-reach.
- **`check_br`** — branch-redirect detection, keyed on the **squash tick** (the B2 fix). Known
  residual: it does not yet enforce the `lc/fnc` window the way `check_ld` does.
- **div faults** — a speculative xmit-div fault is promoted to a leak (`classify_divide_panic`), the
  value that makes the D3 idivq guard meaningful.

---

## 4. The config → env → trace bridge (and why the indirection)

The run-config `gem5.*` keys do not reach the checkers directly. `pipeline.py:_build_gem5_env`
translates them into `SIMSPECT_*` environment variables that `gem5_common.py` reads at the top of the
module:

```
 run_config gem5.binary        → SIMSPECT_GEM5_BIN
            gem5.config_script → SIMSPECT_SE_CONFIG
            gem5.cpu_type      → SIMSPECT_GEM5_CPU
            gem5.extra_args    → SIMSPECT_GEM5_EXTRA   (0x1f-joined)
            gem5.fnc_commit_stall_cycles → SIMSPECT_FNC_COMMIT_STALL_CYCLES
            gem5.branch_ann_enable       → SIMSPECT_BRANCH_ANN_ENABLE
            (+ SIMSPECT_ALLOW_LEAKED, SIMSPECT_GEM5_DBG_FLAG/FILE, ...)
```

**Why the indirection exists:** it makes a checker **reproducible by hand**. A campaign is fully
described by its `run_config.jsonc`; any checker invocation that exports the same `SIMSPECT_*`
reproduces the campaign's exact build/scheme/hook state. This is the mechanical backbone of the
CLAUDE.md rule *"reproduce a hit/bug by running it EXACTLY as the config did"* — the right
binary/scheme/extra_args **and** the full hook state (branch forces, the stalls). Drop any of it and
the window shifts and the hit false-reproduces or vanishes; the cleanest path is always to reuse the
campaign's `run_config.jsonc` verbatim. (`sweep.*` stalls are the one exception — they are injected
into the annotation by `pipeline._inject_stalls`, not an env var; the B3 diagnostic bug was exactly
forgetting that, and the fix forwards them as `SIMSPECT_SWEEP_CFG`.)

---

## 5. The nine source sites (the porting checklist), abridged

Porting the pipeline to a new defense build means adding the same nine hooks; the reference shape is
`/work/gem5-recon-modded`. Grouped by purpose (full code in `reference_gem5_build_hooks`):

| # | site | hook | purpose |
|---|---|---|---|
| 1 | `pred/BranchPredictor.py` | `annotationBranchPCs/ForcedTargets/ResolveStallCycles` params | declare the BTB-force + resolve-stall inputs |
| 2 | `pred/bpred_unit.{cc,hh}` | init maps from params; override target in `predict()`; apply resolve-stall | realize the mispredict (1.1) + hold-unresolved (1.2) |
| 3 | `o3/{O3CPU,BaseO3CPU}.py` | `fncCommitStallPC/Cycles` params | declare the fnc stall (1.3) |
| 4–5 | `o3/cpu.{hh,cc}` | fields + ctor init (watch `params->` vs `params.`) | carry the fnc stall into the CPU |
| 6–7 | `o3/commit{.hh,_impl.hh/.cc}` | `fncStallSeqNum/Cycles` + the stall loop before the squash check | hold the boundary at the ROB head |
| 8 | `common/Options.py` | the four CLI flags | expose the hooks |
| 9 | `example/se.py` | `load_branch_annotations` + wiring | drive the hooks from the annotation |

The verification step is a per-file ripgrep audit (each hook appears once per file). **Build-specific
quirks that bit us** (so the next port doesn't): gem5-spt uses `O3CPU.py` (not `BaseO3CPU.py`), a
pointer ctor (`params->`), `commit_impl.hh`, a **string** `--scheme` (`se.py` normalizes `"2"` →
`"SpectreSafeFence"`), and the `build/X86_MESI_Two_Level` target (the plain `X86` target fails on a
stale `MI_example` Sequencer signature); the four amulet builds each needed the `se.py` BTB-target
`+ base` fix individually; SpecLFB is a newer base (argparse, classic caches, `--branch-ann-base`
needed a hex-parsing fix, and `parse_lsq` needed an additive `memaccess_tick` because the newer base
has no "sent out packet" line).

---

## 6. The bounded / orphan-proof launch (the one harness-level hook)

One piece of instrumentation is neither control nor observation but *operational*: `gem5_common.py`
runs gem5 through `_run_bounded()` — a 120 s wall-clock timeout, `start_new_session` +
process-group SIGKILL on timeout, a `PR_SET_PDEATHSIG` preexec so a killed launcher can't orphan a
running gem5, and an `--abs-max-tick` cap. **Why it exists (D2):** a livelocked or runaway run (e.g.
`commitToIEWDelay ≥ 5`, A6) appended unboundedly to its single pipeview file (65–127 GB/run), and
killed sweeps left gem5 children reparented to PID 1 still writing the unlinked file — filling the
volume so `rm` freed nothing. A litmus run finishes in < 1 s, so a timeout == runaway → killed and
surfaced as `status="error"`, never a hit. It is baked into the common path so every checker
invocation (pipeline, watchers, by-hand) inherits it for free.

---

## 7. The layer in one paragraph

SimSpect adds the **minimum** to a stock defense build: three **control** hooks that *realize* the
modeled speculative scenario (force the mispredict, hold a branch unresolved, hold the speculation
boundary) and never touch the defense's data path; **config glue** that drives those hooks from the
same per-test annotation the checker reads; and **observation** that comes entirely from gem5's
existing O3PipeView/LSQUnit/Commit trace, parsed in `gem5_common.py`, so no cache or defense code is
instrumented to *see* a leak. A `run_config → SIMSPECT_* env → trace` bridge makes every run
reproducible by hand. The hard rule — touch only the hooks, prove each control hook doesn't *cause*
the result (fnc on/off, branch-ann on/off, Unsafe baseline) — is what lets a surviving hit be
attributed to the defense rather than to the instrumentation. And a bounded, orphan-proof launch
keeps a runaway run from taking down the box. Everything outside this layer — the taint logic, the
visibility point, the fences — is exactly as the defense's authors wrote it, which is the only way
gem5 can be trusted as ground truth.
