# Can the pending-squash bug be reproduced by interleaving instructions instead of tuning timing?

**For:** Anna. **Date:** 2026-06-10. **Question:** recreate the nmosier pending-squash signal
*without* the injected `resolve_stall_cycles` knob — instead shape the timing by interleaving real
instructions — or explain why not.

## Verdict

**Partly possible in principle, but interleaving does NOT remove the timing tuning — it only
relocates it** from a cycle-count knob (`resolve_stall_cycles=N`) to a chain-length knob (insert K
dependent ops), and the required *same-cycle collision* becomes strictly **more fragile**, not less.
The bug is fundamentally a **coincidence** (an older tainted branch and a younger untainted branch
mispredicting in the *same* cycle); a coincidence has to be engineered by *some* knob.

⚠️ Overriding caveat: the pending-squash reproduction is already **RETRACTED / under review** (the
faithful value-flip non-interference test gives 0/12 — see `NMOSIER_PENDING_SQUASH_BUG.md` banner).
Re-timing it via interleave does not address that; this doc only answers the timing-mechanism question.

## How resolution timing actually works (verified in /work/stt source)

`iew_impl.hh:1337` — a branch executes at its **natural execute tick** (set by operand readiness),
then the squash/redirect broadcast is **deferred by `resolve_stall_cycles`** via a scheduled event:

```
resolution_broadcast_tick = natural_execute_tick + resolve_stall_cycles
```

So the stall is *additive* on top of natural timing — and natural execute IS controllable by
instruction interleaving (lengthen a branch's condition dependency chain → it executes later).
That is why interleaving *can*, in principle, substitute for the stall.

## Baseline: zero tuning does not fire

`python3 pendsquash_diff.py 8 0` (every branch `resolve_stall=0`, i.e. pure natural timing as the
gadget is generated): **0/8 leak.** Reason (§2.8 in WALKTHROUGH): `B_keep` (pc0) has a *constant*
condition (`movq $1` → ready at issue), so it resolves first and squashes `bo`/`by` before they can
collide. With no knob at all, the gadget never produces the coincidence.

## What interleaving would have to engineer (and why each is still tuning)

1. **Delay `B_keep` past `bo`/`by`.** Its condition is a ready-at-issue constant. The *only* way to
   push its natural execute tick later is to feed that condition through a long dependency chain —
   instructions whose sole purpose is to set a resolution tick. That is tuning by another name (chain
   length instead of cycle count). The chain must be **untainted** (constant-fed) so it doesn't
   change `B_keep`'s role.
2. **Make `bo` and `by` collide in the same cycle.** `bo`'s condition waits on the speculative secret
   load; `by`'s condition is constant (ready immediately) **and must stay untainted** (it is the
   observable). To align them you interleave an untainted latency chain into `by` tuned to land on the
   load's completion cycle. Hitting the *exact same cycle* via natural FU latencies + issue width +
   port contention is microarchitecture-specific and much less robust than one deterministic stall
   event — the stall was introduced precisely because the coincidence is otherwise unreliable.
3. **Addresses shift.** Inserting instructions moves every branch's address; the BTB-force and the
   checker's `branch_addr_hex` (used by `se.py` to force the mispredict) must be regenerated from the
   rebuilt binary, or the branches don't mispredict at all.

## Bottom line

The interleave approach trades a clean, deterministic single knob for a pile of padding instructions
that must be length-tuned per gadget to reproduce the same coincidence — more fragile and no less
"tuned." The honest framing: **the pending-squash signal is a same-cycle mispredict coincidence; you
cannot remove the need to manufacture that coincidence, only change which lever does it.** The
`resolve_stall_cycles` lever is the faithful, controllable one (it adds to natural timing, it does not
fake the branch outcome). If the goal is "no artificial hook," interleaving is achievable but buys
fragility, not fidelity.
