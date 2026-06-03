# SimSpect — Results

*Compiled 2026-06-03. Every number in this document is sourced from artifacts already on
disk (`results/…`, `bug/…`, `/work/amulet-repo/…`) or from a dated `claudelog.md` entry; the
provenance for each figure is in the comment header of `paper_figures/make_paper_figures.py`,
and the per-finding proof is cross-referenced to `bug/BUG_TAXONOMY.md` (the A/B/C/D ids used
throughout). Figures live in `paper_figures/` with **three candidate renderings each**
(`*_a/_b/_c.png`) — pick one per slot.*

**Companion methods docs** (written as standalone alternatives you can diff against your own):
- [`METHODS_LEAKAGE_KNOBS.md`](METHODS_LEAKAGE_KNOBS.md) — every knob in the leakage prompting.
- [`METHODS_CONCRETIZATION.md`](METHODS_CONCRETIZATION.md) — the concretization & enumeration phase, grounded in why each decision exists.
- [`METHODS_INSTRUMENTATION.md`](METHODS_INSTRUMENTATION.md) — the gem5 hook / instrumentation layer.

---

## 0. TL;DR

SimSpect generates **litmus tests for speculative-execution defenses** (Alloy enumerates
taint/speculation dataflow where a chosen transmitter is provably in the speculative
protection set) and uses **gem5 as ground truth** (does that transmitter actually act inside
the speculative window?). A discrepancy — gem5 permits what the model forbids — is the signal.

Headline results:

