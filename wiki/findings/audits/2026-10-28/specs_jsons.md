# Audit: specs/ source-of-truth JSONs (2026-10-28)

Scope: `specs/leakage/{stt,spt,recon}.json`, `transmitter_criteria.json`, `transmitter_stage_mapping.json`, `hit_categories.json`, `defense_units.json`, `gem5_builds.json`, `gem5_hooks.json`, `alloy_models.json`, `alloy_relaxations.json`, `timing/*.json` (+ `timing/records/`), `timing_directives.json`, `fanout/*.json`, `todos.json`. The footprint criteria (`leakage/{invisispec,speclfb,cleanupspec}.json`) are audited separately. This was an audit only: no spec was edited. It was time-boxed to 11 min, so items marked "unverified" need a follow-up check.

Caveat: `results/` on this Mac holds only 4 not-run `*_full` dirs. The campaigns and their `diagnostics/` live on the container, so "does campaign X / diag Y exist" could not be checked from here.

## Headline problems (fix first)

1. **The timing candidates contradict what actually ran.** `timing/slowcomm.json` (`fnc_commit_stall_cycles: 30`, `unresolved_stall_cycles: 0`, `commitToIEWDelay: 3`) is the timing that `defense_units.json` units #1 `stt_on_stt`, #2 `stt_on_recon` and #5 `recon_on_recon` say they used. But the extracted records for those campaigns show `fnc_commit_stall_cycles: 150`, `sweep.unresolved_stall: 5000`, `resolve_stall_points: [0,500,2500]` and no `commitToIEWDelay` (`timing/records/STT_6_sttbuild.json`, `STT_6_interleave_sttbuild.json`, `Recon_6.json`). `runconfigs/run_config_STT_6.jsonc:37` and `run_config_SPT_6_oneLP.jsonc:45` = 150. The `gem5_builds.json` legend `timing_hook_legend.fnc_commit_stall` says "recon/STT use 150 cyc". The value **30** in `slowcomm/fence/delay/dom.json` is attested nowhere I found, so it looks invented. `timing/fence.json` (fnc 30) also contradicts `records/SPT_6_full_fence.json` (fnc 150).

2. **`commitToIEWDelay` is not plumbed.** It appears in `timing/{slowcomm,stock,delay,dom}.json`, but `pipeline.py` has no reference to it (grep: 0 hits). `timing_directives.json` itself says "TODO (not yet wired into _build_gem5_env)". So a timing JSON claiming `commitToIEWDelay: 3` cannot be reproduced through the pipeline. The real slow-comm runs used a separate se script (`gem5-hooks/gem5-spt/se_slowcomm.py:357`). The value also disagrees with the write-up: `wiki/findings/bug/graphs/make_graphs.py:59,63` says SPT slow-comm used **commitToIEWDelay=4**, not 3.

3. **The kind→checker map exists in 4 places, and the code ignores 3 of them.** The pipeline picks checkers only from `pipeline.py:294-298` `_KIND_TO_CHECKER` (`ld`, `br_x`, `other_x`). The other three copies are `leakage/*.json .checkers`, `transmitter_criteria.json kinds.*.checker` and `transmitter_stage_mapping.json kinds.*.checker`, and none of them is read by `pipeline.py` or `STAGE3_gem5/*`. Only the dashboard reads them (`dashboard/dashboard_data.py:1167,1259`). There is no `str` entry in `_KIND_TO_CHECKER`, and `pipeline.py:299-300` sends unknown kinds to `check_ld.py`. So the "24 untriaged str hits" in `spt.json .note` and `transmitter_criteria.json kinds.str.notes` were very likely judged by **check_ld on store transmitters** (unverified: I did not confirm the ann kind string for stores). The specs say only that a str checker "does not exist", which hides this.

4. **`specs/leakage/` mixes two schemas.** `stt/spt/recon.json` are kind-keyed contracts (`transmitters`, `checkers`, `alloy_leakage_function`). The footprint files use `simspect.transmission_criterion/v1`, which `check_footprint.py` consumes via `gem5.criterion` (`pipeline.py:612,626`). Both live in the same folder, the dashboard loads `leakage/*.json` as one set (`dashboard_data.py:1259-1264`), and `pipeline.py:626` advertises `gem5.criterion = specs/leakage/<defense>.json`. That means `gem5.criterion=specs/leakage/stt.json` looks legal but has the wrong schema. This violates the one-canonical-format rule: split the folders or tag each file with a `schema`.

## Per-file findings

### leakage/stt.json, recon.json

