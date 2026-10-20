# bugsynth — generating + hitting two STT-family bugs from the Alloy up

**Author:** autonomous Claude session `bugsynth` (Anna asleep). **Started:** 2026-06-08.
**Goal (Anna's brief):** from the Alloy model up, build a **general** pipeline that *synthesizes the
class* of tests that trigger two known bugs and *actually hits them on real gem5* — not a hand-written
example, not a predicate that merely asserts a fixed shape. Two targets, two builds:

| bug | what it is | target build | scheme |
|---|---|---|---|
| **OTB** (`getOldestTaint`) | recon's ALU keeps only the *oldest* taint feeding an op; a 2-input ALU merging an older-resolving tainted load + a still-speculative tainted load is treated untainted → its result feeds a transmitter load address that issues speculatively | `/work/gem5-recon-modded` | `--scheme=2` **+ `allow_leaked`** |
| **pending-squash** (nmosier coincidence) | STT delays a *tainted* branch's squash; `squashDueToBranch` always keeps the **oldest** mispredicting branch as `instCausingSquash`; so an **older tainted** + **younger untainted** branch mispredicting the same cycle makes the whole squash pending → the younger *untainted* branch's redirect timing is gated by the secret | `/work/stt` | `--scheme=2` |

**Isolation guarantee:** everything lives under `/tests/simspect/bugsynth/`. The real
`pipeline.py`, `STAGE*`, `STAGE1_alloy/models/*.als`, `testsets/`, `results/`, and all running
sweeps are **untouched**. This workspace has its own copies of `pipeline.py`,
`STAGE2_compilation/`, `STAGE3_gem5/`, `models/`, `configs/`, `testsets/`, `results/`. The shared
read-only `alloy6.jar` is reused via `paths.alloy_stage → ../STAGE1_alloy` (jar never modified).

---

## 0. Ground truth: the exact gem5 trigger for each bug (verified from source)

### OTB — `/work/gem5-recon-modded`
Recon's `getOldestTaint` (reconresults.md Bug 1): an ALU op's output is treated as carrying only its
**oldest** input's taint. Gadget shape the *pipeline* must synthesize (general, any surrounding context):
```
br_r        (resolves EARLY — older)        ── ld_inj under it becomes nonspec first (the "oldest" taint)
br_u        (stays speculative — younger)   ── ld_base under it stays speculative
other = f(ld_base, ld_inj)   2-input ALU, ONE operand left free  (ld_inj hooks the free slot)
xm    = load(other)          transmitter address = other's result
```
When `br_r` resolves, `ld_inj` (oldest taint) is freed; `getOldestTaint` then treats `other` untainted
even though `ld_base` (under still-unresolved `br_u`) is speculative → `xm` issues speculatively.
Per `mdsToRead/OTB_GENERATION_GAP.md`: this is **not an Alloy expressivity limit** — the base model
*can* route a transmitter address through an ALU (SAT when the class is required); it's a 150k
enumeration **cap/ordering** artifact (simpler direct `load→xmit` shapes fill the cap first). The
**general** mechanism that manufactures the cross-chain merge is `parsexml.py:pass_interleave`
(injects a second tainted chain pinned to free-pool atoms; `pass3` collides them onto the ALU's blank
operand). So OTB = *require the ALU-on-address class* + *interleave ON* + *sweep so the two chains
resolve at different times*. No new pinned instance.

### pending-squash — `/work/stt` (HEAD `e3283b9`, pre-fix, vulnerable)
Verified source path:
- `iew_impl.hh:482 squashDueToBranch`: `if (!toCommit->squash || inst->seqNum < toCommit->squashedSeqNum) { … instCausingSquash = inst; }` → when two branches mispredict the same cycle, the **oldest (smallest seqNum)** wins and stays `instCausingSquash`; the younger one does **not** override (`squashedSeqNum < younger.seqNum` ⇒ guard false).
- `commit_impl.hh:934-952` (STT + `impChannel`): `if (fromIEW->instCausingSquash->isArgsTainted()) { … hasPendingSquash(true); ++stalledBranchMispredicts; }` else `handleSquashSignalFromIEW()`. So if the **oldest** mispredicting branch is **tainted**, the *entire* squash (covering the younger untainted branch too) is made **pending** — delayed until that tainted branch becomes nonspeculative.

**The leak:** take an **older tainted** branch `B_o` (condition derived from a speculative load) and a
**younger untainted** branch `B_y` (condition a committed/constant value), both mispredicting.
- secret makes `B_o` mispredict ⇒ `instCausingSquash = B_o` (tainted) ⇒ squash pending ⇒ `B_y`'s
  redirect is **delayed** to `B_o`'s resolution.
- secret makes `B_o` correct ⇒ only `B_y` mispredicts ⇒ `instCausingSquash = B_y` (untainted) ⇒ squash
  **immediate** ⇒ `B_y` redirects at its own resolve.

`B_y` is *untainted* and therefore an attacker-observable event, yet **its redirect timing encodes the
tainted branch `B_o`'s direction** = the secret. Detection is a **differential**: run the same gadget
with `B_o` forced mispredict vs forced-correct (BTB force) and show `B_y`'s redirect tick moves by the
`B_o`-pending delay. (`stalledBranchMispredicts>0` while the *pending* inst's own younger branch is
untainted is the in-sim smoking gun.)

This needs (confirmed an **Alloy limitation**): the model currently emits **exactly one** unresolved
branch per test → structurally cannot make two mispredicts collide. So the Alloy must be extended to a
**≥2-unresolved-branch, mixed-taint** dimension + a new insecurity channel so the class enumerates
generally; the sweep must **collide** the two resolutions (coincidence band) at `commitToIEWDelay≥2`.

---

## 1. Workspace layout
```
bugsynth/
  pipeline.py                  copy of the engine (will get: coincidence band, commit/iew-delay env bridge)
  STAGE2_compilation/          copy (parsexml.py will get: 2-mispredict-branch concretization)
  STAGE3_gem5/                 copy (check_br.py will get: differential squash-signal test; gem5_common env)
  models/STT_6.als             pristine copy (baseline)
  models/STT_6_otb.als         OTB class variant
  models/STT_6_pendsquash.als  pending-squash ≥2-branch variant
  configs/                     run configs pointing ALL path keys inside bugsynth/
  testsets/  results/          generated artifacts (isolated)
  WALKTHROUGH.md               this file
```

---

## 2. Change log (each change, why, and the gem5 evidence it produced)

<!-- appended as I go -->

### 2.1  OTB alloy variant (`models/STT_6_otb.als`) — DONE
- Added `pred otb_class { some x: Loads | x in xm and some o:(Otherns+Otherxs) | some(o.outreg & rf.(x.inaddr)) }`
  and conjoined into `run gen_lit`. **General over the class** (any load xmit, any ALU, any context) — not a pinned instance.
- SAT-validated on the real `alloy6.jar` (cap 8): every instance has `other.outreg → xmit_load.inaddr`,
  the ALU carries ONE inreg + a FREE 2nd slot, diverse kinds/context. `/tmp/otb_sat`.
- Generated cap=500 → `bugsynth/testsets/STT_6_otb/xml` (500 instances).

### 2.2  OTB interleave compile — PARTIAL, found a GAP
- Config `configs/run_config_STT_6_otb.jsonc`: recon-modded scheme2 + `allow_leaked`, interleave ON
  (variants_per_instance=4, num_chains=1). llvm phase → 2000 `_v` variants.
- **GAP (inst-000001_v1):** the xmit load (pc7) address = `r8 = load(pc5) + r12_0`, but `r12_0` is a
  free *register init*, NOT an injected load; the injected chain (pc3→pc4 load→ALU) feeds a *different*
  load (pc8). The two tainted chains are **parallel, not merged** → no 2-load→ALU→xmit merge → does NOT
  exercise getOldestTaint. This is precisely the OTB_GENERATION_GAP.md open caveat ("does pass_interleave
  hook the injected chain onto the ALU feeding the xmit address, under an earlier-resolving branch?").
- NEXT: read `parsexml.py:pass_interleave` + `pass3` free-map; make the injected chain's terminal output
  COLLIDE with the xmit-ALU's free operand (general mechanism), and land it under an earlier-resolving branch.

### 2.3  OTB targeted-alias in `parsexml.py:pass_interleave` — DONE (general, config-gated)
- New helper `_otb_target_alias(instructions, all_steps)`: finds the transmitter load → its address
  Reg_s state → the non-synthetic ALU that produces it → that ALU's FREE inreg slot, and pins it to the
  injected chain's terminal `Reg_s$fr` atom. pass3 then maps both to the same physical reg ⇒ the ALU
  genuinely merges the base (speculative) load and the injected (earlier) load. **General over otb_class**
  (wires existing free slot to existing chain; asserts no shape). Gated by `interleave.otb_target:true`;
  default interleave path untouched.
- Also front-places the injected chain right after the committed boundary so the injected load is the
  OLDEST speculative inst (the taint getOldestTaint frees first); base load+ALU+xmit follow.
- Linkage fact used: specified slot `physical` == opstate `Reg_s$X`; same-state rf ⇒ ALU.outreg.physical
  == xmit.inaddr.physical; same fr-atom ⇒ same phys reg in pass3.
- **Verified (inst-000001_v1):** pc6 `leaq (rax, rdi)` now merges rax=base-load(pc5, under mispredict
  branch) + rdi=injected-load(pc1, front-placed/older); xmit pc7 loads `probe[merged]`. Structural sweep
  `otb_merge_check.py`: **428/2000 variants** have a 2-load ALU feeding the xmit address (was 0/2000).
  Not yet 100% (store-terminated chains / ALUs with no free slot) — to tighten next.

### 2.4  Pending-squash alloy model (`models/STT_6_pendsquash.als`) — DONE (the Alloy-limitation fix)
This is the **expressivity extension** the bug needs (the base model emits exactly ONE unresolved
branch; the data-flow `secure_speculation_scheme_p` calls the gadget SECURE because the observable
branch is untainted). New, general (no pinned shape):
- `tainted_operands_p[p]` / `tainted_states_p[p]`: protected mem operand + forward op-edge (rf+ddi)
  closure, and its state projection.
- `branch_cond_tainted_p` (bo): condition rf/ddi-reachable from a speculative load = explicit-dataflow
  taint (concretizes to actually read the secret; acyclic rf+spo ⇒ producing load precedes bo).
- `branch_cond_untainted_p` (by): condition state ∉ tainted_states — **STATE-level**, which closes the
  shared-opstate clobber trap (an inreg with no rf but the same register-state as a tainted value would
  still read it at concretization).
- `pending_squash_insecure_p[p]`: ∃ OLDER tainted unresolved branch `bo` + YOUNGER untainted unresolved
  Branchx `by`=`xm`, `bo` strictly before `by`. Replaces `tag_xm` (data-channel) — xm is now the
  observable untainted branch.
- run `gen_lit_ps` with branch-resolution-minimality (`not pending_squash_insecure_p[RR->i]` over
  unresolved branches) so only load-bearing branches stay unresolved.
- **SAT-validated** (cap 10) on real alloy6.jar: every instance = older-tainted-branch (cond←load via
  rf) + younger-untainted-xm-branch, clobber-free, diverse contexts. `/tmp/ps_sat`.
- The remaining "make bo & by the two COLLIDING oldest mispredicts" is a TIMING concern (the sweep
  coincidence band, §2.6) + the differential checker (§2.7) which isolates bo's effect — NOT a model
  constraint.

### 2.5  OTB first gem5 sample (recon-modded) — 0 hits, ROOT-CAUSED placement bug
- Ran 427 merged variants on /work/gem5-recon-modded scheme2+allow_leaked (sweep points [0,500,2500],
  unres 5000). Result: 427/427 `issued_in_window=false`, **`xmit_issue=0`** — the transmitter never issues.
- Read the authoritative recon bug (`reconresults.md` Bug 1 + `taint_tracker.cc`): `getOldestTaint` picks
  the OLDEST tainted ALU source; `freeTaints` drops a taint when `!isSpeculative()`. The leak needs BOTH
  ALU-source loads SPECULATIVE/tainted, the OLDER resolving FIRST (frees the ALU taint) while the YOUNGER
  stays speculative → xmit issues.
- **Bug in my §2.3 placement:** I front-placed the injected load BEFORE any branch → it was NOT under an
  unresolved branch → `isSpeculative()=false` → never tainted → getOldestTaint never selected it → the
  ALU taint stayed pinned to the (still-speculative) base load → xmit held → squashed (never issues).
- FIX: place the injected load UNDER the first uncommitted branch (speculative, earlier-resolving) so it
  is the OLDER tainted source that frees first; base load stays under the later mispredict.

### 2.6  Pending-squash concretization in `parsexml.py` — DONE
- `_branch_has_specified_inreg`: a non-xm unresolved branch with an Alloy-specified (rf/load-fed) inreg.
- pass2_5: such a branch (`bo`) is routed through **br_bez** (testq+jz reading the inreg via the
  phys-pinned passthrough), value 0 → ZF=1 → jz arch-taken to end_block, BTB fall-through → mispredict —
  same mechanism as the xm branch but NON-xm. Without this, the non-xm branch path overwrote the
  condition with a constant (`movq $1`), erasing the load→branch taint → bo untainted.
- Marker `pendsquash_tainted` propagated to the ann (emit_branch_annotations) so the checker finds bo.
- **Verified:** inst-000001 pc3 (bo) now emits `movq %rcx,%rdx; testq %rdx` where %rcx is pc2's load
  output → tainted; pc0 stays constant (untainted), pc4 = xmit (by). **120/120 tests** have a tainted bo
  older than the br_x xmit. General — no pinned shape.

### 2.7  (next) differential checker — does by's redirect tick depend on bo (the secret)?

### 2.8  Pending-squash differential v1 — diagnosed: bo/by never collide (timing)
- Built `pendsquash_diff.py`: tainted-bo vs untainted-bo twin, compares by's redirect tick on /work/stt.
- v1 (uniform resolve_stall=200): Δ=0 for all — NO leak. Root cause via pipeview seqNum→PC mapping:
  the only made-pending event is the **retq** (RAS mispredict, pc5+12→0x401005); among the litmus
  branches only **pc0** squashes. **bo(pc3) and by(pc4) never resolve** — pc0 (older) mispredicts and
  squashes the whole speculative path (incl. bo,by) before they resolve. No bo/by coincidence → the
  pending gate never sees bo as instCausingSquash for by.
- FIX (timing, task 4): keep-speculative branches OLDER than bo (e.g. pc0, needed to keep the secret
  load speculative so bo is tainted) get a LARGE resolve_stall (resolve late); bo and by get SMALL,
  COINCIDENT resolve_stalls (sweep the bo↔by delta to land them in the same cycle). Then bo (older,
  tainted) is instCausingSquash for the bo/by squash → made pending → by's redirect delayed.

### 2.9  Pending-squash differential — ✅ BUG DEMONSTRATED (17/20 gadgets leak on /work/stt)
`pendsquash_diff.py` final result (keepspec_stall=2000, /work/stt scheme2):
**17/20 gadgets LEAK** — the younger UNTAINTED branch `by` is "made pending" (its mispredict-redirect
squash delayed) in the TAINTED-bo run but NOT in the untainted-bo twin. The ONLY difference between the
twins is whether bo reads the speculative load (tainted) or a constant (untainted), so by's
observable-redirect delay is caused purely by bo's (secret-derived) taint = the nmosier secret-dependent
squash signal. Decisive single-gadget trace (inst-000001, manual): tainted run makes BOTH pc3(bo) and
pc4(by) pending @2951500/2952000; untainted twin makes neither (only the retq RAS event).

**Mechanism path (all verified in /work/stt source):** iew_impl.hh:487 keeps the OLDEST mispredict
(bo) as instCausingSquash when bo & by collide; commit_impl.hh:936 makes the whole squash pending iff
instCausingSquash.isArgsTainted() → by (younger, untainted) is dragged into bo's pending squash.

**Timing that makes it fire:** the keep-speculative branch(es) older than bo get a large resolve_stall
(stay unresolved so the secret load is speculative → bo tainted, and they resolve AFTER bo/by); bo and by
get 0 (resolve & collide early). The 3 non-leaks are degenerate (bo=pc0 has no older keep-spec branch, or
by is independently tainted).

Pieces (all general, no pinned shapes): model `STT_6_pendsquash.als` (§2.4) + concretization (§2.6) +
untainted twin via `SIMSPECT_PENDSQUASH_NO_TAINT` + `pendsquash_diff.py` differential checker.

### 2.10  OTB v2 — ROBUST direct-Alloy generation (no interleave); structure right, xmit not yet issuing
New, more robust OTB approach (replaces the fragile interleave-alias path): generate the full
2-load→ALU→xmit merge DIRECTLY in Alloy. `models/STT_6_otb2.als`:
- `otb_class`: xmit load addr ← a 2-INPUT ALU whose both inputs are rf-fed by DISTINCT loads `la,lb`;
  `la` under a RESOLVED branch `ba` (→ concretizes correctly-not-taken = held by resolve_stall, resolves
  early w/o squash), `lb` under an UNRESOLVED branch `bb` (mispredict, stays speculative); `ba<la<bb<lb`.
  General over the class.
- relaxed driver `gen_useful_otb` (drops branch RR-minimality, which rejects the inherently 2-source
  merge — same reason pending-squash needed its own driver). SAT; structure verified:
  `ba(cnt) < la < bb(mispredict) < lb < ALU < xmit`. Concretization correct (inst-000001: la=pc1 under
  cnt pc0, lb=pc3 under mispredict pc2, ALU pc4 merges both, xmit pc5).
- **gem5 (recon-modded scheme2+allow_leaked): 0 hits — the xmit never issues** (xmit_issue=0 across pc0
  stalls {100..4500}). Only one litmus load shows "Executing load"; needs taint-state tracing.
  HYPOTHESES for next iteration: (a) getOldestTaint pins the ALU taint to `lb` (younger) not `la` because
  `la`'s data reaches the ALU only after pc0 resolves (so the bug needs `la` data BEFORE pc0 resolves —
  a real coincidence band, like the reference's "slow branch_outer"); (b) a generated load doesn't
  execute speculatively (squashed/invalid addr). NEXT: add an observability DPRINTF hook to
  taint_tracker.cc getOldestTaint/freeTaints (allowed: hooks only, not defense logic) and re-run; verify
  the reference hand-crafted test's xmit DOES issue on this build as the control.

### 2.11  OTB — RESOLVE-STALL ANN-SCHEMA FIX (gadget now executes on recon-modded); timing band remains
- **Confirmed control**: the reference `oldest_taint_bug/inst-oldest-taint-bug.s` LEAKS on /work/gem5-recon-modded
  (pc5 xmit issues 2807000, executes/cache-touch sn:575 @2807500, before branch_inner resolves ~2825500).
  So build + getOldestTaint mechanism work.
- **ROOT-CAUSE of "xmit never issues"**: recon-modded's `se.py:load_branch_annotations` reads
  `branch_pc_addr_hex`/`x86_branch_offset_hex` (older schema), NOT `branch_addr_hex` (which /work/stt reads
  and which our compile_annotate wrote). → recon-modded SKIPPED every annotation → no resolve_stall →
  the mispredict branch squashed the wrong-path gadget (load_B, ALU, xmit) immediately, before it issued.
- **FIX (bugsynth `compile_annotate.py`, additive)**: emit `branch_pc_addr`/`branch_pc_addr_hex` +
  `x86_branch_offset`/`x86_branch_offset_hex` aliases alongside `branch_addr_hex`, so the resolve-stall
  registers on EITHER build. Verified: stallCycles now applied (pc0=2500, pc2=5000; were 0/0). The gadget
  now EXECUTES: pc3 load_B, pc4 ALU, pc5 xmit all issue+complete; xmit touches cache. **90/90 xmit_issued
  (was 0/90).**
- **REMAINING (timing band, next iteration):** issued_in_window still 0 — the xmit issues just AFTER the
  window closes. Mechanism: getOldestTaint must pin the ALU taint to `la` (older) while `la` is still
  tainted at ALU-execute, THEN free `la` (pc0 resolve) while `lb` stays speculative (pc2 unresolved), so
  the xmit issues in (la-freed, pc2-resolve). Current grid [0,500,2500]×5000 doesn't land that band (la
  freed ≈ pc2 resolve). NEXT: sweep pc0 vs pc2 so T_alu < T_pc0_resolve < T_xmit < T_pc2_resolve; the
  reference achieves this with a slow branch_inner. Pure timing-sweep problem now — structure is correct.

### 2.12  OTB — ✅ BUG REPRODUCED (10/10 differential on recon-modded)
`otb_check.py` differential (la-branch=2500 resolves first vs control both=9000):
**10/10 gadgets LEAK** — the xmit is released (issues 3924500, completes/accesses cache) while `lb` is
still speculative (bb squashes 7174500), but ONLY when `la` resolves first; the control (la & lb resolve
together) holds the xmit until 7174500 (no early release). That isolates getOldestTaint's oldest-taint
early-free (taint_tracker.cc:119 + freeTaints:134). Reference hand-crafted test leaks identically (control).
Full writeup: `OTB_BUG_REVIEW.md`. **BOTH bugs now reproduced** (pending-squash 17/20 on /work/stt; OTB
10/10 on /work/gem5-recon-modded), each generated from the Alloy up, general, isolated in bugsynth/.

### 2.13  OTB — HARDENED: robust across timing + corpus (30/30), not fine-tuned
- Re-keyed `otb_check.py` leak = the xmit RELEASES earlier under OTB timing than the same-stall control
  (Δrelease ≥ 1 cycle margin) while lb speculative — avoids the tick-level boundary artifact the old
  `xissue<bb_squash` had at tight bb.
- **30/30 gadgets leak at the DEFAULT pipeline mispredict stall (2500/5000)** — Δrelease ≈ 1.25M ticks
  (2500 cyc) consistently (xmit freed when older la resolves, not lb).
- **Robust across the timing band**: 5/5 differential at every tested (la-branch,bb) in
  {(500,5000),(2500,5000),(1500,7000),(2500,9000),(3500,12000)}; control 0/5 throughout. Works at the
  pipeline's natural mispredict stall, so NOT a fine-tuned single point.
- Diversity note: OTB gadgets are 1 branch-structure template (2 br + 2 ld + ALU + xmit fills the
  `exactly 6 Instruction` scope; only register/mem assignment varies). Pending-squash has 7 shapes
  (3–5 branches). Structural diversity is scope-bounded, not a tuning artifact.