| Defense (build) | What SimSpect found | Status |
|---|---|---|
| **Recon-STT** (`/work/gem5-recon-modded`) | **STL / store-to-load-forward taint bypass** (A2) — caught **live** from generator output (`inst-014912`); the *only* confirmed real leak among 184 ld hits. Plus **OTB / `getOldestTaint`** (A1), real but only hand-crafted (generator can't reach it yet, §6). | A2 ✅ live · A1 📝 |
| **STT** (`/work/stt`) | **Visibility-point ↔ squash race** (A4): the defense un-taints at branch *resolution* without excluding the to-be-squashed wrong path → a wrong-path tainted load touches cache in the gap. **Does NOT find the AMuLeT store→TLB bug — by design** (§3). | A4 ✅ (timing-regime) |
| **SPT-Fence** (`/work/gem5-spt`) | The **same** VP↔squash race (A5) — it is **bad logic shared with STT**, not an independent SPT bug. | A5 ⏳ open |
| **SpecLFB** (AMuLeT build) | The **one AMuLeT load bug in SimSpect's scope** — UV6, first-spec-load-unprotected — **demonstrated**: 68/300 unsafe speculative loads access cache in-window when SpecLFB should have delayed them (`isCUSL=1, isUnsafe=0`), same bar as STT A4 / SPT A5. A full secret-*recovery* PoC is the only thing still pending stimulus (§4). | UV6 ✅ |

Two cross-cutting messages:

1. **We are a different scope from AMuLeT and that is the point** (§3). AMuLeT finds *collateral
   shared-resource* leaks (cache eviction, MSHR, L1I, TLB) via input-differential fuzzing;
   SimSpect finds *transmitter-in-window timing races* via targeted dataflow enumeration. Of the
   8 bugs AMuLeT reports on these defenses, exactly **1 (SpecLFB UV6)** is in SimSpect's leakage
   model — and SimSpect **demonstrates it** (§4): the defense fails to delay the first unsafe
   speculative load, which then accesses cache in-window (68/300).

2. **Our test targeting is categorically better** (§5). Of AMuLeT's 500 random STT tests, only
   **85 (17%)** even contain a speculative transmitter gadget that can leak; the other 83% cannot
   leak by construction. **100%** of SimSpect's 100,000 tests do, because each is enumerated *to*
   place a transmitter in the protection set (`tag_xm`).

The **timing-window** and **fragility** sweeps (§5–6) are deliberately modifying micro-architectural
*timing*, not defense logic — and §6 argues why that is not only allowed but necessary: a defense
whose security depends on gem5's optimistic default timing is broken.

The **efficiency comparison to AMuLeT is now measured** (§8): on the SpecLFB build, SimSpect flags the
UV6 insecurity in **6.5× fewer tests** (first at test #6 vs #39) at **~7× the hit density** (23% vs
3.3%), and — isolating *just the gem5 time* (excluding our `as`+`ld` build and the O3PipeView
*measurement* trace) — the **gem5 simulation cost is comparable** (0.092 vs 0.057 s/test). So per-test
gem5 work is the same; SimSpect's targeting means **~6.5× less total simulation to reach the bug**.

---

## 1. The framework — and what counts as a result

```
STAGE1_alloy   Alloy model (.als) ─java─▶ inst-*.xml      (one XML per candidate leak instance)
STAGE2_compile  XML ─parsexml.py─▶ inst-*.ll ─llc/clang─▶ inst-*.s + inst-*.ann.json
STAGE3_gem5    .s + .ann.json ─gem5 O3PipeView/LSQUnit─▶ window-results.json   (leak / no-leak)
```

**The result is a bug in the gem5 defense** — a real microarchitectural weakness where the defense
lets a speculative transmitter act inside the window it claims to close. That is what the rest of this
document is about (§2 onward, Table F9). gem5 is the ground truth; a confirmed discrepancy is a real
defense bug.

Everything else a run produces — a load whose address the *model* over-conservatively flagged but that
isn't actually secret-dependent, or a measurement that scored too early — is **not a result; it is
scaffolding.** Those cases come from known, fixable issues in *our own* generator/checker (model
over-approximation, a stale pre-fix testset, an early-tick checker), and the per-run `diagnostics/`
exist for **one reason: to bucket those known causes so we don't have to re-run the whole 100k corpus
to re-confirm them.** A clean re-generation with the model fixes applied would simply not emit them.
So we present the **gem5 bugs** as the findings and keep the generation/measurement bookkeeping out of
the way (it is summarized once, as an appendix, §9). The standing rule still holds — a hit is only
called a real defense bug after it clears those known causes under a faithful, stall-injected rerun —
but that filtering is method, not result.

---

## 2. The bugs, by defense

> **Table F9 — every defense bug, grouped by defense** (`F9_bug_table.png`; full LaTeX in
> `paper_figures/figures.tex`, Table 1). The one-page master list: for each defense, every known
> speculative-execution bug, **where it was first known from**, **which tool exhibits it**
> (SimSpect / AMuLeT / both), whether it is in SimSpect's leakage model, and the verdict. Read this
> first — the prose below walks the rows that are SimSpect's.

**Confirmed gem5 defense bugs (the result).** Post-scaffolding (real-leak survivors only):

| defense | gem5 bug | how it was found | count / status |
|---|---|---|---|
| Recon-STT | **STL/SLF** taint-check bypass (A2) | SimSpect, **live from generator output** | 1 confirmed (`inst-014912`); the recon **OTB** (A1) is real but generator-unreachable (hand-crafted) |
| STT | **VP↔squash race** (A4) | SimSpect, live (timing-regime) | **≈23,966** race instances (19,845 confirmed + 4,122 NEW re-attributing to the same race); **0 at stock** (defense holds) |
| SPT-Fence | **same VP↔squash race** (A5) | SimSpect, live (timing-regime) | shared with STT; the genuine signal among the slow-comm survivors (no *independent* SPT bug) |
| SpecLFB | **UV6** first-load unprotected | SimSpect (demo) + AMuLeT | demonstrated, 68/300 (§4) |

These are the rows of Table F9 that are SimSpect's; §2.1–2.3 below walk their mechanisms. The
confirmed bugs fall into **three mechanism classes**:

1. **Taint-tracker logic errors** — recon's `getOldestTaint` records the *oldest* (not youngest)
   taint source, so it frees a still-speculative taint early [A1]; and the LSQ store-forward path
   returns `NoFault` *before* the taint check ever runs [A2]. Deterministic logic bugs.
2. **The visibility-point↔squash timing race** — STT *and* SPT-Fence both clear protection at branch
   **resolution** without excluding the instruction that is itself on the to-be-squashed wrong path
   [A4/A5]. One shared logic flaw across two independent defenses; its *exposure window* is sized by
   squash-propagation latency (`commitToIEWDelay`), so it is a timing-regime bug (§7).
3. **The unprotected-first-load exemption** — SpecLFB skips its delay for the first speculative load
   in the LSQ [UV6]. Deterministic.

Class (2) is the headline: the *same* "untaint-at-resolution, no squashed-path guard" mistake appears
in two separately-authored defenses, which is exactly the kind of cross-defense design error a
*targeted* generator surfaces and a random fuzzer is unlikely to isolate.

> *Scaffolding view (appendix).* How the raw hits filter down to those counts — the model
> over-approximation and checker artifacts that a clean re-run would eliminate — is **Figure F1**
> (`F1_attribution_{a,b,c}.png`, a per-run bucket drill-down / funnel / scoreboard) and **§9**. It is
> method, not result; e.g. SPT-Fence slow-comm's ~77k raw hits are ~95% model over-approximation
> (const-addr/rf-clobber), leaving the A5 race as the only real signal. We keep it out of the way here.

### 2.1 Recon — two bugs: OTB and STL

Recon's gem5 (`/work/gem5-recon[-modded]`, `--scheme=2` = its STT mode) has two taint-tracking
defects. Both are documented in full in [`reconresults.md`](reconresults.md); the mechanism
schematics are **figure F7** (`F7_recon_bugs.png`).

**A1 — OTB (`getOldestTaint` keeps the wrong source).** An ALU op with two tainted sources (an
older one whose branch resolves first, a younger one still speculative) calls
`TaintTracker::getOldestTaint`, which records only the **oldest** seqNum as the dest's taint
(`src/cpu/o3/secure_scheme/taint_tracker.cc:119-131`). When the older source's branch resolves,
`freeTaints()` drops the dest taint even though the younger source is still speculative → the
transmitter reads a secret-dependent address that taint-tracking now thinks is clean. The fix is
to track the **youngest** (or all) sources. This is a **real** defense bug — but it is currently
only demonstrable **hand-crafted** (`oldest_taint_bug/…inst-oldest-taint-bug.s`, pipeview shows
the xmit `ic` = issued+completed in the spec window): the generator does not emit the precursor
shape (`ld → other → xm`). That gap is **C3** (§6), and it is an *enumeration cap* artifact, not a
model limitation.

**A2 — STL / SLF (store-to-load forwarding bypasses the taint check) — "the big unknown."** When a
speculative load's address matches a prior in-flight store, the LSQ `read()` forwards the store
data and returns `NoFault` (`src/cpu/o3/lsq_unit.cc` ~line 2030) **before** ever reaching the STT
taint check (~line 2090). The tainted load completes — marked **ready-within-ROB** — inside the
speculative window, with **no cache packet**. This is the one bug SimSpect caught **live from
generator output**: `inst-014912` in `results/Recon_6__20260602_122016` is the only real leak
among that run's 184 ld hits (the other 183 are the checker false positive B1). It is the strongest
result in the project: a real, previously-uncatalogued defense bug surfaced *automatically* by the
pipeline, not hand-built.

> **The correct leak bar came from this bug.** A2 completes *without touching cache* (store-forward),
> so a "did it reach the cache?" test misses it. The leak criterion is therefore **"data obtained
> (completes) before squash while tainted+spec," NOT "sent a cache packet"** — now the
> `store_forward`/data-obtained gate in `check_ld` (B1 fix). The 183 checker FPs were loads that
> `check_ld` scored at the *Executing load* tick but which were bounced to `delay_unit` and
> squashed *without completing* — never a leak.

### 2.2 STT — the timing-race bug, and the store bug we *correctly* do not find

**A4 — the visibility-point ↔ squash race (the "resolved-untaint + squash race", bad logic).**
This is **figure F6** (`F6_vp_squash_race.png`). STT roots a load's taint in
`isAccess() && !isUnsquashable()` and sets `isUnsquashable ⟺ isPrevBrsResolved()`
(`rob_impl.hh`). The instant the controlling mispredict **resolves** (the visibility point),
`isPrevBrsResolved` propagates to the *younger, wrong-path* instructions → the producer load
becomes "unsquashable" → its taint drops → the transmitter's address is now "clean" → it re-issues
and **touches the cache in the gap before the squash drains the LSQ**.

The flaw is **logical, not merely timing**: STT clears protection at branch resolution *with no
guard excluding instructions that are themselves on the to-be-squashed path*. The micro-arch
timing knob `commitToIEWDelay` only sets the *width* of the exposure gap (stock = 1 cyc, squash
wins; ≥ 2–3 cyc, the packet wins). It was rigorously isolated (`claudelog` 2026-06-02 09:30/10:15):
not a checker FP (cache-reach = real packet), not model over-approx (XML 231/231 `addr_from_load`),
not the `fnc` hook (identical on/off), not `squashWidth`. Representative example self-contained at
`bug/stt_slowcomm_vp_squash_race/` (`inst-047231`).

Scale: at stock timing, **0 leaks** (`results/experiments/slow_comm_squash1/sample_stock` 0/600
both modes; STT_6 sttbuild 0 across 11,652 ld + 4,348 br_x per mode). Under the slow-comm regime,
the full corpus gives **19,845 real VP-squash-race hits** + 21 checker FP (auto-bucketed,
`stt_slowcomm_full/diagnostics/buckets/summary.json`).

**Why SimSpect does *not* find STT's store→TLB bug — and why that is correct.** AMuLeT reports a
known STT leak (their KV3, originally DOLMA): a tainted *speculative store* still performs its
address translation, installing a secret-dependent **D-TLB** entry. SimSpect does not find it, for
two precise and *intentional* reasons:

1. **The leakage model has no store transmitter.** `STT_6.als:328`
   `leakage_function = Loads.inaddr + (Branchxs).inreg` — the transmitter operands the model can
   ever tag are a **load's address** and an **xmit-branch's input register**. Stores
   (`TStore`) are never a transmitter, and `Otherxs.inreg` is commented out (line 327). So **by
   construction** no generated test targets a store. This matches STT's own contract: STT protects
   the data a *load/branch* transmitter would expose; the store-address-translation TLB channel is
   a known, separately-named (DOLMA-class) collateral leak that STT does not claim to stop.
2. **The observation channel cannot see it.** The TLB lives outside the O3PipeView + LSQUnit
   instruction trace SimSpect parses (`gem5_common.py`); a store's TLB install is not the
   transmitter's own cache access.

So "we don't find the store bug" is **correct scoping**, not a miss — it is out of STT's transmitter
contract *and* out of our observation channel. What SimSpect finds instead are the load/branch
weaknesses that *are* in scope: the A4 timing race and (on recon-STT) the A2/A1 taint-tracker bugs.

> **STT's branch channel, for completeness.** STT's implicit-channel (branch) defense is
> *structurally* non-functional in the upstream source (A3 in `results.md`: `hasImplicitFlow` is
> computed but never fed into `isArgsTainted`; even if fixed it only fires for already-explicitly-
> tainted control insts). But the **live** br_x "leaks" we saw were the checker bug **B2** (scoring
> the resolve tick, not the squash tick), now fixed; STT's branch defense actually *held* under the
> sweep stall. So A3 is a real *source-level* gap we have not yet demonstrated as a live generated
> leak — flagged, not over-claimed.

### 2.3 SPT-Fence — the same bad logic (not a new bug)

**A5 — SPT-Fence exhibits the *same* VP↔squash race as STT.** The Fence gate is
`lsq_unit_impl.hh:1180 fenceDelay = isAddrTainted()`, lifted at the visibility point. Shape:
`pc0` mispredict branch → `pc1` speculative load (taints `%rax`) → `pc2` xmit load (address
tainted → genuinely fenced). At branch resolution the fence lifts and the wrong-path xmit sends a
cache packet **~2 cycles before** the squash drains (`claudelog` 2026-06-02 23:30/23:55; verified
`inst-000005`: mispredict resolves @2945500, packet @2946500, squash @2947500). This is **figure
F6** again — STT and SPT share one logic flaw.

It is **not an independent SPT defense bug**, and the path to that conclusion is itself a result:
the slow-comm Fence run produces ~77k ld hits, but auto-bucketing
(`spt_slowcomm_fence/diagnostics/buckets/summary.json`) attributes **67,297 to const-addr
over-approximation (C2)** + **5,503 to rf-clobber concretization (C1)** + 358 non-spec co-transmit;
the residual `NEW` (4,397) contains the genuine post-mispredict Spectre-v1 shapes (an earlier
manual pass identified **~983** of them, 80/80 sampled sent a real pre-squash packet —
`claudelog` 2026-06-02). Those ~983 are the A5 race, same class as A4. Two earlier wrong turns were
corrected on the way (it is **not** "zero-init prologue untaints shadowL1" — shadowL1 is OFF — and
**not** a realizability gap; `claudelog` 22:40 → 23:30). Net: **no independent SPT-Fence bug; the
only real signal is the shared race.**

---

## 3. SimSpect vs AMuLeT — different leakage models, complementary scope

> **Figure F2 — scope.** Three candidates:
> - **F2a** `F2_scope_a.png` — the 8 AMuLeT-reported bugs as an IN/OUT matrix (defense, channel,
>   reason). 1 of 8 in scope.
> - **F2b** `F2_scope_b.png` — AMuLeT bugs grouped by **leakage channel**, shaded by which tool
>   observes it (only the transmitter's own D-cache line-fill is SimSpect's).
> - **F2c** `F2_scope_c.png` — a 2×2 quadrant (observation channel × comparison method) placing
>   each tool and each bug.
>
> Source: `docs/AMULET_VS_SIMSPECT_SCOPE.md` (the durable scope note, with paper §/figure citations).

The two tools ask different questions:

| | **SimSpect** | **AMuLeT** (ASPLOS'25) |
|---|---|---|
| test generation | Alloy enumerates taint/speculation **dataflow**; one **chosen transmitter** per test | Revizor-style **random** programs + multiple **inputs** |
| leak definition | the transmitter's **own** action falls in `lc_retire < signal < fnc_retire`, guards unresolved | µarch trace **differs across inputs** beyond the **contract** (CT-SEQ/CT-COND) |
| observed | O3PipeView + **LSQUnit** (the transmitter's load/branch/div) | **full µarch**: cache tags + **evictions**, **MSHRs**, **L1I**, **TLB** |
| sweet spot | *targeted* gadget reachability + **timing races** in the window | *emergent* collateral-resource leaks; black-box coverage |

Every bug AMuLeT reports on these defenses is a **collateral shared-resource** leak — a spec
operation perturbing a resource *other than* the transmitter's intended channel:

| bug | defense | channel | in SimSpect's model? |
|---|---|---|---|
| UV1 | InvisiSpec | spec-load **L1D eviction** of another line | OUT — Ruby eviction, not a transmitter access |
| UV2 | InvisiSpec | **MSHR** contention (single-thread) | OUT — needs input-differential + MSHR trace |
| KV1 | InvisiSpec | **L1I** spec fetch | OUT — I-cache state |
| UV3–5 | CleanupSpec | **post-squash L1D residue** | OUT — install is by-design; final-state diff |
| KV3 | STT | tainted spec **store → D-TLB** | OUT — store transmitter + TLB (§2.2) |
| **UV6** | **SpecLFB** | **first spec load installs a line** | **IN** — the transmitter's own in-window cache touch |

SimSpect is blind to the OUT rows on two independent axes: **wrong observation channel** (evictions/
MSHR/L1I/TLB live in the Ruby controllers, invisible to the pipeline trace) and **wrong stimulus**
(the bugs need cache-set *occupancy* pressure; Alloy enumerates taint *dataflow*, and AMuLeT had to
drop to a 2-way L1D / 2 MSHRs to amplify them). That is not a defect to fix — it is the boundary
between the two methods. Conversely, AMuLeT's random differential search does not *target* the
transmitter-in-window timing races (A4/A5) that SimSpect reproduces deterministically with the
resolve-stall / fnc / commit-latency hooks.

**The one overlap — SpecLFB UV6 (their one load-defense bug in our scope).** SpecLFB is *supposed*
to delay the speculative load's cache install, but an undocumented optimization clears protection
for the **first speculative load in the LSQ** (`isReallyUnsafe` cleared) — a Spectre-v1 single load
then installs a secret-dependent line while speculative. That is exactly `check_ld`'s criterion (the
transmitter load's own in-window cache touch), and the stimulus (a `CMP/JNE` mispredict feeding
`MOV RAX,[R14+secret]`) is the shape the Alloy model already enumerates. So it is **in scope**, and
§4 reports the result: **SimSpect demonstrates UV6** on this build — the defense fails to delay the
first unsafe speculative load, which then accesses cache in-window (68/300).

---

## 4. The one in-scope AMuLeT load bug — SpecLFB UV6 (demonstrated)

SpecLFB is the one AMuLeT *load*-defense bug in scope, and SimSpect was instrumented to run it
(`/work/amulet/amulet-gem5-SpecLFB_AE-v1.1`, newer gem5 base; config-glue only, no recompile;
`check_ld_speclfb.py`). Result, precisely (`results/STT_6_speclfb`, 300-test `mispredict_not_taken`):

- **UV6 demonstrated.** SpecLFB's contract is "delay every **unsafe speculative load** until it is
  safe." The xmit loads are genuine unsafe speculative loads (`isCUSL=1`, a prior branch unresolved),
  but SpecLFB marks them **unprotected** (`isReallyUnsafe=0, isUnsafe=0`) — AMuLeT's first-spec-load
  exemption (their Fig. 8) — and **68/300 (23%) perform their cache access while still speculative,
  in-window**, when the defense should have delayed them. That **is** UV6: the defense failed to
  protect a speculative transmitter that then acted in the window — *held to the exact same bar as
  the STT A4 / SPT A5 race* ("the defense let a speculative transmitter act in-window"). The control
  is built in: **4 `protected_lfb_access`** sibling loads show `isReallyUnsafe=1` and *are* delayed,
  proving SpecLFB engages — it is specifically the first spec load that escapes.

- **Why the "const-addr" label was wrong here — twice over.** An earlier pass called these 68
  "const-addr FPs" because every xmit load reads a fixed, prologue-pre-warmed address (`0x3580`) → a
  `ReadReq … hit`, no secret-dependent install. That is wrong for two independent reasons:
  1. **The address operand is genuinely tainted (verified in asm, 6/6 hits).** The xmit is an *indexed*
     load `movq (%base,%index),%dst` whose **`%index` is fed by an earlier speculative load** on the
     mispredicted path (e.g. `inst-002014`: `%rdx ← pc3`). That is a textbook load→address Spectre-v1
     gadget — the dataflow is intact, not collapsed. The runtime address is fixed at `0x3580` **only
     because the index *value* is 0** (the zero-init prologue makes the speculative load read 0, so
     `base+0`) — it is the **input value** that is zero, **not the address operand** that is constant.
     So this is not even a "const-addr" case in the model's sense.
  2. **Even setting that aside, const-addr is a *data-taint* disqualifier that does not apply here.**
     It correctly voids a hit only on a **data-taint defense (SPT-Fence/DDIFT)**, where a constant
     address is genuinely *untainted* so the fence *correctly* doesn't engage. **SpecLFB — like STT and
     recon-STT — protects a load by virtue of it being an *unsafe speculative* load, not by data
     taint**, and is supposed to delay it whatever its address holds; it didn't. So the fixed runtime
     address does not make UV6 an FP, exactly as it does not make the STT A4 hits FPs (counted as a
     real bug at the same bar). (This also answers the STT question directly: const-addr is *not* a
     disqualifier for STT, and it never was applied as one — STT taints by speculation, not data, §9.)

- **Detection efficiency (the SimSpect side of §8).** In the ordered 300-test sample, SimSpect's
  **first UV6 detection is test #6** (`inst-002014`, `isCUSL=1, isUnsafe=0`, in-window), with a
  **23% UV6 yield** thereafter — because every generated test is a targeted Spectre-v1 single-load
  shape (the UV6 stimulus) by construction.

**What is still open (the *stronger* claim, optional).** The xmit address is already
speculation-derived; what it lacks is a **non-zero (secret) index value** so the resolved address —
and thus the cache **footprint** — *varies* and is observable (the AMuLeT Fig. 8b shape: a flushed
buffer + a secret-valued index that misses). The zero-init prologue currently forces the index to 0.
That is the **stimulus** half of the C2 fix (`POTENTIAL_MODEL_FIX_constaddr_taint.md`): seed the
speculative load with a non-zero secret so the footprint moves. It would upgrade "SpecLFB fails to
protect the first spec load (demonstrated)" to "and here is the secret it leaks" — *not* required to
call UV6 found, but the thing that makes it a full end-to-end PoC.

---

## 5. Test targeting / diversity vs AMuLeT

> **Figure F3 — targeting.** Three candidates:
> - **F3a** `F3_targeting_a.png` — normalized stacked bars: % of generated tests that can even
>   leak (AMuLeT 17% vs SimSpect 100%).
> - **F3b** `F3_targeting_b.png` — AMuLeT's gadget breakdown (LL/BRX/either, tight vs loose) with
>   SimSpect's 100% as a reference line.
> - **F3c** `F3_targeting_c.png` — paired donuts: "leakable-test yield" per generator.

We statically analyzed the tests AMuLeT *generates* for its STT campaign (no gem5, no contract
model): `/work/amulet-repo/src/gen_stt_tests.py` (the exact campaign config) + `analyze_gadgets.py`
(iced-x86 decode + per-CFG-path taint chain + critical-path window schedule). A test "contains a
gadget" only if a real register chain links a speculatively-loaded secret to a transmitter **and**
the speculation window provably outlasts the transmitter's act (plus unprotected/fence exclusions).

Of **500** generated tests (`stt_corpus_gadgets.json`, all filters):

| gadget | tight (window-valid) | loose (structure only) |
|---|---|---|
| LL (load→load) | **70 (14.0%)** | 333 (66.6%) |
| BRX (branch) | **25 (5.0%)** | 162 (32.4%) |
| **either** | **85 (17.0%)** | 349 (69.8%) |

So **only 17% of AMuLeT's random tests can leak at all**; 83% lack the components by construction.
Even loose structural matches top out at 70%, and the window check (the realistic constraint — the
source branch must resolve *after* the transmitter acts) removes most of them. The result is robust
to the latency knob (LOAD_LAT ∈ {20…300} barely moves it — it is determined by *structure*, not a
tuning choice).

By contrast, **100% of SimSpect's 100,000 tests** (`alloy.max_instances`, both modes ≈ 94k–100k
concretized) carry a transmitter that is *provably in the speculative protection set* — that is what
the generator's `tag_xm` constraint (`STT_6.als:270`) *means*. Every test is, by construction, a
candidate leak the defense must stop. This is the diversity/targeting advantage: AMuLeT spends ~83%
of its budget on tests that cannot leak and discovers gadgets emergently; SimSpect spends 100% on
targeted transmitters and additionally controls the *exact dataflow shape* (load→load, branch,
load→ALU→load, interleaved two-chain merges).

> **Caveat we keep honest:** targeting ≠ realizability. SimSpect's 100% are leak-*shaped*, but the
> C1/C2 concretization gaps (§7) mean a fraction concretize to const/clobbered dataflow that gem5
> correctly does not leak. The 100% is "every test targets a transmitter-in-protset," not "every
> test is a realizable secret leak." The fixes are owner-gated model changes (§7).

---

## 6. Timing-window sweeps — the stall knobs (validation against a labeled oracle)

> **Figure F4 — stall-knob sensitivity.** Three candidates:
> - **F4a** `F4_stalls_a.png` — three panels (s_U log, s_R, fnc), the clean curves.
> - **F4b** `F4_stalls_b.png` — normalized overlay (each knob vs its sweep, % of baseline).
> - **F4c** `F4_stalls_c.png` — a tornado of leak-count swing per knob.

The leak **window** itself (`lc_retire < signal < fnc_retire`) is the Alloy model's contract and is
not under test. What needs justifying is the choice of the three micro-arch **stall** knobs we
impose in gem5 to probe each test (`PAPER_EXPERIMENTS.md`):

| knob | config key | what it stalls |
|---|---|---|
| **s_R** resolved | `sweep.points` | a branch that has resolved |
| **s_U** unresolved | `sweep.unresolved_stall_cycles` / `unresolved_points` | a still-unresolved branch |
| **fnc** | `gem5.fnc_commit_stall_cycles` | the commit at the speculation-boundary inst |

We swept each independently on the STT corpus **at `commitToIEWDelay=3`** (the regime where the A4
race is live), 200 ld/mode, and **bucket-confirmed 100% of the hits as `stt_vp_squash_race`** (no FP,
no over-approx) so the curve measures a *real* leak being modulated
(`results/experiments/paper_stalls/`, `bucket_stalls.sh`):

- **s_U masks completely.** `{0→27, 50→0, 250→0, 1000→0, 5000→0}` — any unresolved stall ≥ 50
  shoves the transmitter past `fnc_retire`, out of the window. **`s_U = 5000` is therefore NOT a
  trustworthy default** (it hides real leaks); we report this as a finding, not avoid it.
- **s_R is a near-flat plateau.** `{0→27, 8→22, 64→22}` — resolved-branch stalling barely moves the
  verdict.
- **fnc plateaus.** `{0→16, 150→27, 300→27}` — the leak **survives at fnc = 0** (16 hits), proving
  the result does not hinge on the fnc hook; the hook only widens the window past a plateau.

The stock baseline (recon-modded, no commit-latency override) is **0 across every s_R/s_U/fnc value**
— there is no race at stock timing to modulate. The discipline (per `PAPER_EXPERIMENTS.md` §0/§5 and
the CLAUDE.md "never tune to hit/avoid a bug" rule): this is a **sensitivity study against a labeled
oracle** (real leaks, checker FPs, true negatives), reporting curves as-is. Success is the *shape*
(a plateau/knee with the operating point in the stable regime, and the masking made visible), not a
value chosen for a desired answer.

---

## 7. Fragility — leak vs `commitToIEWDelay`, and why modifying timing is legitimate

> **Figure F5 — fragility threshold.** Three candidates:
> - **F5a** `F5_fragility_a.png` — STT curve (both modes), stock control highlighted.
> - **F5b** `F5_fragility_b.png` — STT vs Fence control, *raw cache-reach vs real (filtered)* —
>   shows why the Fence "control" needs the const-addr filter.
> - **F5c** `F5_fragility_c.png` — a fragility ranking (smallest `commitToIEWDelay` that leaks).

The fragility experiment (`EXPERIMENTS.md`, `results/experiments/paper_fragility/`) sweeps the
**squash→IEW redirect-propagation latency** `commitToIEWDelay ∈ {1,2,3,4}` (bare, `squashWidth=8`,
via additive `se_exp.py`) and reports each defense's **smallest value at which it starts leaking** —
its fragility threshold. For STT (`/work/stt` scheme 2, 300 ld/mode, real cache-access leaks):

| commitToIEWDelay | 1 (stock) | 2 | 3 | 4 |
|---|---|---|---|---|
| not_taken | **0** | 20 | 41 | 42 |
| taken | 0 | 0 | 2 | 2 |

STT is **secure at stock (0)** and **leaks from `commitToIEWDelay ≥ 2`** — a single, realistic
timing bump. The **Fence control** raw curve (`fence_d*`) shows ~50/150 "cache-reach" even at stock,
but **those are const-addr over-approximation (C2), not leaks** — after the const-addr filter the
real tainted-address race is **0/230 at stock** (`claudelog` 23:55) and appears only under
slow-comm. F5b draws exactly this raw-vs-filtered distinction so the control is not misread.

### Why this is allowed — gem5 should be timing-agnostic about defense security

This is the crux of the methodology, so it is worth stating plainly:

1. **The stall/latency knobs are micro-architectural *implementation* parameters, not part of any
   defense's security argument.** `commitToIEWDelay`, `squashWidth`, `back/forwardComSize`, and the
   stall hooks describe how fast a particular pipeline propagates a squash — they are config knobs
   in `se.py`, never defense logic.
2. **A correct speculative-execution defense must be secure across the legal space of these
   timings.** STT/SPT security is a *logical* property — "a tainted value never reaches a transmitter
   inside the window" — that must hold regardless of how many cycles the squash takes to propagate.
   gem5's defaults (`commitToIEWDelay=1`, a one-shot *unbounded* IQ/LSQ flush) are **one optimistic
   point** in that space; real silicon has multi-cycle redirect latency and **bounded** squash
   bandwidth (it cannot flush unbounded LSQ entries per cycle). So the default is, if anything,
   *less* adversarial than real hardware.
3. **Therefore sweeping these knobs is not "tuning to hit a bug" — it is testing whether the
   defense's security survives the legal timing space.** A defense that only holds at
   `commitToIEWDelay=1` is broken: its security depends on an idealization gem5 happens to ship. The
   fragility sweep shows STT/SPT's untaint-at-resolution logic (F6) is exactly this kind of
   timing-dependent: the *logic* flaw is permanent (no `not-on-squashed-path` guard), and the timing
   only sets how wide the resulting window is.
4. **We never touch the defense source.** The timing is changed only through an **additive**
   `se_exp.py` (a copy of `se.py` reading `SIMSPECT_*` env overrides) — the defense's gem5 code is
   untouched, honoring the CLAUDE.md rule "do not mess with gem5 on any front other than the hooks."
   The sweep is reported as-is against the labeled oracle (§6), with the Fence control proving a
   positive result is release-mechanism-specific, not a harness artifact.

In short: gem5 *is* agnostic to these knobs (they are config, not logic) — and that agnosticism is
precisely why a defense whose security depends on a specific value of them is the bug.

---

## 8. Efficiency comparison to AMuLeT — measured (A detection + B throughput)

Both framings were run on the **same SpecLFB build** (`/work/amulet/amulet-gem5-SpecLFB_AE-v1.1`).
AMuLeT's fuzzer was wired to that build (`cli.py fuzz --SpecLFB --gem5-path … --gem5-binary <abs>`;
the author-path default in `autorun.py` is overridable) and **runs end-to-end and finds SpecLFB
contract violations**. Figure **F8** (`F8_efficiency_{a,b,c}.png`). The result is honest and two-sided:
**SimSpect wins on *targeting*; AMuLeT wins on *executor throughput*** — they are optimized for
different things.

