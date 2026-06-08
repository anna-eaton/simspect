# Claude Findings Log (big-picture, durable)

This is the **high-signal, append-only log** of things Claude sessions figured out that
future sessions (and the user) need to know. It is the counterpart to `claudenotes.md`:

- `claudenotes.md` = *ephemeral* "what I'm doing right now" scratchpad. Cleared/overwritten freely.
- `claudelog.md` (this file) = *durable* "what we learned / changed and why". **Append, don't delete.**

## 2026-06-06 — figures — Added `dashboard.py`: web view of both STATUS dashboards + sweep monitor

- **What:** `/tests/simspect/dashboard.py` — a single-file, **stdlib-only** (no flask/markdown;
  neither is installed here) HTTP dashboard for Anna. Serves:
  - both `STATUS.md` (Code = `/tests/simspect`, Paper = `/tests/SimSpect-S-P-2027`), rendered via a
    compact in-file markdown→HTML converter (headings/lists/tables/code/blockquote/inline);
  - click-through to every `.md` the STATUS files reference (auto-extracted, resolved against the
    repo roots + `/tests`, existence-checked; `/api/md` is **path-traversal-guarded** to the two
    repo roots only — verified 404 on `/etc/passwd`);
  - a **Sweep Monitor** tab that runs `sweep_monitor.py --once` (≈2 s, 8 KB ANSI), cached
    (min 25 s between runs) with a 40 s timeout, ANSI→HTML so colors survive;
  - client-side auto-refresh (default 30 s) + refresh-on-focus.
- **How:** `python3 dashboard.py` (binds `127.0.0.1:8765` — loopback only). Reach it via
  `ssh -N -L 8765:127.0.0.1:8765 <dev-box>` then open `http://127.0.0.1:8765`. `--selftest` renders
  once without serving; `--port`/`--host` to override.
- **Scope (per Anna):** dashboards-first, **no** session launcher/relaunch buttons (deferred —
  Claude Code has no IPC to inject into a live interactive session; the agreed model is global
  state in logs/STATUS + fresh/resumed sessions, not driving live ones from the app).
- Tested: `--selftest` (both STATUS render, 11+11 linked docs resolve) + live `curl` on every
  endpoint + the sweep panel populating after its background run.

## 2026-06-06 — 5:invisispec — 🔴 InvisiSpec/CleanupSpec runs were on CLASSIC caches (need --ruby) + BUILT the compound InvisiSpec checker

**🔴 BIG: every prior InvisiSpec (and CleanupSpec) run used the CLASSIC cache model, NOT Ruby — the
defense was INACTIVE.** gem5_common.run_gem5 appends `--caches` but NOT `--ruby`; InvisiSpec's defense
(Spec-GetS invisibility, SB, eviction toggle) lives in the Ruby MESI `.sm`, so classic runs only exercised
the CPU/LSQ side (readSpec/SB/expose), not the cache-side invisibility. Evidence: `cache.cc:192 hasRespData`
aborts = classic cache; `ProtocolTrace` empty w/o --ruby; WITH --ruby it lights up (`SpecLoad M>M`, 1476
lines). `--caches --ruby` coexist (se.py `if options.ruby:` wins). ⇒ earlier InvisiSpec results (0 leaks,
expose-in-window) are on the WRONG memory model — don't test InvisiSpec's real cache defense. SpecLFB
unaffected (classic build/X86, no Ruby).

**BUILT (read `check_ld.py` UNCHANGED — confirmed git-clean; only NEW files + additive gem5_common):**
- `STAGE3_gem5/check_ld_invisispec_compound.py` — many-pronged checker: parses Ruby `ProtocolTrace`
  (`<tick> <node> <Machine> <Event> <cur>><next> [addr, line L]`) for the xmit load's full per-line
  footprint; xmit line from the Squashed "Spec Read Request for PC.., Paddr" line. Flags a USL touching
  ANY forbidden structure in the spec window: L1_Replacement (eviction=UV1), L2_Replacement, L1 install,
  dir SpecFetch; reports TBE/MSHR alloc (NP/I>IX) as needs_pressure (UV2). Self-contained runner (reuses
  gem5_common helpers, own ProtocolTrace parse — does NOT touch the shared CheckFn hot path).
- launcher `results/STT_6_invisispec_compound/run_invisispec_compound.py` (forces --ruby + ProtocolTrace;
  `--patch-off` sets apply_spec_eviction_patch=False to repro UV1 on cache-missing tests).

**VALIDATED:** real ProtocolTrace parse (5 SpecLoad events); synthetic miss+evict → `touched_forbidden:
l1_eviction` + tbe_mshr_alloc; clean hit → `invisible_spec_hit`; live --ruby run on 6 const-hit tests = 0
forbidden, 0 errors (no classic aborts), spec hit invisible (SpecLoad M>M, no setMRU). NOTE: const-hit
corpus is all HITS → doesn't exercise eviction/TBE (need cache-MISSING tests + --patch-off to fire UV1);
also saw 4/6 `no_spec_access_in_window` under --ruby (timing/window differs from classic — worth a look).

## 2026-06-03 — 5:invisispec — DESIGN: compound load-transmission criterion (all µarch structures a USL must not touch) — hook map for all 3 amulet defenses → docs/COMPOUND_TRANSMISSION_CRITERION.md

Deep read-only exploration (no code/model touched) of where a speculative load touches each µarch
structure across InvisiSpec/SpecLFB/CleanupSpec, to design a COMPOUND criterion (not just cache-install)
that catches the AMuLeT bug classes. Transmission surface = L1 tag/LRU/eviction, MSHR/TBE, L2, directory,
D-TLB, L1I, prefetcher, contention — each maps to an AMuLeT bug (eviction=InvisiSpec UV1, MSHR=UV2,
I-cache=KV1, TLB=STT KV3, residue=CleanupSpec UV3/4/5).

Key findings:
- **Observability:** Ruby builds (InvisiSpec, CleanupSpec) have `ProtocolTrace` (CONFIRMED compiled) =
  full per-line per-controller transition+event footprint (L1/L2/dir); classic SpecLFB uses `Cache`+`Speclfb`.
- **InvisiSpec spec load:** HIT is clean (`h_spec_load_hit` OMITS `setMRU` — no LRU touch, vs `h_load_hit:994`).
  MISS touches: TBE/MSHR always (`iw_allocateTBEWithoutCacheEntry`, L1cache.sm:1230 = UV2 surface), L2 GETSPEC,
  and eviction IFF patch OFF (L1cache.sm:514 / L2cache.sm:386, `apply_spec_eviction_patch`=True default).
  Directory does transient I→II→I, no sharer add (invisible) BUT authors left `// Is it secure?` (dir.sm:499)
  — transient II observable to a racer.
- **SpecLFB:** LFB=safe place (`isLFB_RF`/`LFBLatency` cache.cc:806-892); tags handleFill/insertBlock; MSHR
  allocateMissBuffer (base.cc:270); evictBlock (cache.cc:999); ROB-mask base/unsafe_insqueue. CAVEAT to verify:
  is the L1 install actually WITHHELD for isUnsafe or only latency-delayed? key the checker on the `Block…moving`
  install line gated by isUnsafe.
- **CleanupSpec:** criterion FLIPS — it ALLOWS installs + undoes on squash (CleanupTable/rollback,
  EvictedLineAddrL1 tracking); leak = un-restored RESIDUE after cleanup (needs final-state/differential
  observer like AMuLeT). UV3 = writeCallback (Sequencer.cc:443) misses the cleanup metadata readCallback (:548) sets.

Impl plan in the doc: additive parse_ruby/parse_lsq per build → check_ld_compound with a per-STRUCTURE
outcome vector + touched_forbidden; exclude the safe buffer (SB/LFB); MSHR/contention tagged needs_pressure
(only leak under small-structure pressure, à la AMuLeT 2-MSHR/2-way). Read-only; nothing launched.

## 2026-06-04 — 8:alloyCheckUpdated — CORRECTION: nmosier STT bug = TWO-branch coinciding squash (commit 18e304f); our build is vulnerable; Alloy CLI CAN re-ingest XML into a 2nd model

**Two corrections, both Anna-directed.**

