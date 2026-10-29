# InvisiSpec flagged-event triage (check_footprint, 2026-10-28)

Audit only: no code or spec edits, no gem5 runs, no git writes. I re-ran `check_footprint.evaluate_trace` locally on the gzipped fixtures `STAGE3_gem5/tests/fixtures/inv_uv1.*` (SpectreSafeInvisibleSpec, actor `spec`) and `inv_fut.*` (FuturisticSafeInvisibleSpec, actor `futuristic`) with `specs/leakage/invisispec.json`. The trace lines quoted below are from those fixtures, with the `O3PipeView:simspect:` prefix removed. The audit was time-boxed to 12 minutes, and the items marked OPEN were not checked.

## Verdicts

| Event class | Verdict | One-line reason |
|---|---|---|
| `DTLB:repl_touch` by a squashed load (spec mode) | **REAL deviation, but a known gap in the implementation's scope** | The paper delays D-TLB replacement updates on a hit to the visibility point. `tlb.cc` updates `lruSeq` on every hit. |
| `DTLB:fill` / `repl_touch` early in inv_fut (Futuristic mode) | **CHECKER ARTIFACT** | The flagged seqs are store micro-ops. The Futuristic actor does not filter for loads. |
| `L2:coh` after an `L1D:evict` (both modes) | **REAL, but the same root cause as the UV1 L1D eviction** | This is the L2 acting on the L1's writeback of the victim. Attribution is correct; it is not a separate bug. |
| `DIR:coh` (+ `L1D:fill`, `L2:fill`) on 0x3d40, seq 532 (Futuristic) | **CHECKER ARTIFACT (the paper allows the behavior)** | seq 532 is a store micro-op with no pipeview record, so its visibility point became infinite. The fill is a normal fetch that ends with the directory in M. |
| `DIR:coh` on an ifetch line (seq=-) | Paper allows it, and the checker ignores it | The event is unattributed, and instruction-side state is out of scope (footnote 2). |
| `dir.sm:499-503` `transition(M,{Fetch,Expose,SpecFetch})` → `inv_sendCacheInvalidate` | **Possible REAL deviation, not seen in these traces (OPEN)** | A Spec-GetS that reaches the directory in M sends an invalidation, which changes state. That conflicts with §VI-E1. |

## 1. DTLB:repl_touch — REAL deviation from the paper (known implementation gap)

What the paper says. Yan et al. 2018, §VI-E3, p9–10 (`~/Documents/quail/sources/papers/yan-2018-invisispec.pdf`, pdftotext lines 632–643): "To prevent a USL from observably changing the D-TLB state … First, on a D-TLB miss, it delays serving it via a page table walk until the USL reaches the point of visibility … Second, on a D-TLB hit, any observable TLB state changes such as updating D-TLB replacement state or access/dirty bits are delayed to the USL's point of visibility." The paper does not allow replacement updates on a speculative TLB hit.

What the source does. In the InvisiSpec source (cafe2 `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1/src/arch/x86/tlb.cc`, `TLB::lookup`, around lines 146–150), the code runs `if (entry && update_lru) { entry->lruSeq = nextSeq(); … }` with no check for a USL. The hook prints only at that point. AMuLeT also treats the TLB as unprotected and uses a 1-page sandbox "as the TLB is not protected" (AMuLeT §3.5 p7, cited in `specs/leakage/invisispec.json` under `amulet_checks`).

Attribution is reliable here. The hook takes the TLB context from `setTlbCtx(req->getReqInstSeqNum())` in the same synchronous translate call (`simspect_hooks.diff` lines 88–92). It does not use the per-line map.

Trace evidence (inv_uv1). The window is lc_retire=3161000 to fnc_retire=5663500. seqs 566, 573 and 576 are loads that never retired: `ld rdx,[r8]`, `ld r10,[rdx+r8]` and `POP_R ldis t1,SS:[rsp]`, all with `retire:0`.
```
3161500:DTLB:repl_touch:line=0x7fffffffe000:seq=579:pc=0x401c76:...:id=1299
3162000:DTLB:repl_touch:line=0x7fffffffe000:seq=582:pc=0x401c77:...:id=1300
3177500:DTLB:repl_touch:line=0x7fffffffe000:seq=573:pc=0x401c6a:...:id=1313
```
Severity and caveat. The touched entry is the stack page, which committed code also touches all the time. The event updates replacement state only (no fill or evict), so it only becomes observable after a later TLB eviction. Recommendation: put these in a separate bucket, "InvisiSpec artifact does not implement §VI-E3 D-TLB hit protection (known, AMuLeT-acknowledged)", so they do not hide new findings. OPEN: whether the D-TLB miss delay (the first half of §VI-E3) is implemented. These fixtures contain no DTLB fill by a squashed load to show it either way.

## 2. DTLB events early in inv_fut — CHECKER ARTIFACT (actor over-approximation)

The Futuristic offending group lists `DTLB` fill and repl_touch events starting at id 16. The seqs are store micro-ops. For example, `fetch:75000:0x00401000:2:3: CALL_NEAR_I : stis t7, SS:[rsp-8]` is seq 3 (`78000:DTLB:fill:…:seq=3:…:id=16`), and `fetch:80500:0x00401024:0:25: PUSH_R : stis r15,…` is seq 25 (`id=42`).

`check_footprint.py:226-227` (`actor_event_in_window`) together with `is_actor` returning `True` for `before_visibility_point` (around line 221) counts every instruction as an actor. The spec's own text says "Futuristic USL = every squashable load" (`invisispec.json` `actors.modes.futuristic.text`). §VI-E3 protects only USLs, which are loads, so store translations are outside the paper's protection. Fix to propose to Anna (not applied): require the actor in Futuristic mode to be a load, using the pipeview disasm or `ld`/`ldis` micro-ops.