**(A) Detection efficiency — tests to first detection of the SpecLFB (UV6) insecurity.**

| | SimSpect (targeted enum) | AMuLeT (random fuzz) |
|---|---|---|
| **first detection** | **test #6** (`inst-002014`) | **test #39** |
| **hit density** | **23%** (68/300 flag UV6) | **3.3%** (4/120 violations) |
| basis | every test is the targeted Spectre-v1 single-load shape (`tag_xm`) | random programs; ~17% even contain a gadget (§5) |

SimSpect reaches the first detection in **6.5× fewer tests** and at **~7× the hit density** — the
direct, time-axis confirmation of the §5 targeting claim. (Source: `results/STT_6_speclfb`, ordered
300-sample, for SimSpect; `results/STT_6_speclfb/amulet_compare/fuzz.log`, `cli.py fuzz --SpecLFB
--nonstop --profile -n 120`, for AMuLeT.)

> **A precise nuance, kept honest.** The two tools flag slightly different *events*: SimSpect flags the
> UV6 **condition** (an unsafe first spec load accessing cache in-window, `isUnsafe=0`); AMuLeT flags an
> **observable contract violation** (an input-differential cache footprint). AMuLeT found **4 observable
> violations** because it *fuzzes inputs* and so produces the footprint variation that SimSpect's
> zero-init (const-index) corpus does not — which is exactly the §4/§9 stimulus gap, viewed from the
> other side. So the two results are complementary: SimSpect detects the *defense failure* deterministically
> and early; AMuLeT's input-differential supplies the *observable footprint* SimSpect currently lacks.

