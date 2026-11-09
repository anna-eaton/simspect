# SimSpect hooks: the cache/defense event trace in the O3 pipeline output (format v2)

**Status (2026-11-07): v2 built and verified on the three AMuLeT footprint-defense builds (InvisiSpec, CleanupSpec, SpecLFB).** The hooks are print-only. On all 10 verification cases the v2 binary and a reference binary with the same non-print code give identical sim ticks, identical non-simspect O3PipeView lines and identical `parse_pipeview` output (table in "How to verify"). v2 does the approved hook fixes (`wiki/findings/audits/2026-10-28/APPROVALS.md` §E) and exports as much as the builds can print cheaply: hit/miss for every lookup, set/way, request kind, native event and states, LSQ load issue / store forward / data arrival, branch resolution, and each defense's own decisions. v1 (2026-10-28) is the same line format without the appended fields; history and the 2026-10-30 rebuild accident are under "History".

This doc is the spec for what the pipeline parses: every event is one line in the normal `--debug-flags=O3PipeView` output, read by `STAGE3_gem5/gem5_common.py:parse_simspect_line` / `parse_simspect_events` and used by `STAGE3_gem5/check_footprint.py` (criteria in `specs/leakage/*.json`, format in [`TRANSMISSION_CRITERIA_FORMAT.md`](TRANSMISSION_CRITERIA_FORMAT.md)). Per Anna, the O3 pipeline trace is the only interface, so there is no separate debug flag.

## Line format

```
O3PipeView:simspect:<tick>:<struct>:<kind>:line=0x<line>:seq=<sn|->:pc=0x<pc|->:victim=0x<line|->:cause=<id|->:sq=<id|->:id=<id>[:key=value ...]
```

