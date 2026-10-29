# Audit: the four `*_full` run configs (2026-10-28)

Scope: `results/STT_6_invisispec_full_spectre`, `STT_6_invisispec_full_futuristic`, `STT_6_speclfb_full`, `STT_6_cleanupspec_full` (run_config.jsonc + README.md). Audit only: nothing edited, no gem5 run, no git writes. Build sources read from cafe2 `/work/amulet/amulet-gem5-*_AE-v1.1/configs/{common/Options.py,common/Scheme.py,example/se.py,ruby/Ruby.py,ruby/MESI_Two_Level.py}`; old launchers read from cafe2 `/tests/simspect/results/` (they are not on the Mac). 12-minute budget, so items marked UNVERIFIED were not chased.

## Verdict

The configs are sound to launch with two caveats that matter. (1) `filter.xmit_kind: "ld"` is really ignored on the pipeline path, and `gem5.checker` overrides every kind, so these runs will put ALL STT_6 transmitters (ld + br_x + other_x, the full testset, not a 1500/mode sample) through `check_footprint.py`. The old campaigns ran ld-only samples. (2) The CleanupSpec "launcher's inject_stalls" claim is false: `run_cleanupspec_residue.sh` has no stall injection. It ran `check_ld_cleanupspec.py` directly on whatever `<stage-dir>` it was given, so whether the old residue run had the 5000-cycle resolve stall depends on that dir (UNVERIFIED). Every flag exists and parses with its value, and the `--scheme` last-wins override works for Futuristic.

## Sync

The local and cafe2 copies are byte-identical (md5 match on all 8 files).

## Flag existence / parse (per build)

