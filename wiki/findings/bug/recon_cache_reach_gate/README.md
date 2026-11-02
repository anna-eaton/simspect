# check_ld's data-obtained gate can't see a real cache send on the Recon builds

*Found 2026-10-30 by the `stl-spec` session while testing the STL hooks. Not fixed: changing the canonical gate changes how past recon results read, so it needs Anna's call.*

## Claim

On `/work/gem5-recon` and `/work/gem5-recon-modded` (and the `gem5-recon-stl` copy), `check_ld._xmit_cache_fate` never returns `reached_cache`. The line it keys on, `successfully sent out packet(s) for inst [sn:N]`, does not exist in those builds' source. Every executed load is classified `executed_no_packet`. check_ld then calls it a leak only if the transmitter PC has a pipeview `complete` tick (relabelled `store_forward`). So a speculative load that really sent a read packet but was squashed before it completed is scored **not a leak**. On these builds the gate can hide real leaks and mislabels the ones it keeps.

## Evidence

- `grep -rl "successfully sent out packet" <build>/src/cpu/o3`: none in `/work/gem5-recon` or `/work/gem5-recon-modded`; present in `/work/stt` and `/work/gem5-spt` (`lsq_unit.hh`).
- Recon's send print is `Memory request (pkt: %s) from inst [sn:%llu] was %ssent (...)` at `src/cpu/o3/lsq_unit.cc:1546` (`was sent` vs `was not sent`).
- `Doing memory access for inst [sn:N]` (`lsq_unit.cc:2077`) is not a send either: STT's delay unit bounces a tainted load after it (`lsq_unit.cc:2104` `insertTaintedLoad`). Trace `inst-000006` (STT_6_stl, scheme 2): sn 563 logs `Doing memory access` then `Inserted tainted load [sn:563] into delay_unit`, and no `Memory request ... was sent`.
- Unsafe (scheme 0) run of 60 STT_6_stl tests on gem5-recon-stl: all 28 load transmitters log `Memory request ... was sent`, and `_xmit_cache_fate` labels all 28 `executed_no_packet`. Results: cafe2 `results/STT_6_stl_hooktest/controls/stl_B_unsafe.json` (`x_fate` vs `x_mem`).

## Mechanism

`gem5_common.parse_lsq` sets `packet_tick` only from `successfully sent out packet(s)`. `check_ld` (`STAGE3_gem5/check_ld.py:130-142`): `executed_no_packet` → `data_obtained = xmit_complete > 0`. `xmit_complete` comes from pipeview by PC, and a squashed in-flight load often has no pipeview record. The 2026-06-02 claudelog entry ("`executed_no_packet` (recon/DoM delay_unit bounce = FP)") assumed the packet line exists on recon builds.

## Verdict

Checker bug (SimSpect pipeline), not a gem5 bug. Scope: every check_ld result on gem5-recon / gem5-recon-modded where the gate applied (in-window, LSQ records present).

## Fix (proposed, not applied)

Add to `parse_lsq` a regex for `Memory request \(pkt: .*\) from inst \[sn:(\d+)\] was sent ` that sets `packet_tick` when it is still 0. This is additive: builds that print the old line are unchanged. Then re-score recon results (the hits the gate dropped as `executed_no_packet & never completed` are the ones to recheck). `gem5-hooks/stl/stl_hooktest.py:sent_tick` already uses this signal.
