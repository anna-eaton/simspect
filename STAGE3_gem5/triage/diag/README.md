# Fixed-harness diagnostics (2026-11-07)

Canonical source for the `diagnostics/` folders of the fixed-harness campaigns on cafe2 (`/tests/simspect_fixed_20261030/results/<campaign>/diagnostics/`). Copy the files a campaign needs into its folder, plus the evidence JSON written by the triage tools in `STAGE3_gem5/triage/`, then run `python3 bucket_hits.py --xml-dir <testset>/xml`. Buckets land in `diagnostics/buckets/<mode>/<kind>/<cause>.txt` (one line per test: stem, tab, reason).

`bucket_hits.py` is the per-results orchestrator from `results/SPT_6_oneLP_fence__latest/diagnostics/` with two additions: it buckets every transmitter kind (each diagnostic declares `KINDS`, default `("ld",)`), and a diagnostic with a `MODE` attribute gets the branch mode set before `is_known` runs.

## diag_brx_const_condition.py (SPT, br_x)

- **Issue:** a branch transmitter whose condition, in the compiled program, is built only from constants resolves inside the window.
- **Evidence:** gem5-spt taints only what a load produces (`rob_impl.hh:236-250`). Its Lazy implicit-flow rule delays a mispredicted branch's squash only when the branch's arguments are tainted (`commit_impl.hh:944`).
- **Gate:** all three must hold:
  - the x86 slice (`spt_cond_slice.py`) is `const`;
  - the hit reproduces in a faithful re-run at its grid point;
  - gem5 printed no "made pending" line for the first mispredicting transmitter instance, and `VPUntaints` is 0.
- **Counterfactual:** inst-080310 with its constant source replaced by a load is made pending and no longer hits.
- **Verdict:** model over-approximation (the protection set counts constant-derived values; same cause as `diag_constaddr_load`). Not a gem5 bug.

## diag_brx_declassified_condition.py (SPT, br_x)

- **Issue:** the branch condition is a load value that a non-speculative load or store of the compiled program also uses as its address.
- **Evidence:**
  - Once that memory op reaches the visibility point, SPT untaints the register (`lsq_unit_impl.hh:1185-1207, 1262-1279`; `cpu.cc:2132`).
  - Forward propagation then cleans the branch's inputs (`rob_impl.hh:800`).
  - In the Alloy instance the co-transmitter is not rf-linked to that source: concretization gave both the same register through a shared Reg_s state with no rf edge.
- **Gate:**
  - the slice is `declassified` (names the instruction);
  - the hit reproduces;
  - gem5 printed no "made pending" line for the transmitter;
  - `VPUntaints` is at least 1.
- **Counterfactual:** inst-043417 with the store's address register changed from `%rax` to `%r12` has `VPUntaints` 0, every transmitter instance is made pending, and the hit disappears.
- **Verdict:** concretization/model artifact. Not a gem5 bug.

## diag_recon_stlf_bypass.py (gem5-recon-modded, ld) — real bug

- **Issue:** a load the defense itself marks `isTainted=1 isSpeculative=1` gets its data from an older store (`Forwarding from store idx N`) and is marked ready within the ROB before the window-opening branch resolves.
- **Gate:** all four, from one faithful re-run per mode:
  - the hit reproduces;
  - the `STL_CHECK` line after the transmitter's execute says tainted and speculative;
  - a forwarding line follows it;
  - its ready tick is before the branch's `resolve_visible`.
- **Verdict:** real gem5 defense bug, the known A2 (`wiki/findings/bug/recon_SLF_stlf_bypass/`, `results/Recon_6__latest/diagnostics/diag_recon_slf.py`). Build-specific, so it applies to every gem5-recon-modded campaign, each with its own evidence file.
- **Caveat:** it counts as a leak under the repo's rule that a store-forwarded load obtained its data.

## Scope

- The four SPT XML diagnostics copied from June (`constaddr_load`, `rf_clobber`, `nonspec_cotransmit`, `store_cotransmit`) are testset-specific. They belong only to campaigns on `testsets/SPT_6_oneLP`, not on `testsets_latest/SPT_6_oneLP`.
- The evidence-file diagnostics need fresh evidence per campaign (`run_spt_brx_triage.sh`, and the recon probe in `wiki/findings/bug/BRANCH_ANNOTATION_AND_FORCE.md` §7).

## diag_recon_physreg16.py (all gem5-recon* builds, scheme 2, ld) — real bug R-SA-12

Buckets a hit only when gem5's STL_CHECK says the transmitter is untainted and a replay of STT's rename rule shows the taint was lost by writing physical int reg 16 (`taint_tracker.cc:59`). Evidence: `../recon_physreg16_check.py`. Write-up: `diag_recon_physreg16.md`. 2026-11-08 validation: 0 of 188 recon hits match, all of them A2.

## diag_uv4_split.py (CleanupSpec, ld) — real bug, AMuLeT UV4

