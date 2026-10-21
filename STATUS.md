# 📋 STATUS — for Anna (SimSpect project)

Human-readable rollup of the SimSpect pipeline/research workspace, **kept current by every
Claude session** from `claudelog.md` (durable findings) + `claudenotes.md` (right-now) +
the review `.md`s. One file to see where everything stands: what to read, what needs your
call, what's running, the development front, and what's parked.

⚠️ *Run/sweep state below is "as last logged" — always trust `claudenotes.md` for the live
picture and re-verify a sweep is actually alive before relying on it.*

*Last refreshed: 2026-10-20 by cleanuprepo — **repo cleanup + Mac↔cafe2 git reconciliation.** See below.*

---

## 🧹 2026-10-20 — repo cleanup & git sync (cleanuprepo session)

The Mac and cafe2 container had **diverged uncommitted** from Jun 8 in different directions and the
container couldn't even auth to GitHub. All reconciled, nothing lost — **Mac = origin = container**.
- **Git unified:** cafe2's June work (bugsynth/, bug demos, staged-enum tooling, 2 protected
  `.als`) + Mac's Oct work (dashboard rewrite, sim rig, wiki/) merged on `main`, pushed.
- **Container GitHub auth fixed** (repo-scoped deploy key on persistent `/work` mount) — it can
  `git pull`/`push` directly now. See `wiki/state/INFRA.md`.
- **gem5 hooks backed up** → `gem5-hooks/` (they lived only in the ephemeral container; Recon builds
  weren't even git repos). `gem5-recon` = base, `gem5-recon-modded` = change. See `gem5-hooks/README.md`.
- **Layout consolidated:** dashboard → `dashboard/`; root `.md` → `wiki/design/` + `wiki/results/`;
  `RECAP.md` → `old/`. Only `CLAUDE.md`/`STATUS.md`/`claudelog.md`/`claudenotes.md` stay at root.
  Inventory: `wiki/state/REPO_MAP.md`. Full divergence writeup: `wiki/state/SYNC_DIVERGENCE.md`.
- **Still parked:** findings dirs (`bug/`, `mdsToRead/`, `docs/`) → `wiki/findings/` (next pass);
  a `scripts/sim capture-hooks` subcommand; dashboard `vscode://` open-links.

---

## 🚨 STANDING NEED (Anna, top priority): a far more robust BRANCH-CHANNEL check
**The branch transmitter checker (`STAGE3_gem5/check_br.py`) is the weakest link in the whole pipeline and
needs a principled rewrite.** Why this is urgent (collected across many sessions):
- **It misses real branch-channel bugs entirely.** The nmosier **pending-squash** leak is a secret-dependent
  *squash-signal timing* channel — `check_br` cannot express it at all; we had to write a bespoke differential
  (`bugsynth/pendsquash_diff.py`). A general branch checker must be able to catch redirect/squash-timing
  channels, not just "did a redirect happen."
- **No taint/secrecy gate.** `check_br` flags a redirect regardless of whether the branch condition is
  secret-derived → inflated branch hit rates (the historical STT br_x "leaks" were check_br FALSE POSITIVES;
  see `project_stt_branch_leak_cause`).
- **Coarse redirect criterion.** `branch_redirected` ≈ "xmit completed AND fall-through never retired",
  which conflates a genuine in-speculative-window redirect with any squash. It was patched to key on the
  *squash-broadcast* tick (not the complete tick), but still doesn't robustly enforce the
  `(lc_retire, fnc_retire)` window the way `check_ld` does, nor distinguish redirect causes.
- **What "robust" should mean:** (1) enforce the speculative window properly; (2) gate on whether the branch
  condition is actually tainted/secret; (3) key on the real fetch-redirect / squash-broadcast event; (4)
  handle *differential* secret-dependent-timing channels (squash-signal, resolve-coincidence) as first-class,
  not just operand-in-protset; (5) clearly separate real speculative-window redirects from generic squashes.
- Anna's own TODOs already flag this ("audit on the branch checker script", "branch concretization charts").
  **This is the #1 checker debt.** A correct branch-channel check would also be what lets pending-squash (and
  future branch-timing bugs) be found by the *mainline* pipeline instead of bespoke scripts.
