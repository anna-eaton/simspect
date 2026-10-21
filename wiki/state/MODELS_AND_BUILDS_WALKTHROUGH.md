# BRIEF — walkthrough of all Alloy models + all gem5 builds (+ how far we've gotten)

*Spun up 2026-10-21 (cleanuprepo). Purpose: Anna + Claude walk through **every Alloy model** and
**every gem5 build**, and for each discuss **how far we've gotten** — enumerated? run? what was
found? what's open. Tick `[x]` as each is understood/discussed. Data is as-scanned on the container;
verify live before trusting run state. Findings references point to the durable writeups.*

**Legend:** `[ ]` to discuss · `[x]` done · XMLs = instances enumerated into `testsets/<model>/xml/`.

---

## PART 1 — ALLOY MODELS (19 live in `STAGE1_alloy/models/` + 22 archived)

Models encode the same symbolic speculation framework; the **defense family** differs by protection
granularity: **STT** = `hardware_protection_policy: State` (memory), **SPT** = `: Operand`,
**Recon** = parameterized policy. Transmitter set = `leakage_function`.

### A. The 3 crucial / production models  `[ ]`
- [ ] **STT_6** — 6 instr; transmitters loads(inaddr)+branches(inreg); **100,000 XMLs**. The main STT
      model. *How far:* run on recon-scheme2 + sttbuild → **0 ld leaks (model holds)**; br_x were
      check_br FALSE POSITIVES (`wiki/findings/.../STT_BRANCH_LEAK_ROOTCAUSE`); the one real STT race =
      **VP↔squash** (`wiki/findings/bug/stt_slowcomm_vp_squash_race/`). `STT_all`→250k, `STT_6_staged`→8.
- [ ] **SPT_6_oneLP** — 6 instr; loads+branches **+ stores(inaddr)**; **100,000 XMLs**. Main SPT model
      (adds store-address transmitters). *How far:* run on gem5-spt fence (`SPT_6_oneLP_fence`); same
      VP-squash race; **config bug found: freeParam=0 made fwd/bwd untaint INERT**
      (`wiki/findings/mdsToRead/`); 24 untriaged `str` store-addr hits (need a store-transmitter checker).
- [ ] **Recon_6** — 6 instr; loads+branches; **100,000 XMLs**. Recon (parameterized policy). *How far:*
      run on recon-modded; **2 real recon bugs reproduced**: OTB/getOldestTaint + STL/SLF bypass
      (`wiki/findings/bug/recon_SLF_stlf_bypass/`, bugsynth OTB).

### B. STT_6 variants (NOT yet enumerated — 0 XMLs → invisible in old dashboard)  `[ ]`
- [ ] **STT_6_multisource** (15 KB, biggest) — the **OTB two-load→ALU merge** model. *How far:* built,
      **never enumerated**; OTB generation gap writeup `wiki/findings/mdsToRead/OTB_GENERATION_GAP.md`.
- [ ] **STT_6_core** — staged-enumeration ("up to 6" relaxed) + `stage_seed.py`/`stage_pipeline.py`.
      *How far:* staged E2E verified; `STT_6_staged` testset has 8 XMLs. `mdsToRead/STAGED_ENUMERATION.md`.
- [ ] **STT_6_pincommit**, **STT_6_modified_protset** — contract variants; never enumerated.
- [ ] **STT_6_interleave** (→ symlink STT_6) — chain interleaving applied in `parsexml`, not a separate
      enumeration; `STT_6_interleave` campaigns exist (run against recon + sttbuild).

### C. SPT variants  `[ ]`
- [ ] **SPT_6** (base, operand-granularity) — 5,000 XMLs. **SPT_6_full** (→SPT_6 symlink) — 100k.
- [ ] **SPT_6_oneLP_noSTLF** — SPT without store-to-load forwarding; never enumerated.

### D. Older / smaller STT models (model development history)  `[ ]`
- [ ] **STT_5** (100k), **STT_3** (65), **STT_2 / STT_4 / STT_4_new** (0), **STT_5_ld_xmit_only**
      (loads-only transmitters, 0), **LP-only-STT_3** (0). Mostly superseded by STT_6. Discuss: keep/park?
