# STT br_x "Leaks" — Checker Artifact, NOT a gem5 Leak (CORRECTED)

**Build:** `/work/stt/build/X86/gem5.opt` (cwfletcher/stt, DerivO3CPU), `--scheme=2`
**Runs:** `STT_6_sttbuild`, `STT_6_interleave_sttbuild`
**Status:** This file’s ORIGINAL conclusion ("real gem5 STT leak via a FLAGS taint-propagation gap")
was **WRONG**. Corrected 2026-06-02 after running the differential *with the sweep’s resolve-stall
applied*. The corrected finding: **STT’s branch implicit-channel defense works; the br_x hits are
`check_br` false positives** — and `check_br` has been fixed.

---

## 1. Corrected conclusion (TL;DR)

1. STT_6 br_x recorded hits are **false positives in `check_br`**, not real leaks.
2. STT’s defense **does** fire: a tainted, mispredicted branch is **"made pending"** — its
   squash/redirect is delayed until it untaints (≈ window close), so no in-window redirect.
3. `check_br` keyed the hit on the branch’s **resolve/complete tick** (`xmit_complete`), which is
   in-window regardless of the delay → false positive. The leak signal should be the **actual
   squash/redirect broadcast tick** (the squash ordering the checker’s own docstring intended).
4. **Fix applied** to `check_br` (+ `gem5_common`): key the verdict on the xmit’s squash tick from
   the Commit log. Validated: 5/5 STT false positives removed, real leaks (scheme=0) still caught.

## 2. How the original conclusion went wrong

The original write-up ran the gadget under gem5 with the **base `.ann.json`**, which has
`resolve_stall_cycles=None`. The resolve-stall that holds the speculative window open is injected
**by the sweep at its grid points**, not baked into the base ann (`pipeline.py:_inject_stalls`:
every mispredict branch → `unresolved_stall`=5000; `correctly_not_taken` → grid stall `[0,500,2500]`;
xmit → 0). With **no stall**, pc0 resolved in ~38 cycles and squashed the speculative load before it
executed → the branch read a stale `%rax=0`, untainted, so `stalledBranchMispredicts=0`. I read that
as "STT never defends" → "real leak." It was an artifact of running the wrong (un-stalled) config.

**With the stall applied (stall≥500, the real sweep condition):** the load executes, taints `%rax`,
the xmit branch reads the tainted value, and STT delays its squash:
- `stalledBranchMispredicts=2`, and the Commit log shows
  `(Lazy) A branch mispredicInst PC (0x401070=>0x401073) is made pending` — the xmit branch itself.

## 3. The real `check_br` bug

`check_br.py`’s docstring says the leak signal is squash ordering ("branch alive after its
fall-through → it squashed the fall-through → redirect = leak"), and it computes `xmit_last_alive`/
`ft_last_alive`. But the code set `xmit_signal = xmit_complete` (the *resolve* tick) and tested that
against the window. STT (or any delay-based defense) lets the branch **resolve** in-window while
**delaying the redirect** out of it — so the resolve-tick criterion false-positives.

Evidence (inst-000009, stall=5000):

| | xmit branch (`0x401070`) |
|---|---|
| **UNSAFE (scheme=0)** | `Squashing due to branch mispred PC:0x401070` @ **162000 — in-window → real redirect (leak)** |
| **STT (scheme=2)** | `made pending @0x401070`; **no in-window squash** — redirect delayed, subsumed by pc0’s squash at window-close (2657000+) |

`check_br` (old) returned `issued_in_window=True` for BOTH because `xmit_complete`=161500 is in-window
in both. The squash tick differs (162000 vs none-in-window) — that’s the correct discriminator.

## 4. The fix

- `gem5_common.py`: always trace `Commit`; new `parse_commit_squashes()` → `pc → [squash-broadcast
  ticks]`; thread `squash_by_pc` into `check_fn`.
- `check_br.py`: `xmit_signal` = earliest squash tick at `xmit_pc`. No in-window squash ⇒ no hit.
  Falls back to the old `complete`-tick behaviour only when no Commit trace exists (backward-compat).
- `check_ld.py`/`check_other.py`: accept & ignore the new kwarg.

## 5. Validation (`/work/stt`, sweep grid `[0,500,2500]` faithfully replicated)

| condition | result |
|---|---|
| STT (scheme=2), 5 reproduced br_x OLD-hits | **all 5 → NEW no-hit** (false positives removed); 0/15 NEW hits |
| UNSAFE (scheme=0), genuine transmitters | inst-000009/000017/000027/000041 → **NEW hit** (real leak still caught) |
| inst-000002 (xmit never broadcasts a squash) | NEW no-hit in **both** schemes (OLD false-positive, correctly rejected) |

So the corrected `check_br` credits STT’s working defense, still catches real leaks, and drops
gadgets whose xmit never actually redirects.

## 6. What this means for the numbers / scope

- The br_x hit counts in `STT_6_sttbuild` / `STT_6_interleave_sttbuild` are **inflated by `check_br`
  false positives**; re-running with the fixed checker will reduce them (likely to ~0 under STT for
  the sampled population — STT’s branch defense holds).
- This is a **SimSpect checker bug**, fixed in `STAGE3_gem5/`. It is **not** a gem5/STT bug and does
  **not** change testset relaunch scope. (Separately, the duplicate-PC Stage-2 codegen bug *does* —
  see `claudelog.md`.)

## 7. Source references

| File | Role |
|---|---|
| `pipeline.py:_inject_stalls` / `_grid_points` | how the sweep injects resolve-stalls (the window) |
| `/work/stt … commit_impl.hh:934-954` | STT delays a tainted mispredicted branch’s squash ("made pending") |
| `STAGE3_gem5/check_br.py` | fixed: keys verdict on squash tick, not complete tick |
| `STAGE3_gem5/gem5_common.py` | `parse_commit_squashes()`, `Commit` trace, `squash_by_pc` plumbing |

## 8. Superseded claims (do not cite)

- ❌ "STT’s branch defense never fires (`stalledBranchMispredicts=0`)" — true only **without** the
  sweep stall; with the stall it fires.
- ❌ "Taint never reaches the branch through the FLAGS hop" — the branch IS tainted under the real
  (stalled) config; STT delays it.
- ❌ "Real gem5 leak." — it’s a checker artifact; STT works.
</content>