**(1) The nmosier known STT bug is the "pending-squash" TWO-branch coincidence — NOT the single-branch
VP-squash race.** Authoritative: `github.com/cwfletcher/stt` commit `18e304f` "fix pending squash bug"
(branch nmosier/bugfix/pending-squash, PR #10 `5bf4110`), `src/cpu/o3/iew_impl.hh:~1348`. Mechanism: a
YOUNGER UNTAINTED branch and an OLDER TAINTED branch resolving the SAME CYCLE produce a secret-dependent
squash signal (IEW notifies commit of only the older tainted mispredict, hiding the younger; vs notifies
the younger when the tainted branch is correctly predicted). **Our `/work/stt` HEAD `e3283b9` is NOT an
ancestor of the fix (`git merge-base --is-ancestor 18e304f HEAD` → NO; working-tree iew_impl.hh lacks the
"Tainted branch misprediction detected" code) → the build we sweep IS the vulnerable pre-fix version.**
Prior memory `project_coincidence_gap` said single-branch VP-race — now CORRECTED (it even pointed at
`sweep_design_notes.md §2` for the ≥2-branch class, which is exactly this bug).
*Why we don't hit it:* (a) **generation gap** — the Alloy model emits only ONE unresolved branch per test
(`sweep_design_notes.md §2`); this bug needs ≥2 mispredicted branches with MIXED taint (older tainted,
younger untainted). Structurally unreachable with one. Plus a framing gap: the observable is the younger
*untainted* branch's squash-redirect timing leaking the older tainted branch's outcome — not an
operand-in-protset transmit, so `check_br`/leak predicate must be extended. (b) **run-config** — the two
resolutions must coincide in one cycle; default sweep (`s_R≤2500`, `s_U=5000`) never collides. Needs the
coincidence band (`§1` item d) + commitToIEWDelay/squashWidth se.py bridge (`§3` item b). Recipe =
≥2-unresolved-branch `.als` dimension [owner sign-off] + checker squash-signal-dependence detection +
coincidence run-config. This supersedes the "VP-squash race is the nmosier bug" framing in
`bug/stt_slowcomm_vp_squash_race` / PAPER_RESULTS (that's a *separate, real* bug — keep it, but it is NOT
the pending-squash bug).

**(2) Alloy CLI/API CAN read a generated XML instance back into a SECOND model and recheck — the prior
subagent claim ("Alloy doesn't take an instance as input") was too pessimistic.** The pipeline writes
Alloy's NATIVE solution XML (`a6CountModels.java:52` `sol.writeXML(...)`; `<alloy>/<instance>/<sig>/<atom>`
with the command embedded). `alloy6.jar` ships `edu.mit.csail.sdg.translator.A4SolutionReader.read(
Iterable<Sig>, XMLNode)` → reconstitutes the instance bound to ANY model's sigs, and `A4Solution.eval(
Expr)` evaluates any predicate of that model against it. So a **second-stage recheck** (run instance
through a different defense's `secure_speculation_scheme_p`/`leakage_function`) is ~20 lines of Java on
the existing jar — and trivial here because all 3 defense models share the identical base (L1-307), so an
instance from one re-reads cleanly into another. *Decoration* (solve for ADDED non-interfering instrs on
a pinned instance) is also possible but harder: partial-instance bounds via an `inst{}` block or pinned
Kodkod bounds + enlarged `Instruction` scope (the closed facts `no_extra_ops`/`idx_surjective`/`spo_total`/
`exactly 6 Instruction` must be relaxed for the synthetic region, like parsexml's `no_extra_inst` carve-out
already does). Net: the two-stage "enumerate base → recheck/decorate in a 2nd Alloy stage" IS feasible on
the stock jar; recheck is cheap (evaluator), decorate needs a small custom driver.

## 2026-06-03 — 8:alloyCheckUpdated — ALLOY UP-TO-DATE AUDIT (pre-big-run): SPT_6_oneLP + Recon_6 need rf-last-writer fact; other_x + implicit-flow coverage gaps characterized; OTB/VP-race hittability traced

Read-only audit (no `.als`, no run touched) of the 3 latest models before a big generation run.
`latestmodels/*.als` == `STAGE1_alloy/models/*.als` (byte-identical).

**(1) Up-to-date verdict per model:**
- **STT_6 — UP TO DATE.** Has owner-approved `rf_from_most_recent_writer` (L163-169). const-addr correctly NOT a disqualifier for STT (speculation-taint, not data-taint). VP-squash race correctly stays a gem5 signal.
- **SPT_6_oneLP — NEEDS CHANGES.** (a) MISSING `rf_from_most_recent_writer` — owner-approved Option A, present in STT_6, not propagated here; add after L159 (exact fact = STT_6 L163-169). This is why rf-clobber (~58% clobber-shaped) is filtered gem5-side (`diag_rf_clobber`) instead of ruled out in alloy. (b) inaddr-cleanup (L356 `(i.inreg+i.inaddr)`) + `Stores.inaddr` in leakage_function (L344) are APPLIED, but the deployed testset is PRE-fix → REGEN from xml. (c) const-addr proper fix (seed protset from `Loads.outreg+Instruction.inmem` forward-closure at L341) is DESIGNED in POTENTIAL_MODEL_FIX_constaddr_taint.md but UNAPPROVED — largest disqualifier bucket; data-taint defenses only; keep load→load tainted. Owner decision needed.
- **Recon_6 — NEEDS CHANGES.** MISSING `rf_from_most_recent_writer` (same owner-approved fact, add after L159). const-addr correctly N/A (speculation-taint). recon-SLF (inst-014912) is a REAL bug, keep. OTB = coverage gap, see below.

**(2) other_x transmitter NOT covered (all 3 models).** `leakage_function` (STT L328) = `Loads.inaddr+Branchxs.inreg`; the `+Otherxs.inreg` variant is COMMENTED OUT (L327). So `speculative_xmit_p`/`tag_xm` can never tag an ALU op as the transmitter → `check_other.py` is effectively dead. Enabling L327 wholesale is NOT faithful for STT: a constant-latency ALU op has no operand→timing channel; only variable-latency ops (mul/div/shift) do. If wanted, scope to variable-latency ops, not a blanket `Otherxs.inreg`. Owner-gated.

**(3) Implicit-flow (`if(secret) x=A else x=B; load(arr[x])`) — STRUCTURALLY inexpressible, but NOT a model-too-conservative gap.** Branch has no outreg (L120), no ddi (L174), no outgoing rf (L156); single straight-line spo, no path-merge → secret can't reach a later value via control. Model captures ONLY the direct branch-direction channel (`Branchxs.inreg`). **Verified gem5-STT (/work/stt rob_impl.hh:809) taints args from `hasExplicitFlow` ONLY — `hasImplicitFlow` computed (L780) but never folded into value taint; `impChannel` only delays a *tainted branch's own* squash.** So STT itself does NOT defend the divergent-value gadget → it's an STT-PERMITTED leak (characterization: "STT leaves this open"), the opposite polarity from our model-says-no/gem5-says-yes signal. Adding it = a `cdep` control-dependence edge folded into `op_edges_p` (test-alloy sketch exists) + parsexml if/else concretization — owner-gated, and would be a *demonstration* of an STT gap, not a discrepancy hunt.

**(4) OTB hittability in STT.** SAT-WHEN-FORCED (cap/ordering artifact, NOT a model limit) — re-confirmed by running Alloy on a throwaway copy with `pred otb_shape {some x:Loads | x in xm and some o:(Otherns+Otherxs) | some (o.outreg & rf.(x.inaddr))}` → SAT, instance has other→outreg→xmit-load.inaddr. Recipe to hit: forcing predicate as a conjunct of the first `run` + `interleave.enabled:true` (injects the 2nd tainted chain onto the other's blank slot). **interleave is OFF in all current STT configs** (`run_config_STT_6.jsonc` interleave.enabled:false; `_latest` has no interleave block). Owner-gated dedicated OTB testset.

**(5) nmosier squash bug (VP↔squash race, A4) hittability.** The gadget IS generated (inst-047231, load-addr-from-older-spec-load; no Alloy change needed). Blocker is RUN-CONFIG: it's a `commitToIEWDelay≥2-3` timing race; stock O3 (delay=1) → 0 hits. **`commitToIEWDelay`/slow-comm is NOT wired into `pipeline.py:_build_gem5_env`** — only the experimental `se_slowcomm.py` applies it. To hit it in a normal sweep, plumb the knob through the config→env bridge. (Distinct from the store→D-TLB/DOLMA bug, which is intentionally out of scope: no store transmitter in leakage_function + TLB install unobservable in the pipeview/LSQ trace.)

Cross-cutting: every (1) fix is a Stage-1 change ⇒ regen testset from `xml --force`; existing SPT/Recon results are pre-fix and contaminated by exactly the rf-clobber/const-addr/nonspec/store buckets.

## 2026-06-03 — overview — CHECKER CHANGE: SpecLFB UV6 leak re-keyed on the actual L1 line-INSTALL (cache miss/fill), not the bare "Doing memory access" tick

Closes the long-standing SpecLFB open item ("memaccess over-approximates the L1 install — re-key on
the cache.cc/Cache install signal"). Affects **every SpecLFB load sweep** (`check_ld_speclfb.py`).

**What changed (pipeline-side, no gem5 source touched):**
- `gem5_common.py:parse_lsq` now parses the `Cache` debug flag. The trace pairs each load's
  `"Doing memory access for inst [sn:N]"` (lsq) with the FOLLOWING `dcache: access for ReadReq
  [a:b] hit|miss` line (same tick). New per-load fields `cache_fill_tick` (set ONLY on a MISS = L1
  fill/install) + `cache_access_outcome` (hit/miss). Pairing via a `pending_read_sn` cursor;
  conservative (a missed pairing leaves fill_tick=0). Loads=ReadReq; WriteReq ignored. No-op on
  builds without the Cache flag (fields stay 0) → other checkers unaffected.
- `check_ld_speclfb.py` LEAK signal moved from `memaccess_tick` → `cache_fill_tick`. UV6 leak now =
  **L1 install (miss) in (lc_retire,fnc_retire) + branches unresolved + `spec_unprotected`**. A load
  that accesses in-window but HITS a pre-warmed line installs nothing → new outcome
  `access_hit_in_window_no_install` (NOT a leak). New outcome `cache_install_in_window` = the real
  UV6 leak.
- `run_speclfb.py` DBG flag += `Cache` (else `cache_fill_tick` is always 0).

**Result on the 4 prior `cache_access_in_window` UV6 hits (inst-025820/033286/066668/083303):** ALL
now `access_hit_in_window_no_install` — every leaking load reads the pre-warmed const region
(0x35c0 etc.) and the dcache reports `ReadReq ... hit` (0 misses in the whole trace) → **0 concrete
L1 installs**. issued_in_window flips True→False.

**Interpretation (does NOT re-open the const-addr war):** consistent with the owner-confirmed UV6
verdict. The DATAFLOW SIGNAL (unprotected USL whose address is a spec-load index, accesses in-window:
`spec_unprotected` + `access_in_window`) is still present and real — SpecLFB leaves the first spec
load unprotected. The install gate measures the *concrete* cache-state leak, which the
zero-init/const-addr corpus cannot exhibit (the tainted index VALUE is 0 → const address → cache
HIT, no install). So the checker now cleanly separates **signal** (mechanism present) from
**concrete install** (needs the secret-addressed, cache-missing stimulus = test-gen extension #2).
Verified by hand on a keep-tmp Cache-flag trace for inst-025820.

## 2026-06-03 — results — Integrated the SimSpect results + figures into the S&P paper (/tests/S-P-27-SimSpect)

Cloned the two paper repos to /tests/ (S-P-27-SimSpect = main S&P paper; YArch-26-SimSpect-new = baby
paper, inspiration). Installed TeX Live (no engine before). **Added the results as new, additive
sections at the END of the S&P paper** (no existing files overwritten): new `results-simspect.tex`
(bug table centerpiece + bulleted findings + all-TikZ figures) and `results-methods.tex` (knobs /
concretization / instrumentation, bulleted); `paper.tex` +preamble(pgfplots/groupplots/colortbl/colors)
and two `\input` lines; `sample-base.bib`->`bib.bib` symlink so their `\bibliography{sample-base}`
resolves. **All figures are native TikZ/pgfplots/booktabs** (per owner: no matplotlib "random-font"
PNGs; no in-figure titles, captions only) and compile to a 12-page PDF (`paper.pdf`). Figures: bug
table (grouped by defense, the centerpiece), F2 amulet bug-coverage matrix, F8 3-panel timing
(tests-to-first 6 vs 39, density 23 vs 3.3, gem5-sim 0.092 vs 0.057 comparable), targeting, fragility,
stall-mask, **STLF mechanism diagram**, **LSQUnit trace example (inst-047231)**, and a **cycle-by-cycle
visibility-point<->squash race diagram in CheckMate µhb style** (instruction columns × location/cycle
rows, happens-before edges, red leak node, shaded race gap). NEW-bucket closures done earlier this
session: STT slow-comm 23,966 race / 0 unattributed; SPT restored to original buckets. Only compile
error is pre-existing `intro.tex:30` (their undefined macro, non-fatal). Rebuild: `latexmk -pdf paper`.

## 2026-06-03 11:15 — 1a:inspectSTT — RULED OUT a "taint-not-yet-set" window in STT (stage-of-tainting): commit-stage tainting is inefficient but NOT a correctness hole

Investigated **what stage STT applies taint at** and whether the (commit-stage) choice opens a
*transmit-before-taint* window — a speculative load issuing its cache access before `isArgsTainted`
is set, which would be a leak class distinct from the VP↔squash race.

**Where STT taints: COMMIT, not rename.** `rob->compute_taint()` is called from
`commit_impl.hh:1612`, inside `markCompletedInsts()`, which `tick()` invokes **unconditionally** at
`commit_impl.hh:728` (after `commit()` @726; the only early-return above it is
`activeThreads->empty()`, and ROB-squashing falls through to it). `rename_impl.hh` has **zero**
taint references. `explicit_flow` reuses rename's `getArgProducer` map but the computation is an
O(ROB)/cycle walk driven by commit.

**Why there is NO window (closed 5-link chain):**
1. Fence = `isArgsTainted()` **recomputed every IEW tick** (`lsq_unit_impl.hh:1013`), and
   `updateVisibleState()` (iew:1548) runs **before** `executeInsts()` (iew:1551) → fence re-derived
   immediately before any load issues. No conservative-default needed, none present.
2. `compute_taint` is **not starved by the fnc-commit-stall hook**: the stall blocks
   `commitInsts()` *progress*; `markCompletedInsts@728` (which runs compute_taint) is separate and
   unconditional → taint refreshed every cycle even while commit is pinned.
3. Taint is set **eagerly on the STATIC access bit**: load `isDestTainted` iff `isAccess() &&
   !isUnsquashable()` (rob:810-812) → tagged at dispatch, *pre-execution*, not at writeback.
4. Propagation is **single-pass head→tail** (producer tainted before consumer reads it in the same
   walk) → whole dep chain tainted in one compute_taint.
5. A tainted-address load **cannot issue until its address-producer (the secret load) has executed**
   — many cycles after dispatch — by which point compute_taint (every cycle since dispatch) has
   tainted the whole chain.

**Verdict: ⚪ NOT a bug.** Commit-stage tainting is *inefficient* (re-derives rename's producer map
each cycle, O(ROB)/cycle) but the eager static-access tainting means "computed at commit" never lags
"executes in IEW" — the taint is already set before the load is even ready. The only genuine STT/SPT
hole on this thread remains the **VP↔squash race** (untaint keyed on `isPrevBrsResolved`/
`isPrevInstsCompleted` = *executed*, not *committed*; the precise `isPrevBrsCommitted`/
`isPrevInstsCommitted` are computed but used only in a debug printf — rob:1041-42 — never gated on).
Read-only source trace; no source/model/run touched.

## 2026-06-03 11:40 — 1a:inspectSTT — SPT untaint logic audited end-to-end: conditions SOUND; one root imprecision (VP gate); fwd/bwd spread-not-worsen; tier-untaint unsafe-but-OFF

Read-only audit of **every** untaint path in SPT (`/work/gem5-spt`), prompted by "is all the untaint
logic precise — there's so much to mess up." Our live config: `scheme=2` SpectreSafeFence,
`--fwdUntaint=1 --bwdUntaint=1`, `untaintTier=0` (default, none set it), `idealUntaint=0` (default).

**Four mechanisms, with verdicts:**
1. **VP untaint (`UntaintMethod::ReachedVP`)** — the ROOT. Keyed on `isPrevBrsResolved`/
   `isPrevInstsCompleted` = *executed*, not *committed* (lsq_unit:1216-17). = the one known
   VP↔squash race. The only real imprecision.
2. **Forward untaint** (`rob_impl.hh:799`): `!isMemTransmit() && !argsTainted && destTainted` →
   untaint dest. ✅ SOUND (non-load with all-safe inputs ⇒ safe output). `isMemTransmit()=isLoad()||
   isStore()` (base_dyn_inst:731) correctly excludes the only dangerous case (a load's dest =
   memory content, not a fn of its addr args). Adds no new imprecision; propagates VP forward.
3. **Backward untaint** (`rob_impl.hh:850`, SPT-specific/Rutvik): ADD/SUB with non-CC dest untainted
   + exactly 1 tainted src → untaint that src; MOV with untainted dest → untaint src[1].
   🟡 INFORMATION-THEORETICALLY SOUND (src = dest∓other; if result+other-operands public, remaining
   operand is algebraically determined ⇒ no extra secrecy). Fires in "result reached VP but an
   input's producer hasn't" → back-props the result's publicness to inputs. Inherits VP-race, adds
   no new too-early condition. Most intricate → the one to spot-check empirically.
4. **Tier-based UNCONDITIONAL untaint** (`base_dyn_inst_impl.hh:346+`): RBP/RSP (tier≥1), RSI/RDI
   (tier≥2) forced `newTaint=false` regardless of taint. ⚠️ GENUINELY UNSAFE (silently declassifies
   a secret routed through those regs) — but OFF (untaintTier=0 everywhere). **MUST stay off on these
   testsets** — gadgets address through RSP/RSI/RDI, so enabling it would blanket-suppress real leaks.

**Application:** masks → `untaintQueue` → `setPartialTaint(physReg,false,size,offset)` (rob:988) at
**byte granularity**, globally on the physreg, one hop/cycle (idealUntaint=0). The byte-level
partial-taint (x86 sub-register/zero-extension) is the one IMPLEMENTATION spot a subtle over-untaint
could hide — distinct from the conditions being sound; check it if an unexplained SPT load hit shows.

**VERDICT:** untaint is a propagation network (VP root + fwd/bwd spreading it). Conditions all sound;
fwd/bwd WIDEN the REACH of the VP-race untaint but don't WORSEN its correctness — still exactly one
too-early untaint (the VP gate). **Available differential** (not yet run): untaint-ON (SPT_6_oneLP/
_full) vs untaint-OFF (SPT_6_disableUntaint) on the SAME testset → any in-window leak that's untaint-
on-only AND not VP-race = a real fwd/bwd imprecision; else fwd/bwd just spread the race. No
source/model/run touched.

## 2026-06-03 10:30 — 2a:inspectSPT — br_x diagnostic shipped: diag_branch_wrongpath_respec buckets 597/677 (retq/loop re-spec); 80 NEW (gap-band) remain — softens the earlier "0 genuine branch leaks"

Built `diag_branch_wrongpath_respec.py` (+ .md) in both SPT runs' diagnostics/ (standalone gem5 diag,
diag_stt_vp_squash_race pattern). Signature (conservative): xmit branch NEVER COMMITS *and* (a `retq` is
immediately before its block = retq fall-through, OR it is re-fetched after a GADGET — non-entry-stub —
mispredict has drained = loop back-edge). Else stays NEW (redirect_in_primary_window / xmit_committed /
no_redirect). gem5-spt DOES protect branches (delays tainted branch redirect to VP), so an in-window
redirect here is gadget control-flow re-speculation, not a defended-branch failure.

FULL run (677 slowcomm br_x hits, both modes): **597 wrongpath_respec (580 retq + 17 loop) + 80
redirect_in_primary_window (NEW)**. So 88% are the verified retq/loop artifact.

CORRECTION to my 09:30 "0 genuine SPT branch leaks": that was the 16 SPEC-LOAD candidates (all retq/loop,
post-drain). The FULL br_x set has an 80-stem **resolution→drain-GAP** band (controlling gadget mispredict
resolves but the xmit redirect precedes its drain) that the wrongpath_respec diag conservatively does NOT
claim. These 80 are most likely non-spec-condition model over-approximations and/or the branch VP-squash-
race band, but they are NOT yet analyzed — do not claim them closed. NEXT: either a second XML
`diag_nonspec_branch_cond` (caveat: single-Reg_s opstate collapse makes the XML condition-source
unreliable) or a per-stem gem5 pass on the 80. check_br window fix + bucket_hits br_x glob still TODO.

## 2026-06-03 09:30 — 2a:inspectSPT — FULL SPT slowcomm_fence triage COMPLETE: loads = model/concretization bugs + ~3807 genuine VP-race; branches = 0 leaks (wrong-path re-speculation + over-approx). 2 owner-approved model fixes + 3 diags. (Ties together 22:40→08:00 entries; supersedes the no_hold "realizability gap" framing.)

Scope: `results/experiments/spt_slowcomm_fence__20260602_121858` + `results/SPT_6_oneLP_fence__20260602_013615`
(both SPT_6_oneLP testset, gem5-spt SpectreSafeFence+DDIFT). Driven interactively with Anna.

### SPT TAINT MODEL (verified; corrects my earlier shadowL1 error)
- Taint source = rob_impl.hh:240 — EVERY load taints its dest unconditionally (speculation-INDEPENDENT).
  shadowL1 is OFF (boot: "Shadow L1 enabled? no"). Fence gate = lsq_unit_impl.hh:1180
  fenceDelay=isAddrTainted(). Untaint at the visibility point (untaintMemTransmit, :1207).
- OWNER FACTS: (a) loads do NOT necessarily untaint their OUTPUTS on commit — model reflects that;
  (b) the VP *address*-untaint IS correct/in-model; (c) "a committed thing transmitting a value untaints
  it." Do NOT reason "producer committed/reached VP ⇒ its output untainted." See reference_spt_taint_model.
- gem5-spt DOES protect branches: delays a tainted branch's redirect until VP (fetch_impl.hh:1004,
  commit_impl.hh:944, rob_impl.hh:1072).

### TWO OWNER-APPROVED MODEL FIXES (STAGE1_alloy/models/SPT_6_oneLP.als)
1. line 353 protset cleanup: `i.inreg` → `(i.inreg + i.inaddr)`. The de-protection of a consumer whose
   rf-source left the protset only covered inreg; loads transmit via inaddr (have no inreg, fact ld_ops),
   so a speculative load-address transmitter of an already-non-speculatively-leaked value was never
   dropped. Verified differential a6CountModels: bug shape SAT→UNSAT, normal gen + race shape preserved.
2. leakage_function += Stores.inaddr (ALL stores — tests decide if committed matters). Feeds BOTH
   speculative_xmit (stores can be flagged) AND nonspeculative_xmit (line 348 de-protection / the "VP
   thing") since both derive from leakage_function. Verified UNSAT for store-co-transmit shape; normal
   gen preserved; ~36% of generated now have a store xmit (leak-side expansion).
   ⚠️ SAME GAPS still in SPT_6_full.als, SPT_6.als, SPT_6_oneLP_noSTLF.als (not fixed). REGEN needed for
   the fixes to take effect (current testset is pre-fix).

### THREE DIAGNOSTICS (in both runs' diagnostics/, + .md each)
- diag_nonspec_cotransmit.py (ORDER 30): xmit value also rf-transmitted by a non-spec load/branchx.
- diag_store_cotransmit.py (ORDER 35): ditto, non-spec STORE co-transmitter.
- diag_rf_clobber.py EXTENDED with manifestation (b): sibling NON-SPEC transmitter via SHARED OPSTATE
  (the single-Reg_s collapse → all reg operands collapse to one register; a blank-operand load/store/
  branchx collides onto the xmit's value and transmits it). rf-fed excluded (that's nonspec/store). The
  three are DISJOINT (0 overlap).

### LOADS — verdict
oneLP_fence (stock): constaddr 6040 + rf_clobber 65 + nonspec 7 + store 6 + NEW **0**.
slowcomm_fence (live): constaddr 67k + rf_clobber 5882 + nonspec 358 + store 23 + NEW ~3995.
ALL 64 no_hold explained: 25 rf_clobber + 28 nonspec + 11 store (0 genuine). The 3 model/concretization
bugs ALSO contaminate the race bucket: 695 of 4502 vp_squash_race are these bugs → **~3807 GENUINE
vp_squash_race** (the slow-comm VP↔squash timing race) is the only real load signal. (no_hold was NOT a
"realizability gap" — that earlier framing in mdsToRead/SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md is superseded.)

### BRANCHES — verdict: 0 genuine SPT branch leaks
677 br_x hits = 669 not_taken + 8 taken. 661/677 have a NON-speculative condition (other-op/committed/
const) → architectural direction → model over-approximation. 16 have a speculative-LOAD condition (the
only candidate shape). ALL 16 are wrong-path RE-SPECULATION artifacts — the xmit branch NEVER COMMITS
(that path architecturally never occurs, per Anna) and is re-fetched by the gadget's OWN control flow
AFTER the controlling mispredict already resolved (~70-79 cyc later, not in the primary spec window):
  • 12 = retq FALL-THROUGH (codegen lays the xmit branch immediately after the gadget's `retq`; the
    gadget is callq'd so there's a real RAS; fetch runs past the return into the xmit). 
  • 3 = LOOP re-speculation (branches loop to a mid-gadget target; wrong-path region re-fetches the xmit).
Same family as the STT ret/RAS issue (claudelog 05:00). NOT fnc-stall-driven in SPT (verified identical
at fnc150/fnc0 for the retq ones). My two earlier calls ("check_br window-too-wide FP", then "branch
VP-squash race") were BOTH WRONG; Anna's "path never architecturally occurs / is it the RAS issue" was
right. check_br over-counts: the correct discriminator is **redirect must precede the controlling
mispredict's resolution** (all 16 fail it). check_br fix (bound window by controlling-mispred resolution)
is a CHECKER fix, not a diagnostic — not yet written.

### OPEN / TODO
- REGEN SPT_6_oneLP from the fixed model (owner call) → re-bucket to confirm the model-bug buckets drop.
- Propagate the 2 model fixes to SPT_6_full/SPT_6/oneLP_noSTLF (owner call).
- br_x not yet bucketed by bucket_hits (globs ld only); would need const-condition + rf_clobber-inreg
  diags + bucket_hits br_x glob.
- check_br window fix.
- Tooling: --trackInstsFile aborts (regfile.hh:280 off-by-one) — taint trace unusable; used untaint STAT
  counters (VPUntaints etc.) instead. bucket_hits REPO heuristic needs explicit --xml-dir for
  results/experiments/<run>.

## 2026-06-03 — results — Updated the deliverable to the corrected UV6 verdict (per the RE-CORRECTION below) + started the AMuLeT A/B timing comparison

Owner (Anna) confirmed UV6 is NOT a false positive. **Supersedes the UV6 bullet in my "results" entry
below** ("mechanism reproduced, 0 demonstrable leak" was WRONG). Propagated through every deliverable
(no code/model/run touched):
- **`PAPER_RESULTS.md` §0/§3/§4/§9** — UV6 reframed to **DEMONSTRATED**: SpecLFB leaves the first unsafe
  spec load unprotected and **68/300 access cache in-window** (`isCUSL=1, isUnsafe=0`), held to the
  *same bar* as STT A4 / SPT A5. Unifying principle: **const-addr (C2) disqualifies *data-taint*
  defenses (SPT-Fence/DDIFT) ONLY** — for *speculation-taint* defenses (STT, recon-STT, SpecLFB) the
  transmitter is protected by virtue of being speculative, so const-addr does NOT disqualify (answers
  Anna's "const-addr shouldn't apply to STT?" — correct, and it never was). Sharper still (RE-CORRECTION
  below): the xmit is an **indexed load whose index is fed by a spec load** = a real tainted-address
  gadget; runtime addr is fixed `0x3580` only because the index VALUE is 0 (zero-init prologue). Pending
  = a non-zero secret index for a footprint-varying **secret-recovery PoC** (C2 stimulus half), NOT for
  calling UV6 found. Figures F2{a,b,c} + methods docs updated to match.
- **AMuLeT efficiency comparison (A + B): DONE, MEASURED.** Wired AMuLeT's `cli.py fuzz --SpecLFB` to
  the SpecLFB_AE build (abs `--gem5-binary/--gem5-se`; the `autorun.py` author-path default is
  overridable) — **runs end-to-end + finds SpecLFB contract violations.** Results
  (`results/STT_6_speclfb/amulet_compare/fuzz.log`, `-n 120 --nonstop --profile`):
  **(A) detection** — SimSpect first UV6 @ **test #6**, **23%** density (68/300); AMuLeT first violation
  @ **test #39**, **3.3%** (4/120) → SimSpect **6.5× fewer tests, ~7× denser** (targeting).
  **(B) gem5 time (Anna: exclude our build + the pipeview measurement → JUST gem5)** —
  `/tmp/time_gem5_only.py` decomposes SimSpect's per-test wall: gem5 SIM `hostSeconds`=**0.092 s/test**
  (light trace) vs AMuLeT `m5.simulate`=**0.057 s/test** → **COMPARABLE (~1.6×)**. SimSpect's earlier
  "~40× slower" was entirely the O3PipeView *measurement* trace (+0.39 s/test sim) + *fresh gem5 boot*
  per test (+0.61 s wall, AMuLeT amortizes via persistent IPC) + as+ld build (0.03) — all harness/
  instrumentation, NOT simulation. So per-test gem5 work is the same; with the 6.5× targeting edge,
  SimSpect reaches the bug with **~6.5× less total simulation**. **Complementary: SimSpect wins
  targeting; AMuLeT's input-differential supplies the observable footprint SimSpect's zero-init corpus
  lacks** (§4 stimulus gap, other side). Figures **F8{a,b,c}** (F8b = the decomposition); 20 PNGs total;
  `PAPER_RESULTS.md` §0/§8 updated. No SimSpect code/model/run touched.

## 2026-06-03 — 5:invisispec — RE-CORRECTION: SpecLFB UV6 hits are NOT const-addr FPs — the xmit address IS tainted (my prior "const-addr" verdict was WRONG)

Supersedes my earlier "68 = const-addr FPs / not indicative / 0 demonstrable leak." I re-checked the
ACTUAL asm of the hit gadgets and was wrong. The xmit load is an INDEXED load
`movq (%base,%index),%dst` (verified 6/6 hits) → address = base + %index, where %index is the value
from an EARLIER SPECULATIVE load (inst-002014: %rdx ← pc3 `movq (%r8),%rdx` on the mispredicted path).
That is a genuine load→address Spectre gadget — the address operand carries speculative taint; the
dataflow into the address is INTACT, not collapsed.

The runtime address is the fixed 0x3580 ONLY because the index VALUE is 0 (prologue zero-inits the
scratch buffer → the speculative load reads 0 → base+0). That is the INPUT VALUE being zero (no
non-zero secret seeded), NOT the address operand being a hardcoded constant. My error was conflating
"concrete addr constant this run" with "addr operand constant" — only the former is true.

**Corrected verdict:** under SimSpect's dataflow signal (tainted operand reaches transmitter in spec
window), the 68 ARE VALID SpecLFB UV6 hits: a load whose address depends on speculative data issues its
cache access in the spec window, and SpecLFB leaves it unprotected (isUnsafe=0). The 4
`protected_lfb_access` are the control (same gadget, SpecLFB classified isUnsafe=1 → LFB-held). The
zero index only blocks a CONCRETE leak demonstration (footprint variation needs a non-zero secret) —
not the dataflow signal, which is what we track.

**ACTION: the "const-addr FP" framing must be undone wherever it propagated** —
results/STT_6_speclfb/SPECLFB_UV6_REVIEW.md (being fixed), project_speclfb memory (fixed), AND
PAPER_RESULTS.md (the `results` session baked the wrong const-addr verdict — needs updating by that
owner). Lesson: check the gadget asm (addr = base+index from a spec load) before calling a load hit
"const-addr"; a zero-valued tainted index looks like a constant address at runtime but the operand is tainted.

## 2026-06-03 — results — Compiled the SimSpect RESULTS WRITEUP + figure set + 3 methods docs for Anna (read-only synthesis; no code/model/run/`.als` touched)

Pulled every settled finding into a reviewable deliverable. **All numbers sourced from disk/claudelog**
(provenance in each figure-script comment); nothing re-run.
- **`PAPER_RESULTS.md`** — the writeup. By-defense findings (recon **OTB A1** + **STL/SLF A2** = the live
  one, `inst-014912`; STT **VP↔squash race A4** + *why SimSpect doesn't/​shouldn't find the store→TLB bug*
  — `leakage_function` has no store transmitter, `STT_6.als:328`; SPT **same race A5**, no independent SPT
  bug). AMuLeT **scope** (1 of 8 bugs in our model = SpecLFB **UV6**) + **test targeting** (AMuLeT 85/500=17%
  can leak vs SimSpect 100k=100% via `tag_xm`). **Stall sweep** (s_U masks 27→0, s_R flat, fnc plateau, all
  bucket-confirmed `stt_vp_squash_race`) + **fragility** (STT 0→20→41→42 across commitToIEWDelay 1-4; Fence
  raw=const-addr) + the *why-timing-mods-are-legit* argument. **§8 = the one thing still to run**: an AMuLeT
  timing/detection-efficiency comparison on the SpecLFB build (needs the const-addr stimulus fix + an AMuLeT
  fuzz run) — NOT started, flagged for go-ahead.
- **`paper_figures/`** — `make_paper_figures.py` (reproducible, numbers baked w/ provenance like
  `bug/graphs/make_graphs.py`) → 17 PNGs, **3 candidates per data slot** (F1 attribution, F2 amulet scope,
  F3 targeting, F4 stalls, F5 fragility) + F6 VP-squash timeline + F7 recon schematics. README indexes them.
- **3 methods docs** (standalone, design-rationale; user asked for alternatives): `METHODS_LEAKAGE_KNOBS.md`
  (every knob, 7 tiers), `METHODS_CONCRETIZATION.md` (enum + parsexml passes, why each exists),
  `METHODS_INSTRUMENTATION.md` (the 3 control hooks / config glue / observation; realize-not-alter contract).
- **Kept honest:** SpecLFB UV6 = *mechanism reproduced live, 0 demonstrable leak* (the 68 in-window are
  const-addr FPs, prewarmed paddr 0x3580 — same **C2** gap that inflates SPT-Fence; per the 5:invisispec
  correction below). C1/C2 over-approx is both the dominant false-signal AND the UV6 blocker; closing C2 is
  the highest-value next fix.

## 2026-06-03 — 5:invisispec — CORRECTION: SpecLFB UV6 mechanism CONFIRMED but the 68 "leaks" are CONST-ADDR FPs (no demonstrable leak on STT_6)

Supersedes my earlier "72/300 UV6 candidates". After making the checker correct + a direct L1D
cache-state check, the rigorous verdict:
- **UV6 mechanism CONFIRMED present**: SpecLFB leaves the first speculative load unprotected. Verified
  per-load via the `Speclfb` debug flag: xmit load has `isCUSL=1` (genuine conditional USL, should be
  protected) but `isReallyUnsafe=0`/`isUnsafe=0` (the AMuLeT Fig.8 first-spec-load exemption). Added
  parse_lsq `spec_cusl`/`spec_unprotected` (additive, Speclfb-flag) + gated check_ld_speclfb on it.
  300-sample: 72 memaccess-in-window → 68 unprotected-USL + **4 `protected_lfb_access`** (isUnsafe=1,
  LFB-held = SpecLFB correctly protecting = the control proving the defense engages).
- **BUT the 68 are NOT demonstrable cache leaks = CONST-ADDR over-approximation.** `--debug-flags=Cache`
  on 8 of them: every xmit load reads the SAME fixed paddr **0x3580**, which the litmus PROLOGUE
  zero-init stores already install in L1 (tick 188000). The speculative load is a `ReadReq … HIT` on a
  pre-warmed CONSTANT line → no miss, no secret-dependent install, no cache-state change → NO side
  channel. Same artifact as recon/STT/SPT load FPs (diag_constaddr_load / diag_ld_cache_reach).
- **Root gap = STIMULUS not defense/checker:** SimSpect STT_6 load transmitters concretize to a fixed
  scratch addr (not secret-dependent) + prologue pre-warms it. Real UV6 (or any load cache leak) needs a
  secret-DERIVED, cache-MISSING load address (AMuLeT Fig.8b `MOV RAX,[R14+secret]` on a flushed buffer).
- **Lesson (reinforces the load-checker rule):** "memaccess/cache-access in-window" is necessary but NOT
  sufficient — must post-filter by cache-reach/install + secret-dependence (hit on const line ≠ leak).
  SpecLFB build + check_ld_speclfb are ready; the gap is a secret-addressed load gadget testset.
Writeup REWRITTEN: results/STT_6_speclfb/SPECLFB_UV6_REVIEW.md.

## 2026-06-03 08:00 — 2a:inspectSPT — MODEL FIX (owner-approved): SPT_6_oneLP.als protset propagation now de-protects `inaddr` consumers, not just `inreg` — removes the "value also leaked non-speculatively" false leaks

ROOT CAUSE (Anna-guided): the `no_hold` SPT hits trace to a MODEL-GENERATION bug, not gem5/pipeline.
The Alloy leak predicate flagged a speculative load-transmitter whose address value is ALSO transmitted
NON-speculatively by an earlier (pre-branch) load — e.g. inst-021701: pc1 load → %rax feeds BOTH pc2
(non-spec address-xmit, before the mispredict) AND pc4 (the tagged spec xmit, after it). Since pc2
already leaks %rax architecturally, pc4 leaks nothing new → should not be flagged.

The protset update rule `prot_set_propagation_p` DID drop %rax from the protset (line 348 backward
closure from the non-spec xmit pc2), but the companion rule that removes a CONSUMER whose rf-source left
the protset was keyed on `i.inreg` ONLY (old line 353). Loads have NO inreg (`fact ld_ops`) — they
transmit through `inaddr` — so a speculative load-address consumer (pc4) was never de-protected. Gap =
inreg-only cleanup.

FIX (one line, line 353): `- (i.inreg & (Operand - o).(rf_p[p]))`  →
`- ((i.inreg + i.inaddr) & (Operand - o).(rf_p[p]))`.

VERIFIED via differential Alloy run (scratch copies, a6CountModels), test predicate = a generatable
litmus whose load-xmit address shares its rf-source with a non-spec transmitter:
  - original: SAT (bug shape generatable) — `for 5` gives 3, `for 9` gives 5.
  - fixed:    UNSAT (0) at `for 5`  → shape eliminated.
  - fixed still generates the normal testset (gen_lit 150/150 at cap 150) — not over-constrained.
  - RACE shape (xmit fed by a load that is ITSELF speculative/under the unresolved branch) still SAT
    under the fix → genuine speculative leaks preserved.

SCOPE / TODO (owner decisions):
  - Applied to SPT_6_oneLP.als ONLY. SAME gap (inreg-only line) in SPT_6_full.als, SPT_6.als,
    SPT_6_oneLP_noSTLF.als → fix there too? (not done.)
  - The current SPT_6_oneLP TESTSET is now STALE (generated pre-fix). Needs regen-from-XML to take
    effect. The live slowcomm_fence watcher (pid 3139363) sweeps the OLD testset — unaffected but its
    results reflect the pre-fix model. NOT regenerated (owner call).
  - Coverage caveat: fix provably removes the inst-021701 class (value also non-spec transmitted). How
    many of the 64 `no_hold` (and whether any `race`) it eliminates needs a regen + re-bucket to confirm.
  - mdsToRead/SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md framing ("model over-approximation") should be updated:
    this was a fixable model-generation bug (inreg/inaddr), now patched.

## 2026-06-03 05:00 — 1a:inspectSTT — FINAL on slowcomm br_x: the 46 "leaks" are caused by the fnc-commit-stall HOOK, NOT STT (STT==Unsafe). Supersedes my 04:30 "real bug"

**Controlled matrix settles it (3rd and final verdict; Anna pushed: "is the fnc hook the cause?").**
Isolated the variable: `se.py` × `fnc_commit_stall_cycles` × scheme, on the 46 br_x "REAL" candidates.
- **fnc-stall=150 → 46/46 redirect in [VP,drain] gap (leak). fnc-stall=0 → 0/46 (gap collapses ~620cyc → ~5cyc).**
  The fnc-commit-stall hook is the SINGLE variable that flips leak↔no-leak.
- **scheme 2 (STT) == scheme 0 (UNSAFE), byte-identical, at every setting.** STT is NOT delaying squash
  propagation and is not involved. So this is NOT an STT bug.
- **Mechanism:** `--fnc-commit-stall-cycles=150` pins the boundary `fnc` at the commit head 150cyc after
  it resolves → ROB can't drain → wrong-path region keeps re-speculating (gadget `ret`/RAS) → xmit
  re-redirects repeatedly inside the artificially-held post-VP window. fnc0 → fnc commits promptly, ROB
  drains, one redirect at VP (~5cyc), nothing in a gap. xmit never commits in any config (architectural
  path = fnc→endblock→ret, as designed).
- **Verdict ⚪ instrumentation/timing artifact of the fnc-stall hook** (fine to keep the hook; it just
  means these 46 aren't an STT defense failure). 🟢 STT branch == Unsafe. **0 real STT branch leaks.**
  185 of 231 br_x are check_br FPs (no secret feeds branch); the 46 are this fnc-stall artifact.
- ⚠️ **OPEN — applies to the LOAD race too:** the 19,845 ld `stt_vp_squash_race` (currently THE filed real
  STT bug) runs with the same fnc-stall=150. Must re-run loads at **fnc0 + STT-vs-Unsafe diff** to confirm
  the load race is genuinely STT (delay_unit + untaint-at-VP), not fnc-stall-manufactured like branches.
  designconsultant attributed loads to slow-comm `commitToIEWDelay` (a different knob), so loads MAY
  differ — but verify, don't assume. This could affect the headline real-bug count.
- Review md (final, corrected): `…/diagnostics/BR_X_slowcomm_REVIEW.md`. Supersedes my 04:30 (REAL),
  03:30 (FP via window-gap), 01:30 entries.

## 2026-06-03 — 6:invisispec — SpecLFB INSTRUMENTED for SimSpect; UV6 mechanism CONFIRMED live (72/300 candidates); CleanupSpec out of scope

**SpecLFB now runs through SimSpect** (`/work/amulet/amulet-gem5-SpecLFB_AE-v1.1`, build/X86, NEWER
gem5 base/argparse). Config-side glue (no recompile): Options.py --scheme accepts "2"; se.py maps
"2"→"Speclfb"; **--branch-ann-base fixed to parse hex** (argparse type=int couldn't parse gem5_common's
0x… → that was the blocker that made every test error). Added additive `memaccess_tick` to parse_lsq
("Doing memory access for inst [sn:N]" lsq_unit.cc:1766 — the newer base has NO "successfully sent out
packet" line). New checker `STAGE3_gem5/check_ld_speclfb.py` (leak = cache access in-window). Launcher
results/STT_6_speclfb/run_speclfb.py.

**UV6 (AMuLeT first-spec-load-unprotected) mechanism CONFIRMED live:** xmit loads are genuine USLs
(isCUSL=1, prior br unresolved) but SpecLFB leaves them unprotected (isReallyUnsafe=0, isUnsafe=0) =
the first-spec-load exemption (AMuLeT Fig.8). Verified via Speclfb debug flag on 6 tests. Sibling
non-first loads show isReallyUnsafe=1 (protected) → defense engages, first load escapes. 72/300 (24%,
mispredict_not_taken) of these unprotected xmit loads access cache in-window = UV6 leak CANDIDATES.
Unsafe-baseline control = byte-identical (CONSISTENT with UV6: xmit unprotected under both; NOT a refutation).

**OPEN (do not over-claim):** memaccess may over-approximate the L1 install — inst-014986 is
isReallyUnsafe=1 (protected) yet flagged in-window (protected loads can hit "Doing memory access" =
LFB access w/o installing). Next step: key leak on the actual L1 line-install (cache.cc/Cache debug,
classic-cache build) and re-count. Full writeup: results/STT_6_speclfb/SPECLFB_UV6_REVIEW.md.

**CleanupSpec setup audited** (`/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1`, Ruby MESI, OLDER templated
base → parse_lsq works). Hooks ARE ported (BTB-force, resolve-stall iew_impl.hh, branch-ann). BUT worst
SimSpect fit: CleanupSpec INTENTIONALLY installs spec loads in cache and cleans up on squash
(issueCleanupRequest/processCleanup) → check_ld would flag every spec load (by-design install, not a bug);
its real bugs (UV3/4/5) are POST-SQUASH cleanup correctness = final-cache-state differential, which
SimSpect doesn't observe. Out of scope (matches docs/AMULET_VS_SIMSPECT_SCOPE.md). Runnable but not
meaningfully testable here without a post-squash cache-state observer.

## 2026-06-03 04:30 — 1a:inspectSTT — 🔴 REAL BUG: STT VP↔squash race on the BRANCH channel, present at STOCK se.py (reverses my own FP verdict; Anna was right)

**This REVERSES the 03:30 "br_x = all check_br FP" verdict. 46 of the 231 br_x slowcomm hits are REAL
leaks** — the branch manifestation of the STT visibility-point↔squash race (same root cause/class as the
19,845 ld `stt_vp_squash_race`). Anna pushed twice and was right both times:
- **A redirect that occurs before the branch is squashed IS a leak** (the same standard we apply to
  loads), not a FP. My "non-secret post-resolution" framing wrongly held branches to a stricter bar.
- **Mechanism:** xmit branch condition is fed by a speculative load (`%rcx←%rax←load`, dataflow-verified).
  When the controlling branch resolves (VP=`fnc_complete`), STT clears the load's taint (it becomes
  unsquashable → branch `isArgsTainted`=`hasExplicitFlow`→false, `rob_impl.hh:809`), so STT does NOT
  make the branch pending. But the squash that should kill the wrong-path branch is delayed (doesn't
  drain until `fnc` retires). In the **[VP, drain] gap** the wrong-path xmit broadcasts its mispredict
  redirect = observable control-flow leak of the secret-derived direction.
- **Evidence (stock vs slowcomm):** all 46 at **stock se.py**: 46/46 xmit redirects, 46/46 every redirect
  in [VP, drain], 0/46 ever commit (architecturally control still goes fnc→endblock→ret as designed —
  the leak is purely the speculative redirect). So **NOT slow-comm-only** (unlike the SPT load race) →
  a genuine stock STT bug. inst-021185: VP 2948500, drain 3181500, redirects 2957500/2964500/…
- **Ruled out BTB-instrumentation artifact (Anna's check):** both branches are `mispredict_not_taken` →
  forced target 0 → never added to `btbForcedTargets` (`bpred_unit.cc:82`), and the predict-time override
  (`:323`) only fires for that map → **no-op**. `resolve_stall_cycles=0` too. Empirically **branch-ann ON
  vs OFF is byte-identical** at stock (same redirect ticks/VP/drain). The misprediction is the natural
  predictor (not-taken default on an actually-taken branch); the speculation+leak are genuine.
- **Verdict 🔴 real gem5/STT bug** — "STT VP↔squash race, branch (implicit) channel." 46 instances. The
  other 185 br_x are genuine check_br FPs (no speculative load feeds the branch). **Action:** add a
  branch-variant `stt_vp_squash_race` bucket to the diagnostics (parallel to the ld diag) so these are
  counted as the known real bug, and a `bug/` catalog entry. Review md (rewritten, REAL verdict):
  `results/experiments/stt_slowcomm_full__latest/diagnostics/BR_X_slowcomm_REVIEW.md`.
- ⚠️ Supersedes my 03:30 and 01:30 br_x entries (both wrong on the FP conclusion). The ld result is
  unchanged (19,845 race + 21 FP + 0 NEW).
- **Open:** the xmit redirects multiple times (re-speculation while `fnc` is held un-drained; `fnc`
  commits 3×) — the first in-gap redirect is the clean leak; whether later ones re-read the secret vs a
  post-VP reload is a tightening detail, not load-bearing for the verdict.

## 2026-06-03 — reconHitDiag — Moved top-level `run_config_*.jsonc` → `runconfigs/` (per-results configs UNTOUCHED)

The 19 repo-root `run_config_*.jsonc` templates now live in `runconfigs/` (git mv). **How to invoke
changed:** `--config runconfigs/run_config_X.jsonc` (was `--config run_config_X.jsonc`). Updated the
examples in `CLAUDE.md` + `Makefile`. Safe because: only referenced via explicit `--config`; no live
process used them; `load_config` doesn't chdir and inner paths (`testsets`, `results`, `STAGE1_alloy`)
resolve against CWD (repo root), so running from root still works. **NOT moved (deliberately):**
`results/<name>/run_config.jsonc` (22) + `results/experiments/.../run_config.jsonc` + `latestmodels/`
— live watchers/manifests/diagnostics reference those by exact path and a campaign must stay
self-describing; moving them would break in-flight sweeps + reproduction.

## 2026-06-03 — 6:invisispec — InvisiSpec×STT_6 ld run: 0 leaks (defense holds); SpecLFB instrumentation assessed

Ran the expose-in-window checker (check_ld_invisispec.py) on STT_6 load transmitters vs the
amulet InvisiSpec build (SpectreSafeInvisibleSpec, TSO, 1500/mode, stall=5000). Results in
results/STT_6_invisispec/{mode}/window-results.json + RESULTS.md. **0 hits both modes** — every
USL squashed before its visibility point (never_exposed_squashed); no VP↔squash race. Expected
negative control. not_taken is the meaningful mode (345/1480 had in-window spec reads = USLs
genuinely exercised); **taken mode mostly degenerate for ld (1000/1500 load_never_executed** — BTB
forced taken → fall-through load PC unreached). **NOTE: this does NOT test the AMuLeT InvisiSpec
bug** (spec-read L1D eviction) — that's out of scope (docs/AMULET_VS_SIMSPECT_SCOPE.md). 43/3000
(1.4%) errors = gem5 abort `cache.cc:192 Assertion pkt->hasRespData()` (per-test robustness abort
on certain spec-buffer packets; scheme banner confirms config correct — NOT a config fault; could
bucket/report later, it's a crash not a leak).

**SpecLFB instrumentation assessment** (`/work/amulet/amulet-gem5-SpecLFB_AE-v1.1`, build/X86,
NEWER gem5 base — lsq_unit.cc/iew.cc/dyn_inst.hh, argparse): the hard hooks are ALREADY ported
(BTB-force, branch-resolve-stall applied at iew.cc:1302, branch-ann loader in se.py, --branch-ann-
file/--scheme/--needsTSO). SpecLFB enabled via simulateScheme=="Speclfb" (lsq_unit.cc:228);
isSpeclfbStalled = the load-delay flag; dedicated `Speclfb` debug flag. UV6 (AMuLeT) = first spec
load in LSQ not stalled → installs in cache in-window = **check_ld's exact criterion** (no custom
checker needed). BLOCKERS: (1) scheme glue — --scheme choices=["unsafebaseline","Speclfb"], pipeline's
auto --scheme=2 would fatal; need add "2"+map→"Speclfb" in the NEWER argparse se.py/Options.py (small);
(2) fnc=0 (no hook); (3) **REAL COST ~1-2h: parse_lsq written for OLD base's trace phrasings**; newer
base differs ("Executing load PC %s,[sn]" lsq_unit.cc:609 likely parses, but the packet-sent line —
the leak-distinguishing signal — and squash/spec lines did NOT grep under DPRINTF(LSQUnit), and lsq
component=iew.name()+".lsq"); must capture a real SpecLFB trace and add additive regex variants (like
the expose_tick add) so check_ld's data-obtained gate works. Not done yet — awaiting go-ahead.

## 2026-06-03 — 6:invisispec — AMuLeT bugs are OUT OF SCOPE for SimSpect (different leakage model); see docs/AMULET_VS_SIMSPECT_SCOPE.md

Read the AMuLeT paper (`amulet.pdf`, ASPLOS'25). Key realization: the
`/work/amulet/*_AE-v1.1` builds ARE the AMuLeT artifact packages (InvisiSpec README =
"InvisiSpec-1.0"; AMuLeT added `apply_spec_eviction_patch` toggle). AMuLeT's bugs are all
**collateral shared-µarch-resource** leaks — InvisiSpec **spec-load L1D EVICTION** on a full
set (`MESI_Two_Level-L1cache.sm:514`, toggle default "True"=patched, set False to repro;
L2 `:386`), single-threaded **MSHR-interference** (UV2, needs few MSHRs), **L1I** fetches;
STT tainted-store **TLB**; CleanupSpec missing cleanup; SpecLFB insecure. **Why:** each defense
made "invisible/safe" too narrow (e.g. InvisiSpec = no coherence-state change) while the spec op
still perturbs eviction/MSHR/I-cache/TLB.

**SimSpect CANNOT find these** (2 independent gaps): (1) wrong observation channel — evictions/
MSHR/I-cache/TLB live in the Ruby controllers, invisible to O3PipeView+LSQUnit; (2) wrong
stimulus — bug needs a FULL cache set, but Alloy enumerates taint *dataflow*, not cache
*occupancy* (AMuLeT dropped to 2-way/2-MSHR to amplify). My new `check_ld_invisispec.py`
explicitly ASSUMES Spec-GetS invisibility — the exact thing the eviction bug breaks. SimSpect's
complementary niche = transmitter-in-window **timing races** (VP↔squash class), which AMuLeT's
random search doesn't target. Recommendation: use AMuLeT (you have it) for collateral-cache bugs;
SimSpect for targeted transmitter-window questions. Full writeup: `docs/AMULET_VS_SIMSPECT_SCOPE.md`.
InvisiSpec ld run (expose-in-window checker) is staged at results/STT_6_invisispec/ but NOT launched (paused).

## 2026-06-03 01:20 — 2a:inspectSPT — SPT `no_hold` hits root-caused to MODEL OVER-APPROXIMATION (not pipeline, not gem5); grounded in SPT_6_oneLP.als predicates

Anna pushed back: "no_hold isn't a classification — why did the Fence not hold the transmitter? there's
an error in pipeline or gem5." Investigated against the MODEL's own predicates (read-only) + XML intent
+ gem5 traces. Answer: it is NEITHER a pipeline nor a gem5 error — it is the model's intended
GL-IFT-style over-approximation.

Model (STAGE1_alloy/models/SPT_6_oneLP.als):
- speculation_contract_p (line 337) = uncommitted & has_unresolved_brs  → an inst is "speculative" iff
  it comes AFTER any unresolved branch.
- hardware_protection_policy (line 341) = protect every input addr/reg that is rf-FED by a prior
  instruction's output (propagated along rf/ddi/spo).
- leak (secure_speculation_scheme_p / tag_xm) = a speculative xmit's address operand is in that protset.
=> the model flags a leak whenever a speculative load's address is rf-produced by ANY earlier
instruction, WITHOUT requiring that producer to itself be unsafe/speculative.

Real STT/SPT (gem5) is narrower: taint a value only while its producing LOAD is still squashable (older
unresolved branch), clear at the visibility point. The no_hold hits are exactly the gap:
- case A/C (45): producer load sits BEFORE the unresolved branch (inst-021701: producer pc1, unresolved
  br pc3) → reaches VP → gem5 untaints → Fence correctly doesn't hold. Verified via XML rf + idx
  (idx is REVERSED: Instruction$k → pc(5-k)); xmit=Instruction with isxm.
- case B (19): model routes the address through a TOtherx whose INPUT is unspecified (inst-007654:
  rf Outreg$1[pc1=TOtherx]→xmit inaddr, inreg empty) → concretized to a free-pool prologue-zero reg →
  untainted constant. NOT a clobber/dead-load bug; faithful to the model. Same family as OTB gap.

So test is correctly generated (satisfies the leak predicate) AND gem5 correctly shows no leak (producer
safe). Both halves working as designed; the discrepancy is model conservatism — the reason gem5 is the
ground-truth filter. The genuine signal is the opposite case (producer UNDER the unresolved branch =
the VP-squash race).

CAVEAT logged: the race(4502)/no_hold(64) split is TIMING-based (access before vs after resolve), NOT
taint-based. The 64 no_hold are verified safe-producer; the 4,502 race are NOT yet re-verified to have
genuinely-held tainted producers (some could be pre-branch loads that merely executed late). Next step
if we want the race count trustworthy: apply the producer-taint/position check to the race bucket too.

Deep writeup updated: mdsToRead/SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md (now leads with the model root cause).

## 2026-06-03 02:45 — deepdiveBugCompilation — Standardized Recon_6 + stt_slowcomm_full into the bucket_hits.py convention (so they stop reporting "no diag")

Per Anna, wired both runs into the same auto-discovering `bucket_hits.py` form the SPT runs use (each
cause = a `diag_*.py` exposing `is_known(stem,xml_dir)` + PHASE/CATEGORY/NEEDS_GEM5/ORDER + a bug `.md`;
output = `buckets/<mode>/<cause>.txt` + `summary.json`). Both were "no diag" for *different* reasons:
Recon_6 had only ad-hoc scripts (no `bucket_hits.py`/`buckets/`); `stt_slowcomm_full` had the same gap
**and** a path trap — the real run is under `results/experiments/`, while top-level
`results/stt_slowcomm_full*` are empty stubs and `results/stt_slowcomm_full__latest` points at a stub.

- **Recon_6__20260602_122016** (recon-modded STT, not_taken): `diag_check_ld_no_completion` (disqualifier,
  🟠checker, reads `leak_complete_before_squash.json`, `leak==False`) = **183**; `diag_recon_slf`
  (real_bug, 🔴, double-gated XML-SLF-shape + gem5 `leak==True`) = **1** (`inst-014912`); **NEW=0**.
- **experiments/stt_slowcomm_full__20260602_121858** (STT /work/stt slow-comm, STT_6, both modes):
  `diag_check_ld_not_real_access` (disqualifier, 🟠) = **21** (6+15); `diag_stt_vp_squash_race`
  (real_bug, 🔴 A4) = **19,845** (16,797+3,048); **NEW = 4,122** (3,492+630).
  - The race diag/check_ld-FP diag read the precomputed `race_full_<mode>.json` verdicts (no live gem5);
    added an ADDITIVE `is_known`/metadata block to the existing `diag_stt_vp_squash_race.py` (CLI
    `diagnose_one`/`main` untouched — verified `--help` still works) + a new
    `diag_check_ld_not_real_access.py`. **Did NOT touch 1a:inspectSTT's br_x files** (`brx_*`).
  - **Reconciles with 1a's 00:45 "ld 0 NEW":** 1a bucketed the *cache population* (19,866 = fully
    covered → 0 NEW); `bucket_hits` reads the *current* window-results, which the LIVE sweep has grown to
    23,988, so NEW = exactly the 4,122 hits swept **after** the last `race_full` rerun — **un-rerun, not
    anomalies** (ratios say they're the race). Close the gap by re-running `diag_stt_vp_squash_race` to
    extend the cache, then re-bucket (documented in that folder's README; deferred — box is gem5-loaded).

Convention tweak in both `bucket_hits.py` copies (backward-compatible): REPO is found by walking up to
the dir containing `testsets/` (fixes the `results/experiments/<run>` extra-nesting REPO mis-resolve),
and `SIMSPECT_BUCKET_MODE=<mode>` is exported per mode so gem5-EVIDENCE diags pick the right per-mode
cache (XML diags ignore it). `results/` is gitignored — all artifacts, no source touched. Catalog
cross-ref unchanged: `bug/BUG_TAXONOMY.md` (A2/A4 real, B1 checker FP, B4 OTB-classifier trap).

## 2026-06-03 03:30 — 1a:inspectSTT — CORRECTION (Anna caught it): check_br DOES enforce the lc/fnc window. br_x FPs are from check_br having no taint/secrecy gate + a vacuous branches_unresolved, NOT a "window gap"

**Supersedes the 01:30 entry's mechanism (struck below). Conclusion (br_x = check_br FPs) stands; the
reasoning was wrong twice.** Anna pushed on three points; all correct:
1. **check_br DOES enforce `(lc_retire, fnc_retire)`** (`check_br.py:90-99`: `after_lc`/`before_fnc` are
   ANDed into `issued_in_window`). My "window-gap" claim was a **wrong tick comparison** — I compared the
   redirect to the controlling branch's *squash* tick (~2945500), not `fnc_retire` (3241000 for
   inst-021185; redirect 2984000 < that → genuinely in-window). The CLAUDE.md note that check_br "doesn't
   enforce the lc/fnc window" is **STALE** (pre-fix).
2. **`not_real_access` is a LOAD verdict** = check_ld/diag data-obtained gate False (load executed per the
   "Executing load" tick but obtained no data: delay_unit bounce / spec_read / never_executed → check_ld FP).
3. **A branch can't "leak after its controlling branch closed the window" — and doesn't.** The real
   criterion: a br_x leak needs the xmit to redirect while its condition is **still secret** (controlling
   branch unresolved / feeding load squashable). For all 46, the redirecting xmit instance is fetched
   **after** the controlling mispredict resolved+squashed (inst-021185: xmit sn:609 redirects @2984000,
   fnc sn:557 squashed @2945500, fnc completes/resolves @2930500) → post-VP, **non-secret** → STT
   correctly does NOT make it pending → check_br FP.
**Two actual check_br gaps:** (a) for br_x, `unresolved=[]` ALWAYS (the xmit is the only mispredict and
process_one excludes it) → `branches_unresolved` is **vacuously true**, no constraint; (b) check_br has
**no taint/secrecy gate** (unlike check_ld's data-obtained gate), so it flags any redirect in
`(lc_retire,fnc_retire)` regardless of whether the branch is still a secret-dependent transmitter. STT's
model: load force-taints dest only while **squashable** (`rob_impl.hh:810`); `isArgsTainted=hasExplicitFlow`
(`:809`); taint clears at VP. **Recommended fix:** give check_br a taint-at-redirect gate (branch analog of
data-obtained) + treat vacuous `branches_unresolved` as "no protection." **Real signal in these gadgets is
load-side** (feeding load pre-resolution cache access, e.g. inst-021185 packet @2930000 < resolve @2930500),
not the branch. **Residual:** 100%-certain "no STT taint miss" needs STT's per-inst `ArgsTainted` (debug
build) or instance squashability tracking; if intended taint is *implicit*, results.md Bug 1 could make a
real one. Review md rewritten: `…/diagnostics/BR_X_slowcomm_REVIEW.md`.

## ~~2026-06-03 01:30~~ (SUPERSEDED by 03:30 above) — 1a:inspectSTT — slowcomm br_x mechanism via "lc/fnc-window gap" — WRONG mechanism (check_br does enforce the window); see 03:30

**Closes the OPEN br_x item from the 00:45 entry below.** Confirmed the 63 candidates via register-
dataflow (trace each xmit's condition reg → its producing load) + redirect-vs-resolve timing:
- **231 br_x hits = ALL check_br false positives. No distinct real branch leak.** Breakdown:
  185 = feeding load never forwards (168 not-executed + 17 executed-no-data) → branch reads stale reg;
  **46 = feeding load reaches cache pre-resolution (a real LOAD access), but the xmit branch redirects
  POST-resolution** (`brx_timing.json`: 46/46 `xmit_redirect > fnc_resolve`, 46/46 `feed_packet <
  fnc_resolve`) → scored only because **check_br doesn't enforce the lc/fnc window** (the gap already in
  CLAUDE.md "Leak criteria").
- **Two verdicts:** (1) STT branch defense NOT shown broken here (consistent with corrected
  `project_stt_branch_leak_cause`); (2) **check_br lc/fnc-window gap is real, now with 46 concrete
  instances** — recommend gating the branch redirect on the window + taint-at-redirect (zeroes these 46).
  The 46 feeding loads are a load-channel item (pre-resolution access; not in this run's ld-transmitter
  set), not a branch leak.
- Worked example inst-021185: feedload `0x401c4d` packet @2930000 < fnc resolve @2945500 < xmit
  `0x401c68` redirect @2984000. Deliverables: **`…/diagnostics/BR_X_slowcomm_REVIEW.md`** (Anna review),
  `brx_confirm.py` + `brx_{probe2,confirm,timing}.json`. `brx_triage.md` now a stub → review md.
- **Process note:** also added a CLAUDE.md convention — big bugs / fundamental results get a standalone
  review `.md` for Anna (not just a claudelog line), placed where the result lives.

## 2026-06-03 00:45 — 1a:inspectSTT — Slowcomm STT: ld fully triaged (19,845 known VP-race + 21 FP + 0 NEW); br_x first-pass (SUPERSEDED by 01:30 above: the 63 candidates all resolved to check_br FPs)

Diagnostic pass on `results/experiments/stt_slowcomm_full` (`/work/stt`, `se_slowcomm.py`, scheme 2, no
resolve-stall).

**ld — FULL set (19,866 hits), `diag_stt_vp_squash_race.py` (aligned to check_ld's data-obtained gate,
see 23:35 entry): 19,845 `stt_vp_squash_race` (known real STT load bug) + 21 `not_real_access`
(executed_no_packet, stale pre-22:45-gate check_ld FPs) + 0 NEW / 0 `stt_no_hold`.** Done. No new ld signal.

**br_x — CORRECTION to an earlier-in-session claim.** I first bucketed all 231 br_x hits as check_br FPs
using a WRONG signal ("was *any* branch made-pending?"). Invalid: the made-pending inst is usually an
**unrelated** tainted inst (e.g. a speculative `retq`), not the check_br-flagged xmit branch. Anna flagged
it (STT has no untaint; the question is whether a *speculative load feeds the xmit*). Re-probed with the
right discriminator (`brx_probe2.json`):
- **168/231 `fp_load_not_executed`** — the xmit's feeding litmus load never executes on the realized path
  → xmit reads a **stale architectural reg** → untainted → check_br FP. Verified: the 8 "no-defense"
  stems (load PC absent from trace entirely) + inst-019490 (pc1 `0x401056` not executed; the made-pending
  `0x401065` is an unrelated spec `retq`).
- **63/231 `REAL_CANDIDATE_load_exec_no_pend`** (62 not_taken, 1 taken) — a litmus load EXECUTES and the
  xmit branch (which has an **explicit** data dep on the loaded reg, e.g. inst-020917 xmit `0x401067`
  `je %rcx`←`%rax`←load `0x40104f`) redirects **without** being made-pending. If the load truly tainted
  the branch and STT let the redirect through → **real undefended tainted-branch leak** (the `results.md`
  broken-implicit-channel class).
- **The 63 are NOT confirmed.** "Executing load" is logged before STT's delay decision (same over-count
  as check_ld), so an executed-but-**delay_unit-bounced** load may never forward to the xmit's condition
  reg (stale → still FP). Each of the 63 needs: (1) did the load **forward/complete** before the xmit
  redirected, (2) is the xmit's dynamic source the **speculative** load's output (not a committed
  producer — rf/"shared opstate ≠ rf edge" pitfall). Then cross-check `results.md` (isArgsTainted ignores
  hasImplicitFlow, `rob_impl.hh:809`) and the corrected `project_stt_branch_leak_cause` (which concluded
  "defense works" on only 5 stems — the 63 may be its counterexamples or the load-delayed-stale FP it
  predicts).
- **Verdict: br_x OPEN — do NOT call it 0 leaks.** Writeup + data: `…/diagnostics/brx_triage.md`,
  `brx_probe2.json`. Next: a forward+taint diagnostic over the 63.

## 2026-06-03 — invisispec — InvisiSpec load-xmit criterion ≠ STT/SPT: it's the EXPOSE/VALIDATE packet, not the spec read

Investigated the InvisiSpec defense (paper `InvisiSpec_*.pdf` §V-B / Fig.2) to define its load-leak
criterion for SimSpect testing. Build: `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1` (Ruby
`X86_MESI_Two_Level`, like SPT). **Key difference from STT/SPT: a USL touches memory TWICE.**

1. **Spec read** (`Packet::createReadSpec` → `MemCmd::ReadSpecReq`/Spec-GetS) — issued at addr-resolve
   *while still a USL*, fills only the Speculative Buffer. **INVISIBLE by design** (no cache/coherence/
   replacement change). `check_ld`'s current "Executing load" / first-cache-packet signal lands on THIS
   → pointed at this build it would false-positive on ~every USL. Must be EXCLUDED (`isSpec()` /
   `OnlyAccessSpecBuff`).
2. **Expose/Validate** (`createExpose`/`createValidate`) — the cache-MODIFYING access, the real xmit.

So the InvisiSpec leak criterion = **an expose/validate (non-spec) cache packet for the xmit fires
inside the spec window** (before the shadowing branch resolves for IS-Spectre; before ROB-head/
non-squashable for IS-Future). Correct InvisiSpec never does this — gate is `readyToExpose()`.

Exact pipeline anchors (in build above):
- issue gate (spec vs normal read): `src/cpu/o3/lsq_unit.hh:855` `read()` — `isInvisibleSpec &&
  !readyToExpose()` → `createReadSpec`, else `createRead` (already-safe load = state N).
- **visibility point**: `lsq_unit_impl.hh:1042` `updateVisibleState()` (driven `iew_impl.hh:1535`) sets
  `readyToExpose()`. IS-Spectre gate = `isPrevBrsResolved()` (:1072); IS-Future = `isPrevInstsCompleted()`
  (:1071). `++loadsToVLD` at :1078.
- **load-xmit point**: `lsq_unit_impl.hh:1104` `exposeLoads()` (driven `iew_impl.hh:1195`), gated
  `needPostFetch() && readyToExpose()` (:1161). Packet built :1210 `createExpose` / :1213
  `createValidate`, **SENT to D-cache at :1280 `dcachePort->sendTimingReq(data_pkt)`**, `setExposeSent()`
  :1348. → **:1280 is where to flag; criterion = its tick is inside the spec window.**

Build already carries SimSpect `DPRINTF(Squashed,...)` hooks separating the two accesses:
`"InvisiSpec - Spec Read Request for PC ..."` (lsq_unit.hh) vs `"Validate/Expose: PC %#x, Addr %#x"`
(`lsq_unit_impl.hh:1194,1204`) — stock InvisiSpec uses `LSQUnit` flag, so these are added (see
`/work/amulet/rebuild_InvisiSpec_hooks.log`). An InvisiSpec checker should key `signal` on the
Validate/Expose tick from these, not the spec-read tick. Checker change = pipeline-side (allowed),
NOT a gem5 change. No code touched this session (read-only investigation).

## 2026-06-03 00:30 — 2a:inspectSPT — SPT slowcomm_fence FULLY BUCKETED: every ld hit explained, 0 residual NEW; the only signal is the VP-squash race (slow-comm-only). 64 stt_no_hold all verified harmless

Ran the OFFICIAL build-agnostic `diag_stt_vp_squash_race.py` (copied into
`results/experiments/spt_slowcomm_fence__20260602_121858/diagnostics/` + SPT companion
`stt_vp_squash_race.md`) on the 4,571 NEW survivors (ld hits minus constaddr+rf):
  stt_vp_squash_race 4,502 | stt_no_hold 64 | not_real_access 5.

Then GROUND-TRUTH-verified the 64 stt_no_hold (the diag conservatively leaves these NEW). Did NOT
trust asm structure — ran gem5 and traced the LEAKING xmit instance's actual data source:
  - 40: address-producer load RETIRED (correct path) → architectural addr → harmless.
  - 19: xmit index reg is an architectural CONSTANT (prologue zero-init reg, e.g. `movq %r15,%rax`
        with %r15=0; or `leaq (%r8,%r10)` both 0) → no load dependency → harmless (const-addr-like).
  - 5: dual-instance src load — v2 heuristic FALSE-FLAGGED these as CANDIDATE_BUG by matching the
        latest *squashed* xmit (which never executed) to a squashed src. v3 matched the actually-
        EXECUTED leaking xmit instance → it consumed a RETIRED (correct-path) src → harmless.
        (inst-040343/041681/042209/042221/042242; src load pc1 is BEFORE the mispredict.)
  → ALL 64 harmless. 0 candidate bugs. (no_hold_resolution.json in the diag folder.)

PITFALL logged: across a mispredict, a PC executes on BOTH wrong (squashed) and correct (retired)
paths → multiple dynamic instances per PC. Dataflow attribution MUST follow the executed/data-obtained
instance, not max-seqNum or "is the PC ever squashed." (cf OTB_GENERATION_GAP dataflow pitfalls.)

**COMPLETE accounting, slowcomm_fence ld hits (~53k):** constaddr_load ~38.7k (harmless const addr) +
rf_clobber ~5k (model artifact) + stt_vp_squash_race 4,502 (THE signal) + stt_no_hold 64 (harmless:
correct-path/constant addr) + not_real_access 5 (check_ld FP). **0 unexplained NEW.** br_x hits (~154)
are a SEPARATE track (check_br), not covered here. The only real-ish signal = the VP-squash race, which
is SLOW-COMM-ONLY (0/230 at stock, claudelog 23:55) — same verdict/class as the STT race.

## 2026-06-03 00:20 — figureoutwhynocoinc — CORRECTION to my 23:58 entry: the coincidence bug is a SINGLE *mispredicted resolve* vs its own squash-propagation race (= the known STT VP-squash race), NOT a "need ≥2 unresolved branches" generative gap

Anna pushed back: "wouldn't it not be more unresolved but rather a mispredicted resolve." She's right.
Read the STT untaint source to ground it.

**Mechanism (verified, `/work/stt/src/cpu/o3/rob_impl.hh`):** `updateVisibleState()` (commit, every
cycle, before `compute_taint()`) marks an inst `isUnsquashable(true)` — taint clears — when
`isPrevBrsResolved()`. A branch stops blocking untaint when **`readyToCommit() && !isSquashed()`**
(rob_impl.hh:491-493). A mispredicting branch becomes `readyToCommit` AT its resolve cycle, but its
squash takes extra cycle(s) to walk the ROB / cross the `commitToIEWDelay` timebuffer and mark the
younger transmitter `isSquashed`. In that gap: transmitter sees prevBrsResolved=true → untainted →
issues its cache access → THEN squash arrives. **Defense lifts protection at branch *resolution*; the
resolution is a misprediction whose squash hasn't propagated yet.** Needs ONE mispredicted branch that
RESOLVES — not two, not a held-open one. This IS the VP↔squash race (claudelog 23:30/23:55 SPT,
designconsultant STT slow-comm), just viewed as "untaint and squash hitting the same dependent in
overlapping cycles."

**Why Run B (`results/experiments/stt_coincidence/`) still gets 0:**
1. It HOLDS the mispredict unresolved (`s_U∈{50,100,250,500}`/legacy 5000) to keep the window open →
   the branch never hits readyToCommit-but-not-squashed *while the transmitter is live*. Large s_U =
   never resolves in window; small s_U = resolves early, squashes xmit BEFORE it executes. The Goldilocks
   tick (resolve ≈ xmit execute) is per-test and the discrete s_U grid rarely lands on it.
2. Even when aligned, Run B uses **stock se.py** (commitToIEWDelay=1) → squash removes the xmit same/next
   cycle → untaint loses. Reproduces only at commitToIEWDelay≥2-3 (slow-comm), which Run B never sets. Run
   B sweeps STALL cycles but never the PIPELINE DELAY that opens the race.

**My 23:58 "need ≥2 unresolved branches" was WRONG for this bug** — that conflated it with
`sweep_design_notes.md` §2 (two redirects colliding in the timebuffer / squash-priority), a DIFFERENT
class. The resolve-vs-squash race needs no .als change. **Right levers:** (1) sweep s_U so the mispredict
RESOLVES in a band around the xmit's execute tick (not held open); (2) widen resolve→squash slack via the
commitToIEWDelay/squashWidth se.py bridge (`sweep_design_notes.md` §3). Memory `project_coincidence_gap`
updated. Cross-ref `project_spt_onelp_zeroinit_untaint`, `project_slow_comm_experiment`.

## 2026-06-02 23:58 — figureoutwhynocoinc — [SUPERSEDED by 2026-06-03 00:20 — see correction above] Why the resolution-COINCIDENCE sweep (Run B) generates 0 hits: it's a GENERATIVE gap (one unresolved branch per test), not a sweep-tuning problem

Anna asked why the small-value coincidence sweep (`results/experiments/stt_coincidence/{STT_6,STT_6_interleave}`,
dense `s_R=[0,1,2,4,8,16,32,64,128,256]` × small `s_U=[50,100,250,500]`, max_grid=24, /work/stt scheme 2)
never reproduces the known STT same-cycle squash-coincidence bug. Read-only investigation; touched nothing.

**Verdict — the bug shape is structurally absent from the corpus:**
1. **Every test has exactly ONE unresolved (mispredicting) branch.** Scanned 5,000 STT_6 anns:
   unresolved-count = {1: 5000} (always 1); resolved-count = {0:2085,1:2317,2:543,3:55}. The only branch
   that ever *squashes/redirects* per test is that single mispredict. The "resolved" branches the sweep
   varies are all `correctly_not_taken` → predicted right, fall through, **never issue a redirect** — they
   move timing only, not control flow.
2. **The known STT coincidence bug needs TWO redirects colliding** (squash priority between two in-flight
   redirects / two redirects in the same `commitToIEWDelay` timebuffer slot — `sweep_design_notes.md` §2).
   With one unresolved branch there is only ever one squash in flight; aligning a *correctly-predicted*
   branch's resolution onto the same cycle creates no second redirect to collide.
3. **Even the timing target is measure-zero with these knobs.** Coincidence needs
   `complete_R + s_R == complete_U + s_U` (checker `gem5_common.py:529` `prop_tick=complete+stall*tpc`).
   We control `s_R`/`s_U` but NOT `complete_R`/`complete_U` (per-test, 500 ticks/cyc). A few discrete
   `(s_R,s_U)` combos (max_grid=24) almost never cancels the arbitrary per-test gap. Dense points give
   statistical *near*-coincidence, not same-cycle (design note §1 already said this); the only mechanism
   that would *design* collisions (§1(d) coincidence-aligned band, `s_R` swept around `s_U`) was never run.

**Blocker is generative, not in the sweep.** Harness is ready (`check_branch_resolutions` already loops a
LIST of unresolved branches). The constraint is the Alloy model emitting exactly one. To generate the bug
intuitively you need **≥2 independent unresolved mispredicting branches per test** (an `.als` change — OWNER
GATE, deferred to Anna). Cross-ref `sweep_design_notes.md` §2 / step (e) and `project_branch_xmit_rework`.

## 2026-06-02 23:40 — deepdiveBugCompilation — Synthesized ALL bugs into a by-LAYER taxonomy + per-run attribution graphs (read-only; no code/model/run touched)

Consolidated every bug/finding across the project into two new durable artifacts next to Anna's
`bug/BUGS.md` (which is by-*build*):
- **`bug/BUG_TAXONOMY.md`** — same findings organized by **root-cause LAYER** (TARGET / CHECKER / ALLOY /
  PIPELINE), the "is this a real target bug or is my model/checker/codegen lying?" drill-down. Leads with
  the triage frame (a hit = gem5-permits-what-model-forbids → 5 possible causes across 4 layers,
  disqualifier-before-real-bug ordering), then A1–A6 (targets), B1–B4 (checkers), C1–C4 (alloy),
  D1–D7 (pipeline/config), a summary matrix, and a per-layer big-picture. IDs cross-ref BUGS.md +
  `mdsToRead/` + `claudelog`.
- **`bug/graphs/`** (`make_graphs.py`, reproducible) — per-(testset × implementation) **hit-attribution**
  charts colored by category + a coverage matrix + a findings-by-layer bar. Numbers verified from disk
  (`results/<run>/diagnostics/buckets/`, `window-results.json`) cross-checked vs claudelog.

Key cross-checks done this pass (all consistent with prior entries): Recon_6__20260602_122016
`leak_complete_before_squash.json` = **1 real leak (inst-014912 SLF) + 183 check_ld FP** of 184 ld hits.
SPT_6_oneLP_fence buckets = constaddr 6040 + rf_clobber 56 + NEW 22 (15 alloy + 7 checker), 0 real.
spt_slowcomm_fence = constaddr 38,726 + rf_clobber 4,962 + NEW 4,532 + **postmispred_producer 983**
(= A5 VP-squash candidate, attribution OPEN). STT_6_sttbuild = 0 hits (defense holds). STT_6@recon
partial = 253 ld FP. **Note for future sessions:** `results/STT_all_amulet` currently shows 9,215
not_taken hits (NOT the all-error state AUDIT #1 described) but it is a **pre-`check_br`-fix (B2),
un-typed** run → those hits are NOT attributable (mix of B2 FP + possible A3 real branch leaks); left
grey/"open" in the graph; re-run with fixed checkers + kind split before trusting (ties to AUDIT #20).
No checker/model/pipeline/run was modified — pure documentation.

## 2026-06-02 23:35 — 1a:inspectSTT — Slowcomm STT diag started: 400/400 sampled ld hits = known VP-squash race; aligned the diag to check_ld's data-obtained gate (complete caveat)

Started the diagnostic pass on the live full-corpus slow-comm STT campaign
`results/experiments/stt_slowcomm_full` (`/work/stt`, **`se_slowcomm.py`**, scheme 2, sweep disabled).
Current hits: ld 16,706 (not_taken) + 2,941 (taken), br_x 198 + 33.
- **Sampled 200 ld hits/mode (seed 42) through `diag_stt_vp_squash_race.py` (faithful: run's own config)
  → 400/400 = `stt_vp_squash_race`. 0 NEW, 0 `stt_no_hold`, 0 FP.** The slow-comm STT ld leaks are
  fully explained by the already-root-caused STT visibility-point↔squash-drain race (real gem5 STT bug;
  `results/experiments/slow_comm_squash1/diagnostics/stt_vp_squash_race.md`). No new signal in the sample.
  Outputs: `results/experiments/stt_slowcomm_full__latest/diagnostics/race_<mode>.json`.
- **⚠️ Aligned `diag_stt_vp_squash_race.py` to check_ld's data-obtained gate (the statusBar 22:45 change).**
  It previously gated condition (1) on `diag_ld_cache_reach.classify_trace`'s `real_access`, which is
  **trace-only** and True for `reached_cache` **only** — so it MISSED `store_forward` (SLF: executed,
  no packet, reached pipeview `complete`), the exact "complete caveat" check_ld now counts as a leak.
  Rewrote `diagnose_one` to compute `data_obtained` with check_ld's own `_xmit_cache_fate` + pipeview
  `complete` (reused via `import check_ld`), and to use the **data-obtained tick** for the race timing
  (cache packet for `reached_cache`, completion tick for `store_forward`). Effect on this sample: the
  one not_taken hit that was `not_real_access` under the old packet-only rule was an `executed_no_packet`
  that DID complete → a real SLF access → now correctly `stt_vp_squash_race`. Net 199→200.
- **Doc:** added the canonical data-obtained gate (store_forward/complete caveat, cache-reach-is-not-the-
  bar, squash-never-gates) to `CLAUDE.md` "Leak criteria" §, plus the standing rule that **every
  diagnostic re-deciding real-leak-vs-FP MUST reuse `check_ld._xmit_cache_fate` + pipeview `complete`,
  not `classify_trace.real_access`** (which misses SLF). Future diagnostics: copy the
  `diag_stt_vp_squash_race` pattern.
- **Still open:** br_x slow-comm hits (198+33) not yet bucketed; ld diag was a 200/mode sample, not the
  full ~19.6k (campaign still live, growing). Scale up / add br_x bucketing next.
- **NB** cross-check with the 23:55 entry below: that race is **slow-comm-only** (0 at stock se.py); these
  400 hits are all under `se_slowcomm.py`, consistent.

## 2026-06-02 23:55 — 2a:inspectSPT — VP-squash race is SLOW-COMM-ONLY: 0/230 tainted-addr gadgets race at stock se.py (deep stock-vs-slowcomm verify)

Anna asked for a STOCK example of the race. There ISN'T one for these gadgets. Cache-reach at stock
(se.py + fnc150, the SPT_6_oneLP_fence config) on 230 tainted-address post-mispredict-producer stems:
**0/230 reached cache — ALL never_executed** (transmitter squashed before it can execute).

Deep verify, same stem inst-000005, load 401c58 sn:570, stock vs slowcomm:
- STOCK: mispredict resolves @2949000 → pc2 squashed in LSQ @2949500 (+1 cyc). pc2 NEVER executes /
  no packet. Fence HOLDS.
- SLOW-COMM: mispredict resolves @2945500 → pc2 released+executes+packet @2946500 (+1 cyc) → squash
  reaches LSQ @2947500 (+2 cyc). Packet slips the 2-cyc gap → leak.

Race window = commit→LSQ squash-propagation latency. Stock=1 cyc (too narrow; load squashed before it
can issue), slow-comm (commitToIEWDelay=4)=2 cyc (wide enough). So the VP-squash race is MANUFACTURED
by the slow-comm regime, NOT a property of stock SPT — matches designconsultant's STT result (stock
does not leak; commitToIEWDelay≥2-3 drives it).

Reconciles 18:50's "60-53% at stock": that sampled the FULL hit set (80% const-addr / pre-branch
class-1, whose address is legitimately untainted → reaches cache at stock with NO fence and NO race =
harmless over-approx). 18:50 conflated class-1 (harmless, leaks at stock) with class-2 (the race,
slow-comm-only). They are different: class-1 address untainted; class-2 address tainted+fenced+raced.

**Refined verdict:** stock SPT Fence HOLDS on the tainted-address race gadgets. The "Fence leaks
pre-squash" signal splits into (1) harmless untainted-address over-approx (stock+slowcomm) and (2) the
VP-squash race (slow-comm-only timing artifact, commitToIEWDelay≥2-3). Neither is a stock-gem5 Fence
bug. Whether the slow-comm race counts as a "real bug" = whether a CPU with multi-cycle commit→squash
latency is in scope (same open question as the STT race).

## 2026-06-02 23:30 — 2a:inspectSPT — CORRECTION: SPT "Fence leaks pre-squash" is the VP↔squash race, NOT memory untaint (my 22:40 entry was WRONG)

My 22:40 conclusion ("zero-init prologue untaints all shadowL1 → testset realizability gap") is
WRONG. Anna pushed back (everything routes through mem, that can't be the SPT contract). Verified by
running gem5-spt with --trackInstsFile + reading rob_impl.hh/lsq_unit_impl.hh:

- **shadowL1 is OFF** in these runs (boot prints `Shadow L1 enabled? no`; enableShadowL1 unset). The
  taint-through-memory code is dead. The `movq $0` prologue is irrelevant to taint.
- **Taint source = rob_impl.hh:240, speculation-INDEPENDENT:** every load taints its dest
  unconditionally ("Access instructions always taint their destination, regardless of speculative").
- Fence gate = lsq_unit_impl.hh:1180 `fenceDelay = isAddrTainted()`. Untaint at the visibility point
  (isUnsquashable → untaintMemTransmit).

**Real mechanism for the 983 post-mispredict-producer survivors (the genuine signal):** shape pc0 =
mispredict branch (no committed predecessor) → pc1 = speculative load → pc2 = xmit. pc1 taints rax;
pc2 address tainted → pc2 GENUINELY FENCED. Verified inst-000005 (slowcomm): rax ready @2932500, pc2
held until @2946500 (28 cyc past data-ready — not a data dependency). @2945500 mispredict resolves →
pc2 reaches VP → fence lifts → pc2 sends cache packet @2946500 → squash drains to LSQ @2947500.
**Packet beats squash by ~2 cycles = visibility-point↔squash race** (defense lifts the fence at branch
*resolution*, before the squash propagates; wrong-path transmitter touches cache in the gap). Same
class as the STT VP-squash race (designconsultant, claudelog slow_comm). Slow-comm (commitToIEWDelay=4)
WIDENS the gap; at stock inst-000005 is squashed in time, but other stems still race at stock (18:50:
60-53%). The OTHER ~3.5k survivors are pre-branch-producer (address from a non-speculative load that
reaches VP immediately → untainted → correctly not fenced) = harmless over-approx.

**Verdict:** NOT memory untaint, NOT a realizability gap. The 983 = VP-squash race; real-bug-vs-hook
attribution OPEN, routed to the STT-race root-cause track. Tooling note unchanged (bucket_hits REPO
heuristic needs explicit --xml-dir for results/experiments/<run>).

## 2026-06-02 23:10 — 1a:inspectSTT — /work/stt STT runs: 0 leaks everywhere; the 348 "error" rows are an incomplete-sweep artifact, NOT a bug

Ran the per-results diag on the two **/work/stt** build runs (`/work/stt/build/X86/gem5.opt`,
scheme 2): `results/STT_6_sttbuild__20260602_013615`, `results/STT_6_interleave_sttbuild__20260602_013615`.
- **0 leaks** across **every** kind/mode: STT_6 ld 11,652 + br_x 4,348 (×2 modes) all `ok`; interleave
  ld/br_x all `ok` too. STT defense holds on these testsets — nothing to root-cause as a security signal.
  (Distinct from the **recon-modded** STT runs `__015852`, which DO have ld hits — those are the
  load→load check_ld false positives already covered in the 430-line entry / `project_stt_load_leak_cause`.)
