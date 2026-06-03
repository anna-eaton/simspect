# SimSpect — every knob in the leakage prompting

*A complete catalog of the parameters that (a) **define** what a leak is, (b) **shape** the tests we
enumerate, and (c) **probe** each test in gem5. For each knob: what it controls, its default, and —
the point of this document — **why it exists**, grounded in the design constraint or the empirical
finding that put it there. Companion to [`PAPER_RESULTS.md`](PAPER_RESULTS.md),
[`METHODS_CONCRETIZATION.md`](METHODS_CONCRETIZATION.md),
[`METHODS_INSTRUMENTATION.md`](METHODS_INSTRUMENTATION.md).*

The knobs fall in seven tiers, from "what is a leak" down to "what timing does the CPU run at":

```
 Tier 1  LEAKAGE SPECIFICATION   — Alloy predicates: what counts as a transmitter / speculative / protected / a leak
 Tier 2  ENUMERATION QUALITY     — Alloy minimality + scope: which instances get generated, how many, how minimal
 Tier 3  SPECULATION REALIZATION — speculation.* : how the abstract "unresolved branch" becomes a concrete mispredict
 Tier 4  CHAIN INTERLEAVING      — interleave.* + free_pool : manufacturing multi-source merges (OTB)
 Tier 5  DEFENSE / PROBE         — gem5.* : which defense, which scheme, which hooks
 Tier 6  WINDOW SWEEP            — sweep.* : the stall knobs that move the speculative window (s_R, s_U, fnc)
 Tier 7  MICRO-ARCH TIMING       — se_exp.py env : commitToIEWDelay & friends (the fragility axis)
```

Tiers 1–2 live in `STAGE1_alloy/models/*.als` (**owner-gated — never edit without approval**).
Tiers 3–6 live in the run-config JSONC. Tier 7 lives in an additive `se_exp.py` (config, not defense
source). The golden rule that frames all of it: **the leak *window* (Tier 1) is the contract and is
fixed; everything below it is how we probe that contract, and must be reported as a swept variable,
never tuned to a desired answer** (`PAPER_EXPERIMENTS.md`, CLAUDE.md).

---

## Tier 1 — the leakage specification (what *is* a leak)

These are the Alloy predicates in `STT_6.als` (SPT/Recon variants differ only where noted). They are
the actual definition of leakage; the gem5 side is just ground truth for it. Line numbers are from
`STAGE1_alloy/models/STT_6.als`.

### 1.1 The instruction & dataflow vocabulary (the substrate the knobs act on)

| element | line | what it is | why it exists |
|---|---|---|---|
| `InstrType` = `TLoad`/`TStore`/`TBranchn`/`TBranchx`/`TOthern`/`TOtherx` | 30–35 | the six instruction kinds; the `…x` kinds are *transmitting* variants of branch / ALU | a litmus test is a sequence of these; the `n`/`x` split is what lets the model mark *which* op is the intended transmitter |
| `tBool` (`xm`), `cBool` (`committed`), `rBool` (`resolved`) | 19–21, 66–68 | per-instruction booleans: is this the flagged transmitter / has it committed / has its branch resolved | these three booleans **are** the speculative state of an instruction; the whole leak predicate is phrased over them |
| `IX0…IX5` + `spo` | 38–43, 129–131 | up to **6** program-order positions; `spo` is the total order | bounds gadget length at 6 instructions — long enough for `br → load → ALU → xmit` shapes, short enough to enumerate |
| `Operand` = `Inreg`/`Inaddr`/`Inmem`/`Outreg`/`Outmem`; `State` = `Reg_s`/`Mem_s`; `opstate` | 85–93, 24–26 | operands and the abstract register/memory *state* they read/write | the abstraction that makes dataflow *symbolic*: two operands sharing an `opstate` is a data dependency without committing to a physical register |
| `rf`, `ddi`, `spo` edges | 155–174 | reaching-definition (`rf`), direct-data-influence (`ddi`), program-order (`spo`) | `rf` is the dataflow edge the leak predicate chases from a transmitter back to a speculative source |

These are not "knobs" you turn per run — they are the model's type system. But they are the surface
every Tier-1 predicate is written against, so the catalog needs them.