- [ ] **old_models/** — 22 archived `.als` (MCMtso, STTcommitted*, model*, test_ordering*, …). Archive.

### E. Testsets with no current model (probes/scratch)  `[ ]`
- [ ] `_verify_ld_taken` (1270), `_otb_search_c1/c2` (500), `_otb_alloy_probe` (100), `OTB`/`SMOKE`/
      `STL_bug` (0). OTB-search + taken-branch probes. Discuss: promote to a model, or clean up?

---

## PART 2 — gem5 BUILDS (`/work/*` in the `gem5_dev` container)

Each build = a different defense implementation the SAME testset is run against; gem5 is ground truth.
Schemes/variants selected via `run_config.jsonc` → `SIMSPECT_*` env (see `wiki/design/.../METHODS_INSTRUMENTATION`).

### A. Recon / STT family — the `-modded` BTB-override builds  `[ ]`
- [ ] **`/work/gem5-recon`** (4.5G, **NO git** — the BASE) & **`/work/gem5-recon-modded`** (4.5G, **NO
      git** — the CHANGE; adds `--branch-ann-file` BTB override). X86 `X86O3CPU`. Schemes **0=Unsafe
      1=Delay 2=STT 3=DoM**. *How far:* primary build for STT_6/STT_all/Recon_6 runs; found Recon OTB +
      STL/SLF bugs. **Hooks backed up** → `gem5-hooks/gem5-recon-modded/`. ⚠️ not git-tracked (durability).
- [ ] **`/work/stt`** (7.0G, git cwfletcher/stt @e3283b9) & **`/work/stt-dbg`** (7.0G, debug). The STT
      build (`--scheme` 0–3). *How far:* `STT_6_sttbuild` runs → 0 ld leaks (model holds). Hooks →
      `gem5-hooks/stt/`, `stt-dbg/` (uncommitted diffs on upstream).

### B. SPT  `[ ]`
- [ ] **`/work/gem5-spt`** (7.1G, git FPSG-UIUC/SPT @0d2be0f). `DerivO3CPU`, `X86_MESI_Two_Level`.
      `se.py --scheme=2`→SpectreSafeFence; `extra_args` pick variant (SpectreSafeInvisibleSpec, Lazy,
      `--fwdUntaint`/`--bwdUntaint`). *How far:* `SPT_6_oneLP_fence` runs; VP-squash race; **freeParam=0
      untaint-inert config bug**. Hooks → `gem5-hooks/gem5-spt/`.

### C. AMuLeT load-defenses  `[ ]`
- [ ] **`/work/amulet`** (27G, **NO git**) + **`/work/amulet-repo`** (289M, git sith-lab/amulet @c871bdf).
      The AMuLeT fuzzing framework + InvisiSpec / CleanupSpec / SpecLFB (Ruby MESI ProtocolTrace).
      *How far:* **InvisiSpec UV1 confirmed**, **SpecLFB UV6 demonstrated**, **CleanupSpec unXpec**, KV1/UV2
      mechanisms confirmed; compound hardware-structure checker built (`check_ld_invisispec_compound.py`,
      `check_ld_speclfb.py`, `check_ld_cleanupspec.py`). Full accounting:
      `wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md`, `..._LOAD_DEFENSES_PROJECT_LOG.md`,
      `INVISISPEC_UV1_CONFIRMED.md`. Scope vs us: `wiki/design/docs/AMULET_VS_SIMSPECT_SCOPE.md`.

### D. SDO  `[ ]`
- [ ] **`/work/sdo`** (194M, git cwfletcher/sdo @5d058fd, clean — no hooks). Speculative Data-Oblivious.
      *How far:* present, **little/no runs** — discuss whether in scope.

---

## PART 3 — the model × build matrix + what's OPEN  `[ ]`
- [ ] Which models have been run against which builds (from `results/`): Recon_6→recon; STT_6 &
      STT_6_interleave→recon-scheme2 + sttbuild; SPT_6_oneLP→gem5-spt fence (+ newts rerun); AMuLeT
      campaigns (STT_6_invisispec/_compound/_speclfb, STT_6_cleanupspec_residue, STT_all_amulet/_recon).
- [ ] **Open items to discuss:** (1) the **store-transmitter checker** (24 untriaged SPT `str` hits);
      (2) the **branch-channel checker rewrite** (`check_br.py` — the #1 checker debt; see STATUS +
      `bugsynth/BRANCH_CHANNEL_CHECK_DESIGN.md`); (3) **OTB enumeration** (STT_6_multisource never run);
      (4) Recon builds not git-tracked (durability); (5) which old models/probes to retire.

---
*Discussion notes (fill as we walk):*