- Only anomaly: **348 `error` rows in `STT_6_interleave_sttbuild` mispredict_taken/ld** (0 elsewhere).
  Root cause = **incomplete sweep grid, not a leak/gem5/STT bug.** `pipeline._aggregate_sweep_results`
  marks a stem `error` when its row is missing from ≥1 of its `sweep_grid_size` (=3) grid points. All 348
  stems (`inst-003885..~004000_vN`) are present+`ok` in grid pts 0 and 1 but absent from grid pt 2: the
  re-sweep (raw timestamp `20260602092334`) wrote `grid0000/0001/0002_batch0008` ld outputs but the
  grid-pt-2 second-chunk ld file `grid0002_batch0009` **was never written** — that check_ld invocation
  hung/was-killed mid-batch (~09:18–09:21); from `grid0003` on the run emitted only tiny ~3.5 KB near-empty
  check_br files and wound down at 09:23. Consistent with the known gem5 runaway/livelock-under-heavier-
  -stall risk (`project_pipeview_space_blowup`, commitToIEWDelay≥5 livelock note).
- **Verdict:** sweep-completeness artifact (🟡pipeline/harness). The two completed grid pts score all 348
  clean `ok`; grid pt 2 (a *different* stall config) is simply unrun, so "no hidden leak" is only
  *confirmable* by re-running grid pt 2 for those 348 stems (idempotent — would flip them `ok`/reveal a
  hit). Not done yet (extra gem5 run; box already has live sweeps).

