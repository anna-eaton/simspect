# bugsynth — consolidated findings & decisions (for Anna)

*One-page rollup of the whole bugsynth effort (2026-06-08…09). Everything is isolated under
`/tests/simspect/bugsynth/`; the live pipeline/models/sweeps were never touched. Detailed docs linked per
item. This is the decision page — read it first.*

## TL;DR
| thing | status | the honest bottom line |
|---|---|---|
| **OTB (recon getOldestTaint)** | ✅ **valid, reproduced** | Real DEFENSE FAILURE — the tainted-address xmit reaches cache speculatively (30/30, robust, scheme0/2 matrix, reference matches). **But forced** (Q2), and the on-top secret→cache-LINE exfiltration needs a line-scaled index the gadget doesn't yet build (RECON_OLDEST_TAINT_BUG.md §scope nuance). |
| **Pending-squash (nmosier)** | 🔴 **invalid / structurally blocked** | The faithful value-flip test shows our gadget does NOT leak; the bug *mechanism* is real but litmus gadgets can't construct the needed coincidence (see Q1). |
| **Robust branch checker** | 🟢 **general tool + definitive audit** | `check_br_ni.py` (general, any testset; value-flip + scheme-0 positive control; covers channels A/B/C). On the CANONICAL base STT_6 br_x testset: **42/42 live gadgets SOUND, 0 LEAK** — and old check_br would have false-flagged **all 42** → the entire historical STT br_x "leak" signal is check_br FPs (now confirmed on native gadgets). `CHECK_BR_NI.md`. Pipeline-fold (#1) remains. |
| **Channel D (implicit flow)** | 🟢 **probed + closed w/ evidence** | A public load gated by a secret branch: VERIFIED secret-invariant cache access even UNPROTECTED (scheme0) — single-level implicit gadgets don't leak (speculative path is predictor-determined). True channel-D reduces to the pending-squash coincidence (blocked); `check_br_ni` already projects the detecting observable. `CHANNEL_D_DESIGN.md` + `channel_d/`. |
| **Q1: pending-squash coincidence** | answered | structurally blocked (below) |
| **Q2: do bugs emerge from the model?** | answered | NO — forcing is fundamentally necessary (below) |

## The two reproductions
- **OTB** — `RECON_OLDEST_TAINT_BUG.md` (what it is) + `OTB_BUG_REVIEW.md` (full repro + scheme-0/2 validity
  matrix). Gadget generated directly in Alloy (`STT_6_otb2.als`), run on `/work/gem5-recon-modded`
  scheme2+allow_leaked. The transmitter reaches cache while a younger load is still speculative *only*
  because getOldestTaint frees the merged taint at the OLDER load's resolution; the same-binary control
  (loads resolve together → xmit held) proves it. **Reference test leaks identically.** Solid.
- **Pending-squash** — `NMOSIER_PENDING_SQUASH_BUG.md` (mechanism, still correct) + `PENDING_SQUASH_BUG_REVIEW.md`
  (RETRACTED banner). The earlier 17/20 was a *taint-flip* artifact (two different binaries; gem5 treats our
  `by` as tainted regardless of the secret). The value-flip (vary the in-memory secret on one binary) → 0/12.

## Q1 — why the pending-squash coincidence can't fire (structural)
In STT, `bo`'s taint REQUIRES a speculative load before it → which REQUIRES an older unresolved branch → which
DEFINES the speculation window. gem5 holds bo & by's (pending) squashes until bo becomes non-speculative =
until that older branch resolves (a fixed tick). So `by`'s observable fetch-redirect ALWAYS broadcasts at
window-close, **independent of the secret**. You cannot have `bo` tainted (needs the window-defining branch)
AND `by`'s redirect be an early, distinct, secret-dependent observable (that branch masks it). Confirmed: `by`
is made-pending even with a provably-clean `xorq` condition, so it is NOT a condition-taint issue — it's the
coincidence. The nmosier bug likely needs a deeper-pipeline resolution race that a 6-instruction litmus gadget
can't construct. **Parked as structurally blocked** (a dedicated /work/stt taint-debug build could trace the
argProducer/squash-priority path to confirm, but I did not rebuild the shared binary other sessions use).

## Q2 — do the bugs come FROM the model? No, and OTB *cannot* (definitive)
- **Pending-squash** is a channel the base data-flow model can't even express (a squash-timing channel) — we
  ADDED it as a new predicate (`STT_6_pendsquash.als`), a legitimate extension, not emergence.
- **OTB**: the model's leak DEFINITION *does* flag it, but its enumeration never produces the gadget.
  Measured chain: relaxed-minimality + 2000 instances → 0 OTB (kind-counts ARE diverse: 59 skeletons, 1001
  with 2 loads — so the gap is *dataflow topology*, not kind-counts). Forcing a general "ALU on the xmit
  address path" → still 0/300 2-load merges (280 have a 1-input ALU; 20 have a 2-input ALU with the other
  operand a CONSTANT). **Root:** one tainted operand already satisfies the leak, so minimality MINIMIZES
  load-fed operands and structurally avoids the multi-source merge OTB needs. ⇒ Forcing the merge
  (`otb_class`) is **fundamentally necessary**; a coverage enumerator would have to target the
  #load-fed-operands dimension, which reduces to the same constraint. (OTB is also a *recon*-defense bug; the
  base model is STT-only and not recon-getOldestTaint-aware.)

## Decisions for you
1. **Mainline or keep dedicated?** `STT_6_otb2.als` (+ the `compile_annotate.py` `branch_pc_addr_hex` alias,
   which is a genuine bugfix for recon-modded) — fold into mainline, or keep as a dedicated OTB repro? The
   `STT_6_pendsquash.als` channel + parsexml tainted-branch routing are infrastructure but the *repro* is not
   valid, so I'd hold those.
2. **Pending-squash:** accept it as structurally blocked in the litmus framework, or invest in a dedicated
   /work/stt taint-debug build + a deeper-pipeline gadget attempt?
3. **Branch checker:** ~~invest in finishing it~~ — **DONE** as `check_br_ni.py` (general, channels A/B/C),
   audited the canonical STT_6 br_x testset (42/42 live SOUND, 0 leak), closed channel D with evidence
   (`CHANNEL_D_DESIGN.md`), and shipped the pipeline integration as a separate audit pass
   (`br_ni_audit.py`, emits `window-results.json`). The ONLY thing left is the **optional** per-test fold
   into the live `pipeline.py` — not done on purpose (mainline edit + 5× sweep cost; the audit pass is the
   recommended form). Your call whether you also want the per-test fold. (`CHECK_BR_NI.md`.)

## Durable wins regardless of the above
- A **value-flip non-interference checker** that caught a flawed reproduction (rigorous validation method).
- A **precise, evidence-backed characterization** of two long-standing open questions (coincidence + diversity)
  so future sessions don't re-chase them blindly.
- The **recon-modded resolve-stall ann-schema fix** (`branch_pc_addr_hex`/`x86_branch_offset_hex` alias).
