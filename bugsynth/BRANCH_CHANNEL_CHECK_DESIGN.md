# Workshopping a robust branch-channel transmitter check

*Standing need (Anna, top priority). The current `STAGE3_gem5/check_br.py` ("did a tainted branch redirect
in the window") + the squash-order check do NOT cover the space of branch channels. This is the design
discussion for a principled replacement.*

## The core realization
The **load** channel is detectable from a **single run** because its observable is essentially **binary and
local**: did the speculative load touch the cache, yes/no. So "did the cache access happen inside the
speculative window" is a sound criterion.

**Branch channels are different: most of them are DIFFERENTIAL / TIMING channels.** What an attacker reads
off a branch is not a yes/no cache event — it's *when* (and *whether*) a redirect happens, *which* branch's
squash wins, *how long* a window stays open, *what* got speculatively fetched. Many real branch leaks
(pending-squash is the proof) are about a **public/untainted** branch event whose *timing* depends on a
**secret** — you literally cannot see that from one run. You have to **vary the secret and watch whether a
public observable moves.** That is the architectural mistake in the current checker: it's a single-run
window test applied to a channel class that is inherently differential.

## Taxonomy — the branch-channel types we need to cover
| # | channel | observable | what carries the secret | current check_br? |
|---|---|---|---|---|
| **A** | **Direct direction** | the speculative path / redirect of a *tainted* branch in-window | the branch's own taken/not-taken | partial (no clean taint gate, coarse redirect) |
| **B** | **Redirect-timing (cross-branch)** | an *untainted* branch's redirect **tick** | a *different*, tainted branch (via shared squash signal) | **no — can't express** (pending-squash) |
| **C** | **Squash priority / order** | which squash wins / redirect target / order | which of several branches resolves "first" (secret-dependent) | partial ("squash-order" check; incomplete) |
| **D** | **Implicit flow (control→data)** | a downstream **load** (arr[x]) | branch direction sets a value x | **no — model can't even generate** (needs `cdep` edge) |
| **E** | **Window modulation** | a downstream load's *ability to leak* | a tainted branch's resolution timing widens/narrows the window | **no — cross-instruction, indirect** |

The current pipeline tests roughly a slice of **A** (and the squash-order check a slice of **C**). **B, D, E
are uncovered**, and A/C are covered fragilely.

## The unifying frame: non-interference (differential) testing
Treat the whole thing as **non-interference**: an attacker-visible (public/untainted) branch observable must
be **invariant to the secret**. If it isn't, that's the leak, and the magnitude is the channel capacity.

```
   for each secret value s in {s0, s1, ...}:          # vary ONLY the secret
       run the test, fixing all non-secret inputs
       extract PUBLIC_OBS(s) = the attacker-observable branch trace projection
   LEAK  iff  PUBLIC_OBS(s) is NOT constant over s
```
- **Secret** = the tainted input(s) the gadget depends on (a speculative load's value; or a branch we force
  taken vs not-taken via the BTB/condition).
- **Public observable** = things an attacker may legitimately measure: **untainted** branches' redirect
  ticks, the fetch-redirect schedule of public PCs, squash order/target among untainted events, commit
  timing of public instructions (window width). Crucially it **excludes** tainted events (those are what the
  defense is allowed to hide).
- **Leak** = any public observable that *moves* with the secret.

This single frame **subsumes A–C**:
- **A** (direct direction): vary the secret → the tainted branch redirects vs not / at a different tick →
  the *public* speculative-fetch schedule downstream changes ⇒ leak. (And it correctly reports STT as SAFE
  when the made-pending defense keeps the public schedule invariant.)
- **B** (pending-squash): vary the tainted branch `bo` → the *untainted* branch `by`'s redirect tick moves ⇒
  leak. This is exactly `bugsynth/pendsquash_diff.py`, generalized.
- **C** (squash order): vary the secret → which untainted squash wins / its tick changes ⇒ leak.

And it is **robust by construction**: no fragile "is this redirect inside (lc,fnc)" heuristic — it directly
measures secret-dependence of what the attacker can see.

## What a concrete checker needs (design sketch)
1. **Secret parameterization.** Identify the gadget's secret input and a way to set it to ≥2 values without
   perturbing anything else:
   - simplest: the tainted **branch's architectural direction** — force it taken vs not-taken (BTB/condition
     value), holding all timing/stalls fixed; or
   - the value of the **speculative load** that feeds the tainted branch (init the loaded line to 0 vs
     nonzero). *Only the secret changes between runs.*
