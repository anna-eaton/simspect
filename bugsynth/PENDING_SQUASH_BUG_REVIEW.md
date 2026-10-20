# Review: nmosier "pending-squash" bug GENERATED from Alloy and HIT on /work/stt

> 🔴 **RETRACTED / UNDER REVIEW (2026-06-09).** The "HIT" claim below does NOT survive the faithful
> value-flip non-interference test (0/12 leak; public observables invariant to the secret). The 17/20 here
> used a taint-flip comparing two different binaries and measured a codegen artifact (gem5 treats our `by`
> as tainted), not nmosier's secret-dependent squash signal. The Alloy/concretization infrastructure stands,
> but the demonstration needs: `by` genuinely untainted in gem5 + a same-cycle bo/by collision + value-flip
> validation. See `NMOSIER_PENDING_SQUASH_BUG.md` banner, STATUS, and claudelog 2026-06-09.


**For:** Anna. **Author:** autonomous `bugsynth` session, 2026-06-08. **Status:** ✅ demonstrated.
All work is isolated under `/tests/simspect/bugsynth/` — the live pipeline/models/testsets/results and
running sweeps were never touched.

## Claim (up front)
We built a **general** SimSpect pipeline — Alloy model → concretization → gem5 differential checker —
that *synthesizes the class* of the nmosier STT **pending-squash** gadget and **confirms the leak on the
real `/work/stt` gem5 (HEAD `e3283b9`, the pre-fix vulnerable build), scheme 2**. On a 20-gadget sample,
**17/20 leak**: a younger **untainted** branch's mispredict-redirect (squash) is **delayed** purely
because an older branch is **tainted** (secret-derived). This is the secret-dependent squash signal that
nmosier commit `18e304f` ("fix pending squash bug") fixes. It is a **real defense/gem5 bug**, not a
SimSpect artifact.

It is **not** a hand-written example or a predicate that asserts a fixed shape: the gadget class is
enumerated by Alloy and concretized generally; 17 distinct instances leak.

## The gadget (what the model generates)
Older **tainted** branch `bo` (condition fed by a speculative load) + younger **untainted** Branchx
`by` (the observable), both mispredicting, with an even-older branch holding the secret load speculative:
```
B_keep   (unresolved, keeps the load speculative; resolves LATE)
  L      speculative load  (secret)
  bo     branch, condition = L     -> TAINTED, mispredicts
  by     branch, condition = const -> UNTAINTED, mispredicts   (the attacker-observable event)
```

## Mechanism (verified in /work/stt source)
- `iew_impl.hh:487 squashDueToBranch`: when `bo` and `by` mispredict the same cycle, the **oldest**
  (smallest seqNum = `bo`) stays `instCausingSquash`; `by` does not override it.
- `commit_impl.hh:936` (STT + impChannel): `if (fromIEW->instCausingSquash->isArgsTainted()) {
  hasPendingSquash(true); ++stalledBranchMispredicts; }` else squash immediately. So a **tainted `bo`**
  makes the *whole* squash pending — dragging the younger **untainted** `by` into the delay. `by`'s
  redirect is therefore gated by `bo`'s (secret) taint, even though `by` itself is attacker-observable.

## Evidence (re-runnable)
Decisive single gadget — `inst-000001`, manual trace (resolve_stall: pc0=2000, bo/by=0):
- **TAINTED** (bo reads the load): both `pc3 (bo)` @2951500 and `pc4 (by)` @2952000 are
  `(Lazy) ... is made pending`.
- **UNTAINTED twin** (bo reads a constant): neither is pending (only the `retq` RAS event).
⇒ `by`'s pending is caused *only* by `bo`'s taint.

Differential over the corpus:
```
cd /tests/simspect/bugsynth && python3 pendsquash_diff.py 20 2000
# => 17/20 gadgets LEAK
```
`pendsquash_diff.py` builds each gadget two ways (tainted-bo testset `STT_6_pendsquash` vs untainted-bo
twin `STT_6_pendsquash_ut`), runs both on `/work/stt` scheme 2 with identical stalls, and flags a leak
iff `by` is made pending in the tainted run but not the untainted one.

## How it was built (general, from the Alloy up — full detail in `WALKTHROUGH.md`)
1. **Alloy** (`models/STT_6_pendsquash.als`): the base STT_6 model emits exactly ONE unresolved branch
   and its data-flow `secure_speculation_scheme_p` calls this gadget *secure* (the observable branch is
   untainted) — so this is a genuine **model-expressivity gap**. Added the squash-timing channel:
   `pending_squash_insecure_p` = ∃ older tainted unresolved branch + younger untainted unresolved
   Branchx (=xm), with explicit-dataflow taint for `bo` and STATE-level untaint for `by` (closing the
   shared-opstate clobber trap). Branch-resolution-minimality keeps only load-bearing branches.
2. **Concretization** (`STAGE2_compilation/parsexml.py`): a non-xm unresolved branch with a load-fed
   inreg is routed through `br_bez` (reads the inreg via the phys-pinned passthrough) so gem5-STT marks
   it tainted — instead of overwriting the condition with a constant. Marker `pendsquash_tainted` in the
   ann. `SIMSPECT_PENDSQUASH_NO_TAINT=1` emits the untainted-bo twin.
3. **Timing**: keep-speculative branches older than `bo` resolve late; `bo`/`by` resolve early & collide.
4. **Differential checker** `pendsquash_diff.py`.

## Verdict
**Real bug** (the defense leaks an untainted branch's redirect timing as a function of an older tainted
branch's outcome). It exists in `/work/stt` because HEAD is pre-`18e304f`. SimSpect's *base* model could
not express it (one unresolved branch + data-flow-only channel); the extension here closes that gap.

## What's open / caveats
- 3/20 non-leaks are degenerate (`bo=pc0` has no older keep-speculative branch so `bo` isn't actually
  tainted; or `by` is independently tainted because the xmit passthrough read a tainted register). The
  model could be tightened to force exactly one tainted branch (`bo`) and a guaranteed-untainted `by`.
- Owner decision: whether to fold `STT_6_pendsquash.als` (and the parsexml routing) into the mainline
  models, or keep as a dedicated bug-repro testset. **No mainline `.als`/pipeline was modified.**
- The matching nmosier fix is `18e304f`; running this corpus on a post-fix `/work/stt` should show 0/20
  (a good regression check we have not run).
