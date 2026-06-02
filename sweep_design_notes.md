# Sweep design consult — windows, unresolved branches, CPU-delay/squashWidth knobs

*2026-06-01 — design discussion, inspection only. No files changed.*

Three questions: (1) resolved-branch sweep windows are long — how to catch
resolution-coincidence bugs; (2) only one unresolved branch per test — generate
more?; (3) stretch the O3 IEW↔commit delays (both directions) and shrink squash
width, and inspect where those live.

---

## 1. Resolved-branch sweep windows — add short/dense points, but absolute values are the wrong lever for coincidence

**How it works today** (`pipeline.py:368` `_inject_stalls`, config `sweep` block):

- **Resolved** branches (`correctly_not_taken`) get `resolve_stall_cycles` drawn
  from `points: [0, 500, 2500]`, joint Cartesian across all resolved branches.
- **Unresolved** (mispredicted) branch gets a fixed `unresolved_stall_cycles: 5000`.
- The **xmit** branch is pinned to `0`.
- `gem5_common.check_branch_resolutions`: a branch's resolution propagates at
  `prop_tick = complete + stall · ticks_per_cycle`.

A coincidence (resolved + unresolved resolving in the **same cycle**) needs:

```
complete_R + s_R  ==  complete_U + s_U
```

You control `s_R` (0/500/2500) and `s_U` (5000), but **not** `complete_R` /
`complete_U` — those are per-test, set by where each branch lands in the pipeline.
With `s_R ≤ 2500` and `s_U = 5000`, the resolved branch always propagates well
before the unresolved one. You essentially never collide in the same cycle.

**Two complementary fixes:**

- **Dense short cluster** — e.g. `points: [0,1,2,4,8,16,32,64,128,256]`. Keeps
  resolved resolution near its *natural* tick and near other resolved branches, so
  across a large corpus near-coincidences arise statistically. Cheap, fully
  general, doesn't tune toward any target. **Safe to just do (config-only).**
- **Coincidence-aligned band** (new sweep mode, optional) — sweep `s_R` in a band
  *around* `s_U`, e.g. `s_U + {-2,-1,0,+1,+2}` cycles, so resolutions are *designed*
  to collide. This tunes toward a bug **class** (resolution coincidence), not a
  specific bug — defensible as robustness, but it brushes the "don't tune to hit
  cases" boundary. **Wants your explicit sign-off.**

**Don't shorten the unresolved stall globally.** The long `unresolved_stall=5000`
is what keeps the speculation window wide enough that xmit lands inside
`(lc_retire, fnc_retire)`. Shortening it improves coincidence odds but narrows the
window and costs in-window hits. If you want a coincidence campaign with a shorter
unresolved stall, run it as a **second sweep profile**, not by changing the default.

---

## 2. One unresolved branch per test — more would materially help; it's an `.als` change (your call)

The checker already takes a **list** of unresolved branches
(`check_branch_resolutions` loops over `unresolved`), so the harness supports >1
*today*. The only thing emitting one is the Alloy model.

Multiple nested speculative branches is exactly where the richest microarch squash
bugs live:

- squash **priority** between two in-flight redirects,
- partial squash / ROB-walk ordering bounded by `squashWidth`,
- two redirects colliding in the `commitToIEWDelay` timebuffer slot.

With a single unresolved branch, none of that is reachable.

Per the scope rules I won't touch the `.als`. Recommendation: make ≥2 independent
unresolved branches a model dimension (you already vary `oneLP` vs `full`).
**Caveat:** the resolved-branch Cartesian product already explodes — read the
sampling note in §4 before also multiplying branch count.

---

## 3. CPU delays + squashWidth — inspected; layout and the right place to stretch them

All in `/work/gem5-spt/src/cpu/o3/O3CPU.py` (`BaseO3CPU`, defaults):

| param | default | role |
|---|---|---|
| `iewToCommitDelay` | 1 | **forward** IEW→commit timebuffer wire (`commit_impl.hh:344,374`, `getWire(-iewToCommitDelay)`) |
| `commitToIEWDelay` | 1 | **backward** commit→IEW wire — carries squash/redirect (`iew_impl.hh:336`) |
| `renameToIEWDelay` | 2 | rename→IEW |
| `squashWidth` | 8 | insts squashed per cycle in the ROB (`rob_impl.hh:436`, `numSquashed < squashWidth`) |
| `backComSize` / `forwardComSize` | 5 / 5 | **timebuffer depth** (`cpu.cc:181` `timeBuffer(backComSize, forwardComSize)`) |

The forward/backward pair you remembered is `iewToCommitDelay` /
`commitToIEWDelay`. Decreasing `squashWidth` makes a squash span more cycles, so
squashed speculative instructions linger longer in the window — directly the
timing stretch you're after.

**Critical gotcha:** the timebuffer is sized `(backComSize, forwardComSize)` and
read at `getWire(-delay)`. So `commitToIEWDelay` / `iewToCommitDelay` must stay
**≤ backComSize (5)**. Stretch a delay past 5 and you read out of the buffer's
range — you must bump `backComSize` / `forwardComSize` in lockstep. Never move one
without the other.

**Where to set them — NOT in `O3CPU.py`.** Editing the defaults there is global:
it silently re-times *every* build (recon, stt, spt, amulet) and isn't sweepable.
These are pure timing knobs (not defense logic, not the hooks), so the
project-consistent move is the existing `config → SIMSPECT_* env → se.py` bridge
you already use for `fnc_commit_stall_cycles`:

1. add `iew_to_commit_delay` / `commit_to_iew_delay` / `squash_width` (+ an
   auto-bumped `back/forwardComSize`) to `gem5.*` in the run_config,
2. thread them through `pipeline.py:_build_gem5_env` as `SIMSPECT_*` env vars,
3. apply them to the CPU object in `se.py`.

That keeps them **per-run and sweepable** like any other point and touches only the
config-glue layer (se.py) — the same class of edit `reference_gem5_build_hooks`
already sanctions, not gem5 internals.

---

## 4. Other robustness suggestions

- **Grid sampling, not full Cartesian.** Dense points (§1) × more resolved
  branches × more unresolved branches (§2) makes `itertools.product` blow up fast.
  Switch `_grid_points` to random or pairwise (covering-array) sampling so you can
  afford density and branch count without combinatorial cost.
- **`check_br` redirect criterion is coarse.** It *does* now enforce the
  `(lc_retire, fnc_retire)` window (`check_br.py:71–83` — the CLAUDE.md note saying
  it doesn't is stale). But `branch_redirected` is just "xmit completed AND
  fall-through never retired," which conflates a real speculative-window redirect
  with any squash. Worth tightening if branch hit rates look inflated.

---

## Proposed next steps

| # | Action | Boundary |
|---|---|---|
| a | Drop in dense short-point profile | config-only, fully general — **safe to do** |
| b | Prototype CPU-delay / squashWidth bridge through se.py + a small `(squashWidth, commitToIEWDelay)` sweep | config-glue layer — **safe, but confirm se.py edits OK** |
| c | Switch grid to sampled instead of Cartesian | pipeline change — **safe** |
| d | Coincidence-aligned sweep band (§1) | tunes toward a bug *class* — **needs your go-ahead** |
| e | ≥2 unresolved branches per test (§2) | `.als` change — **needs your go-ahead** |
