# Audit: SpecLFB SimSpect print hooks + the "second spec load is isUnsafe=0" claim (2026-10-28)

**Status:** done (12-minute audit-only pass; no code, config, spec, or gem5 file was touched; nothing built or run). Sources read: `wiki/design/SIMSPECT_HOOKS.md`, `gem5-hooks/amulet-SpecLFB/simspect_hooks.diff`, and on cafe2 `gem5_dev:/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/src/` (`cpu/o3/dyn_inst.hh`, `cpu/o3/rob.cc`, `cpu/o3/lsq_unit.cc`, `cpu/o3/lsq.cc`, `mem/cache/base.cc`). All line numbers below are in that remote tree (hooked source).


**Update 2026-11-07 (hooks v2 trace):** on `lfb_uv6x` the mechanism is the order of the two walks, not the load-queue-head skip: the ROB walk set the sticky `PrevNoUnsafe` on both speculative loads (seq 28, 29) at tick 92500, one cycle before the LSQ walk set `cusl` on seq 28, and neither load was the LQ head (`LSQ:unsafe ... lqhead=0`). Trace and lines: `wiki/design/SIMSPECT_HOOKS.md` "What the v2 trace already showed".
## Update 2026-11-08: STT_6 sample through hooks v2, a NEW candidate bug ("jmp-shadow"), and the walk-order (c) evidence

**For Anna, read this first.** A 3000-test STT_6 run (testsets_latest, current STT_6.als, fixed seed 20261107, 1500 ld-kind tests per branch mode) on the v2 SpecLFB binary, scored by `check_footprint.py` + `specs/leakage/speclfb.json` (L1D/L2 fill or evict by a squashed load inside the lc/fnc window), ran with 0 errors: **1300/1500 hits in mispredict_not_taken, 1452/1500 in mispredict_taken.** The run mirrors the `results/STT_6_speclfb_full` config (1 kB/2-way L1D, `--l2cache` 2 MB/16, resolve stall 5000; gem5 argv, staged ann and `config.ini` in `proof/`). Every in-window footprint is a `req=ld` fill; no model artifacts or checker false positives were found. Everything is on cafe2 in `/tests/simspect_fixed_20261030/results/STT_6_speclfb_v2hooks__20261107/` (`README.md`, `triage/`, `pipeviews/` of every hit).

**Buckets per hit (first that applies):**

| mode | hits | UV6 as published (first spec load) | walk-order (later load, sticky PrevNoUnsafe) | NEW jmp-shadow | NEW other (same mechanism, delayed) |
|---|---|---|---|---|---|
| mispredict_not_taken | 1300 | 1143 | 157 | 0 | 0 |
| mispredict_taken | 1452 | 1142 | 162 | 144 | 4 |

The first speculative load is usually the load-queue head (`lqhead=1`), which never gets CUSL because the LSQ walk starts at `++iter` (`lsq_unit.cc:877`). That is UV6 as AMuLeT publishes it. The model's transmitter is among the offending loads in 911/1300 and 937/1452 hits (D2 evidence), but in only 2 of the 148 NEW hits.

**NEW candidate bug, jmp-shadow (verified in source on 2026-11-08 by the hooks-v2 session).** In `ROB::updateSafeState` (`/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/src/cpu/o3/rob.cc`, the control branch of the walk loop after the load block, around `:532-565`), an unresolved control instruction first sets `prevBrsResolved = false`. But inside `if(!prevBrsResolved){...}` the code then *assigns* `prevBrsResolved = inst->isDirectCtrl() && inst->isUncondCtrl()` (or, through the mnemonic fallback, `prevBrsResolved = true` for any `*_I` CALL or JMP). The comment cites DOLMA: direct unconditional jumps are not unresolved branches. The intent is that such a jump should not *make* the state unresolved. The assignment instead *resets* the false left by an older unresolved conditional branch, so every load after any direct `jmp`/`call` in the shadow is treated as "prior branches resolved", never gets CUSL, and fills the cache. SpecLFB's own rule (§6.2.2, p638) makes a load safe only "if there are no older control instructions that are unresolved".
- **Clean A/B demo:** `lfb_probe/uv6jmp.s` is `uv6lfb.s` plus one `jmp` to the next instruction.
  - Without the jmp, the later loads print `LSQ:unsafe … unsafe=1:cusl=1:…:prevbrsres=0` and are bounced, never filled.
  - With it, the same loads print `unsafe=0:cusl=0:…:reallyunsafe=1:prevbrsres=1` (seq 48, 49, 51, 54, at tick 167000-168000) and fill L1D before the squash at 1094500.
  - check_footprint flags it.