### 1.2 `leakage_function` — **which operands can be a transmitter** (the scope knob)

```alloy
//fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}   // line 327 (disabled)
fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}             // line 328 (active)
```

- **Controls:** the set of operands the model is ever willing to call a *transmitter*. Active value:
  a **load's address** (`Loads.inaddr`) and an **xmit-branch's input register** (`Branchxs.inreg`).
- **Why it exists / why this value:** this is the single most consequential scoping decision in the
  model. It says SimSpect targets **load and branch transmitters only** — never stores, and (with
  `Otherxs.inreg` commented out) not yet ALU transmitters. Two consequences, both deliberate:
  1. It is **why SimSpect does not — and by STT's contract should not — find the store→TLB bug**
     (`PAPER_RESULTS.md` §2.2): there is no store operand in this set, so no generated test targets a
     store transmitter.
  2. It is the lever to **widen scope**: un-commenting `Otherxs.inreg` turns on ALU transmitters
     (and would arm the dormant `idivq` div-fault leak path, D3). Owner-gated.

### 1.3 `speculation_contract_p` — **what counts as speculative**

```alloy
fun speculation_contract_p[p] : Instruction { uncommitted_p[p] & has_unresolved_brs_p[p] }   // line 325
```

- **Controls:** an instruction is "speculative" iff it is uncommitted **and** sits after some
  unresolved branch.
- **Why:** this is the threat model — speculation is opened by an *unresolved branch*, and only
  uncommitted instructions under one are at risk. The commented alternative at line 324 also admits
  unresolved *memory* (`no_unresolved_mem`); the active contract is branch-only, matching the
  Spectre-v1 family the defenses target. It is the predicate `DESIGN.md` reasons about when it proves
  "xmit branches are always resolved in STT_6."

### 1.4 `hardware_protection_policy` + `prot_set_propagation_p` — **what is protected, and how it flows**

```alloy
fun hardware_protection_policy : State { Mem_s }                              // line 326
fun prot_set_propagation_p[p,i,s] : State {
    s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate          // line 331 (declassify)
    ... }                                                                     // (multi-line fixpoint)
```

- **Controls:** the protection set seeds at all **memory state** (`Mem_s`) and propagates forward,
  with **non-speculative loads declassifying** the memory state they read (a load with no unresolved
  branch before it removes its read state from the protected set). The fixpoint is assembled by
  `a[]` / `last_committed_protset_p` (lines 231–239).
- **Why:** this encodes "secret data originates in memory and stays protected until a non-speculative
  instruction legitimately reads it." **This is also the source of the C2 over-approximation**
  (`PAPER_RESULTS.md` §9): because protection is seeded broadly and propagates to *anything produced
  under speculation*, a register written by a speculative ALU op reading only constants is still
  marked protected — so gem5 correctly doesn't leak it and we get a false "hit." The proposed fix
  (forward closure from real sources, monotone union) is in `POTENTIAL_MODEL_FIX_constaddr_taint.md`.
  The SPT variant's `inaddr`-vs-`inreg` declassification asymmetry was a *real model bug*, already
  fixed and verified UNSAT (`project_spt_model_inaddr_protset_fix`).

### 1.5 `speculative_xmit_p` and `secure_speculation_scheme_p` — **the leak predicate itself**

```alloy
fun speculative_xmit_p[p] : Operand { leakage_function_p[p] <: speculation_contract_p[p].operands }  // 229
pred secure_speculation_scheme_p[p] {                                                                 // 262
    (no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and
    (no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p]) }
```

- **Controls:** a *speculative transmitter operand* = a transmitter operand (1.2) that belongs to a
  speculative instruction (1.3). The scheme is **secure** iff no protected state reaches such an
  operand — directly, or through the transitive closure `^(op_edges_p)` of dataflow edges. **A leak =
  `not secure_speculation_scheme_p`.**
- **Why:** this is the formal statement of "a secret-derived value reaches a transmitter while
  speculative." The transitive-closure second conjunct is what lets the leak travel through arbitrary
  ALU chains, not just a direct load→xmit edge. This predicate is the oracle gem5 is checked against.

### 1.6 `tag_xm` — **force the instance to actually contain the leaking transmitter**

