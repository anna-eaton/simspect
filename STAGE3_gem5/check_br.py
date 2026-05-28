#!/usr/bin/env python3
"""
check_br.py — branch transmitter checker.

The xmit instruction is a BEZ.  Registers are 0 so it will be taken, but
the predictor predicts not-taken → the processor fetches the fall-through
path.  When the BEZ resolves it squashes those instructions.

Leak detection:  compare the "last alive" tick (highest non-zero pipeline
stage) of the xmit branch vs. its fall-through instruction.  If the branch
is alive *after* its fall-through, the fall-through was squashed by the
branch — that redirect is the observable leak.

Usage:
    python3 check_br.py <input_dir> [--jobs N] [--out results.json] [--scheme N]
"""

from gem5_common import best_record, check_branch_resolutions, run_batch

_STAGES = ("fetch", "decode", "rename", "dispatch", "issue", "complete", "retire")


def _last_alive_tick(rec):
    """Return the tick of the last non-zero pipeline stage for a record."""
    if rec is None:
        return 0
    for stage in reversed(_STAGES):
        if rec[stage] > 0:
            return rec[stage]
    return 0


def check_br(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle, lsq_by_pc=None):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    # Find the fall-through instruction: smallest PC in the trace > xmit_pc
    ft_pc  = None
    ft_rec = None
    for pc in sorted(by_pc.keys()):
        if pc > xmit_pc:
            ft_pc  = pc
            ft_rec = best_record(by_pc[pc])
            break

    xmit_last_alive = _last_alive_tick(xmit_rec)
    ft_last_alive   = _last_alive_tick(ft_rec)

    # The branch redirected the processor → fall-through was squashed → leak.
    # Criterion: branch completed (resolved) AND fall-through never retired
    # (was squashed).
    branch_redirected = (
        ft_rec is not None
        and xmit_rec is not None
        and xmit_rec.get("complete", 0) > 0
        and ft_rec.get("retire", 0) == 0
    )

    # Dual condition: all *other* unresolved branches in the annotation must
    # still be unresolved at the moment the xmit branch propagates its
    # redirect (its own complete tick).  process_one already excluded xmit_pc.
    xmit_complete = xmit_rec.get("complete", 0) if xmit_rec else 0
    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, xmit_complete, unresolved, ticks_per_cycle)

    issued_in_window = branch_redirected and branches_unresolved

    return dict(
        issued_in_window=issued_in_window,
        xmit_last_alive=xmit_last_alive,
        ft_last_alive=ft_last_alive,
        ft_pc=hex(ft_pc) if ft_pc else None,
        lc_retire=lc_rec["retire"] if lc_rec else 0,
        fnc_retire=fnc_rec["retire"] if fnc_rec else 0,
        fnc_complete=fnc_rec["complete"] if fnc_rec else 0,
        branches_unresolved=branches_unresolved,
        branch_resolutions=branch_details,
    )


if __name__ == "__main__":
    run_batch(check_br, description="branch transmitter: xmit outlives fall-through")