## 3. L2:coh — REAL coherence change, but a consequence of the UV1 L1D eviction (not a separate class)

Every flagged `L2:coh` comes right after an `L1D:evict` with the same seq and `victim` equal to the coh line. inv_uv1 shows the same pattern three times:
```
3161000:L1D:evict:line=0x3540:seq=566:...:victim=0x3b40:cause=1296:...:id=1297
3165000:L2:coh:line=0x3b40:seq=566:pc=0x401c5a:...:id=1303
3176500:SB:buf_fill:line=0x3540:seq=566:...:id=1306        # data goes to the SB only, so 0x3540 is never installed
3176500:L1D:evict:line=0x3dc0:seq=576:...:victim=0x39c0:...:id=1310
3180500:L2:coh:line=0x39c0:seq=576:...:id=1314
3192000:L1D:evict:line=0x3580:seq=573:...:victim=0x3980:...:id=1321
3196000:L2:coh:line=0x3980:seq=573:...:id=1328
```
Mechanism. The L1 evicts a victim to make room for a USL's Spec-GetS, but the incoming line goes only to the SB. That is the UV1 eviction (`test_check_footprint.py:304` `test_uv1_offending_is_the_spec_eviction`). The victim's writeback or PUT then changes the L2's stable state for that line, which is the `coh` hook (`simspect_hooks.diff` ~476–486: stable→stable change, present before and after, no tag change). For an L1-owned line this is most likely MT→M. I did not check the exact state names against L2cache.sm.

Could a committed instruction have been misattributed? Not in these cases. The L2 transition runs on a message, not a CPU request, so `attr()` reads the per-line map (`getLineAttr`). The `Replacement` branch of `onCacheDeallocate` sets that map entry for the victim line to the evicting seq (`simspect_hooks.diff` ~531, `setLineAttr(line, seq, pc)`). Between each evict and its coh (about 4000 ticks), no other event touches 0x3b40, 0x39c0 or 0x3980, so the entry still belongs to the squashed USL. In general the map can go stale, because other `setLineAttr` sites (diff lines 581 and 585) could overwrite it. A diagnostic should still require "a preceding L1D:evict with victim==line and the same seq, with no intervening event on that line" before it trusts an L2/DIR seq.

Paper. §V p5 says "USLs do not modify the cache coherence states, cache replacement algorithm states, or any other cache hierarchy state". §III-B p3 protects "coherence information". So the paper does not allow this. It is the coherence half of the same footprint, so it should be bucketed together with UV1 and not counted as a second finding.

## 4. DIR:coh (Futuristic, 0x3d40, seq 532) — CHECKER ARTIFACT; the transition itself is allowed

```
3031000:L1D:evict:line=0x3d40:seq=532:pc=0x401bcb:victim=0x3940:...:id=1257
3035000:L2:coh:line=0x3940:seq=532:...:id=1258
3038500:L1D:fill:line=0x3d40:seq=532:...:id=1256
3042500:L2:fill:line=0x3d40:seq=532:...:id=1261
3092000:DIR:coh:line=0x3d40:seq=532:pc=0x401bcb:...:id=1265
```
seq 532 is micro-op 1 (the store) of `MOV_M_I` at 0x401bcb. Only micro-op 0 has a pipeview record (`fetch:3024500:0x00401bcb:0:531: MOV_M_I : limm t1, 0`), and there are 0 fetch records for seq 532. This is a normal L1 allocate → L2 fill → directory fetch (I→IM→M) path. It is a store's write after commit, not a Spec-GetS, which would go `I --SpecFetch--> II` and leave the directory unchanged (dir.sm:494–497). In the trace, `vp` for 532 is `[Infinity,"never"]` only because the seq has no pipeview record, and the actor gate accepts stores (§2). Both the L1D:fill and evict and this DIR:coh are therefore flagged falsely. The DIR protocol counts I→M on every LLC miss as a "coh" change, because both I (Read_Write) and M (Maybe_Stale) count as present in `isPresentPerm`. So `DIR:coh` is benign whenever the request was a normal Fetch or Expose made by a safe load or a committed store. The same transition appears unattributed for an ifetch line: `3087000:DIR:coh:line=0xc00:seq=-:…:id=1263`.

OPEN: why micro-op 1 of a macro-op has no pipeview record. If that is common, the Futuristic `vp` needs a fallback (the macro-op's retire tick) or should count as undecided instead of infinite.

## 5. dir.sm:499–503 — possible real deviation in the source, not exercised here

`// [InvisiSpec] Is it secure?` `transition(M, {Fetch, Expose, SpecFetch}) { inv_sendCacheInvalidate; z_stallAndWaitRequest; }`. A SpecFetch that reaches the directory in state M makes the directory invalidate the current holder. That is a state change caused by a USL, which contradicts §VI-E1 p9 ("a Spec-GetS obtains a copy … without changing any cache or coherence states"; a forwarded Spec-GetS should bounce instead). Neither fixture contains a `DIR:inv` or `L2:inv` attributed to a squashed load, so there is no trace evidence yet. In a single-core run with a single L2 this path needs a race (the L2 replaced the line while a writeback is in flight). OPEN: grep campaign traces for `DIR` or `L2` `inv` with a squashed-load seq right after a SpecFetch.

## Status of remaining work

- The verdict that L2:coh belongs to UV1 rests on the event pattern plus the hook code. I did not confirm the exact L2 state pair (MT→M or something else) against `MESI_Two_Level-L2cache.sm`.
- No fixes were applied. Two changes are proposed for Anna's review: limit the Futuristic actor to loads, and handle a missing pipeview record as undecided instead of `vp=∞`.