- **InvisiSpec** (`Options.py`): `--ruby` :117, `--l1d/l1i/l2_size` :104-106 (strings), `--l1d/l1i/l2_assoc` :108-110 (int), `--abs-max-tick` :120, `--scheme` :319 is `type="choice"` with `UnsafeBaseline, FuturisticSafeFence, SpectreSafeFence, FuturisticSafeInvisibleSpec, SpectreSafeInvisibleSpec, "2"`, so both scheme names parse. `--needsTSO` :324 and `--allowSpecBuffHit` :326 are int. `--L1_TBEs/--L2_TBEs/--DC_TBEs` are in `Ruby.py:83-88` (default 2). `--apply-spec-eviction-patch` is in `Ruby.py:91` and is correctly NOT passed. `se.py:348` maps `"2"`. The SimSpect hooks `--branch-ann-file/base` and `--fnc-commit-stall-pc/cycles` are at :307-313.
- **SpecLFB** (argparse `Options.py`): `--l2cache` :180, sizes :184-186, assocs :188-190, `--scheme` choices `["unsafebaseline","Speclfb","2"]` :567-573. `se.py:333-334` maps `"2"` to `Speclfb`, so the explicit `--scheme=Speclfb` is redundant but harmless. `--needsTSO` :560 is left unset, as before.
- **CleanupSpec**: `--scheme` :319 is a free string, accepted and ignored (matches the config's comment). `--scheme_invisispec` :322 is a choice that includes `UnsafeBaseline`. `--scheme_cleanupcache` is in `Scheme.py:9-14` and includes `Cleanup_FOR_L1L2`. `Scheme.py:76-83` confirms that `Cleanup_FOR_L1L2` = rand_L2 + cleanupLQExecd + cleanupLQInflight + l1d_mshr_tracking + random_repl_L1 + L2Inv + InternalInterferenceHit, which is a superset of `Cleanup_FOR_L1` (:70-75). The claim checks out.
- **Geometry takes effect under Ruby.** `configs/ruby/MESI_Two_Level.py` (both IS and CS builds) reads `options.l1i_size/assoc`, `l1d_size/assoc`, `l2_size/assoc`, `L1_TBEs`, `L2_TBEs`. I did not see `DC_TBEs` in the grep window (it is presumably the directory controller's; UNVERIFIED).

## `--caches` + `--ruby`

There is no conflict. `gem5_common.py:run_gem5` always emits `--caches`. In both Ruby builds `se.py` (IS :299-341, CS :307-346) does `if options.ruby: Ruby.create_system(...)` and only the `else` branch calls `CacheConfig.config_cache`, so `--caches` is inert under `--ruby`. The only other use is the fastmem fatal (IS :263, CS :267), and that needs `--fastmem`, which no config passes. Dropping `--l2cache` for CleanupSpec is correct for the same reason: the grep found no `options.l2cache` in `MESI_Two_Level.py`.

## Env bridge (`pipeline.py:_build_gem5_env` :555-628)

- `extra_args` are 0x1f-joined into `SIMSPECT_GEM5_EXTRA` and appended LAST in `run_gem5` (`gem5_common.py:200-202`), after `--scheme=2` and `--abs-max-tick`. So optparse/argparse last-wins makes `--scheme=FuturisticSafeInvisibleSpec` and the CleanupSpec `--abs-max-tick=3000000000` win. The Futuristic override works.
- `check_footprint.scheme_name_from_args` (:66-76) applies the same last-wins rule to pick the criterion actor. I assumed it receives the extra args, since this audit saw only the function and not its caller (UNVERIFIED). Before launch, confirm that the Futuristic run's per-record `actor_mode` = futuristic.
- `fnc_commit_stall_cycles: 0` is falsy, so no env var is set and no `--fnc-commit-stall-*` is emitted. That matches every old launcher (all `"0"`).
- `branch_ann_enable: true` sets `SIMSPECT_BRANCH_ANN_ENABLE=1`, which matches all old launchers.
- `checker: check_footprint.py` requires `criterion`, or the run aborts (:624-626). All 4 set it, and the paths resolve repo-relative. `_checker_for` (:304-312) is used at every dispatch site (:749, :930, :962, :1111), so check_footprint IS selected on all gem5 paths. `make run` → `testrun.py:155` → `pipeline.py gem5`, so the selection holds there too.
- `debug_flags` are comma-joined into `SIMSPECT_GEM5_DBG_FLAG`, with Commit auto-added. The new configs carry the old launchers' flag sets (IS-compound/CS: O3PipeView,LSQUnit,Squashed,ProtocolTrace; SpecLFB: O3PipeView,LSQUnit,Speclfb,Cache).

## Hooks vs the old launchers

- **Resolve stall.** `pipeline._inject_stalls` (:397-426) sets mispredict branches to 5000, the xmit branch to 0, and correctly_not_taken to grid value 0 for `points:[0]`. That matches `inject_stalls` in `run_invisispec.py:35-49`, `run_invisispec_compound.py:31-42` and `run_speclfb.py:35-49`. `sweep.enabled:true` is required for this, as the comment says. **Exception:** `run_cleanupspec_residue.sh` has no inject step (see the verdict).
- **Test selection (unintended difference).** The old launchers staged ld-kind only, `--n 1500` per mode. The new configs run the whole testset and every kind, because `filter` is never read (no `filter`/`xmit_kind` filter in `pipeline.py` or `testrun.py`). This has three consequences. br_x/other_x transmitters will be judged by a footprint criterion, and whether `check_footprint` gives non-ld transmitters a meaningful verdict is UNVERIFIED. Results are not directly comparable to the old campaigns' counts. Runtime is much larger.
- **InvisiSpec.** The comparison against `_compound` is mostly right. Its "differs only by explicit L1I/L2/TBE flags" overstates it: the TBEs equal the defaults (2), but `--l1i_assoc=4` (default 2) and `--l2_assoc=16` (default 8) are real geometry changes, not restated defaults. The plain `STT_6_invisispec` campaign ran classic caches (no `--ruby`) with flags O3PipeView,LSQUnit only, which is the documented and intended difference.
- **SpecLFB.** The old run had no extra args: L1D 64kB/2, L1I 32kB/2, no L2. The new run uses L1D 1kB/2, L1I 32kB/8, `--l2cache` L2 2MB/16. These are intended and documented. The L1D shrink is flagged in the config as UNTESTED on this classic build.
- **CleanupSpec.** Same flags as the `.sh` minus the inert `--l2cache`, plus `--l1i_assoc=4`, `--l2_assoc=16` (defaults 2/8) and explicit TBEs=2. `--abs-max-tick=3000000000` replaces `SIMSPECT_GEM5_MAX_TICK`. `jobs` 4 is the same. The stall-injection difference is noted above.

## Suggested pre-launch checks (for Anna)

1. Decide whether all kinds should run. If ld-only is wanted, the pipeline needs a real `filter.xmit_kind` implementation (a pipeline change), or the runs must be staged ld-only.
2. Check the CleanupSpec residue stage dir (`CLEANUPSPEC_RESIDUE_REVIEW.md`) to find out whether its anns had injected stalls.
3. On a 1-test smoke run, confirm that the Futuristic `actor_mode` and the `extra_args` order appear in the gem5 cmdline (`m5out/config.ini`).
