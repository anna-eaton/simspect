# Audit: SimSpect print hooks on the InvisiSpec build (2026-10-28)

**Scope:** adversarial read of `gem5-hooks/amulet-InvisiSpec/simspect_hooks.diff` (pristine vs hooked, tree `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1` on cafe2) against `wiki/design/SIMSPECT_HOOKS.md`. Audit only: nothing was edited, built or run. Line refs are `diff:<line>` (line in the .diff file) plus the hooked source file. Items marked *(verify)* are inferred from the diff and gem5 conventions, not confirmed in the tree.

## Verdict on behavior/timing

No hook found that can change simulated behavior or timing. Every hook is gated on `SimSpect::enabled()` (= `DTRACE(O3PipeView)`) and writes only file-static print-side state (`g_msg`, `g_trans`, `g_lineAttr`, `g_pendingFill`, `g_tbe`, `g_resident`, `g_lastStable`, `simspect_llcsb_live`). The SLICC codegen changes (`StateMachine.py` diff:~1000-1025, `PeekStatementAST.py` diff:~985) only insert calls: `beginTransition` after the existing `DPRINTF` and `endTransition` after the Valid/ResourceStall/ProtocolStall chain, before `return result` (the generated `doTransition` has no other return), and `noteMsg(in_msg_ptr)` after the reject check. No simulated field (TBE, cache entry, message) is written. The one unconditional write, `simspectInsertVpn = vpn` (`arch/x86/tlb.cc`, diff:~45), is a file static never read by the TLB. `TBETable::deallocate` calls the hook before its asserts (diff:~795), harmless. The hooks can only crash (e.g. a stale `m_pkt` deref in `noteRubyRequest`, diff:~403), not perturb timing.

## Findings, ranked

### 1. MEDIUM-HIGH: `SB:buf_release` at squash is printed before the `SB:buf_fill` of in-flight squashed loads, and covers only one line

`LSQUnit::squash` (hooked `cpu/o3/lsq_unit_impl.hh`, diff:~120-128) prints `SB:buf_release` when the squashed load has `needPostFetch() && !isExposeSent() && effAddrValid()`. `SB:buf_fill` is printed in `Sequencer::updateSBB` (diff:~806-812) when the spec data returns. For a spec load squashed while its SpecLoad is in flight, the Sequencer still receives the response and runs `updateSBB` (confirmed: `Sequencer::readCallback` calls `updateSBB(pkt, data, address)` for every `isSpec()` response with no squash check, `src/mem/ruby/system/Sequencer.cc:494-497`, and again for each merged `dependentSpecRequests` packet at `:535`), so the trace shows release then fill for the same seq, leaving a fill with no release. Any criterion that reconstructs SB occupancy (the SB holds data at time t) is wrong for exactly the squashed in-window loads it cares about. The release is a modeled notion: the Sequencer's `m_specBuf[idx]` entry keeps its data until reused, nothing is cleared at squash. Also: (a) only `physEffAddrLow` is released, so a split spec load's second SB block (`sbe.blocks[1]`) never gets a release; (b) the condition does not check that a SpecLoad was ever issued, so a load squashed after translation but before issue prints a release with no fill; (c) `physEffAddrLow` may still be 0 if the squash lands between `effAddrValid` and translation completion, printing `line=0x0` *(verify)*.

### 2. MEDIUM: stale `g_pendingFill` makes `cause=` ids collide and link UV1 evictions to later fills

`reserveFill` (`sim/simspect_hooks.cc`, diff:~1120) stores `(struct,line) -> (id, seq)`; `takeFill` consumes it only when the same `(struct,line)` fills. An InvisiSpec SpecLoad replacement (UV1) reserves an id that the spec load never consumes (it does not allocate in L1D). When the same seq later allocates that line in L1D (its expose/validate re-access), `takeFill` returns the old id, so the in-window UV1 evict's `cause=` points to the post-visibility expose fill. If that expose also replaces a way, `reserveFill` finds the pending entry with the same seq and returns the same id again, so two `evict` lines share one `cause`. This contradicts the doc's gap note "the evict's `cause` id never appears as a fill". The map also grows without bound with unconsumed reservations.

### 3. MEDIUM: clusivity removals print as `evict` (victim == line, cause=-), not `inv`

`onCacheDeallocate` (`SimSpectRubyHooks.cc`, diff:~566-585) chooses `evict` whenever the SLICC event name contains `Replacement`. Stock `MESI_Two_Level-L1cache.sm` handles "block is in the wrong L1" (ifetch to a line in L1D, or load to a line in L1I) by triggering `L1_Replacement` on the request's own address (confirmed in the InvisiSpec tree: `src/mem/protocol/MESI_Two_Level-L1cache.sm:479-481` and `:509-511`, "The block is in the wrong L1, put the request on the queue to the shared L2"). Then `incoming == line`, so the hook prints `evict line=X victim=X cause=-`. The doc's vocabulary puts clusivity under `inv`. A criterion counting replacement evictions will count these.