- **In the sample:** only `mispredict_taken` contains a jmp in the shadow: the function-epilogue `jmp ftbypass0`, followed by stack pops at line 0x3d40.
  - Across loads with a `JMP_I`/`CALL_NEAR_I` in the shadow, only 6 of 6081 had `cusl=1`.
  - Example `inst-016567`: the branch at 0x401c4f is held to 6213000; `JMP_I` is fetched at 3710500; `LSQ:unsafe seq=576 … cusl=0 … prevbrsres=1` at 3786000; `L1D:fill line=0x3d40 seq=576` at 3798000.
  - The 4 "NEW other" hits are the same: a load held only by mUSL is re-sent when the store resolves and fills while the branch is still held.
- **Not yet done:** a check against the original SpecLFB artifact (this tree is AMuLeT's AE copy) and against DOLMA's code, which the comment says the logic comes from. Until then it is a candidate implementation bug, not a confirmed one. DECIDE in `URGENT_TODO.md`.

**Walk-order DECIDE, option (c) done.**
- `--debug-flags=O3PipeView,Speclfb,LSQUnit` on `uv6x` lines up exactly with the v2 lines, and the simspect lines are md5-identical to the verify run, so the extra flags change nothing:
  - the native `Inserting load` for sn 28/29 and the LSQ walk's `Set unsafe` are at 93000;
  - the v2 `usl_flag f=prevnounsafe by=rob` for both is at 92500.
- **Structural cause:** `renameToROBDelay=1` is less than `renameToIEWDelay=2`, so the ROB walk sees a load one cycle before it is in the LQ. Within a cycle IEW runs before commit, and `PrevNoUnsafe` is never cleared.
- **At scale,** for fills by a non-head load with `unsafe=0 prevnounsafe=1` (not_taken / taken):
  - 1331 / 1149 such fills;
  - 876 / 876 where the older load is the never-flagged LQ head;
  - 455 / 273 with the 1-cycle lag, where the older load is flagged exactly 500 ticks after the younger load's `prevnounsafe=1`.
- **Scope beyond the paper:** in `uv6dep` the second load translates about 93 cycles after the first got CUSL and is still `unsafe=0` (fills at 247000/257500). AMuLeT's text claims single-load leaks only.
- **Agent's recommendation:** report it as UV6's mechanism (the same `PrevNoUnsafe` → `reallyUnsafe` code AMuLeT names, Fig. 8a p12) with a wider scope than published, and count jmp-shadow separately.

**LFB events never fire (0 in 3000 tests + 5 demos), and by code reading the LFB park path is unreachable in this build.**
- **Why:**
  - USL is set only together with HitUSL (`lsq.cc:1049-1051`).
  - A HitUSL miss clears HitUSL (`base.cc:1943`), allocates no MSHR (`base.cc:604-617`), and the port refuses the request (`base.cc:3236-3238`), so the load becomes `SpeclfbStalled` (`lsq_unit.cc:1891-1897`).
  - The replay arrives as `usl=1 hitusl=0`, and `base.cc:597-602` clears USL before the MSHR is allocated.
  - So `base.cc:853` (`isUSL && !isHit_USL`) never parks.
- **What is visible instead:** the hold, as `L1D:miss … usl=1:hitusl=1:touch=0` plus `LSQ:issue sent=0:bounced=1`. No `unsafe=1` load ever filled while still unsafe (5578 + 700 held loads).
- **Docs to correct (not yet done, pending Anna):** `wiki/findings/mdsToRead/PROTECTION_SCOPE_TABLE.md` ("an unsafe miss is parked in refillBlocks") and the `not_covered` note in `specs/leakage/speclfb.json`.

**Hook gaps (none blocks these findings):**
- `setPrevBrsResolved` (`rob.cc:464`) and the jump reset are visible only as `prevbrsres=` on `LSQ:unsafe`.
- `setPrevStoreResolved` (`rob.cc:476`) and `SpeclfbStalled` set/clear (`lsq_unit.cc:1896`, `rob.cc:510-511`, `lsq_unit.cc:974-975`) are not printed.
- A replayed held load prints no new `LSQ:unsafe`. Adding the flags to `LSQ:issue` (`lsq_unit.cc:1445`) would fix that.

**Old numbers:** 68/300 (access-keyed, counted hits) and 11/12 (install-keyed demo) vs 86.7% / 96.8% install-keyed now (D3 evidence).

## Part 2 (claim check): why the SECOND speculative load also gets isUnsafe=0

**Verdict: the claim is mechanistically real, and it is broader than "first load only" (UV6) in a specific, predictable situation: when the first speculative load is the head (oldest entry) of the load queue.** It comes from three code facts that combine.

1. `isUnsafe()` needs `reallyUnsafe` (`cpu/o3/dyn_inst.hh:640-642`): `isUnsafe = !isSquashed && (isCUSL || ismUSL) && isreallyUnsafe`. A load with an unresolved older branch (CUSL) is still treated as safe unless `reallyUnsafe` is also set. This is SpecLFB's intended "first USL is allowed" rule (UV6).
2. `reallyUnsafe` is set only when the load is NOT `PrevNoUnsafe` (`cpu/o3/lsq_unit.cc:900-912`), and `PrevNoUnsafe` is set by the ROB walk (`cpu/o3/rob.cc:463-469`) for every load that has no older load flagged CUSL/mUSL at the time of that walk (`rob.cc` sets `preNoUnsafe=false` only after a load with `ismUSL()||isCUSL()`). `PrevNoUnsafe` is **sticky**: it is set at `rob.cc:464` and there is no clear anywhere in `cpu/o3/` (grep: only `dyn_inst.hh:177,876,877`, `rob.cc:464`, `lsq_unit.cc:902`). Once a load is ever seen with no flagged older load, it stays "not really unsafe" for life.
3. The ROB walk never SETS CUSL/mUSL (it only clears them, `rob.cc:443-458`); only `LSQUnit::updateSafeState` sets them (`lsq_unit.cc:852-858`, `889-894`). And that loop is `auto iter = loadQueue.begin(); while (++iter != loadQueue.end() && iter->instruction())` (`lsq_unit.cc:815-818`): the pre-increment **skips the load-queue head**. So the oldest load in the LQ never gets CUSL or mUSL, so it can never flip `preNoUnsafe` to false in the ROB walk.

Consequence (mechanism): if the first speculative load L1 is the LQ head (no older uncommitted load in the LQ, e.g. the window is made by a stall hook or a non-load branch condition rather than by a missing condition load), L1 is never CUSL (head skip), so in the ROB walk nothing before L2 is flagged, so L2 gets `PrevNoUnsafe` (sticky) and `reallyUnsafe` is cleared, so L2 is `isUnsafe=0` and its request is not tagged (`cpu/o3/lsq.cc:1009-1027`: `setUnsafe()/setHitUSL()` only if `isUnsafe()` at translation; otherwise cleared). L2 then fills L1D normally (matches `lfb_uv6x`: seq 28 and seq 29 both `L1D:fill`, both `isUnsafe=0` in the SpecLFB trace). The third load can be unsafe only if L2 already had CUSL set by an LSQ walk before the ROB walk that first saw L3; otherwise L3 is stuck `PrevNoUnsafe` too (ordering race between `ROB::updateSafeState`, called from `commit.cc:1403`, and `LSQ::updateSafeState`, called from `iew.cc:1514`).

When L1 is NOT the LQ head (an older load, e.g. the branch-condition load that is still missing, sits in the LQ), L1 gets CUSL, so L2 sees a flagged older load and becomes `reallyUnsafe` (UV6 exactly as published: first load only). So the "second load too" behavior is an implementation artifact (head-skip off-by-one plus sticky `PrevNoUnsafe` plus walk ordering), not the paper's design rule.



**Caveat (what was not done):** this is a code reading, not a run. The ordering race for the third load, and whether a given SimSpect test has its first spec load at the LQ head, should be confirmed with `--debug-flags=Speclfb` on one test (look for the `Checking updateSafeState` lines: the head load never prints them, `lsq_unit.cc:822`). The verification note in `SIMSPECT_HOOKS.md:102,114` ("every spec load `isUnsafe=0`", "both loads `isUnsafe=0`") fits this mechanism.

**Consequence for SimSpect:** SpecLFB "leaks" on the second (transmitting) spec load in gadgets whose window is not opened by a pending older load are an implementation artifact of the AMuLeT SpecLFB code (`lsq_unit.cc:817` head skip and the sticky `PrevNoUnsafe` at `rob.cc:464`), not the published UV6 rule. They should not be counted as UV6. It also explains why the `LFB` hooks were never exercised in verification: with the window opened by a stall hook, no spec load ever becomes `isUnsafe=1`. To exercise the LFB hooks, a gadget needs an older load still in the LQ (for example a missing branch-condition load) plus at least two younger spec loads.

## Part 1: hook audit, ranked findings

Overall: the hooks are print-only as claimed for every site read. Every hook reads state and calls `DPRINTFR` or edits hook-private maps (`simspect_fill`, `simspect_lfb`, `simspect_mshr`, `g_lineAttr`); none writes cache, packet, MSHR or CPU state, and none changes control flow (the `allocateBlock` early return at `base.cc:2157-2160` only clears the hook flag before the native `return nullptr`).

1. **MEDIUM: the LFB refill path can read a freed packet in the hook.** Native SpecLFB parks `pkt` in `refillBlocks` and then runs `delete pkt` (`base.cc:838-846`), so `reFillBlockInfo.rpkt` is dangling when the refill later calls `handleFill(rpkt, ...)` (`base.cc:647`). The hook avoids it only while the per-(cache, PC) deque has an entry: then `allocateBlock` uses `simspect_refill` (`base.cc:2145-2148`). If the deque is empty for a matching native entry, the hook falls back to `simspectReqAttr(pkt)` on the freed packet (`base.cc:2150`). The deque and `refillBlocks` are pushed together only while `SimSpect::enabled()` (`base.cc:827`), so they get out of step if O3PipeView is switched on mid-run (`--debug-start`) after an entry was parked. Native code reads the same freed packet, so this is a native use-after-free that the hook makes worse in that one case, not a new behavior change. In normal SimSpect runs (flag on from tick 0) the deque stays in step: entries are removed only at the refill (`base.cc:664`, one per request, `break` at `base.cc:670`), and both sides are FIFO by PC.
2. **MEDIUM: an LFB entry is never released at squash, so `LFB:buf_fill` can have no matching `buf_release`.** `refillBlocks` has no removal path except the same-PC refill (grep: `base.cc:621,664,838` only). A squashed unsafe load's line stays parked until a later load with the same PC arrives (it can be much later, for example a later loop iteration, and then that later load's request fills the line). The hook prints the release at that time, attributed to the parked load's seq (`simspect_refill`), not to the load that triggered it. This is a correct trace of native behavior, but `SIMSPECT_HOOKS.md:82` should say so: the line can enter L1D long after the squash, and `seq` on that fill is the original spec load, not the one that caused it. No `sq=` is given on the LFB release (unlike the InvisiSpec `SB:buf_release`).
3. **LOW: evictions without a fill context are not printed.** The evict hook requires `simspect_fill.active` (`base.cc:1325`), and `simspect_in_evict` suppresses the `inv` print (`base.cc:1334-1336`, `2246`). `handleEvictions` is also called by `updateCompressionData` (compressed caches, data expansion), and there a removal would print nothing. No compressor is configured in SimSpect runs, so this is a latent gap, not a live one.
4. **LOW: `repl_touch` has no per-line fallback.** `base_set_assoc.hh:155-167` uses only `pkt->req`, so a writeback or other packet that hits L2 prints `seq=-`, while `fill`/`evict` use the per-line map (`simspectReqAttr`, `base.cc:112-129`). This contradicts `SIMSPECT_HOOKS.md:90` slightly. The hook is placed correctly: inside `if (update_metadata)` right after `replacementPolicy->touch` (`base_set_assoc.hh:148-153`), so SpecLFB's no-update USL hits correctly print nothing.
5. **LOW: struct naming is by substring.** `simspectStruct` (`base.cc:74-83`) maps any name containing `l2` to L2, checked after `dcache`/`icache`. This is fine for `system.cpu.dcache`/`icache`/`system.l2`. A name like `l2bus` never reaches a cache. `MSHR_OTHER`/`LLC` are fallbacks only.

