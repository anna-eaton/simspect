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