- The first 11 fields are exactly v1 and always appear in this order (`check_v2_trace.py` checks it). v2 only appends `key=value` fields. Values never contain `:` or `=` (the emitter replaces them, and whitespace, with `_`); `-` means none. `parse_simspect_line` already returns unknown keys verbatim, so v1 consumers keep working and `check_footprint` gives the same verdicts on v1 and v2 traces of the same runs (`STAGE3_gem5/tests/test_check_footprint.py`, `TestRealTracesV2`).
- **Header:** the first simspect line of every run is `O3PipeView:simspect:0:META:hooks:line=-:seq=-:pc=-:victim=-:cause=-:sq=-:id=0:ver=2:build=<InvisiSpec|CleanupSpec|SpecLFB>`. A trace with no META line is v1.
- Lines are printed with `DPRINTFR` when the event happens, between the normal O3PipeView records (gem5 prints an instruction's record in one block when it retires or is destroyed, so a simspect line never lands inside one). In Ruby builds, events raised inside a SLICC transition get their id when they happen and are printed when the transition ends (so `nst=` is known); within one tick, order by `id`.
- `line` = 64-byte physical line address. Exceptions: `ROB:squash`, `L1D:cleanup_done`, `LSQ:unsafe`, `LSQ:usl_flag`, `BR:*` have `line=-`; `DTLB`/`ITLB` lines carry the virtual page. Physical line `0x0` is real: in SE mode the code page at vaddr 0x401000 maps to paddr 0, so instruction-fetch events name it.
- `seq` = the dynamic instruction's seqNum (field 6 of its `O3PipeView:fetch:` line), so events join to instructions. `pc` = that instruction's PC (fetch address for instruction fetch).
- `victim` only on `evict`: the removed line. `cause` only on `evict`: the `id` of the fill that took the way (that fill carries the same `id`; v2 guarantees no id is the cause of two evicts).
- `sq` = squash id: new on `ROB:squash`; on cleanup events, squash-time buffer releases and `cleanup_done` it names the squash. `id` = unique per run, except the resolve-hook `BR:` lines from [`RESOLUTION_HOOKS.md`](RESOLUTION_HOOKS.md), which print `id=-`.

## Appended fields (v2)

| key | meaning | on |
|---|---|---|
| `addr`, `size` | byte address and size of the request (physical for caches, virtual for TLBs) | cache, TLB, LSQ, buffer events |
| `vaddr`, `paddr` | the other address where both are known | LSQ events (`vaddr`), TLB fill (`paddr`) |
| `set`, `way` | the slot touched (`vset`/`vway` = the victim's slot on SpecLFB evicts) | fill, evict, inv, hit, repl_touch, TLB |
| `req` | request kind, closed list: `ld st ifetch specld expose validate cleanup rollback wb pf flush coh -` (`coh` = traffic for a line with no CPU cause yet) | everywhere a request is known |
| `msg` | native message or command name (`RubyRequestType`, `CoherenceRequestType`, classic `MemCmd`) | Ruby and classic cache events |
| `ev`, `st`, `nst` | Ruby: SLICC event, state before, state after the transition (`pst` on `coh` = last stable state). TLB/classic: native function in `ev` | Ruby transition events, TLB, SpecLFB `inv` |
| `lvl` | where the data came from or was found: `L1 L2 MEM SB -` | hit/miss, `LSQ:data`, `SB:buf_release`, `cleanup_req` |
| `why` | the native reason, per kind (below) | skips, releases, safe, inv |
| `usl`, `hitusl` | SpecLFB's request flags (`Request::isUSL`, `isHit_USL`) | SpecLFB cache + LSQ events |
| `perm`, `touch` | SpecLFB hit: block has the needed permission; replacement state updated | SpecLFB `hit` |
| `dirty` | the removed block was dirty | SpecLFB evict / inv |
| `occ`, `cap` | MSHR occupancy after allocation / capacity | SpecLFB `MSHR:buf_fill` |
| `idx`, `blk`, `src_idx`, `core` | InvisiSpec spec-buffer entry, block half, source entry on an SB hit, LLC-SB core | `SB`, `LLCSB` |
| `filled`, `half`, `sqseq`, `post_squash` | InvisiSpec squash release: the SB entry had data / which line of a split load / the squashing seqNum / a fill that landed after its load's release | `SB` |
| `bufd`, `merged` | CleanupSpec: loads the squash episode buffered for cleanup (0 = nothing to undo) / squash ids merged into the episode | `cleanup_done` |
| `mode`, `rb`, `evl1` | CleanupSpec: exec or inflight cleanup / rollback line / the L1 line the load's fill evicted | `cleanup_req`, `LSQ:data` |
| `issued`, `ret` | CleanupSpec: the squashed load had issued / had returned | `cleanup_skip` |
| `trig` | SpecLFB: seq of the same-PC load whose miss released a parked LFB line | `LFB:buf_release` |
| `mispred`, `predtaken`, `act`, `stalled`, `upc`, `cond` | IEW branch resolution: mispredicted / predicted taken / this resolution triggers the squash / released by the resolve-stall hook / micro-PC / conditional | `BR:resolve` |
| `unsafe`, `cusl`, `musl`, `prevnounsafe`, `reallyunsafe`, `prevbrsres`, `lqhead`, `split`, `requsl` | SpecLFB per-load state at translation (`dyn_inst.hh:640-642`: `unsafe = (cusl or musl) and reallyunsafe`), whether the load is the load-queue head, split, and the request's USL flag after tagging | `LSQ:unsafe` |
| `f`, `v`, `by` | SpecLFB flag change: flag name, new value, which walk (`lsq` = `LSQUnit::updateSafeState`, `rob` = `ROB::updateSafeState`) | `LSQ:usl_flag` |
| `sent`, `bounced`, `blocked`, `split`, `line2` | LSQ issue: the cache accepted the packet / SpecLFB refused a hit-USL request / the port was blocked / split load and its second line | `LSQ:issue` |
| `via`, `squashed`, `src`, `spc` | LSQ data: `mem`, `sb` (InvisiSpec spec buffer), `stlf`, `ipr` / the load was already squashed / forwarding store's seq and PC | `LSQ:data`, `LSQ:stlf` |

## Event vocabulary (closed list)

| struct:kind | meaning |
|---|---|
| `META:hooks` | trace header (`ver`, `build`) |
| `<cache>:hit` / `<cache>:miss` | a demand lookup found / did not find the line. Ruby L1: CPU-request events `Load Ifetch Store SpecLoad Expose` (miss = the transition allocated a TBE or the line was not present); Ruby L2: `L1_GET*`, `L1_UPGRADE`, `L1_EXPOSE`; classic: every `BaseCache::access` except writebacks, evictions and cache maintenance; TLB: `TLB::translate` lookup; InvisiSpec `SB`: the LSQ's spec-buffer check |
| `fill` | line allocated into the struct (Ruby MESI L1 allocates the way at miss time; CleanupSpec at install time) |
| `evict` | line removed by replacement: `line` = incoming line, `victim` = removed line, `cause` = that fill's id. CleanupSpec rollback-space evictions carry `req=rollback`, the squash `sq`, `line` = the rollback line, `cln` = the cleanup request's line |
| `inv` | line removed by anything other than replacement or cleanup: coherence, flush, uncacheable, wrong-L1 clusivity (`why=clusivity`), TLB `flushAll`/`flushNonGlobal`/`demapPage` (`ev=`) |
| `coh` | Ruby only: last stable state changed to another stable state while present, with no tag change in that transition |
| `repl_touch` | replacement-state update on an access |
| `buf_fill` / `buf_release` | entry into / out of a buffer: `SB`, `LLCSB`, `LFB`, `MSHR`, `L1IMSHR`, `L2MSHR`, `DIRTBE` |
| `L1D:expose` / `L1D:validate` | InvisiSpec visibility-point re-access issued for load `seq` |
| `LSQ:safe` | InvisiSpec/fence scheme: the load became safe (`why=prev_brs_resolved` Spectre, `prev_insts_completed` Futuristic, `fence_*` for the fence scheme) |
| `LSQ:fence` | fence scheme holds the load |
| `LSQ:issue` | the LSQ offered the load's packet to the D-cache (`sent=0` = not accepted this cycle) |
| `LSQ:stlf` | store-to-load forward (`src` = store seq) |
| `LSQ:data` | the load obtained its data (`via`, `lvl`, `squashed`) |
| `LSQ:unsafe` | SpecLFB: the per-load unsafe decision, printed where the LSQ tags the request at translation (`lsq.cc` `initiateTranslation`) |
| `LSQ:usl_flag` | SpecLFB: a per-load safety flag changed (`prevnounsafe` printed once, it is sticky) |
| `BR:resolve` | IEW resolved a control instruction (`executeInsts`, or the resolve-stall release) |
| `BR:predict_force`, `resolve_hold`, `resolve_drop`, `resolve_release`, `resolve_bcast`, `resolve_visible` | resolution-hook lines, defined in [`RESOLUTION_HOOKS.md`](RESOLUTION_HOOKS.md) (`id=-`) |
| `ROB:squash` | the core squashed everything younger than `seq` |
| `L1D:cleanup_req` | CleanupSpec issued a cleanup request for squashed load `seq` (`lvl` = the hit level that chose the undo path, `lsq_unit_impl.hh:142-160`; `rb` = rollback line) |
| `cleanup_inv` | CleanupSpec invalidated a line during cleanup |
| `cleanup_restore_req` | CleanupSpec rollback started: victim tag allocated, GETS issued |
| `cleanup_restore` | rollback done: the victim's data returned (printed at the rollback TBE's free; `nst` = S/E, or I if it was invalidated meanwhile) |
| `cleanup_skip` | no undo for this load/line (`why`: `split`, `not_issued`, `inflight_cleanup_off`, `l1hit`, `nohitinfo`, `reissue_nocleanup`, `present`, `ack_no_inv`, or a native skip event in `ev`) |
| `cleanup_wait` | L2 `SendAck_Cleanup_Invalidate` kept the request waiting (NP recycle or stall), printed once per request message |
| `cleanup_drop` | CleanupSpec decided to drop an in-flight load's fill |
| `cleanup_drop_data` | `DropIncomingPacket*`: the dropped fill's data actually arrived and was discarded |
| `L1D:cleanup_done` | CleanupSpec finished all undo work: exactly one per squash id (squashes during a cleanup merge into its episode and each get their own line), including squashes that buffered nothing (`bufd=0`) |

Structures: `L1D`, `L1I`, `L2` (the LLC in all three builds), `DIR` (Ruby directory), `DTLB`, `ITLB`, `ROB`, `LSQ`, `BR`, `META`, and the buffers `SB` (InvisiSpec L1-side spec buffer, `Sequencer::m_specBuf`), `LLCSB` (InvisiSpec memory-side spec buffer, `AbstractController::m_specBuf`), `LFB` (SpecLFB, `BaseCache::refillBlocks`), and the miss-handling entries: Ruby TBEs `MSHR` (L1 controller, shared by L1D and L1I), `L2MSHR`, `DIRTBE`; classic `MSHR` (L1D), `L1IMSHR`, `L2MSHR`. Every structure present in a build is exported, not only the ones a paper protects; the criterion JSON chooses what counts. No prefetcher is configured in any SimSpect run.

## Per-build sites

**All three:** core emitter `src/sim/simspect_hooks.{hh,cc}` (ids, squash ids, per-line attribution, evict-to-fill link, `Kv` fields, META header, print-side tag sets); `ROB::squash` → `ROB:squash`; IEW `executeInsts` + the resolve-stall release → `BR:resolve`.

**Ruby builds (InvisiSpec, CleanupSpec), shared** (`src/mem/ruby/slicc_interface/SimSpectRubyHooks.{hh,cc}`, identical in both trees):

- SLICC codegen: `PeekStatementAST.py` opens a `SimSpect::MsgScope` per peek, so each message is the attribution context only until its peek ends (v1 used one global that was never cleared). `StateMachine.py` brackets every `doTransition` with `beginTransition`/`endTransition` plus a `TransGuard` that closes the bracket if an action throws.
- `CacheMemory::allocate` → `fill` (`cleanup_restore_req` under a `*ROLLBACK*` event); `deallocate` → `evict` (event contains `Replacement`, except the request's own line → `inv why=clusivity`, and a replacement under a cleanup request → `evict req=rollback`), `cleanup_inv` (`Inv_CLEANUP`, `Cleanup_Invalidate(_clean)`), else `inv`; `setMRU` → `repl_touch`. All with `set`/`way`.
- `TBETable` alloc/free → `MSHR`/`L2MSHR`/`DIRTBE` `buf_fill`/`buf_release`; the free of a CleanupSpec rollback TBE → `cleanup_restore`.
- `endTransition` → `hit`/`miss`, `coh`, and the CleanupSpec decision events.
- `arch/x86/tlb.cc` → TLB `hit`/`miss` (`translate`), `fill` (`insert`), `evict` (`evictLRU`), `repl_touch` (`lookup`), `inv` (`flushAll`, `flushNonGlobal`, `demapPage`).
- `cpu/o3/lsq_unit.hh` / `lsq_unit_impl.hh` → `LSQ:issue`, `LSQ:stlf`, `LSQ:data`, `LSQ:safe`, `LSQ:fence`.

**InvisiSpec only:** `Sequencer::updateSBB` and the SB-hit copy → `SB:buf_fill` (`post_squash=1` + an immediate `buf_release why=post_squash` when the load's entry was already released at its squash); `Sequencer::makeRequest` → `L1D:expose`/`validate`; `readCallback` expose/validate completion → `SB:buf_release` (`lvl`); `hitCallback` notes the hit level for `LSQ:data lvl=`; `LSQUnit::squash` → `SB:buf_release why=squash` for both lines of a split load, only for a load whose SpecLoad was sent (`needPostFetch`, set in `lsq_unit.hh` only after a successful send), `sq` = the squash being applied (`sqExact(squashed_num)`); `LSQ:issue`-time SB lookup → `SB:hit`/`miss`; `AbstractController` → `LLCSB:buf_fill`/`buf_release` (keyed per controller; a ReadSpec overwriting a live entry releases it first; consistent `line`).

**CleanupSpec only:** native event → SimSpect kind, complete for the cleanup-family events in `MESI_Two_Level-L1cache.sm`, `-L2cache.sm` and `lsq_unit_impl.hh`:

| native (state) | SimSpect |
|---|---|
| L1 `Inv_CLEANUP` (S, X, E: deallocates) | `L1D:cleanup_inv` |
| L1 `Inv_CLEANUP` (NP, I, M: `clirs`/`clirs2`) | `L1D:cleanup_skip` |
| L1 `Load_ROLLBACK` (NP, I: allocates + GETS) | `L1D:cleanup_restore_req`, then `L1D:cleanup_restore` when the rollback TBE is freed |
| L1 `Load_ROLLBACK` (S, E, M, X: present) | `L1D:cleanup_skip why=present` |
| L1 `Skip_ROLLBACK`, `Skip_Inflight_Cleanup` | `L1D:cleanup_skip` |
| L1 `L1_Replacement` to make room for a rollback | `L1D:evict req=rollback` (`sq`, `line` = rollback line, `cln`) |
| L1 `Inflight_CLEANUP_reqs` (NP) / `Drop_Load_Cleanup_Inflight` | `L1D:cleanup_drop` |
| L1 `Inflight_CLEANUP_reqs` (M_I / I → NP) | `L1D:cleanup_skip` |
| L1 `DropIncomingPacket`, `DropIncomingPacketnUnblockL2`, `DropIncomingPacketnUnblockRevertL2` | `L1D:cleanup_drop_data` (these also fire with no TBE, not only for cleanup) |
| L2 `Cleanup_Invalidate` / `Cleanup_Invalidate_clean` | `L2:cleanup_inv` |
| L2 `SendAck_Cleanup_Invalidate`, request consumed with a state change (`C_ISS`→`CC_ISS`, `M_I`→`C_M_I`, L2cache.sm:1136-1139, 1162-1165) | `L2:cleanup_skip why=ack_no_inv` |
| L2 `SendAck_Cleanup_Invalidate`, request kept (NP recycle, L2cache.sm:1147-1149; stalls) | `L2:cleanup_wait`, once per request (v1 printed `cleanup_skip` on every recycle) |
| L1/L2 transient-state waits, `Inflight_CLEANUP_resp`, `Done_CLEANUP` | nothing |
| LSQ `issueBufferedCleanupReqs`, cleanup request sent | `L1D:cleanup_req` |
| LSQ split load (the UV4 `TODO`), not issued, inflight with cleanup off, L1 hit, no hit info, reissue with nothing to do | `L1D:cleanup_skip` with that `why` (an untranslated load prints `line=-`, never `0x0`) |
| LSQ `clearLoadQueue` succeeds | `L1D:cleanup_done`, one per squash id of the episode |

**SpecLFB** (newer gem5, classic caches): `BaseCache::access` → `hit`/`miss` (`perm`, `touch`, `usl`, `hitusl`); `allocateBlock` → `fill` and its `handleEvictions` victims → `evict` (`vset`/`vway`, `dirty`; an LFB refill never reads the natively freed parked packet); `invalidateBlock` outside a replacement → `inv`; `BaseSetAssoc::accessBlock` LRU touch → `repl_touch` (v2: per-line fallback attribution); the unsafe-load branch of `recvTimingResp` that parks the line → `LFB:buf_fill why=usl_miss`; the same-PC refill → `LFB:buf_release why=refill` (`sq` of the parked load, `trig`) then the cache `fill`; `MSHRQueue` → `MSHR`/`L1IMSHR`/`L2MSHR` (`occ`/`cap`); `lsq.cc` `initiateTranslation` → `LSQ:unsafe`; `LSQUnit`/`ROB::updateSafeState` → `LSQ:usl_flag`; `LSQUnit::trySendPacket` → `LSQ:issue` (`bounced`); forwarding → `LSQ:stlf`; `WritebackEvent::process` / `completeDataAccess` → `LSQ:data`.

## Attribution and remaining gaps

- Requests carry the seqNum in all three builds (`Request` created with `this->seqNum` in the old base; `setReqInstSeqNum` in SpecLFB). Ruby L1 events processed from a Sequencer `RubyRequest` are exact. Ruby responses and all L2 / DIR / LLCSB events use a per-line "most recent cause" map (set when an L1 allocates a TBE for a CPU request; moved to a line's writeback when an eviction is caused by it); exact in single-core SE runs except when a later request to the same line has already started. L2 cleanup events take `seq` from that map, so their `sq` can name a later squash (audit finding 6, not fixed: the L2 only sees a protocol message).
- `seq=-`: instruction fetch (`L1I`, `ITLB` and their L2/DIR traffic) happens before the dynamic instruction exists; lines never requested by an instruction (startup, page table) have none. Ruby L1 TBEs print `MSHR` for both sides, so I-side TBEs are told apart only by `seq=-`/`req=ifetch`.
- In-flight squashed loads never get an `O3PipeView:fetch:` line (gem5 prints a record only when the instruction is destroyed), so their seqs are valid but do not join.
- InvisiSpec SpecLoad replacement (UV1): the spec load does not allocate in L1D, so the evict's `cause` id never appears as a fill. v2 drops that reservation at the end of the transition, so a later expose fill can no longer inherit it.
- CleanupSpec rollback-space evict: its `cause` id is reserved for the rollback line, whose allocate prints as `cleanup_restore_req` (not `fill`), so the id does not reappear. `req=rollback` and `sq` mark it.
- SpecLFB: an LFB entry has no removal path except the same-PC refill (`base.cc` grep: only the push, the refill and its erase), so a squashed unsafe load's parked line can enter L1D much later, when a later load with the same PC misses; `seq` on that fill is the parked load, `trig` the later one. A split SpecLFB load is tagged USL only on its main request (`lsq.cc` SplitDataRequest), which `LSQ:unsafe split=1 requsl=` shows.
- TLB events carry the virtual page; TLB attribution is the most recent `translate` (exact in SE mode, where `insert` is synchronous).
- `coh` is Ruby only. Compiled but **not exercised by any v2 verification case** (0 lines in all 10 traces): `LLCSB` (no spec load missed the L2), `DIRTBE` (MESI allocates directory TBEs only for DMA), `LFB` (on the three SpecLFB cases no unsafe load parked a line; see the UV6 note below), `cleanup_wait`, `cleanup_drop`, `cleanup_drop_data`, `evict req=rollback`, `inv why=clusivity`. Their code paths were reviewed, not run.
- **Gaps found by the first STT_6 runs (2026-11-08, details in `wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md` "CURRENT"):**
  - **Ruby resource and protocol stalls print nothing.** The generated `doTransition` passes only `result==Valid` to `SimSpect::endTransition` (`src/mem/slicc/symbols/StateMachine.py` ~1273-1295). That leaves UV2 contention and the CleanupSpec TBE-2 deadlocks visible only in ProtocolTrace.
  - **Instruction-fetch events have no `seq`,** so KV1 cannot be attributed (`fetch_impl.hh` `fetchCacheLine` runs before the DynInst exists).
  - **CleanupSpec `cleanup_drop` prints `seq=-`/`sq=-`.** It is raised from the mandatory-queue peek (`MESI_Two_Level-L1cache.sm:867`) after the sequencer entry is gone, and it drops a queued request, not a returned fill.
  - **A read-modify-write read prints `req=st`.**
  - **SpecLFB flag changes not printed:**
    - `setPrevBrsResolved` (`rob.cc:464`) and the direct-jump reset show only as `prevbrsres=` on `LSQ:unsafe`;
    - `setPrevStoreResolved` (`rob.cc:476`) is not printed;
    - `SpeclfbStalled` set/clear is not printed;
    - a replayed held load prints no new `LSQ:unsafe` (adding the flags to `LSQ:issue` at `lsq_unit.cc:1445` would cover it).
  - **SpecLFB `LFB` events never fire,** because the native park path is unreachable in this build: a HitUSL miss is refused and replayed (`lsq.cc:1049-1051`, `base.cc:597-617,853,1943,3236-3238`).
  - **Now exercised:** `cleanup_restore_req`/`cleanup_restore` (1505×, correct) and `cleanup_drop` (320×, only in deadlocked runs). `cleanup_wait`, `cleanup_drop_data`, `evict req=rollback` and `inv why=clusivity` are still at 0 in about 6100 CleanupSpec runs.
  - **Parser hazard (fixed 2026-11-08 in the Mac copy):** native formats that print text after their own newline glue it onto the next line: CleanupSpec `src/cpu/o3/lsq_unit.hh:1257` (`"Created CleanupReq … 0x%llx\n."`) and `src/mem/ruby/system/RubyPort.cc:272` (`"…Ruby.\n "`). A grep of the InvisiSpec, SpecLFB, recon-modded, stt and spt trees found no others in CPU or cache code. With `LSQUnit` on, a hook line could be dropped (this happened in the UV3 demo). `gem5_common._unglue` now strips the residue before every trace parser (`_trace_lines`, `parse_simspect_line`), and `gem5-hooks/verify/check_v2_trace.py` does the same. Fixture parses are unchanged (all 10 fixtures identical); test `test_glued_native_print_residue_is_ignored`.
- Not added (no cheap print-only site found, or out of time): Ruby `lvl=` on hit/miss for the L1 beyond L1/-, classic hit level on `LSQ:data` (`lvl=-`), coherence-bit changes on the classic cache, compressed-cache `handleEvictions` from `updateCompressionData` (no compressor is configured).

## What the v2 trace already showed (SpecLFB UV6)

On `lfb_uv6x` (two speculative loads behind a held mispredicted branch, `gem5-hooks/verify/uv6x.s`), the new lines show why the second load is also treated as safe. At tick 92500 the ROB walk sets `prevnounsafe=1` on both loads (seq 28 and 29), before the LSQ walk sets `cusl=1` on seq 28 at 93000. `PrevNoUnsafe` is sticky, so at translation (94000) both print `LSQ:unsafe unsafe=0 cusl=1 prevnounsafe=1 reallyunsafe=0 lqhead=0`, and both fill L2 (174000, 179000) and L1D (184500, 189500) before the squash at 1094500. So the "wider than UV6" behavior here comes from the order of the two walks in one cycle, not from the load-queue-head skip the 2026-10-28 audit guessed (`wiki/findings/audits/2026-10-28/hooks_speclfb_and_uv6.md`; the oldest load in the LQ here is the committed load seq 22, which is older than the branch). Later instances of the same loads print `unsafe=1` and are not sent (`LSQ:issue sent=0 usl=1 hitusl=1`). Whether this counts as a SpecLFB implementation bug is Anna's call (`URGENT_TODO.md`).

## How to verify

- `gem5-hooks/verify/run_all_verify_v2.sh` (copy on cafe2 in `/work/amulet/simspect_hooks_verify_v2/`, run inside `gem5_dev`) runs every case with `gem5-hooks/verify/verify_simspect_hooks.py` against a **reference binary with the same non-print code**, then `gem5-hooks/verify/check_v2_trace.py` on the new trace. Log: `run_all_v2_20261107.log` there.
- Reference binaries: Ruby builds `/work/amulet/hooks_v2_work/ref_<build>/build/X86_MESI_Two_Level/gem5.opt`, built by `gem5-hooks/verify/make_refs.sh` (copy `/work/amulet/hooks_v2_work/make_refs.sh`, logs `make_refs_<build>.log`): a copy of the tree with every v2-touched file restored to the v1+resolve snapshot plus the 2026-10-30 IEW wake fix. SpecLFB: `build/X86/gem5.opt.simspect-hooks-v1-resolve-wake-20261030` (the binary just before v2).
- `check_v2_trace.py` hard checks: META header `ver=2` with the right build; every line parses; v1 fields first; no `line=0x0` on squash-time releases/skips; no fill id is the cause of two evicts; at most one `cleanup_done` per squash id; every post-squash SB fill has a release.
- Results 2026-11-08 01:04 UTC (all `ok`, ticks new = ref, non-simspect lines identical, `parse_pipeview` identical, all hard checks pass):

| case | build | test | sim ticks | events |
|---|---|---|---|---|
| inv_uv1 | InvisiSpec Spectre | STT_6 inst-002014 | 5691000 | 2189 |
| inv_fut | InvisiSpec Futuristic | inst-002014 | 5699500 | 2211 |
| inv_014986 | InvisiSpec Spectre | inst-014986 | 5699500 | 2256 |
| cln_uv4align | CleanupSpec | uv4align | 1252000 | 170 |
| cln_uv4split | CleanupSpec | uv4split | 1251500 | 173 |
| cln_uv5clean | CleanupSpec | uv5clean | 1378000 | 243 |
| cln_inst002014 | CleanupSpec | inst-002014 | 6383500 | 2058 |
| lfb_uv6x | SpecLFB | uv6x | 1110500 | 327 |
| lfb_uv6dep | SpecLFB | uv6dep | 1109500 | 275 |
| lfb_inst002014 | SpecLFB | inst-002014 | 6227500 | 1169 |

- The v1 cases that existed on 2026-10-28 give the same ticks as then (inv_uv1 5691000, cln_uv4align 1252000, cln_uv4split 1251500, cln_uv5clean 1378000, lfb_uv6x 1110500, lfb_inst002014 6227500).
- `python3 STAGE3_gem5/tests/test_check_footprint.py`: 29 tests pass, including `TestRealTracesV2` (same leak verdicts on the v2 traces of inv_uv1, lfb_uv6x, cln_uv5clean, cln_uv4split, inv_fut; fixtures `STAGE3_gem5/tests/fixtures/<case>.v2.pipeview.txt.gz`).
- Example lines (cln_uv5clean): `L1D:cleanup_req:line=0x4000:seq=35:...:sq=4:...:mode=exec:lvl=MEM:rb=0x3000`, `L1D:cleanup_restore_req:line=0x3000:...:ev=Load_ROLLBACK:st=NP:nst=IS` at 1295500, `L1D:cleanup_restore:line=0x3000:...:req=rollback:ev=Data_Exclusive:st=IS:nst=E` at 1303500, `L1D:cleanup_done:...:sq=3:...:bufd=21:merged=2` and `...:sq=4:...` at 1311000. (inv_uv1): `SB:buf_release:line=0x3dc0:seq=576:...:sq=4:...:why=squash:filled=1:half=lo:sqseq=564`, `L1D:miss:line=0x3dc0:seq=576:...:req=specld:msg=SPEC_LD:addr=0x3de8:size=8:ev=SpecLoad:st=NP:nst=IX`.

## Cache setup strategies

Run-config knob `gem5.cache_setup` (2026-11-08, cache-setup session), next to the timing knobs (`fnc_commit_stall_cycles`, branch forces). `pipeline._build_gem5_env` turns it into `SIMSPECT_CACHE_SETUP`; `gem5_common.process_one` applies it through `STAGE3_gem5/cache_setup.py`; `testrun.py` writes it into the campaign `manifest.json` and every record carries `cache_setup` (plus `cache_setup_info` when not warm). Absent = `warm`.

Why: the Stage-2 prologue zero-fills every sandbox array with stores and then runs an `mfence` barrier (`parsexml.py` "Prologue → test region barrier"), so every sandbox line is hot in L1D when the test region starts. That hides any bug that needs a line to be absent, e.g. CleanupSpec UV3 (a squashed RMW's write-intent fill is never cleaned): the RMW line is already cached, so there is no install to clean.

Strategies (a registry, `cache_setup.STRATEGIES`; a new one is one `payload(frame) -> asm lines` function):

- `warm`: today's behavior. The `.s` is untouched and `build_binary` runs exactly as before; the binary is byte-identical (unit test `test_warm_byte_identical`).
- `cold`: right after the prologue barrier, `clflush` every 64-byte line of the test function's data region, one flush in flight at a time, then `mfence`. The data region is the whole stack frame, derived from the prologue only (never from the transmitter or any one instruction): with a frame pointer (`push %rbp; mov %rsp,%rbp; push*P; and $-A,%rsp; sub $N,%rsp`) it is `[rbp-(8P+A-1+N), rbp+16)`, i.e. allocas, realignment gap, saved registers, saved rbp and return address; for a leaf without frame pointer it is `[rsp-128, rsp+N+8P+8)` (red zone included when used). Every direct rsp/rbp operand in the function must fall inside it, else the test errors. rip-relative data (globals) would be refused; no current corpus has any (checked on 1,500 tests of STT_6, STT_6_rmw, Recon_6, SPT_6_oneLP, STT_6_fp). Pacing: each `clflush off(%rbp|%rsp,%rax)` takes its index from `%rax = 0` loaded after the previous flush's `mfence` through 64 dependent `leaq (%rax,%rax),%rax`; `%rax` is saved to and restored from a `.bss` slot outside the frame (lea and mov write no flags; no other register is touched). Pacing exists because back-to-back flushes panic CleanupSpec's Ruby with `L2_TBEs=2` (below).
- `cold_burst`: the same lines flushed back to back with `disp(%rsp|%rbp)` operands and one final `mfence`. Not for CleanupSpec footprint configs.
- `random` (2026-11-09, cache-random session; **the default for CleanupSpec and SpecLFB only**, Anna 2026-11-09; every other build stays `warm`; not a standard run dimension): each test runs `warm` or `cold`, chosen per test by `cache_setup.choose(stem, seed)` = bit 0 of `sha256(seed + NUL + stem)`, with any `__<suffix>` dropped from the stem so every sweep grid point of a test gets the same choice. Seed: run-config `gem5.cache_setup_seed` (→ `SIMSPECT_CACHE_SETUP_SEED`), default `cache_setup.DEFAULT_SEED = "simspect-cache-random-v1"` (the two footprint configs set it explicitly). About half cold (unit test: within 4σ on 20,000 stems; 296/590 on the RMW sample stems). Every record carries the strategy actually used (`cache_setup: warm|cold`) plus `cache_setup_mode: "random"` and `cache_setup_seed`; `pipeline._aggregate_sweep_results` copies these three keys into `window-results.json` rows for non-warm runs (warm runs unchanged); `testrun.py` writes `cache_setup_seed` into the manifest. A test that resolves to warm is built exactly as in a warm run (byte-identical binary, unit test `test_random_warm_half_byte_identical`). Refused wherever `cold` is. Reproduce one test's choice by hand: `python3 STAGE3_gem5/cache_setup.py choose <stem> [--seed S]`, then run it with `gem5.cache_setup` set to that strategy. Diagnostics read the per-record `cache_setup` (`diag_uv3_rmw.py`; `bucket_hits.py` writes a `by_cache_setup` split into `buckets/summary.json`). Tests: `RandomTests` and `test_random_*` in `STAGE3_gem5/tests/test_cache_setup.py`.
- `l1_evicted` (out of L1D, still in L2): not implemented. It needs an eviction sweep sized to each config's L1D and is not exact under random replacement (CleanupSpec); follow-up.

PCs: inserting code shifts every later PC, so `cache_setup.prepare` builds the warm binary and the rewritten one, then re-resolves the annotation: the code before the insertion must be unchanged, the code after it must be the same instruction stream shifted by one constant (direct branch targets included), every `__litmus_*` label must move by that constant, and every annotation address (any `addr` / `*_addr` field, walked with `make_rmw_corpus.addr_fields`) must land on the same instruction; the `*_hex` siblings follow. Any deviation is a per-record error, never a guess. Checked on 1,666 real tests (all 5 corpora, both modes, both strategies): 0 failures. Unit tests: `STAGE3_gem5/tests/test_cache_setup.py` (fixtures include a BTB-forced `mispredict_taken` test and an `stl_bypass` test with `stl_annotations`). `gem5_common.build_binary` refuses to build when `SIMSPECT_CACHE_SETUP` is not `warm` unless called through `prepare`, so the legacy direct checkers (`check_ld_cleanupspec.py`, `check_ld_invisispec_compound.py`, `hook_audit.py`, `diag_ld_cache_reach.py`) fail loudly instead of running warm with stale PCs; `hook_audit.py` records `cache_setup: warm`.

Per-build support, smoke 2026-11-08 (`STAGE3_gem5/triage/cache_setup_20261108/smoke_cache_setup.py`; two fixture tests per build; "miss" = every flushed line that the test touched again missed on its first demand access, from the `Cache` debug flag on classic builds or `ProtocolTrace` on Ruby builds). Unsupported builds are refused at checker start (`cache_setup.CLFLUSH_UNSUPPORTED`):

| build (runconfig) | clflush | result |
|---|---|---|
| CleanupSpec, footprint config (`L1_TBEs=8, L2_TBEs=2`; `L2_TBEs=3` since 2026-11-09, below) | works paced | `cold`: 37/37 flushes, touched lines miss in L1D and L2. `cold_burst` panics: `MESI_Two_Level-L2cache.sm:308: Invalid L1 forwarded request type` (a PUTFLUSH hits an L2 Resource Stall and is re-dispatched to a handler without PUTFLUSH). In campaigns, cold also makes CleanupSpec's own undo panic the same way with a PUTINV: 326/590 plain STT_6 tests, 1/590 STT_6_rmw (more lines to clean concurrently once the sandbox is cold) |
| CleanupSpec, amulet_parity config (TBEs 256) | works | miss in L1D and L2 |
| SpecLFB (classic) | works | miss in L1D and L2 |
| /work/stt, /work/stt-master, /work/gem5-recon-modded (classic, no L2 in these configs) | works | miss in L1D (to memory) |
| InvisiSpec (Ruby MESI_Two_Level) | no-op | no Ruby request is issued for a clflush (RubyPort lacks CleanupSpec's CleanInvalidReq→FlushReq conversion); L1D demand misses unchanged. Refused |
| amulet-STT (Ruby MESI_Two_Level) | no-op | same as InvisiSpec. Refused |
| /work/gem5-recon-ruby3 (Ruby MESI_Three_Level) | no-op | first access after the flush hits M in L0. Refused |
| /work/gem5-spt | panics | `commit_impl.hh:1610: Assertion srcRegTaintVec != nullptr` when the clflush commits. Refused |

No eviction-buffer fallback is implemented for the four unsupported builds (DECIDE in `URGENT_TODO.md`).

**CleanupSpec cold crash fixed by `L2_TBEs=3` (2026-11-09).** With `--L2_TBEs=2`, cold made CleanupSpec's own cleanup panic (`L2cache.sm:308`, PUTINV meets an L2 Resource Stall) on 326/590 plain STT_6 tests. TBE sweep on those 590 stems (`STAGE3_gem5/triage/cache_setup_20261108/tbe_sweep.sh`; cafe2 `results/STT_6_rmwstems_cleanupspec_tbe_l2_{3,4,8,16}_dc_2_{cold,warm}__latest`, summary `results/STT_6_cleanupspec_tbe_sweep_20261109.json`): `L2_TBEs` 3, 4, 8 and 16 give 0/590 errors cold (10 hits, the same stems as the 264 survivors at 2), and warm gives 13 hits, the same 13 stems as `L2_TBEs=2`, at every value, so UV4 sensitivity to L2 TBE pressure did not show on this sample. The footprint config now uses `--L2_TBEs=3` (smallest crash-free; `DC_TBEs` stays 2), following the principle that our configs use crash-free settings; the AMuLeT-parity config keeps TBEs 256.

**AMuLeT's own initial cache state (read 2026-11-09, cafe2 `/work/amulet/`):** it differs per build. SpecLFB AE (`amulet-gem5-SpecLFB_AE-v1.1/src/revizor_ipc/revizor_ipc.cc:317-319, 350-352`, `RevizorIPC::traceTestCase`): write back, then `memInvalidate()` L1D, L1I and L2 before every test case, so every test starts fully cold. CleanupSpec AE (`amulet-gem5-CleanupSpec_AE-v1.1/src/revizor_ipc/revizor_ipc.cc:304-327`): no reset; the input is memcpy'd into the sandbox in host memory and cache state carries over from earlier test cases. InvisiSpec/STT AE and upstream `amulet-gem5` (`configs/revizor/ipc_base_x86.s:89-117`): before each test, an L1D thrash loop (L1D_ASSOC accesses to addresses mapping to each sandbox set), so the sandbox is out of L1D (an `l1_evicted`-like state). Our parity configs run `warm`, so they differ from AMuLeT here (DECIDE in `URGENT_TODO.md`).

## Rebuild

`gem5-hooks/verify/build_simspect_hooks.sh <InvisiSpec|CleanupSpec|SpecLFB> [tag]` (copy `/work/amulet/build_simspect_hooks.sh`; log `/work/amulet/rebuild_<build>_simspect_hooks_<tag>.log`; `J=` sets scons `-j`). v2 logs: `..._v2fix_20261107.log` (InvisiSpec), `..._v2_20261030.log` (InvisiSpec/CleanupSpec, the first v2 build), `..._v2_20261107.log` (SpecLFB). The build script's END line is missing from the InvisiSpec v2fix log (I killed the wrapper shell while its scons finished; the binary is from that scons run, 2026-11-08 00:56 UTC).

## Backups and diff chain

- Binaries in each `build/<ISA>/`: `gem5.opt.pre-simspect-hooks-20261028` (pristine: every result before 2026-10-28), `gem5.opt.simspect-hooks-v1-20261028` (v1), `gem5.opt.pre-resolve-hooks-20261030` (= v1), `gem5.opt.simspect-hooks-v1-resolve-20261030` (v1 + resolve hooks, no wake fix), SpecLFB `gem5.opt.simspect-hooks-v1-resolve-wake-20261030` (v1 + resolve + wake), CleanupSpec `gem5.opt.hooks-v2-partial-20261030` (the 2026-10-30 21:27 partial v2), InvisiSpec `gem5.opt.hooks-v2-broken-20261030` (the one that panicked). Current `gem5.opt` = v2.
- Sources: pristine `/work/amulet/backups/<build>-pre-simspect-hooks-20261028.tgz`; full v1+resolve `src/` snapshot `/work/amulet/backups/<build>-simspect-hooks-v1.tgz` (taken 2026-10-30 19:38, after the resolve hooks; extracted in `/work/amulet/hooks_v2_work/v1snap_<build>/`); pre-resolve `/work/simspect_backups/resolve-hooks-20261030/`; SpecLFB just before v2 `/work/amulet/hooks_v2_work/SpecLFB-src-before-v2-20261107.tgz`.
- Diffs in the repo, applied in order from the build root: `gem5-hooks/amulet-<build>/simspect_hooks.diff` (pristine → v1, `patch -p1`), `resolve_hooks.diff` (v1 → resolve, [`RESOLUTION_HOOKS.md`](RESOLUTION_HOOKS.md)), `hooks_v2_vs_v1resolve.diff` (v1+resolve snapshot → v2; it also contains the 3-line IEW wake fix, which belongs to the resolve work).

## History

- 2026-10-28: v1 built and verified (`claudelog.md` "simspect-hooks").
- 2026-10-30: the v2 agent edited the InvisiSpec/CleanupSpec sources and died (API error) mid-build, leaving nothing on the Mac. The resolve-hooks session's 21:27 rebuild compiled those unverified edits; the InvisiSpec binary then panicked on every run (`panic: Invalid range for type MachineType`) because the new `hitCallback` hook called `MachineType_to_string(mach)` on L1 hits, where `mach` is not a valid machine type. CleanupSpec ran.
- 2026-11-07: recovered the partial v2 from the cafe2 trees, fixed the panic (`simspectLvlOf` in `Sequencer.cc` converts `mach` only when `externalHit`), wrote SpecLFB v2, built references, verified (above).