Coverage checked as OK (by code reading): all tag allocations go through `allocateBlock` (demand fills via `handleFill`, writeback/clean-writeback allocation in `access`, the LFB refill), so `fill` covers L1D, L1I and L2 alike (one `BaseCache` class, separate `this`). Replacement victims print `evict` with `cause` = the fill id, which is reserved before `handleEvictions` (`base.cc:2140-2162`), so the cause link is exact. Failed allocation (`!victim` or victim with a pending MSHR) prints neither fill nor evict, which is correct. `handleFill` with `allocate=false` uses `tempBlock` and prints nothing, which is correct because no tag was allocated (`blk != tempBlock`, `base.cc:2246`). Uncacheable flush, snoop, clusivity and `memInvalidate` all go through `invalidateBlock` and print `inv` with the per-line attribution. An evicted line's attribution moves to the evicting instruction (`base.cc:1331-1333`), so its writeback fill at L2 is attributed. MSHR `buf_fill`/`buf_release` hook `MSHRQueue::allocate`/`MSHRQueue::deallocate` (`mshr_queue.cc:95-140`). Parked LFB loads keep their MSHR (the park `return`s before `serviceMSHRTargets`, `base.cc:846`), so `MSHR:buf_release` comes at the refill, which matches native behavior. Prefetch `forceDeallocateTarget` also ends in `deallocate`. No prefetcher is configured.

Not checked (time): `base.cc:2110-2130` (SpecLFB's `wasVictimAccess` victim handling just before the hook context is set; the hook runs after it, so it can only affect which victim is printed, not miss one), `cache.cc` snoop paths, and the write buffer (`WriteQueue`, not exported by design).
