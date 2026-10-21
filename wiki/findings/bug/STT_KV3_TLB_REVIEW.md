# STT KV3 — speculative store leaks via the TLB (✅ EMPIRICALLY DEMONSTRATED + source chain)

**Status: HIT.** Source chain fully traced (below) AND demonstrated end-to-end on the live STT build
with a controlled gadget + a 2×2 control (`bug/kv3_demo/`): a speculative store fills the TLB for a
secret-dependent cold page under STT, while the load equivalent is protected. See "Status" at the end.


**For Anna. Claim up front:** STT's speculative-execution protection is **loads-only by
construction**, and a **speculative store translates its address at *execute* with no
deferral**, so a wrong-path store's TLB miss page-walks and **fills the TLB speculatively,
unprotected**. That secret-dependent TLB fill survives the squash = the AMuLeT **KV3** bug.
This is a **real STT defense-scope bug**, confirmed in STT's own source — and, unlike
CleanupSpec UV3 (which I showed is unreachable because cache writeback is post-commit), KV3 is
**reachable** because TLB translation happens pre-commit. Verdict: **real defense bug**, not a
SimSpect artifact. What's missing is a SimSpect *demonstration* (store-address transmitter +
multi-page sandbox + TLB watcher), enumerated below.

## Evidence — the full mechanism chain (all in `/work/stt/src`, re-checkable)
The TLB protection is keyed on **`req->isSpec()`**, and that flag is set on the **load path only**.
Each link verified:
1. **The TLB protects ONLY when the request is speculative.** `tlb.cc:338-347` — on a TLB miss:
   ```cpp
   if (!entry) {
       if (req->isSpec()) {                  // [SafeSpec] do not perform TLB fill for spec load
           specMisses++; DPRINTF(TLB, "Get a TLB miss for a speculative load …");
           return GeneralProtection(0);      // ABORT: no page-walk, no fill
       }
       // else: page-walk + fill the TLB  (p->pTable->lookup, …)
   }
   ```
2. **`Request::SPEC` is set ONLY in the load path.** `base_dyn_inst.hh:1162`, inside `readMem` and
   guarded by `if(!readyToExpose())`:  `req->setFlags(Request::SPEC);`. A speculative load's request
   is flagged spec → the TLB skips its fill.
3. **The store path never sets it.** `base_dyn_inst.hh:1236+` `writeMem` calls
   `initiateTranslation(req,…, BaseTLB::Write)` (translates at **execute**) and has **zero**
   `spec`/`expose`/`SPEC` mentions (vs 8 in `readMem`). So a store's request has `isSpec()==false`.
4. **⟹ a speculative store's TLB miss falls through to the page-walk + fill** (the `else` in link 1) —
   unprotected. Combined with `isTransmit()=isAccess()=isLoad()` (`base_dyn_inst.hh:675-676`, stores
   are never transmitters), STT simply doesn't cover stores in the TLB.
5. **Observable.** `tlb.cc:345` DPRINTF (the spec-load branch) + the `else` branch's
   "Handling a TLB miss for address %#x at pc %#x"; stat `spec_tlb_misses` (`tlb.cc:486`); the `TLB`
   debug flag traces every translation/walk/fill.

**This is the full chain, every link source-verified — KV3 is conclusively a real STT bug, not inferred.**

## Why reachable here but UV3 (CleanupSpec cache) was not
TLB translation is performed at **execute** (the LSQ needs the physical address for ordering /
forwarding), so a wrong-path store genuinely does the lookup and, on a miss, the page-walk +
TLB fill — *before* it is squashed. Cache writeback, by contrast, is **post-commit** (`canWB`
is set only in `commitStores`), so a squashed store never touches the cache. Same "stores are
unprotected" gap; different observable because of *when* the structure is touched.

## What it takes to DEMONSTRATE in SimSpect (mechanism already proven; these are the build asks)
1. **Store-address transmitter.** SimSpect's Alloy model emits `ld` / `br_x` transmitters only.
   KV3 needs a *speculative store whose ADDRESS is secret-dependent*. → either a new
   store-address transmitter in the model (**owner-gated `.als` change**) or an isolated
   bugsynth-style hand-crafted gadget (mispredicted branch → spec store to secret-indexed addr).
2. **Multi-page sandbox.** The secret-dependent store address must be able to **miss the TLB**
   (span >1 page / 4 KB) so the fill is secret-dependent; the current litmus sandbox is a single
   small stack buffer (one page) → no TLB miss.
3. **TLB watcher (per-defense, STRICT lc/fnc).** Key the leak on the spec store's page-walk / TLB
   fill in the `TLB` trace (or `spec_tlb_misses` delta), in the window `lc_retire < t < fnc_retire`
   with branches unresolved. Same source-event discipline as the InvisiSpec/SpecLFB/CleanupSpec
   watchers — detect at the TLB fill, not via a final-state diff.

## Status — ✅ EMPIRICALLY DEMONSTRATED (source chain + a controlled gadget with a 2×2 control)
Beyond the source chain, I built a controlled gadget (`bug/kv3_demo/`, reproducible via
`run_kv3_demo.py`) and demonstrated KV3 on the live STT build. The gadget: a mispredicted branch
(held unresolved via `resolve_stall_cycles=2000`) guards a speculative load of a tainted index, then
the **transmitter** accesses `kv_buf + index*4096` — a **COLD page** (`0x40b000`). Two variants
(identical except store vs load) × two schemes:

| transmitter | STT (`--scheme=2`) | Unsafe (`--scheme=0`) |
|---|---|---|
| **store** | cold page **TLB walk+fill** ✗ (leaks) | walk+fill |
| **load**  | **NO walk** ✓ (STT protects) | walk+fill |

Reading it: the **load** would leak (Unsafe walks the cold page) but **STT protects it** (no walk — the
spec load is held un-executed in the LSQ until the squash; trace shows `Inserting load …[sn:45]` at
153000 then `…squashed,[sn:45]` at 1155000, never an `Executing load` for it). The **store fills the
TLB identically under STT and Unsafe** — **STT does not protect the store = KV3**. The walk is genuinely
speculative: it happens at tick 212000 while the branch is held unresolved; the mispred squash is at
1154500 (= 154500 + 2000 cyc × 500 tick), so the store filled the TLB *inside* the speculative window
and the fill persists past the squash. The load-under-Unsafe control rules out a "gadget doesn't leak"
false positive. **Verified, not inferred.**

Remaining for a full pipeline integration (not needed to establish the bug): a model-emitted
store-address transmitter (so SimSpect generates these automatically) + a TLB watcher folded into the
sweep. The standalone gadget already demonstrates it end-to-end.

Build: `/work/stt` (has branch-ann + fnc-stall hooks + `TLB` flag + `spec_tlb_misses` stat). Gate:
STRICT lc/fnc. Cross-reference: `claudelog.md` 2026-06-08 KV3 entry; the parallel CleanupSpec UV3
why-not is in `results/STT_6_cleanupspec_residue/CLEANUPSPEC_RESIDUE_REVIEW.md`. This **revises** the
master accounting (`mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md`), which listed KV3 as "out of
formulation (TLB observation)": the TLB *is* observable and KV3 *is* reachable — only the
store-address transmitter (a model/bugsynth piece) is missing.