```alloy
fact tag_xm {
    (some (last_committed_protset_p[no_p].(~opstate) & speculative_xmit_p[no_p] & xm.operands)) or
    (some last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands) }  // 270
```

- **Controls:** every generated instance must contain an instruction flagged `xm` whose operand is a
  *protected, speculative transmitter* (directly or via closure).
- **Why:** this is the knob that makes **100% of generated tests targeted** (`PAPER_RESULTS.md` §5):
  without it Alloy would happily emit benign sequences; with it, every instance is, by construction, a
  candidate leak the defense must stop. It is the formal meaning of "test targeting."

### 1.7 The PTag minimization machinery (`RO`/`RC`/`RR`/`RI`/`RS`)

```alloy
one sig RO/RC/RR/RI/RS extends PTag {}   // 191–195  : remove operand / make committed / make resolved / remove instruction / remove state
```

- **Controls:** a family of *perturbations* the model can apply to an instance and re-check security
  under (`secure_speculation_scheme_p[RR->i]` = "is it still a leak if branch `i` were resolved?").
- **Why:** these are how `gen_useful_litmus` (Tier 2) asks "is every part of this gadget *necessary*?"
  Crucially, the minimizer uses only `RR` (resolve a branch) and `RS` (remove a state) — **never `RI`
  (remove instruction) or `RO` (remove operand)**. That asymmetry is exactly why extra `other` ops and
  *unspecified operands* survive minimization, which is what makes the **OTB generation gap** a
  *cap/ordering* artifact rather than a model limit (C3; `OTB_GENERATION_GAP.md`).

---

## Tier 2 — enumeration quality & scope (which instances actually get generated)

### 2.1 `gen_useful_litmus` — the minimality/necessity conjunction

```alloy
let gen_useful_litmus {
    not secure_speculation_scheme_p[no_p]                                  // 302  base instance leaks
    all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]   // 306  every unresolved branch necessary
    secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]     // 308  the first-uncommitted is necessary
    all s: State | secure_speculation_scheme_p[RS->s] }                    // 310  every State necessary (no no-op padding)
```

- **Controls:** an instance is "useful" iff it leaks, **and** removing any single necessary part
  (resolving any unresolved branch, or removing any state) would make it *not* leak.
- **Why each clause:**
  - **302** — the instance must actually be a leak (else it is not a litmus test).
  - **306/308** — every unresolved branch must be load-bearing; a branch you could resolve without
    killing the leak is dead weight.
  - **310 (the `RS` clause)** — **every abstract State must be necessary.** This is the clause that
    eliminates no-op padding. Empirically (`claudelog`, `project_stale_stt_testsets`): with `RS`
    **active**, fresh enumeration gives **0% isolated no-op `other` ops, 1.4× redundancy, 45 distinct
    leak dataflows**; with it commented out, **38% isolated, 8.6× redundancy, only 2 dataflows**. The
    existing `STT_6` testsets predate the effective `RS` (C4) and are massively under-covering — which
    is *why* a regen is recommended. (An earlier "require-interaction / WIN1" proposal was found
    **redundant** with `RS` and explicitly rejected.)

### 2.2 The well-formedness facts (the realizability guardrails)

| fact | line | constraint | why |
|---|---|---|---|
| `limited_inregs ≤ 2`, `limited_inaddrs ≤ 1`, `limited_ins ≤ 2`, `limited_outs ≤ 1` | 122–126 | operand-count caps per instruction | x86 instructions have bounded operands; keeps concretization realizable |
| `ld_ops`/`str_ops`/`other_ops`/`br_ops` | 117–120 | a load takes addr+mem→reg; a store takes addr+reg→mem; branch has no output; etc. | ties each `InstrType` to a legal operand signature so Stage-2 can emit real asm |
| `spo_total`/`spo_acyclic`/`committed_last` | 129–137 | program order is a total acyclic order; committed prefix precedes uncommitted | a litmus test is a straight-line sequence with a well-defined commit boundary |
| `same_state_rf` | 159 | an `rf` edge connects operands of the same `opstate` | a reaching-def must actually carry the same value |
| `rf_from_most_recent_writer` | 163 | (the **C1 fix** target) pins `rf` to the latest same-state writer | **NOT yet enforced in the shipped models** → the C1 clobber (`ALLOY_RF_LASTWRITER_BUG.md`); without it concretization can wire a consumer to a stale writer (~58% of the testset). Owner-gated. |

