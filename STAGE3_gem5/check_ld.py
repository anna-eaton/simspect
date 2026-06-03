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


def _xmit_cache_fate(lsq_by_pc, xmit_pc):
    """Secondary cache-reach classification for the xmit load, read from the
    SAME LSQUnit trace (no gem5 re-run): "Executing load" fires at the top of
    the load path, before the defense decides whether to expose the access. A
    load is only a real leak if it actually sent a read packet to cache
    (reached_cache); a delay_unit bounce (executed_no_packet) or invisible spec
    read (spec_read_only) is a check_ld false positive. Touching cache is the
    leak even if the load is later squashed (squash tick is informative only,
    NOT a disqualifier).

    Returns None when there is no LSQ record for xmit_pc (e.g. a build without
    LSQUnit logging, where check_ld fell back to pipeview) — caller then leaves
    the verdict ungated rather than risk hiding a real leak.
    """
    recs = (lsq_by_pc or {}).get(xmit_pc, [])
    if not recs:
        return None
    executed = [r for r in recs if r.get("execute_tick", 0) > 0]
    if not executed:
        return dict(cache_fate="never_executed", real_access=False,
                    packet_tick=0, spec_read_tick=0, load_squash_tick=0)
    reached = [r for r in executed if r.get("packet_tick", 0) > 0]
    if reached:
        r = min(reached, key=lambda r: r["packet_tick"])
        return dict(cache_fate="reached_cache", real_access=True,
                    packet_tick=r["packet_tick"], spec_read_tick=0,
                    load_squash_tick=r.get("squash_tick", 0))
    specd = [r for r in executed if r.get("spec_read_tick", 0) > 0]
    if specd:
        r = min(specd, key=lambda r: r["spec_read_tick"])
        return dict(cache_fate="spec_read_only", real_access=False,
                    packet_tick=0, spec_read_tick=r["spec_read_tick"],
                    load_squash_tick=r.get("squash_tick", 0))
    r = executed[0]
    return dict(cache_fate="executed_no_packet", real_access=False,
                packet_tick=0, spec_read_tick=0,
                load_squash_tick=r.get("squash_tick", 0))


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
    in_window = (not disqualified
                 and (xmit_signal > 0) and after_lc and before_fnc
                 and branches_unresolved)

    # Secondary "data-obtained" gate (no gem5 re-run; reads the same LSQ trace).
    # A load leaks if it OBTAINED its data in the window — by either:
    #   reached_cache       a real read packet went to cache, OR
    #   store_forward (SLF) executed, no packet, but reached pipeview 'complete'
    #                       (its value was forwarded from a store in the LSQ).
    # False positives (NOT leaks):
    #   executed_no_packet & never completed → delay_unit bounce (defense held)
    #   spec_read_only                        → invisible spec read (hidden fill)
    #   never_executed
    # NB cache reach is NOT the bar — SLF leaks without ever touching cache.
    # squash timing NEVER gates: a load that obtained data then got squashed
    # still leaked. Applied only to in-window hits scored via the LSQ path
    # (xmit_execute > 0) with LSQ records present; otherwise left ungated so we
    # never hide a possible real leak on a build without LSQ logging.
    fate = _xmit_cache_fate(lsq_by_pc, xmit_pc)
    cache_fate = (fate or {}).get("cache_fate")
    if fate is None:
        data_obtained = None
    elif cache_fate == "reached_cache":
        data_obtained = True
    elif cache_fate == "spec_read_only":
        data_obtained = False
    elif cache_fate == "executed_no_packet":
        data_obtained = xmit_complete > 0            # SLF forward-completion
        if data_obtained:
            cache_fate = "store_forward"
    else:                                            # never_executed
        data_obtained = False

    gated = in_window and (xmit_execute > 0) and (data_obtained is not None)
    issued_in_window = (bool(data_obtained) if gated else in_window)

    return dict(
        issued_in_window=issued_in_window,
        in_window=in_window,
        data_obtained=data_obtained,
        cache_fate=cache_fate,
        real_access=(fate or {}).get("real_access"),
        packet_tick=(fate or {}).get("packet_tick"),
        spec_read_tick=(fate or {}).get("spec_read_tick"),
        load_squash_tick=(fate or {}).get("load_squash_tick"),
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
