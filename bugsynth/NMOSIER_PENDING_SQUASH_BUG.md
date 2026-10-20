# The nmosier "pending-squash" bug in STT — what it is and why it leaks

> 🔴 **STATUS (2026-06-09): the bug MECHANISM below is correct, but our SimSpect REPRODUCTION is UNDER
> REVIEW / not yet valid.** The faithful value-flip non-interference test shows our generated gadget does
> NOT leak (public observables invariant to the secret; only `bo`'s own — protected — pending differs).
> The earlier 17/20 used a taint-flip across two different binaries and measured a codegen artifact, not a
> secret channel (gem5 treats our `by`'s condition as tainted). To get a valid repro: make `by` genuinely
> untainted, force bo & by to collide same-cycle, validate with the value-flip. See claudelog 2026-06-09.


*Conceptual writeup of the bug itself. For the SimSpect reproduction (how we generate gadgets for it and
confirm the leak on /work/stt), see `PENDING_SQUASH_BUG_REVIEW.md`. Upstream fix: `cwfletcher/stt` commit
`18e304f` ("fix pending squash bug"), branch `nmosier/bugfix/pending-squash`, PR #10.*

## One line
STT delays a **tainted** branch's squash to hide its (secret-dependent) direction — but when a tainted
branch and an **untainted** branch mispredict in the same cycle, the untainted branch gets dragged into the
delay, so **the untainted (attacker-observable) branch's redirect timing leaks the tainted branch's secret
direction.**

## The vulnerable scenario
Two in-flight, mispredicting branches in program order:

```
   ... speculation window ...
   ld_secret                 (speculative load of a secret)
   bo:  if (ld_secret) ...   ← OLDER branch, condition TAINTED  (the secret)        [mispredicts]
   by:  if (constant)  ...   ← YOUNGER branch, condition UNTAINTED (public/observable)[mispredicts]
```

`bo` is the secret (its condition came from a speculative load → STT marks it **tainted**).
`by` is untainted — an attacker is *allowed* to observe its mispredict-redirect timing, because by itself
carries no secret. The dangerous case is when `bo` and `by` resolve in the **same cycle**.

## The mechanism (two gem5 sites that combine)
*(verified in /work/stt, HEAD `e3283b9`, the pre-fix vulnerable build)*

1. **`iew_impl.hh:487` `squashDueToBranch`** — when multiple branches mispredict in the same cycle, IEW
   keeps the **oldest** (smallest seqNum) as `instCausingSquash`. A younger branch does **not** override it
   (`inst->seqNum < toCommit->squashedSeqNum` is false for the younger one). So with `bo` older, the squash
   is attributed to `bo`, and it *covers everything younger — including `by`*.

2. **`commit_impl.hh:936`** (STT + implicit channel) — STT makes the **entire** incoming squash *pending*
   (held until the instruction becomes non-speculative) **iff** `fromIEW->instCausingSquash->isArgsTainted()`:
   ```cpp
   if (fromIEW->instCausingSquash[tid]->isArgsTainted()) {
       fromIEW->instCausingSquash[tid]->hasPendingSquash(true);   // delay the WHOLE squash
       ++stalledBranchMispredicts;
   } else {
       handleSquashSignalFromIEW(tid);                            // squash immediately
   }
   ```
   Because `instCausingSquash == bo` is tainted, the whole squash — `by` included — is held pending until
   `bo` becomes non-speculative.

The *intent* is correct: don't broadcast a tainted branch's redirect (that would reveal its direction).
The *bug* is that the **untainted** `by` is collapsed into `bo`'s pending squash.

## Why it leaks — the secret-dependent timing channel
The observable is **`by`'s mispredict-redirect tick** (when fetch is redirected / the wrong-path is
cleared). `by` is untainted, so this is something the attacker can legitimately measure. But its timing now
depends on `bo`:

```
secret makes bo MISPREDICT (tainted):
    instCausingSquash = bo  →  isArgsTainted → squash PENDING
    →  by's redirect is DELAYED  (until bo becomes non-speculative)

secret makes bo CORRECTLY predicted:
    only by mispredicts → instCausingSquash = by (untainted)
    →  squash handled immediately
    →  by's redirect is EARLY  (at by's own resolution)
```

So the attacker reads off `by`'s redirect timing — *early* vs *late* — and learns whether `bo` mispredicted,
i.e. **the secret-dependent direction of the tainted branch**, without ever observing a tainted event. STT's
data-flow protection considers this gadget *secure* (no tainted value reaches an observable transmitter
operand); the leak is a **timing/squash-signal channel** the data-flow model doesn't capture.

## The fix (upstream `18e304f`)
Squash-signal **untainted** mispredicted branches **unconditionally**; only a **tainted** mispredicted branch
gets `hasPendingSquash(true)`. Then `by`'s redirect is never gated by `bo`'s taint, so its timing no longer
depends on the secret. Our `/work/stt` HEAD `e3283b9` is **not** an ancestor of this fix → it is the
vulnerable version.

## How we demonstrate it (SimSpect)
Differential on /work/stt scheme 2: build the *same* gadget two ways — `bo` reading a speculative load
(tainted) vs a constant (untainted) — and measure whether `by` is "made pending". `by` is delayed **only**
when `bo` is tainted ⇒ the secret-dependent squash signal. **17/20** generated gadgets show it.
Run: `python3 bugsynth/pendsquash_diff.py 20 2000`. Full reproduction + the Alloy/concretization changes:
`bugsynth/PENDING_SQUASH_BUG_REVIEW.md`.

## A note on where this sits in SimSpect
This bug does **not** fall out of the base SimSpect model: the base data-flow security predicate
(`secure_speculation_scheme_p`) calls the gadget secure (the observable branch is untainted). Capturing it
required **adding a new insecurity channel** to the model (`pending_squash_insecure_p` in
`models/STT_6_pendsquash.als`) — the squash-signal channel, analogous to adding implicit-flow. See the
"future directions" block in `STATUS.md` for the model-expressivity discussion.