### 2.3 `run gen_lit … for N` — the scope (gadget size)

- **Controls:** the Alloy `run` scope bounds the number of `Instruction`/`State`/`Operand` atoms — i.e.
  the maximum gadget length and dataflow breadth.
- **Why:** with `IX0…IX5` the instruction bound is 6. The scope is the lever between "expressive enough
  for `br→load→ALU→xmit`" and "small enough to enumerate 100k instances." Larger scope = richer gadgets
  but a combinatorial blow-up; this is part of why OTB-class shapes are reachable in principle but lost
  to the `max_instances` cap in practice (Tier 2.1 + C3).

### 2.4 `alloy.max_instances`, `alloy.batch_size` (run-config)

```jsonc
"alloy": { "max_instances": 100000, "batch_size": 1000 }
```

- **Controls:** how many instances Alloy enumerates (the cap) and the batch granularity for streaming.
- **Why:** 100k is the corpus size. **The cap is itself a methodological knob with a known side
  effect:** the enumeration fills the cap with the *simplest* satisfying shapes first (direct
  `load→xmit`), so rarer shapes (the `ld→other→xm` OTB precursor) never appear even though they are SAT
  — the C3 generation gap is a `max_instances`+ordering artifact, *not* a model limit. The lesson
  (`OTB_GENERATION_GAP.md`): never infer "the model can't" from "absent in the capped enumeration" —
  force the shape with a predicate and re-run.

---

## Tier 3 — speculation realization (`speculation.*`, run-config)

```jsonc
"speculation": { "control_flow": true, "data_flow": false,
                 "branch_modes": ["mispredict_not_taken", "mispredict_taken"] }
```

| knob | default | controls | why |
|---|---|---|---|
| `control_flow` | `true` | enable branch-misprediction speculation | the Spectre-v1 primitive the defenses target |
| `data_flow` | `false` | enable data/memory speculation | off — the active contract (1.3) is branch-only; turning it on would need the `no_unresolved_mem` contract variant |
| `branch_modes` | both | how the abstract unresolved branch concretizes: predicted-not-taken-but-taken vs predicted-taken-but-not | **the two modes exercise different pipeline timing.** `taken` mode requires the BTB-force hook (Tier 5) to make the predictor go the wrong way; `not_taken` falls through. Outputs are split per mode (`testsets/<m>/<mode>/…`) because the speculative window opens differently in each — and several findings (e.g. the taken-mode load degeneracy on InvisiSpec, the 6–7× taken asymmetry D7) are mode-specific. |

---

## Tier 4 — chain interleaving (`interleave.*` + `free_pool`, run-config)

```jsonc
"interleave": { "enabled": false }       // + free_pool.reg (default 5), free_pool.mem (default 3)
```

| knob | default | controls | why |
|---|---|---|---|
| `interleave.enabled` | `false` | `parsexml.pass_interleave`: expand each base instance into `_v<k>` variants by injecting 1–2 synthetic chains into the speculative region | **the only mechanism that can build a *two-independent-source* merge** — the recon OTB / `getOldestTaint` gadget (an ALU merging two tainted loads of differing speculation status). A single Alloy instance describes ONE dataflow chain, so it structurally cannot express the merge; interleaving manufactures it by colliding an injected chain's terminal into a base instruction's *blank* operand via the shared free pool. |
| `free_pool.reg` | 5 | count of `Reg_s$fr*` free atoms | the pool from which **both** unspecified ("blank") Alloy operands **and** injected-chain operands draw at concretization — a collision in this pool is the natural cross-chain data dependency that hooks an injected load onto a base ALU's blank argument |
| `free_pool.mem` | 3 | count of `Mem_s$fr*` free atoms | same, for memory offsets |

