# STT Implicit Channel Defense: Broken in Upstream gem5

## Overview

Investigation of a 4-hit discrepancy between STT base (`/work/stt`, cwfletcher/stt) and Amulet STT_AE (`/work/amulet/amulet-gem5-STT_AE-v1.1`) builds revealed that the difference is not a defense logic divergence but a microarchitectural config artifact (`l1d_assoc` default 2 vs 8). More importantly, the investigation uncovered that STT's implicit channel defense — the mechanism meant to block branch-based speculative side channels — is structurally broken in all known versions of the STT gem5 implementation.

## Empirical observation

| Build | Hits | Total | Config difference |
|-------|------|-------|-------------------|
| STT base (sttbuild) | 8082 | 27102 | `l1d_assoc=2` (Options.py default) |
| Amulet STT_AE | 8086 | 27103 | `l1d_assoc=8` (Options.py default) |

4 tests hit in amulet but not sttbuild: `inst-010216_v2`, `inst-009259_v0`, `inst-007572_v0`, `inst-013555_v7`. All are branch transmitters (`br_x`). The difference is pure timing — different L1D associativity shifts when the fall-through instruction enters the pipeline, pushing edge cases across the hit/no-hit boundary. Neither `gem5_common.py` nor the run configs pass `--l1d_assoc` explicitly, so each build silently uses its own default.

## Bugs found

### Bug 1: `hasImplicitFlow` is computed but never used

**File:** `src/cpu/o3/rob_impl.hh`, function `compute_taint()`

```cpp
explicit_flow(tid, instIt);     // sets hasExplicitFlow
implicit_flow(tid, instIt);     // sets hasImplicitFlow  <-- COMPUTED
address_flow(tid, instIt);
DynInstPtr inst = (*instIt);

inst->isArgsTainted(inst->hasExplicitFlow());  // BUG: ignores hasImplicitFlow
```

