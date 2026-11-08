# Alloy models & gem5 builds — reference

*Reference doc: what every Alloy model encodes, and every gem5 build + my intention with it.
Written 2026-10-21 (derived from the `.als` sources + runconfigs). Companion to the
discussion checklist [`../state/MODELS_AND_BUILDS_WALKTHROUGH.md`](../state/MODELS_AND_BUILDS_WALKTHROUGH.md)
(how-far-we've-gotten) — this one is the stable "what each thing is" reference.*

> **Ground truth is the `.als` itself.** Do not edit any `.als` without Anna's per-change sign-off
> (repo `CLAUDE.md`). This doc paraphrases; the model files are canonical.

---

## PART 0 — the common skeleton

Every current model (`STT_6` lineage) is the **same symbolic speculation framework** and differs
only in (a) the **defense** it encodes and (b) the **generation driver** (which leaks it enumerates).

- One concrete `sig Instruction { kind: one InstrType, ... }` (ld / str / br / other), topo-ordered by
  `spo` (program order). idx/IX atoms give in-model symmetry-breaking → zero duplicate instances.
- A **transmitter** `xm` is the instruction whose observable operand could leak.
- The research signal = **gem5 lets through a test the model says is *disallowed*** (model is
  conservative; gem5 is ground truth).

The three knobs that define a model's meaning:

| knob | what it is |
|---|---|
| `hardware_protection_policy` | **the protection set** — what the defense protects (STT: a `State` = memory; SPT: `Operand`s; Recon: a *parameterized* policy). |
| `leakage_function` | **the transmitter set** — which operands can leak (loads' `inaddr`, branches' `inreg`, sometimes stores' `inaddr`). |
| `gen_useful_litmus` (the driver) | **the minimality contract** — what counts as a genuine, non-redundant speculative leak worth emitting. |

---

## PART 1 — THE LATEST / PRODUCTION MODELS  ⭐ (what I care about most)

These are the three curated in `latestmodels/` and the primary enumeration targets. Each is
**6 instructions**, ~100,000 XML instances per last container scan (testsets are gitignored).

### ⭐ STT_6 — Speculative Taint Tracking
*File: `STAGE1_alloy/models/STT_6.als`. Symlinks `STT_6_interleave`, `STT_all` → this file.*

- **Defense:** protect at the **state (memory) level** — `hardware_protection_policy: State { Mem_s }`.
  A transmitter leaks only if its operand is provably in the speculative protection set propagated
  from protected memory.
- **Transmitters:** `leakage_function = Loads.inaddr + Branchxs.inreg` (load addresses + branch
  conditions).
- **Driver:** `not secure[no_p]` (it leaks) **+ per-branch resolution-minimality** — for *each*
  unresolved branch, resolving *that one branch alone* must secure the program
  (`all i: unresolved | secure[RR->i]`), plus state-minimality (`RS`) and a commit+resolve boundary
  clause on `first_uncommitted`.
- **Consequence to know:** the per-branch clause means STT_6 **structurally cannot emit a
  two-source merge** (in-degree ≥ 2 to the transmitter) — ~99.6% of its transmitters are
  single-source. That amputation is exactly what `STT_6_multisource` and the OTB probes exist to
  work around. See [`../findings/mdsToRead/OTB_GENERATION_GAP.md`](../findings/mdsToRead/OTB_GENERATION_GAP.md).
- **Intention:** the main STT model — the baseline "does the defense hold?" enumeration run against
  the recon/stt builds.

### ⭐ SPT_6_oneLP — Speculative Privacy Tracking, one-leak-point
*File: `STAGE1_alloy/models/SPT_6_oneLP.als`.*

- **Defense:** protect at **operand granularity** (`hardware_protection_policy: Operand`), with
  explicit **untaint flows** (`nonspeculative_xmit_p`) and STLF (store-to-load-forward)
  de-protection — an input whose rf-source left the protset is de-protected, **including `inaddr`**
  (loads transmit through their address and have no `inreg`, so an inreg-only rule missed
  load-address transmitters).
- **Transmitters:** `Loads.inaddr + Branchxs.inreg + **Stores.inaddr**` — adds **store-address**
  transmitters (a store's cache access leaks like a load's).
- **Driver:** `one_insecure_speculation_scheme_p` — requires **exactly one** insecure leak point
  (not just "≥1"), plus per-branch RR-minimality and the commit+resolve boundary clause.
- **Intention:** the main SPT model, run against `/work/gem5-spt` (fence + untaint variants). The
  store-transmitter additions produced the ~24 untriaged `str` hits that still need a store checker.

### ⭐ Recon_6 — Recon (dynamic / parameterized protection)
*File: `STAGE1_alloy/models/Recon_6.als`.*

- **Defense:** the protection set is **dynamic** — `hardware_protection_policy[p]: State` =
  `Mem_s` **minus** the state reachable *backward through data-dependence from speculative loads*.
  i.e. Recon de-protects memory that a speculative load has already (transitively) consumed.
  Also carries the `rf_from_most_recent_writer` fact (rf must read the most-recent writer).
- **Transmitters:** loads(inaddr) + branches(inreg) (same as STT).
- **Intention:** the Recon defense under test — run against `/work/gem5-recon-modded`. This is where
  the **two real recon bugs** reproduced: OTB / `getOldestTaint` and the STL/SLF bypass
  ([`../findings/bug/recon_SLF_stlf_bypass/`](../findings/bug/recon_SLF_stlf_bypass/)).

---

## PART 2 — VARIANTS OF THE PRODUCTION MODELS

### STT_6 variants (same STT defense, different generation contract)
| model | the *only* meaningful change vs STT_6 | why it exists |
|---|---|---|
| **STT_6_core** | idx/IX ordering removed; length relaxed `exactly 6` → *up to* 6; driver turns on **every** minimality clause (adds RO operand-min + RI instruction-min) → maximally-minimized "leak cores." | Base of the **staged enumeration**: emit minimal cores, then Stage 2 re-seeds each into real STT_6 and lets it grow (`mdsToRead/STAGED_ENUMERATION.md`). |
| **STT_6_stl** | speculation source switched from unresolved branches to unresolved-**address stores** (store-to-load / memory-dependence speculation); all branches resolved; a fact requires a true alias (a load at or before the xmit reads the `Mem_s` an older unresolved store writes). Added 2026-10-28. | Spectre-v4-style store-bypass tests (false-negative alias prediction). Concretize with branch mode `stl_bypass`; gem5 needs the SimSpect-STL hooks (`gem5-hooks/stl/`, not built yet). [`STL_SPECULATION.md`](STL_SPECULATION.md). |
| **STT_6_multisource** | minimality relaxed **per-branch → aggregate** (`secure[RR->unresolved]`): "resolving *all* speculation secures it" instead of "resolving *each branch alone* secures it." | **Admits the OTB / `getOldestTaint` two-source merge** (in-degree ≥ 2) that base STT_6 structurally can't emit. The dedicated OTB-enumeration model. |
| **STT_6_commitsplit** | commit boundary split into C (must be committed) / D (don't care) / U (must be uncommitted, holds every unresolved instruction); the leak must hold at every commit-head position in D, C and U are shrunk to the laxest leaking boundary; every unresolved instruction must alone sustain the leak (non-contiguous branches allowed). Replaces STT_6 clauses (b) and (c). Added 2026-10-29. | Tests whose lc/fnc are only as strict as the leak needs, so the harness enforces them instead of relying on timing. [`COMMIT_BOUNDARY.md`](COMMIT_BOUNDARY.md). |
| **STT_6_pincommit** | adds one fact: `rf_from_most_recent_writer` (rf reads the most-recent writer of a state — "Option A"). | Contract experiment on rf resolution. |
| **STT_6_modified_protset** | protection tracked at **Operand** granularity (not State) + `rf_from_most_recent_writer` + `first_uncommitted` fallback to `first_instr`. | Contract experiment: STT-at-operand-granularity. |

### SPT variants
| model | change | why |
|---|---|---|
| **SPT_6** (= **SPT_6_full**, symlink) | base operand-granularity SPT; `hardware_protection_policy = Instruction.operands`; **no** one-leak-point restriction; no store transmitters. | The full/base SPT model. |
| **SPT_6_oneLP_noSTLF** | `SPT_6_oneLP` **minus** store-to-load-forwarding paths — leakage back to loads+branches only, inreg-only de-protection. | Isolates whether STLF is the leak source (control for the oneLP STLF additions). |

---

## PART 3 — BUG-SYNTHESIS PROBES  (`bugsynth/models/`)

`bugsynth/models/STT_6.als` is **byte-identical** to the production STT_6. The rest are targeted
probes for the OTB/channel gaps (background: [`../findings/mdsToRead/OTB_GENERATION_GAP.md`](../findings/mdsToRead/OTB_GENERATION_GAP.md)):

| probe | what it forces |
|---|---|
| **STT_6_alupath** | *general* "ALU-on-address-path" steering (`some ALU.outreg feeds xmit.inaddr`) + relaxed driver (no per-branch RR) — tests whether the OTB 2-load merge appears **naturally** in that stratum. Not a pinned shape. |
| **STT_6_otb** | `otb_class` predicate: forces an ALU to feed the xmit load address so the capped enumeration spends budget there; the 2nd tainted load is hooked on by `parsexml:pass_interleave` (merge manufactured by interleave, not asserted). |
| **STT_6_otb2** | expresses the **full 2-load → 2-input-ALU → xmit** merge **directly in Alloy** (both ALU inputs rf-fed by distinct loads) — no interleave needed. |
| **STT_6_pendsquash** | the **pending-squash channel** (nmosier two-branch coincidence): explicit tainted-operand dataflow (`tainted_operands_p` / `tainted_states_p`) + tainted vs untainted branch-condition predicates. |

---

## PART 4 — LEGACY / DEVELOPMENT LINEAGE (park / reference only)

- `STT_2`, `STT_3`, `STT_4`, `STT_4_new`, `STT_5`, `STT_5_ld_xmit_only` (loads-only transmitters),
  `LP-only-STT_3` — the STT model development history, superseded by STT_6.
- `STAGE1_alloy/models/old_models/` — 22 archived `.als` (MCMtso, STTcommitted*, model*,
  test_ordering*, …). Archive.

---

## PART 5 — gem5 BUILDS  (`/work/*` in the `gem5_dev` container)

Each build = a different defense **implementation** the same testset is run against; gem5 is ground
truth. Defense/variant selected via `run_config.jsonc` → `SIMSPECT_*` env (see
[`METHODS_INSTRUMENTATION.md`](METHODS_INSTRUMENTATION.md)). `branch_ann_enable: true` (BTB force +
per-branch resolve-stall) works **only on `-modded`/SPT builds** — vanilla rejects `--branch-ann-file`.

| build | repo / git | CPU / config | defense selector | **my intention** |
|---|---|---|---|---|
| **`/work/gem5-recon-modded`** ⭐ | 4.5G, **NO git** (hooks → `gem5-hooks/gem5-recon-modded/`) | X86 `X86O3CPU`, `configs/example/se.py` | `--scheme` **0**=Unsafe **1**=NDA (code enum `Delay`) **2**=STT **3**=DoM; adds `--branch-ann-file` BTB override | **Primary build.** Runs STT_6 / STT_all / Recon_6. Where recon OTB + STL/SLF bugs reproduced. The `-modded` BTB override is what realizes the modeled mispredict (taken mode) + branch-resolve stalls. |
| **`/work/gem5-recon`** | 4.5G, **NO git** — the BASE of `-modded` | X86 `X86O3CPU` | same schemes, **no** branch-ann | Baseline control: the un-modded recon, to confirm a hit isn't an artifact of the BTB hook. |
| **`/work/stt`** | 7.0G, git cwfletcher/stt @e3283b9 (hooks → `gem5-hooks/stt/`) | X86 `X86O3CPU`, `configs/example/se.py` | `--scheme` 0–3 | The **upstream STT** build — cross-check STT_6 results against recon-scheme2. `STT_6_sttbuild` → 0 ld leaks (model holds). |
| **`/work/stt-dbg`** | 7.0G, debug build of `/work/stt` (hooks → `gem5-hooks/stt-dbg/`) | same | same | Debug/trace variant of `/work/stt` for diagnosing specific records (slower, fuller logging). |
| **`/work/gem5-spt`** ⭐ | 7.1G, git FPSG-UIUC/SPT @0d2be0f (hooks → `gem5-hooks/gem5-spt/`) | `DerivO3CPU`, `X86_MESI_Two_Level` | `--scheme=2`→`SpectreSafeFence`; `extra_args` pick variant: `SpectreSafeInvisibleSpec`, `Futuristic*`, `--configImpFlow=Lazy`, `--applyDDIFT`/`--fwdUntaint`/`--bwdUntaint`/`--disableUntaint` | The **SPT** build. Runs SPT_6 / SPT_6_oneLP across fence & invisible-spec & untaint variants. Where the **freeParam=0 untaint-inert** config bug was found. |
| **`/work/amulet/` — four AE builds** | 27G total, **NO git** | each a full separate gem5 tree (not scheme flags of one build) | see sub-table below | AMuLeT **load-defense** campaigns. Confirmed: InvisiSpec UV1, SpecLFB UV6, CleanupSpec unXpec, KV1/UV2. Compound hardware-structure checkers built. Scope vs us: [`docs/AMULET_VS_SIMSPECT_SCOPE.md`](docs/AMULET_VS_SIMSPECT_SCOPE.md). |
| **`/work/amulet-repo`** | 289M, git sith-lab/amulet @c871bdf | the AMuLeT **framework** source | — | Git-backed AMuLeT framework (fuzzer/analysis); the four prebuilt AE gem5 artifacts live in the 27G `/work/amulet`. |

**The four `/work/amulet/amulet-gem5-*_AE-v1.1` builds** (each a distinct gem5 defense implementation):

| defense | build dir | gem5 build / cache | scheme selector | checker |
|---|---|---|---|---|
| **InvisiSpec** | `amulet-gem5-InvisiSpec_AE-v1.1` | `build/X86_MESI_Two_Level` — Ruby MESI (`--ruby`) | `SpectreSafeInvisibleSpec` | `check_ld_invisispec_compound.py` (`bug/kv1_demo/`, `uv2_demo/`) |
| **SpecLFB** | `amulet-gem5-SpecLFB_AE-v1.1` | `build/X86` — **classic cache** | scheme `"2"`→`Speclfb` | `check_ld_speclfb.py` |
| **CleanupSpec** | `amulet-gem5-CleanupSpec_AE-v1.1` | `build/X86_MESI_Two_Level` — Ruby MESI (`--ruby`) | passthrough `--scheme` | `check_ld_cleanupspec.py` (`uv4_demo/`, `unxpec_demo/`) |
| **STT (AMuLeT's)** | `amulet-gem5-STT_AE-v1.1` | `build/X86_MESI_Two_Level` — Ruby MESI | `--scheme` | — (cross-build `l1d_assoc` comparison vs `/work/stt`) |

> ⚠️ The Ruby builds (all but SpecLFB) are **Ruby-only** — passing `caches: true` is fatal (AUDIT #1 / BUG_TAXONOMY D4).
| **`/work/sdo`** | 194M, git cwfletcher/sdo @5d058fd, **clean (no hooks)** | Speculative Data-Oblivious | — | Present but **little/no runs** — scope decision open (whether SDO is in scope for this paper). |

**Durability ⚠️:** `gem5-recon`, `gem5-recon-modded`, `amulet` are **not git-tracked**. Their hooks
are backed up under `gem5-hooks/`, but the full trees are undiffable — see
[`../state/SYNC_DIVERGENCE.md`](../state/SYNC_DIVERGENCE.md).

---

## PART 6 — which models have run against which builds (as last logged)

Recon_6 → recon-modded · STT_6 & STT_6_interleave → recon-scheme2 + sttbuild · SPT_6_oneLP →
gem5-spt fence/untaint · AMuLeT campaigns (STT_6_invisispec/_compound/_speclfb,
STT_6_cleanupspec_residue, STT_all_amulet/_recon). Verify live before trusting — see
[`../state/RUNNING.md`](../state/RUNNING.md).

---

## PART 7 — Defense-model fit per build: does each build get the right model and load criterion? (2026-11-03, defense-fit session)

*Anna's question (2026-11-03): "for each gem5, investigate if the STT load ones need to be different than the AMuLeT load ones." Investigation only: no code, config, spec or model was changed. Sources read this session: `specs/defense_units.json`, `specs/gem5_builds.json`, `specs/leakage/{stt,recon,spt,invisispec,speclfb,cleanupspec}.json`, `specs/transmitter_criteria.json`, the defense blocks of `STT_6.als:320-332`, `Recon_6.als:311-324`, `SPT_6_oneLP.als:333-361`, `STT_6_stl.als:280-370`, `STAGE3_gem5/check_ld.py:28-150`, `check_ld_speclfb.py:1-145`, `check_footprint.py:185-235,473-482`, the run configs in `runconfigs/` and `results/*_full*/`, `gem5-hooks/stt/stt.patch:120-145`, and the papers in `~/Documents/quail/sources/papers/` via `pdftotext` (PDF pages unless noted; SpecLFB = printed pages; the ReCon copy is a 3-page web capture, so it is cited by section). Builds live on cafe2, which was not accessed; build-side claims cite earlier sessions' code reads.*

**Short answer.** Yes, they must differ, and mostly they already do. There are two kinds of load criterion, because the defenses hide different things. (1) **Delay defenses** (STT-Spectre, Recon-STT, ReCon, SPT-Fence) promise that a *tainted transmitter does not execute*: "STT considers the execution of a transmit instruction as an explicit covert channel that leaks its argument" (STT §6.1 p5), and STT deliberately lets untainted speculative loads (the access load) execute and change the cache (STT §1 p2: "executing and selectively forwarding the results of speculative access instructions"). Their criterion must be keyed on the model's transmitter and count *any* execution that obtains data, cache hits included: that is `check_ld`. (2) **Hide/undo defenses** (InvisiSpec, SpecLFB, CleanupSpec) promise that *no unsafe speculative load leaves a visible footprint*, whatever its address depends on, while the load may obtain data (into the SB, the LFB, or an install that is later cleaned). Their criterion is a footprint of any unsafe speculative load in the protected structures: that is `check_footprint` + `specs/leakage/<defense>.json`. Swapping them is wrong both ways: a footprint criterion on STT flags the access load's legal footprint, and an "obtained data / reached the cache" criterion on SpecLFB counts speculative hits, which SpecLFB puts out of scope ("Leakage through speculative loads under cache hits is out of the current defense scope of SpecLFB", §9 p643).

**The protection set differs too, and AMuLeT itself says so.** AMuLeT tests "the CT-SEQ contract for testing InvisiSpec [37] (Futuristic), CleanupSpec [29], and SpecLFB [8], and the ARCH-SEQ contract for testing STT [41] (Futuristic)" (AMuLeT §3.1 p5). ARCH-SEQ also exposes "the values of all data loaded from memory on architectural program paths" (§2.1 p3), i.e. STT protects only speculatively accessed data, matching STT's own scope (non-transient access attacks are "out of scope", STT §3 Fig. 3 p3) and SPT's description ("STT does not protect non-speculatively-accessed data", SPT §2.2 p2). CT-SEQ treats every value as secret unless an architectural load/store address or the PC exposes it, and CleanupSpec says it directly: "The secret may be accessed from the memory or from a register, or computed, transiently" (§2.1 p3). `STT_6`'s protection set (`Mem_s`, untainted when a load has no older unresolved branch, `STT_6.als:326-332`) is the ARCH-SEQ one, so it is right for STT and narrower than what the three AMuLeT defenses protect.

**But for the three AMuLeT builds the model does not decide the verdict.** `check_footprint.check_footprint` never reads `xmit_pc` (`check_footprint.py:473-482`); its actor is any squashed instruction younger than lc (`squashed_after_lc`, `:216-221`). So for these builds `STT_6` is only a *stimulus generator*: its protection set and leakage function choose which programs run, never which run is a hit. Every `STT_6` test contains at least one speculative load whose own address is not tainted (the access load), which is exactly the single-load, register-address shape of AMuLeT's UV6 gadget (AMuLeT p3: "leaking secret registers with a single speculative load"). So the narrower STT protection set costs little stimulus for footprint checks. The speculation contract costs more: `STT_6` only realizes control-flow squashes, while InvisiSpec-Futuristic (AMuLeT's setting, p8), CleanupSpec ("We deem all transient instructions potentially 'unsafe' until they retire", §2.1 p3) and SpecLFB (memory-order MUSLs, §5 p637-638; the gem5 build sets `setmUSL` for unresolved older stores, `lsq_unit.cc:893` per `PROTECTION_SCOPE_TABLE.md`) also protect loads behind other squash sources, which no `STT_6` test exercises. The leakage function also includes branches (`Branchxs.inreg`), which none of the three defenses protect (InvisiSpec: "we limit ourselves to load instructions", §IV p4), so `br_x` tests can only produce incidental load footprints (APPROVALS F-1 already proposes loads-only footprint runs).

**Where the mismatch already changed a result: the SpecLFB UV6 numbers.** The paper's "68/300" and "first detection at test #6" (`results.tex:83,155-156,170`; source `wiki/results/PAPER_RESULTS.md` §4, claudelog 2026-06-03 "results") were scored by the older, STT-shaped `check_ld_speclfb` signal (the transmitter's in-window "Doing memory access"). Every one of the 68 transmitters read the pre-warmed line `0x3580` and the dcache reported a hit (`PAPER_RESULTS.md:302-304`). Later the same day the checker was re-keyed on the L1 install (claudelog 2026-06-03 "CHECKER CHANGE", `check_ld_speclfb.py:20-34`), and on the four hits it re-checked, every one flipped to `access_hit_in_window_no_install` (not a leak). The current criterion (`specs/leakage/speclfb.json`: fill/evict in L1D/L2) would not count hits either. On SpecLFB's own terms, a speculative hit is out of scope, so the 68/300 measure the mechanism (`isUnsafe=0` on a conditional USL), not a leak. The install-keyed result that does count is 11/12 on a 12-test demo with a 1kB L1D (claudelog 2026-06-08). Separately, those transmitters are the *second* speculative load; the 2026-10-28 code read (`wiki/findings/audits/2026-10-28/hooks_speclfb_and_uv6.md`) attributes second-load exemptions to a head-skip artifact (`lsq_unit.cc:817`, sticky `PrevNoUnsafe` `rob.cc:464`), not to the published first-load rule. The published UV6 leaks via the first speculative load, which `STT_6` never marks as the transmitter.

### Fit table

| gem5 build | defense | Alloy model used | load criterion used | speculation contract matches paper? | protection set matches? | leakage function matches? | proposed change | confidence |
|---|---|---|---|---|---|---|---|---|
| `/work/stt`, `/work/stt-dbg` | STT-Spectre | `STT_6` (also `STT_6_commitsplit`) | `stt.json` = `check_ld` (transmitter-keyed; data obtained = packet or store-forward) | **yes**: STT §6.1 p5 Spectre visibility point; `--scheme=2` sets `threatModel='Spectre'`, `implicitChannel` on (`gem5-hooks/stt/stt.patch:133-137`) | **yes**: `Mem_s` + untaint at the visibility point = "STT taints the output of any speculative access instruction … untaints the output of an access instruction once it becomes safe" (§6.1 p5) | **mostly**: loads + explicit branches; the store-to-load-forwarding implicit branch (§6.4.2 p8) is missing (APPROVALS STT-1) | keep `check_ld`; never move STT to a footprint criterion. Open refinements: window the data-obtained fate (existing DECIDE); check whether `spec_read_only` can occur here (D4) | high |
| `gem5-recon-modded` `--scheme=2` | Recon-STT | `STT_6`, `STT_6_interleave` | `stt.json` = `check_ld` | **subset**: the build casts shadows from branches and stores (ReCon §3.1: "we use only speculation cast by control flow and store instructions"; `decode.cc:686-695`, `STT_VS_RECON_STT.md`). Sound, misses store shadows | yes (STT's) | as STT; this build's tainted-branch handling was never read | `STT_6_shadows` (existing DECIDE, URGENT_TODO) ; packet-line fix in `parse_lsq` (existing DECIDE, `recon_cache_reach_gate`) | high |
| `gem5-recon-modded` (ReCon) | ReCon | `Recon_6` | `recon.json` = `check_ld` | subset, as above (APPROVALS R-5) | STT's set minus a reveal that is a no-op (APPROVALS R-1); paper: "values that reside in registers before the point of speculation are not considered to be potential secrets" (§3.1), same as STT | as STT | existing R-1/R-2; no local run config, so how ReCon mode is enabled was not verified | medium |
| `gem5-recon-stl` | Recon-STT, store half | `STT_6_stl` | `stt.json`/`check_ld` (STL window checker not written) | matches the store-shadow half | yes | yes | none new | medium |
| `gem5-spt` (SpectreSafeFence / SpectreSafeInvisibleSpec) | SPT | `SPT_6_oneLP` | `spt.json` = `check_ld`; `str` falls back to `check_ld` | Spectre variants yes; the `FuturisticSafe*` configs would be a subset | direction right (SPT protects non-speculative secrets, §3 p3-4) but the seed is over-broad (A1, `PROTECTION_SET_REEVAL.md`) | loads + branches + store addresses: paper-supported (SPT §2.1 p2: memory, control-flow and variable-time instructions transmit) | existing A1 / SPT-1..3 and the store checker; `spec_read_only` = not a leak is right for the InvisibleSpec variant | high |
| `amulet-InvisiSpec` | InvisiSpec | `STT_6` | reported numbers: `check_ld_invisispec_compound`; current: `invisispec.json` via `check_footprint` (any squashed instruction after lc; `*_full_*` configs never run) | Spectre mode **yes** (§IV-A1 p4 = STT's Spectre VP); Futuristic mode (AMuLeT's, p8) **no**: control-only stimulus | **no**: hides every USL (§V-A p4); CT-SEQ (AMuLeT §3.1 p5). Verdict does not use it | **no**: includes branches; InvisiSpec covers loads only (§IV p4) | loads-only runs (F-1); Futuristic stimulus (D1); attribution field (D2) | high (mismatch), medium (impact) |
| `amulet-SpecLFB` | SpecLFB | `STT_6` | reported 68/300: older access-keyed `check_ld_speclfb` (counted hits); current: install-keyed `check_ld_speclfb` and `speclfb.json` via `check_footprint` (full config never run) | control-flow part **yes** (p638); memory-order MUSLs (§5 p637, built via `setmUSL`) **not generated** | **no**: every MUSL, no taint (§4-5 p635); CT-SEQ | loads (misses) only; branches unprotected | re-score UV6 under the install/fill criterion (D3); `STT_6_stl`/shadows stimulus (D1) | high |
| `amulet-CleanupSpec` | CleanupSpec | `STT_6` | reported: `check_ld_cleanupspec` (gates on squash timing); current: `cleanupspec.json` per-line balance (full config never run) | **no**: "all transient instructions … 'unsafe' until they retire" (§2.1 p3), any squash source | **no**: register and computed secrets included (§2.1 p3) | loads only ("prevent any transient load from leaking", §2.1 p3) | Futuristic/shadow stimulus (D1) | high |
| `amulet-STT` | STT (AMuLeT) | `STT_6` (`STT_all_amulet`, 100% errors, `AUDIT.md` #1) | `stt.json` | **unknown**: AMuLeT ran it Futuristic (p8; `gem5-hooks/amulet-repo/gen_stt_tests.py:43` `STT_FuturisticSpec`); which threat model its `se.py` picks for `--scheme=2` was never read | STT's if STT | as STT | TODO: read its `se.py` before any campaign; if Futuristic, judge against `STT_6_futuristic` | low |

### Proposed defense-block clauses (proposals only; no `.als` touched; none run through Alloy)

**P1, branch + store shadows** (Recon-STT, SpecLFB's control + memory-order MUSLs). Built from `STT_6`'s and `STT_6_stl`'s own clauses (`STT_6.als:245-256,327-332`, `STT_6_stl.als:283-287,365-370`); same as the pending `STT_6_shadows` idea:

```
fun has_unresolved_brs_strs_p[p: PTag->univ] : Instruction {
	((unresolved_p[p] & (Branchxs+Branchns+Stores)).(^(spo_p[p])))   // after an unresolved branch or an unresolved-address store
}
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_strs_p[p]}
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
	s - (Loads & (i_p[p] - has_unresolved_brs_strs_p[p]) & i).inmem.opstate
}
// hardware_protection_policy, leakage_function unchanged from STT_6
```

**P2, CT-SEQ footprint model** (InvisiSpec, SpecLFB, CleanupSpec), only worth it if D2 makes the footprint verdict transmitter-keyed. Seed in `Recon_6`'s parameterized form (`Recon_6.als:316-318`), generalized from "flows into a non-speculative load address" to every CT-SEQ observation (AMuLeT Table 1: PC and load/store addresses on the architectural path):

```
fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}   // Spectre USL; Futuristic: has_unresolved_any_p (STT_6_futuristic)
fun exposed_ops_p[p: PTag->univ] : Operand {
	((Loads + Stores) - speculation_contract_p[p]).inaddr + ((Branchxs + Branchns) - speculation_contract_p[p]).inreg
}
fun hardware_protection_policy[p: PTag->univ] : State {Mem_s - (~opstate).(*(op_edges_p[p]).(exposed_ops_p[p]))}   // secret unless it reaches an architectural observation
fun leakage_function : Operand {Loads.inaddr}   // loads only (InvisiSpec §IV p4; CleanupSpec §2.1 p3)
fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State { s }   // no visibility-point untaint
```

Caveats: the backward closure declassifies a whole source when any function of it is exposed (over-declassifies, so it under-generates rather than producing invalid tests); the `[p]` seed needs the `a[p,f[p],hardware_protection_policy[p]]` call form `Recon_6` uses; minimality (`all s: State | secure[RS->s]`) at exactly 6 instructions was not checked for SAT.

### Decisions for Anna

- [ ] DECIDE (defense-fit D1, model for the AMuLeT builds): (a) keep `STT_6` as their stimulus and say in the paper that it is a sound but incomplete generator whose protection set does not enter the footprint verdict; (b) add speculation-contract variants on the same skeleton so the stimulus covers the squash sources these defenses claim: P1 (branch + store shadows) for SpecLFB and Recon-STT, `STT_6_futuristic` for InvisiSpec-Futuristic and CleanupSpec; (c) also change the protection set to CT-SEQ (P2). Recommendation: (a) for this paper, (b) next; (c) only if D2 picks a transmitter-keyed verdict, since otherwise it changes no verdict.
- [ ] DECIDE (defense-fit D2, extends the existing InvisiSpec actor DECIDE to all three footprint defenses): who must leave the footprint? (a) any squashed load younger than lc (today; matches each paper's claim); (b) only the model's transmitter, with `STT_6` (would miss published UV6, whose leaking load is not `STT_6`'s transmitter); (c) only the transmitter, with P2; (d) keep (a) as the verdict and record per hit whether the footprint's seq is the model's transmitter. Recommendation: (d).
- [ ] DECIDE (defense-fit D3, SpecLFB UV6 numbers in the paper): the 68/300, test #6 and 23% figures counted speculative cache hits, which SpecLFB scopes out and which the current install/fill criteria do not count. (a) Re-run `results/STT_6_speclfb_full` under `speclfb.json` (likely needs the B-1 cold-line stimulus to get any misses); (b) report the install-keyed 12-test demo (11/12) instead; (c) keep 68/300 but call it a mechanism signal (`isUnsafe=0` on a conditional USL, in-window hit), not a leak. Recommendation: (a) if there is time, else (c); in all cases say the transmitter is the second speculative load.
- [ ] DECIDE (defense-fit D4, delay-defense load criterion): keep `check_ld` (transmitter-keyed, any data-obtaining execution) for STT-Spectre, Recon-STT, ReCon and SPT (recommended), and decide whether `spec_read_only` should stay "not a leak" on delay builds. It is right only where the defense makes loads invisible (InvisiSpec, SPT-InvisibleSpec); on STT/Recon/SPT-Fence a spec read by a tainted transmitter would still be an execution. Recommendation: first grep existing `/work/stt`, `gem5-recon-modded` and SPT-Fence traces for `send a spec read` (read-only); if none occur, record that in `stt.json` and change nothing.