## 2026-06-02 23:05 — reconHitDiag — Created repo-root `bug/` cross-build bug catalog + first verified example

New `bug/` folder at repo root: `BUGS.md` = cross-build catalog (every build + pipeline; each entry
has signature / verdict 🔴real-gem5 🟠checker 🟡pipeline 🔵model ⚪config / provenance / status). First
representative example folder shipped: `bug/recon_SLF_stlf_bypass/` (`inst-014912`) = the confirmed
recon STT **SLF / store-to-load-forwarding taint bypass** — full provenance.json, NOTE.md, asm/ann/xml,
and the gem5 trace excerpt (ready-in-ROB @2682500 < squash @2683500, no cache packet). Only that one
of the 184 Recon_6 ld hits is a real leak. Catalog clearly marks what I verified this session
(recon SLF, recon "OTB" non-realization, check_ld over-count, diag repro bug) vs. what's
cross-referenced from other sessions' claudelog/diagnostics (STT race, SPT zero-init, dup-PC, rf
last-writer, OTB gap, pipeview blowup) — those need a faithful stall-injected rerun before treated as
settled. Add new examples as `bug/<bug_id>/` with a provenance.json + NOTE.md.
- **(23:15) Added 2nd example:** `bug/stt_slowcomm_vp_squash_race/` (`inst-047231`) — the STT
  visibility-point↔squash race (designconsultant's slow_comm_squash1 finding), self-contained:
  provenance.json + BUG_EXPLAINER.md + example_inst-047231.md + diag + asm/ann/xml. Copied from the
  experiment dir, not independently re-verified this session.

## 2026-06-02 22:45 — statusBar — check_ld FIX: secondary "data-obtained" gate folded inline (cache-packet OR store-forward completion); global load-leak definition tightened
**What changed (CHECKER FIX, affects every load sweep going forward):**
- `gem5_common.py:parse_lsq` now also captures `packet_tick` ("successfully sent out
  packet(s)", lsq_unit.hh:1056) and `spec_read_tick` ("send a spec read", :897) per load.
  Both are under the **LSQUnit** debug flag, which check_ld already enables → **no extra gem5
  run, no extra debug flag**; the data was already in the trace.
- `check_ld.py` ANDs a secondary **data-obtained** gate on top of the existing
  `lc<signal<fnc` window + branches-unresolved verdict (can only DOWNGRADE a windowed hit,
  never promote). A load is a leak iff it OBTAINED its data:
    - `reached_cache` (real packet to cache), OR
    - `store_forward`/SLF (executed, **no packet**, but reached pipeview `complete` — value
      forwarded from a store in the LSQ).
  Dropped as false positives: delay_unit bounce (executed, no packet, never completed),
  invisible `spec_read_only`, never_executed.
  **Cache reach is NOT the bar** — SLF leaks without touching cache. This CORRECTS the 20:25
  reconHitDiag conclusion "0/122 reach cache → all false positives": an SLF load completes
  without a packet and IS a real leak under the completion bar; the 122 need re-classifying by
  complete-before-squash (reconHitDiag in progress).
  **Squash timing NEVER gates** (squashed load that obtained data still leaked); recorded as
  `load_squash_tick` for info only. Gate applies only to LSQ-path hits (`xmit_execute>0`) with
  LSQ records present; else left ungated (builds w/o LSQUnit logging) so no real leak is hidden.
- New output fields: `in_window`, `data_obtained`, `cache_fate`, `real_access`, `packet_tick`,
  `spec_read_tick`, `load_squash_tick`.
- `diag_ld_cache_reach.py` bug fixed: removed `speculative_real = packet-before-squash` gating
  that printed post-squash real accesses as "window over-count" (WRONG per squash rule). Now
  `real_access`=True for any `reached_cache` regardless of squash (squash → `packet_before_squash`,
  info only). Documents that its trace-only `executed_no_packet` bucket may be SLF (real leak) →
  must cross-check completion, which the checker now does inline.

**Implication:** load hit counts DROP on the next run to genuine data-obtained cases (real
cache touch + SLF). Re-run/triage any load campaign whose counts span this change. Owner (Anna)
approved folding into the checker as a secondary gate.

## 2026-06-02 22:40 — 2a:inspectSPT — SPT diag pipeline (oneLP_fence + slowcomm_fence): 0 real leaks; root-caused the slow-comm "real pre-squash cache access" open case to zero-init-prologue shadowL1 untaint (testset realizability gap, NOT a Fence/DDIFT bug)

Ran both recent SPT runs through bucket_hits.py + diag_ld_cache_reach.py (per Anna's scope: oneLP_fence Jun2 + experiments/spt_slowcomm_fence live).

**SPT_6_oneLP_fence__20260602_013615** (6118 ld hits): constaddr_load 6040, rf_clobber 56, NEW 22.
Cache-test on the 22 NEW: 7 = check_ld false positives (executed_no_packet); 15 = reached_cache
SPECULATIVE. All 15 = xmit load address index (%rax) fed by a load at pc0/pc1 BEFORE the first
branch -> no older unresolved branch -> value commits, reads a fixed zero-init stack slot -> SPT
correctly untaints -> harmless (constant address). **0 real leaks.**

**experiments/spt_slowcomm_fence__20260602_121858** (48,220 ld hits, slow-comm Fence + DDIFT):
constaddr_load 38,726, rf_clobber 4,962, NEW 4,532. Of the 4,532: 3,549 are the same pre-branch
safe-addr over-approx; **983 are a genuinely speculative Spectre-v1 shape** (pc0 = mispredicting
branch with NO committed predecessor -> pc1 = speculative load under that mispredict -> pc2 = xmit
load transmitting pc1's result). Sampled 80/983 through cache-reach: **80/80 send a REAL cache
packet BEFORE squash** = the "Fence leaks pre-squash" open case from 18:50.

**ROOT CAUSE (resolves the 18:50 OPEN item; NOT a Fence/DDIFT bug):** gate is
lsq_unit_impl.hh:1180 `fenceDelay = isAddrTainted()`. Packets went out => pc2 address (rax from the
speculative pc1) was UNTAINTED. DDIFT taint is DATA-based via shadowL1, not speculation-based: a load
result is tainted only if its loaded shadow-L1 address is tainted (lsq_unit_impl.hh:206/1335
`newTaint = shadowL1[a] && ...`). The litmus prologue zero-inits the whole frame with
`movq $0, N(%rsp)` = UNTAINTED-constant stores -> shadowL1[stack]=untainted. pc1 reads a zero-init
slot -> untainted result -> pc2 never fenced. Verified ALL 983 residual gadgets contain ONLY
`movq $0` stores, ZERO register/value stores (no taint source). So no secret can reach any
transmitter: the cache access is real but carries a non-secret (constant) address.

**Verdict:** testset/concretization REALIZABILITY GAP (same family as const-addr / rf-lastwriter
artifacts), NOT a real gem5 bug and NOT model over-flagging per se. SPT_6_oneLP under the DDIFT Fence
build CANNOT exhibit a real leak — the zero-init prologue poisons shadowL1 to untainted before any
gadget load. To get a real DDIFT leak the testset must establish a live taint source (a store of a
speculatively-loaded/secret value WITHOUT untaint, or a load from never-stored memory that stays
shadowL1-tainted). Mirrors the documented STLF-untaint finding (project_spt_load_diagnosis).

Artifacts: installed bucket pipeline into slowcomm_fence/diagnostics (NOTE: bucket_hits.py REPO
heuristic mis-resolves for results/experiments/<run> — one extra nesting level; pass
--xml-dir <repo>/testsets/SPT_6_oneLP/xml explicitly). Bucket lists +
buckets/<mode>/postmispred_producer.txt written. No pipeline/gem5/model edits.

## What belongs here (write it as you discover it)

- **Bugs** found (concretization, parsexml/Stage-2 codegen, gem5 hooks, model expressivity) — with verdict (real gem5 bug vs. pipeline artifact) once known.
- **Changes** that affect other sessions or future runs (fixes to `parsexml.py`, hooks, configs, scripts).
- **Big-picture fixes / decisions** about pipeline structure or methodology.
- **Reasons a sweep had to be restarted / relaunched** (e.g. mid-run contamination, stale `.ll`, `--force` needed) and *which models/stages* are affected.
- **Cross-stage gotchas** newly discovered (candidates for promotion into `DESIGN.md` / `AUDIT.md`).

## What does NOT belong here

- Minute-by-minute "I'm running X now" status → `claudenotes.md`.
- Findings already captured in `DESIGN.md`, `AUDIT.md`, `results.md`, `reconresults.md`, or git history. Cross-reference instead of duplicating.

## Format

Newest at top. Every entry **dated** and signed with the session label you use in `claudenotes.md`:

```
## YYYY-MM-DD HH:MM — <session-label> — <one-line title>
<a few lines: what it is, evidence/where, verdict, and what action it implies (relaunch? report to user? promote to AUDIT?)>
```

Keep entries self-contained — point to the file/log/line that proves it so the next session can re-verify.

---

## 2026-06-02 19:22 — reconHitDiag — Diagnosed live Recon_6 hits via diag_recon_load_hits.py; first SLF/OTB recon hits appear; old Recon_6 set is STALE

Live recon campaign = `results/Recon_6__20260602_122016` (testrun, gem5-recon-modded, scheme=2 STT +
`allow_leaked`, mode mispredict_not_taken). Swept so far: ld 11,261 (122 leak, 0 err), br_x 14,239
(0 leak, 0 err). Ran the build-specific `diag_recon_load_hits.py` (SLF/OTB classifier) on the 122 ld
hits → **SLF=1 (inst-014912), OTB=3 (inst-004271/4272/4273), load_load=118**. Buckets + README +
script copied into `results/Recon_6__20260602_122016/diagnostics/`.
- **VERDICT (20:40) — 1 REAL SLF LEAK + 183 check_ld FPs (of 184 ld hits).** The correct leak test
  is **"load COMPLETES (marks ready in ROB) before its squash while tainted+spec"**, NOT "sends a
  cache packet" (Anna's catch: these hits were gated on *complete*, not cache-reach). A
  store-forwarded / cache-hit load leaks by completing without a fresh packet, so my first
  cache-PACKET rerun (`cache_reach.json`, 0/122 reached cache) was the WRONG bar and MISSED the real
  leak. `leak_complete_before_squash.json` (faithful: stalls injected, widest window) classifies on
  the LSQ/Commit trace (`Executing load`→`STL_CHECK isTainted/isSpec`→`Marking … ready within ROB`
  vs `Load … squashed`):
  - **REAL: `inst-014912` (SLF)** — tainted spec load `ready within ROB` @2682500 BEFORE squash
    @2683500 → store-to-load forwarding returns data before the STT taint check (recon SLF bug).
  - **183 FP** (incl. the 3 "OTB" `inst-004271/2/3` + all load_load) — load executes (check_ld scores
    it) but is bounced to delay_unit and **squashed without ever marking ready** (e.g. `inst-000257`:
    exec @2681500, squash @2683500, no ready/writeback). No completion → no leak.
  - The 3 "OTB" are NOT real OTB: pc3 spec load overwrites `%rax`, pc1 `idivq` output dead → xmit
    addr fed by a single spec load, not a committed+spec merge ("shared opstate ≠ rf edge" — the
    classifier matched abstract opstate, not a real rf edge).
- **check_ld over-counts**: scores at "Executing load" (request dispatch); a bounced+squashed load
  never leaked. Remedy = check_ld fix (completion/ready-aware). `inst-014912` = representative recon
  SLF leak for the bug folder.
- ⚠️ **diag_ld_cache_reach.py FIXED (faithful-repro bug):** it was rerunning gem5 with the RAW ann,
  omitting the sweep's `unresolved_stall_cycles=5000` (the stall is injected into the annotation by
  `pipeline._inject_stalls`, NOT an env var, so `_apply_config_env` missed it) → window collapsed,
  rerun was invalid. Now `_apply_config_env` forwards `sweep.*` (as `SIMSPECT_SWEEP_CFG`) and
  `diagnose_one` rebuilds the grid + injects stalls per grid point, OR-ing real_access. Grid sizes
  1/3/9 now match the campaign's `sweep_grid_size`. Both the pre-fix and post-fix runs gave 0/122,
  but only the post-fix one is trustworthy. **Any prior cache-reach rerun that didn't inject sweep
  stalls is suspect — re-run with the fixed diag.**
- ⚠️ **`results/Recon_6/results/` (the non-timestamped set, 1120 hits) is STALE May-15**
  (window-results mtime 2026-05-15, pre-RS testset / pre-branch-fix, 37,227/100k errors). Do NOT
  treat its 861-SLF count as current — it's a different/old testset+config. Removed the diag output
  I briefly wrote there to avoid confusion.

## 2026-06-02 18:50 — runManager — Run A (SPT FENCE CONTROL) cache-reach diag: Fence shows REAL speculative cache accesses at BOTH slow-comm AND stock timing — control "fails", root cause OPEN (handed to hit-inspector)

**Result (EXPERIMENTS.md §6 control check on Run A = SPT_6_oneLP Fence, `diag_ld_cache_reach.py`).**
Sampled 500 in-window ld hits/mode from the live campaign
(`results/experiments/spt_slowcomm_fence__latest`); staged `.s`+bare `.ann.json` from
`testsets/SPT_6_oneLP/<mode>/{asm,ann}`:

| regime | not_taken real-cache | taken real-cache |
|---|---|---|
| **slow-comm** (se_slowcomm.py, commitToIEWDelay=4) | **466/500 (93%)** | **477/500 (95%)** |
| **stock** (se.py, no prop delay, same stems) | **298/500 (60%)** | **266/500 (53%)** |

ALL real accesses are **pre-squash speculative** (0 post-squash over-count). So these are NOT
check_ld false positives — they are genuine speculative cache touches on FENCE.

**Key isolation:** the leak is present at **stock timing too** — the slow-comm prop delay only
*inflates* it (the stock `never_executed` 171/214 become executed-before-squash once the window is
widened). ⇒ this is **NOT** "slow-comm breaks Fence." Two live hypotheses, NOT yet resolved:
  1. **Known model over-approximation (most likely):** const-addr / untainted-address loads — the
     model marks them protected but their address is untainted, so Fence *correctly* lets them touch
     cache (not a real leak). A diagnostic already exists for exactly this testset+build:
     `results/SPT_6_oneLP_fence__20260602_013615/diagnostics/diag_constaddr_load.py`
     (analysis-claude 02:40 bucketed 2795 known / 3 unknown). **Apply it to these hit stems.**
  2. **Harness/config (less likely but must rule out):** Fence (`--scheme=SpectreSafeFence` +
     `--applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy`) not actually engaged for
     these tests. Verify the flags reach gem5 (config.ini) on a sample.

**Data on disk:** `/tmp/A_cachereach/{mispredict_not_taken,mispredict_taken}/`
{`cache_reach.json` (slow-comm), `cache_reach_stock.json` (stock se.py), `_hits.json` (the 500 stems),
staged `.s`/`.ann.json`}. **Stock-fence cfg:** `/tmp/A_cachereach/stock_fence_cfg.jsonc`.
**HANDOFF:** root-causing these hits (const-addr bucket vs real) is going to the hit-inspecting Claude;
runManager stopped here. Until resolved, **Run A control is UNSETTLED → do not yet trust B/D as
"Fence-anchored."** (D's own slow-comm hits were separately validated as addr-from-load/tainted, but
the cross-defense Fence anchor is pending this.)

## 2026-06-02 12:34 — runManager — Launched 4 coincidence/slow-comm sweeps; PIPELINE sweep extension (gated); new gem5-spt se_slowcomm.py; recon deprioritized+queued

**Pipeline change (affects every sweep — but backward-compatible/gated).** `pipeline.py`
`_grid_points` + `_inject_stalls` gained two OPTIONAL `sweep.*` keys; when absent, behavior is
byte-identical to before (unit-tested), so running sweeps are unaffected:
- `sweep.unresolved_points: [..]` — sweep the *unresolved* branch stall `s_U` too (folded into each
  grid point under reserved key `"__unresolved__"`, honored by `_inject_stalls`; scalar
  `unresolved_stall_cycles` is the fallback). Lets ONE campaign vary `s_U` instead of one fixed value.
- `sweep.max_grid: N` — randomly (seeded, per-stem) sub-sample the grid to N points. Needed because
  dense `points` across several resolved branches is `len(points)**n_resolved * len(unresolved_points)`
  → explodes. Threaded at BOTH call sites (`_enumerate_grid_for_corpus` corpus path used by testrun.py,
  and the `phase_asm_gem5_streaming` path). This is sweep_design_notes.md §1d (coincidence band) + §4c
  (sampling), with Anna's explicit go-ahead.

**New build config (additive, sanctioned config-glue — se.py untouched).**
`/work/gem5-spt/configs/example/se_slowcomm.py` = faithful port of the STT slow-comm block
(iewToCommitDelay=30, commitToIEWDelay=4, back/forwardComSize=40, squashWidth=1). **Smoke-tested:
gem5-spt does NOT livelock at commitToIEWDelay=4** (STT capped at 4; gem5-spt ceiling now ≥4 verified
on 2 ld tests, exit 0). Hardcoded (not env-gated) so it always applies.

**4 priority sweeps running (testrun.py watchers, type-sorted results):**
- **A — SPT Fence slow-comm = EXPERIMENTS.md Fence CONTROL** (expect 0 *real-cache* leaks). Full
  SPT_6_oneLP corpus, gem5-spt `--scheme=SpectreSafeFence`, se_slowcomm.py, bare resolution sweep,
  fnc150. `results/experiments/spt_slowcomm_fence/`. NOTE: check_ld flags `in_window` hits on Fence —
  must run `diag_ld_cache_reach.py` to separate REAL cache access from fence-suppressed before calling
  anything a leak.
- **D — FULL-corpus STT slow-comm** (the 186/42 finding was only ever a 600-test run_sample.py SAMPLE;
  this runs the whole STT_6 corpus). /work/stt, se_slowcomm.py. `results/experiments/stt_slowcomm_full/`.
- **B — STT resolution-coincidence** (STT_6 + STT_6_interleave, /work/stt se.py): dense short `s_R`
  points × SMALL `s_U` (`unresolved_points [50,100,250,500]`, `max_grid 24`). Smaller `s_U` narrows
  the spec window (fewer plain in-window hits) — intended SECOND profile per §1, NOT a default change.
  `results/experiments/stt_coincidence/{STT_6,STT_6_interleave}/`.

**Recon DEPRIORITIZED + QUEUED (Anna's call).** Recon = scheme 2 STT + `--allow_leaked`
(`results/Recon_6/run_config.jsonc` already encodes this; "recon on" = allow_leaked, NOT
address_prediction). Old `testsets/Recon_6` is a stale May *flat-layout* testset (complete but
pre-current-pipeline); regenerating into modern mode-split layout (xml+llvm present → asm only). Regen
killed at 30,391/100k asm (resumable). `queue_recon_behind.sh` (nohup pid 3563103) waits for 1-min
load <35 (x2) then resumes the asm regen + watcher at nice 19 — i.e. behind A/B/D.

**Testset note:** STT_6_interleave taken asm is now COMPLETE (400k) — the dead generator was restarted
and finished. STT_6_full remains unusable (taken asm 0/100k — not restarted, per Anna).

## 2026-06-02 — reconbugs — STT_6 / STT_6_interleave TESTSETS ARE STALE (pre-effective-RS): only 2 leak dataflows, 40% no-op padding — REGEN from current model gives 45 dataflows
**Affects every session sweeping these testsets.** The XML in `testsets/STT_6/xml` and
`testsets/STT_6_interleave/xml` was generated **2026-05-19 02:44** from a model state where the
`gen_useful_litmus` clause **`all s: State | secure_speculation_scheme_p[RS->s]`** ("every state must be
necessary") was NOT active; the current committed `STT_6.als` (mtime 04:47) HAS it. Proven by toggling it:
generate from current model → **0% isolated** ops; comment out just the RS line (`/tmp/noRS.als`) →
**38% isolated** ops return. So RS is the mechanism that forbids isolated no-op `other` ops.
Consequences, measured fresh-from-current-model (2000 inst) vs the stale testset (2000):
- redundancy (inst ÷ distinct struct): **8.6× stale → 1.4× fresh**
- distinct leak **dataflows** (typed rf-edge shapes): **2 stale → 45 fresh** (!!) — the stale corpus
  exercises only `load→xmit.inaddr` and `load→branchx.inreg`; the isolated others add nodes but **no rf
  edges**, so 100k stale tests cover just 2 leak topologies.
- isolated no-op `other` outputs: **40% stale → 0% fresh**.
**Action:** regenerate the STT testsets from the current model (wipe xml→ on; this is a from-XML relaunch).
The stale tests aren't *wrong* (they satisfy the old contract) but they are massively redundant and cover
only 2 of ~45 leak dataflows — the STT sweeps are under-covering. NOT regenerated/​touched by me (running
sweeps + cross-session coordination = user call). The gem5-behavior findings on these tests (check_ld FP,
slow-comm VP-squash race, SPT buckets) remain valid for the specific tests run.

## 2026-06-02 — reconbugs — CORRECTION to the OTB entries: the bloat analysis was on the STALE testset; "WIN1" is redundant with the existing RS clause
My earlier "require interaction (WIN1)" proposal and the 9.1× bloat / 40%-isolated numbers were computed on
the **stale** testset (above). On the **current** model the user's `RS` clause already yields 1.4× /
0-isolated / 45-dataflows — so **WIN1 is unnecessary** (it re-derives what `RS` enforces). Do NOT add it.
The OTB-precursor conclusion is UNCHANGED and re-confirmed on fresh current-model output: `other→xmit.inaddr`
rf edge = **0/2000 fresh** (was 0/100k stale), and forcing `otb_shape` is SAT (that test used the current
model). So `mdsToRead/OTB_GENERATION_GAP.md` stands: OTB legal but absent from the default enumeration,
needs the forcing predicate; just note its rf-scan numbers were on the stale testset and re-confirmed fresh.

## 2026-06-02 10:15 — designconsultant — NO zero-stretch PoC: window depth is NOT a lever; commitToIEWDelay is the sole knob (corrects 09:30/09:55 "deep window" speculation)
Tested whether a DEEP speculative window reproduces the STT vp/squash leak at STOCK timing (the
real-world-relevance question): hand-modified inst-047231 by inserting N filler insts after the xmit
(younger, wrong-path; ann stays valid since xmit/branch/lc/fnc PCs don't move). Result at stock
(commitToIEWDelay=1, squashWidth=8, fnc off): **N=0/96/300 → NO leak (xmit never executes)**; leak only
returns at commitToIEWDelay≥3 regardless of depth. (NOP fillers = depth neutral; dependent-addq fillers
even SUPPRESS via exec contention.) **Mechanism:** on a mispredict the IQ squashes ALL younger-than-branch
insts in ONE shot when the squash signal arrives — NOT drained at squashWidth/cycle (squashWidth bounds
only ROB commit-side retirement). So wrong-path depth / squashWidth cannot widen the resolution→squash
gap; only the commit→IEW squash-signal latency (commitToIEWDelay) can. **→ No pure-stock PoC exists on
this gem5 O3.** Minimal PoC = stock + commitToIEWDelay=3 (realistic squashWidth=8) — a single
arguably-realistic param. **Corrects** the earlier writeup caveat that "deep window + finite squashWidth"
could realize it (DISPROVEN for THIS gem5); fixed in stt_vp_squash_race.md, inst-047231.md.
**Realism (refined):** gem5's IQ/LSQ flush is ONE-SHOT/unbounded (idealization) — only the ROB unwind is
squashWidth-bounded. So the race window in gem5 = commitToIEWDelay (redirect latency). On real silicon
the window is plausibly LARGER via TWO routes gem5 under-models: (a) multi-cycle resolution→squash-effective
redirect latency (gem5 default=1 is optimistic), and (b) BOUNDED squash bandwidth (real HW can't flush
unbounded LSQ entries/cycle → deep wrong-path loads linger). So the bug is plausibly MORE realizable on
real HW than gem5 shows; the deep-window intuition is right for real HW but un-demonstrable in this gem5
(would need a bounded LSQ/IQ-squash model = gem5 change, out of scope). Core point: it's a DESIGN flaw
(STT un-taints at isPrevBrsResolved without excluding to-be-squashed insts); timing only sets window size.

## 2026-06-02 09:30 — designconsultant — ROOT CAUSE rigorously isolated: STT visibility-point↔squash race; driver = commitToIEWDelay (NOT squashWidth); does NOT leak at stock; fnc-hook & check_ld FP & model-over-approx all ruled out. Bug writeup + diagnostic shipped.
Sharpens/corrects the 08:30 + 08:55 entries below. **Bug:** a wrong-path tainted load→load xmit's taint
clears at the visibility point (`isPrevBrsResolved` → `isUnsquashable` → dest-taint dropped; rob_impl.hh
compute_taint 812-814 + updateVisibleState 519-520), the load re-issues, and accesses cache in the gap
**before the squash drains it**. STT never enforces squash-before-expose. IQ smoking gun (inst-047231):
operands ready+issued @2.9315M, held ~29cyc, RE-issued @2.946M right after branch resolves @2.9455M,
packet @2.9465M, squashed @2.9475M.
**Rigorous isolation (inst-047231, fnc-hook OFF, robust sn-aware leak check):**
- **stock (commitToIEWDelay=1, squashWidth=8): NO leak.** Reconciles the STT_6_sttbuild baseline 0-hits
  (which ALSO had unresolved_stall=5000 masking) AND the stock-config bare sample (B): **0/1200 hits.**
- **Driver = `commitToIEWDelay`** (backward commit→IEW wire carrying the squash). Threshold ≈2–3:
  bwd2/fwd1=no, bwd3/fwd1=LEAK, bwd2/fwd2=LEAK, bwd4/fwd4/**sw8**=LEAK.
- **squashWidth is NOT the driver** (sw1+stock-comm = no leak; sw8 leaks when comm stretched).
- **forward `iewToCommitDelay` alone does NOT cause it** (bwd1/fwd30 = no leak).
- **fnc-commit-stall hook RULED OUT** — leak identical with fnc=150 and fnc=0 across 5 stems.
- **Not a check_ld FP** (cache-reach=reached_cache), **not model over-approx** (XML 231/231 addr_from_load),
  **not concretization**, **not the BTB-force hook** (that just realizes the modeled mispredict).
- **Heterogeneous threshold:** inst-000230 leaks at modest bwd4/fwd4/sw8; inst-001204/000816/001133/000366
  need the full slow-comm gap (sw1+fwd30+bwd4). All leak under full slow-comm; none at stock.
- **EARLIER ERROR (retracted):** a shell-grep bug (empty xmit sn → matched another load's packet) made me
  briefly think it "leaks at stock." It does NOT. Use the sn-aware check (diagnostic below).
**Verdict:** REAL STT defense weakness (timing-parameter-dependent), NOT present at gem5 default O3 timing
(commitToIEWDelay=1, squashWidth=8) — needs the commit→IEW redirect gap ≥~2-3 cyc and/or deep/slow squash
drain. Real-world exploitability = open (plausible in deep pipelines; unproven here as gadgets are shallow
≤6 insts). I read gem5 source only; no gem5 edits.
**Artifacts:** `results/experiments/slow_comm_squash1/diagnostics/{stt_vp_squash_race.md, diag_stt_vp_squash_race.py}`
(one-cause bucketing diagnostic; conservative: only buckets reached_cache + squashed + packet≥branch-resolve;
access-before-resolve → `stt_no_hold` left NEW). Validated: not_taken sample → **186/187 stt_vp_squash_race**,
1 check_ld FP, 0 unexplained.

## 2026-06-02 — 6:spaceAudit — FIX: bounded/orphan-proof gem5 launch — stops the disk-full crashes
**Root cause of the recurring "container fills, can't even connect" crashes:**
`STAGE3_gem5/gem5_common.py:run_gem5` ran gem5 via `subprocess.run(check=True, capture_output=True)`
with **no timeout and no tick cap**. A run that livelocks (see commitToIEWDelay>=5 in the slow-comm
notes) or just runs unbounded keeps appending to its single `--debug-file=pipeview.txt`
(`O3PipeView,LSQUnit,Commit`) → **65–127 GB per run**; ~10 in parallel fill the 1.8 TB volume.
Worse, when a sweep/session is killed the gem5 children **reparent to PID 1 and keep writing to the
already-unlinked pipeview.txt**, so `rm` frees nothing and `df` stays at 100% until the PIDs are
killed (`ls -la /proc/*/fd | grep 'pipeview.txt (deleted)'`). NOTE: the pipeline already retains
**zero** pipeviews (process_one rmtrees every workdir; keep_tmp=false everywhere) — the blowup was
the *live in-flight* trace, not saved artifacts.
**Fix (harness only — inside the hook/pipeline boundary, gem5 source untouched):** new
`_run_bounded()` runs gem5 with (1) a **120 s wall-clock timeout** (`SIMSPECT_GEM5_TIMEOUT_S`;
litmus runs finish in <1 s, so a timeout == runaway → killed, surfaced as `status="error"`, never a
hit), (2) **`start_new_session` + process-group SIGKILL on timeout** and a **`PR_SET_PDEATHSIG`
preexec** so a killed launcher can't orphan a disk-filling gem5, and (3) a generous
`--abs-max-tick=1e11` cap (`SIMSPECT_GEM5_MAX_TICK`; all builds incl. amulet's se.py accept it) as
defense-in-depth. Normal/nonzero-exit semantics preserved (still raises `CalledProcessError` with
bytes out/err). Verified: timeout fires + group-kill leaves no strays; normal & error exits intact.
Defaults are baked into gem5_common so **every** checker invocation (pipeline, watchers, manual)
gets it for free — no run_config change needed. Memory: project_pipeview_space_blowup.

## 2026-06-02 — reconbugs — CORRECTION: OTB precursor IS generatable — it's a `max_instances` cap artifact, NOT minimality/expressivity
**Supersedes the verdict in the entry directly below** (which wrongly said OTB "can't be generated" /
"minimality forbids the free operand"). User pushed back correctly: `gen_useful_litmus` minimizes only via
`RR` (resolve branch) + `RS` (remove state) — **never `RI`/`RO`** — so extra `other` ops and *unspecified
operands are NOT pruned*. Tested directly: copied STT_6.als → `/tmp/otb_test.als`, added
`pred otb_shape { some x: Loads | (x in xm) and (some o:(Otherns+Otherxs) | some (o.outreg & rf.(x.inaddr))) }`
as a conjunct of the first `run`, ran `a6CountModels` → **SAT, instances immediately**
(`/tmp/otb_test_out/`). Representative `inst-000002`: `br(committed) ld(committed) br(UNRESOLVED) ld(spec)
TOtherx(1 rf-bound inreg, fed by a load) ld-XMIT(inaddr←other.outreg)` — i.e. the exact `… ld other xm`
gadget, with the `other`'s 2nd operand left **unspecified** (the slot interleave/pass3 fills).
**So the real reason the testset has 0 OTB:** the default `gen_lit` enumeration fills the
`alloy.max_instances=100000` cap with the simpler direct-`load→xmit` and `branchx` shapes **before reaching
any `other`-on-path instance** — an enumeration-order + cap artifact, NOT a model limit. **Fix:** enumerate
a dedicated OTB testset with the forcing predicate + `interleave.enabled` so `pass_interleave` adds the 2nd
load under an earlier-resolving branch (owner approval for the `.als`/config change). Doc
`mdsToRead/OTB_GENERATION_GAP.md` + CLAUDE.md caveat **rewritten** with the corrected root cause and a new
pitfall: *never infer "model can't" from "absent in the capped enumeration" — force the shape & run Alloy.*

## 2026-06-02 — reconbugs — DEFINITIVE: OTB precursor `ld→other→xm` is NEVER generated (0/100k, rf-level) → full doc written
Closes the OTB-generation question (two entries below have the right verdict but cited a buggy asm scan;
**trust this rf-level result instead**). Scanned **all 100,000** base STT_6_interleave XML by true `rf`
edges (`/tmp/rf_shape.py`): **66,512/66,512 `ld` transmitters have their address fed by an `rf` edge
DIRECTLY from a load; 0 route it through an `other`/ALU op.** (33,488 are branchx xmits;
`leakage_function` line 315 has `Otherxs.inreg` commented out → **no `other_x` transmitters** exist either.)
So the OTB gadget (`br_r [inj-ld] br_u ld other xm`, user's spec) cannot be assembled: there is no
combiner-with-a-fillable-operand on the transmitter's address path for interleave's injected load to hook.
**Model-level root cause:** the leak is satisfied by the *direct* speculative-load→`xm.inaddr` rf edge, and
`gen_useful_litmus`'s `all s:State | secure[RS->s]` state-minimality forbids the non-essential free operand
the gadget needs (and forbids/avoids the longer `ld→other→xm` chain). To exercise OTB = model change (owner
approval) or run the hand-crafted `oldest_taint_bug/...inst-oldest-taint-bug.s` on recon-modded.
**Wrote `mdsToRead/OTB_GENERATION_GAP.md`** (full root cause + the analysis pitfalls that gave wrong answers
twice: base XML is pre-interleave; shared opstate≠rf edge; `$N` atom suffix; idx reversed; x86 SIB
comma-split + `lea`-is-not-a-load) and **linked it from CLAUDE.md** (the Chain-interleaving note now points
there with a "read before re-investigating" warning).

## 2026-06-02 09:00 — analysis-claude (inspectHitsSPT) — all 34 undiagnosed SPT_6_oneLP_fence ld hits bucketed: NONE real leaks (15 STLF check_ld-FP + 19 safe-load over-approx)
Bucketed every undiagnosed (non-const-addr) ld hit in results/SPT_6_oneLP_fence__20260602_013615 (both modes),
XML shape + gem5 cache-reach (SPT build, sweep stall applied). 34 total:
- **15 STLF, no cache packet** → check_ld FALSE POSITIVE (xmit store-forwards, no cache line).
- **19 reached_cache** (real cache packet, NOT fenced) — but XML: **19/19 have the address-producing load
  BEFORE every branch** → SAFE load (no unresolved branch precedes it) → architectural/const address →
  **Alloy over-approximation** (model treats *uncommitted* as secret; should treat *under-an-unresolved-
  branch* as secret). Same root cause as the const-addr artifact, just load-sourced not ALU-sourced.
**Answer to "is load-output unprotection real?":** SPT leaves these untainted, but CORRECTLY — the producing
load is safe. A load's output starts tainted only UNDER a misprediction; these are pre-branch. So it's the
MODEL over-flagging, not SPT mis-unprotecting. **CONTRAST** the STT slow-comm case (designconsultant 08:30):
there the producing load is AFTER the mispredict (speculative) → real leak. SPT_6_oneLP model puts the
taint-source load before all branches → 0/19 real. So SPT_6_oneLP exercises NO real load leaks.
**Corrected** the earlier md claim that LL cases are "a real taint source gem5 untaints" — they're safe-load
over-approximation. Model fix (mdsToRead/POTENTIAL_MODEL_FIX_constaddr_taint.md §6) now covers both shapes;
the precise speculative-source test = "address chain reaches a load spo-AFTER an unresolved branch."
Still PENDING per claudenotes: optionally encode the safe-load bucket into diag_constaddr_load (refine
"uncommitted"→"under unresolved branch"); not done (conservative, awaiting call).

## 2026-06-02 08:30 — designconsultant — slow-comm ld hits are REAL LEAKS (231/231 model-protected load→load; 228/231 real cache access); squash tick is NOT a disqualifier
Diagnosed the bare slow-comm ld hits (results/experiments/slow_comm_squash1/sample/, 600 ld/mode):
- **XML shape (model-level):** `xml_shape.py` over all 231 hits → **231/231 `addr_from_load`** — every
  xmit load's address is fed (via `rf`) by a speculative `TLoad` output sitting after the unresolved
  mispredict branch. So ALL are **model-correct load→load** leak shapes STT must protect; **0** are the
  SPT-style const-addr/ALU-on-constants over-approximation. (My earlier "likely over-approx" guess was
  WRONG — refuted by the XML. The const *value* rax=0 is just the zeroed-stack harness, not a model gap;
  STT has NO STLF-untaint, that's SPT.)
- **Cache-reach (gem5-level):** `diag_ld_cache_reach.py` → **228/231 `reached_cache`** (186/187 not_taken,
  42/44 taken); 3 `executed_no_packet` check_ld FPs. So ~98.7% of hits are tainted speculative loads STT
  let send a REAL cache packet. **These are real STT discrepancies** (the research signal).
- **SEMANTICS (user, important):** the branch squash/resolution tick is **NOT an eliminating factor** for
  load transmitters. inst-047231: mispredict branch 0x401c51 broadcasts Commit squash @2,945,500, xmit
  packet @2,946,500 (LSQ squash @2,947,500). I initially called the post-broadcast access "not a leak" —
  WRONG: a mis-speculated tainted load that touched the cache then got squashed **is** the leak. Squash
  tick is informative only. Codified in memory `feedback_squash_not_eliminating`. → I did **NOT** build the
  squash-based window-elimination in the checkers (the user stubbed that); checkers left as-is.
- **ROOT CAUSE (CONFIRMED 08:55, see hits/inst-047231.md):** STT *does* taint+hold these loads while
  speculative; it RELEASES them at the visibility point the instant the controlling branch resolves, and
  the wrong-path load then hits the cache before the squash drains it. Smoking gun (IQ trace, sn:571):
  operands all ready + first issued @2,931,500 (data NOT the bottleneck), held ~29 cyc, RE-issued @2,946,000
  right after branch 0x401c51 resolves @2,945,500 → cache packet @2,946,500 → squashed @2,947,500.
  Mechanism: `rob_impl.hh:compute_taint()` roots load taint in `isAccess() && !isUnsquashable()`;
  `updateVisibleState()` sets `isUnsquashable ⟺ isPrevBrsResolved()` (all older branches resolved). At
  branch resolution `isPrevBrsResolved` propagates to the YOUNGER wrong-path insts → producer becomes
  unsquashable → dest-taint drops → xmit untainted → readyToExpose → re-issues to cache. But the wrong-path
  load is supposed to be SQUASHED at that resolution; the squash isn't instantaneous. **STT's
  visibility-point treats "prev branches resolved" as "safe to expose" without accounting for the inst being
  on the to-be-squashed path** — its security implicitly assumes squash completes atomically with the
  taint-clear. slow-comm (squashWidth=1 + stretched IEW↔commit delays) widens that gap from ~0 to several
  cycles, exposing it. General to all 228 hits; plausibly realizable on realistic configs with finite
  squashWidth + deep speculative window. **This is the research signal: a real STT visibility-point/squash
  race, not a model over-approx and not a check_ld FP.** (I read gem5 source only — no gem5 edits.)
- Artifacts: `results/experiments/slow_comm_squash1/{xml_shape.py, run_sample.py, sample/*/cache_reach.json,
  hits/inst-047231.md}`; `STAGE3_gem5/diag_ld_cache_reach.py` (path-bug fixed: resolve .s/.ann to abs).

## 2026-06-02 07:30 — designconsultant — slow-comm flips appear at NATURAL timing; resolve-stall sweep SUPPRESSES them; bare ld hit rate ~31%/7% (real cache access)
Two findings on results/experiments/slow_comm_squash1/ (/work/stt, se_slowcomm.py fwd30/bwd4/sq1, scheme2):

1. **METHODOLOGY: the resolve-stall sweep suppresses slow-comm hits — run BARE.** With the inherited
   `sweep` (unresolved_stall_cycles=5000), inst-047231 → MISS: the 5000-cyc branch-resolve-stall pushes
   the xmit load's execution to tick 5.45e6, PAST fnc_retire=3.02e6 (out of the (lc,fnc) window). On the
   bare ann (natural branch timing) it HITS (signal 2.95e6, in window). So unresolved_stall and the
   slow-comm CPU timing are *opposed* window levers for this gadget. **Both run_configs set
   `sweep.enabled:false`** now (→ bare gem5 phase; BTB-force still on via branch_ann_enable, no stall).
   The first 2 watchers (which used unresolved=5000) were measuring the wrong regime; STOPPED, their
   orphaned `pipeline.py gem5 --force`/check_br children killed, and results archived under
   `<model>/_WRONG_REGIME_unresolved5000_*`.

2. **RESULT (bare sample, 600 ld/mode, `run_sample.py --unresolved-stall 0`):** not_taken 187/600 hits
   (**31%**), 186 real cache access + 1 check_ld FP; taken 44/600 (**7%**), 42 real + 2 FP. Baseline
   (default O3 timing, results/STT_6_sttbuild__latest) = 0 hits. So slow-comm timing causes a real
   in-window speculative *cache access* in ~⅓ of not_taken ld tests — diagnostic-confirmed ~99% real
   (not the check_ld delay/bounce FP). **OPEN (separate, deeper):** real cache access ≠ real secret leak
   — many likely have constant addresses (zeroed stack → offset reg = 0), i.e. model over-approximation
   (cf inst-047231 writeup + SPT const-addr 02:40). Next triage: classify hits by whether the xmit
   address is secret-dependent vs constant. Sample driver: results/experiments/slow_comm_squash1/run_sample.py
   (now has `--unresolved-stall`). Full-corpus watchers NOT relaunched yet (box CPU-saturated; sample suffices).

## 2026-06-02 — reconbugs — ROOT CAUSE: why interleave doesn't build the OTB merge (+ correction: first asm scan had SIB/lea parser bugs)
Follow-up to the entry below (user asked *why* interleave fails to generate OTB). **Correction first:** my
initial `/tmp/otb_asm_scan.py` had two asm-parser bugs — (1) it split operands on every `,` so the SIB
operand `(%rsi,%rax)` was truncated to `(%rsi`, tracing only the **base** register; (2) when fixed, it
then counted `leaq 64(%rsp),%r` as a "load" (lea computes an address, it does **not** dereference). With a
correct parser (top-level comma split + `lea` excluded), the conclusion **re-confirms ≤1 load** but for
the right reason: across ~9.1k interleave xmit-load variants, **9086 have exactly 1 real load feeding the
xmit address, 76 have 0, and 0 have ≥2.**
**Root cause (why the mechanism can't fire):** the OTB gadget needs `xmit.index ← O(2-input ALU) ←
{load_A, load_B}`, and interleave is meant to make an injected load collide into O's *blank* operand. But:
- **The transmitter's address operand is fed DIRECTLY by a single load** in ~99% of generated tests —
  the leak condition (`xmit address is a speculative value`) is satisfied by a direct load→xmit `rf`
  edge, so the model never inserts a 2-input combiner ALU on the address path. In the asm, the xmit
  index's last writer is a `movq` load; only **34/9000 (0.4%)** have it produced by a real ALU `O`, and
  those are degenerate (`notq` 1-input, or `imul` whose 2nd operand is undefined/constant) — never a 2nd
  load. (The XML "≈33% addr-via-TOther" is a red herring: the same abstract state `Reg_s$0` is written by
  *both* a TOther and a load, but the load is the last writer → wins at concretization.)
- **No blank slot on the address path to hook.** With no 2-input ALU feeding the xmit index, there's no
  free operand for an injected chain to collide into. Worse, the xmit's address operand and its single
  load producer are `rf`-**specified** → assigned via `locked_reg_map` (deterministic), *not* sampled from
  `free_pool`, which is the only place interleave's `fr_reg_map` collisions can land.
- So interleave's collisions DO happen, but only on (a) the injected chains' own intra-chain operands
  (whose terminal is never the annotated xmit) and (b) base instructions' unspecified operands that are
  off the address path. None reach the transmitter address → 0 OTB.
**Implication:** to realize OTB, the generator/model must be changed so a 2-input ALU with a *fillable*
operand sits on the transmitter's address chain (so an injected load can hook it) — an `.als`/parsexml
change → user approval. Re-confirms the verdict in the entry below; that entry's "13k, 0 merges" stands,
but its evidence script was buggy — trust this corrected scan instead.

## 2026-06-02 — reconbugs — OTB (getOldestTaint) shape is NOT exercised by any STT_6 / STT_6_interleave test (interleave doesn't reach the xmit address)
Question: does the STT interleave testset contain a test that triggers the recon OTB bug (Bug 1,
`getOldestTaint` — an ALU op merging TWO tainted loads of differing speculation status, result feeding
the xmit load address)? **No.** Evidence:
- `old_scripts/scan_otb_shape.py` over all **100,000** STT_6_interleave base XML: **0** exact-chain matches.
- `categorize_hits` LL signature: 0/15k. Structural core (any TOther whose reg inputs are fed by ≥2
  distinct loads): **0/15k** — the model never merges two loads in one ALU at the *abstract* level.
- Base XML is *pre*-interleave, so I also scanned the concrete `_v<k>` variant **asm** dataflow
  (`/tmp/otb_asm_scan.py`): across **13,267** variants (both modes), the xmit address traces to **≤1
  load in 100%** of cases (n_loads_feeding_addr=1: 13210, =0: 57); **0 ALU-merge-of-2-loads feed the
  xmit address** (10,919 reach the address via an ALU, but that ALU's value is a single load).
- **Verdict:** OTB is a **model/interleave-expressivity gap**, not a sweep-coverage gap (contrast SLF,
  which is just unswept). Chain interleaving (`pass_interleave`, free-pool `fr_reg_map` collisions — now
  documented in CLAUDE.md) is *designed* to manufacture the two-chain merge, but the collision does not
  in practice land on the transmitter's address operand, so the OTB gadget is never built. To exercise
  OTB today: re-run the hand-crafted `oldest_taint_bug/debug_out/inst-oldest-taint-bug.s` on
  recon-modded, or extend the model/interleave so an injected load can hook the xmit-address ALU (any
  `.als`/generator change → user approval). reconresults.md Bug 1 was demonstrated hand-crafted, never
  from generator output — consistent with this.

## 2026-06-02 05:30 — designconsultant — shared check_ld cache-reach diagnostic + first slow-comm hit (inst-047231) VERIFIED real cache access
Built `STAGE3_gem5/diag_ld_cache_reach.py` — the shared remedy for the check_ld false-positive
(reconbugs entry below). check_ld keys on the LSQ "Executing load" tick, emitted BEFORE the defense
decides to expose the access, so hits can be non-accesses. The diagnostic re-runs gem5 identically
(reuses gem5_common; env from `--config run_config.jsonc`; `--hits-from window-results.json`) and
classifies the xmit load's TRUE cache fate from the LSQUnit trace: `reached_cache` (real — "successfully
sent out packet(s)"), `spec_read_only` (InvisibleSpec spec buffer), `executed_no_packet` (recon/DoM
delay_unit bounce = FP), `never_executed` (held-then-squashed = FP). **Per-user methodology: trace
classification is a reusable diagnostic, applied across EVERY check_ld consumer — not inline.** This is
the cross-cutting counterpart to per-results `diagnostics/`; promote-to-shared because it's a checker
artifact, not defense-specific.

**inst-047231** (STT_6/not_taken/ld) — first slow-comm hit, full writeup
`results/experiments/slow_comm_squash1/hits/inst-047231.md`. Baseline squashes the spec load before it
executes (signal=0); slow-comm (fwd30/sq1) lets it **send a real cache packet at 2946500, in-window
(2907000<·<3037500), then squash 2 cyc later.** Diagnostic = `reached_cache` → **NOT the check_ld FP**;
genuine speculative cache access STT did not prevent. BUT it ran as a "normal"/untainted load and its
addr = 64(%rsp)+rax with rax=0 (zeroed stack) → effectively constant → **most likely model
over-approximation** (cf SPT const-addr, 02:40 entry), not a real secret leak. Why STT left it untainted
(STLF from committed zero-stores vs real taint gap) unconfirmed — needs an STT taint-trace flag. Note the
cache-reach diagnostic answers "real access vs FP"; "real leak vs over-approx" (constant addr) is a
separate deeper triage on top.

## 2026-06-02 — reconbugs — recon-modded STT_6 ld "hits" so far = check_ld FALSE POSITIVES (STT works), NOT SLF/OTB
Diagnostic on the recon-modded STT sweeps (`results/STT_6__20260602_015852`,
`results/STT_6_interleave__20260602_015852`; both `/work/gem5-recon-modded` scheme 2). ld hits so far:
253/665 (STT_6 not_taken/taken), 49/179 (interleave). **Counts are partial — only the first ~10k of
100k stems swept** (incremental watchers, still running).
- **NOT the recon SLF (STLF) bug and NOT the recon OTB (getOldestTaint) bug.** 0 of the hit XMLs contain
  a TStore (SLF needs store-forwarding) and 0 match the getOldestTaint two-load-merge shape. The reason
  there's no SLF signal yet: **the store-shaped tests haven't been run** — of the ~10k ld tests swept,
  only **2 contain any store / 1 is SLF-shaped** (0 hit). The testset has ~1.9% SLF-shaped tests
  (~1900/100k); they sit in higher stem numbers still in the compile/sweep queue. So SLF is untested,
  not absent.
- **100% of current ld hits are load→load:** xmit load's address = output reg of a prior speculative
  load (no store, no ALU taint-merge). Verdict after gem5 repro (LSQUnit+DelayUnit, scheme 2, 5000-cyc
  resolve-stall on the mispredict branch): **check_ld false positive.** For the xmit load (e.g.
  inst-000070 sn:602, PC 0x401c77): `Executing load` @2681500 → `STL_CHECK isTainted=1` → `Doing memory
  access` → **`Inserted tainted load into delay_unit`** → squashed. STT bounces the tainted load into the
  delay_unit at `lsq_unit.cc:2104` and `return NoFault` **before** `sendPacketToCache()` (`:2140`) — **no
  cache access happens**. check_ld keys on the `Executing load` tick (`lsq_unit.cc:725`, emitted at the
  TOP of `executeLoad`, *before* `initiateAcc()`→`read()`'s STT delay), so a delayed-then-squashed load
  is mis-scored as a leak. Confirmed general: inst-000070/000092/000112 (not_taken) + 000062/000065
  (taken) all isTainted=1 → delay_unit bounce; all have xmit_complete=0 & xmit_retire=0.
- **This is the exact analog of the check_br false-positive** (keyed on too-early a tick; see memory
  `project_stt_branch_leak_cause` / check_br squash-tick fix). **Remedy is a check_ld fix** (treat a load
  as leaking only if it actually reaches the cache — disqualify loads bounced into delay_unit / never
  sent to cache), NOT a gem5 change. **Pending user decision** (fix check_ld like check_br vs. add a
  per-results diagnostic bucket); no checker edited yet. Diagnostics folders created with an XML-only
  SLF/OTB signature classifier (`diag_recon_load_hits.py`) but NO blind known/unknown buckets written
  (load→load is now-explained, not a triaged bug type until the check_ld remedy lands).

## 2026-06-02 04:30 — designconsultant — gem5 O3 livelocks at commitToIEWDelay ≥ 5 (generic, NOT STT / NOT a hook)
Setting up the "slow-comm" experiment (stretch IEW↔commit comms + squashWidth=1 on /work/stt to
widen the observable speculative window). **First config (iewToCommitDelay=commitToIEWDelay=15,
back/forwardComSize=25, squashWidth=1) does NOT terminate** — gem5 livelocks in commit (ROB stuck
"Trying to commit"; a single test ran to tick 3.05e9 vs ~3.0e6 baseline and produced a 2.5 GB
pipeview before I killed it). Bisected on testsets/STT_6/.../inst-047231 with `--abs-max-tick=5e7`:

- **`commitToIEWDelay` (backward wire, commit→IEW) is the culprit.** Livelocks at **≥5**; **≤4 is OK**.
- `iewToCommitDelay` (forward wire) is fine up to at least **30**. `squashWidth=1` alone is fine.
- Livelock reproduces with **scheme=0 (Unsafe, STT off)** AND with **fnc-commit-stall=0** → it is a
  **base-model timing-config limit of this gem5 O3 fork** (backward redirect round-trip doesn't
  converge), NOT the STT defense and NOT one of our SimSpect hooks.

**Verdict:** out of scope (not a hook, not a speculative leak, scheme-independent). Do **not** chase
as a research signal and do **not** "fix" gem5. Just respect the ceiling. Max terminating stretch
verified (all exit ~3.1e6): `iewToCommitDelay=30, commitToIEWDelay=4, backComSize=forwardComSize=40,
squashWidth=1` (also fwd15/bwd4/sq1). Stretching forward delay + squashWidth=1 barely changes total
runtime, so runs stay ~1–2 s.

**State / action:** Experiment LAUNCHED — 2 NEW `_sweep_watcher.py` (STT_6 pid 3945425,
STT_6_interleave pid 3945426) sweeping into results/experiments/slow_comm_squash1/ with the safe
config. Smoke (4 tests) terminated in ~1 s, all status=ok; inst-047231 flipped NO→hit vs baseline se.py.
Files: `/work/stt/configs/example/se_exp.py` (env-driven O3 overrides: SIMSPECT_{IEW_COMMIT,COMMIT_IEW}_DELAY,
SIMSPECT_{BACK,FWD}_COM_SIZE, SIMSPECT_SQUASH_WIDTH — additive, does NOT touch the in-use se.py);
`/work/stt/configs/example/se_slowcomm.py` (hardcoded — **still has the BROKEN 15/15/25/25/1**, must be
reset to the safe config before any run); `results/experiments/slow_comm_squash1/{STT_6,STT_6_interleave}/run_config.jsonc`
(point config_script at se_slowcomm.py, same binary — CPU delays are runtime params, no rebuild).
New experiment uses NEW watchers + NEW se variant only; existing watchers (all reference se.py) untouched.
Baselines to diff against: `results/STT_6_sttbuild`, `results/STT_6_interleave_sttbuild`.

## 2026-06-02 02:40 — analysis-claude (inspectBrHitsGem5) — SPT const-addr ld "hits" = Alloy over-approximation (NOT real); conservative diagnostic added
The live SPT_6_oneLP_fence run (new checkers) has 0 br_x hits (check_br fix holds) but ~2800 ld hits.
Classified: **~99.9% are NOT real leaks.** Root cause (model-vs-gem5): `leakage_function=Loads.inaddr`
enumerates every load address as a candidate xmit, and Alloy's protection set counts ANY
*speculatively-produced* value as protected — so a load whose address is computed by a speculative ALU
op (`TOther`) reading only **constants** gets flagged. SPT correctly untaints it (taint flows only from
speculative LOADS), so it issues with a public address → gem5 "hit" but no leak. The 06-01 20:17
`.als` edit (`hardware_protection_policy - ((Inreg+Inaddr)-outreg.rf)`) only excluded Inaddr with NO rf
edge at all; these have a producer (the const-op), so they slipped through — that's why const-addr
"hits" persist despite the edit. Confirmed testset used the edited model (provenance .als matches).
**Diagnostic added** (per CLAUDE.md diagnostics/ convention, first one built):
`results/SPT_6_oneLP_fence__20260602_013615/diagnostics/diag_constaddr_load.py` (+README). Conservative
signature: ld xmit whose transitive address chain (excluding the xmit itself — handles
`movq (%rsi,%rax),%rax` dest/addr aliasing) has **no uncommitted load** → known const-addr artifact.
On this run: **2795 known (masked) / 3 unknown** (`inst-001746/004097/004532` = load→load, address from a
speculative load → potential real leaks, left for review). Cross-checked vs the gem5-side taint
analyzer: masked set is 100% const-addr, no tainted-addr load hidden.
**Proper model fix (pending owner approval, NOT done):** derive the protection set as a forward closure
from real secret SOURCES (speculative load/memory outputs) via data-dependency edges, with monotone
(union) taint — then constant/missing-operand ops are untainted automatically and can never untaint a
tainted input. Don't enumerate missing operands; don't use AND-semantics. The dup-PC Stage-2 bug and
the check_br fix (entries below) are separate.

## 2026-06-02 01:58 — runmanagernew — added recon-modded gem5 watchers for the STT testsets (now both STT builds in parallel)
Per user, also point the STT testsets at `/work/gem5-recon-modded` (the STT/Recon build; scheme 2 = STT,
`branch_ann_enable`, X86O3CPU, fnc-stall 150) using the existing `run_config_STT_6.jsonc` /
`run_config_STT_6_interleave.jsonc` (already wired to recon-modded). Smoke-passed (branch-ann + fnc-stall path
OK, type-sorted). Launched 2 more `testrun.py` watchers:
- STT_6 → `results/STT_6__<ts>/` (pid 4165134); STT_6_interleave → `results/STT_6_interleave__<ts>/` (4165135).
Now 5 gem5 watchers total: STT_6 + STT_6_interleave on BOTH `/work/stt` (`*_sttbuild__<ts>`) and
recon-modded (`STT_6__<ts>` / `STT_6_interleave__<ts>`), plus SPT_6_oneLP fence (`/work/gem5-spt`). Each
campaign `manifest.json` records `gem5_binary` to disambiguate the bare-named recon-modded dirs. Load ~55.

## 2026-06-02 01:45 — runmanagernew — killed the leftover SPT monolith (`pipeline.py all`) that was self-sweeping gem5
The legacy `pipeline.py all --model SPT_6_oneLP` (pid 3474228, launched 20:11 for xml) was never killed after
xml. `all` couples xml→llvm→asm→**gem5 self-sweep**, so once it finished xml(100k)+llvm it entered
`phase_asm_gem5_streaming` and was running a **second, redundant Fence gem5 sweep** (non-type-sorted, into
`results/SPT_6_oneLP/`) in parallel with the new fence `testrun` watcher — double gem5 load on the same testset.
Killed it + subtree. Also killed the SPT stage-2 `--follow` follower (1801844): SPT asm is done
(not_taken 96,943 / taken 95,991 of 100k; the ~3–4k gap = dup-PC dropped stems, `.ll`-without-`.s`), and
`--follow` never self-terminates so it was busy-spinning re-failing the buggy `.ll`. **SPT now = follower-free
producer-complete + only the fence `testrun` watcher doing gem5.** Leftover redundant self-sweep
(`results/SPT_6_oneLP/`, ~6k partial recs, non-type-sorted) left in place pending user call (discard/keep).
Lesson: `pipeline.py all` is the monolith — for the split workflow use `testsetgen.py` (gen) + `testrun.py`
(gem5); don't leave an `all` running or it self-sweeps.

## 2026-06-02 01:36 — runmanagernew — restarted all gem5 watchers on the new (branch-fix) checkers, results now type-sorted
Per user: the checker scripts were updated 06-02 ~00:57–01:03 (`check_br.py`/`check_ld.py`/`check_other.py`/
`gem5_common.py` — esp. analysis-claude's check_br false-positive fix in the 00:30 entry below). Killed the 3
live `_sweep_watcher.py` watchers (STT_6_sttbuild 3473035, STT_6_interleave_sttbuild 3473036, SPT_6_oneLP_fence
3474229) + their gem5 subtrees only (other sessions' gem5 left alone). **Archived their pre-fix cumulative
results → `results/prebranchfixResults/`** (STT_6 34k, interleave 33k, SPT fence ~20k, invispec; old
non-type-sorted `_sweep_watcher` output). Relaunched the 3 via **`testrun.py`** (new checkers picked up
automatically; results split **by transmitter kind** into `results/<name>__<ts>/<mode>/<kind>/`). Smoke
confirmed new check_br is stricter (same gadget: old `br_x 1/1` → new `0/1`). invispec NOT relaunched
(fence-only, per 20:17 decision). Generators (SPT follower 1801844, legacy all 3474228, STT_6_interleave gen
3473033) untouched. **STT_6 gen finished**: 93,901/100,000 asm per mode, 6,099 (~6%) dropped by the dup-PC bug
(recoverable subset = `.ll` w/o `.s`).

## 2026-06-02 00:30 — analysis-claude (inspectBrHitsGem5) — CORRECTION + FIX: STT br_x hits are check_br false positives (NOT a gem5 leak); STT branch defense works
**Supersedes my 2026-06-01 23:22 entry below** ("STT branch leaks are REAL gem5 bugs"). That verdict was
WRONG — it came from running the gadget under gem5 with the **base ann (no resolve-stall)**, so the
speculative load never executed and the branch looked untainted (`stalledBranchMispredicts=0`).
The resolve-stall that opens the window is injected by the sweep (`pipeline.py:_inject_stalls`:
mispredict→5000, correctly_not_taken→grid[0,500,2500], xmit→0), not baked into the base ann.
**With the stall applied (real-sweep condition):** the load executes, taints `%rax`, and STT DOES
defend — the xmit branch is `made pending` (`stalledBranchMispredicts=2`; Commit log:
`(Lazy) A branch mispredicInst PC (0x401070=>...) is made pending`). Its redirect is delayed to
≈window-close. So there is **no in-window leak**; STT’s branch implicit-channel works.
**Root bug = `check_br`**: it keyed the verdict on the branch’s *resolve/complete* tick
(`xmit_complete`, in-window in both STT and unsafe) instead of the *squash/redirect* tick. STT delays
the redirect, not the resolve → false positive (exactly the complete-tick-vs-squash-tick gap flagged
in my 23:30 entry — now confirmed as the actual cause).
**FIX (applied, STAGE3_gem5/):** `gem5_common.py` now always traces `Commit`, adds
`parse_commit_squashes()` (pc→squash-broadcast ticks), and threads `squash_by_pc` into `check_fn`;
`check_br.py` keys `xmit_signal` on the xmit’s squash tick (no in-window squash ⇒ no hit), with a
fallback to the old complete-tick behaviour when no Commit trace exists; `check_ld.py`/`check_other.py`
accept+ignore the new arg.
**Validation (faithful sweep grid):** STT scheme=2 — all 5 reproduced br_x OLD-hits flip to NEW no-hit,
0/15 NEW hits. UNSAFE scheme=0 — inst-000009/000017/000027/000041 still NEW-HIT (real leaks caught);
inst-000002 (xmit never broadcasts a squash) correctly no-hit in both (was an OLD false positive).
**Impact:** br_x hit counts in STT_6_sttbuild / interleave are inflated by these false positives;
re-run with the fixed checker to get true numbers (likely ~0 under STT). **Checker bug — does NOT
change testset relaunch scope** (unlike the dup-PC Stage-2 bug). Full writeup: `STT_BRANCH_LEAK_ROOTCAUSE.md`
(rewritten with the corrected conclusion + "superseded claims").

## 2026-06-01 23:40 — opus-claude — Deep audit: PC numbering is correct across all existing testsets (read-only, no bug)
Audited PC-numbering integrity over ~96k tests across 11 testsets (STT_3/5, SPT_6, SPT_6_full, _otb_search_c1/c2,
_otb_alloy_probe, _verify_ld_taken, STL_bug, OTB, SMOKE) — both branch_modes, interleave `_vN` variants, all xmit
kinds (ld/br_x/other_x). Invariants checked per test by cross-referencing each `.ann.json` against the actual
`__litmus_<stem>_pcN:` labels in its `.s`: (1) no duplicate PC labels, (2) labels contiguous 0..max, (3) xmit.pc,
(4) every branch_pc, (5) btb_forced_target_pc (∈ labels or == end_block), (6) commit_boundary pcs all land on real
labels, (7) resolved addr/offset strictly monotonic with PC. **All clean.** Verdict: pass1 contiguous numbering, the
interleave renumber+target-remap (`parsexml.py:1056-1085`), and the post-fix NOP-last append are all self-consistent;
`compile_annotate.py` resolves PCs from `nm` ground truth.
Two non-PC notes: (a) two annotation schemas coexist — old relative `x86_*_offset` (STT_3/5, _otb_*, _verify_ld_taken,
STL_bug, OTB, SMOKE) vs new absolute `addr`/`func_base_addr` (SPT_6, SPT_6_full); both fully resolved (flag only if a
consumer assumes one schema). (b) `STL_bug/inst-000637-no-store` has a real PC gap (pc=3 removed) + stale
btb_forced_target_pc=3, but it's a hand-crafted debug variant (no source XML), not generator output. Could not audit
the post-22:50-fix regen output (SPT_6_oneLP/STT_6/STT_6_interleave have 0 resolved anns yet); the one inst-000001 I
regenerated by hand was clean.

## 2026-06-01 23:30 — analysis-claude (inspectBrHitsGem5) — check_br scope: sound for resolution-blocking defenses, NOT redirect-delaying ones
Methodology note for interpreting `br_x` hits. `check_br.py` flags a hit on: xmit branch *resolves/completes*
in `(lc_retire, fnc_retire)` AND fall-through never retired (squashed) AND other branches unresolved. That is
a correct detector of "secret-dependent branch resolved speculatively" — and it's keyed on the branch's
**complete tick**, NOT the squash/redirect-propagation tick.
- ✅ Correct for defenses that PREVENT speculative resolution / fence inputs (STT load-fence, DoM). Borne out:
  tainted-addr loads 0% hit.
- ⚠️ Would FALSE-POSITIVE for a defense that lets the branch resolve but DELAYS the squash broadcast (STT's
  intended branch implicit-channel): branch still completes in-window + wrong-path fall-through still never
  retires → still flagged, even if the redirect was pushed out of the window. To be airtight there, check the
  actual squash tick (when fall-through micro-ops are killed), not `xmit_complete`.
- Does NOT change the current STT verdict (branch delay is fully non-functional, redirect genuinely in-window),
  and the verdict doesn't rely on check_br anyway (`stalledBranchMispredicts=0` is gem5's own counter).
- Secret-dependence is CONFIRMED structurally (unbroken `load→mov→testq→jCC` chain) and by STT's own tagging
  (`rob_impl.hh:812-814` taints every speculative load dest). Not yet confirmed by a dynamic two-value
  differential (litmus loads 0 from zeroed mem) — dependency not in doubt, but that test would close all doubt.
  Detail in `STT_BRANCH_LEAK_ROOTCAUSE.md` §4a/§4b. CLAUDE.md:130's "known gap" note is partly stale (window IS
  enforced now; real residual gap = complete-tick vs squash-tick).

## 2026-06-01 23:22 — analysis-claude (inspectBrHitsGem5) — STT branch leaks are REAL gem5 bugs (taint never reaches branches through FLAGS)
Verdict for STT_6 `br_x` hits (verified by running `/work/stt/build/X86/gem5.opt` on individual gadgets,
NOT trusting AUDIT): **real gem5 leaks**, not pipeline/model artifacts.
- All STT hits are `BR_tainted` (branch condition data-dependent on a speculative load); all `ld` xmits
  are tainted-addr and 0% hit (load fence works). Loads protected, branches not.
- STT's branch implicit-channel defense IS on (`se.py:334 implicitChannel=scheme==2`) and exists
  (`commit_impl.hh:934-954` delays a mispredicted branch's squash while `instCausingSquash->isArgsTainted()`).
  It never fires: `stalledBranchMispredicts=0`, zero "made pending" in trace → the tainted branch redirects
  inside the window → leak.
- Cause: `isArgsTainted` is set only from `hasExplicitFlow` (`rob_impl.hh:809`). That explicit-flow taint
  propagates through INTEGER regs (so tainted load *addresses* fence via the SAME flag, `lsq_unit_impl.hh:1013`)
  but does NOT reach conditional branches — the chain `load→mov→testq→jCC` runs through the x86 condition-code
  /FLAGS register and the taint isn't carried across that hop.
- **Action: report-only.** gem5 STT taint-tracking bug → fix domain is gem5, **does NOT change relaunch scope**
  (unlike the dup-PC codegen bug below). Left unpatched per "don't touch gem5 except hooks". Full writeup:
  `STT_BRANCH_LEAK_ROOTCAUSE.md`. Open (needs instrumented build): exact failing link = CC-register
  `argProducer` match (`rob_impl.hh:228-236`) vs multi-hop ordering in `compute_taint`.

## 2026-06-01 23:18 — runmanagernew — in-flight generation predates opus-claude's 22:50 parsexml fix → contaminated
The running generators all started BEFORE the 22:50 parsexml fix below, so their testsets are a MIX
of old-(buggy)-logic and new-logic `.ll`/`.s` (the exact mid-run contamination `DESIGN.md` warns of):
- SPT_6_oneLP stage-2 follower (`testsetgen.py --follow`, pid 1801844) + the legacy `pipeline.py all`
  (pid 3474228) still enumerating xml.
- STT_6 + STT_6_interleave test-gen (pids 3473032/3473033) in asm.
**Action:** matches opus-claude's relaunch note — after the fix, wipe/`--force` the **llvm** phase for
SPT_6_oneLP / STT_6 / STT_6_interleave and regen llvm→asm onward. Pending user sign-off (do NOT have
the running gens silently produce a half-fixed testset). The 4 gem5 watchers consuming these will need
their cumulative results discarded for the affected br_x stems too.

## 2026-06-01 23:00 — runmanagernew — added streaming producer/consumer framework (testsetgen.py / testrun.py)
New `testsetgen.py` (producer: xml+llvm+asm pipelined via a bg xml thread; `--follow` attaches to an
externally-running xml producer) and `testrun.py` (consumer: a *copy* of `_sweep_watcher.py` that
splits gem5 results **by transmitter kind** into `results/<name>__<ts>/<mode>/<kind>/` + timestamped
campaign + `latest` symlink + manifest). Makefile gains `gen`/`run`/`pipeline`. **`pipeline.py` and
`_sweep_watcher.py` are unchanged** (in-flight legacy runs depend on them). Both smoke-tested e2e.
Ad-hoc launch scripts (incl. `run_sweep.sh`) moved to `archive/`. See CLAUDE.md "Pipelined run".

## 2026-06-01 20:17 — runmanagernew — relaunched SPT_6_oneLP fresh from edited .als; old results archived
Per user, edited `SPT_6_oneLP.als:337` (the `hardware_protection_policy` seed) to also untaint
`Inaddr` operands with no incoming `rf` edge — fixes the model/gem5 mismatch where constant-address
loads were tagged as transmitters but gem5/SPT correctly untaints them (was ~99% spurious ld "leaks").
**Restart reason = model fix:** wiped `testsets/SPT_6_oneLP` and relaunched from Alloy. Old results
(95,941 recs/run, fence+invispec) preserved in `results/_archive_SPT_6_oneLP_20260601_201714/`.
Stopped the SPT invispec watcher (load relief); keeping only `SpectreSafeFence` — the delay/fence
substrate is the closer match to SPT-the-paper's described protection (the SPT-ness is the
`applyDDIFT`+`fwd/bwdUntaint`+`configImpFlow=Lazy` flags, not the scheme name).

## 2026-06-01 22:50 — opus-claude — FIXED parsexml duplicate-PC label bug (~6% br_x tests dropped)
Root cause: the xm-branch NOP-injection queue in `parsexml.py` (~:737) injected a NOP both when the
xm branch was last *and* when the next instruction was a branch, duplicating a PC label → compile
failure, so ~6% of STT_6 `br_x` tests were silently dropped. Fix: inject only when the xm branch is the
last instruction. Verified `inst-000001` (previously dropped) now compiles; labels unique. AUDIT #14's
"dormant" claim was wrong — this was firing live in `pipeline_STT_6.log`.
**Relaunch needed:** already-generated `.ll` keep the old logic; wipe/`--force` the **llvm** phase for
**SPT_6_oneLP, STT_6, STT_6_interleave** and regen llvm→asm onward to recover the dropped br_x tests.
Full handoff writeup in `claudenotes.md` ("VERIFIED BUG" section).

## 2026-06-03 05:50 — 3a:runManagerNew — Stall-param validation: s_U masks (cliff), fnc plateaus at 150, s_R minor
Aimed the stall sweep (s_R/s_U/fnc) at the BUILD+REGIME WITH THE KNOWN BUG — /work/stt se_exp.py at
commitToIEWDelay=3 (VP-squash race active; reproduces fragility d=3: s_U=0 gives 27/200 NT ≈ 41/300).
Earlier recon-modded run was flat 0 (no leak to modulate; fixed check_ld) — NOT a usable result.
Real curves (real_cache_hits/200, not_taken), seeded sample, results/experiments/paper_stalls/stt_*:
 - s_U (unresolved stall): 27 @0 → 0 @50 → 0 @{250,1000,5000}. CLIFF: ANY nonzero s_U masks the leak
   (shoves xmit past fnc_retire). Campaign default 5000 erases it. => MUST sweep BARE s_U=0 to see leaks.
 - s_R (resolved stall): 27→22→22 (plateau by 8). Minor.
 - fnc (fnc_commit_stall): 16 @0 → 27 @150 → 27 @300. Window-widener reveals ~11 more; SATURATES at 150,
   so the chosen fnc=150 sits on the plateau (justified). Contra older "identical on/off" note — 16 vs 27.
Plots: plots/stall_curves.png + plots/fragility_curve.png. Fence/SPT negative-control DROPPED (per Anna:
not needed for STT analysis; STT timing leaks already independently real = VP-squash race). Doc:
PAPER_EXPERIMENTS.md (stall-only scope). Extended run_sample copy (paper_stalls/) adds --resolved-stall
(uniform over correctly_not_taken pcs) + --fnc-stall; pipeline/checker UNTOUCHED.

## 2026-06-03 05:58 — 3a:runManagerNew — Stall-sweep hits BUCKETED: 100% stt_vp_squash_race, 0 contamination
Ran diag_stt_vp_squash_race.py (--hits-from, commitToIEWDelay=3 env) on every hit of every stall point.
ALL hits classify as stt_vp_squash_race (the real bug): raw==bucketed at every point (sU_0 27/27,
sR_0/8/64 27/22/22, fnc_0/150/300 16/27/27, both modes). ZERO stt_no_hold / committed_access /
not_real_access / constaddr / rf. So the stall curves (plots/stall_curves.png) are pure-bug — the
metric needed no stripping on this regime. Bucket outputs: paper_stalls/stt_*/<mode>/race.json.
