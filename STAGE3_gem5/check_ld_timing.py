#!/usr/bin/env python3
"""
check_ld_timing.py — load transmitter checker with extra timing fields.

Same hit condition as check_ld.py:

    lc_retire < xmit_complete < fnc_retire

Additional output fields:
  fnc_fetch  — tick at which the unresolved branch was fetched / predicted.
               This is the START of the speculation window (the processor
               started executing speculatively from this point).
  lc_fetch   — tick at which the last-committed instruction was fetched
               (for reference).

Usage:
    python3 check_ld_timing.py <input_dir> [--jobs N] [--out results.json] [--scheme N]
"""

from gem5_common import best_record, run_batch


def check_ld_timing(by_pc, xmit_pc, lc_pc, fnc_pc):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    xmit_issue    = xmit_rec["issue"]    if xmit_rec else 0
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    lc_retire     = lc_rec["retire"]     if lc_rec   else 0
    fnc_retire    = fnc_rec["retire"]    if fnc_rec  else 0
    fnc_fetch     = fnc_rec["fetch"]     if fnc_rec  else 0
    lc_fetch      = lc_rec["fetch"]      if lc_rec   else 0

    after_lc         = (lc_retire == 0) or (xmit_complete > lc_retire)
    before_fnc       = (fnc_retire == 0) or (xmit_complete < fnc_retire)
    issued_in_window = (xmit_complete > 0) and after_lc and before_fnc

    return dict(
        issued_in_window=issued_in_window,
        xmit_issue=xmit_issue,
        xmit_complete=xmit_complete,
        lc_retire=lc_retire,
        fnc_retire=fnc_retire,
        fnc_fetch=fnc_fetch,
        lc_fetch=lc_fetch,
    )


if __name__ == "__main__":
    run_batch(check_ld_timing,
              description="load transmitter + fnc_fetch: xmit_complete in (lc_retire, fnc_retire)")