**(B) gem5 cost per test — the *fair* number isolates the actual simulation.** SimSpect's pipeline
per-test cost mixes three things: an `as`+`ld` build (not gem5), the **gem5 simulation**, and the
**O3PipeView/LSQUnit measurement trace** (SimSpect's instrumentation, not gem5 work). Excluding the
build and the measurement trace — i.e. **just the gem5 time** — the two tools are **comparable**
(`/tmp/time_gem5_only.py`, gem5's own `hostSeconds`; AMuLeT's `m5.simulate` from `--profile`):

| per-test cost (s) | SimSpect | AMuLeT |
|---|---|---|
| **gem5 simulation** (the fair number) | **0.092** (`hostSeconds`, light trace) | **0.057** (`m5.simulate`) |
| as+ld build (not gem5) | 0.03 | — (different codegen) |
| O3PipeView measurement trace | +0.39 (SimSpect instrumentation) | light cache trace |
| fresh gem5 boot / test | +0.61 (no IPC) | amortized (persistent gem5) |

The **pure gem5 simulation is the same order (~1.6×)** — once SimSpect's *measurement* pipeview (+0.39 s)
and its *fresh per-test gem5 boot* (+0.61 s, which AMuLeT amortizes with a persistent IPC process) are
excluded, both tools do essentially the same simulation work per litmus. SimSpect's earlier apparent
slowness was **instrumentation + harness**, not gem5: it emits a heavy instruction trace (its observation
channel) and re-boots gem5 each test — both removable (lighter trace / persistent gem5), neither a
fundamental cost.

**Bottom line (the comparison's real message):** per-test **gem5 work is comparable**, so SimSpect's
**6.5× targeting advantage** (A) means it reaches the bug with **~6.5× less total simulation** once
instrumentation is normalized out. The two tools are complementary in *kind* (targeted transmitter
reachability = SimSpect; emergent observable footprint via input-differential = AMuLeT, §3), not in raw
gem5 cost. *(Caveat: throughput timed at box load ~43–55; tests-to-detection counts are load-independent,
the per-test seconds are gem5's own `hostSeconds`/`m5.simulate` measures and robust to load.)*

---

## 9. Appendix — the generation/measurement scaffolding (not results)

**These are not findings about the defenses.** They are known, fixable issues in *our own*
generator/checker; a clean re-generation with the model fixes applied would not produce them. The
per-run `diagnostics/` bucket exactly these so we don't re-run the 100k corpus to re-confirm them
(§1). They are listed here once, demoted out of the results, so §2's gem5-bug counts are read
correctly — every count there is *post-scaffolding* (the real-leak survivors), never the raw hit total.

- **C2 — const-addr over-approximation (a *data-taint* disqualifier only).** The model treats
  *produced-under-speculation* as secret; a constant-valued address concretizes to a fixed scratch
  slot. **This is a disqualifier *only* for data-taint defenses (SPT-Fence/DDIFT)** — there a constant
  address is genuinely untainted, so the fence *correctly* doesn't engage and the hit is not a bug
  (~99.9% of SPT ld "hits"). It is **not** a disqualifier for **speculation-taint** defenses
  (**STT, recon-STT, SpecLFB**), which protect a load by virtue of it being *speculative* regardless
  of its address value — so the STT A4 race and SpecLFB UV6 are real defense failures at the
  in-window bar even with constant addresses (this is the correction in §4; it is why const-addr was
  never applied to STT and shouldn't be). What const-addr *does* bound, for **every** defense, is the
  *end-to-end secret-recovery PoC* — a constant-valued address means that test doesn't *recover* a
  secret. Closing it (`POTENTIAL_MODEL_FIX_constaddr_taint.md`, the secret-derived cache-missing
  stimulus; SPT `inaddr` half already applied) is what upgrades "defense failed (demonstrated)" to
  "and here is the leaked secret."
- **C1 — rf last-writer clobber.** `rf` is not pinned to the most-recent writer, so ~58% of the
  testset has register dataflow that concretization silently rewrites. Owner-gated (`Option A`,
  `ALLOY_RF_LASTWRITER_BUG.md`), 17 models, full from-XML regen.
- **C3 — OTB generation gap.** The `ld→other→xm` precursor for the real A1 bug is absent from the
  capped 100k enumeration but **legal** (SAT when forced). A `max_instances`/ordering artifact, not a
  model limit — needs a forcing predicate + interleave (`OTB_GENERATION_GAP.md`).
- **C4 — stale STT testsets.** `STT_6`/`interleave` XML predate the effective `RS` minimality clause
  → cover only 2 of ~45 leak dataflows. Regen recommended.
- **Checker fixes (B1/B2) and pipeline fixes (D1 dup-PC, D2 pipeview blowup)** landed mid-project;
  any campaign spanning them must be re-triaged. The catalog (`bug/BUG_TAXONOMY.md`) tracks status.

The throughline: **the model layer is the dominant source of *false* signal on the *data-taint*
defense (C1/C2 inflate the SPT-Fence hits), and is simultaneously *under-covering* the real bugs
(C3/C4).** Closing C2's stimulus half (secret-derived, cache-missing addresses) would deflate the
false SPT load hits *and* upgrade the already-demonstrated SpecLFB UV6 / STT A4 findings from
"defense failed" to a secret-recovery PoC — the single highest-value next fix.

---

## 10. Figure index & provenance

All figures: `python3 paper_figures/make_paper_figures.py` (numbers baked in with per-figure
provenance comments; same discipline as `bug/graphs/make_graphs.py`). Existing complementary charts
live in `bug/graphs/` (`make_graphs.py`).

**Publication-quality source:** `paper_figures/figures.tex` is standalone **TikZ / pgfplots / booktabs**
LaTeX for the bug table + the key figures (F2 scope, F1c scoreboard, F3, F4, F5, F8, and the F6/F7
schematics as native TikZ). Compile with `pdflatex figures.tex` (needs `tikz`, `pgfplots`≥1.16,
`booktabs`). *No TeX toolchain was available where this was generated, so the `.tex` is unverified
locally — it uses only standard constructs; tweak sizes in your paper env.* The PNGs are the raster
preview / candidate set; the `.tex` is for the paper.

| slot | candidates | data source |
|---|---|---|
| F9 bug table | `F9_bug_table.png` + `figures.tex` Tab.1 | `bug/BUG_TAXONOMY.md`, `docs/AMULET_VS_SIMSPECT_SCOPE.md`, `reconresults.md`, `results.md` |
| F1 hit attribution | `F1_attribution_{a,b,c}.png` | `results/*/diagnostics/buckets/summary.json`, `slow_comm_squash1/sample*/summary.json`, `results.md` |
| F2 AMuLeT scope | `F2_scope_{a,b,c}.png` | `docs/AMULET_VS_SIMSPECT_SCOPE.md` |
| F3 test targeting | `F3_targeting_{a,b,c}.png` | `/work/amulet-repo/stt_corpus_gadgets.json`; `alloy.max_instances`; `STT_6.als:270` |
| F4 stall sensitivity | `F4_stalls_{a,b,c}.png` | `results/experiments/paper_stalls/stt_*/summary.json` |
| F5 fragility | `F5_fragility_{a,b,c}.png` | `results/experiments/paper_fragility/{frag,fence}_d*/summary.json` |
| F6 VP↔squash race | `F6_vp_squash_race.png` | `bug/stt_slowcomm_vp_squash_race/`, `claudelog` 09:30/23:55 |
| F7 recon bugs | `F7_recon_bugs.png` | `reconresults.md`, `bug/recon_SLF_stlf_bypass/` |
| F8 AMuLeT efficiency | `F8_efficiency_{a,b,c}.png` | `results/STT_6_speclfb` (SimSpect #6/23%) + `results/STT_6_speclfb/amulet_compare/fuzz.log` (AMuLeT #39, 4/120, profile) + `time_gem5_only.py` (0.092 vs 0.057 s/test) |

Verdict legend (consistent across figures and the catalog): 🔴 real target bug · 🟠 checker
artifact · 🔵 alloy over-approx/concretization/enumeration · 🟡 pipeline/codegen · ⚪ config ·
🟢 defense holds.