2. **Public-observable projection.** From each run's trace, extract, **for untainted/public events only**:
   the redirect/squash-broadcast tick of every *untainted* branch; the fetch sequence of public PCs and
   their ticks; the commit tick of the public boundary (window width). (Parse from `Commit` +
   `O3PipeView`; reuse `parse_commit_squashes`, `parse_pipeview`.)
3. **Invariance test.** Diff the projections across secret values, with a tick **margin** (≥1 cycle) to
   ignore measurement noise. Any public feature whose value/tick differs ⇒ leak; report *which* feature and
   the Δ (the channel "signal").
4. **Taint gate** comes for free: tainted events are excluded from the projection, so the defense correctly
   hiding a tainted branch's own redirect is *not* a leak — only a public observable moving is.
5. **Generality knob:** the set of secret values and the observable projection are the two parameters; new
   branch-channel types (C variants, etc.) are new projections, not new ad-hoc checkers.

## Why this is the right investment
- It turns pending-squash (and squash-order, and direct-direction) from **bespoke scripts** into one
  **mainline** differential checker — so future branch-timing bugs are found by the pipeline, not by hand.
- It is **principled** (non-interference is the actual security property STT/recon claim) rather than a
  redirect heuristic, so it stops both false positives (the historical STT br_x FPs) and false negatives
  (pending-squash, which the current checker simply cannot see).
- **D (implicit flow)** still needs a model/concretization change to *generate* the gadget (the `cdep`
  control-dependence edge), but once generated its leak is just another public observable (the downstream
  load) moving with the secret — so the *same* differential checker covers it.
- **E (window modulation)** also fits: the public observable is a downstream load's access, and the secret
  is the branch timing — same frame.

## Open questions to settle with Anna
- **Secret parameterization** per gadget: direction-flip vs load-value-flip — which is more faithful / less
  perturbing? (Direction-flip changes control flow; value-flip keeps structure but needs a writable secret
  line.) Probably support both.
- **What counts as "public"** precisely — define the attacker observation model (timing of which events).
  This is the one real judgement call; everything else follows from it.
- **Cost**: N runs per test (N = #secret values). For a 2-value differential that's 2× — acceptable, same as
  pendsquash_diff / otb_check already do.
- Relationship to the **load** checker: loads could also be folded into this frame (cache access as a public
  observable), unifying both — but the single-run load check is cheaper and already works, so keep it and
  add the differential branch check alongside.

---

## Prototype — `bugsynth/check_br_differential.py` (2026-06-09)
First implementation of the non-interference frame (channel type **B**; extensible to A/C). Run on
/work/stt scheme 2: `python3 bugsynth/check_br_differential.py 20 2000`.

- **Secret-flip:** taint-flip (variant A = older branch reads a speculative load / secret-derived; variant
  B = reads a constant) using the `STT_6_pendsquash` / `_ut` twins. *(VALUE-FLIP — init the secret load's
  line 0 vs 1 so the branch direction flips — is the faithful next step; the framework is identical, only
  `run_variant`'s two inputs change. Implementing it needs a committed secret-store injected at
  concretization, since SE-mode memory is zero-init.)*
- **Taint classification** is proper forward dataflow over the asm (a register is tainted iff transitively
  written by a load) — fixes the naive "reads a register" classifier that mis-marked the xmit br_bez
  passthrough as tainted.
- **Observable projection:** each branch's redirect timing (`made_pending` + squash-broadcast tick),
  partitioned by taint. A leak = an **untainted** branch whose timing MOVES with the secret; a **tainted**
  branch moving is the DEFENSE (STT delaying it), not a leak.

**Validation (all three design promises met):**
1. **Reproduces pending-squash:** 18/20 gadgets leak (an untainted branch's redirect timing depends on the
   secret) — matches the bespoke `pendsquash_diff.py` (17/20), but via the *general* frame.
2. **No false positives:** old check_br (flags ANY branch redirect/move) would flag ~all; our taint-gated
   differential reports the *tainted*-branch moves as DEFENSE — exactly the historical STT br_x FPs
   (`project_stt_branch_leak_cause`), now correctly SAFE. (Negative-control gadgets where only tainted
   branches move → reported safe.)
3. **Self-consistency:** 12/12 give identical observables when the secret is unchanged (A vs A) → no
   measurement-noise false leaks.

**Still TODO to make it the mainline branch checker:** (a) VALUE-FLIP secret parameterization (faithful);
(b) observable projections for channel **A** (downstream public-fetch schedule) and **C** (squash order);
(c) generate-side support for **D** (implicit-flow, needs the `cdep` edge) and **E** (window modulation);
(d) a clean base-`br_x` negative-control testset; (e) fold into `pipeline.py` as a per-test consumer.