- `alloy_leakage_function` `Loads.inaddr+(Branchxs).inreg` matches `STT_6.als:328`, all STT_6 variants (`_core:323`, `_multisource:350`, `_pincommit:318`, `_modified_protset:316`, `_stl:368`) and `Recon_6.als:320`. OK.
- `stt.json .note` "matches STT's own contract" has no citation (no paper section). This is a provenance gap.

### leakage/spt.json

- `alloy_leakage_function` `...+Stores.inaddr` matches **only** `SPT_6_oneLP.als:344`. `SPT_6.als:331`, `SPT_6_full.als` (a symlink to SPT_6) and `SPT_6_oneLP_noSTLF.als:339` are all `Loads.inaddr+(Branchxs).inreg` with no `str`. So this is the SPT_6_oneLP contract, not "the SPT" contract. Key it by model, or note the exceptions.
- `checkers.str` = "NEEDS: ..." (see headline 3).

### transmitter_criteria.json vs transmitter_stage_mapping.json (duplicate format)

- Both define the per-kind checker, signal and gate. `transmitter_stage_mapping.json` is `_status: "stub"`, lacks `str`, and leaves `other_x` as TODO. `transmitter_criteria.json` has `str`. The `br_x` signal wording differs: "branch-redirect / squash-broadcast tick" vs "branch-redirect detection". These should be merged into one file.
- **check_br's window gap is reflected correctly** in both: `transmitter_criteria.json kinds.br_x.not_leak_if`/`status: WEAK` and `transmitter_stage_mapping.json kinds.br_x.leak_gate`. This matches CLAUDE.md. Minor: the gap is put under `not_leak_if`, which is a caveat rather than a criterion, so the field is misused. The referenced `bugsynth/BRANCH_CHANNEL_CHECK_DESIGN.md` and `bugsynth/check_br_differential.py` exist.
- `kinds.other_x` signal and gate are all "TODO", but the code already states a semantics: `pipeline.py:297` "variable-latency → timing at complete". The spec should take it from `check_other.py`.
- `kinds.other_x.notes` says Otherxs is in "older models (STT_2/4/5)". That is incomplete: `STT_4_new.als:307` and `LP-only-STT_3.als:310` include it too. `STT_3.als:301` does not.
- The `ld` gate matches the CLAUDE.md data-obtained gate. OK.

### timing/*.json, timing/records/, timing_directives.json

- 30 vs 150 and `commitToIEWDelay` (headlines 1 and 2).
- The two timing formats disagree, although `timing/records/README.md` says "same format". The candidates use a flat `unresolved_stall_cycles` and no `resolve_stall_points`. The records use `sweep.{resolve_stall_points, unresolved_stall}` plus `gem5_binary` and `cpu_type`. The run-config key the code reads is `sweep.unresolved_stall_cycles` (`pipeline.py:731,873`), which is a third spelling.
- `records/SPT_6_oneLP_fence.json` and `SPT_6_oneLP_invispec.json` have build, scheme, fnc, branch_ann and sweep all **empty**. That is the exact campaign unit #3 (`spt_fence`, status `done`) cites, so its timing provenance is missing. `records/Recon_6.json` has `fnc_commit_stall_cycles` missing.
- Nothing in `pipeline.py`, `testsetgen.py` or `testrun.py` reads `specs/timing/`. It is descriptive, consumed by the dashboard only (`dashboard_data.py:1169`), so it can drift silently from the run configs.
- `timing_directives.json` is `_status: stub`.
  - `branch_resolve_stall.config_key` = "TODO", yet `gem5_hooks.json` has hook `branch_resolve_stall` and the records carry `sweep.resolve_stall_points`. The key looks attestable (unverified).
  - `branch_ann_enable.applies_to` "-modded / SPT builds ONLY" is contradicted by the records: `branch_ann_enable: true` on the `stt` build (`records/STT_6_sttbuild.json`) and the `amulet` builds (`records/STT_6_invisispec.json`, `STT_all_amulet.json`). So it is stale, and CLAUDE.md's matching sentence is stale too.
  - `unresolved_stall_cycles` correctly has no `env`: it is injected into the ann via `pipeline.py:402-425 _inject_stalls`.

### fanout/*.json

- `standard.json` and `interleave.json` `max_instances: 150000` match **no** run config. The runconfigs use 100, 500, 5000, 100000 (most) and 250000 (one). CLAUDE.md speaks of the 100k cap. 150000 looks invented. `otb.json` 50000 is also unattested.
- `otb.json .otb_shape` is consumed by no live code (only `old_scripts/scan_otb_shape.py`). It pairs `STT_6_multisource`, but `alloy_models.json` puts the OTB forcing predicate in bugsynth `STT_6_otb`/`STT_6_otb2`, while `STT_6_multisource` is "minimality relaxed per-branch". Check which model unit #8 should name.
- No pipeline code reads `specs/fanout/`: the run config's `alloy.max_instances`/`interleave` is the real source, so these files duplicate it.

