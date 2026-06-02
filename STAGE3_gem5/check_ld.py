#!/usr/bin/env python3
"""
check_ld.py — load transmitter checker.

A load leaks via cache state change at the time it issues its memory request
(the cache line is fetched into L1). The check is:

    lc_retire < xmit_signal < fnc_retire

`xmit_signal` is the LSQ "Executing load" tick for the xmit PC — the moment
the LSQ dispatches the load's memory request. Pipeview can't see this for
speculative loads: gem5's `~BaseO3DynInst()` only emits pipeview lines when
the DynInst is freed, and speculative-then-squashed loads stay alive in the
LSQ until simulation end (see /work/stt/src/cpu/o3/dyn_inst_impl.hh). The
LSQUnit debug trace logs the load through insert/execute/squash regardless,
so we use it as the primary signal and fall back to pipeview `complete` if
the LSQ trace has no entry (e.g. running against a gem5 without LSQUnit
logging, or for non-load xmits routed here by mistake).

If fnc is squashed (retire==0), the upper bound is infinity — the load
completed speculatively and was never cancelled.

Usage:
    python3 check_ld.py <input_dir> [--jobs N] [--out results.json] [--scheme N]
"""

from gem5_common import best_record, check_branch_resolutions, run_batch


def _xmit_execute_tick(lsq_by_pc, xmit_pc):
    """Latest LSQ 'Executing load' tick at xmit_pc (= memory-request dispatch),
    or 0 if the LSQ never executed a load at that PC."""
    if not lsq_by_pc:
        return 0
    recs = lsq_by_pc.get(xmit_pc, [])
    return max((r.get("execute_tick", 0) for r in recs), default=0)


def check_ld(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle, lsq_by_pc=None, squash_by_pc=None):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    # Primary signal: LSQ "Executing load" tick (cache-touch moment, includes
    # speculative loads invisible to pipeview). Fallback: pipeview complete.
    xmit_execute  = _xmit_execute_tick(lsq_by_pc, xmit_pc)
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    xmit_signal   = xmit_execute if xmit_execute > 0 else xmit_complete

    xmit_issue   = xmit_rec["issue"]   if xmit_rec else 0
    xmit_retire  = xmit_rec["retire"]  if xmit_rec else 0
    lc_retire    = lc_rec["retire"]    if lc_rec   else 0
    fnc_retire   = fnc_rec["retire"]   if fnc_rec  else 0
    fnc_complete = fnc_rec["complete"] if fnc_rec  else 0

    # Disqualifier: if the spec says there's a last-committed predecessor, it
    # must actually retire in gem5 — otherwise the test isn't behaving as the
    # Alloy model claims and the "hit" is a test-setup artefact, not a leak.
    lc_unretired_but_specified = (lc_pc is not None) and (lc_retire == 0)
    disqualified = lc_unretired_but_specified

    # xmit_retired_in_window: NOT a disqualifier. A surviving hit whose xmit
    # load retired (rather than being squashed) is a strong "real bug" signal —
    # the leaking load wasn't even cancelled, which means SPT let an
    # architecturally-committed load issue speculatively past unresolved branches.
    # Surfaced in the output for downstream reporting; does not gate the hit.
    xmit_retired_in_window = xmit_retire > 0

    after_lc   = (lc_retire == 0) or (xmit_signal > lc_retire)
    before_fnc = (fnc_retire == 0) or (xmit_signal < fnc_retire)
    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, xmit_signal, unresolved, ticks_per_cycle)
    issued_in_window = (not disqualified
                        and (xmit_signal > 0) and after_lc and before_fnc
                        and branches_unresolved)

    return dict(
        issued_in_window=issued_in_window,
        xmit_signal=xmit_signal,
        xmit_execute=xmit_execute,
        xmit_complete=xmit_complete,
        xmit_issue=xmit_issue,
        xmit_retire=xmit_retire,
        xmit_retired_in_window=xmit_retired_in_window,
        lc_retire=lc_retire,
        lc_unretired_but_specified=lc_unretired_but_specified,
        fnc_retire=fnc_retire,
        fnc_complete=fnc_complete,
        branches_unresolved=branches_unresolved,
        branch_resolutions=branch_details,
    )


if __name__ == "__main__":
    run_batch(check_ld, description="load transmitter: xmit_complete in (lc_retire, fnc_retire)")
