#!/usr/bin/env python3
"""
check_other.py — other (variable-latency) transmitter checker.

Variable-latency instructions (e.g. integer divide, bit operations) can leak
via timing side-channels observable when the instruction completes.  The
observable effect is analogous to a load's cache-line fetch — it happens at
completion time.

The check is identical to the load transmitter check:

    lc_retire < xmit_complete < fnc_retire

Usage:
    python3 check_other.py <input_dir> [--jobs N] [--out results.json] [--scheme N]
"""

from gem5_common import best_record, check_branch_resolutions, run_batch


def check_other(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle, lsq_by_pc=None):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    xmit_issue    = xmit_rec["issue"]    if xmit_rec else 0
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    lc_retire     = lc_rec["retire"]     if lc_rec   else 0
    fnc_retire    = fnc_rec["retire"]    if fnc_rec  else 0
    fnc_complete  = fnc_rec["complete"]  if fnc_rec  else 0

    after_lc   = (lc_retire == 0) or (xmit_complete > lc_retire)
    before_fnc = (fnc_retire == 0) or (xmit_complete < fnc_retire)
    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, xmit_complete, unresolved, ticks_per_cycle)
    issued_in_window = ((xmit_complete > 0) and after_lc and before_fnc
                        and branches_unresolved)

    return dict(
        issued_in_window=issued_in_window,
        xmit_issue=xmit_issue,
        xmit_complete=xmit_complete,
        lc_retire=lc_retire,
        fnc_retire=fnc_retire,
        fnc_complete=fnc_complete,
        branches_unresolved=branches_unresolved,
        branch_resolutions=branch_details,
    )


if __name__ == "__main__":
    run_batch(check_other, description="other transmitter: xmit_complete in (lc_retire, fnc_retire)")