Buckets a hit only when every offending item is a fill or victim of a squashed split load whose cleanup was skipped `why=split` (`lsq_unit_impl.hh:2529-2535`). Evidence: `../cleanupspec_skip_evidence.py` → `diagnostics/cleanupspec_skip_evidence.json`. Write-up: `diag_uv4_split.md`. 2026-11-09: 7/7 `UV4_split_plus_other` stems in each warm 590-stem run are pure UV4 (the "other" is the same load's victim).

## diag_cs1_store_upgrade.py (CleanupSpec, ld) — known cause, verdict pending (`PHASE = "known_pending"`)

Buckets a hit only when every offending item is the victim of a squashed load whose E install an older committed store upgraded to M, so CleanupSpec skipped the cleanup (`Inv_CLEANUP st=M`). Same evidence file. Write-up: `diag_cs1_store_upgrade.md`; whether it counts is Anna's DECIDE (URGENT_TODO, CS-1). `bucket_hits.py` ranks unknown phases after `real_bug`, so these never land in NEW. 2026-11-09: 5 stems in each warm 590-stem run.

## diag_uv3_rmw.py (CleanupSpec, ld, RMW corpus) — real bug, known (AMuLeT UV3)

- **Issue:** a squashed RMW transmitter (`orq $0,(mem)`, corpus `testsets_latest/STT_6_rmw`) installs its line with a write request (`L1D:fill req=st msg=ST`, `L2:fill req=st msg=GETX`) and CleanupSpec logs `L1D:cleanup_skip why=nohitinfo` instead of undoing it.
- **Gate:** from `diagnostics/uv3_rmw_evidence.json` (`STAGE3_gem5/triage/uv3_rmw_evidence.py <campaign>`, needs `keep_tmp: true` or its gzipped traces): every hitting variant has `terms_fired` exactly `under_clean`, every offending event is such a fill at the record's own xmit pc by a never-retired instance, with the matching `nohitinfo` skip; every variant carries its per-record `cache_setup` (2026-11-09).
- **Cache setup:** the textbook chain needs a cold RMW line (`gem5.cache_setup` cold, or the cold half of `random`, the CleanupSpec/SpecLFB default since 2026-11-09). The reason names the cache_setup; `bucket_hits.py` adds a `by_cache_setup` split to `buckets/summary.json` when any test did not run warm.
- **Verdict:** real gem5 defense bug, already known (AMuLeT UV3); Anna 2026-11-09: counts as found. Bug note: `diag_uv3_rmw.md` in each campaign's `diagnostics/`.

## diag_cleanupspec_em.py (CleanupSpec, ld, RMW corpus) — real bug, UV3 family (E→M path), not deployed (2026-11-09, bug-investigate-em)

Buckets a hit only when every offending item is the install (L1D/L2) or victim of a squashed load S whose E line the squashed RMW transmitter U upgraded to M (`L1D:hit st=E nst=M req=st` at the xmit pc), with U's cleanup `why=l1hit` and S's cleanup `cleanup_skip ev=Inv_CLEANUP st=M` (`MESI_Two_Level-L1cache.sm:2294-2298` then `:2701-2705`). Evidence: `../cleanupspec_em_evidence.py <campaign> [--out-dir DIR]` → `cleanupspec_em_evidence.json` (reuses `cleanupspec_skip_evidence.py` and adds a strict re-check). Write-up: `diag_cleanupspec_em.md`. 2026-11-09 counts: cold 72/82 NEW, random 44/58 NEW, warm 10/11 NEW; plain-load controls 0. Not installed in any campaign (count-as-new-bug vs UV3 variant is Anna's DECIDE).

## Fanout-v2 diagnostics (bucket-fv2, 2026-11-09)

Installed in the 2% fanout-v2 campaigns (`/tests/simspect_alloy_20261108/code_20261109/results/<row>_STT_6_fv2{,fp}__latest/diagnostics/`, cafe2 = fv2, cafe3 = fv2fp) with `install_diag.sh` (bugwork copy). Each ships its bug `.md` here. Static ones need no rerun. Evidence ones read `<name>_evidence.json` from `../rerun_hits_evidence.py`, which reruns a campaign's hits in bounded batches (workdirs under `<work>/tmp/<batch>`, deleted after each batch) from the campaign's own config. They bucket a hit only when the rerun hit with the campaign's offending (struct, kinds) signature. Ruby reruns (InvisiSpec, CleanupSpec) are not bit-identical to the campaign run, so the rerun's own record and trace are classified.

- `diag_stt_xmm4_skip.py` (S1, real_bug, static; E3/E4 fv2fp): xmm4 on the transmitter slice + GPR twin held.
- `diag_recon_sse_load_producer.py` (R-SA-13, real_bug; E2/E8 fv2fp): direct SSE-load producer + GPR twin held, or (twin hit) a rerun STL_CHECK showing the transmitter untainted or the SSE producer non-speculative.
- `diag_recon_stlf_bypass.py` (A2/R-SA-9; E2): evidence now from `rerun_hits_evidence.py --analyzer recon_stlf --extra-debug Commit`.
- `diag_recon_oldest_taint.py` (R-SA-8, real_bug; E2): OTB-transmitter test + rerun STL_CHECK tainted.
- `diag_nda_forwarded_producer.py` (R-SA-18 NDA half, known_pending; E8): the producer load is speculative and store-forwarded (`--analyzer nda_fwd`).
- `diag_dom_xmit_store_forward.py` (known_pending, raw-record; E9): every in-window record store_forward; DoM criterion R-SA-18/Q6.
- `diag_invisispec_store_actor.py` (disqualifier), `diag_invisispec_uv1.py` (real_bug), `diag_invisispec_d1_dtlb.py` (known deviation): E12a/E12b, `invisispec_evidence.json`.
- `diag_speclfb_nonload_footprint.py` (disqualifier), `diag_speclfb_uv6.py`, `diag_speclfb_jmp_shadow.py` (real_bug), `diag_speclfb_walk_order.py` (known_pending): E14, `speclfb_evidence.json`.
- E13 uses the existing `diag_uv4_split.py` / `diag_cs1_store_upgrade.py`, with `cleanupspec_skip_evidence.json` built from a shim of rerun traces (`--analyzer cs_trace`).
- Helpers (not diagnostics): `_fv2_slice.py` (static transmitter slice + twin lookup), `_fv2_evidence.py`, `_speclfb_common.py`.
