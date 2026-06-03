# Recon/STT SLF (store-to-load forwarding) taint-check bypass

**Verdict: REAL gem5 defense bug** on the recon-modded STT build (`/work/gem5-recon-modded`,
`--scheme=2` STT). A tainted *speculative* load obtains its data via store-to-load forwarding
**before** the STT taint check can hold it — so a load whose address is speculative (tainted)
completes and makes its value available inside the speculative window.

Representative instance: **`inst-014912`** (campaign `results/Recon_6__20260602_122016`,
`mispredict_not_taken`, `ld`). Full provenance in `provenance.json`.

## The gadget (concretized asm — see `inst-014912.s`)

```
pc0 (last_committed):  idivq ...            # TOther → %rax  (committed)
pc1 (first_noncommitted): xorq %rdx,%rdx; jne   # mispredicted branch (unresolved)
pc2:  movq $1,%rdx; jne ; leaq 40(%rsp),%rsi
pc3:  movq (%rsi), %rax                     # speculative load → %rax  (TAINTED address source)
      leaq 64(%rsp), %rsi
pc4:  movq %rdi, (%rsi,%rax)                # STORE to addr 64(%rsp)+%rax
pc5:  movq (%rsi,%rax), %r12                # XMIT LOAD from the IDENTICAL addr 64(%rsp)+%rax
```

pc4 and pc5 address the **same** location `(%rsi,%rax)`; the address index `%rax` comes from the
speculative load pc3, so the xmit load's address is tainted+speculative. Under STT this load must be
delayed until the branch resolves. Instead the LSQ forwards pc4's store data to pc5 and returns it
before the taint check fires.

## Evidence (gem5 LSQ/Commit trace, faithful run — `trace_excerpt_sn600.txt`)

```
2681500  Executing store [sn:599]  +  Executing load [sn:600]
2681500  STL_CHECK: load PC 0x401c7c isTainted=1 isSpeculative=1
2682500  Marking [sn:600] ready within ROB        <-- xmit load COMPLETED (data obtained)
2683500  Load Instruction ... squashed [sn:600]    <-- squash comes 1000 ticks LATER
```

The tainted speculative load is marked **ready within ROB** (its result is available) at 2682500,
1000 ticks **before** its squash. The leak is the *completion*, not a cache packet — this load never
sends a cache packet (the value is store-forwarded), which is why a cache-reach/"sent packet" test
does NOT detect it. The correct leak criterion is **"data obtained (completes) before squash while
tainted+speculative"**, now implemented in `check_ld` as the `store_forward` / data-obtained gate.

## Reproduce (EXACTLY as the campaign — stalls matter)

```bash
# build + run inst-014912 with the campaign's config, injecting the sweep stalls
python3 STAGE3_gem5/check_ld.py <dir with inst-014912.{s,ann.json}> \
    --scheme 2 --jobs 1 --out slf.json
# env / flags must mirror results/Recon_6/run_config.jsonc:
#   SIMSPECT_GEM5_BIN=/work/gem5-recon-modded/build/X86/gem5.opt
#   SIMSPECT_SE_CONFIG=/work/gem5-recon-modded/configs/example/se.py
#   SIMSPECT_GEM5_CPU=X86O3CPU  SIMSPECT_ALLOW_LEAKED=1  SIMSPECT_BRANCH_ANN_ENABLE=1
#   and the .ann.json must carry resolve_stall_cycles (unresolved=5000) — inject via
#   pipeline._inject_stalls, else the speculative window collapses and it won't reproduce.
```

## Scope note

This is the only confirmed real leak among the 184 ld hits of `Recon_6__20260602_122016`; the other
183 are `check_ld` false positives (load executed but bounced to delay_unit and squashed without
completing). The classifier `diag_recon_load_hits.py` also flagged 3 "OTB" instances — those are
NOT real OTB (abstract-opstate false matches; see `bug/` catalog and `OTB_GENERATION_GAP.md`).
