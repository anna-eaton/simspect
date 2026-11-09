# diag_recon_physreg16: physical int reg 16 is never tainted (R-SA-12)

*2026-11-08, recon-ruby session, for Anna (#18). Source finding: `wiki/findings/audits/2026-11-08/SOURCE_AUDIT_RECON.md` R-SA-12.*

## Issue and signature

On every gem5-recon* build (`/work/gem5-recon`, `-modded`, `-stl`, `-ruby3`), `src/cpu/o3/secure_scheme/taint_tracker.cc:59` in `TaintTracker::insertTaint` reads `if (regId->flatIndex() == 16) return;`. Every taint insertion goes through it: `rename.cc:714-720` calls `insertTaintInst` for a load that is speculative at rename and `propagateTaints` for every other instruction. `flatIndex` 16 is IntRegClass physical register 16 (`Register 16 (flat: 16) (IntRegClass)` in the Rename trace). x86 has no zero register, so phys int 16 is an ordinary renamable register: it is first mapped to microcode temp `t0`, then recycled through the free list. A speculative value renamed to it is never tainted, so a transmitter that reads it is not delayed (`lsq_unit.cc:2095-2104`).

The diagnostic buckets a **load-transmitter** hit only when all of the following hold. The evidence comes from `STAGE3_gem5/triage/recon_physreg16_check.py`, which re-runs the hit once, faithfully, with the `Rename` debug flag added (prints only).
- **S1:** the hit reproduces.
- **S2:** gem5's own `STL_CHECK` for the xmit's decisive execution (`lsq_unit.cc:1886`) says `isTainted=0 isSpeculative=1`.
- **S3:** replaying STT's rename rule over the xmit's register slice *with* the reg-16 skip gives untainted, in agreement with gem5.
- **S4:** the same replay *without* the skip gives tainted.
- **S5:** an instruction in the slice writes phys int 16 and would be tainted without the skip.
- **S6:** `allowlistedTaintsFromTT` is 0, so no ReCon untaint is involved.
- **S7:** every rename block in the slice parsed cleanly.

Two conservative choices keep it from over-bucketing:
- A taint origin must be a load that is younger than a forced branch still unresolved at the xmit signal, and whose own `STL_CHECK` says speculative. Store shadows are not counted, so the replay can only under-taint.
- br_x hits are never bucketed, because the tracker's verdict for branches is not printed.

## Evidence and validation (2026-11-08)

- **Synthetic traces:** `STAGE3_gem5/tests/test_recon_physreg16.py`. The positive case and three negatives (the dest is not reg 16; the load is older than the branch; the producer is squashed) all pass.
- **Real hits:** every ld hit of `results/STT_6_reconmodded_fixed_latest__20261108_012818` (185 test×mode), the 2 Recon_6 classic Recon-STT hits, and the 1 no-STLF hit (`STT_6_ns_nostlf_reconmodded`). All 188 reproduced and parsed cleanly, and in every one gem5 says `isTainted=1`. These are the A2 store-forwarding bypass, not R-SA-12. **0 bucketed.** No hit's slice touches phys int 16.
- Evidence files are on cafe2 under `/tests/simspect_fixed_20261030/results/physreg16_dev/{r4,recon6,nostlf}/recon_physreg16_evidence.json`.
- So far no hit shows R-SA-12. The positive path is verified only on synthetic traces.

## Verdict and scope

If the signature fires, it is a **real gem5 defense bug**: an implementation special case that breaks STT's taint invariant. It is not a model, concretization or hook artifact. The scope is build-specific: any scheme-2 campaign on the gem5-recon* builds. The tracker is used only under `Scheme::STT` (`rename.cc:714`).

## Use

```
python3 STAGE3_gem5/triage/recon_physreg16_check.py --campaign results/<camp> --config <its run_config> \
    --testset testsets_latest/<model> --out results/<camp>/diagnostics/recon_physreg16_evidence.json
cp STAGE3_gem5/triage/diag/diag_recon_physreg16.py results/<camp>/diagnostics/   # only if it matches >0 there
```
