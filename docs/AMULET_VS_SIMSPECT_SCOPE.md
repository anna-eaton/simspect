# AMuLeT vs. SimSpect: what each tool can and cannot find

*Written 2026-06-03 (session `6:invisispec`). Durable scope note for posterity —
not a transient finding. Companion to `claudelog.md`; lives in `docs/` so it
survives independently of the running log.*

## TL;DR

SimSpect and AMuLeT test secure-speculation defenses in **different leakage
models** and therefore find **different bug classes**. They are complementary,
not redundant.

- **SimSpect** asks: *does a chosen **transmitter** (a specific load / branch /
  ALU op) perform its own observable action **inside the speculative window**?*
  It enumerates **taint/speculation dataflow** gadgets with Alloy and observes
  the **transmitter's own access** through the gem5 **O3PipeView + LSQUnit**
  instruction trace.
- **AMuLeT** asks: *do two inputs to a **random** program produce **different
  µarch state** in a way a leakage **contract** forbids?* It observes the
  **full µarch trace** — cache **tags/evictions**, **MSHRs**, **L1I**, **TLB** —
  and compares against a contract (Revizor-style differential fuzzing).

The bugs AMuLeT reports in these defenses are all **collateral side-effects on
shared µarch resources** (cache *eviction*, MSHR *contention*, I-cache, TLB) —
**outside SimSpect's observation channel and test-generation scope.** SimSpect,
in turn, targets *transmitter-in-window* races (e.g. the visibility-point↔squash
race) that AMuLeT's random search does not aim at.

> The `/work/amulet/amulet-gem5-*_AE-v1.1` builds **are** the AMuLeT
> artifact-evaluation packages (e.g. InvisiSpec's README is "InvisiSpec-1.0";
> AMuLeT added a `apply_spec_eviction_patch` toggle). So the AMuLeT bugs are
> reproducible *in these exact builds* — with AMuLeT, not with SimSpect.

Reference: Fu et al., *AMuLeT: Automated Design-Time Testing of Secure
Speculation Countermeasures*, ASPLOS '25 (`amulet.pdf` in repo root). InvisiSpec:
Yan et al., MICRO '18 (`InvisiSpec_*.pdf`).

---

## The two leakage models side by side

| | **SimSpect** | **AMuLeT** |
|---|---|---|
| Test generation | Alloy enumerates taint/speculation **dataflow** gadgets; one **chosen transmitter** per test | Revizor-style **random** programs + multiple **inputs** |
| Leakage definition | Transmitter's observable action falls in `lc_retire < signal < fnc_retire` with guarding branches unresolved | µarch trace **differs across inputs** beyond what the **contract** (CT-SEQ / CT-COND) allows |
| What's observed | The **transmitter's own** access: O3PipeView + **LSQUnit** trace (load execute / packet / spec-read / expose tick; branch redirect; div fault) | **Full µarch trace**: cache **tags + evictions**, **MSHRs**, **L1I**, **TLB** |
| Comparison | Single run vs. the **model's** window prediction (discrepancy = signal) | **Differential** across inputs vs. a **contract** |
| Sweet spot | *Targeted* gadget reachability + **timing races** in the speculative window | *Emergent* leaks via shared-resource side effects; black-box coverage |
| Blind spot | Collateral state changes that aren't the transmitter's own access (evictions of **other** lines, MSHR/I-cache/TLB); needs cache **occupancy** pressure it can't generate | A specific targeted gadget random search may not hit; contract must encode the channel |

---

## The bugs AMuLeT found (and why they occur)

AMuLeT reports **3 known + 6 unknown** bugs across InvisiSpec, CleanupSpec, STT,
SpecLFB. The unifying root cause: **each defense defined "safe/invisible" too
narrowly** — it neutralized the *intended* channel (e.g. coherence state) but the
speculative operation still perturbs **another shared µarch resource** that is
observable.

### InvisiSpec

