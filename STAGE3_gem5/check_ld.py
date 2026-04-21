#!/usr/bin/env python3
"""
check_ld.py — load transmitter checker.

A load leaks via cache state change at the time it completes (the cache line
is fetched into L1).  The check is:

    lc_retire < xmit_complete < fnc_retire

If fnc is squashed (retire==0), the upper bound is infinity — the load
completed speculatively and was never cancelled.

Usage:
    python3 check_ld.py <input_dir> [--jobs N] [--out results.json] [--scheme N]
"""

from gem5_common import best_record, run_batch


def check_ld(by_pc, xmit_pc, lc_pc, fnc_pc):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    xmit_issue    = xmit_rec["issue"]    if xmit_rec else 0
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    lc_retire     = lc_rec["retire"]     if lc_rec   else 0
    fnc_retire    = fnc_rec["retire"]    if fnc_rec  else 0

    after_lc         = (lc_retire == 0) or (xmit_complete > lc_retire)
    before_fnc       = (fnc_retire == 0) or (xmit_complete < fnc_retire)
    issued_in_window = (xmit_complete > 0) and after_lc and before_fnc

    return dict(
        issued_in_window=issued_in_window,
        xmit_issue=xmit_issue,
        xmit_complete=xmit_complete,
        lc_retire=lc_retire,
        fnc_retire=fnc_retire,
    )


if __name__ == "__main__":
    run_batch(check_ld, description="load transmitter: xmit_complete in (lc_retire, fnc_retire)")
