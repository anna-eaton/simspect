# STT (`/work/stt`) vs Recon's STT (`gem5-recon*` scheme 2)

*Living doc. Written 2026-10-30 by the `stl-spec` session, from code read in that session (cafe2 was unreachable while writing, so line numbers are from the earlier reads, not re-checked). Purpose: stop calling both of these "STT". They are different implementations with different threat models.*

## Names to use

| Name | Build(s) | What it is |
|---|---|---|
| **STT-Spectre** | `/work/stt`, `/work/stt-dbg` with `--threatModel=Spectre` (harness default, `gem5-hooks/stt/se_exp.py:332`) | Upstream STT (`cwfletcher/stt @ e3283b9`, the STT authors' code) |
| **STT-Futuristic** | same builds with `--threatModel=Futuristic` | Same code, other threat model. Never run by the harness yet |
| **Recon-STT** | `/work/gem5-recon`, `/work/gem5-recon-modded`, `/work/gem5-recon-stl`, `--scheme=2` | The Recon paper's re-implementation of STT, on a newer gem5, sharing a `secure_scheme/` framework with Delay (1) and DoM (3) |

The names are a proposal (DECIDE item in `URGENT_TODO.md`); the differences below are not.

## The one difference that changes results: what counts as speculative

| | STT-Spectre | Recon-STT | STT-Futuristic |
|---|---|---|---|
| A load is speculative (its output tainted) while… | an older **control** instruction is unresolved | an older **conditional branch** is unresolved **or an older store has no address** | **any** older instruction has not completed |
| Code | ROB `updateVisibleState`: only a control inst clears `prevBrsResolved` while `!readyToCommit()` / fault / squashed (`rob_impl.hh:444-495`); the LSQ marks the load unsquashable when `isPrevBrsResolved()` (`lsq_unit_impl.hh:1018,1051,1075`, the `!cpu->isFuturistic && inst->isPrevBrsResolved()` branch at `:528`) | decode inserts cond branches (`shadowTracker.insertBranch`, `decode.cc:688`) and stores (`insertStore`, `:690`); a load decoded while any shadow exists becomes a spec inst (`:693-694`); exceptions are commented out (`:692`). `ShadowTracker::tick` frees branches on resolve and stores on `effAddrValid()` (`shadow_tracker.cc:162-166, 218-226`), then `freeSpecInsts` clears `setSpeculative(false)` (`:279-293`) | `isPrevInstsCompleted()` (`rob_impl.hh:493-512`); the committed variant is commented out (`:516`) |
| Source | STT paper p5 (Spectre model) | Recon paper Sec. 3, 6 ("speculation cast by control flow and store instructions") | STT paper p5 ("cannot be squashed") |
| Alloy model it should be judged against | `STT_6.als` | none yet (`STT_6` ∪ `STT_6_stl`; proposed `STT_6_shadows.als`) | `STT_6_futuristic.als` (awaiting review) |

Consequences:

- **Recon-STT protects a superset of STT-Spectre.** Every load STT-Spectre calls speculative, Recon-STT does too. So an STT_6 test that is "no leak expected" on STT-Spectre is also "no leak expected" on Recon-STT, and STT_6 hits on Recon-STT are still real signal.
- **STL tests (`STT_6_stl`) are in scope only on Recon-STT and STT-Futuristic.** On STT-Spectre a store with an unknown address casts no shadow, so a bypassing load's value is untainted and a "leak" there is expected by design, not a bug.
- **Futuristic-only sources (a slow ALU op, a slow load, a fault) are out of scope on Recon-STT** and on STT-Spectre. Only STT-Futuristic should block them.
- **Cross-build comparisons need care.** "STT_6 gives 0 ld leaks on /work/stt but hits on recon-modded" compares two implementations, not the same defense twice.

## Other implementation differences (affect the checkers and hooks, not the threat model)

| | STT-Spectre (`/work/stt`) | Recon-STT (`gem5-recon*`) |
|---|---|---|
| gem5 base | old gem5, templated `*_impl.hh` O3 files | newer gem5, `.cc` O3 files plus `src/cpu/o3/secure_scheme/` (`shadow_tracker`, `taint_tracker`, `delay_unit`) |
| Untaint | `rob->compute_taint()` each commit cycle (`commit_impl.hh:1611`) | taint tracker untaints once the load is no longer speculative (`taint_tracker.cc:138`), after `shadowTracker.tick()` (`cpu.cc:488`) |
| How a tainted load is blocked | held in the LSQ until unsquashable | gets as far as `Doing memory access` (`lsq_unit.cc:2077`), then goes into the delay unit (`lsq_unit.cc:2104` `insertTaintedLoad`) |
| Implicit channel (tainted branch) | the squash is made pending until untaint (`commit_impl.hh:934-953`), fetch defers the redirect (`fetch_impl.hh:1021-1070`) | not checked |
| Real cache-send log line | `successfully sent out packet(s)` (what check_ld's gate keys on) | `Memory request (pkt: …) from inst [sn:N] was sent` (`lsq_unit.cc:1546`); the check_ld line does not exist → [`../findings/bug/recon_cache_reach_gate/README.md`](../findings/bug/recon_cache_reach_gate/README.md) |
| Threat-model switch | `--threatModel` (Spectre / Futuristic) | none |
| Other schemes in the same binary | Unsafe / STT variants | 0 Unsafe, 1 Delay, 2 STT, 3 DoM |

`amulet-STT` (AMuLeT's artifact) is a third STT build. Its threat model is **not checked**; don't group it with either until someone reads its code.

Related: [`FUTURISTIC_MODEL.md`](FUTURISTIC_MODEL.md), [`STL_SPECULATION.md`](STL_SPECULATION.md), [`RESOLUTION_HOOKS_SURVEY.md`](RESOLUTION_HOOKS_SURVEY.md), `specs/gem5_builds.json` (`threat_model` field on each build).