1. **Speculative L1D-cache eviction (UNKNOWN / headline).** A spec load
   (`SPEC_LD` / Spec-GetS) that **misses on a full cache set** triggers an
   `L1_Replacement` — it **evicts a conflicting line** while still speculative.
   The eviction is observable → leaks the spec load's address, breaking
   invisibility even **single-threaded**.
   - **Why:** invisibility was implemented at the **coherence-state** layer
     (Spec-GetS doesn't change directory/coherence state) but **not** at the
     **allocation/replacement** layer — the spec load still allocates an L1 line
     and evicts to make room. AMuLeT paper §4.5, Fig. 5, Listings 1–2.
   - **In this build:** `src/mem/protocol/MESI_Two_Level-L1cache.sm:514` (and
     L2 `…-L2cache.sm:386`) carry AMuLeT's fix as a toggle:
     `if (L1Dcache.cacheAvail(addr) || (in_msg.Type == SPEC_LD && apply_spec_eviction_patch))`.
     `apply_spec_eviction_patch := "True"` is the **default (patched)**; the bug
     is reproduced by setting it **False** (`configs/ruby/MESI_Two_Level.py`
     wires `options.apply_spec_eviction_patch`).
2. **Single-threaded speculative-interference variant (UNKNOWN, "UV2").** With
   few MSHRs (2 vs default 256), spec loads **contend for MSHRs**; the contention
   is observable **from the same core** — no SMT/multithread needed (a stronger
   form of the speculative-interference attack [Behnia et al.]).
   - **Why:** spec loads consume a **shared resource (MSHRs)** whose occupancy
     leaks via timing.
3. **L1I-cache speculative fetches (KNOWN limitation, "KV1").** Spec instruction
   fetches change L1I state; InvisiSpec explicitly does not protect the I-cache.

### Other defenses (for completeness)

- **STT:** tainted **speculative stores** speculatively access the **TLB** → TLB
  state leak (previously shown by DOLMA — **known**).
- **CleanupSpec:** leaks of speculatively-accessed addresses (**unXpec**, known)
  + a **lack of cleanup** on some paths (**unknown**).
- **SpecLFB:** the open-source implementation is **insecure** (**unknown**).

**Pattern:** cache **replacement/eviction**, **MSHR** contention, **L1I**,
**TLB** — all *shared µarch resources* perturbed as a *collateral* effect of the
speculative operation, distinct from the transmitter's "intended" channel.

### Per-bug scope determination (does SimSpect's model reach it?)

The deciding principle: **SimSpect can see a leak iff it is the transmitter's
*own* access occurring *inside* the speculative window**, visible in the
O3PipeView+LSQUnit instruction trace. It is blind when the leak is (i) collateral
state on another resource, (ii) post-squash residue / cleanup correctness, or
(iii) on a channel other than the D-cache line-fill the transmitter performs.

| Bug | Defense | Leak channel | Stimulus needed | SimSpect observes? | Verdict |
|---|---|---|---|---|---|
| UV1 — L1D eviction | InvisiSpec | spec load **evicts** a conflicting line | full cache set | no (Ruby cache) | **OUT** |
| UV2 — interference | InvisiSpec | **MSHR** contention (timing) | few MSHRs (2) | no (MSHR/debug-log) | **OUT** |
| KV1 — I-fetch | InvisiSpec | **L1I** state | — | no (I-cache) | **OUT** |
| UV3 — store not cleaned | CleanupSpec | **post-squash L1D residue** of a spec store | spec store | no (final cache; install is *expected*) | **OUT** |
| UV4 — split not cleaned | CleanupSpec | post-squash L1D residue (split req) | cacheline-crossing access | no | **OUT** |
| UV5 — too much cleaning | CleanupSpec | cleanup wrongly **evicts** a non-spec line | NSL+SL reordered, same line | no (final cache, differential) | **OUT** |
| KV3 — store→TLB | STT | tainted spec store installs a **D-TLB** entry | tainted spec store + multi-page | no (TLB; store transmitter) | **OUT** |
| **UV6 — first load unprotected** | **SpecLFB** | transmitter **load installs a secret-dependent line in the spec window** | Spectre-v1 single load | **YES** (LSQUnit/pipeview) | **IN SCOPE** |

**The one exception — SpecLFB UV6.** SpecLFB is *supposed to* delay/prevent the
speculative load's cache install, but an undocumented optimization clears
protection for the **first speculative load in the LSQ** (`isReallyUnsafe`
cleared), so a Spectre-v1 single load **installs a secret-dependent line into the
cache while speculative** (AMuLeT §4.7, Fig. 8). That is exactly `check_ld`'s
criterion — the transmitter load's *own* cache touch in-window — and the stimulus
(`CMP/JNE` mispredict → `MOV RAX,[R14+secret]`) is the Spectre-v1 shape the Alloy
model already enumerates. AMuLeT detects it via a cache-state diff; SimSpect would
detect the *same event* via the in-window cache reach. **Caveat:** SpecLFB is the
one amulet build **not yet hooked** for SimSpect (newer gem5 base; see
`project_amulet_hooks`), so it is in-scope *methodologically* but needs the
BTB-force / resolve-stall / LSQUnit-trace port before SimSpect can run it.

**Why CleanupSpec installs are NOT in scope even though they're cache line-fills:**
CleanupSpec *allows* the in-window install **by design** and cleans it up on
squash. So the in-window install isn't the bug (SimSpect's `check_ld` would
false-positive on every spec load); the bug is whether the **final** cache state
was correctly restored — a post-squash, end-of-test cache-snapshot question only
AMuLeT's differential answers. Contrast SpecLFB, which is supposed to *prevent*
the install — there the in-window install *is* the bug.

---

## Why SimSpect (today) cannot find them