`implicit_flow()` runs every cycle for every instruction in the ROB. It checks whether the instruction is under the implicit control of a tainted branch (i.e., executing on a path that depends on a tainted branch's taken/not-taken decision). The result is stored in `hasImplicitFlow` but **never feeds into `isArgsTainted`**. The taint decision uses only `hasExplicitFlow` (explicit data dependency on a tainted producer).

**Consequence:** Enabling `--implicit_channel=1` activates the `implicit_flow()` computation and the squash-delay logic in `commit_impl.hh`, but since `isArgsTainted` never reflects implicit flow, the squash-delay condition (`instCausingSquash->isArgsTainted()`) is always false for branches without explicit taint. The implicit channel defense has zero effect.

**Affected versions:**
- `cwfletcher/stt` `master` branch (origin/master) — present in first commit (`01ba263`) and HEAD
- `cwfletcher/stt` `updates` branch — the author (Jiyong Yu) deleted `implicit_flow` entirely in commit `9f84aa1` ("temp changes", Dec 2020) rather than fixing it
- Amulet `amulet-gem5-STT_AE-v1.1` — same code as master

### Bug 2: `implicit_flow` only triggers on explicitly-tainted branches

**File:** `src/cpu/o3/rob_impl.hh`, function `implicit_flow()`

```cpp
void ROB<Impl>::implicit_flow(ThreadID tid, InstIt instIt)
{
    DynInstPtr inst = (*instIt);
    if (cpu->impChannel) {
        for (auto prevInstIt = instList[tid].begin(); prevInstIt != instIt; prevInstIt++) {
            DynInstPtr prevInst = (*prevInstIt);
            if (prevInst->isControl() && prevInst->hasExplicitFlow()) {  // BUG
                inst->hasImplicitFlow(true);
                return;
            }
        }
    }
    inst->hasImplicitFlow(false);
}
```

Even if bug 1 were fixed, implicit flow only propagates when a **previous control instruction has `hasExplicitFlow=true`** — meaning the branch's operand itself must depend on a tainted (speculative) load. But the mispredicted branch that creates a speculative window typically has untainted operands. For example, in `inst-007572_v0`:

```asm
# first_noncommitted:
    movq    $1, %rdx           # immediate -> untainted
    testq   %rdx, %rdx
    je      .LBB0_1            # MISPREDICTED BRANCH (hasExplicitFlow=false)

    # --- speculative window ---

    movq    (%rsi), %rax       # speculative LOAD -> %rax tainted
    xorq    %rdx, %rdx         # reads %rdx (untainted), NOT %rax
    testq   %rdx, %rdx
    jne     .LBB0_3            # XMIT BRANCH -> isArgsTainted=false
```

The mispredicted branch (`je`) tests `%rdx` which came from `movq $1, %rdx` — an immediate, no load dependency, `hasExplicitFlow=false`. So `implicit_flow` never fires for instructions in the speculative window. The speculative load taints `%rax`, but the xmit branch depends on `%rdx` — a completely independent register chain.

**Consequence:** STT cannot protect against branch transmitters whose operands don't have explicit data dependencies on speculative loads, even when `--implicit_channel=1`.

### Bug 3: Pending squash race condition (master-only fix)

**File:** `src/cpu/o3/iew_impl.hh`

The `master` branch contains a third-party fix (Nicholas Mosier, Stanford, commit `18e304f`, Dec 2025) for a race where a younger untainted branch and an older tainted branch mispredicting in the same cycle creates a secret-dependent squash signal. The `updates` branch and Amulet artifact do **not** have this fix.

From the commit message:
> If the younger, untainted branch was mispredicted but the older, tainted branch was correctly predicted, then the IEW stage notifies the commit stage of the younger, untainted branch misprediction. This results in a secret-dependent squash signal.

## Intended configuration vs actual behavior

The STT README (`cwfletcher/stt`) and the official sample script (`sample_scripts/run_stt.sh`) specify:

```bash
--threat_model=Spectre --needsTSO=1 --STT=1 --implicit_channel=1
```

This confirms implicit channel defense is an intended feature of STT. However, due to bugs 1 and 2, enabling `--implicit_channel=1` has **no functional effect** on branch-based implicit channels.

The only working STT mechanism is the **explicit channel defense**: `fenceDelay` on tainted loads (`lsq_unit_impl.hh:1016-1017`), which blocks speculative loads from accessing the cache. This indirectly starves dependent branches of their operands — but only when the branch has a direct data dependency chain back to a speculative load.

## Scope of impact

These bugs affect the STT defense's coverage of branch-based transmitters (Spectre v1 / branch-misprediction side channels). Load-based transmitters are unaffected — the `fenceDelay` mechanism for tainted loads works correctly.

With `moreTransmitInsts=0` (the default, and the value used by all known configurations including the sample script), branches are additionally not gated at issue time by `readyToIssue_UT()`, which only covers div/float operations. This means there is **no point in the pipeline** where a tainted branch is blocked from executing and broadcasting its redirect.

## Source references

| File | Lines | Description |
|------|-------|-------------|
| `src/cpu/o3/rob_impl.hh` | `compute_taint()` | Bug 1: `isArgsTainted` ignores `hasImplicitFlow` |
| `src/cpu/o3/rob_impl.hh` | `implicit_flow()` | Bug 2: requires `hasExplicitFlow` on control inst |
| `src/cpu/o3/commit_impl.hh` | squash handler | `impChannel` path checks `isArgsTainted` (always false due to bug 1) |
| `src/cpu/o3/iew_impl.hh` | `executeInsts()` | No taint check before `inst->execute()` or `squashDueToBranch()` |
| `src/cpu/o3/inst_queue_impl.hh` | `addIfReady()` | Taint-gated issue only when `moreTransmitInsts!=0` |
| `src/cpu/base_dyn_inst_impl.hh` | `readyToIssue_UT()` | Only gates div/float, never branches |
| `src/cpu/o3/lsq_unit_impl.hh` | load visible state | `fenceDelay(isArgsTainted())` — the only working taint gate |

## Repository

- Upstream: `https://github.com/cwfletcher/stt.git`
- Branches examined: `master` (HEAD + first commit `01ba263`), `updates` (`9f84aa1`)
- Amulet artifact: `/work/amulet/amulet-gem5-STT_AE-v1.1` (no git history; matches master for taint logic)

---

## STT_6 / STT_6_interleave sweeps on `/work/stt` (scheme 2, stock se.py) — FULLY ANALYZED, NO BUGS

**Date:** 2026-06-02 (session `1a:inspectSTT`). Runs:
`results/STT_6_sttbuild__20260602_013615`, `results/STT_6_interleave_sttbuild__20260602_013615`
(`/work/stt/build/X86/gem5.opt`, `--scheme=2`, stock `configs/example/se.py`,
`fnc_commit_stall_cycles=150`, sweep grid `[0,500,2500]`, `unresolved_stall_cycles=5000`).

**Result: 0 leaks across every transmitter kind and mode.**

| run | mode | ld | br_x | leaks |
|-----|------|----|------|-------|
| STT_6_sttbuild | not_taken | 11,652 | 4,348 | 0 |
| STT_6_sttbuild | taken | 11,652 | 4,348 | 0 |
| STT_6_interleave_sttbuild | not_taken | 11,956 | 6,044 | 0 |
| STT_6_interleave_sttbuild | taken | 10,284 | 5,368 | 0 |

Every `ld` and `br_x` record is `ok`/no-leak — the STT defense holds on these testsets under
stock timing. Nothing to root-cause. (Contrast: the **recon-modded** STT runs `__015852` do show
`ld` hits, but those are the load→load `check_ld` false positives already documented in
`claudelog` / `reconresults.md`, not a `/work/stt` signal.)

**The 348 `error` rows in `STT_6_interleave_sttbuild` taken/ld are NOT a bug** — they are a
sweep-completeness artifact. `pipeline._aggregate_sweep_results` flags a stem `error` when its row
is missing from ≥1 of its 3 sweep grid points. All 348 (`inst-003885..~004000_vN`) are present and
clean `ok` at grid points 0 (`0`) and 1 (`500`); they are absent from grid point 2 (`2500`, the
heaviest stall) only because that batch's `check_ld` output file (`grid0002_batch0009`) was never
written — the invocation died mid-batch (~09:18–09:21) and the run wound down. Stock timing, so this
is **not** the `commitToIEWDelay≥5` slow-comm livelock. Verdict: 🟡 harness/pipeline artifact, no
hidden leak in the two completed grid points. Full trace: `claudelog.md` 2026-06-02 23:10.
