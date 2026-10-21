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
| **STT_6_multisource** | minimality relaxed **per-branch → aggregate** (`secure[RR->unresolved]`): "resolving *all* speculation secures it" instead of "resolving *each branch alone* secures it." | **Admits the OTB / `getOldestTaint` two-source merge** (in-degree ≥ 2) that base STT_6 structurally can't emit. The dedicated OTB-enumeration model. |
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
| **`/work/gem5-recon-modded`** ⭐ | 4.5G, **NO git** (hooks → `gem5-hooks/gem5-recon-modded/`) | X86 `X86O3CPU`, `configs/example/se.py` | `--scheme` **0**=Unsafe **1**=Delay **2**=STT **3**=DoM; adds `--branch-ann-file` BTB override | **Primary build.** Runs STT_6 / STT_all / Recon_6. Where recon OTB + STL/SLF bugs reproduced. The `-modded` BTB override is what realizes the modeled mispredict (taken mode) + branch-resolve stalls. |
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