- **Design workshop / proposal: `bugsynth/BRANCH_CHANNEL_CHECK_DESIGN.md`** — taxonomy of the 5 branch-channel
  types (A direct-direction, B redirect-timing/pending-squash, C squash-order, D implicit-flow, E window-modulation)
  and a unifying **non-interference (differential) checker**: vary the secret, flag any *public/untainted* branch
  observable (redirect tick, fetch schedule, squash order, window width) that moves with it. Single-run window
  checks can't cover B/C/D/E; the differential frame subsumes A–C (and D/E once generated).
- **PROTOTYPE built: `bugsynth/check_br_differential.py`** — non-interference frame, channel type B, with
  BOTH a taint-flip and a faithful **value-flip** secret parameterization + a forward-dataflow taint
  classifier. **It paid for itself immediately:** the value-flip mode showed the pending-squash
  reproduction is INVALID (0/12; public observables secret-invariant) — the taint-flip's 18/20 was a
  two-binary artifact. So the framework correctly catches both false negatives (the bug) AND, here, a
  false *positive* in our own repro. No-FP + self-consistency checks pass. Next: observable projections for
  channels A/C, fold into pipeline. See design doc §Prototype + claudelog 2026-06-09.
- **POSITIVE AUDIT (2026-06-09): `bugsynth/stt_branch_soundness_audit.py`** — used the same value-flip
  non-interference test for a positive result: **12/12 gadgets show STT's branch defense is SOUND** (the full
  public fetch-redirect timeline is secret-invariant). Principled confirmation that STT's branch defense works
  and the historical STT br_x "leaks" were check_br FALSE POSITIVES. Same framework, same value-flip that
  retracted the pending-squash repro — it correctly reports both.

---