**Why it exists at all:** the OTB target bug (A1) needs the merge shape; the default enumeration never
produces it (C3). Interleaving is the *intended* path to that shape — but note (`OTB_GENERATION_GAP.md`)
that in practice the collisions land on operands *off* the transmitter's address path, so even with
interleaving the OTB gadget is not assembled without a forcing predicate. The full mechanism and the
analysis pitfalls (base XML is pre-interleave; shared opstate ≠ rf edge; x86 SIB/`lea` parsing traps)
are documented there — **read it before re-investigating OTB.**

---

## Tier 5 — defense & probe (`gem5.*`, run-config)

This tier selects *which defense* runs and *how it is instrumented* — it does not change what a leak
is. (The hook mechanics are in [`METHODS_INSTRUMENTATION.md`](METHODS_INSTRUMENTATION.md).)

| knob | example | controls | why |
|---|---|---|---|
| `binary` / `config_script` / `cpu_type` | `/work/gem5-recon-modded/…`, `X86O3CPU` | which gem5 build + `se.py` + CPU model | one testset is run against many defenses by swapping these (recon, /work/stt, gem5-spt, the 4 amulet builds) |
| `scheme` | `2` | the defense: recon `0`=Unsafe `1`=Delay `2`=STT `3`=DoM; gem5-spt `2`→`SpectreSafeFence` | the defense under test; `0`=Unsafe is the byte-identical baseline control that proves a hit is defense-specific |
| `extra_args` | `--applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy` | per-build defense variant selection | e.g. SPT Fence vs InvisibleSpec; `Lazy` is the real implicit-flow defense (`Eager` is a disabled stub) |
| `branch_ann_enable` | `true` | turn on the BTB-force + per-branch resolve-stall annotations | **only** on `-modded`/SPT builds (vanilla rejects `--branch-ann-file`); it is what realizes the modeled mispredict (taken mode) and lets us stall a branch's resolution. Must match the build (`reference_gem5_build_hooks`). |
| `fnc_commit_stall_cycles` | `150` | hold the speculation-boundary (`first_noncommitted`) inst at the ROB head N cycles | widens the speculative window deterministically. **Proven not to be the leak cause** for A4 (identical on/off) — it is a window-widener, included precisely so we can *show* results don't hinge on it (Tier 6). |
| `allow_leaked` | (recon) | recon's `--allow_leaked` STLF flag | the "recon on" mode; relevant to the A2 STLF path |
| `caches` | `true`/`false` | classic-cache config | **`true` on a Ruby build is the D4 config bug** (port-already-connected → 100% errors reported as "0 hits"). Must be `false` on Ruby builds. |
| `sample_fraction` | `1.0` | run a fraction of the corpus | throughput knob for quick passes |
| `debug_flags` / `debug_file` | `["O3PipeView","LSQUnit"]` | which gem5 trace the checkers parse | the observation channel — `O3PipeView` (issue/complete/squash) + `LSQUnit` (execute/packet/spec-read). Adding `Commit` enabled the B2 squash-tick fix. |

---

## Tier 6 — the window sweep (`sweep.*`, run-config) — the three stall knobs

```jsonc
"sweep": { "enabled": true, "points": [0, 500, 2500], "unresolved_stall_cycles": 5000 }
//  + optional: "unresolved_points": [...], "max_grid": N
```

These are the knobs validated in `PAPER_RESULTS.md` §6 (figure F4). They move the speculative *window*
around a test without changing the defense.

| knob | role | known fact it must respect (the grounding) |
|---|---|---|
| `points` = **s_R** | per-test stall on a **resolved** branch | a near-flat plateau (27→22 in the validation) — resolved-branch timing barely moves the verdict |
| `unresolved_stall_cycles` (scalar) / `unresolved_points` (list) = **s_U** | stall a still-**unresolved** branch | **`5000` MASKS leaks** (shoves the xmit past `fnc_retire`): the validation shows `{0→27, ≥50→0}`. So `5000` is *not* a trustworthy default; sweep it small→large to *show* the masking rather than silently hide leaks. This single fact is why every slow-comm run is launched **bare** (`s_U=0`). |
| `gem5.fnc_commit_stall_cycles` = **fnc** | (Tier 5) the third stall, swept here | leak persists at `fnc=0` (16 hits) then plateaus — included to *prove* results don't hinge on the hook |
| `max_grid` = N | seeded sub-sample of the grid | dense `points` across several resolved branches is `len(points)^n_resolved × len(unresolved_points)` — it explodes; `max_grid` caps it reproducibly (the coincidence-band experiment) |

