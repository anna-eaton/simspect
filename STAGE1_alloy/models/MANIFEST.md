# Alloy models — folder manifest (`STAGE1_alloy/models/`)

At-a-glance index of every `.als` physically in this folder. **This is a navigational front-door, not a competing source of truth:** the canonical per-model metadata lives in `specs/alloy_models.json` (keyed by stem; drives the dashboard Utilities → Alloy models table) and the deeper design write-up is `wiki/design/MODELS_AND_BUILDS.md`. Summaries below are mirrored from that JSON — edit metadata there, not here. **Never edit, regenerate, or reformat any `.als` without Anna's per-change sign-off** (CLAUDE.md).

Last built: 2026-10-30; manifest section rebuilt 2026-11-08. Folder holds 21 `.als` (incl. 3 symlinks) + the `old_models/` archive + `util/` + a visualizer theme, plus the draft folders `proposed/` (STL and shadows drafts, `derive_stl.py`) and `proposed_twophase/` (Stage-1 core drafts, `derive_core.py`, `run_stage1.py`), which the pipeline does not read.

---

## ⭐ Main models per defense → moved to [`wiki/state/EVAL_MANIFEST.md`](../../wiki/state/EVAL_MANIFEST.md) (2026-11-08)

The per-defense tables that were here (model families: main / split core / STL / STL split core; defenses we test; STL scope) were consolidated on 2026-11-08 (simspect-c8, at Anna's request) into the eval manifest, together with the approved eval set (builds, flags, run configs, checkers) and which testsets are current. Update that file and `specs/defense_units.json` (`model_families`, per-unit fields), not this one. This file stays the catalog of the `.als` files in this folder.

---

## Production models (in use)

| File | Defense | What it encodes (from `specs/alloy_models.json`) |
|---|---|---|
| `STT_6.als` | STT | Canonical STT. Protect at state/memory level (`hardware_protection_policy = Mem_s`). Transmitters = loads(inaddr) + branches(inreg). Per-branch resolution-minimality. **Caveat:** the per-branch minimality clause means it structurally cannot emit a two-source (in-degree ≥ 2) merge (~99.6% single-source) — see `OTB_GENERATION_GAP.md`. |
| `SPT_6_oneLP.als` | SPT | SPT one-leak-point. Operand-granularity protection + untaint flows + STLF de-protection (inaddr too). Transmitters add stores(inaddr). Requires exactly one insecure point. |
| `Recon_6.als` | Recon | Dynamic/parameterized protection: `Mem_s` minus state reachable backward through data-dependence from speculative loads. Does NOT carry `rf_from_most_recent_writer` (grep 2026-11-08: only the STT_6 family has it; proposal P1 in `wiki/state/ALLOY_MODEL_CHANGES.md`). Where both real recon bugs reproduced (OTB/getOldestTaint + STL/SLF bypass). |

## Variants (per-defense experiments; see JSON for full notes)

| File | Base | What it changes |
|---|---|---|
| `STT_6_core.als` | STT_6 | Staged-enumeration base: idx/IX ordering removed, length "up to 6", driver turns on EVERY minimality clause (RO+RI) → maximally-minimized leak cores. Stage 1 of the two-stage build. See `STAGED_ENUMERATION.md`. |
| `STT_6_multisource.als` | STT_6 | Minimality relaxed per-branch → aggregate; admits in-degree ≥ 2 merges. The dedicated OTB / getOldestTaint two-source-merge model. Built, not yet enumerated. |
| `STT_6_stl.als` | STT_6 | Speculation source switched from unresolved branches to unresolved-address stores (Spectre-v4 store-bypass). Control-flow speculation off. Added 2026-10-28 (Anna-approved). See `wiki/design/STL_SPECULATION.md`. |
| `STT_6_commitsplit.als` | STT_6 | Commit boundary split into C (committed prefix) / U (uncommitted suffix) / D (don't-care middle); laxest leaking boundary; every unresolved instruction must individually sustain the leak. Added 2026-10-29 (Anna-approved). See `wiki/design/COMMIT_BOUNDARY.md`. |
| `STT_6_pincommit.als` | STT_6 | Adds `rf_from_most_recent_writer` fact ("Option A"). Contract experiment; never enumerated. |
| `STT_6_modified_protset.als` | STT_6 | STT at operand granularity (not state) + `rf_from_most_recent_writer` + first_uncommitted fallback. Contract experiment; never enumerated. |
| `SPT_6.als` | — | Base/full SPT, operand-granularity (`hardware_protection_policy = Instruction.operands`). No one-leak-point restriction; no store transmitters. |
| `SPT_6_oneLP_noSTLF.als` | SPT_6_oneLP | Minus store-to-load-forwarding paths — leakage back to loads+branches only. Control to isolate STLF as the leak source. Never enumerated. |

## Symlinks (aliases — not separate models)

| Link | → Target | Note |
|---|---|---|
| `STT_6_interleave.als` | `STT_6.als` | Chain interleaving is a parsexml/config knob, not a separate enumeration. |
| `STT_all.als` | `STT_6.als` | Alias used for the larger 250k campaign naming. |
| `SPT_6_full.als` | `SPT_6.als` | Alias of the full SPT model. |

## Legacy / superseded (dev lineage — park or reference only)

`STT_5.als`, `STT_5_ld_xmit_only.als`, `STT_4.als`, `STT_4_new.als`, `STT_3.als`, `STT_2.als`, `LP-only-STT_3.als` — STT development history, all superseded by `STT_6`.

## `old_models/` (archive subdir)

Unmaintained development-history archive (not individually catalogued, not enumerated): `bigmodel.als`, `MCMtso.als`, `model_edge.als`, `model_overloaded.als`, `model.als`, `no_RI_add_spacers.als`, `RS_noRIRO.als`, `STT_edge.als`, `stt_final.als`, `STT.als`, `STTcommitted.als`, `STTcommittedsp_kind_flaggedxmit.als`, `STTcommittedsp_kind.als`, `STTcommittedsp.als`, `STTold.als`, `STTsp.als`, `test_generation_newest.als`, `test_ordering{,2,3,4}.als`, `testordering.als`.

## Related models that live ELSEWHERE (not in this folder)

The bug-synthesis OTB/channel probes referenced in `specs/alloy_models.json` (`STT_6_alupath`, `STT_6_otb`, `STT_6_otb2`, `STT_6_pendsquash`) are tier `bugsynth` and live under `bugsynth/models/`, not here.

## Non-model files

- `util/` — Alloy utility modules imported by the models (ordering / boolean helpers).
- `execution-theme.thm` — Alloy Analyzer visualizer theme for these models.
