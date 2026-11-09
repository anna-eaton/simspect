# Eval manifest: what we run, on what, from which model

**The one place that says what the eval is.** Last refreshed 2026-11-08 17:20 PST (simspect-c8).

**Sources consolidated here** (each brief's facts were checked against the files before merging):
- the "Main models per defense" tables from `STAGE1_alloy/models/MANIFEST.md` (stl-spec);
- the eval subset of the 33-row build list in [`../findings/audits/2026-11-07/HOOK_AUDIT.md`](../findings/audits/2026-11-07/HOOK_AUDIT.md);
- the two-phase brief (twophase-spt, now deleted);
- the STL handoff in [`../design/STL_SPECULATION.md`](../design/STL_SPECULATION.md) (stl-spec);
- the SPT v2 brief (resolve-hooks) and the AMuLeT-hooks brief (hooks-v2). Both were deleted 2026-11-08 at Anna's request once their content was here.

**Where things live:**
- Machine-readable copy: `specs/defense_units.json` (each unit's `eval` object, `model_families`, `amulet_parity_runs`, `pending_rows`); the dashboard unit inspector shows the units.
- Build facts: `specs/gem5_builds.json`. Model metadata: `specs/alloy_models.json`. Catalog of every `.als`: `STAGE1_alloy/models/MANIFEST.md`.
- Edit this file and `defense_units.json` together.

**Status rule (Anna, 2026-11-08): everything is NOT RUN for this eval.** All testsets will be regenerated from the two-stage models and every campaign re-run. Earlier campaigns are listed only as reference.

## Live runs (also on the dashboard's Eval manifest page; registry `specs/eval_runs.json`)

**Weird version (3), jmp-everywhere fanout, 1% (cafe1, 2026-11-09 16:00Z, DRAFT):** `STT_6_fv2jmp` = STT_6_fv2 options with the ultimate-stt `jmp_all` table (default vocabulary + every resolved correctly-not-taken non-transmitter branch emitted as a direct `jmp`). E14 SpecLFB 1837 / 1930 hits (8 errors) vs 1825 / 1930 for STT_6_fv2 at 1%; E3 stt-master 0 / 1930 (same as fv2). So forcing jmps adds little at this sample size; jmp-shadow attribution needs the per-cause bucketing (triage agent). Configs `runconfigs/twostage_fv2_20261109/*fv2jmp*`; results cafe1 `code_20261109/results/E{14,3}_STT_6_fv2jmp__latest`.

**Ultimate STT_6_u (DRAFT model, STT_6_v2 semantics), two-stage + fanout v2, 2% sample: DONE 2026-11-09 ~22:30Z** (1,874 tests per mode = 3,748 per campaign; 93,157-program corpus; fv2 on cafe3, fv2fp on cafe1; raw hits, errors in parentheses). Row-by-row comparison with STT_6 at 1%: no bug class STT_6 misses (EVAL_MANIFEST ucompare section).

| row | STT_6_u_fv2 hits / 3748 | STT_6_u_fv2fp hits / 3748 |
|---|---|---|
| E1 Unsafe | 3734 | 3724 |
| E2 STT (recon-modded) | 68 | 1885 |
| E3 stt-master | 0 | 348 |
| E4 amulet-STT | 0 | 348 |
| E8 NDA | 25 | 547 |
| E9 DoM | 2636 | 2636 |
| E12a / E12b InvisiSpec | 3748 / 3748 | 3748 / 3748 |
| E13 CleanupSpec | 96 (26) | 106 (26) |
| E14 SpecLFB | 3519 (26) | 3520 (26) |

**E6 on ultimate Recon_6_u_base (gem5-recon-ruby3, authors' setup, base Stage-2 options), 1% DONE:** 26 hits / 1,932, 0 errors; the first 20 traced are all R-SA-9 (also hit on classic E2 20/20). 2% top-up running on cafe2.

**Two-stage STT_6 fanout v2, 2% sample: DONE 2026-11-09 ~15:00Z** (1,872 tests per mode = 3,744 per campaign; superset of the 1% sample below; raw hits, untriaged except as noted in the 1% table; errors in parentheses).

| row | STT_6_fv2 hits / 3744 | STT_6_fv2fp hits / 3744 |
|---|---|---|
| E1 Unsafe | 3731 | 3703 |
| E2 STT (recon-modded) | 88 | 1882 |
| E3 stt-master | 0 | 357 |
| E4 amulet-STT | 0 | 359 |
| E8 NDA | 44 | 650 |
| E9 DoM | 2602 | 2602 |
| E12a InvisiSpec Futuristic | 3744 | 3744 |
| E12b InvisiSpec Spectre | 3744 | 3744 |
| E13 CleanupSpec | 91 (16) | 91 (16) |
| E14 SpecLFB | 3546 (16) | 3544 (16) |

Next step: hit bucketing per row with the existing diagnostics (`bucket_hits.py` + `diag_*`) so known causes (S1, R-SA-13, R-SA-9/A2, UV1, UV4, UV6/walk-order, jmp-shadow, SL-1, R-SA-14) separate from NEW.

**2% hit bucketing: DONE 2026-11-09 (bucket-fv2).** Each campaign has its buckets in `diagnostics/buckets/<mode>/<kind>/` and `summary.json`: cafe2 for fv2, cafe3 for fv2fp, under `/tests/simspect_alloy_20261108/code_20261109/results/<row>_STT_6_<t>__latest/`. Diagnostics live in `STAGE3_gem5/triage/diag/` (README section "Fanout-v2 diagnostics"). Trace-based evidence comes from faithful batched reruns (`STAGE3_gem5/triage/rerun_hits_evidence.py`; workdirs deleted per batch; scratch in `/tests/simspect_alloy_20261108/bugwork/bucket_fv2/` on cafe1/2/3). Counts are hit tests (stem × mode). A hit is bucketed only when its rerun reproduced it with the campaign's offending signature. **Ruby reruns (InvisiSpec, CleanupSpec) are not bit-identical to the campaign runs** (E12a fv2fp inst-042604: 196 vs 207 hook events, stable across reruns), so 18 E13 and 10-12 E12a hits did not reproduce and stay NEW.

| row | testset | hits | known buckets | NEW | NEW examples / what they are |
|---|---|---|---|---|---|
| E1 Unsafe | both | 3731 / 3703 | control, not bucketed | — | — |
| E2 STT | fv2 | 88 | A2 recon_stlf_bypass 64, R-SA-8 OTB oldest-taint 19 | 5 | ld inst-086556 both modes and inst-081976 not_taken: OTB tests where gem5 says the transmitter is `isTainted=0` (lost taint, not R-SA-8's release); br_x inst-052473 both modes |
| E2 STT | fv2fp | 1882 | R-SA-13 1832, A2 26, R-SA-8 19 | 5 | ld inst-086854 both modes, inst-081976 taken; br_x inst-052473 both modes |
| E3 stt-master | fv2 / fv2fp | 0 / 357 | S1 xmm4 357 | 0 | — |
| E4 amulet-STT | fv2 / fv2fp | 0 / 359 | S1 xmm4 359 | 0 | — |
| E8 NDA | fv2 | 44 | R-SA-18 NDA forwarded producer 42 (known_pending, Q6) | 2 | inst-086088 both modes (2 producers on the slice; the lcbound agent's store-forward stem) |
| E8 NDA | fv2fp | 650 | R-SA-13 628, R-SA-18 20 | 2 | inst-086088 both modes |
| E9 DoM | fv2 / fv2fp | 2602 / 2602 | dom_xmit_store_forward 2602 (known_pending, criterion R-SA-18/Q6) | 0 | every ld hit is store_forward, the same 2602 as E1 |
| E12a InvisiSpec Fut. | fv2 | 3744 | UV1 3384 | 360 | 348 br_x with no UV1: DTLB fill by a seq with no pipeview record + D-1 + store events (inst-000042, -000082, -000095); likely the triage §2 store-actor artifact, unconfirmed; 12 did not reproduce (inst-002408, -009985) |
| E12a | fv2fp | 3744 | UV1 3386 | 358 | same 348 br_x pattern; 10 did not reproduce |
| E12b InvisiSpec Spectre | fv2 / fv2fp | 3744 / 3744 | UV1 3396, D-1 DTLB 348 | 0 | — |
| E13 CleanupSpec | fv2 | 91 (16 err) | UV4 split 39 | 52 | 17 ld `unattributed` installs, all mispredict_taken (inst-005142, -005789, -015602, -015954, -018481); 16 br_x whose evidence is UV4 (the canonical diag is ld-only); 18 did not reproduce (inst-009280, -054084, -072971); 1 E→M upgrade by a squashed store-like U (inst-029763 taken; no RMW in this vocab). **Root-caused 2026-11-09 (bug-investigate-e13new):** 29 = UV3/CS-EM via the harness padding RMW (H-PAD; the "no RMW" premise is wrong: `00 00` past `.text` decodes as `add %al,(%rax)`); the 18 non-reproducing hits are a TMPDIR-length stack shift (H-STK), not Ruby nondeterminism; the 7 non-padding ones look like UV4 (inst-009280 confirmed). SOURCE_AUDIT_CLEANUPSPEC_SPECLFB.md round 6 |
| E13 | fv2fp | 91 (16 err) | UV4 split 39 | 52 | same shape (unattributed 15, EM 3) |
| E14 SpecLFB | fv2 | 3546 (16 err) | UV6 3085, jmp-shadow 134, walk-order 48 (known_pending) | 279 | 274 carry the `replayed_after_safe(jmp_in_shadow)` tag (with uv6_first in 265) (inst-012796, -013826, -038066); 2 have only that tag (inst-035848, -075754); inst-055160 both modes = SL-1 `unsafe1_filled` |
| E14 | fv2fp | 3544 (16 err) | UV6 3126, jmp-shadow 133, walk-order 48 | 237 | same tag pattern (inst-012796, -014276, -003208); inst-055160 SL-1 |

New diagnostics: `diag_stt_xmm4_skip` (S1), `diag_recon_oldest_taint` (R-SA-8 on fanout_v2 OTB-transmitter tests, from bug-investigate-e2new), `diag_recon_sse_load_producer` (R-SA-13; twin-held path plus gem5 STL_CHECK paths), `diag_nda_forwarded_producer` (R-SA-18 NDA), `diag_dom_xmit_store_forward` (DoM criterion), `diag_invisispec_uv1`, `diag_invisispec_d1_dtlb`, `diag_invisispec_store_actor` (0 matches, not installed), `diag_speclfb_uv6`, `diag_speclfb_jmp_shadow`, `diag_speclfb_walk_order`, `diag_speclfb_nonload_footprint` (0 matches, not installed). Not written: R-SA-14 (its effect is masked, and DoM hits are all store_forward) and SL-1 (inst-055160 only; left NEW). Open DECIDEs are in URGENT_TODO.

**Ultimate STT_6_u_fv2 vs STT_6_fv2, 1% sample (bug-investigate-ucompare, 2026-11-09):** both corpora restricted to `sample_keep(stem, 0.01)` (STT_6_u_fv2 cafe3 = 966 tests per mode, 679 ld + 287 br_x; STT_6_fv2 cafe2 = 965 per mode, 668 ld + 297 br_x); hits = `issued_in_window` summed over both modes and kinds (errors in parentheses). The corpora are different programs, so compare rates and hit classes, not stems. Scratch + evidence: cafe2/cafe3 `/tests/simspect_alloy_20261108/bugwork/ucompare/` (`stlf_E2_*.json`, `stlf_E8_*.json` from `STAGE3_gem5/triage/recon_stlf_check.py` on every 1% ld hit; cited trace `trace_E8_inst-038175_not_taken/`).

| row | STT_6_fv2 hits / 1930 (ld+br_x) | STT_6_u_fv2 hits / 1932 (ld+br_x) | hit classes (1%) |
|---|---|---|---|
| E1 Unsafe | 1926 (1336+590) | 1930 (1358+572) | control, saturated |
| E2 Recon-STT | 54 (54+0) | 38 (38+0) | same 3 classes in both: A2 signature (tainted+speculative load forwarded from a store, ready before the held branch) old 42 / u 26 records; a tainted, `store_forward`, no-forward-line class ready 3 cycles after the probe's earliest held-branch visible, old 11 / u 11 (old = exactly bucket-fv2's 6 NEW stems per mode); `isTainted=0` (R-SA-9 shape) old 1 / u 1 |
| E3 stt-master | 0 | 0 | none |
| E4 amulet-STT | 0 | 0 | none |
| E8 NDA | 32 (32+0) | 21 (20+1) | ld: every hit forwarded from a store, `isTainted=0 isSpeculative=1` (R-SA-18), old 32/32, u 20/20. br_x: u-only `inst-038175` (not_taken), also R-SA-18, see below |
| E9 DoM | 1336 (1336+0) | 1358 (1358+0) | every ld test hits in both (warm-L1 criterion DECIDE) |
| E12a InvisiSpec Futuristic | 1930 | 1932 | saturated in both |
| E12b InvisiSpec Spectre | 1930 | 1932 | saturated in both |
| E13 CleanupSpec | 52 (50+2) (8) | 41 (40+1) (14) | same footprint shapes: hits whose offending items are L1D+L2 `under_clean` old 40 / u 32 stem-modes, L1D-only `under_clean` old 12 / u 9 (from the raw records' `offending`; not re-attributed to UV4/CS-1 since no traces are kept) |
| E14 SpecLFB | 1825 (1313+512) (8) | 1824 (1335+489) (14) | near-saturated in both (ld 97.6% u vs 97.2%, br_x 85.0% vs 86.2% not_taken) |

**Verdict: STT_6_u finds no new bug class.** Rates match or are lower (E2 2.0% vs 2.8%, E8 1.1% vs 1.7% of tests), and every u hit falls in a class the STT_6 corpus also produces, except one hit whose *shape* only the new model generates: E8 br_x `inst-038175` (not_taken). Its program stores to word A at `pc0` (last committed), opens the window at `pc1`, re-loads A at `pc2` inside the window, and feeds that value to the transmitter branch `pc3`. The trace shows the speculative load `sn:561` (0x401c3a) logging `STL_CHECK isTainted=0 isSpeculative=1` and then `Forwarding from store idx 262` at tick 2626000, ready at 2627000; the dependent `jb` (0x401c55, `sn:572`) squashes mispredicted at 2675500 while the window branch 0x401c35 is held until 5124000. That is R-SA-18 (NDA forward skips the delay) with a branch transmitter instead of a load. The shape (committed store, then an in-window re-load of the same operand before the transmitter) occurs in 1/287 u br_x tests and 0/571 STT_6_fv2 br_x tests at 2%, so it is the instance-based protection admitting a store-then-reload shape that STT_6's location-based set drops. It is not a new bug. No other u-only class was found. Not checked: E13 UV4/CS-1 attribution of the u hits (no kept traces); the E2 "ready 3 cycles after visible" class is shared and belongs to queue row 19.

**Two-stage STT_6 fanout v2, 1% sample: DONE 2026-11-09 13:38Z** (965 tests per mode per campaign, both modes = 1,930; raw hits by each row's checker, untriaged except where noted; configs `runconfigs/twostage_fv2_20261109/`; results cafe2 `/tests/simspect_alloy_20261108/results_fv2/<row>_STT_6_fv2__latest`, FP set on cafe3 `.../code_20261109/results/<row>_STT_6_fv2fp__latest`).

| row | build | STT_6_fv2 hits / 1930 (errors) | STT_6_fv2fp hits / 1930 (errors) | what the hits are (so far) |
|---|---|---|---|---|
| E1 | recon-modded scheme 0 (Unsafe) | 1926 | 1911 | control |
| E2 | recon-modded scheme 2 (STT) | 54 | 973 | fv2: R-SA-9 store-forward shape (inst-027890 checked); fp-only: R-SA-13 SSE loads (agent, 121/121 of the first batch) |
| E3 | stt-master | 0 | 192 | fp-only = S1 xmm4 (31/31 checked; xmm3 control 0/3) |
| E4 | amulet-STT (parity) | 0 | 194 | fp-only = S1 xmm4 (97/97 checked) |
| E8 | recon-modded scheme 1 (NDA) | 32 | 351 | fp-only = R-SA-13 (50/50 br_x checked); fv2 hits untriaged |
| E9 | recon-modded scheme 3 (DoM) | 1336 | 1336 | DoM delays only misses; warm-cache L1 hits are not leaks (criterion DECIDE, R-SA-18) |
| E12a | InvisiSpec Futuristic | 1930 | 1930 | UV1 class (untriaged) |
| E12b | InvisiSpec Spectre | 1930 | 1930 | UV1 class (untriaged) |
| E13 | CleanupSpec | 52 (8) | 50 (8) | untriaged; no RMW in this vocabulary, so no UV3/CS-EM |
| E14 | SpecLFB | 1825 (8) | 1824 (8) | UV6 / walk-order class (untriaged) |

Next: the 2% top-up (superset of this sample) is launched with `--resume` on cafe2 (fv2) and cafe3 (fv2fp); hit bucketing per row is the next triage step.

**2026-11-09 03:45 PST: current live state and the autopilot runbook are in `wiki/state/RUNNING.md`** (two-stage STT_6 fanout v2 + FP, 20 gem5 campaigns on rows E1-E4, E8, E9, E12a/b, E13, E14; ultimate-model Alloy). The 2026-11-08 notes below are history: the Recon/SPT runs there were stopped (superseded).

**Stage 1, cores, RI-only, up to 6 instructions: RUNNING since 2026-11-09 01:01Z (17:01 PST)** on cafe2's `gem5_dev` container.
- Workspace: `/tests/simspect_alloy_20261108` (`PROVENANCE_sha256.txt` lists every `.als`/script).
- tmux session `alloy_stage1_1108`. Status JSON `status/stage1_status.json` (rewritten every 60 s, with a CONTENTION flag). Logs `logs/launcher.log` and `logs/<family>__<part>.log`.
- **Families:** `STT_6_core_ri`, `Recon_6_core_ri`, `SPT_6_oneLP_v2_core_ri`, `Recon_6_stl_core`, `STT_6_stl_core`.
- **Parallelism:** each family is split into disjoint, exhaustive partitions (`proposed_twophase/partition_stage1.py`).
  - Exact sizes k = 1..4 run as one partition each.
  - k = 5 and 6 are also split by transmitter kind: one partition per kind in the leakage function, plus a `rest` partition that must be UNSAT, as a coverage check.
  - That gives 52 partitions, 48 in parallel (`launch_stage1.py`). Each has a cap of 200,000, a 24 h timeout and `-Xmx8g`.
- **Sanity check before launch:**
  - SPT v2's partitions k1 + k2 + k3 = 0 + 0 + 546, exactly the 546 resolve-hooks found at `but 3`, so the partitioning loses and duplicates nothing.
  - In the container, k1/k2 exhaust at 0 for every family.
- **Cross-checks when it finishes:**
  - `STT_6_stl_core` must total 306 (the Mac's exhaustive count).
  - Every `rest` partition must be UNSAT.
  - The old RO+RI cores (2 each for STT/Recon) must appear among the RI-only cores (RO+RI-minimal implies RI-minimal).
  - A sample of cores must concretize through parsexml.
  - Transmitter-kind mix should be compared with `testsets_latest`.
- **Watch:** the cafe2 Slurm holder job (`hold_simspect`, 18374614, 2-day limit) started 2026-11-08 ~00:49Z and expires ~00:49Z 2026-11-10 (squeue, 2026-11-09 05:00Z). Renew it (`make hold`) before it expires, so ssh access to cafe2 continues; the container itself runs under docker, not the job.

**Stage 1 results so far (2026-11-09 05:00Z; 38 of 52 partitions done, 14 running, load 21 of 64, no contention):**
- **STT_6_stl:** complete, 306 cores (exhaustive, = the Mac).
- **STT_6:** 129 cores, all at 3 instructions. Sizes 4 and 5 and k6_Loads are EXHAUSTED at 0; only k6_Branchxs is still running (3.8 h, 0 found). 129 = the earlier RI-only isolation sweep.
- **Recon_6:** 129 cores at 3 instructions; sizes 4 and 5 are 0; k6_Branchxs and k6_Loads are still running (0 found).
- **Recon_6_stl:** 858 cores at 3 instructions; sizes 4 and 5 are 0; k6_Branchxs and k6_Loads are still running (0 found).
- **SPT_6_oneLP_v2: not converging.** k3 = 546, k4 ≈ 145,000 and climbing about 10 per second, so it will hit the 200,000 cap (CAPPED, not exhaustive) around 06:30Z. The three k5 partitions have 14, 26 and 17 after 4 h; the k6 partitions have 0. Sampled k4 cores (`inst-000001`, `inst-100001`) contain no load. They are branch/ALU chains over initial-state registers ending in a `Branchx` transmitter, and they vary in resolved/committed flags, operand counts and which of the 2 register states alias. RI-only minimality pins none of those, which is where the count comes from.
- **Every finished `rest` partition is UNSAT** (coverage check holds).
- **Timing:** the 24 h partition timeout ends at ~01:00Z 2026-11-10. The holder job `hold_simspect` (18374614) expires at ~00:49Z 2026-11-10.
- **Superseded models (Anna's decisions, claudelog 2026-11-08 ~21:15):** the `rf_from_most_recent_writer` fact is authorized for `Recon_6.als`, `Recon_6_core_ri.als`, `Recon_6_stl.als` and `Recon_6_stl_core.als` but not applied yet, so the Recon_6 and Recon_6_stl runs here use the pre-fix models and must be rerun once it is applied. SPT audit S-1 Option A (`proposed/SPT_6_oneLP_v3.als`, draft) replaces v2, so the SPT run here is v2 only. STT_6 and STT_6_stl already carry the rf fact; STT_6 may still change if the instance-based protection diff (item 1) is approved.

**Stage 1.5: RUNNING since 2026-11-09 01:54Z** (tmux `alloy_stage15_1108`; `launch_stage15.py`; status `status/stage15_status.json`; results `s15/<family>/results.jsonl`).
- **Method:** each core is pinned into its production model with `stage_seed.py` and fleshed out at exactly 6 instructions, one run per core, 24 in parallel, 30 min per core.
- **Size (Anna, 2026-11-08): about 300,000 instances per family.**
  - That is split evenly over the family's cores: per-core cap = ceil(300000 / cores), e.g. STT_6_stl 981 per core.
  - If a family has more than 300,000 cores, a uniform sample of 300,000 is run (seed 20261108) at 1 per core; this is recorded in `s15/<family>/PROVENANCE.json`.
- **Scheduling:** each family starts when its Stage 1 completes. STT_6_stl started first.
- **STT_6_stl: DONE (01:58Z-02:06Z).** All 306 cores were run at 981 per core: 266,946 instances; 266 cores CAPPED and 40 EXHAUSTED (fewer than 981 programs exist). Results are in `s15/STT_6_stl/`. The other four families are waiting for their Stage 1.
- **Sanity:**
  - One STT core alone fleshes out to more than 31,000 programs in 15 min (not exhausted), so a per-core cap is required.
  - 38/38 sampled STT_6_stl Stage-1.5 instances concretize through `/tests/simspect` parsexml (2096e32a) in `stl_bypass` mode.
- **Contention (2026-11-09 01:55Z):** load hit 63-68 of 64 cores when Stage 1.5 started. Two causes: another session's gem5 campaign (`check_ld.py --jobs 16` in `/tests/simspect_fixed_20261030`), and the JVMs' many GC/compiler threads.
  - The fix: restarted with 24 jobs and `JAVA_TOOL_OPTIONS=-XX:+UseSerialGC -XX:CICompilerCount=2`; load is back to about 55.
  - Using cafe1/cafe3 would add 128 cores (setup below).
- **Next after Stage 1.5:** merge each family (dedup across cores with `STAGE2_compilation/find_duplicates.py`, then renumber into `testsets/<family>__twostage/xml`). Then Stage 2, after the vocabulary expansion.

**Using cafe1 / cafe3** (both have 64 cores and about 500 GB free; checked with sinfo 2026-11-09). Each needs a Slurm holder job before ssh works (pam_slurm_adopt). Use a distinct job name, because `scripts/sim` tracks `hold_simspect`:
1. `ssh cafe1 true` once, interactively, to accept cafe1's host key (it currently fails host-key verification).
2. `ssh sc "sbatch --account=cafe --nodelist=cafe3 -p cafe-interactive --mem=32G --time=2-00:00:00 --job-name=hold_simspect_cafe3 --wrap 'sleep infinity'"`, and the same with `cafe1`.
3. Then check whether docker and the `gem5_dev` image (or Java 17) exist there. Copy the workspace (`/tests/simspect_alloy_20261108` minus `out/`, `s15/`), and give that node its own share of families or partitions with its own status JSON (add it to `specs/eval_runs.json`).

## How the pieces connect

```
 Alloy model family            STAGE1_alloy/models/...                 which leaks exist (symbolic)
   Stage 1    core model       <model>_core*.als (RI-only; SPT too)    → minimal leak skeletons ("cores")
   Stage 1.5  production model <model>.als + pin one core (round 2)     → full instances grown around each core, cores in parallel
      ▼
 testset                       testsets*/<model>/xml/                   one XML per leak instance
      │  Stage 2: parsexml.py + compile_annotate.py (per branch mode, or stl_bypass for STL)
      ▼
 programs                      testsets*/<model>/<mode>/{asm,ann}/      .s + .ann.json per test
      │  Stage 3: one run config = gem5 binary + flags + hook state + checker
      ▼
 eval unit (one row below)     runconfigs/... or results/<x>/run_config.jsonc
      │  checker (check_ld / check_br / check_footprint / STL window checker)
      ▼
 results                       results/<results_name>__<timestamp>/<mode>/<kind>/
```

**How models, builds and run configs relate:**
- **One model family feeds many builds.** The STT_6 family is the stimulus for every row except ReCon (Recon_6), SPT (SPT_6_oneLP_v2) and OTB.
- **One row = one gem5 binary with one flag set,** so each row has its own run config and its own results directory. Rows that share the Kaxiras-group binary `gem5-recon-modded` (Unsafe, STT, ReCon, NDA, DoM, Doppelganger) differ only in flags, and they are still separate runs.
- **Copy the run config verbatim** when reproducing a hit. It carries the full hook state (branch force, unresolved stall, fnc stall); see CLAUDE.md.

**Harness additions, the same on every row:**
- the SimSpect hook flags and debug flags;
- the derived branch force, the resolve stall, and the execution-validity gate. These are on all 8 hooked builds; see [`../design/RESOLUTION_HOOKS.md`](../design/RESOLUTION_HOOKS.md) and [`../findings/bug/BRANCH_ANNOTATION_AND_FORCE.md`](../findings/bug/BRANCH_ANNOTATION_AND_FORCE.md).

**Where rows deviate from the authors' configuration:** everything else matches it, with one deliberate exception. The footprint rows E12-E14 use an amplified geometry: shrunk L1D, and InvisiSpec 2 TBEs / CleanupSpec 8 (Anna, 2026-11-08; the paper's discussion explains it). These shrunk configs are the default eval runs. AMuLeT's exact flags (the T rows below) are used only for timing numbers and for confirming bugs. **Confirmed by Anna (2026-11-08):** the taint-tracking rows (E1-E11: STT, ReCon, NDA, DoM, Doppelganger, SPT) deliberately keep unshrunk caches, because their leak test (did the transmitter obtain its data inside the window) does not depend on cache pressure; only the footprint rows shrink. **Known deviation found 2026-11-08:** ReCon is implemented in Ruby/SLICC and the authors run it with `--ruby` and the `ruby-singlecore` protocol folder (`documentation/docs/Files/email.txt:20-23`), but E6 runs classic `--caches`, where the reveal never takes effect (`wiki/findings/audits/2026-11-08/SOURCE_AUDIT_RECON.md` R-SA-1). Until that is resolved, E6 measures Recon-STT, not ReCon. **Resolved as far as the build goes (recon-ruby, 2026-11-08):** a correct ReCon build now exists, `/work/gem5-recon-ruby3` (MESI_Three_Level + `ruby-singlecore`, the authors' recipe); see E6 and "ReCon under the authors' setup (verified 2026-11-08)" below. Two things still block a ReCon result: one config line (the authors' `se.py` ships `from ruby import Ruby` commented out) and the testset, which cannot exercise the reveal.

**Checker and harness state on the AMuLeT builds** (deployed to `/tests/simspect_fixed_20261030/`, 2026-11-08, md5-verified, per hooks-v2):
- The `check_footprint` by_pc fix: it had wrongly disqualified 114/3000 InvisiSpec tests and 202 CleanupSpec records.
- CleanupSpec's ownership rule ("count as both").
- `gem5_common._unglue`: native debug-print residue no longer drops trace lines.
- Hooks v2 on all three footprint builds; every trace starts `META:hooks … ver=2:build=<name>`.

**Before the final batch:**
- `make sync`. The lc/fnc-from-Commit-trace fix (`gem5_common.fill_retire_from_commit`, 2026-11-07) is in this repo and the cafe2 fixed copy, but not yet in `/tests/simspect`.
- Every final run config needs its `sample_fraction` set. The templates `runconfigs/fixed_20261030/*_fixed_latest.jsonc` still say `0.02` from validation.
- Point every final run config's `testset_dir` / `results_name` at the regenerated testsets.
- **Grow the instruction vocabulary for the fanout (Stage 2) runs (Anna, 2026-11-08).** `wiki/design/VOCAB_TABLES.md` covers this, with decisions V1-V9. Everything beyond other_n is an approval-gated `parsexml.py` emitter change, so it must land before Stage 2 of the final batch, not during it.

**Naming:** this manifest says **Stage 1.5** for the pinned flesh-out that the briefs call "Stage 2 / round 2". That is the name in the pipeline figure and `URGENT_TODO.md` (decided 2026-11-02), because "Stage 2" already means concretization.

## ReCon under the authors' setup (verified 2026-11-08, recon-ruby)

**Builds on cafe2 (read-only survey):**
- `/work/gem5-recon`, `/work/gem5-recon-modded` and `/work/gem5-recon-stl` all have `src/mem/ruby` identical to `ruby-versions/ruby-singlecore`, with 0 differing entries (`diff -rq`); against `ruby-default` there are 17. All three `build/X86` were built `PROTOCOL = 'MESI_Two_Level'` (`build/X86/gem5.build/variables`); the ARM builds are CHI. Before 2026-11-08 no MESI_Three_Level build existed.
- `ruby-singlecore` also adds the reveal bit to MESI_Two_Level (`MESI_Two_Level-L1cache.sm`: `Reveal` event, `revealTheBit`, `readCallback(..., revealBits)`). So the existing binaries could run a Ruby reveal under `--ruby`. The authors' instructions say MESI_Three_Level, though, and their example command uses L0 options, which exist only in `configs/ruby/MESI_Three_Level.py:64-67`. The new build follows the authors.

**New build `/work/gem5-recon-ruby3`** is a copy of `/work/gem5-recon-modded` with `build/` and `m5out*` left out. Its `src` and `configs` have 0 differences from recon-modded, so the SimSpect hooks came along, and `src/mem/ruby` has 0 differences from `ruby-singlecore`. Built with `/usr/bin/scons build/X86/gem5.opt PROTOCOL=MESI_Three_Level -j 24` (script `build_ruby3.sh`, log `build_ruby3.log`, EXIT=0, 2026-11-09 02:47 UTC). There are no source edits. The one new file is `configs/example/se_ruby.py`: the authors' `se.py` with line 56 `# from ruby import Ruby` uncommented. The authors ship that import commented out (`/work/gem5-recon/configs/example/se.py:55`), so `se.py --ruby` dies with `NameError: name 'Ruby' is not defined` (se.py:224). Their own runs used `fs.py`, which imports Ruby (`fs.py:53`). We use `gem5.opt`, not their `gem5.fast`, because the checkers need DPRINTFs.

**Legitimacy of E2 (Recon-STT, scheme 2 without `--allow_leaked`, classic caches): legitimate.**
- STT's protection is CPU-side. Tainted loads are held in the LSQ (`lsq_unit.cc:2095-2104`, `delayUnit.insertTaintedLoad`), and tainted instructions in the IQ (`inst_queue.cc:1453`). Taints are kept in `secure_scheme/taint_tracker.cc`.
- The only memory-side defense state is ReCon's reveal bit and DoM's `L1_ONLY` flag. Every reveal path is gated on `cpu->allowLeaked`: the Reveal send `lsq_unit.cc:870`; the load-pair table `:946`; the reveal untaint `taint_tracker.cc:142`; NDA's allowlist `lsq_unit.cc:199`; `inst_queue.cc:1053`; `commit.cc:1050`. `L1_ONLY` is set only for `Scheme::DoM` (`lsq.cc:1442-1446`).
- So without `--allow_leaked`, no reveal bit is ever set, and classic vs Ruby does not change what STT protects.
- Measured: on 50 Recon_6 load tests, Recon-STT gave the same 2 hits (inst-021381, inst-133326) on classic recon-modded and on Ruby ruby3, with identical cache-fate counts.
- Caveat: `L1_ONLY` is handled only by classic `BaseCache` (`mem/cache/base.cc:462`), so DoM (E9) must stay on classic caches.

**Legitimacy of the checkers and hooks under `--ruby` MESI_Three_Level: valid, with the same pre-existing gate bug as classic.**
- The hooks are CPU-side: branch force (`bpred_unit.cc`), resolve stall and wake (`iew.cc`), fnc stall (`commit.cc`). No hook touches `src/mem/ruby`.
- On every validation run (5 configs, 2 samples, 484 Ruby records), `br_resolve_source=observed` and 0 records failed the validity gate.
- `check_ld` reads only LSQUnit/O3PipeView/Commit lines, which are CPU-side. Under Ruby they are the same lines: the smoke trace has 270 `Memory request … was sent`.
- The known recon gate bug (`wiki/findings/bug/recon_cache_reach_gate/README.md`, URGENT_TODO DECIDE) applies unchanged. These builds never print `successfully sent out packet(s)`, so fates are only `store_forward` / `executed_no_packet` / `never_executed`.
- Unsafe control on Ruby: 43/50 hits (s50 sample) and 21/50 (ldld50), all `store_forward` fate.
- The AMuLeT Ruby builds use hooks v2 (Ruby cache-event lines, `wiki/design/SIMSPECT_HOOKS.md`); recon-ruby3 does not need them, because `check_ld` needs no cache-event lines.

**Does the reveal fire? It is sent and marks the right address, but it never untaints anything in our tests.**
- Stats: `system.cpu.lsq0.revealRequests` (`lsq_unit.cc:381,911`), `system.cpu.taint_tracker.allowlistedTaintsFromTT` (`taint_tracker.cc:30,144`).
- Workspace `/tests/simspect_fixed_20261030/results/recon_ruby3_val/`: `run_val*.sh`, `analyze_val.py`, `summary_{s50,ldld50,revealprobe}.json`.

| sample | config | hits | revealRequests | allowlistedTaintsFromTT |
|---|---|---|---|---|
| s50 (50 random Recon_6 ld tests) | ReCon Ruby | 2 | 0 | 0 |
| s50 | Recon-STT Ruby / classic, classic + allow_leaked | 2 / 2 / 2 | 0 | 0 |
| ldld50 (50 tests with a committed LD→LD pair) | ReCon Ruby | 0 | 71 (43 stems) | 0 |
| ldld50 | classic + allow_leaked (old E6) | 0 | 71 (43 stems) | 0 |
| ldld50 | Recon-STT Ruby / classic | 0 / 0 | 0 | 0 |
| revealprobe (inst-063358, its speculative load retargeted to the revealed slot) | ReCon Ruby / classic + allow_leaked | 0 / 0 | 1 per run | 0 |

- A ProtocolTrace of the probe on ruby3 shows the Reveal reach L0 at the right address: `3042500 Seq Begin [0x34e8, line 0x34c0] Reveal`, then `3043000 L0Cache Reveal M>M [0x34e8 …]`. 0x34e8 is offset 40 in the line, which is the committed LD1's slot. Classic sends it to paddr 0 (R-SA-1).
- It does not untaint anything, because the speculative load and the transmitter execute at tick 3040000, before LD2 retires at 3042000. A reveal sent at LD2's commit is too late in a one-pass litmus. (Those probe tests are not hits under Unsafe either: the signal falls before `lc_retire`.)
- A scan of all 150,000 Recon_6 `mispredict_not_taken` tests found 1,210 with a committed LD→LD pair and **0** where a speculative load reads the revealed slot. This matches the Alloy side, where R-1 makes the reveal a no-op.

## stt-master: upstream STT master for E3 (built 2026-11-08)

- **Source:** `https://github.com/cwfletcher/stt` @ `5bf41109477e1c9c5822674afa4103e6eb16ff09`. Fetched as a tarball (sha256 `aa2281ad…4cc1c`), plus a bare clone for the log, both in `/work/stt-master-src/`. `e3283b9..5bf4110` = `18e304f fix pending squash bug` + the merge. It changes only `src/cpu/o3/iew_impl.hh` (+13/-1, in `executeInsts`): a tainted mispredicted branch now gets `hasPendingSquash(true)` instead of squashing in IEW.
- **Hooks:** `/work/stt`'s full working-tree diff vs `e3283b9` (`/work/stt-master-src/stt_worktree_vs_e3283b9.diff`: stt.patch + resolve hooks + wake edit), applied with `patch -p1`. Every hunk applied exactly, with no offset or fuzz. `se_exp.py`, `se_futuristic.py` and `se_slowcomm.py` were copied unchanged, along with the `README -> README.md` symlink that `/work/stt` has (the SConscript needs `README`).
- **Tree check:** `diff -rq` of `/work/stt` vs `/work/stt-master` (excluding build/.git) shows only `iew_impl.hh` (the upstream fix) plus untracked `README`/`parsetab.py`.
- **Build:** `python2 scons-2.5.1 build/X86/gem5.opt -j16`, the same as `gem5-hooks/resolve/rebuild_resolve_hooks.sh` (`/work/stt-master/build_stt_master.sh`, log `build_stt_master.log`, EXIT=0). gem5.opt sha256 `ca7259637a59c3f2…5c1e`.
- **Validation** (`/tests/simspect_fixed_20261030/results/stt_master_val/`):
  - `hook_audit.py --build stt-master` vs `--build stt` (12 tests, seed 0): the check dicts are identical on all 12, including every tick. The one `resolved_correct` FAIL (inst-116576) is the same on `/work/stt`.
  - E3 sample (`testsets_sttmaster_val/STT_6_s60`, 30 ld + 30 br_x per mode, 532 records): same verdicts, 0/120 hits on both. 51 records differ in timing, all `br_x` transmitters (9 test×modes, a few cycles later). That is the expected effect of the pending-squash fix on tainted transmitter branches (`compare_e3.json`).
  - S1 xmm4 (`testsets_fpr_s1check/STT_6_fpr_xmm4`): 98/100 hits on stt-master, the same stems as `/work/stt`.
- **Interaction to decide:** the resolve-stall hook's deferred release (`iew_impl.hh`, `stallBcast` lambda) copies the *pre-fix* squash code. So a stalled (annotated) branch that is mispredicted *and* tainted still squashes from IEW instead of getting the new pending squash. The hook audit showed no difference on 12 tests. It matters only if a forced-unresolved branch's condition is tainted.

## needsTSO for E3 (Anna #14, 2026-11-08)

- **What it changes in `/work/stt`** (and in `/work/stt-master`, which has identical LSQ code):
  - Store writeback is serialized, so only one store is in flight to the cache at a time (`lsq_unit_impl.hh:1358`, `:1681`, `:1873`).
  - On an invalidation snoop that hits a load's line, the load and *all younger loads* are squashed (`lsq_unit_impl.hh:564`, via `checkSnoop` from `LSQ::recvTimingSnoopReq`, `lsq_impl.hh:419,433`).
  - The other uses (`:629`, `lsq_unit.hh:1063`) are InvisiSpec validation/expose paths, inactive under STT.
  - It touches no taint, delay, or STT logic.
- **Ours vs the authors':** our `se.py` glue forces `cpu.needsTSO = False` whenever `--scheme` is given (`configs/example/se.py:333`). The authors' `sample_scripts/run_stt.sh:19-20` uses `--needsTSO=1 --threat_model=Spectre --STT=1 --implicit_channel=1`, with `--caches --l2cache`. Second deviation found: our E3 runs have **no `--l2cache`**.
- **Expected effect on our tests:** none on taint or verdicts.
  - In single-core SE with classic caches nothing else sends invalidation snoops, so the TSO load squash never fires.
  - The one-store-in-flight rule only delays the drain of committed stores, so `lc`/`fnc` retire times and store-to-load forwarding (from SQ entries) are unchanged in most tests.
  - Small timing shifts are possible in tests with several committed stores.
  - x86 is TSO, so `needsTSO=1` is the architecturally faithful setting.
- **Recommendation:** match the authors, `needsTSO=1` and `--l2cache`.
  - This needs a config-glue change: set `needsTSO` from a new option instead of hard `False` at `se.py:333`, and add `--l2cache` to E3's `extra_args`.
  - Then re-check the E3 60-stem sample for identical verdicts.
  - Low risk, and it removes a deviation reviewers could question.

## The eval set (approved by Anna, 2026-11-08)

Anna: "ok im down with those builds. make sure we're gonna run all the stts separately." So each STT implementation is its own row with its own results. Roles (Anna, 2026-11-08): E3 gives SimSpect's STT results; E4 is only for comparing with AMuLeT; E2 stays its own row. Every row is **NOT RUN**, and its testset will be the two-stage regeneration of the listed family.

| # | defense | gem5 binary | flags that make it this defense | model family | checker | run config | blocker / known causes / prior runs (reference only) |
|---|---|---|---|---|---|---|---|
| E1 | Unsafe (control: every test should leak) | `/work/gem5-recon-modded/build/X86/gem5.opt` | `--scheme=0` (no shadows, `decode.cc:685`) | STT_6 | check_ld / check_br | to create (copy E2's, scheme 0) | none; never run |
| E2 | STT, Kaxiras-group implementation ("Recon-STT") | same | `--scheme=2`; control + store shadows (`decode.cc:686-695`). Classic `--caches` is legitimate: verified 2026-11-08 that STT's protection is CPU-side only and that every ReCon memory-side path is gated on `allowLeaked` (see "ReCon under the authors' setup"). On a 50-test Recon_6 sample, classic and Ruby MESI_Three_Level gave the same hits | STT_6 | check_ld / check_br | `runconfigs/fixed_20261030/STT_6_reconmodded_fixed_latest.jsonc` (set `sample_fraction`); optional Ruby cross-check `runconfigs/recon_ruby3/STT_6_reconstt_ruby3.jsonc` | **known real bug A2 dominates:** a load the defense marks tainted and speculative takes store-forwarded data and completes before the branch resolves. In round 4 (2% sample), 91/94 load tests hit, and all 185 test×mode runs were A2. Classifier: `STAGE3_gem5/triage/recon_stlf_check.py` + `triage/diag/diag_recon_stlf_bypass.py`. Prior: `results/STT_6_reconmodded_fixed_latest__20261108_012818` |
| E3 | STT, upstream (cwfletcher) implementation, Spectre: **SimSpect's STT results** | **`/work/stt-master/build/X86/gem5.opt`** (cwfletcher/stt @ `5bf4110`, 2025-12-14, includes `18e304f` "fix pending squash bug"; built 2026-11-08). `/work/stt` (`e3283b9`) stays for reproducing old results and the A3c bug | `se.py --scheme=2`; our glue sets Spectre and `needsTSO=0`, the authors' `run_stt.sh` uses `needsTSO=1` (HOOK_AUDIT decision) | STT_6 | check_ld / check_br | `runconfigs/fixed_20261030/STT_6_sttmaster_fixed_latest.jsonc` (set `sample_fraction`); the old `STT_6_stt_fixed_latest.jsonc` = `/work/stt` e3283b9 | needsTSO decision; resolve-stall vs pending-squash DECIDE (see "stt-master" below). Validation 2026-11-08: hook_audit identical to `/work/stt` on 12 tests; E3 60-stem/mode sample same verdicts (0/120 hits both); S1 xmm4 98/100 on both. Prior (all labelled **e3283b9**): 0 hits in rounds 2 and 4 (`results/STT_6_stt_fixed_latest__20261108_012818`) |
| E4 | STT, AMuLeT's build: **AMuLeT comparison only** | `/work/amulet/amulet-gem5-STT_AE-v1.1/build/X86/gem5.opt` (MESI_Two_Level) | AMuLeT's: `--ruby --needsTSO=1 --STT=1 --implicit_channel=1 --threat_model=Futuristic`, TBEs 256, L1D 32kB/8, L2 2MB/8, `--cpu-clock=2GHz --sys-clock=2GHz --access-backing-store` (`executor.py:208-250`, `benchmark_all.sh:51-53`) | STT_6 (sound but incomplete for Futuristic; the Futuristic model is parked) | check_ld / check_br | `runconfigs/amulet_parity/run_config_STT_6_amuletstt_amulet_parity.jsonc` | **unblocked 2026-11-08** (Anna approved the glue fix): the `se.py` glue now honours `--threat_model`/`--needsTSO`/`--STT`/`--implicit_channel` (diff `gem5-hooks/amulet-STT/se_py_threatmodel_glue_20261108.diff`). Smoke test with `--ruby`: rc 0, `config.ini` `threatModel=Futuristic`, `needsTSO=true`. Never run on a testset. Prior: `STT_all_amulet` (05-28, pre-fix, superseded) |
| E5 | STT on SPT's STT-like sub-mode | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | unknown | STT_6 | check_ld / check_br | none | **unverified** that gem5-spt has an STT-only sub-mode; include only if it exists |
| E6 | ReCon (the authors' setup) | **`/work/gem5-recon-ruby3/build/X86/gem5.opt`** (PROTOCOL MESI_Three_Level, `src/mem/ruby` = `ruby-singlecore`, recon-modded hooks; built 2026-11-08) | `--scheme=2 --allow_leaked --ruby` + the authors' example cache geometry `--l0d_size=65536 --l0i_size=65536 --l0d_assoc=8 --l0i_assoc=8 --l1d_size=2MB --l1d_assoc=16 --l2_size=16MB --l2_assoc=32 --cacheline_size=64` (`documentation/docs/Files/email.txt`, their FS SimPoint command); config script `se_ruby.py` (approved, Anna #11). The old classic E6 (`gem5-recon-modded --caches --allow_leaked`, e.g. `results/Recon_6__20260602_122016`) is **relabelled Recon-STT** (Anna #16, 2026-11-08). The reveal can only mark the line at paddr 0 (R-SA-1), its only untaint path (`taint_tracker.cc:142`) needs that bit, and the 248 classic `--allow_leaked` validation runs show `allowlistedTaintsFromTT` = 0 | Recon_6 | check_ld / check_br | `runconfigs/recon_ruby3/Recon_6_recon_ruby3_authors.jsonc` | **blocker (2026-11-08):** `se_ruby.py` and the authors' cache sizes are approved (Anna #11/#12); remaining: Recon_6 cannot exercise the reveal: 0 of 150,000 not_taken tests have a speculative load from a committed-revealed address, and one-pass litmus timing puts the transmitter before LD2 commits anyway, so on this testset ReCon = Recon-STT by construction (validation: the reveal fires and marks the right address, `allowlistedTaintsFromTT` = 0 everywhere). Also open: `Recon_6.als` lacks `rf_from_most_recent_writer`, the same skeleton gap SPT v2 fixes (v2-1); no Recon v2 exists. Prior: `Recon_6__20260602_122016` (pre-fix) |
| E7 | ReCon OTB (getOldestTaint) | `gem5-recon-modded` | as E6 | OTB: decided 10-30 that OTB comes from Stage-2 interleave on the two-stage output; for now, DECIDE whether to use bugsynth `STT_6_otb2` + interleave | check_ld | none | OTB testset decision; OTB has never come out of enumeration |
| E8 | NDA (code enum `Delay`): **DROP (recommended, Anna's 2026-11-08 rule: only defenses whose implementation is by their own authors)** | `gem5-recon-modded` | `--scheme=1` (`lsq_unit.cc:194-211`; email.txt:18) | — | — | none | **Authorship:** NDA is Weisse, Neal, Loughlin, Wenisch, Kasikci (Michigan; `quail/sources/papers/weisse-2019-nda.pdf` p1). The `--scheme=1` code is the Kaxiras group's reimplementation, "NDA-P": Doppelganger §6 says "we implement NDA-P, STT, and DoM in a common simulation infrastructure using the gem5 simulator, version 22", and ReCon §6.1 says it "shares implementations for NDA, STT, and RECON". So it is by the ReCon authors but not by NDA's authors, the same status as Recon-STT (E2). Reinstate if "same authors as ReCon" is the rule rather than "official" |
| E9 | DoM (Delay-on-Miss): **KEEP (official)** | `gem5-recon-modded` | `--scheme=3`; classic caches only (`L1_ONLY` is handled only by the classic `mem/cache/base.cc:462`) | STT_6 (no DoM model yet) | check_ld / check_br | to create (E2's, scheme 3) | **Authorship:** Sakalis, Kaxiras, Ros, Jimborean, Själander (Uppsala; `sakalis-2019-dom.pdf` p1). Kaxiras and Själander are ReCon co-authors (`aimoniotis-2023-recon.pdf` p1). This tree is that group's gem5-v22 implementation (Doppelganger §6; email.txt:18 lists scheme 3 = DoM), not the 2019 artifact, and it has **no value predictor** (no VTAGE code in `src/cpu/o3`). So it is DoM without the paper's VP part. Never run |
| E10 | Doppelganger (on STT): **KEEP (official)** | `gem5-recon-modded` | `--scheme=2 --address_prediction`, no `--ruby` (email.txt:19, "the predictor with the default parameters as it was in the paper"). The paper also evaluates NDA+D (`--scheme=1`) and DoM+D (`--scheme=3`) (Kvalsvik 2023 abstract p1) | STT_6 (no model yet) | check_ld / check_br | to create | **Authorship:** Kvalsvik, Aimoniotis, Kaxiras, Själander (`kvalsvik-2023-doppelganger.pdf` p1). Pavlos Aimoniotis wrote both ReCon and this repo, and says it contains Doppelganger Loads (email.txt:40). Open: a test exercises the predictor only if it trains it first (DECIDE). NDA+D falls with E8 |
| E11 | SPT (SpectreSafeFence + DDIFT) | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | `--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3`; ours: `needsTSO=0`, classic caches; the authors' `run_spt.py:56` uses `--needsTSO=1 --ruby` (HOOK_AUDIT decision) | **SPT_6_oneLP_v2** (draft, awaiting sign-off) | check_ld / check_br; **store transmitters (`str`) have no checker** (check_ld's fallback scores the store's complete tick) | `runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc` (set `sample_fraction`; point at the v2 regen) | approve v2; needsTSO/Ruby decision; store-transmitter criterion. **Expect these v2 hits to classify, not count as bugs:** constant-derived transmitters (~10% of v2 instances; P3 not applied on purpose), and hits made public by unfed reads (P5). Tools: `STAGE3_gem5/triage/spt_cond_slice.py`, `spt_taint_probe.py`, `triage/diag/`. Prior: round 4 ran the OLD model; all 341 hit tests were model or concretization artifacts (`results/SPT_6_oneLP_fence_fixed_latest__20261108_012818`) |
| E12a | InvisiSpec, Futuristic (AMuLeT's mode) | `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` (hooks v2) | shrunk eval config: `--ruby --scheme=FuturisticSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1`, L1D 1kB/2, TBEs 2 (AMuLeT's own amplification, Table 6 row 3), L1I 32kB/4, L2 2MB/16 | STT_6 | check_footprint (`invisispec.json`) | `runconfigs/footprint/run_config_STT_6_invisispec_futuristic_footprint.jsonc` | P-2 open for this row (needsTSO/allowSpecBuffHit; the parity run uses 0/0). Needs a D-1 bucket (a DTLB replacement-on-hit deviation present in every hit) before results are readable. Prior: `results/STT_6_invisispec_v2hooks_futuristic__20261107` (3000 tests, UV1 in 3000 after the by_pc fix, 0 NEW) |
| E12b | InvisiSpec, Spectre (a SimSpect extra; AMuLeT did not run it) | same | as E12a with `--scheme=SpectreSafeInvisibleSpec` | STT_6 | check_footprint | `runconfigs/footprint/run_config_STT_6_invisispec_spectre_footprint.jsonc` | P-2, P-3 open. Prior: `..._v2hooks_spectre__20261107` (UV1 2995/3000 after the fix, 0 NEW) |
| E13 | CleanupSpec | `/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` (hooks v2) | shrunk eval config: `--ruby --needsTSO=0 --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2`, L1D 2kB/4, `--L1_TBEs=8` (decided; never 2), L2/DC TBEs 2, L1I 32kB/4, L2 2MB/16 | STT_6 (0 RMW instructions, so UV3 is unreachable; see C1) | check_footprint (`cleanupspec.json`, with the ownership rule "count as both") | `runconfigs/footprint/run_config_STT_6_cleanupspec_footprint.jsonc` | must re-run: the ownership rule and the by_pc fix both postdate the prior run. Debug flags `O3PipeView` only (a native DPRINTF glues lines). Prior: `results/STT_6_cleanupspec_v2hooks__20261107` (TBE 8 arm: 38 UV4; 2 hits now victim-only) |
| E14 | SpecLFB | `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/build/X86/gem5.opt` (hooks v2) | shrunk eval config: `--scheme=Speclfb --caches --l2cache`, L1D 1kB/2, L1I 32kB/8, L2 2MB/16, Tournament predictor | STT_6 | check_footprint (`speclfb.json`) | `runconfigs/footprint/run_config_STT_6_speclfb_footprint.jsonc` | P-5 open for this row's predictor (BiModeBP keeps the branch force working; smoke-tested). Findings to bucket: UV6 (the first load), walk-order (DECIDE), and **jmp-shadow, a new real bug** (`wiki/findings/bug/speclfb_jmp_shadow/README.md`; whether the paper counts it is Anna's DECIDE). Prior: `results/STT_6_speclfb_v2hooks__20261107` (1300/1500 and 1452/1500 hits) |

**Cache setup (Anna 2026-11-09):** `gem5.cache_setup: random` (per-test hot/cold, chosen from sha256(seed, stem), recorded on every record) for CleanupSpec (E13) and SpecLFB (E14); warm everywhere else; the parity configs (T2, T3) keep AMuLeT's setting (today `warm`; AMuLeT itself differs per build, DECIDE in `URGENT_TODO.md`); not a standard dimension. E13 now runs `--L2_TBEs=3` (was 2): with 2, cold panicked CleanupSpec's cleanup (`L2cache.sm:308`) on 326/590 tests; 3 is the smallest crash-free value measured, and warm hits are unchanged (13/590, same stems, at 2/3/4/8/16). Details: `wiki/design/SIMSPECT_HOOKS.md` "Cache setup strategies".

Paths starting `testsets_latest/`, `runconfigs/fixed_20261030/` and `results/` are in the fixed-harness copy on cafe2, `/tests/simspect_fixed_20261030/` (the run configs are also in this repo, as are `runconfigs/footprint/` and `runconfigs/amulet_parity/`).

**Proposed provenance (not yet implemented):** record in each campaign the trace's `META:hooks ver=` / `build=`, plus the checker revision (`check_footprint.py` / `cleanupspec.json` md5 or git sha). Both changed on 2026-11-08, so results are not comparable across those versions.

**Not in the eval set** (optional or retired). Row numbers refer to HOOK_AUDIT's build list.
- SPT variants #21-#25 (Futuristic, InvisibleSpec, ImpFlow=Ignore, disableUntaint).
- The June latency experiments #15/#16/#26 (`se_slowcomm.py`, `se_exp.py`); the STT race leaks only appear there.
- DoM+ReCon #6; STT+Doppelganger+bypass #10; InvisiSpec on classic caches #28.
- STT-Futuristic on `/work/stt` #18 (unreachable, and parked by Anna 2026-11-07).
- stt-dbg #19; the unhooked recon control #11; SDO #33 (never built).

## AMuLeT-parity runs: timing and bug confirmation only

These rows are not the eval; the default runs are E12-E14 on the shrunk configs. They have the same priority as the eval (hooks-v2 brief).

**Rule for every T row:** run only from `runconfigs/amulet_parity/`, and check `config.ini` against `wiki/findings/audits/2026-10-28/full_configs.md` before trusting any number. The shrunk eval configs must never produce a timing number (STATUS urgent todo, 2026-11-08).

| # | experiment | build | run config | measures | status |
|---|---|---|---|---|---|
| T1 | InvisiSpec-Futuristic at AMuLeT parity | E12's binary | `runconfigs/amulet_parity/run_config_STT_6_invisispec_futuristic_amulet_parity.jsonc` (32kB/8, TBEs 256, `--needsTSO=0`, 2GHz, `--access-backing-store`) | tests per hour per core, and wall time to the first UV1 detection; plus re-running each E12 NEW bug at parity | **RUN 2026-11-09 on cafe1 (dedicated), STT_6_fv2, 1500 tests: UV1 0/1500** (every test hits, but on squashed-store L1D fills + DTLB touches, not UV1; see 'Timing results' below) |
| T2 | CleanupSpec at AMuLeT parity | E13's binary | `…/run_config_STT_6_cleanupspec_amulet_parity.jsonc` (TBEs 256) | the same, for UV4; plus E13 NEW bugs at parity | **RUN 2026-11-09 on cafe1: UV4 first at test 47 (130 CPU-s total, 52 gem5 CPU-s); 44/4000 hits, all UV4.** Cold variant T2c: UV4 at 47, 49/3000. UV3 unreachable (no RMW in STT_6_fv2) |
| T3 | SpecLFB at AMuLeT parity | E14's binary | `…/run_config_STT_6_speclfb_amulet_parity.jsonc` (BiModeBP) | the same, for UV6 and jmp-shadow; plus E14 NEW bugs at parity | **RUN 2026-11-09 on cafe1: warm UV6 first at test 47 (77 CPU-s), jmp-shadow at 105 (172 CPU-s); cold variant T3c: UV6 at test 1 (3 CPU-s), jmp-shadow at 7 (21 CPU-s)** |
| T4 | amulet-STT at AMuLeT parity | E4's binary | `…/run_config_STT_6_amuletstt_amulet_parity.jsonc` | the same. AMuLeT's STT finding KV3 (a speculative store reaching the D-TLB) is outside our STT leakage function, so there is no detection target | **RUN 2026-11-09 on cafe1: 0/1000 hits (no target); 2.18 total CPU-s per test** |
| T5 | AMuLeT's own campaigns on the same machine (baseline) | the four AMuLeT builds | AMuLeT repo `/work/amulet-repo` @ c871bdf, `src/benchmark_all.sh` with its own YAMLs | AMuLeT's tests per hour and time to detection on cafe2, so T1-T4 are compared on the same hardware, not with the paper's numbers | **BLOCKED 2026-11-09:** needs Python 3.11 + AMuLeT's pip deps; downloading them was refused by the permission classifier (external code). Exact plan below; Anna's OK needed |

- **Confirm new bugs at parity.** Before claiming any NEW footprint bug, re-run its test once at parity (the T1-T3 configs), so a reviewer can't call it an artifact of the shrunk caches. jmp-shadow already reproduced on a pristine build.
- **Even at parity the comparison is not identical, so state this beside every T number.**
  - AMuLeT starts each test with a filled or flushed L1D, uses a 1-page sandbox (128 pages for STT), and decides relationally across 140 inputs.
  - We start each test with a cold cache and decide from one trace.

### Timing results: SimSpect at AMuLeT parity on STT_6_fv2 (timing-amulet, 2026-11-09)

**Setup.** Machine: cafe1 `gem5_dev` (64 cores, dedicated, nothing else running; load about 18 from these runs alone). Testset: two-stage `STT_6_fv2` (cafe2 `/tests/simspect_alloy_20261108/testsets_twostage/STT_6_fv2`, 107,601 (mode, stem) pairs with both `.s` and `.ann.json` when the order was drawn at 11:40 UTC). Configs: `runconfigs/amulet_parity_fv2/T{1..4}_STT_6_fv2.jsonc`, path-only copies of `runconfigs/amulet_parity/` (testset_dir, results_name, instruction_tables). T2c/T3c add one key, `gem5.cache_setup: cold`, because AMuLeT starts CleanupSpec and SpecLFB tests from flushed sandbox lines (`fu-2025-amulet.pdf` p9). `config.ini` of each run matches the AMuLeT column of `wiki/findings/audits/2026-10-28/full_configs.md`: L1D 32768/8, L2 2MB/8, TBEs 256, sys clock 500 ps, DTB 64, `access_backing_store=true`, needsTSO false (true for STT), BiModeBP on SpecLFB.

**Method.** One fixed order for every defense: the sorted (mode, stem) list shuffled with `random.Random(20261109)` (`order_seed20261109.tsv`). One `pipeline.py gem5` call per test, 6 at a time (`STAGE3_gem5/timing/timing_driver.py`). Per test: gem5 CPU = user+sys of the gem5 process (os.wait4 via `STAGE3_gem5/timing/sitecustom/sitecustomize.py`, no source edits); total CPU = the whole pipeline.py subtree (assemble, link, checker, gem5). Hits are attributed by `STAGE3_gem5/timing/classify_hits.py`, which reuses existing rules: UV1 = an in-window `L1D:evict req=specld`; UV4/UV5/CS1 = `cleanupspec_skip_evidence.py` unchanged; UV6/walk-order/jmp-shadow = the SpecLFB triage tags (`speclfb_analyze.py`, vendored from the 2026-11-07 triage). "Tests to first" is the position in the order; "expected" is (N+1)/(K+1) for K detections in N tests. For K=0 the bound is "> N tests".

| row | defense, cache start | N | hits | CPU-s per test (gem5 / total) | target | first detection: test #, cum. gem5 / total CPU-s | K of N | expected tests (gem5 / total CPU-s) to first |
|---|---|---|---|---|---|---|---|---|
| T1 | InvisiSpec-Fu, warm | 1500 | 1500 | 0.45 / 2.07 | UV1 | not found | 0 | > 1500 (> 679 / > 3101) |
| T2 | CleanupSpec, warm | 4000 | 44 | 1.09 / 2.71 | UV4 | #47 inst-085661 (nt), 51.7 / 129.7 | 44 | 88.9 (96.6 / 241.3) |
| T2c | CleanupSpec, cold | 3000 | 54 (41 harness errors) | 1.17 / 3.65 | UV4 | #47 inst-085661, 58.1 / 180.9 | 49 | 60.0 (70.0 / 219.3) |
| T2/T2c | CleanupSpec | | | | UV3 | not reachable: STT_6_fv2 has no RMW transmitter | 0 | — |
| T3 | SpecLFB, warm | 1500 | 17 | 0.53 / 1.64 | UV6 | #47 inst-085661, 24.8 / 77.1 | 15 | 93.8 (49.8 / 153.7) |
| T3 | SpecLFB, warm | | | | jmp-shadow | #105 inst-055537, 55.5 / 172.5 | 2 | 500 (266 / 820) |
| T3c | SpecLFB, cold | 1500 | 1463 (21 harness errors) | 0.65 / 2.78 | UV6 | #1 inst-046298, 0.68 / 3.05 | 1380 | 1.09 (0.71 / 3.03) |
| T3c | SpecLFB, cold | | | | jmp-shadow | #7 inst-027147, 4.8 / 20.7 | 480 | 3.1 (2.0 / 8.7) |
| T4 | amulet-STT | 1000 | 0 | 0.51 / 2.18 | none (KV3 out of scope) | — | 0 | — |

- Throughput (tests per core-hour, total CPU): T1 1742, T2 1326, T2c 986, T3 2198, T3c 1294, T4 1652.
- Hit attribution: T2 44/44 UV4. T2c 49 UV4, 1 E→M upgrade (`EM_upgrade_squashed`), 4 unattributed (first at #841, inst-015843 taken; not yet looked at). T3c also has walk-order (first #2). Harness errors: T3c 21 and T2c 41 tests refused by cache_setup ("expected 1 prologue mfence, found 2"); not gem5 failures.
- **T1 caveat (needs a look):** all 1500 InvisiSpec hits are squashed `req=st` L1D/L2 fills plus DTLB touches (60-hit sample), and 182/200 sampled hits have no lc instruction, so the window starts at tick 0. None is UV1. UV1 needs a spec load to evict a live line, and at 32 kB/8 our tests never fill a set; AMuLeT fills the L1D with lines that conflict with the sandbox before each InvisiSpec test (p9), and `cache_setup` has no such mode (it is refused on InvisiSpec). So T1 measures nothing comparable yet.
- **Contended cross-check (cafe2, load about 115/64, 6 workers, partial, stopped when cafe1 came up):** the same tests are first (UV4 #47, UV6 #47, jmp-shadow #105), and CPU per test is 1.6-2x higher (T1 0.77 vs 0.45 gem5 CPU-s), so cafe2 CPU times are not usable. Data: cafe2 `results_fv2/T{1..4}_STT_6_fv2__timing/`.
- **AMuLeT's numbers, paper only (not measured here):** Table 4, p9, 100 parallel instances on a 128-core EPYC (p8): "Avg. Detection Time (sec.)" InvisiSpec 2.1, CleanupSpec 1.1, SpecLFB 1.6, STT 10371; throughput 630 / 2592 / 2595 / 34 test cases per second. In the code that number is campaign wall time divided by the total violation count of all 100 instances (`src/benchmark.py:267-268`, `avg_wall_time/total_violations`), so it is a rate, not a time to first detection, and it counts violations of any kind. With about one core per instance it is roughly 210 / 110 / 160 / 1.04M core-seconds per violation (derived, not measured). That is the same kind of number as our total CPU-s / K: CleanupSpec UV4 247 (warm) and 224 (cold); SpecLFB UV6 164 (warm) and 3.0 (cold).
- Where: cafe1 `/tests/simspect_alloy_20261108/results_fv2/T*_STT_6_fv2__timing_cafe1/` (`results.jsonl`, `classes.jsonl`, `first_detection.json`, `config.ini`, `driver.log`, hit traces); copy on cafe2 `/tests/simspect_alloy_20261108/timing/from_cafe1/`. Launchers: `timing/cafe1_launch.sh` (cafe1), `timing/launch.sh` + `chain.sh` (cafe2).

**T5 plan (blocked; Anna's OK needed).** AMuLeT's fuzzer needs Python 3.11 with `unicorn pyyaml types-pyyaml numpy toml iced-x86 protobuf==3.20 pydot xxhash` (`docker/docker_invisispec/entrypoint.sh`). Neither cafe image has them, and downloading a standalone Python + those wheels into `/tests/.../timing/amulet_env` was refused by the permission classifier as external code. Steps once allowed, all on cafe1:
1. Copy `/work/amulet-repo` (289 MB) from cafe2.
2. Install Python 3.11 + the packages above into `/tests/simspect_alloy_20261108/timing/amulet_env` (no system change).
3. Copy the four YAMLs that `src/benchmark_all.sh:21-35` names and point `gem5_location`, `gem5_binary` and `gem5_se` at `/work/amulet/amulet-gem5-<D>_AE-v1.1` (build `X86_MESI_Two_Level` for IS/CS, `X86` for SpecLFB/STT). These binaries contain RevizorIPC (checked with grep), but they also carry SimSpect's print-only hooks; either accept that (hooks are off without debug flags) or rebuild pristine AE trees (hours).
4. From `src/`, run `benchmark.py -i 70 -n 200 -r 60 -c <yaml> --extra-args=<benchmark_all.sh args> -p <D> -o benchmark-out-<D>`, under a wrapper that records `RUSAGE_CHILDREN`. Report total CPU-s / violations (the same kind as our CPU-s / K) and the per-instance "First Violation (s)" column (about CPU-s to first detection when there is one core per instance).
5. Effort: about 1 h of setup once downloads are allowed. Runs take about 20-75 min each for IS/CS/SpecLFB (paper campaign times 18 min to 1 h 14 min at 100 instances). STT takes about 23 h (Table 4) and is optional.

## Pending rows (conditional on decisions; not eval rows yet)

| # | experiment | depends on | what it adds |
|---|---|---|---|
| C1 | **RMW as a disjoint corpus (DECIDED, Anna 2026-11-08).** (i) Interim: a post-processed corpus `testsets_latest/STT_6_rmw`, whose ld transmitters are value-neutral RMWs (`orq $0,(mem)`). (ii) Planned: a model variant `proposed/STT_6_rmwjmp.als` (draft, needs sign-off) that adds RMW and direct-jump kinds, pinned so every instance contains one. Runs on E13 and the STT rows, in its own row and results directory, and never mixes into the main STT_6 corpus. Being built by the hooks-v2 session | a `diag_uv3_rmw` bucket (every CleanupSpec test is expected to show UV3) | the only way the STT_6 family reaches CleanupSpec UV3; RMW load halves are already protected on every other build (checked 2026-11-08) |
| C2 | 2-core CleanupSpec: does a speculative GETX invalidating another core's copy leak? | Anna's go-ahead | tests an unverified hypothesis from the RMW study (CleanupSpec assumes RFOs are non-speculative, p8 §4) |
| C3 | SpecLFB jmp-shadow as a counted finding: a variant matrix and counterfactual as a paper figure | Anna's DECIDE (count it; contact the authors) | the evidence already exists in `/work/amulet/jmpshadow_probe/` |

## Two-stage model families (Stage 1 core → Stage 1.5 flesh-out)

**What a core file is:** not a separate model. Each `_core` file is the production model's defense block, byte-identical, plus only the Stage-1 minimality and the scope relaxation (`but 6` instead of `exactly 6`, idx symmetry-breaking removed), made by `proposed_twophase/derive_core.py`. All core files are **unapproved drafts**, including the `STT_6_core.als` prototype in `models/` (committed 2026-10-20, never signed off). Anna signs off clause by clause before any production campaign or paper number.

**Minimality (decided 2026-11-08, Anna): RI-only for every family, SPT included.** SPT can use RI-only now because SPT_6_oneLP_v2 contains the seed fix. RO+RI makes the STL cores impossible. The STT_6/Recon_6 core drafts are still RO+RI and must be re-derived; the owner is Anna's Alloy agent, and since these are `.als` drafts, per-change sign-off applies.

| family | production model (Stage 1.5 base) | Stage-1 core | Stage-1 minimality | Stage-1 result | Stage 1.5 |
|---|---|---|---|---|---|
| STT_6 | `STT_6.als` (approved) | **`proposed_twophase/STT_6_core_ri.als`** (derived 2026-11-08 by `derive_core.py --minimality ri`; differs from the RO+RI prototype `STT_6_core.als` only by the missing RO clause) | RI-only | **running on cafe2** (the old RO+RI core gave 2) | not built |
| Recon_6 | `Recon_6.als` (approved) | **`proposed_twophase/Recon_6_core_ri.als`** (derived 2026-11-08, RI-only) | RI-only | **running on cafe2** (the old RO+RI core gave the same 2 as STT, R-1) | not built |
| **SPT_6_oneLP_v2** | **`SPT_6_oneLP_v2.als`** (**APPROVED by Anna 2026-11-08**; sha256 acb1f2e2) | **`proposed_twophase/SPT_6_oneLP_v2_core_ri.als`** (draft) | RI-only | 546 at `but 3`; 5,000 (capped) at `but 4`; **full run to 6 on cafe2** | not built |
| (v2 fallback) | — | `proposed_twophase/SPT_6_oneLP_v2_core_conservative.als` | none | 546 at `but 3` | — |
| (v2, not recommended) | — | `proposed_twophase/SPT_6_oneLP_v2_core.als` | RO+RI | 6 at `but 3`; nothing in 15 min at `but 4` | — |
| (pre-v2, provenance only) | `SPT_6_oneLP.als` (sha256 713d0904, unchanged) | `proposed_twophase/SPT_6_oneLP_core_conservative.als` / `SPT_6_oneLP_core.als` | none / RO+RI | 20,000 capped / 0 (the unperturbed-seed dead end) | — |
| STT_6_stl | `STT_6_stl.als` (approved 2026-10-28) | `proposed_twophase/STT_6_stl_core.als` (draft) | RI-only (RO+RI is UNSAT by construction) | **306 cores, exhausted** at ≤6 instructions in 23 min (Mac); re-running partitioned on cafe2 as a cross-check | not built |
| Recon_6_stl | `proposed/Recon_6_stl.als` (draft) | `proposed_twophase/Recon_6_stl_core.als` (draft) | RI-only | the Mac run stalled at 858 for over 40 min; **re-running partitioned on cafe2** | not built |
| SPT STL | `proposed/SPT_6_oneLP_stl.als` (draft, derived from the pre-v2 model; generates 0) | `proposed_twophase/SPT_6_oneLP_stl_core_conservative.als` (draft) | none | UNSAT at ≤3 and ≤4: SPT's state-minimality (RS) conflicts with the alias fact; the seed fix does not help (stl-spec probe) | blocked (RS DECIDE; re-derive from v2) |
| STT_6_multisource (OTB) | `STT_6_multisource.als` | none | — | never enumerated | — |

**Stage 1.5:**
- **Not built for any family.** Anna's Alloy agent owns the two-stage ladder: `stage_seed.py` / `stage_pipeline.py` are an unwired STT prototype, and making them parallel is the open TODO.
- So every "two-stage" row is Stage-1-only so far, and **no two-stage testset exists for any defense.**

**Where the Alloy runs: the cafe2 `gem5_dev` container (decided 2026-11-08, Anna).**
- The container has Java 17 (`/usr/bin/java`, 17.0.15) and `alloy6.jar`, and `testsets_latest` was enumerated there in June.
- `run_stage1.py`'s Java and disk-guard paths are now configurable (`SIMSPECT_JAVA` / `SIMSPECT_DISK`); the Mac defaults are kept.
- Still needed: `a6CountModels.class` in `/tests/simspect/STAGE1_alloy/` (only the `.java` is there; the fixed copy has the `.class`).

**If SPT's Stage 1.5 volume is unwieldy** (its RI-only Stage 1 caps at 5,000 already at `but 4`), a scope ladder (enumerate N = 3..6 and keep the smallest distinct shapes) is the smaller but still conservative alternative.

## Testsets: what exists (all NOT RUN for this eval)

| testset | where | size | built from | use |
|---|---|---|---|---|
| two-stage regeneration of every family | — | — | the families above (SPT from v2) | **the eval's testsets; not built** (regenerate everything once the two-stage model exists, Anna 2026-11-08) |
| `testsets_latest/STT_6`, `Recon_6` | cafe2 `/tests/simspect_fixed_20261030/` | 150,000 programs per branch mode | today's exact `.als` (sha256 7a6ac4c0 / 01252c82), generated 2026-06-03 at git e298a9e | current **flat** testsets; interim stimulus only |
| `testsets_latest/SPT_6_oneLP` | same | 150,000 per mode | pre-v2 `SPT_6_oneLP.als` (713d0904) | **pre-v2, provenance only** (63% of its instances read a register past a newer writer) |
| `testsets_latest/STT_6_rmw` | same | being built | post-processed STT_6 (C1) | the disjoint RMW corpus |
| `testsets_v2sample_{cleanupspec,invisispec}` | same | 1,500 per mode | fixed-seed (20261107) samples of `testsets_latest/STT_6` | hooks-v2 samples |
| Stage-1 core corpora (`*__twophase_draft*`) | Mac `testsets/` | see the family table | draft core models | input to Stage 1.5, not tests yet. The `SPT_6_oneLP__twophase_draft*` corpora are pre-v2, provenance only |
| `testsets/STT_6`, `Recon_6`, `SPT_6_oneLP`, `STT_all`, `SPT_6_full`, ... | cafe2 `/tests/simspect/testsets/` | 5k-400k | older `.als` (hashes in claudelog 2026-11-07) | **stale, don't use** |
| `testsets/STT_6_stl` | cafe2 `/tests/simspect/testsets/` | 60 | `STT_6_stl.als` | hook test only |

Why `testsets_latest` counts as current even though `parsexml.py` changed since June: its provenance hash is 30de6b77 and today's is 2096e32a, but the diff (checked 2026-11-08) only adds three things. These testsets use none of them, and the instruction table is identical (28e77a1d):
- the STL `stl_bypass` mode;
- commit-split model support;
- a commit-boundary rule that skips interleave-inserted steps.

## Alloy models: which ones are up to date

"Current" means the file in `STAGE1_alloy/models/` is approved and the newest testset was built from exactly that file. Every approved production model is unchanged since git e298a9e (2026-06-03).

| model | role | approved? | newest testset from this exact file | pending proposals (none applied to approved files) |
|---|---|---|---|---|
| `STT_6.als` | production; stimulus for most rows | yes | flat `testsets_latest/STT_6` | P5 (a skeleton-wide unfed-read fact) would touch every model |
| `Recon_6.als` | production; ReCon | yes | flat `testsets_latest/Recon_6` | add `rf_from_most_recent_writer` (it lacks it; the same gap as SPT's v2-1) |
| **`SPT_6_oneLP_v2.als`** | **the SPT model for the final batch** | **yes (Anna, 2026-11-08)**; `specs/alloy_models.json` tier = production, `canonical_models.SPT` = v2 | none yet (3,000 scratch instances, `results/spt_v2_20261108/`); Stage 1 running | P3, P5 not applied on purpose |
| `SPT_6_oneLP.als` | pre-v2 SPT, provenance only | yes (kept unchanged) | `testsets_latest/SPT_6_oneLP` | superseded by v2 |
| `STT_6_stl.als` | STL stimulus for the STT family | yes (2026-10-28) | 60-test hook testset | `rf` vs atom-based alias fact (DECIDE) |
| `STT_6_multisource.als` | OTB variant | yes (variant) | none (never enumerated) | OTB testset decision (E7) |
| `STT_6_commitsplit.als` | commit-boundary variant | yes (2026-10-29) | 20k per mode, fixed copy | review DECIDE in `URGENT_TODO.md` |
| `proposed/Recon_6_stl.als`, `proposed/SPT_6_oneLP_stl.als`, `proposed/STT_6_shadows.als`, `proposed/STT_6_rmwjmp.als` | STL / shadows / RMW drafts | drafts | scratch only | approvals pending (stl-spec, hooks-v2) |
| NDA, DoM, Doppelganger | (no model) | — | rows E8-E10 use STT_6 (sound, incomplete) | DECIDE: write a defense block per scheme |

**SPT_6_oneLP_v2: what changed** (resolve-hooks; checked by simspect-c8 against `SPT_6_oneLP.als`: exactly these four edits, each marked `[v2-n]`, everything else byte-identical).

| | change | why | effect |
|---|---|---|---|
| v2-1 | add `rf_from_most_recent_writer`, verbatim from `STT_6.als:161-170` | only STT_6 had it; in 68% of the old SPT testset an rf edge reads a register past a newer writer, so parsexml's program is not the instance | removes only instances no register machine can realize |
| v2-2 | protection seed computed over the perturbed program: `o_p[p] - ((Inreg + Inaddr) - i_p[p].outreg.(rf_p[p]))`, and `[p]` at the call site | the old seed ignored perturbations, so removal minimality could never shrink it and the SPT core was empty | identical to the old seed when nothing is perturbed (scratch `eq_base`: 0 counterexamples), and a subset under every perturbation. So it changes no leak verdict and loses no instance; it adds instances (≥500 capped in production) and makes SPT cores satisfiable. It is **not** the A1 seed rewrite in `ALLOY_MODEL_CHANGES.md` |
| v2-3 | base clause `not secure_speculation_scheme_p[no_p]` (≥1 insecure transmitter) instead of `one_insecure_…` (exactly 1) | the skeleton form STT/Recon use; SPT alone pruned two-leaker tests | strictly adds instances; `xm` still names the one the checker scores |
| v2-4 | declassification removes only the transmitted value and its producer (`.*(~rf_p)`), not the whole rf+ddi backward cone | SPT untaints backward only through MOV, and through invertible arithmetic when all but one input is public (paper §6 "Untaint rules"; gem5-spt `rob_impl.hh:853-878`) | the protection set becomes a superset of SPT's (more tests); some hits will be SPT legitimately untainting through mov/add, which the x86 slicer classifies |

**Not included, on purpose** (Anna prefers too many tests): P3, which drops constant-derived transmitters, and P5, the skeleton-wide unfed-read fact. Both are in `ALLOY_MODEL_CHANGES.md`.

**Evidence** (`results/spt_v2_20261108/`):
- v2 is satisfiable: 3,000 instances in 2 min at `exactly 6`.
- Shape census, old → v2: stale rf 63% → 0, clean 23% → 58%, unfed read 28% → 33%, constant-derived transmitter 2.4% → 9.6%.
- Differential: ≥500 instances in both, and ≥500 gained by v2.

**"Lost" checks** (old-useful and not new-useful):
- For v2 as a whole: only v2-4 can lose an instance, through minimality. An 8 h run is on cafe2 (`/tests/simspect_fixed_20261030/triage/spt_v2/lost_cafe2.log`); a 90-min Mac run found no counterexample.
- For v2-2 alone: simspect-c8's Mac run **timed out after 4 h with no counterexample**. That is not a proof, since it never reached UNSAT; the proof is the argument (equal at no perturbation, a subset under every perturbation, monotone propagation), which resolve-hooks audited independently (`results/twophase_stage1_2026-11-03/probe_spt_seed_20261107/differential_20261108/run.log`).
- That run's log labels the model "sha 65eae944". That is the SHA-1 of the same unchanged file whose SHA-256 is 713d0904, not a different file.

## STL (store-to-load speculation): builds, per-defense scope, experiments

**What STL is here** (`STL_SPECULATION.md`):
- An older store's address is held unresolved, and the memory-dependence predictor is forced to say "no alias".
- A younger load to the same address reads the stale value. When the store's address resolves, gem5 squashes the load (memory-order violation).
- The window runs from load issue to that squash (Spectre v4).
- The opposite direction (predict alias when the addresses differ) opens no window and is only a negative control.

**Builds:**
- **Only `/work/gem5-recon-stl` has STL hooks.** It is stale: copied from recon-modded before the 2026-10-30 resolve hooks, so it has no `BR:` lines, the old-style branch force and no CPU-wake fix (HOOK_AUDIT: BORDERLINE).
  - Flags: `--stl-ann-file`, `--stl-store-stall-cycles N`, `--stl-alias-pred {no_alias,alias,off}`.
  - Schemes as on recon-modded.
  - Run config: `runconfigs/run_config_STT_6_stl.jsonc` (scheme 2, hold 5000, `no_alias`, fnc 150).
- **Every other build needs a port:** `gem5-hooks/stl/apply_stl_hooks.py <gem5_root>` plus a rebuild.

**Checker: there is no STL window checker yet.** check_ld / check_br verdicts mean nothing on STL tests (there is no `lc`, and `fnc` is the store). Until it exists, `gem5-hooks/stl/stl_hooktest.py` scores them.

**STL this round (decided 2026-11-08, Anna): the Kaxiras-group builds only.**
- Rebuild `/work/gem5-recon-stl` from today's `gem5-recon-modded`, which adds the resolve hooks.
- Write the STL window checker.
- That covers E1, E2, E6, E8, E9 and E10.
- No port to the AMuLeT builds or gem5-spt this round. **Not started; no owner yet.**

| eval row | STL in its threat model? | STL model family | can it run today? |
|---|---|---|---|
| E1 Unsafe | control | STT_6_stl | yes, on `gem5-recon-stl --scheme=0` (the control in the hook test) |
| E2 STT Kaxiras | yes (`decode.cc:686-695`) | STT_6_stl | yes, on `gem5-recon-stl` (stale); no window checker |
| E3 STT upstream | no: no store shadows (`rob_impl.hh:444-495`); a bypass leak is expected by design | STT_6_stl only as a labelled control | no hooks (not this round) |
| E4 STT AMuLeT (Futuristic) | yes (a store-load alias is a squash source under Futuristic) | STT_6_stl | no hooks (not this round) |
| E6 ReCon | yes (runs on Recon-STT's shadow tracker) | Recon_6_stl (draft) | partly: ReCon mode on `gem5-recon-stl` is not verified |
| E8 NDA, E9 DoM, E10 Doppelganger | probably (same shadow tracker; not verified in code) | STT_6_stl | on `gem5-recon-stl --scheme=1/3` (+ `--address_prediction`), untested |
| E11 SPT (Spectre configs) | no (branch-only visibility point) | — | no hooks |
| E12 InvisiSpec | Futuristic mode only (InvisiSpec Sec. IV Table I) | STT_6_stl | no hooks (not this round) |
| E13 CleanupSpec, E14 SpecLFB | yes (CleanupSpec Sec. 2.1; SpecLFB Sec. 5) | STT_6_stl | no hooks (not this round) |
| E7 OTB | n/a (two-source merge shape) | — | — |

**STL experiments done:**
- **Ultimate STT_6_u_stl two-stage, 1% (2026-11-09 18:43Z, DRAFT; cafe2 `results_stl_u/`, the stl-campaign scorer unchanged):** 488 stems (353 ld, 135 br_x; 48,017 deduped corpus, atom-based alias model). In-window ld transmitters: Unsafe 343/353, STT 0/353, NDA 0/353, DoM = Unsafe (warm-cache L1 hits; DoM criterion DECIDE). Unlike STT_6_stl (NDA 8/467, the R-SA-18 store-forward shape), the atom-alias model's corpus produces no NDA in-window transmitter in this sample.
- Hook test, 60 `STT_6_stl` tests on `gem5-recon-stl` (2026-10-30): 58/60 valid bypasses. STT sent 0/28 load transmitters in the window vs Unsafe 28/28; the `alias` and hold-0 controls gave 0 (`results/STT_6_stl_hooktest/controls/`).
- Shadows store-only + alias (2026-11-07): STT 0/32 vs Unsafe 32/32 (`results/STT_6_shadows_draft/`).
- **1% campaign on the two-stage STT_6_stl family (stl-campaign, 2026-11-09; draft: no STL window checker, stale build).** 717 sampled stems (`sample_keep(stem, 0.01)` over the 65,398 compiled `stl_bypass` stems; 467 ld + 250 br_x transmitters) on `gem5-recon-stl`, hold 5000, `no_alias`, warm caches, scored by a path-only copy of `stl_hooktest.py` (ld transmitters only). Results, logs and notes: cafe2 `/tests/simspect_alloy_20261108/results_stl/` (`RUN_NOTES.md`, `summary.json`).
  - Valid bypass: Unsafe 707/717, STT 707, NDA 694, DoM 707 (the invalid ones fail only the 16-byte `squash_ok` case; NDA also has 14 where L did not execute before release).
  - ld transmitter sent in [hold, release): **E1 Unsafe 453/467, E2 STT 0/467, E8 NDA 8/467, E9 DoM 453/467.** Agrees with the 2026-10-30 hook test (STT 0/28 vs Unsafe 28/28).
  - DoM equals Unsafe on every timing field of all 717 records. This is not a leak signal: DoM sends speculative loads as L1-only packets (`/work/gem5-recon-stl/src/cpu/o3/lsq.cc:1443-1446`) and delays only misses, and with warm caches every xmit hits L1. A DoM STL run needs cold or random cache setup plus a hit/miss-aware criterion.
  - NDA (scheme 1, `Delay` in `cpu.hh`) candidate leaks, 8 stems, timings identical to Unsafe: inst-005328, inst-005911, inst-006285, inst-020279, inst-021314, inst-021955, inst-030235, inst-063118 (in inst-020279 the xmit's address register comes straight from the bypassing load). **Root-caused 2026-11-09 (bug-investigate-ndastl): all 8 are R-SA-18.** In each, the bypassing load is store-forwarded from an older resolved store, and the forward path skips NDA's delay. The 451 stems where L goes to memory send 0 (SOURCE_AUDIT_RECON.md R-SA-18 'gem5 check').
  - br_x transmitters (250) are not scored by the smoke-test scorer.

## Decisions

**Decided (Anna, 2026-11-08):**
- Scheme 1 = NDA.
- Regenerate every testset once the two-stage model exists; everything is NOT RUN.
- Stage-1 minimality: RI-only for every family.
- STL this round: the Kaxiras-group builds (rebuild `gem5-recon-stl`, write the STL checker).
- SPT seed fix (now inside v2).
- Alloy runs on the cafe2 container.
- Footprint rows run shrunk caches; AMuLeT parity is only for timing and bug confirmation (P-1).
- CleanupSpec TBEs: 8 for the eval, 256 for parity, never 2.
- amulet-STT glue fixed, so E4 is unblocked (P-4).
- STT roles: E3 = SimSpect's STT results; E4 = AMuLeT comparison.
- RMW as a disjoint corpus (C1).
- Comparisons use AMuLeT's flags as the reference.

**Also decided (Anna, 2026-11-08, later):** SPT_6_oneLP_v2 is the SPT model; it stays in `models/`; delete the briefs once their content is here; start every Alloy run now, at 6 instructions; grow the vocabulary before the fanout runs.

**Open:**
- **Models:**
  - (SPT v2 approved; the cafe2 "lost" check on v2-4 is still running, for the record);
  - P3 (proposed: no);
  - P5, the unfed-read fact for all models;
  - give `Recon_6.als` the rf fact;
  - approve each core draft clause by clause, and re-derive the STT_6/Recon_6 cores RI-only;
  - NDA / DoM / Doppelganger defense blocks.
- **Pipeline:**
  - build and parallelize Stage 1.5, then regenerate;
  - set `sample_fraction` for the final batch;
  - `make sync` before the final batch.
- **Checkers:**
  - a criterion for store transmitters (E11 `str`);
  - the InvisiSpec D-1 bucket;
  - the SpecLFB walk-order rule;
  - whether jmp-shadow counts in the paper, and contacting the authors (C3).
- **Configs:**
  - P-2 (InvisiSpec needsTSO/allowSpecBuffHit for the eval rows);
  - P-3 (keep E12b, Spectre);
  - P-5 (SpecLFB predictor for the eval row);
  - the eval rows' clock (they run gem5's 1 GHz default; parity runs 2 GHz);
  - needsTSO / Ruby for E3 and E11.
  - **ReCon (recon-ruby, 2026-11-08):** `se_ruby.py` approved (#11) and the authors' cache sizes kept (#12). Still open: (c) a ReCon stimulus that can exercise the reveal (a committed pair, then a speculative load that issues after LD2 commits), because Recon_6 never does. The old classic runs are relabelled Recon-STT (#16).
  - **stt-master:** the pending-squash mirror in the resolve-stall hook is decided and done (#13; see "stt-master").
- **STL:**
  - who rebuilds `gem5-recon-stl` and writes the checker, and the checker's design;
  - approve `Recon_6_stl`;
  - SPT STL's RS rule (exempt the alias location / drop RS / skip);
  - `rf` vs atom alias fact;
  - `STT_6_shadows`;
  - whether the forced memory-dependence prediction counts as "the predictor".
- **Other:**
  - how OTB tests are produced (E7);
  - whether gem5-spt has an STT sub-mode (E5);
  - the Doppelganger training stimulus (E10);
  - C2.

## Later: AMuLeT on the defenses it never tested

This is Anna's urgent STATUS todo of 2026-11-08, planned for after the eval.

**The goal:** run AMuLeT itself, with its own parameters, on every SimSpect defense AMuLeT never tested: E1, E2, E3, E6, E8, E9, E10, E11, and the STL build.

**What each needs:**
- AMuLeT's µarch-trace extraction ported into that build (check whether our v2 hooks can stand in for it);
- the contract AMuLeT would use for that defense (ARCH-SEQ for STT-like defenses, CT-SEQ for footprint-like ones; AMuLeT §3.1 p5);
- a parity config taken from that build's own authors, where AMuLeT has none.

**Status:** not planned; write the plan before any run.
