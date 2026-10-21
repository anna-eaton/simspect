# AMuLeT vs. SimSpect: what each tool can and cannot find

*Written 2026-06-03 (session `6:invisispec`). Durable scope note for posterity —
not a transient finding. Companion to `claudelog.md`; lives in `docs/` so it
survives independently of the running log.*

---

## Why InvisiSpec is out of scope (the definitional argument) — advisor-facing

*(Added 2026-06-10. This is the principled scope boundary, stated as a category
distinction, not a difficulty plea. Read this section first.)*

**Slide figure:** `docs/scope_diagram.png` (regenerate with `python3 docs/make_scope_diagram.py`).

```
   secret ─▶ dataflow ─▶ [ TRANSMITTER ] ─▶ µarch channels ─▶ attacker observes
   operand    (taint)     load / branch       L1 tag · LRU · MSHR/TBE · L2 ·
                               │               dir · TLB · L1I · undo/cleanup
                               │                        │              (open-ended)
              ┌────────────────┘                        └────────────────┐
        SimSpect ORACLE  ✓ IN SCOPE                  AMuLeT ORACLE  (out of scope for us)
   "did the transmitter fire in the window?"   whole-µarch, DIFFERENTIAL across runs,
   channel-agnostic, single-run                per-channel + defense-specific

   transmitter-blocking defenses act at ▲       footprint-hiding defenses act at the channels
   STT · SPT · Recon · NDA · fence/delay         InvisiSpec · CleanupSpec · SpecLFB · MuonTrap
   (same security def as our oracle)             (let transmitter FIRE, hide/undo the footprint)
```

**Thesis.** SimSpect's leakage oracle is defined at the **transmitter level**: track secret
dataflow to a transmitter, then check whether that transmitter *performed its speculative
action inside the window*. The oracle is **channel-agnostic on purpose** — and that is exactly
correct for the class of defense we target.

**Why it's correct for our class.** The comprehensive Spectre defenses we evaluate — STT, SPT,
Recon, NDA, taint-tracking / delay / fence families — all define security at the **transmitter
gate**: *no instruction may execute on a secret-derived (speculatively-tainted) operand while it
is unsafe, regardless of which microarchitectural channel it would have used.* They kill the leak
at its source. So the matching oracle is "did the transmitter fire in the window?" — binary. Our
oracle and the defense's security definition are **the same definition**; that alignment is what
makes our detection sound and general.

**Why InvisiSpec is a different animal.** InvisiSpec does **not** stop the transmitter. By design
it *lets the speculative load execute* and instead tries to make its microarchitectural
**footprint** invisible (speculative buffer; no coherence-visible install until the visibility
point). Its security property is therefore **not** "the transmitter didn't occur" — *the
transmitter occurs, intentionally* — it is "the speculative access leaves no observable
secret-dependent state in any µarch structure." So our oracle is **type-mismatched, not merely
under-powered**: applied to InvisiSpec it would report "the transmitter occurred" on essentially
every test — which is **true and intended**, not a bug. The distinction between a *working* and a
*broken* InvisiSpec lives entirely in the channel/footprint, which our oracle deliberately
abstracts away. A transmitter-occurrence oracle structurally cannot judge a footprint-hiding
defense.

**Testing InvisiSpec is a different oracle, for three independent reasons.**
1. **The channel set is open-ended and defense-specific.** A speculative access can perturb L1
   tags, replacement/LRU metadata, MSHR/TBE occupancy, L2, the coherence directory, the TLB, the
   L1I, the prefetcher, and the defense's own undo machinery. That set is not fixed — it depends
   on the microarchitecture and the defense — so there is no single channel-independent observer;
   you hand-build one per (defense × structure). **Empirically proven here:** every AMuLeT bug we
   reproduced needed its *own* bespoke watcher — UV1 a Ruby compound-eviction watcher, UV2 a
   contention/stall watcher, KV1 an I-fetch watcher, UV4/unXpec a cleanup-event correlator. N bugs
   → N instrumentation efforts, none reusing the general pipeline.
2. **It is a final-state / differential property, not an in-window occurrence.** Eviction, residue,
   over-clean, "the cleanup footprint differs by hit/miss" — these are *state left behind* or *what
   differs between two runs*. SimSpect is single-run, in-window, occurrence-based by construction.
   (By our own methodology a final-state diff is *confirmation*, not *detection*.)
3. **Several of the bugs aren't even data transmitters.** We generate load/branch *data*
   transmitters; KV1 is an instruction fetch, KV3 a store→TLB walk — outside the transmitter
   vocabulary, independent of the oracle issue.

**There is a right tool for the other side.** Channel/footprint/invisibility violations are
exactly what AMuLeT (and Revizor-style contract differential testing) is built for: observe the
full µarch trace, compare against a leakage contract. SimSpect and AMuLeT are **complementary by
construction** — SimSpect catches transmitter-level violations in *transmitter-blocking* defenses;
AMuLeT catches footprint violations in *invisible/undo* defenses. Re-instrumenting every InvisiSpec
channel inside SimSpect would be reimplementing AMuLeT, worse.

**Pre-empting the obvious objection.** *"But you demonstrated UV1/KV1/UV4/unXpec."* That **supports**
the boundary. Each was a **forced controlled gadget + a bespoke per-channel watcher**, built to
*characterize* the defenses — not a detection produced by the SimSpect pipeline. The general oracle
never surfaced any of them; each required stepping outside the methodology with custom
instrumentation. That is the cost of going out of scope, demonstrated repeatedly.

**One-sentence version.** *SimSpect verifies that the transmitter never fires on protected data;
InvisiSpec lets the transmitter fire and promises you won't see it — so testing InvisiSpec means
auditing every microarchitectural surface that firing could mark, which is a whole-µarch,
differential, defense-specific oracle (AMuLeT's job), not the transmitter-occurrence oracle that
matches the comprehensive transmitter-blocking defenses we target.*

**Crisp scope statement.**
- **In scope** — defenses that enforce security at the *transmitter/execution gate*: "no
  transmitter executes on a secret-derived operand during the speculative window" (STT, SPT, Recon,
  NDA, delay/fence). Oracle: dataflow-to-transmitter + transmitter-occurrence-in-window.
  Channel-agnostic *because the defense is*.
- **Out of scope** — defenses that *permit* the transmitter and instead hide/undo its µarch
  footprint (InvisiSpec, CleanupSpec, SpecLFB-style invisibility, MuonTrap-style). Correctness = a
  per-channel final-state property → AMuLeT's domain.

---

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
