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

## One Alloy model per threat model (checked 2026-11-07)

All three are STT_6's skeleton with a different speculation source; each differs from `STT_6.als` only in a helper block plus the contract and protection-set clauses.

| Model | Threat model / build | File | State |
|---|---|---|---|
| `STT_6` | STT-Spectre, `/work/stt` | `STAGE1_alloy/models/STT_6.als` | production |
| `STT_6_shadows` | Recon-STT, `gem5-recon*` scheme 2 | `STAGE1_alloy/models/proposed/STT_6_shadows.als` (**draft, not approved**; the pipeline does not read `proposed/`) | contract `uncommitted & after an unresolved branch or unresolved-address store` = proposal P1 in `MODELS_AND_BUILDS.md` PART 7 |
| `STT_6_futuristic` | STT-Futuristic, `/work/stt` + `configs/example/se_futuristic.py` | `STAGE1_alloy/models/STT_6_futuristic.als` | **parked 2026-11-07** (Anna: Futuristic is not STT's only mode; see `FUTURISTIC_MODEL.md`); written 10-30, not reviewed |

**Which speculation sources each model admits** (`STAGE1_alloy/model_source_matrix.py`: Alloy asked for an instance with `gen_useful_litmus` plus "the unresolved instructions are only of kind K"; exactly 6 instructions):

| Model | branch only | store only | store only, true alias | store only, no alias | load only | ALU only | branch + store |
|---|---|---|---|---|---|---|---|
| `STT_6_shadows` | SAT | SAT | SAT | SAT (by `rf`; see below) | UNSAT | UNSAT | none found in 15-25 min (SAT cases take 2-7 s) |
| `STT_6_futuristic` | SAT | SAT | SAT | SAT | SAT | SAT | none found in 25 min |

Branch + store finding nothing is expected. Resolution-minimality requires every unresolved instruction to be needed on its own, but the older of two sources already covers everything the younger one covers. So a minimal 6-instruction instance has exactly one source; the Futuristic enumeration on 10-30 never had two source kinds either.

**Concretization:** branch-only instances go through `mispredict_not_taken` (60/60), and true-alias store-only instances through `stl_bypass` (60/60). Store-only instances **without** a true alias do not concretize. Of 60 picked by an `rf`-based "no alias" predicate, 34 have a store whose memory location is unspecified (no `Mem_s` atom). Those are the real no-alias cases, and they fail with "unresolved store has no specified outmem". The other 26 do alias: the store and a load before the transmitter name the same `Mem_s` atom, with no `rf` edge between them (the "shared opstate ≠ rf edge" trap). `stl_bypass` pairs by atom, so they concretize correctly. See the DECIDE item and the next section. Futuristic load and ALU sources have no concretization mode (parked with the rest of Futuristic).

**gem5, 60 tests per shape** (cafe2 `results/STT_6_shadows_draft/` and `results/STT_6_futuristic_draftcheck/`, configs and `run.log` in each):

| Model, shape | Build | Defense on | Unsafe | Note |
|---|---|---|---|---|
| shadows, branch only | `gem5-recon-modded` scheme 2 / 0, fixed harness, unresolved hold 5000 | 1/60 hits | 49/60 | the one hit, `inst-000003`, is the known recon SLF gadget (load → store to `(%rsi,%rax)` → transmitter loads `(%rsi,%rax)`, value forwarded), `wiki/findings/bug/recon_SLF_stlf_bypass/NOTE.md`; its diagnostic was not run |
| shadows, store only + alias | `gem5-recon-stl`, `stl_hooktest.py`, hold 5000 | 0/32 load transmitters sent during the hold (59/60 valid bypasses) | 32/32 sent | `alias` control: 0 bypasses, 0 sent. Same as `STT_6_stl` on 10-30 |
| futuristic, branch only | `/work/stt` scheme 2 with `se_futuristic.py` / `se.py` / scheme 0 | Futuristic 0/60, Spectre 0/60 | 43/60 | gem5 prints `Info: simulation uses threatModel: Futuristic` with `se_futuristic.py` |

### How a store-source test gets its alias (2026-11-07)

The order in a store-source test is: store S (address unresolved, the shadow starts here) → load L (younger than S, reads the same location) → transmitter X (at or after L, uses L's value). Under Recon-STT everything after S is speculative until S's address resolves, so L's value is protected and X must not send it. With a true alias, the memory-dependence predictor says "no alias", L reads the stale value, and S's address resolution squashes L: a real transient window. Without one, L's value is architecturally correct and nothing is squashed. Recon-STT still delays X (the shadow doesn't care about aliasing), but the test only checks that conservatism, not a leak window.

The alias is checked in three places:

1. **Alloy (generation).** A fact says the alias exists. `STT_6_stl` uses an `rf` edge (`stl_alias_pair`: `some (s.outmem.rf & l.inmem) and l in xm + xm.^(~spo)`). The draft `STT_6_shadows` has no alias fact. The proposed atom-based version: every unresolved store S has a younger uncommitted load L, at or before `xm`, naming the same `Mem_s`, with no other store to that `Mem_s` between them; `rf` is not required. Because a store's `outmem` is `set` (it can be absent), this fact also forces the store to have a location. Checked with `model_source_matrix.py --only str_alias_atom` (the run predicate = that fact plus "store-only"): SAT, 60 instances in 4 s; 60/60 concretize with `stl_bypass`; 37 of the 60 pair only by a shared `Mem_s` atom with no `rf` edge, so an `rf`-based fact would have excluded them.
2. **parsexml (concretization).** `pass2_6_specify_stl` (`parsexml.py:983-1037`) pairs each unresolved store with the first uncommitted load after it that names the same `Mem_s` atom before any other store writes it (the same "most recent writer" rule), then makes the store's runtime address equal the load's. It refuses a store with no location ("no specified outmem") or no aliasing load.
3. **gem5 (did the bypass actually happen).** `gem5-hooks/stl/stl_hooktest.py:58` marks a test valid only if the store was held (`stl_hold`), the predictor said `pred_no_alias` for L, L executed before the store's address was released, and gem5 raised the memory-order squash of L caused by S. 59/60 shadow store tests were valid (the table above).

Related: [`FUTURISTIC_MODEL.md`](FUTURISTIC_MODEL.md), [`STL_SPECULATION.md`](STL_SPECULATION.md), [`RESOLUTION_HOOKS_SURVEY.md`](RESOLUTION_HOOKS_SURVEY.md), `specs/gem5_builds.json` (`threat_model` field on each build).
