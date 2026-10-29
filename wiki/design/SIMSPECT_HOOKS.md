# SimSpect hooks: the cache/defense event trace in the O3 pipeline output

**Status:** built and verified 2026-10-28 on the three AMuLeT footprint-defense builds (InvisiSpec, CleanupSpec, SpecLFB). Print-only: no defense logic, timing, or behavior changed (verified: identical non-simspect O3PipeView lines, identical `parse_pipeview` output, identical sim ticks, pre-hook vs hooked binary). This implements Layer 1 of [`TRANSMISSION_CRITERIA_FORMAT.md`](TRANSMISSION_CRITERIA_FORMAT.md), with one deliberate change from that proposal: there is no separate `SimSpectCache` flag and no `SSEV` prefix. Per Anna, the only interface is the O3 pipeline trace, so every event prints under the existing `O3PipeView` flag.

## Line format

```
O3PipeView:simspect:<tick>:<struct>:<kind>:line=0x<line>:seq=<sn|->:pc=0x<pc|->:victim=0x<line|->:cause=<id|->:sq=<id|->:id=<id>
```

- `--debug-flags=O3PipeView` alone gives everything. Lines are printed with `DPRINTFR` at the moment of the event, interleaved with the normal O3PipeView records (which gem5 prints in one block when an instruction retires or is destroyed, so a simspect line never lands inside an instruction's record).
- `STAGE3_gem5/gem5_common.py:parse_pipeview` ignores unknown stages, so existing parsers are unaffected. Verified on all three builds: `parse_pipeview(new) == parse_pipeview(ref)`.
- `line` is the 64-byte physical line address. Exceptions: `ROB:squash` and `L1D:cleanup_done` have no line (`line=-`); `DTLB`/`ITLB` events carry the virtual page address.
- `seq` is the dynamic instruction's seqNum, the same number as field 6 of that instruction's `O3PipeView:fetch:` line, so events join to instructions. `-` means no instruction can be named (see Attribution gaps).
- `pc` is the instruction's PC (for instruction fetch: the fetch address).
- `victim` is set only on `evict`: the line that was removed.
- `cause` is set only on `evict`: the `id` of the fill that took the victim's way (that fill line carries the same `id`).
- `sq` is the squash id: set on `ROB:squash` (new id), on CleanupSpec cleanup events and on `SB:buf_release` at squash (the squash that covers the instruction, i.e. the latest squash whose squashing seqNum is below `seq`), and on `cleanup_done`.
- `id` is a unique event id per run.

## Event vocabulary (closed list)

| kind | meaning |
|---|---|
| `fill` | line allocated into `struct` (tag allocated; Ruby allocates the way at miss time in MESI L1, at install time in CleanupSpec's L1) |
| `evict` | line removed by replacement. `line` = the incoming line whose fill caused it, `victim` = the removed line, `cause` = that fill's id |
| `inv` | line removed by anything other than replacement or CleanupSpec cleanup (coherence invalidation, flush, uncacheable access, clusivity) |
| `coh` | the line's last stable coherence state changed to a different stable state while present before and after, with no tag change in that transition (Ruby only) |
| `repl_touch` | replacement-state update (LRU touch) on an access |
| `buf_fill` / `buf_release` | entry into / out of a buffer: the defense buffers (`SB`, `LLCSB`, `LFB`) and the miss-handling entries (`MSHR`, `L1IMSHR`, `L2MSHR`, `DIRTBE`) |
| `expose` / `validate` | InvisiSpec visibility-point re-access issued for a load (`seq` = that load; this marks its visibility point, in both Spectre and Futuristic modes) |
| `cleanup_inv` | CleanupSpec invalidated a line during cleanup |
| `cleanup_restore` | CleanupSpec re-installed an evicted victim (rollback) |
| `cleanup_skip` | CleanupSpec decided no undo is done for this load/line |
| `cleanup_drop` | CleanupSpec dropped / cancelled an in-flight load's fill |
| `cleanup_done` | CleanupSpec finished all undo work for squash `sq` (quiescence point) |
| `squash` | the core squashed everything younger than `seq` (struct `ROB`) |

Structures: `L1D`, `L1I`, `L2` (the LLC in all three builds), `DIR` (Ruby directory), `DTLB`, `ITLB`, `ROB`, and the defense buffers `SB` (InvisiSpec L1-side speculative buffer, `Sequencer::m_specBuf`), `LLCSB` (InvisiSpec's memory-side speculative buffer, `AbstractController::m_specBuf`, used by the directory controller), `LFB` (SpecLFB's line-fill buffer, `BaseCache::refillBlocks`), and the miss-handling entries: Ruby TBEs print as `MSHR` (L1 controller, shared by L1D and L1I), `L2MSHR` (L2 controller), `DIRTBE` (directory); classic MSHRs print as `MSHR` (L1D), `L1IMSHR`, `L2MSHR`. Every cache/memory structure present in a build is exported, not only the ones a paper claims to protect; the criterion JSON chooses which ones count. Prefetchers: none is configured in any SimSpect run; if one is enabled, its fills go through the same allocate path and print as `fill` with `seq=-`.

## Per-build sites

All three: `ROB::squash` (`cpu/o3/rob_impl.hh`, SpecLFB `cpu/o3/rob.cc`) emits `ROB:squash`; core emitter `src/sim/simspect_hooks.{hh,cc}` (event ids, squash ids, per-line attribution map, evict-to-fill id link).

**Ruby builds (InvisiSpec, CleanupSpec), shared code** (`src/mem/ruby/slicc_interface/SimSpectRubyHooks.{hh,cc}`):

- SLICC code generator: `mem/slicc/ast/PeekStatementAST.py` adds `SimSpect::noteMsg(in_msg_ptr)` after every peek (records the message being processed: for a Sequencer `RubyRequest`, its line, PC and the packet's seqNum; for protocol messages, their `m_addr`). `mem/slicc/symbols/StateMachine.py` brackets every `doTransition` with `SimSpect::beginTransition(machine, version, event, state, permission)` / `endTransition(valid, next_state, permission)`, so cache-tag hooks know which SLICC event they run under.
- `CacheMemory::allocate` → `fill` (or `cleanup_restore` under a `*ROLLBACK*` event); `CacheMemory::deallocate` → `evict` (event name contains `Replacement`), `cleanup_inv` (`Inv_CLEANUP`, `Cleanup_Invalidate`, `Cleanup_Invalidate_clean`), else `inv`; all three `CacheMemory::setMRU` overloads → `repl_touch`. Struct from the CacheMemory name (`L1Dcache`→L1D, `L1Icache`→L1I, `L2cache`→L2).
- `TBETable::allocate` / `deallocate` → `MSHR`/`L2MSHR`/`DIRTBE` `buf_fill` / `buf_release` (allocation also records per-line attribution). This is where InvisiSpec UV2 (TBE contention) is visible.
- `endTransition` → `coh` (rule in the table above, using each state's AccessPermission: present = `Read_Only`/`Read_Write`/`Maybe_Stale`, transient = `Busy`) for L1, L2 and DIR; and the CleanupSpec decision events below.
- `arch/x86/tlb.cc` → `DTLB`/`ITLB` `fill` (`TLB::insert`), `evict` (`TLB::evictLRU`, victim = evicted page), `repl_touch` (`TLB::lookup` with LRU update); attribution from the request in `TLB::translate`.

**InvisiSpec only:** `Sequencer::updateSBB` and the SB-hit copy path → `SB:buf_fill`; `Sequencer::makeRequest` → `L1D:expose` / `L1D:validate` when the visibility-point request is issued; `Sequencer::readCallback` expose/validate completion → `SB:buf_release`; `LSQUnit::squash` → `SB:buf_release` for a squashed spec load (`needPostFetch && !isExposeSent`); `AbstractController::recvTimingResp` ReadSpec data → `LLCSB:buf_fill`; the three `m_specBuf` clears in `queueMemoryRead` → `LLCSB:buf_release` (only for an entry that was filled: empty slots hold address 0).

**CleanupSpec only:** native event → SimSpect kind mapping, complete for every cleanup-family event in `MESI_Two_Level-L1cache.sm`, `MESI_Two_Level-L2cache.sm` and `lsq_unit_impl.hh`:

| native (state) | SimSpect |
|---|---|
| L1 `Inv_CLEANUP` (S, X, E: deallocates) | `L1D:cleanup_inv` |
| L1 `Inv_CLEANUP` (NP, I, M: skip actions `clirs`/`clirs2`) | `L1D:cleanup_skip` |
| L1 `Inv_CLEANUP` (transient: waits/recycles) | nothing (re-fires when stable) |
| L1 `Load_ROLLBACK` (NP, I: allocates + GETS) | `L1D:cleanup_restore` (the L2 fill of that GETS prints as `L2:fill`) |
| L1 `Load_ROLLBACK` (S, E, M, X: already present) | `L1D:cleanup_skip` |
| L1 `Load_ROLLBACK` (transient) / `Waiting_Rollback_CLEANUP` / `Waiting_CLEANUP` / `Waiting_Final_CLEANUP` / `Waiting_CLEANUP_inprogress` | nothing (waits) |
| L1 `Skip_ROLLBACK`, `Skip_Inflight_Cleanup` | `L1D:cleanup_skip` |
| L1 `L1_Replacement` triggered to make room for a rollback | `L1D:evict` (line = the cleanup request's line, see gaps) |
| L1 `InvL2_CLEANUP` | nothing at L1 (it sends `PUTINV`; the L2 prints the result) |
| L2 `Cleanup_Invalidate` / `Cleanup_Invalidate_clean` (deallocates) | `L2:cleanup_inv` |
| L2 `SendAck_Cleanup_Invalidate` (NP: line not in L2) | `L2:cleanup_skip` |
| L1 `Inflight_CLEANUP_reqs` (NP) | `L1D:cleanup_drop` |
| L1 `Inflight_CLEANUP_reqs` (M_I / I → NP) | `L1D:cleanup_skip` |
| L1 `Drop_Load_Cleanup_Inflight` | `L1D:cleanup_drop` |
| L1 `Inflight_CLEANUP_resp`, `Done_CLEANUP` (per-request ack), `Done_Invalidate_CLEANUP` (never triggered in this .sm) | nothing |
| L1 `L1_Replacement_OnInstall` | `L1D:evict` (+ the `AllocateLine_OnInstall` `L1D:fill`) |
| LSQ `issueBufferedCleanupReqs`: split load (`isSplitReq`, the UV4 `TODO`) | `L1D:cleanup_skip` on both lines |
| LSQ: returned load that hit L1, or has no hit-level info | `L1D:cleanup_skip` |
| LSQ `reissueSkippedCleanupReq`: no cleanup needed | `L1D:cleanup_skip` |
| LSQ `clearLoadQueue` succeeds (all cleanup acks in) | `L1D:cleanup_done` (`seq` = squash seqNum) |

A not-issued squashed load (never touched memory) prints nothing. A cleanup request the D-cache port refused is retried by the LSQ and prints nothing until it is issued.

**SpecLFB** (newer gem5, classic caches; `mem/cache/base.cc`, `mem/cache/tags/base_set_assoc.hh`): `BaseCache::allocateBlock` → `fill`, and the replacement victims it evicts in `handleEvictions` → `evict` (exact cause link: the fill id is assigned before the evictions); `BaseCache::invalidateBlock` outside a replacement → `inv`; `BaseSetAssoc::accessBlock` LRU touch → `repl_touch`; the unsafe-load branch of `recvTimingResp` that parks the line in `refillBlocks` → `LFB:buf_fill`; the refill from `refillBlocks` when the same-PC load returns → `LFB:buf_release` then the cache `fill`. Struct from the cache name (`dcache`→L1D, `icache`→L1I, `l2`→L2). `MSHRQueue::allocate` / `deallocate` (`mem/cache/mshr_queue.cc`) → `MSHR`/`L1IMSHR`/`L2MSHR` `buf_fill` / `buf_release`. Both classic levels are covered whenever `--l2cache` is on.

## Attribution (how `seq` is found)

- Requests already carry the seqNum: the two older Ruby builds create every data `Request` with `this->seqNum` (`cpu/base_dyn_inst.hh`), and copies (`postReq`, `cleanupReq`, split halves) keep it; the SpecLFB base sets `setReqInstSeqNum` in `LSQ::SingleDataRequest::initiateTranslation`. No seqNum had to be threaded.
- Ruby L1 events processed from a Sequencer `RubyRequest` (loads, stores, SpecLoad, Expose, CleanupSpec cleanup requests) are exact: the seqNum comes from the request being processed.
- Ruby L1 events from responses, and all L2 / DIR / LLCSB events, use a per-line "most recent cause" map: set when an L1 allocates a TBE for a CPU request (that is the moment a request leaves L1), propagated to a line's writeback when an eviction or TBE for another line is caused by it. In single-core SE runs this names the right instruction except where a later request to the same line has already started.
- Evictions are attributed to the request that caused them (`seq` on the evict line), and the evicted line's attribution moves to that instruction so its writeback/L2/DIR traffic is attributed too.
- Classic (SpecLFB): fills, evictions, repl_touch use the packet's request; writebacks and other packets without a seqNum fall back to the per-line map.

## Attribution gaps (`seq=-` and other limits)

- **Instruction fetch** (`L1I`, `ITLB`, and the L2/DIR traffic of an I-miss): `seq=-`. A fetch happens before the dynamic instruction exists, so no seqNum exists. `pc` = fetch address.
- **Lines never requested by an instruction** (startup, page-table, the loader's first touches): `seq=-`.
- **In-flight squashed loads never get an `O3PipeView:fetch:` line** (gem5 prints a record only when the instruction object is destroyed, and the LSQ keeps squashed in-flight loads until the end); their seqs are valid but do not join. Seen on InvisiSpec UV1 (12 seqs).
- **CleanupSpec rollback-space replacement** (`L1cache.sm` "Space unavailable for CleanupReq"): the evict's `line` is the cleanup request's line, not the rollback target, and its `cause` id has no matching fill.
- **InvisiSpec SpecLoad replacement (UV1):** the spec load does not allocate in L1D, so the evict's `cause` id never appears as a fill. `line`/`seq` on the evict are the attribution.
- **TLB** events carry the virtual page, not a physical line. TLB attribution is the most recent `translate` call.
- **`coh` is Ruby only.** The classic cache changes coherence bits in many places with no single site; not implemented for SpecLFB (single-core classic runs have no downgrades to see).
- **`LLCSB` and `DIRTBE` hooks are compiled but printed nothing in the verification runs** (no spec load missed the L2 in those tests, and the MESI directory allocates TBEs only for DMA).
- **`LFB` hooks are compiled but were not exercised** by any verification run: on the gadgets tried (`gem5-hooks/verify/uv6x.s`, `uv6dep.s`, STT_6 inst-002014 and inst-014986) SpecLFB classified every spec load `isUnsafe=0`, so nothing was parked in the LFB.

## How to verify

`gem5-hooks/verify/verify_simspect_hooks.py` (copy on cafe2 in `/work/amulet/simspect_hooks_verify/`) builds one litmus test, runs it with only `--debug-flags=O3PipeView`, counts simspect lines per `struct:kind`, checks that attributed events join to `fetch` seqNums, and with `--ref-bin` reruns on the pre-hook binary and requires identical non-simspect lines, identical `parse_pipeview` output and identical sim ticks. `gem5-hooks/verify/mkann.py` makes the annotation for a hand gadget (`<name>_branch`, `<name>_xmit` labels). Rebuild script: `gem5-hooks/verify/build_simspect_hooks.sh` (copy at `/work/amulet/build_simspect_hooks.sh`, log `/work/amulet/rebuild_<build>_simspect_hooks_20261028.log`).

`gem5-hooks/verify/run_all_verify.sh` reruns every case below and prints one line each (`ok`, sim ticks new/ref, non-simspect identical). Final run 2026-10-28 22:57 after the last rebuild: all `ok=True`; ref ticks identical for inv_uv1 5691000, cln_uv4align 1252000, cln_uv4split 1251500, cln_uv5clean 1378000, lfb_uv6x 1110500, lfb_inst002014 6227500; inv_fut (FuturisticSafeInvisibleSpec, no ref run) shows `L1D:expose ... seq=647:pc=0x401c74` with the load's seq. MSHR events: e.g. `O3PipeView:simspect:80500:MSHR:buf_fill:line=0x3dc0:seq=3:pc=0x401000:...` (InvisiSpec), `L1IMSHR`/`MSHR`/`L2MSHR` on SpecLFB with `--l2cache`.

Results on 2026-10-28 (outputs in `/work/amulet/simspect_hooks_verify/<name>/`):

- **InvisiSpec UV1** (`inv_uv1`: STT_6 `mispredict_not_taken/inst-002014`, `--ruby --scheme=SpectreSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1 --l1d_size=1kB --l1d_assoc=2`, stall 5000): spec loads evict live L1D lines in the window, e.g. `O3PipeView:simspect:3176500:L1D:evict:line=0x3dc0:seq=576:pc=0x401c74:victim=0x39c0:cause=1458:sq=-:id=1459`, then `SB:buf_fill` for each spec load and `SB:buf_release ... sq=4` at the squash (`ROB:squash:...:seq=564:pc=0x401c53`). Ref binary: identical ticks (5691000) and pipeview.
- **InvisiSpec KV1** (`inv_kv1mispred`): wrong-path `L1I:fill ... pc=0x4020ff` before the squash; `L1D:expose` present.
- **SpecLFB UV6 shape** (`lfb_uv6x`, `--l2cache`): the first spec load fills L1D (and L2) in the window, `O3PipeView:simspect:184500:L1D:fill:line=0x2000:seq=28:pc=0x40102f:...`, squash at 1094500 (`seq=27`, the branch). The second spec load (seq 29) also fills L1D: SpecLFB's own trace shows both loads `isUnsafe=0`. Ref binary identical.
- **CleanupSpec** (`cln_uv5clean`, `uv5_demo/uv5clean.s`, `--l1d_size=8kB --l1d_assoc=2 --L1_TBEs=8`): spec load seq 35 `L1D:fill line=0x4000` evicts committed `0x3000` (`evict ... victim=0x3000:cause=59`, fill id 59), squash `sq=4`, then `L1D:cleanup_inv line=0x4000`, `L1D:cleanup_restore line=0x3000`, `L1D:cleanup_done sq=4`. `cln_uv4align`: L1D and L2 `cleanup_inv`. `cln_uv4split` (UV4): spec load seq 58 fills two L1D lines (0x1000, 0x1040) and gets `cleanup_skip` on both, zero `cleanup_inv`; ref binary identical (1251500 ticks). unXpec: `unxmiss` has L1D+L2 `cleanup_inv`, `unxhit` only `cleanup_skip`.

## Backups

- Pre-hook binaries: `build/X86_MESI_Two_Level/gem5.opt.pre-simspect-hooks-20261028` (InvisiSpec, CleanupSpec), `build/X86/gem5.opt.pre-simspect-hooks-20261028` (SpecLFB). Every earlier result was produced by these binaries; rerun with them to reproduce exactly.
- Pristine sources of every touched file: `/work/amulet/backups/<build>-pre-simspect-hooks-20261028.tgz` (InvisiSpec/CleanupSpec: paths start `src/`, extract in the build root; SpecLFB: paths are relative to `src/`, extract in `src/`).
- Diffs (pristine vs hooked, `diff -ruN`): `gem5-hooks/amulet-{InvisiSpec,CleanupSpec,SpecLFB}/simspect_hooks.diff`. Apply from the build root with `patch -p1` (paths start `pristine/src/...` / `hooked/src/...`).
