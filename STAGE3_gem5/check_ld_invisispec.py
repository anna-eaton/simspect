#!/usr/bin/env python3
"""
check_ld_invisispec.py — load transmitter checker for the InvisiSpec defense.

WHY A SEPARATE CHECKER (do not use check_ld.py for InvisiSpec):
Under STT/SPT/recon a load has ONE cache access and that access IS the
transmit, so check_ld keys the leak on the LSQ "Executing load" tick. InvisiSpec
gives a USL TWO memory accesses (paper §V-B, Fig.2):

  1. Spec read  — `ReadSpecReq` (Spec-GetS) issued at addr-resolve while the
     load is still an Unsafe Speculative Load. It fills only the Speculative
     Buffer and is INVISIBLE to the cache hierarchy by design. In the trace it
     is "send a spec read for inst [sn:N]" (lsq_unit.hh) and STILL produces
     "successfully sent out packet(s)" (lsq_unit.hh:1021) + "Executing load".
     => check_ld would see packet_tick>0 and FALSE-POSITIVE on every USL.
  2. Validate / Expose — the cache-MODIFYING access, issued only at the
     load's VISIBILITY POINT (for IS-Spectre: when all prior branches resolve;
     gated by readyToExpose(), set in lsq_unit_impl.hh:updateVisibleState()).
     In the trace it is "Validate/Expose request for inst [sn:N]"
     (lsq_unit_impl.hh:1190/1200), parsed by gem5_common.parse_lsq into
     `expose_tick`. The packet is sent at lsq_unit_impl.hh:1280. THIS is the
     transmit.

LEAK CRITERION (faithful to InvisiSpec): the transmitter load made a VISIBLE
cache access (expose/validate) while still speculative — i.e. its expose_tick
falls in the speculative window:

    lc_retire < expose_tick < fnc_retire   AND   guarding branches unresolved
                                                 at expose_tick

By construction InvisiSpec defers the expose to branch resolution, so a
correctly-working build yields issued_in_window=False everywhere (this run is a
DEFENSE-VALIDATION / negative control). A hit means an expose fired before its
guarding branch resolved — an InvisiSpec/hook bug, the research signal.

The invisible spec read (spec_read_tick) and its packet (packet_tick) are
surfaced for diagnosis but NEVER gate the leak: a spec read in-window is the
EXPECTED, harmless behaviour of a USL. NB this checker tests "expose-in-window"
from the trace; it ASSUMES the Ruby Spec-GetS is genuinely invisible (a coherence
-protocol property). Confirming spec-read invisibility would need a cache-state
diagnostic — out of scope for a trace checker; see the run's README.

Usage (env mirrors the InvisiSpec run_config — see results/STT_6_invisispec/):
    SIMSPECT_GEM5_BIN=.../build/X86_MESI_Two_Level/gem5.opt \
    SIMSPECT_SE_CONFIG=.../configs/example/se.py \
    SIMSPECT_GEM5_CPU=DerivO3CPU SIMSPECT_BRANCH_ANN_ENABLE=1 \
    SIMSPECT_GEM5_EXTRA="--scheme=SpectreSafeInvisibleSpec"$'\x1f'"--needsTSO=1" \
    python3 check_ld_invisispec.py <dir-with-.s-and-injected-.ann.json> --jobs 8 --out out.json
"""

from gem5_common import best_record, check_branch_resolutions, run_batch


def _max_field(lsq_by_pc, xmit_pc, field):
    recs = (lsq_by_pc or {}).get(xmit_pc, [])
    return max((r.get(field, 0) for r in recs), default=0)


def check_ld_invisispec(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved,
                        ticks_per_cycle, lsq_by_pc=None, squash_by_pc=None):
    xmit_rec = best_record(by_pc.get(xmit_pc, []))
    lc_rec   = best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    # The transmit = the cache-modifying expose/validate at the visibility point.
    expose_tick   = _max_field(lsq_by_pc, xmit_pc, "expose_tick")
    # Diagnostics (the invisible spec read; never gates the verdict).
    spec_read_tick = _max_field(lsq_by_pc, xmit_pc, "spec_read_tick")
    execute_tick   = _max_field(lsq_by_pc, xmit_pc, "execute_tick")
    packet_tick    = _max_field(lsq_by_pc, xmit_pc, "packet_tick")
    load_squash    = _max_field(lsq_by_pc, xmit_pc, "squash_tick")
    has_lsq_rec    = bool((lsq_by_pc or {}).get(xmit_pc))

    xmit_signal = expose_tick

    xmit_issue  = xmit_rec["issue"]  if xmit_rec else 0
    xmit_retire = xmit_rec["retire"] if xmit_rec else 0
    lc_retire   = lc_rec["retire"]   if lc_rec   else 0
    fnc_retire  = fnc_rec["retire"]  if fnc_rec  else 0
    fnc_complete = fnc_rec["complete"] if fnc_rec else 0

    # Same disqualifier as check_ld: a specified last-committed predecessor that
    # never retires means the test didn't behave as the model claims.
    lc_unretired_but_specified = (lc_pc is not None) and (lc_retire == 0)
    disqualified = lc_unretired_but_specified

    after_lc   = (lc_retire == 0) or (xmit_signal > lc_retire)
    before_fnc = (fnc_retire == 0) or (xmit_signal < fnc_retire)
    branches_unresolved, branch_details = check_branch_resolutions(
        by_pc, xmit_signal, unresolved, ticks_per_cycle)

    # LEAK iff a cache-modifying expose/validate fired in the speculative window.
    in_window = (not disqualified
                 and (expose_tick > 0) and after_lc and before_fnc
                 and branches_unresolved)
    issued_in_window = in_window

    # Diagnostic: was the (invisible) spec read in-window? Expected True for a
    # genuine USL — confirms the test actually exercised speculative execution.
    spec_read_after_lc  = (lc_retire == 0) or (spec_read_tick > lc_retire)
    spec_read_before_fnc = (fnc_retire == 0) or (spec_read_tick < fnc_retire)
    sr_unresolved, _ = check_branch_resolutions(
        by_pc, spec_read_tick, unresolved, ticks_per_cycle)
    spec_read_in_window = (spec_read_tick > 0 and spec_read_after_lc
                           and spec_read_before_fnc and sr_unresolved)

    if not has_lsq_rec:
        outcome = "no_lsq_record"        # build w/o LSQUnit logging; ungated
    elif execute_tick == 0:
        outcome = "load_never_executed"  # defense: USL never even read
    elif expose_tick == 0:
        # The load did its invisible spec read but was squashed before its
        # visibility point — InvisiSpec prevented the leak.
        outcome = ("never_exposed_squashed" if load_squash > 0
                   else "never_exposed")
    elif in_window:
        outcome = "exposed_in_window"    # LEAK — expose before resolution
    else:
        outcome = "exposed_after_resolution"  # defense worked

    return dict(
        issued_in_window=issued_in_window,
        in_window=in_window,
        outcome=outcome,
        xmit_signal=xmit_signal,
        expose_tick=expose_tick,
        exposed=(expose_tick > 0),
        spec_read_tick=spec_read_tick,
        spec_read_in_window=spec_read_in_window,
        xmit_execute=execute_tick,
        packet_tick=packet_tick,
        load_squash_tick=load_squash,
        xmit_issue=xmit_issue,
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
    run_batch(check_ld_invisispec,
              description="InvisiSpec load transmitter: expose/validate "
                          "(NOT spec read) in (lc_retire, fnc_retire)")
