# 📋 STATUS — for Anna (SimSpect project)

Human-readable rollup of the SimSpect pipeline/research workspace, **kept current by every
Claude session** from `claudelog.md` (durable findings) + `claudenotes.md` (right-now) +
the review `.md`s. One file to see where everything stands: what to read, what needs your
call, what's running, the development front, and what's parked.

⚠️ *Run/sweep state below is "as last logged" — always trust `claudenotes.md` for the live
picture and re-verify a sweep is actually alive before relying on it.*

*Last refreshed: 2026-06-07 by figures (added Anna's personal code-branch TODO dump; prior: InvisiSpec denser-xmit rehooking, Alloy cleaning, OTB + double-squash into-testset work).*

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

## 📖 To read (review docs for you, newest first)
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

## ✋ Needs your call / approval pending
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
  `results/STT_6_invisispec_compound/`); needs **cache-MISSING tests + `--patch-off`** to actually
  fire UV1 (current const-hit corpus is all invisible hits).

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
