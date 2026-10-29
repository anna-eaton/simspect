# Audit sweep, 2026-10-28 (15 parallel read-only audits)

Launched at about 16:24 with a hard cap of about 12 minutes each. Each audit writes its own file in this directory. A missing or partial file means that agent hit the time cap; rerun it from the prompt topic below. None of these audits edited code, configs, specs, `.als` or gem5; they only read.

| file | what it audits |
|---|---|
| `hooks_invisispec.md` | InvisiSpec SimSpect hook diff: behavior change, attribution, missed sites |
| `hooks_cleanupspec.md` | CleanupSpec hook diff: every cleanup event mapped, cleanup_done, restore victim |
| `hooks_speclfb_and_uv6.md` | SpecLFB hook diff + the "second spec load isUnsafe=0" claim |
| `check_footprint_review.md` | `check_footprint.py`, gem5_common additions, pipeline `gem5.checker` path |
| `criteria_provenance.md` | every quote in `specs/leakage/{invisispec,speclfb,cleanupspec}.json` vs the PDFs |
| `full_configs.md` | the four new `results/STT_6_*_full*` configs: flags exist, parse, match old timing hooks |
| `invisispec_flagged_events_triage.md` | DTLB repl_touch / L2,DIR coh "leaks": real vs artifact |
| `scope_claims_verification.md` | spot-check of PROTECTION_SCOPE_TABLE + paper audit build/AMuLeT claims |
| `testset_reachability.md` | can STT_6 tests reach each criterion term (eviction, split, hit/miss, L2/TLB) |
| `docs_consistency.md` | contradictions / stale text / hard-wrap violations in today's docs |
| `alloy_STT_6.md` | STT_6.als vs the STT paper + general Alloy bugs |
| `alloy_SPT_6_oneLP.md` | SPT_6_oneLP.als vs the SPT paper |
| `alloy_Recon_6.md` | Recon_6.als vs the Recon paper |
| `specs_jsons.md` | all other specs/*.json vs code, models and configs |
| `campaign_configs_defense_active.md` | does every campaign config actually activate its claimed defense |
