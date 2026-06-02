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


def check_br(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle, lsq_by_pc=None, squash_by_pc=None):
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
    xmit_complete   = xmit_rec.get("complete", 0) if xmit_rec else 0

    # The observable leak is the xmit branch BROADCASTING its mispredict squash
    # (redirecting fetch) while still speculative — NOT merely resolving. A
    # delay-based defense (STT implicit-channel "made pending") lets the tainted
    # branch COMPLETE in-window yet never broadcasts the redirect in-window, so
    # keying on `complete` would false-positive. Use the actual squash tick from
    # the Commit log (`squash_by_pc`). Fall back to the complete tick only when
    # no Commit trace is present (e.g. a build/run that didn't emit it), which
    # preserves the legacy behaviour for non-delay defenses.
    commit_traced = bool(squash_by_pc)
    xmit_squashes = squash_by_pc.get(xmit_pc, []) if squash_by_pc else []
    if commit_traced:
        # earliest squash this branch broadcast (0 => it never redirected:
        # delayed/defended), used as the leak signal
        xmit_redirect = xmit_squashes[0] if xmit_squashes else 0
        xmit_signal   = xmit_redirect
        branch_redirected = (xmit_redirect > 0
                             and (ft_rec is None or ft_rec.get("retire", 0) == 0))
    else:
        xmit_redirect = 0
        xmit_signal   = xmit_complete
        branch_redirected = (
            ft_rec is not None
            and xmit_rec is not None
            and xmit_complete > 0
            and ft_rec.get("retire", 0) == 0
        )

    # Dual condition: all *other* unresolved branches in the annotation must
    # still be unresolved at the moment the xmit branch propagates its redirect.
    # process_one already excluded xmit_pc.
    lc_retire     = lc_rec["retire"]  if lc_rec  else 0
    fnc_retire    = fnc_rec["retire"] if fnc_rec else 0
    fnc_complete  = fnc_rec["complete"] if fnc_rec else 0

    # Mirror check_ld: lc must actually retire if specified; xmit redirect must
    # land in the (lc_retire, fnc_retire) speculation window.
    lc_unretired_but_specified = (lc_pc is not None) and (lc_retire == 0)
    disqualified = lc_unretired_but_specified

    after_lc   = (lc_retire == 0)  or (xmit_signal > lc_retire)
    before_fnc = (fnc_retire == 0) or (xmit_signal < fnc_retire)

    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, xmit_signal, unresolved, ticks_per_cycle)

    issued_in_window = (not disqualified
                        and branch_redirected
                        and (xmit_signal > 0) and after_lc and before_fnc
                        and branches_unresolved)

    return dict(
        issued_in_window=issued_in_window,
        xmit_signal=xmit_signal,
        xmit_complete=xmit_complete,
        xmit_redirect=xmit_redirect,
        xmit_last_alive=xmit_last_alive,
        ft_last_alive=ft_last_alive,
        ft_pc=hex(ft_pc) if ft_pc else None,
        lc_retire=lc_retire,
        lc_unretired_but_specified=lc_unretired_but_specified,
        fnc_retire=fnc_retire,
        fnc_complete=fnc_complete,
        branches_unresolved=branches_unresolved,
        branch_resolutions=branch_details,
    )


if __name__ == "__main__":
    run_batch(check_br, description="branch transmitter: xmit outlives fall-through")