**Why a sweep at all:** a single stall value is one arbitrary point on the window axis; whether a
test leaks can depend on where the window edge falls relative to the transmitter's act. Sweeping
turns "does it leak at this one timing?" into "is the leak verdict stable across the window-stall
regime?" — and the answer's *shape* (plateau / knee / mask) is what justifies the operating point.
The hard rule (`PAPER_EXPERIMENTS.md` §5, CLAUDE.md): **report the curve as-is; a knob that flips a
labeled anchor is a finding, never a value to avoid.**

---

## Tier 7 — micro-architectural timing (`se_exp.py` env, `SIMSPECT_*`)

The fragility axis (`PAPER_RESULTS.md` §7, figure F5). These are **CPU timing parameters**, applied
through an **additive** `se_exp.py` that reads env overrides — the defense source is never touched.

| env var | gem5 param | controls | why it is the right axis |
|---|---|---|---|
| `SIMSPECT_COMMIT_IEW_DELAY` | `commitToIEWDelay` | cycles for a squash to propagate commit→IEW | **the sole driver of the A4/A5 VP↔squash race.** Stock `1` → squash wins (0 leaks); `≥2–3` → the packet beats the squash. It is the *width* of the exposure gap created by the untaint-at-resolution logic flaw. Rigorously isolated as the driver (not `squashWidth`, not the fnc hook). |
| `SIMSPECT_SQUASH_WIDTH` | `squashWidth` | ROB-unwind commit width | **NOT** the driver — it bounds only the ROB retirement, not the one-shot IQ/LSQ flush. Held at a realistic `8` to prove the race survives it. |
| `SIMSPECT_IEW_COMMIT_DELAY` | `iewToCommitDelay` | forward IEW→commit delay | swept/held to show the *forward* path alone does not cause the race |
| `SIMSPECT_BACK_COM_SIZE` / `SIMSPECT_FWD_COM_SIZE` | `back/forwardComSize` | timebuffer depths | must exceed the delays (held at 10) so the delay knobs are realizable, not clamped |
| (ceiling) | `commitToIEWDelay ≥ 5` | — | **livelocks gem5** (generic, scheme-independent A6) — the sweep is capped at 4. The livelock was also the upstream cause of the disk-full crashes (D2, now fixed with a timeout + tick cap). |

**Why these are legitimate to modify** (the full argument is `PAPER_RESULTS.md` §7): they are
*implementation* timings, not part of any defense's security argument; a correct defense must be
secure across the legal space of them; gem5's defaults are an optimistic point in that space (real HW
has higher redirect latency and *bounded* squash bandwidth gem5 idealizes as one-shot). Sweeping them
tests whether the defense's *logic* holds independent of timing — and STT/SPT's does not (F5/F6). The
change is made in config (`se_exp.py`), never in the gem5 defense source — honoring "do not mess with
gem5 on any front other than the hooks."

---

## One-screen summary

| tier | where | the knob that matters most | the finding it grounds |
|---|---|---|---|
| 1 leak spec | `*.als` | `leakage_function` (loads+branches, no stores) | why we don't find STT's store→TLB bug (correct scoping) |
| 1 leak spec | `*.als` | `prot_set_propagation` (protect produced-under-spec) | C2 const-addr over-approx (dominant false signal on *data-taint* SPT-Fence; **not** a disqualifier for STT/SpecLFB) |
| 1 leak spec | `*.als` | `tag_xm` | 100% targeted tests (§5) |
| 2 enum | `*.als` | `gen_useful_litmus` `RS` clause | kills no-op padding; C4 staleness |
| 2 enum | run-config | `max_instances` cap | C3 OTB generation gap (cap artifact, not a limit) |
| 4 interleave | run-config | `interleave.enabled` + `free_pool` | the OTB two-source merge mechanism |
| 6 window | run-config | `s_U` (`unresolved_stall_cycles`) | `5000` masks leaks → run bare; F4 |
| 7 timing | `se_exp.py` | `commitToIEWDelay` | the fragility driver; F5/F6 |
