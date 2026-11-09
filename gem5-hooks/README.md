# gem5 hooks — durable backup of the instrumentation

The gem5 builds live in **`/work/*` inside the `gem5_dev` docker container**, outside this repo.
The "hooks" are the modifications SimSpect inserts into each gem5 build (the instrumentation every
result depends on — see CLAUDE.md "reproduce EXACTLY as the config did"). They were surviving only
as uncommitted/untracked changes in an **ephemeral container**; this directory captures them durably.

**Captured 2026-10-20.** These are snapshots, not a live mirror — re-capture after changing a hook.

## What's here (per build)

| build (container path) | base | capture | hook files |
|---|---|---|---|
| `/work/stt` | git, cwfletcher/stt @ `e3283b9` | `stt/stt.patch` (`git diff`, excl `build/`) + `se_exp.py`, `se_slowcomm.py` (untracked) | o3 commit/cpu/fetch/iew, pred bpred_unit, MESI/MOESI `.sm`, se.py, Options.py |
| `/work/stt-dbg` | git, cwfletcher/stt @ `e3283b9` | `stt-dbg/stt-dbg.patch` + `se_exp.py`, `se_slowcomm.py` | same family as stt (debug build) |
| `/work/gem5-spt` | git, FPSG-UIUC/SPT @ `0d2be0f` | `gem5-spt/gem5-spt.patch` + `se_exp.py`, `se_slowcomm.py` | o3 commit/cpu/fetch/iew, pred bpred_unit, se.py, Options.py |
| `/work/amulet-repo` | git, sith-lab/amulet @ `c871bdf` | `amulet-repo/{analyze_gadgets,gen_stt_tests}.py` (untracked gen scripts) | SPEC/gadget tooling only |
| **`/work/gem5-recon-modded`** | **`/work/gem5-recon` (no git — the BASE, per owner)** | `gem5-recon-modded/recon-modded_{src,configs}.diff` (`diff -ruN recon recon-modded`) | **pcstate (arm/generic/x86), o3 commit/cpu/fetch/iew/lsq_unit/store_set_annot, pred bpred_unit + BranchPredictor.py** — the BTB-override / Recon instrumentation |
| `/work/gem5-recon` | **no git — treated as the BASE** | not captured (it is the reference) | — |
| `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1` | no git (AMuLeT AE artifact) | `amulet-InvisiSpec/simspect_hooks.diff` (`diff -ruN` pristine vs hooked, 2026-10-28) | SimSpect cache-event hooks: SLICC peek/doTransition codegen, CacheMemory, TBETable, x86 TLB, ROB squash, Sequencer SB, AbstractController LLC-SB, LSQ squash |
| `/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1` | no git (AMuLeT AE artifact) | `amulet-CleanupSpec/simspect_hooks.diff` (2026-10-28) | SimSpect cache-event hooks: same Ruby set as InvisiSpec + LSQ cleanup decisions (`cleanup_skip`/`cleanup_done`) |
| `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1` | no git (AMuLeT AE artifact) | `amulet-SpecLFB/simspect_hooks.diff` (2026-10-28) | SimSpect cache-event hooks: classic BaseCache fill/evict/inv, tags LRU touch, LFB refillBlocks, ROB squash |
| **SimSpect-STL** | `/work/gem5-recon-stl` (built 2026-10-30) | `stl/apply_stl_hooks.py` (anchor-based inserter) + `stl/stl_hooks_vs_gem5-recon-modded.diff` (the applied diff; `stl_hooks_vs_gem5_v22.0.0.2.diff` is the older upstream reference, before the 2026-10-30 barrier/alias fixes) + `stl/stl_hooktest.py` (control-run driver) | o3 `iew.{hh,cc}` store address-generation hold, `mem_dep_unit.{hh,cc}` prediction override, `BaseO3CPU.py` params, `Options.py` + `se.py` flags `--stl-ann-file` / `--stl-store-stall-cycles` / `--stl-alias-pred`. Built into `/work/gem5-recon-stl` only; controls pass. See `wiki/design/STL_SPECULATION.md`. |
| `/work/gem5-recon-ruby3` (2026-11-08) | copy of `/work/gem5-recon-modded` src/configs (0 diff), built `PROTOCOL=MESI_Three_Level` | `recon-ruby3/build_ruby3.sh` + `recon-ruby3/se_ruby_vs_se.diff` (new `configs/example/se_ruby.py`, approved 2026-11-08) | same hooks as recon-modded; ReCon per the authors (`--ruby --scheme=2 --allow_leaked`) |
| `/work/stt-master` (2026-11-08) | cwfletcher/stt @ `5bf4110` (tarball) | `stt-master/stt_worktree_vs_e3283b9.diff` (= `/work/stt`'s full hook diff, applied with `patch -p1`, all hunks exact) + `stt-master/build_stt_master.sh` | same as stt; E3 build |
| `/work/sdo` | git, cwfletcher/sdo @ `5d058fd` | clean (no hooks) | — |

## Key fact: Recon base vs change (per owner, 2026-10-20)

**`gem5-recon` is the base; `gem5-recon-modded` is the change.** Neither is a git repo, so the
"modded" hooks are captured as a plain diff of modded **against** recon (`recon-modded_src.diff`,
`recon-modded_configs.diff`). To reconstruct the modded build: start from a copy of `gem5-recon`
and apply those diffs. `gem5-recon` itself is the reference build — we do not have its upstream
baseline, and per the owner it is treated as the base, not re-diffed.

## Re-applying a hook set

- **git builds** (stt / stt-dbg / gem5-spt): from a clean checkout at the base commit above,
  `git apply gem5-hooks/<build>/<build>.patch`, then drop the `se_exp.py` / `se_slowcomm.py` into
  `configs/example/`.
- **recon-modded**: copy `/work/gem5-recon`, then `patch -p0` (or `-p1`, check the headers) the two
  `recon-modded_*.diff` files over `src/` and `configs/`.

## Re-capturing (after editing a hook)

Run in the container (`make cafe`), then stream the tarball to this dir. The one-shot used on
2026-10-20 is reproducible from `claudelog.md` (entry: gem5-hook backup). TODO: fold this into a
`scripts/sim capture-hooks` subcommand so it is a single command, not an ad-hoc pipe.

## SimSpect cache-event hooks (v1 2026-10-28, v2 2026-11-07; amulet InvisiSpec / CleanupSpec / SpecLFB)

**v2 (current, 2026-11-07):** the approved fixes plus the extra fields and events; diff `amulet-<build>/hooks_v2_vs_v1resolve.diff` (from the v1+resolve snapshot), verify `verify/run_all_verify_v2.sh` + `verify/check_v2_trace.py` against reference binaries from `verify/make_refs.sh`. Spec, results and backups: [`wiki/design/SIMSPECT_HOOKS.md`](../wiki/design/SIMSPECT_HOOKS.md). The v1 notes below still describe the base layer.

Print-only hooks that emit `O3PipeView:simspect:...` lines (cache fills, evictions, invalidations, coherence changes, replacement touches, defense-buffer and cleanup events, squashes) under the existing `O3PipeView` flag. Full spec: [`wiki/design/SIMSPECT_HOOKS.md`](../wiki/design/SIMSPECT_HOOKS.md). These three builds have no git, so the capture is a `diff -ruN` of every touched file against its pristine copy (`amulet-<build>/simspect_hooks.diff`). The earlier branch-force + fnc-commit-stall hooks in these builds are NOT in these diffs (they predate them and are still uncaptured; the pristine tarballs below include them as the base).

- Pristine sources: `/work/amulet/backups/<build>-pre-simspect-hooks-20261028.tgz` (cafe2 container). InvisiSpec/CleanupSpec tarballs extract in the build root (paths `src/...`); the SpecLFB one extracts in `src/`. Pre-hook binary: `build/<ISA>/gem5.opt.pre-simspect-hooks-20261028` in each tree.
- Re-apply: from the build root, `patch -p1 < amulet-<build>/simspect_hooks.diff`, then `gem5-hooks/verify/build_simspect_hooks.sh <build>` (scons -j12; log `/work/amulet/rebuild_<build>_simspect_hooks_20261028.log`).
- Verify: `gem5-hooks/verify/run_all_verify.sh` (all cases) / `verify_simspect_hooks.py` (one case; see the wiki page, "How to verify"); hand gadgets `verify/uv6x.s`, `verify/uv6dep.s`; annotation maker `verify/mkann.py`.

## SimSpect resolve hooks (2026-10-30, all 8 hooked builds)

BR resolve lines (`predict_force`, `resolve_hold/drop/release/bcast`, `resolve_visible`), forced target 1 = predict not-taken, and the release waking the CPU. Full spec and verification: [`wiki/design/RESOLUTION_HOOKS.md`](../wiki/design/RESOLUTION_HOOKS.md).

- Generator: `resolve/apply_resolve_hooks.py <gem5_root>` (anchor-based, idempotent). Rebuild + backup: `resolve/rebuild_resolve_hooks.sh <build>`.
- Captured diffs: `<build>/resolve_hooks.diff` (live files vs the originals in `/work/simspect_backups/resolve-hooks-20261030/<build>-src.tgz`). ⚠️ For amulet-InvisiSpec and amulet-CleanupSpec the `iew_impl.hh` hunk also contains about 31 lines from the concurrent hooks-v2 session's edits (2026-10-30 19:38–19:48), because the diff is taken against the pre-resolve original. Only the hunks marked `SimSpect resolve hooks` / `SimSpect resolve wake` are from these hooks.
- Binaries per build: `build/<ISA>/gem5.opt.pre-resolve-hooks-20261030` (before), `.resolve-print-only-20261030` (edits 1-3), `gem5.opt` (edits 1-4).
