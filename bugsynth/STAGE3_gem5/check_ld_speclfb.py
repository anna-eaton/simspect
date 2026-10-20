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

LEAK CRITERION (the UV6 cache channel): the transmitter load installs a line in
L1 (a cache MISS / fill — the actual secret-dependent cache-state perturbation)
in the speculative window:

    lc_retire < cache_fill_tick < fnc_retire   AND   branches unresolved
                                               AND   SpecLFB left it unprotected

This is the actual-install signal (Cache debug flag), NOT the bare "Doing memory
access" tick. A load logs the memaccess and then the dcache reports hit/miss;
parse_lsq pairs them and records cache_fill_tick only on a MISS. Re-keying on the
install (rather than memaccess) gates out the const-addr over-approximation: a
load that accesses in-window but HITS a pre-warmed constant line changes no L1
tag state, so it is `access_hit_in_window_no_install`, NOT a leak. A correctly
protected load is stalled before any access (issued_in_window=False); an
unprotected (UV6) load that misses+installs in-window yields True.

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

    # The transmit = the load's L1 line INSTALL (a cache miss/fill), the real
    # cache-state perturbation. memaccess_tick (the bare access) is kept as a
    # diagnostic; cache_fill_tick (set only on a MISS) is the leak signal.
    memaccess_tick = _max_field(lsq_by_pc, xmit_pc, "memaccess_tick")
    cache_fill_tick = _max_field(lsq_by_pc, xmit_pc, "cache_fill_tick")
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

    xmit_signal  = cache_fill_tick or memaccess_tick   # install if it missed, else access
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    xmit_issue   = xmit_rec["issue"]  if xmit_rec else 0
    xmit_retire  = xmit_rec["retire"] if xmit_rec else 0
    lc_retire    = lc_rec["retire"]   if lc_rec   else 0
    fnc_retire   = fnc_rec["retire"]  if fnc_rec  else 0
    fnc_complete = fnc_rec["complete"] if fnc_rec else 0

    lc_unretired_but_specified = (lc_pc is not None) and (lc_retire == 0)
    disqualified = lc_unretired_but_specified

    # Leak window keyed on the INSTALL tick (cache miss/fill). Branch-resolution
    # and lc/fnc bounds are evaluated at that tick.
    after_lc   = (lc_retire == 0) or (cache_fill_tick > lc_retire)
    before_fnc = (fnc_retire == 0) or (cache_fill_tick < fnc_retire)
    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, cache_fill_tick, unresolved, ticks_per_cycle)

    # LEAK iff: the load INSTALLED a line in L1 (a cache miss/fill) in the
    # speculative window AND SpecLFB left it unprotected (isUnsafe=0 = UV6). A
    # load that merely accesses in-window but HITS a pre-warmed constant line
    # installs nothing (const-addr over-approximation) → not a leak.
    install_in_window = (not disqualified
                         and (cache_fill_tick > 0) and after_lc and before_fnc
                         and branches_unresolved)
    in_window = install_in_window and spec_unprotected
    issued_in_window = in_window

    # Diagnostic: the bare access (memaccess) fell in-window but the load HIT
    # (no install) — the const-addr over-approximation the install gate removes.
    ma_after_lc   = (lc_retire == 0) or (memaccess_tick > lc_retire)
    ma_before_fnc = (fnc_retire == 0) or (memaccess_tick < fnc_retire)
    ma_unresolved, _ = check_branch_resolutions(
        by_pc, memaccess_tick, unresolved, ticks_per_cycle)
    access_in_window = ((memaccess_tick > 0) and ma_after_lc and ma_before_fnc
                        and ma_unresolved)

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
    elif install_in_window and spec_unprotected:
        outcome = "cache_install_in_window"       # UV6 LEAK (unprotected USL misses+installs in L1)
    elif install_in_window and spec_cusl:
        outcome = "protected_lfb_install"         # USL installed in-window but LFB-held (rare)
    elif install_in_window:
        outcome = "cache_install_in_window_nonusl"
    elif access_in_window:
        outcome = "access_hit_in_window_no_install"  # const-addr over-approx: accessed but HIT (no install)
    else:
        outcome = "accessed_after_resolution"     # defense worked / accessed post-resolution

    return dict(
        issued_in_window=issued_in_window,
        in_window=in_window,
        outcome=outcome,
        xmit_signal=xmit_signal,
        memaccess_tick=memaccess_tick,
        cache_fill_tick=cache_fill_tick,
        cache_accessed=(memaccess_tick > 0),
        cache_installed=(cache_fill_tick > 0),
        install_in_window=install_in_window,
        access_in_window=access_in_window,
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
              description="SpecLFB load transmitter: L1 line INSTALL (cache miss) "
                          "in (lc_retire, fnc_retire) = UV6 leak")