Two independent gaps, illustrated with the InvisiSpec eviction bug:

1. **Wrong observation channel.** Evictions, MSHR occupancy, L1I and TLB state
   live in the **Ruby cache/coherence controllers** and are **invisible to
   O3PipeView + LSQUnit** (the instruction-pipeline trace SimSpect parses in
   `STAGE3_gem5/gem5_common.py`). SimSpect's load checkers key on the
   **transmitter load's own** cache touch, never on the eviction of *another*
   line. The InvisiSpec checker added this session
   (`STAGE3_gem5/check_ld_invisispec.py`) **explicitly assumes** the Spec-GetS is
   invisible — the very assumption the AMuLeT bug violates.

2. **Wrong test stimulus.** The eviction only fires on a **full cache set** + a
   conflicting spec load. SimSpect's Alloy model enumerates taint/speculation
   **dataflow**, not cache-set **occupancy** — its tiny litmus tests never fill a
   set (AMuLeT had to drop to a **2-way** L1D and **2** MSHRs to amplify it).
   SimSpect's generator cannot produce the contention gadget.

3. **No input-differential.** AMuLeT compares two inputs' µarch traces against a
   contract; SimSpect checks one program against the model's window prediction.

| AMuLeT bug | Observation needed | SimSpect today |
|---|---|---|
| L1D speculative eviction | Ruby `L1_Replacement` events, correlated to the spec load | ❌ pipeview/LSQUnit can't see evictions |
| MSHR interference (UV2) | timing/contention diff over inputs | ❌ no differential, no MSHR trace |
| L1I / TLB | L1I / TLB state in the trace | ❌ observes neither |

---

## What SimSpect *does* cover that AMuLeT doesn't

SimSpect targets **transmitter-in-the-speculative-window** questions, including
**timing races** that random fuzzing is unlikely to land:

- The **visibility-point ↔ squash race** class — e.g. STT/SPT, where a genuinely
  protected transmitter is released *at branch resolution* and a packet beats the
  squash by 1–2 cycles. SimSpect reproduces these deterministically with the
  resolve-stall / fnc-commit-stall hooks.
- For **InvisiSpec specifically**, the analogous question is whether the
  **expose/validate** (the *visibility-point* cache access, `lsq_unit_impl.hh`
  `exposeLoads()` → send at `:1280`, gated by `readyToExpose()` /
  `updateVisibleState():1042`) ever fires **before** its guarding branch resolves.
  `check_ld_invisispec.py` tests exactly this. Early observation: on STT_6 ld
  tests the wrong-path USLs are **squashed before any expose** (`never_exposed_
  squashed`, 0 hits) — the defense defers correctly. This is a legitimate,
  distinct result; it is **not** one of AMuLeT's bugs, and AMuLeT does not target
  it.

So: a transmitter's **own** observable action and its **timing** = SimSpect;
**collateral shared-resource** state (evictions/MSHR/I-cache/TLB) = AMuLeT.

---

## If we wanted SimSpect to find AMuLeT-class bugs (cost)

Reproducing AMuLeT's eviction finding inside SimSpect would require **rebuilding
AMuLeT's methodology**:

1. **Cache-event observation** — a checker keying on Ruby `L1_Replacement`
   (a new debug-flag trace), correlating an eviction to an in-flight `SPEC_LD`.
2. **Cache-pressure test generation** — programs that fill an L1 set then issue a
   conflicting spec load; outside the Alloy taint-dataflow model (a different
   generator), and/or small-cache configs (2-way, 2 MSHRs).
3. **Input-differential** — compare two inputs' cache states against a contract.

Given the artifact builds already ship with the toggle, the pragmatic path for
the **collateral-cache** bugs is **AMuLeT itself** (flip
`apply_spec_eviction_patch=False`, run its fuzzer), keeping SimSpect for the
targeted transmitter-window / timing-race questions.

---

## Pointers

- Paper: `amulet.pdf` (root) — InvisiSpec eviction bug §4.5, Fig. 5, Listings 1–2.
- Build (AMuLeT artifact): `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1`
  - eviction bug + toggle: `src/mem/protocol/MESI_Two_Level-L1cache.sm:514`,
    `…-L2cache.sm:386`; default `apply_spec_eviction_patch := "True"`.
  - visibility point: `src/cpu/o3/lsq_unit_impl.hh:1042` (`updateVisibleState`),
    expose send `:1280`; spec read `src/cpu/o3/lsq_unit.hh:855`.
- SimSpect InvisiSpec support added this session:
  `STAGE3_gem5/check_ld_invisispec.py`, `parse_lsq` `expose_tick` in
  `STAGE3_gem5/gem5_common.py`, run at `results/STT_6_invisispec/`.
- Related memory: `project_invisispec`, `reference_gem5_build_hooks`,
  `project_amulet_hooks`. claudelog: 2026-06-03 InvisiSpec entries.