### 4. MEDIUM: one global, never-cleared message context (`g_msg`) drives all Ruby attribution

`g_msg` (diff:~347) is set at every peek in every controller and never reset when a peek or wakeup ends. Consequences: (a) `noteMsg` is placed before the `block_on` check in `PeekStatementAST.py`, so a message that is then delayed (`continue`) still becomes the context; (b) peeks inside actions overwrite it mid-transition; (c) any tag/TBE change outside a peek uses whatever message any controller peeked last. In current InvisiSpec code tag/TBE changes all appear to run inside peek-triggered transitions, so the practical exposure is small, but nothing enforces it. The fallback `getLineAttr` is the per-line "most recent" map, which mislabels when two in-flight requests target one line (the doc admits this).

### 5. LOW-MEDIUM: LLC-SB bookkeeping can drop releases

`simspect_llcsb_live` (`AbstractController.cc`, diff:~212) is one file-static set shared by every `AbstractController` instance, so multiple directories would alias `(core, idx)` keys. A ReadSpec that overwrites a live `(coreId, sbeId)` (diff:~250-260) prints a new `buf_fill` but no `buf_release` for the old line. The three `queueMemoryRead` clears are the only clear sites (confirmed: `AbstractController.cc:279,310,330`; the only other write is the fill at `:454`), so coverage of clears is complete, but the fill at `:454` overwrites without checking for a live entry. The fill prints `lineOf(addr)` but releases print raw `addr`. The doc says LLCSB printed nothing in verification, so none of this has been exercised.

### 6. LOW: squash-id attribution uses the load's seq, not the squash being applied

The `LSQUnit::squash` hook calls `sqForInst(ld_inst->seqNum)` (the latest squash in time whose seq is below the load) instead of `sqForSquashSeq(squashed_num)`. If commit records a second, older squash before IEW applies the first (commit-to-IEW delay), the loads squashed by the first get the second's `sq`. `ROB:squash` pc lookup (`rob_impl.hh`, diff:~150) prints `pc=-` when `squash_num` is not in the ROB.

### 7. LOW: TLB attribution and coverage

`setTlbCtx` is one global shared by ITLB and DTLB (diff:~95). It is exact in SE mode, where `TLB::translate` inserts synchronously, but in FS timing mode a page-walk `insert` would take the seq of whatever translated last. `flushAll`, `flushNonGlobal` and `demapPage` remove entries with no `inv` event.

### 8. LOW: small cache-path gaps

`CacheMemory::allocate` over a non-null `NotPresent` slot (gem5's warn_once protocol-bug path) replaces an entry silently. The allocate-time `touch` is not printed as `repl_touch` (consumers must infer it from `fill`). If an action throws (e.g. `RejectException` from a peek inside an action), `beginTransition` is pushed with no `endTransition`, leaving a stale `g_trans` top for any hook outside a transition. With `--debug-start`, bookkeeping that began mid-run is partial (TBE release `seq=-`, LLCSB releases skipped, `coh` seeded late).

### Struct/kind mapping

The mapping is correct as documented: Ruby L1 TBEs print `MSHR` for both I and D (no `L1IMSHR` on Ruby, so I-side TBEs are told apart only by `seq=-`), L2 is the LLC, `DIRTBE` is DMA-only in MESI. The struct for `coh`/cleanup decisions in L1 falls back to `g_msg.isIfetch`, so it inherits finding 4.

## Status

Written in a 12-minute budget. Confirmed on cafe2 (read-only grep/sed): findings 1 (Sequencer fill path), 3 (clusivity `L1_Replacement`), 5 (LLC-SB clear sites). Also confirmed the SB-hit `buf_fill` (`Sequencer.cc` ~`:680-700`) is correct: `sbb` there is the destination block `m_specBuf[idx].blocks[blkIdx]`, which really receives the copied data. Additional edge noted in that code: `updateSBB` matches only on line address, so a stale in-flight response whose LQ/SB index was reused by a newer load to the same line overwrites the newer entry's data and prints `buf_fill` with the old load's seq. Still unverified: 1(c) (`physEffAddrLow` = 0 window), finding 4's claim that all tag/TBE changes run inside peek-triggered transitions. `--debug-start` does not appear in `STAGE3_gem5/gem5_common.py`, so the partial-bookkeeping case in finding 8 does not arise in standard SimSpect runs.