## 🆕 bugsynth — BOTH STT bugs REPRODUCED from the Alloy up (isolated, nothing live touched) — 2026-06-08
Everything under `/tests/simspect/bugsynth/` (own pipeline.py, STAGE2/3, models, configs, testsets,
results). **READ FIRST — decision page: `bugsynth/FINDINGS_SUMMARY.md`** (one-page rollup: what's settled,
what needs your call). Then bug explainers: `bugsynth/NMOSIER_PENDING_SQUASH_BUG.md` +
`bugsynth/RECON_OLDEST_TAINT_BUG.md`. Reproductions (for you): `bugsynth/PENDING_SQUASH_BUG_REVIEW.md` +
`bugsynth/OTB_BUG_REVIEW.md`. Every change: `bugsynth/WALKTHROUGH.md`.**
- **🔴 Pending-squash (nmosier `18e304f`, bug B) — REPRODUCTION UNDER REVIEW / NOT YET VALID (2026-06-09).**
  The faithful VALUE-FLIP non-interference test (vary the in-memory secret 0 vs 1 on the SAME binary so bo's
  direction flips) shows **0/12 leak** — the public observables (fetch-redirect broadcasts, by's pending
  tick) are INVARIANT to the secret; only **bo's own** pending differs (the tainted branch — protected,
  allowed). The earlier 17/20 (`pendsquash_diff.py`) / 18/20 (`check_br_differential.py` taint mode) used a
  TAINT-FLIP that compared two DIFFERENT binaries — and `by` is intrinsically made-pending in the tainted-bo
  binary regardless of the secret (gem5 treats by's condition as tainted), so that "leak" is a binary/codegen
  artifact, not a secret channel. **Root cause refined (2026-06-09):** by is made-pending even with a PROVABLY-CLEAN `xorq` condition
  — so it is NOT a condition-taint issue; the same-cycle bo/by COINCIDENCE that the bug needs simply isn't
  firing in a way that makes a PUBLIC observable secret-dependent (matches the long-standing
  `project_coincidence_gap` / Anna's "why can't we have the coincidence fire?"). **To get a valid repro:**
  force bo & by to resolve the SAME cycle so bo (older,tainted) wins instCausingSquash and delays by's PUBLIC
  redirect secret-dependently; validate ONLY with the value-flip. Likely needs a dedicated /work/stt
  taint-debug build to trace argProducer + squash priority. See claudelog 2026-06-09 + `NMOSIER_PENDING_SQUASH_BUG.md`
  (the bug *mechanism* is still correct; our *gadget* doesn't yet exhibit it). The differential FRAMEWORK
  (`check_br_differential.py`) is what caught this and is sound. The Alloy channel `STT_6_pendsquash.als` +
  parsexml routing stand as infrastructure; the *demonstration* needs the fixes above.
- **✅ OTB (recon getOldestTaint, bug A) — 30/30 gadgets leak on /work/gem5-recon-modded scheme2+allow_leaked.**
  **Bug explainer: `bugsynth/RECON_OLDEST_TAINT_BUG.md`** (mechanism, validity matrix, the fix, + honest
  "where we're at": still forced via `otb_class`, not yet emergent from the model).
  Gadget generated DIRECTLY in Alloy `models/STT_6_otb2.als` (2-load→ALU→xmit; la under correctly-not-taken
  branch, lb under mispredict). Differential `otb_check.py` (`python3 bugsynth/otb_check.py 10 2500 9000`):
  the xmit is released (issues+accesses cache) while lb is still speculative ONLY when la resolves first;
  control (both resolve together) holds it → the getOldestTaint oldest-taint early-free (taint_tracker.cc:119
  + freeTaints:134). KEY FIX: recon-modded se.py reads `branch_pc_addr_hex`/`x86_branch_offset_hex` not
  `branch_addr_hex` → added the alias in `compile_annotate.py` (this was the long-standing "xmit never
  issues" blocker). Reference oldest_taint_bug.s leaks identically (control).
  - **Awaiting your call:** fold `STT_6_pendsquash.als` / `STT_6_otb2.als` + the parsexml tainted-branch
    routing + the compile_annotate alias into mainline, or keep as dedicated repros? **No mainline `.als`/
    pipeline modified.** Regression (not run): post-fix builds → 0 leaks.

### 🔭 bugsynth — future directions / open questions (2026-06-09): do the bugs come FROM the model?
**Honest status: NEITHER bug emerges from the unmodified base model — both needed predicates we wrote.**
- **OTB** — the base model's `secure_speculation_scheme_p` *does* flag it (xmit addr ∈ protset), but (a) the
  enumeration never produces the 2-load→ALU→xmit shape (**0/100k** — simple direct-load shapes fill the cap;
  re-tested 2026-06-09: relaxed driver w/o `otb_class` → 0/60 natural), and (b) the per-branch RR-minimality
  PRUNES multi-source merges (resolving one load's branch leaves the other tainted → "not minimal"). So
  `otb_class` HAND-FORCES the shape. The leak is in the model's definition; the *generation* is forced.
- **Pending-squash** — the base data-flow security predicate calls it SECURE (younger branch untainted). The
  leak is a **timing/squash-signal channel the model cannot express**; `pending_squash_insecure_p` is a NEW
  channel we ADDED (a real model extension, like implicit-flow), not the base model finding it.
- **TODO — make OTB emerge (principled):** (1) relax per-branch minimality to allow **multi-source leaks**
  (general: a leak may have ≥2 contributing spec sources), (2) fix enumeration **COVERAGE** so rare/complex
  skeletons appear (the real work — see Diversity). Then OTB would appear without `otb_class`.
- **TODO — implicit-flow channel:** `if(secret)x=A else x=B; load(arr[x])` is STRUCTURALLY inexpressible in
  the base model (branch has no outreg/ddi/rf → secret can't reach a later value via control). Needs a `cdep`
  control-dependence edge folded into `op_edges_p` + parsexml if/else concretization (owner-gated). Same
  category as pending-squash (a channel the data-flow model lacks). [xref claudelog 8:alloyCheckUpdated]
- **TODO — DIVERSITY (the core generation problem):** the enumerator is biased to the SIMPLEST instances
  (symmetry-breaking + minimality + SAT solve-order = simplest-first), so (a) complex gadgets like OTB never
  appear naturally, and (b) within a forced shape only register/value varies (OTB = 1 structural template;
  the `exactly 6 Instruction` scope leaves no room for context; pending-squash has 7 shapes). Candidate fixes:
  **(i) skeleton-stratified enumeration + blocking clauses** (after K instances of a structural skeleton, add
  a fact excluding it → solver forced to a NEW skeleton → covers the shape space incl. OTB with no bug-specific
  predicate); **(ii) larger instruction scope** (6→8, for in-context variation; needs IX6/IX7 + bigger SAT);
  **(iii) randomized SAT var-ordering** for statistical coverage. RECOMMEND prototyping (i).
  **MEASURED 2026-06-09:** 2000 relaxed-minimality instances (no otb_class) → 0 OTB-shaped, 0 even route the
  xmit addr through an ALU — yet they ARE kind-diverse (59 skeletons; 1001 have 2 loads, 811 have 2 ALUs).
  So the gap is the **DATAFLOW TOPOLOGY around the transmitter** (xmit addr always direct-from-load; the ALUs
  sit on other paths), NOT kind-counts. ⇒ blocking clauses must cover **rf/ddi dataflow skeletons** (block
  "xmit-addr direct-from-load" after K to force "xmit-addr through ALU"), not kind-sequences. That makes OTB
  appear as one covered topology with no bug-specific predicate. (claudelog 2026-06-09.)
  **DEFINITIVE (2026-06-09):** even FORCING an ALU on the xmit address path (general, no 2-load pinning)
  → 280/300 have a 1-input ALU, 20/300 a 2-input ALU with the other operand a CONSTANT, **0/300 the 2-load
  merge**. ROOT: one tainted operand already satisfies the leak, so minimality MINIMIZES load-fed operands
  and structurally avoids the multi-source merge. ⇒ OTB's leak is in the model's *definition* but its 2-source
  *gadget* cannot emerge from minimality-guided enumeration; forcing the merge (otb_class's "≥2 distinct loads
  feed the ALU") is FUNDAMENTALLY NECESSARY, not a shortcut. (Blocking-clause coverage would have to target
  the #load-fed-operands dimension, which reduces to the same constraint.) Diversity question CLOSED for OTB.

---

## 🗒️ Anna's personal TODO notes (verbatim — Anna's own dump, not Claude's analysis)
*Captured 2026-06-07 from a brain-dump. Kept as-is; reminders to herself for the code/pipeline
branch — not acted on, not verified. The "?"/asides are Anna's.*

**Branches / sweeps**
- Start inspecting branch hits.
- Resolved br sweep windows.
- Generating more unresolved branches ??? take off relaxation.
- Two-phase alloy??
- Tune IEW to commit delay etc.
- End block is not at the end??

**Recon / OTB / coincidence bugs**
- Eventually go back to Recon to concretize the bugs we've got there, and also check if the ORB bug is generating.
- Figure out why the two bugs we know of aren't triggering on STT Recon yet.
- Is the OTB bug ever generated :(
- Do some test sweeps on the oldest-taint bug; show results about timing etc.
- Make sure that bug isn't real.
- Gotta eventually rerun duplicate-PC bugs.
- Have to figure out why the one with two coincidences isn't hitting.
- Leftover question: why can't we have the coincidence fire?

**Checkers / scripts / audits**
- Let's do an audit on the branch checker script.
- Should I really update the shared checkld diagnostic script?
- Did we not make a triage script for slowcomm?
- Audit the models to see if there's anything out of date with the others.
- Audit the 1234 low cases.
- Force a clean recompute (if you suspect a stale count): `rm results/.sweep_monitor_cache.json`.

**Timing sweeps (before bed)**
- Run something with natural timing for a second sweep, and a sweep with shorter timing windows for delays.
- Natural timing necessary for the slow-regime hits.
- Run natural timing for a bunch of stuff before bed; also a short timing sweep before bed.
- Post-nap: run the baby ones for AMuLeT, run other lil experiments, make the figures, write the paper.

**Alloy / model**
- Alloy: make it able to emit the other transmitter.
- Gosh we don't build implicit-flow gadgets right??

**Charts**
- Gen charts for: branch concretization; transmitter detection.
- Run vs scheme 0 in a lot of them to see if that's good.

**SPT**
- Does a load output unprotected when it's non-speculative — yea?
- SPT flag stickiness flaw???

**Config**
- ShadowL1 on vs off.

**Logistics / submission**
- Figure out if the authors have to be fixed by the time I submit the abstract — if so, do Nick + Prof. Mitchell go on there.

**Open questions**
- Who are we to say what is irrelevant variation?

---

## 🛡️ Ongoing project — SOTA load-defense bug reproduction (InvisiSpec / SpecLFB / CleanupSpec / STT)
**Living rollup → `mdsToRead/AMULET_LOAD_DEFENSES_PROJECT_LOG.md`** (read this first for the defense work).
Aim: reproduce **every** AMuLeT-reported bug on the real gem5 build (or give a precise source why-not).
**As of 2026-06-09: 6/9 demonstrated** — UV1 (InvisiSpec evict), UV6 (SpecLFB first-load), KV1 (InvisiSpec
L1I), KV3 (STT store→TLB), UV4 (CleanupSpec split), unXpec (CleanupSpec undo-as-channel). **UV2** reachable
but empirical demo blocked (spec data loads don't issue GETSPEC in a gadget). **UV3** precise why-not.
**UV5** (over-clean) = next to build. Per-defense builds/observation-points + repro commands in the doc.

## 📖 To read (review docs for you, newest first)
- **`docs/AMULET_VS_SIMSPECT_SCOPE.md`** (headline section) — 📐 **ADVISOR-FACING: why InvisiSpec / footprint-
  hiding defenses are OUT OF SCOPE.** Definitional argument: our oracle is transmitter-level (did the
  transmitter fire in the window?), which matches the comprehensive transmitter-blocking defenses (STT/SPT/
  Recon/…); InvisiSpec lets the transmitter fire and hides the footprint → type-mismatched oracle → needs a
  whole-µarch differential defense-specific check (AMuLeT's job). Hand straight to advisor. (2026-06-10.)
- **`mdsToRead/ENUMERATION_OVERSPECIFICATION.md`** — 🔴 **enumeration over-specifies: 100k tests = ~10 leak-
  cores (98% on 2 shapes); minimality kills control-multiplicity, simplest-first SAT + no instr-minimality
  waste the budget on padding.** Built+validated `STT_6_multisource.als` (relax minimality) + `a6DiverseModels.java`
  (leak-core diversity driver). (2026-06-09/10.)
- **`results/STT_6_cleanupspec_residue/uv5_demo/NOTE.md`** — 🟡 **NEW: CleanupSpec UV5 (over-clean) EXAMINED
  → empirical demo BLOCKED** (mechanism source-confirmed). Free-way path: CleanupSpec correct (spec line
  cleaned, committed neighbour stays resident, 0 over-clean). The eviction path UV5 needs trips the
  defense-independent assoc-thrash `Resource Stall` storm (ON==OFF) at assoc-2 AND assoc-4 → can't stage.
  Same blocker class as UV2. (2026-06-09, 5:invisispec.)
- **`results/STT_6_cleanupspec_residue/unxpec_demo/`** — ✅ **NEW: CleanupSpec unXpec EMPIRICALLY
  DEMONSTRATED** (reproducible `run_unxpec_demo.py`). The undo *itself* is the channel: spec-load MISS
  (cold) → 7 cleanup events (L1+L2+dir invalidation cascade); HIT (pre-warmed) → 0. Cleanup footprint is
  secret-dependent (`lsq_unit_impl.hh:142-160`, `pkt->isL1Hit()`). **6th AMuLeT bug demoed.** (2026-06-09.)
- **`bug/uv2_demo/`** — ✅ **NEW: InvisiSpec UV2 (MSHR/TBE contention) EMPIRICALLY DEMONSTRATED**
  (`run_uv2_demo.py`). 4 spec loads on a TLB-warm page exhaust the 2-entry TBE pool: `--L1_TBEs=2` → 248
  retry GETSPECs + 122k-tick serialization; `=8` → 4 clean concurrent. Unblocked via the **TLB-warm-page
  trick** (committed access warms the page so the speculative TLB miss isn't deferred). **7th bug demoed →
  7/9; only UV5 (over-clean) empirical gap left + UV3 why-not.** (2026-06-09, 5:invisispec loop.)
- **`bug/kv1_demo/`** — ✅ **NEW: InvisiSpec KV1 (L1I fetch channel) EMPIRICALLY DEMONSTRATED**
  (reproducible `run_kv1_demo.py`). A branch forced (BTB) to predict TAKEN to a far code label reached
  only speculatively → that label's L1I line installs (`Ifetch NP>IS`) under the misprediction but NOT
  in the correctly-predicted control. InvisiSpec makes data loads invisible but **not** instruction
  fetches. **5th AMuLeT bug demoed (UV1, UV6, KV3, UV4, KV1).** (2026-06-09, 5:invisispec loop.)
- **`bug/STT_KV3_TLB_REVIEW.md`** — ✅🔴 **NEW: STT KV3 (spec store → TLB) EMPIRICALLY DEMONSTRATED**
  (source chain + a controlled gadget `bug/kv3_demo/`, reproducible). STT protection is loads-only
  (`isTransmit()=isLoad()`; `Request::SPEC` set only in `readMem`); a wrong-path STORE translates at
  execute and **fills the TLB for a secret-dependent cold page** unprotected. 2×2 control on the live
  STT build: store walks the cold page under **both** STT and Unsafe (= unprotected = KV3); load walks
  under Unsafe but **NOT** under STT (= STT protects loads). The 3rd AMuLeT bug demoed in SimSpect
  (after UV1, UV6). Reachable unlike CleanupSpec UV3 (translation is pre-commit). (2026-06-08, 5:invisispec loop.)
- **`results/STT_6_cleanupspec_residue/CLEANUPSPEC_RESIDUE_REVIEW.md`** — 🔴 **NEW: CleanupSpec
  residue watcher built + validated.** On STT_6 ld the defense WORKS (0 residue; a "3 RESIDUE"
  reading was a checker FP — spec *hit* on a committed line — caught by gem5 verification + fixed).
  UV3 precise why-not (loads-only cleanup + squashed stores never touch cache). **✅ UV4 EMPIRICALLY
  DEMONSTRATED** (`uv4_demo/`): split spec load installs 2 lines, gets 0 cleanup (residue), vs the
  aligned control which is cleaned — source `isSplit=false` + single `cleanupReq`. assoc-2 deadlock
  RULED OUT as a bug (ON==OFF). (2026-06-08, 5:invisispec loop.)
- **`mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md`** — 🔴 **full accounting: every AMuLeT bug ×
  our detection (+ WHY-not).** Detected 2/9 (InvisiSpec UV1, SpecLFB UV6); the other 7 are out of
  our formulation for precise reasons (store/I-fetch transmitter, TLB/I-cache observation, timing
  channel, or post-squash residue = final-state diff). Includes observation points per defense +
  why, the lc/fnc-window fix + parallel lc/fnc-OFF analysis, the cache-size flag, and the pipeline
  changes needed to generate each undetected bug. **This is the master doc for this work.**
- **`mdsToRead/INVISISPEC_UV1_CONFIRMED.md`** — 🔴 **InvisiSpec UV1 (speculative L1 eviction)
  CONFIRMED** via the compound hardware-structure watcher on the real Ruby defense. Patch-OFF
  29/30 evict speculatively; the AMuLeT fix → 0/30 (airtight). Generalizes to STT-interleave.
  Real bug, NOT a test-gen artifact. UV2 (MSHR/TBE) surface also present.
- **`PAPER_RESULTS.md`** — findings by defense (recon OTB+STL, STT/SPT VP-squash race, AMuLeT
  scope + SpecLFB UV6, targeting 17%→100%, timing sweeps). UV6 reframed to **DEMONSTRATED**.
- **`results/STT_6_speclfb/SPECLFB_UV6_REVIEW.md`** — SpecLFB UV6 confirmed; the 68 hits are
  **valid dataflow leaks, NOT const-addr FPs** (corrected). ⚠️ this corrected an earlier verdict.
- **`docs/COMPOUND_TRANSMISSION_CRITERION.md`** — the all-µarch-structures load criterion + per-
  defense hook map (design; partially implemented for InvisiSpec).
- **`docs/AMULET_VS_SIMSPECT_SCOPE.md`** — which AMuLeT bugs are in/out of SimSpect's scope.
- Methods docs: `METHODS_LEAKAGE_KNOBS.md` / `METHODS_CONCRETIZATION.md` / `METHODS_INSTRUMENTATION.md`.
- **Paper (S&P 2027) review docs** (in `/tests/SimSpect-S-P-2027/toread/` + `paper_figures/`):
  - `paper_figures/reviews/DISCUSSION_AND_FINAL.md` — PC debate + 3 finals on the YArch mini-paper
    (all **Weak Reject**; flip-it deliverable = one bug end-to-end + negative control).
  - `paper_figures/YARCH_PORT_PLAN.md` — what to port from YArch (related work, pipeline fig, etc.).
  - `…/toread/technical-review.md` — per-paragraph grades on `model.tex` + `pipeline.tex`.
  - `…/toread/reconstl_figure_critique.md` — critique of the ReCon STL figure.

## ✅ TODO (from 5:invisispec autonomous run — AMuLeT bug replication)
- **DONE this run:** lc/fnc gate-cheat reverted (kept STRICT); ported the **fnc-commit-stall hook**
  (non-defense) to the InvisiSpec + SpecLFB builds + rebuilt; **UV1 (11/12) and UV6 (11/12) confirmed
  in the STRICT lc/fnc window** with `fnc_commit_stall_cycles=150`. (The amulet builds had lacked the
  standard window-widener recon/STT use — that, not the gate, was why the slow touches fell out.)
- **Write a paper section on the CACHE-SIZE CONSTRAINT** (amplification): litmus-test µarch defense
  testing needs a small-L1D / few-MSHR knob so short tests reach the full-set/contention conditions
  where conflict/eviction/interference bugs manifest. Used `--l1d_size=1kB --l1d_assoc=2`. Details +
  paper framing in `mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md` §4. ← *flagged for you.*
- **Make UV1/UV6 hits secret-dependent** (concretization): seed a non-zero value into the
  speculatively-loaded location so the evicted victim / installed line varies with the secret
  (today index=0 from the zero-init prologue → structural touch confirmed, victim is fixed).
- **CleanupSpec UV3/4/5 — NOW detectable (reclassified):** residue traces to the in-window
  `L1_Replacement_OnInstall` + MISSING/OVER post-squash cleanup (`Inv_CLEANUP`/`Load_ROLLBACK`,
  ProtocolTrace-visible) → EVENT-correlation watcher (NOT a final-state diff). Build: port the
  fnc-stall hook to the CleanupSpec build (`X86_MESI_Two_Level`, --ruby) + write the install↔cleanup
  correlator. Recipe known.
- **Still need new transmitter types / channels:** STT KV3 (store-address transmitter + D-TLB watcher),
  InvisiSpec UV2 (MSHR-timing watcher), KV1 (L1I watcher). See accounting doc §5.

## ✋ Needs your call / approval pending
- **🆕 Staged enumeration — new `STT_6_core.als` to eyeball (2026-06-10).** New optional XML
  producer (minimal cores → STT_6 flesh-out) to fight enumeration over-specification: enumerate
  maximally-minimized leak cores once, then cap fleshed-out tests **per core** so one shape can't
  fill the cap. Files: `STAGE1_alloy/{models/STT_6_core.als, stage_seed.py, stage_pipeline.py}`.
  `STT_6_core.als` is a pure **copy of STT_6.als** + 3 flagged changes (idx/ordering rules removed,
  `exactly 6`→`but 6`, all relaxations RO+RI on); STT defense byte-identical. Verified E2E (2 cores
  → 8 XMLs → 8/8 `.ll`). **Doc: `mdsToRead/STAGED_ENUMERATION.md`.** Additive — flat pipeline + all
  existing `.als` untouched. Your sign-off on the new model + whether to make it a `pipeline.py` phase.
- **Alloy `rf_from_most_recent_writer` fact** — owner-approved but **NOT yet applied** to
  `SPT_6_oneLP` + `Recon_6` (`STT_6` already has it, L163-169). Until applied, rf-clobber is
  filtered gem5-side instead of ruled out in Alloy → **regen all affected testsets after applying.**
- **const-addr proper-closure fix** (`.als` L341) — DESIGNED but **UNAPPROVED**; data-taint only,
  must NOT apply to STT/Recon.
- **Any `.als` edit needs your sign-off** (standing rule). SPT model has 2 approved fixes
  (inaddr-cleanup L356 + stores-in-leakage_function) that imply a **regen**.
- **`check_br.py` taint-at-redirect gate** — recommended (branch hits are check_br FPs); your call.
- **Paper:** where to `\input` the new `tikz/reconstl.tex` (ReCon STL conceptual figure) — left
  un-placed; if used early it needs "transmitter"/"bound-to-squash" defined first. Also decide
  whether to port YArch's related work into the **empty `sections/related.tex`**.

## 🏃 Runs / work last logged (verify before trusting)
- **150k regen** of `STT_6`, `SPT_6_oneLP`, `Recon_6` alloys + fresh testsets via `testsetgen`
  (logs `latestmodels/<m>_gen150.log`) — *launched 06-03, confirm completion.*
- **recon-modded gem5 watchers** jobs=12 sweeping the (stale pre-RS) `testsets/STT_6` — *check alive.*
- **InvisiSpec compound checker** built (`STAGE3_gem5/check_ld_invisispec_compound.py` +
  launcher `results/STT_6_invisispec_compound/run_invisispec_compound.py`) and **FIRES**: with
  `--ruby` + small L1D (`--l1d_size=1kB --l1d_assoc=2`, AMuLeT-style amplification) + default
  patch-OFF, **UV1 confirmed** (29/30 STT_6, 10/14 interleave); `--patch-on` → 0 (control).
  See `mdsToRead/INVISISPEC_UV1_CONFIRMED.md`. `check_ld.py` untouched.

## 🔭 Development front
- **InvisiSpec on Ruby — scoping + rehooking with denser transmit-point checks** (ongoing). 🔴
  prior InvisiSpec/CleanupSpec runs were on CLASSIC caches (defense inactive). Moving the load-leak
  test off the single cache-install check to the **compound criterion**: re-hooking the checker to
  flag a speculative USL that touches **any** forbidden µarch structure (L1 tag/LRU/evict,
  MSHR/TBE, L2, dir `SpecFetch`, TLB) via Ruby `ProtocolTrace`. Scope: `docs/COMPOUND_TRANSMISSION_
  CRITERION.md`. Compound checker built (`STAGE3_gem5/check_ld_invisispec_compound.py`); next:
  missing-line corpus + `--patch-off` to actually fire UV1.
- **Alloy bug cleaning** (ongoing) — pushing model-level false-leak sources back into the `.als` so
  they're *ruled out in Alloy* instead of filtered gem5-side: `rf_from_most_recent_writer` fact
  (→ `SPT_6_oneLP`, `Recon_6`), SPT inaddr-cleanup + stores-in-leakage, and the pending const-addr
  closure. Each implies a **regen**. Owner-approval + regen status tracked under "✋ Needs your call."
- **SpecLFB UV6** — demonstrated; the dataflow signal stands.
- **STT/SPT VP↔squash race** — the one confirmed real-bug-class signal (untaint on resolved/
  completed not committed); ~3807 genuine SPT load signal + STT load race.
- **Two gadgets to get *into* the testset** (ongoing — each with a bug diagnosis in progress):
  - **OTB / `getOldestTaint`** — recon merges two still-speculative tainted loads into the xmit
    address and untaints on the *oldest* source resolving (should track the *youngest*). Absent from
    default enumeration but **legal when forced** (`otb_shape` predicate + `interleave.enabled=true`).
    Work: enumerate the forced OTB testset + ship the recon youngest-vs-oldest-taint diagnosis.
  - **Double-squash (nmosier two-branch coinciding squash)** — our `/work/stt` build IS vulnerable
    (HEAD not ancestor of fix `18e304f`) but unreachable today: model emits only 1 unresolved branch;
    bug needs ≥2 mispredicted, mixed-taint branches with coinciding squash. Work: model/config change
    to emit the ≥2-branch shape (owner ok) + the coinciding-squash diagnosis.
- **Paper (S&P 2027)** `/tests/SimSpect-S-P-2027` (current; old copy archived `/tests/old/`). Infra
  done (IEEEtran bib, two-tier logs, `toread/`, this dashboard's paper analogue). Figures: added
  `tikz/reconstl.tex` (ReCon STL); `images/pipeline.png`+`examplefigure.png` still never
  `\includegraphics`'d; `sections/related.tex` empty. The reviewers' bar for any bug claim:
  **one discrepancy carried end-to-end through a falsification protocol + a negative control** —
  state both explicitly (ties to the VP-squash race + recon SLF results).

## 🗂️ Scoped / flagged for future
- *(OTB / getOldestTaint and the nmosier two-branch coinciding-squash bug are now **active** — see
  "Two gadgets to get into the testset" under 🔭 Development front.)*
- **`commitToIEWDelay`≥3** wiring into `_build_gem5_env` to faithfully reproduce the VP-squash race
  (not in stock pipeline; ≥5 livelocks gem5).
- **branch xmit rework** — in progress; STT relaunch deferred; regen from parsexml for br_x.
- **dup-PC codegen bug** — parsexml xm-branch NOP injection duplicates a PC label → ~6% of br_x
  tests fail compile; fix Stage 2, relaunch from parsexml.
