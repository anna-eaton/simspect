#!/usr/bin/env python3
"""
check_ld_speclfb.py — load transmitter checker for the SpecLFB defense.

WHY A SEPARATE CHECKER (do not use check_ld.py for SpecLFB):
SpecLFB runs on a NEWER gem5 base whose LSQ trace differs from the STT/recon/
InvisiSpec base. There is no "successfully sent out packet(s)" line, so check_ld's
data-obtained gate misfires (it falls back to the pipeview-complete heuristic and
reports spurious store_forward hits). On this base the load's real cache access is
logged as "Doing memory access for inst [sn:N]" (lsq_unit.cc:1766), emitted by
LSQUnit::read() right before issuing the request and ONLY when the load is NOT
store-forwarded. parse_lsq captures it as `memaccess_tick`.

SpecLFB delays unsafe speculative loads (`isSpeclfbStalled`): a PROTECTED load is
stalled BEFORE reaching the cache-access path, so it does not do a memory access
in the speculative window (it either accesses after resolution or is squashed
first). The AMuLeT UV6 bug is that the FIRST speculative load in the LSQ has its
protection cleared (`isReallyUnsafe` cleared) — so it is NOT stalled and installs
a secret-dependent line into the cache WHILE SPECULATIVE.

LEAK CRITERION (the UV6 cache channel): the transmitter load issues its cache
access in the speculative window:

    lc_retire < memaccess_tick < fnc_retire   AND   guarding branches unresolved

A correctly-protected load yields issued_in_window=False (no in-window memory
access); an unprotected (UV6) load yields True.

NB store-forwarding (SLF): a load satisfied from the store queue never reaches
"Doing memory access" (the forwarding case returns earlier). SLF is a non-cache
channel outside SpecLFB's stated scope (it appears under unsafebaseline too), so
it is surfaced as a diagnostic (`store_forward_in_window`) but does NOT set the
primary issued_in_window verdict. The cache channel (memaccess) is the UV6 test.
"""

from gem5_common import best_record, check_branch_resolutions, run_batch


def _max_field(lsq_by_pc, xmit_pc, field):
    recs = (lsq_by_pc or {}).get(xmit_pc, [])
    return max((r.get(field, 0) for r in recs), default=0)


def check_ld_speclfb(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved,
                     ticks_per_cycle, lsq_by_pc=None, squash_by_pc=None):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    # The transmit = the load's cache access (UV6 channel).
    memaccess_tick = _max_field(lsq_by_pc, xmit_pc, "memaccess_tick")
    execute_tick   = _max_field(lsq_by_pc, xmit_pc, "execute_tick")
    load_squash    = _max_field(lsq_by_pc, xmit_pc, "squash_tick")
    has_lsq_rec    = bool((lsq_by_pc or {}).get(xmit_pc))
    # SpecLFB classification (Speclfb debug flag). spec_cusl: the xmit load is a
    # genuine conditional USL (should be protected). spec_unprotected: SpecLFB
    # left it UNPROTECTED (isUnsafe=0 = UV6) → its fill installs in L1; a
    # protected (isUnsafe=1) load's fill is LFB-held (no in-window install), so
    # memaccess-in-window alone is NOT a leak for it.
    recs = (lsq_by_pc or {}).get(xmit_pc, [])
    spec_cusl       = any(r.get("spec_cusl") for r in recs)
    spec_unprotected = any(r.get("spec_unprotected") for r in recs)

    xmit_signal  = memaccess_tick
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    xmit_issue   = xmit_rec["issue"]  if xmit_rec else 0
    xmit_retire  = xmit_rec["retire"] if xmit_rec else 0
    lc_retire    = lc_rec["retire"]   if lc_rec   else 0
    fnc_retire   = fnc_rec["retire"]  if fnc_rec  else 0
    fnc_complete = fnc_rec["complete"] if fnc_rec else 0

    lc_unretired_but_specified = (lc_pc is not None) and (lc_retire == 0)
    disqualified = lc_unretired_but_specified

    after_lc   = (lc_retire == 0) or (xmit_signal > lc_retire)
    before_fnc = (fnc_retire == 0) or (xmit_signal < fnc_retire)
    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, xmit_signal, unresolved, ticks_per_cycle)

    # LEAK iff: the load issued a cache access in the speculative window AND
    # SpecLFB left it unprotected (isUnsafe=0 = UV6) so the line actually installs
    # in L1. A protected (LFB-held) load can also do memaccess in-window but does
    # NOT install — so spec_unprotected gates out that over-approximation.
    cache_in_window = (not disqualified
                       and (memaccess_tick > 0) and after_lc and before_fnc
                       and branches_unresolved)
    in_window = cache_in_window and spec_unprotected
    issued_in_window = in_window

    # Diagnostic: store-forward in-window (non-cache channel, not the UV6 verdict).
    sf_after_lc   = (lc_retire == 0) or (xmit_complete > lc_retire)
    sf_before_fnc = (fnc_retire == 0) or (xmit_complete < fnc_retire)
    sf_unresolved, _ = check_branch_resolutions(
        by_pc, xmit_complete, unresolved, ticks_per_cycle)
    store_forward_in_window = (memaccess_tick == 0 and execute_tick > 0
                               and xmit_complete > 0
                               and sf_after_lc and sf_before_fnc and sf_unresolved)

    if not has_lsq_rec:
        outcome = "no_lsq_record"
    elif execute_tick == 0:
        outcome = "load_never_executed"
    elif memaccess_tick == 0:
        outcome = ("store_forward_in_window" if store_forward_in_window
                   else ("protected_squashed" if load_squash > 0
                         else "protected_no_cache_access"))
    elif cache_in_window and spec_unprotected:
        outcome = "cache_access_in_window"        # UV6 LEAK (unprotected USL installs in L1)
    elif cache_in_window and spec_cusl:
        outcome = "protected_lfb_access"          # USL accessed in-window but LFB-held (no install)
    elif cache_in_window:
        outcome = "cache_access_in_window_nonusl" # accessed in-window but not flagged a USL
    else:
        outcome = "accessed_after_resolution"     # defense worked

    return dict(
        issued_in_window=issued_in_window,
        in_window=in_window,
        outcome=outcome,
        xmit_signal=xmit_signal,
        memaccess_tick=memaccess_tick,
        cache_accessed=(memaccess_tick > 0),
        cache_in_window=cache_in_window,
        spec_cusl=spec_cusl,
        spec_unprotected=spec_unprotected,
        store_forward_in_window=store_forward_in_window,
        xmit_execute=execute_tick,
        load_squash_tick=load_squash,
        xmit_issue=xmit_issue,
        xmit_complete=xmit_complete,
        xmit_retire=xmit_retire,
        xmit_retired_in_window=(xmit_retire > 0),
        lc_retire=lc_retire,
        lc_unretired_but_specified=lc_unretired_but_specified,
        fnc_retire=fnc_retire,
        fnc_complete=fnc_complete,
        branches_unresolved=branches_unresolved,
        branch_resolutions=branch_details,
    )


if __name__ == "__main__":
    run_batch(check_ld_speclfb,
              description="SpecLFB load transmitter: cache access (Doing memory "
                          "access) in (lc_retire, fnc_retire) = UV6 leak")