### defense_units.json (`_status: SCAFFOLD`)

- Units #11 `delay` and #12 `dom` say `timing: "NEEDS: delay.json (scheme 1)"` / `"NEEDS: dom.json"`, but `timing/delay.json` and `dom.json` exist (dated Oct 21). This is stale. `dashboard_data.py:1169` skips any value starting with "NEEDS", so the existing files never show for these units.
- Units #1, #2, #5 timing `slowcomm.json` is wrong per the records (headline 1).
- Unit #9 `stt_on_spt` uses `fence.json` (SPT SpectreSafeFence) for an "STT sub-mode". That is a placeholder, and `needs` says so. OK, but it is not a real value.
- The `results` campaign names (`STT_6__latest`, `STT_6_speclfb`, `STT_6_cleanupspec_residue`, ...) and the counts in `notes` (e.g. "23,966 instances", "68/300") could not be checked against disk here.

### hit_categories.json

- Diag scripts referenced in `categories.*.diag` that are **not anywhere in the repo checkout**: `diag_check_ld_no_completion.py`, `diag_recon_slf.py`, `diag_recon_load_hits.py`, `diag_constaddr_load.py`, `diag_nonspec_cotransmit.py`, `diag_rf_clobber.py`, `diag_branch_wrongpath_respec.py`. Only `wiki/findings/bug/stt_slowcomm_vp_squash_race/diag_stt_vp_squash_race.py` exists. They presumably live in gitignored `results/*/diagnostics/` on the container, so the registry points at unversioned files.
- `bug_md` uses mixed formats: bare names (`check_ld_no_completion.md`, `branch_wrongpath_respec.md`) next to repo paths. `recon_load_hits`, `nonspec_cotransmit` and `rf_clobber` have `bug_md: null`, which violates CLAUDE.md "Every diagnostic script MUST ship with a bug .md".
- `check_ld_no_completion` may be stale. CLAUDE.md says check_ld's own gate now rejects "executed_no_packet & never completed", so this checker-FP class may no longer fire. Confirm, and if it is kept, it should be checker-scoped rather than testset-scoped.
- `recon_slf` and `vp_squash_race` are `verdict: real_bug`, while CLAUDE.md "Systematic hit bucketing" says "2. Known real bugs — None yet." One of them is stale.
- `vp_squash_race` is build-caused, but `scope.testsets` lists only `STT_6`, `SPT_6_oneLP`. Under the propagation rule a build cause goes to all runs on that build, including `STT_6_interleave` and `STT_all`, so the testsets list is narrower than the stated rule.

### alloy_models.json / alloy_relaxations.json

- The symlink claims are correct: `SPT_6_full.als -> SPT_6.als`, `STT_6_interleave.als` and `STT_all.als -> STT_6.als`.
- The bugsynth entries `STT_6_alupath`, `STT_6_otb`, `STT_6_otb2` and `STT_6_pendsquash` are not in `STAGE1_alloy/models/`. Presumably they are in `bugsynth/models/` (unverified).
- `alloy_relaxations.json` covers only STT_6, SPT_6_oneLP, Recon_6 and STT_6_core. `STT_6_multisource` is missing, although it is defense unit #8's model.

### gem5_builds.json, gem5_hooks.json, todos.json

- `gem5_builds.json` fnc legend (150) agrees with the runconfigs and disagrees with the timing candidates (see headline 1).
- Builds and hooks were not deep-checked in the time box (paths are `/work/...` on the container).
- `todos.json` is empty, and the dashboard writes to it (`dashboard_data.py:827,902`). OK.

## Suggested actions (need Anna's OK; nothing applied)

- Correct `timing/{slowcomm,fence,delay,dom}.json` fnc to the attested 150, or cite the source of 30.
- Either wire `commitToIEWDelay` into `_build_gem5_env`, or mark it as "se_slowcomm.py only" and fix 3 vs 4.
- Pick one kind→checker source and add `str` handling explicitly instead of the silent check_ld fallback.
- Merge `transmitter_stage_mapping.json` into `transmitter_criteria.json`.
- Split the footprint criteria out of `specs/leakage/`.
- Clear the stale `NEEDS` entries in units #11 and #12.
- Fill `records/SPT_6_oneLP_*`.
- Give the fanout files attested caps.
- Version or relocate the diag scripts and add the missing bug mds.
