# Footprint defenses: paper audit (InvisiSpec, SpecLFB, CleanupSpec)

**For:** Anna · **Written:** 2026-10-28 (paper-audit session) · **Status:** findings only. Nothing in `specs/`, the `.als` models, the run configs, or any gem5 tree was changed. The speculation-definition choice is still pinned; §6 lists the options without picking one.

**Sources (all read this session):**

- InvisiSpec: `~/Documents/quail/sources/papers/yan-2018-invisispec.pdf`. This is the authors' **corrected** version ("Correction: InvisiSpec…", UIUC i-acoma site, 15 pp.). The as-published MICRO 2018 version is next to it as `yan-2018-invisispec-original.pdf`. Both have the same threat-model text (§III-B is on p3 of each). One sentence (§VII, the MSHR one) is cut off in the corrected PDF's extracted text, so I quote it from the original, p10. Page numbers below are PDF pages of the corrected version unless I say otherwise. Note: the repo root also has `InvisiSpec_Making_Speculative_Execution_Invisible_in_the_Cache_Hierarchy-2.pdf` (IEEE copy, different md5). I did not use it.
- unXpec: `li-2022-unxpec.pdf` (HPCA 2022; see §4b).
- CleanupSpec: `saileshwar-2019-cleanupspec.pdf` (Georgia Tech memlab author copy, 14 pp.). PDF pages.
- SpecLFB: `cheng-2024-speclfb.pdf` (USENIX open access). I cite **printed** proceedings pages (631–648). Printed page = PDF page + 629, because PDF p1 is the USENIX cover.
- AMuLeT: `fu-2025-amulet.pdf` = arXiv 2503.00145**v1**, the only arXiv version (16 pp., carries the ASPLOS '25 header). I did not fetch or diff the ASPLOS camera-ready linked from the AMuLeT README. PDF pages.
- STT: `yu-2019-stt.pdf` (already local). PDF pages.
- Code (read-only, on cafe2 in `gem5_dev`): AMuLeT `/work/amulet-repo` and the three builds `/work/amulet/amulet-gem5-{InvisiSpec,SpecLFB,CleanupSpec}_AE-v1.1`. Our run launchers are in `/tests/simspect/results/STT_6_*`. `STAGE1_alloy/models/STT_6.als` was read, not edited.

## 1. Summary table

| defense | caches the paper protects | state protected | explicitly out of scope | caches AMuLeT checks | caches in our runs | speculation def vs STT_6 |
|---|---|---|---|---|---|---|
| **InvisiSpec** | Every level of the **data** cache hierarchy (L1D, L2, LLC), the **directory**/coherence state, and the **D-TLB** (§III-B p3; §VI-E3 p9) | presence/occupancy, **replacement**, **coherence** (§III-B p3; p5) | L1I and I-TLB (not described: fn. 2 p3); execution units, NoC, DRAM, SMT channels (§III p3); **MSHR contention** (§VII, orig. p10); physical channels | Final **L1D tags** (+ D-TLB, but with a 1-page sandbox "as the TLB is not protected"; L1I only in some campaigns). Never L2, directory, or replacement bits | `STT_6_invisispec`: **classic `--caches`, no `--ruby`**: L1I 32kB/2 + L1D 16kB/8, no L2. Defense cache logic is Ruby-only, so **inactive here**. `_compound`: Ruby MESI with L1D 1kB/2, L1I 32kB/2, L2 2MB/8, directory, TBEs=2 | Spectre-USL = STT_6's contract exactly (`--scheme=SpectreSafeInvisibleSpec`). STT_6 adds a taint precondition, so it **under-generates**. AMuLeT tested **Futuristic**, which is broader still |
| **SpecLFB** | **L1D** in the paper's design and RTL. The gem5 implementation applies the same check to **both levels (L1D + L2)** (p632, p640) | **presence only**: unsafe speculative loads that **miss** may not refill the cache, which also blocks the victim eviction (§5 p635; §6.1 p637) | **cache hits and replacement/LRU metadata** (§9 p643); TLB and port contention (§4 p635); value prediction not implemented (p637) | Final **L1D tags** (+ L1I + D-TLB in `ct-seq.yaml`, 1-page sandbox) | `STT_6_speclfb`: **classic `--caches` only**: L1I 32kB/2 + L1D 64kB/2, **no L2** (paper and AMuLeT both have L2) | Paper "unsafe" = control flow + memory order + consistency + exceptions, then narrowed to misses (MUSL). STT_6 = control flow only, plus taint. STT_6 **under-generates**. A transmitter that hits is out of SpecLFB's scope |
| **CleanupSpec** | **L1D** (invalidate the install, restore the victim) and **L2/LLC** (invalidate the install). L2/LLC **and directory** are randomized so their evictions are benign (p2; §3.1 p5) | presence (installs + L1 victims); **replacement** via random L1 replacement; **coherence** by delaying M/E→S (p2; §3.2 p6; §3.5 p7) | I-cache, TLB, branch predictor (p1 fn.; §2.1 p3); prefetcher (assumed off), DRAM row buffer, SMT port / NoC / DRAM contention, AVX, EM/power (§2.1 p3); **cleanup timing** acknowledged as future work (§4(b) p8) | Final **L1D tags** (+ L1I, which is how unXpec showed up). `cleanupspec_analysis.py` diffs L1D/L1I tag sets only. Never L2 | `STT_6_cleanupspec_residue`: Ruby MESI with L1D 2kB/4, L1I 32kB/2, L2 2MB/8, directory, TBEs=2. `Cleanup_FOR_L1L2` turns on **rand-L2 + random L1 replacement + L2 invalidate** | Paper: "all transient instructions potentially unsafe until they retire", and secrets "from the memory or from a register, or computed" (§2.1 p3). STT_6 = branch-only + taint from memory. STT_6 **under-generates** |

**Six things that are wrong or surprising in our current setup:**

1. **`STT_6_invisispec` (the main 1500-test InvisiSpec campaign) did not run the InvisiSpec cache defense.** Its `run_config.jsonc` `extra_args` are `["--scheme=SpectreSafeInvisibleSpec","--needsTSO=1","--allowSpecBuffHit=1"]` with no `--ruby`. `gem5_common.py:159-168` adds only `--caches`, so gem5 built classic caches. A grep of the InvisiSpec build's `src/mem/cache/` for `isSpec|SpecLoad|SPEC_LD|invisi` finds nothing: the invisible-load logic lives in the Ruby `.sm` files. The run's `RESULTS.md:4` says "Ruby `X86_MESI_Two_Level`". That is the binary, not the memory system that was simulated. Only `STT_6_invisispec_compound` (`--ruby`) exercised the defense. One part of InvisiSpec is still active on classic caches: its D-TLB "no fill for speculative load" path is CPU-side (`src/arch/x86/tlb.cc:341`).
2. **`STT_6_speclfb` has no L2.** `run_speclfb.py:96-103` passes no extra args, so the run is classic `--caches` with L1I + L1D only (L1D 64kB/2 are the SpecLFB build's `Options.py:184-189` defaults). The paper's gem5 evaluation applies SpecLFB "to both levels of the cache" with a 2MB/16-way L2 (Table 2, p640). AMuLeT always passes `--caches --l2cache` for classic builds (`executor.py:220-221`). The L2-level LFB check is therefore untested in our runs. Also, `specs/defense_units.json` unit 4 says "SpecLFB build, Ruby MESI", but the binary is `build/X86/gem5.opt` (classic).
3. **AMuLeT never observes L2, the directory, or replacement state, for any defense.** InvisiSpec and CleanupSpec both claim to protect L2/LLC. `executor.py:471-496` reads only `system.cpu.dcache` / `system.ruby.l1_cntrl0.L1Dcache` (and L1I), even though gem5's `serializeAllCaches` dumps every cache. The replacement-bits option is dead code: `executor.py:462` does `getattr(atk, "include_replacements", False)` on a **dict**, which always returns `False`.
4. **AMuLeT's paper says InvisiSpec's TLB "is not protected"** (§3.5 p7: "For InvisiSpec, CleanupSpec, and SpecLFB, we use a sandbox with 1 physical page (as the TLB is not protected)"). InvisiSpec's own paper protects the D-TLB (§VI-E3 p9), and the build implements it (`tlb.cc:341-346`). So AMuLeT's InvisiSpec campaigns do not test a claim the paper makes.
5. **UV2 (MSHR contention) is outside InvisiSpec's own stated scope.** Original p10 §VII: "contention on other resources, such as MSHRs or execution units, could slow down the receiver, but such side channels are considered out of scope in this paper (Section III-B)." AMuLeT counts it because it surfaces as an L1D-state difference. A criterion built from the paper alone should not flag it. This needs your call (§7).
6. **UV5 contradicts a rule the CleanupSpec paper states.** p7: "Changes made to the cache by older non-squashed loads that execute after squashed loads due to re-ordering, need to be preserved and not reversed … corresponding invalidations / restorations are skipped." So UV5 ("too much cleaning") is a deviation from the paper's spec, not a gap in it. The criterion can encode this directly.

## 2. InvisiSpec (Yan et al., MICRO 2018)

### A. What it protects

- **Scope statement**, §III-B "Channels Protected", p3: "InvisiSpec blocks covert and side channels that are constructed by monitoring the state of any level of a multiprocessor data cache hierarchy. This includes cache state such as occupancy (e.g., what lines live in what sets), replacement information, and coherence information (e.g., whether a line is in the Exclusive or Shared state). It also includes data TLB state (e.g., what entries live in the TLB). Our goal is to provide a complete defense for the data cache hierarchy, as it has been proven to lead to practical attacks [1], [2]."
- **What a USL may not touch**, §V-B, p5: "USLs do not modify the cache coherence states, cache replacement algorithm states, or any other cache hierarchy state. No other thread, local or remote, can see any changes." §V-A2, p4: "a USL cannot modify the cache hierarchy in any way that is visible to other threads, including the coherence states."
- **Mechanism per level**: the Spec-GetS transaction "requests the line in an invisible mode, without changing any state in any cache" (§VI-A, p8). The directory is covered too: "a Spec-GetS obtains the line from the directory … without changing any cache or coherence states" (§VI-E1, p9). The LLC gets a per-core LLC-SB so a validation or exposure can skip DRAM (§VI-B, p7). D-TLB (§VI-E3, p9): "To prevent a USL from observably changing the D-TLB state … on a D-TLB miss, it delays serving it via a page table walk until the USL reaches the point of visibility … Second, on a D-TLB hit, any observable TLB state changes such as updating D-TLB replacement state or access/dirty [bits]…" are deferred.
- **Settings** (§III-C, p3): SameThread (shares private caches + TLBs), CrossCore ("monitor the last-level cache and its directory — e.g., how line coherence state changes over time"), and SMT.
- **Not covered (by simplification)**: footnote 2, p3: "For simplicity, we do not describe the protection of the instruction cache or instruction TLB. However, we believe they can be protected with similar or even simpler structures." So L1I is "not described", not "protected". AMuLeT treats KV1 as a known limitation on that basis (AMuLeT p10).
- **Explicitly out of scope**: §III, p3: physical channels (power, EM); "We also do not protect microarchitectural channels other than those listed above", for example execution-unit timing, NoC and DRAM contention, and fine-grain SMT structures. **MSHR contention**, original p10 §VII: "contention on other resources, such as MSHRs or execution units, could slow down the receiver, but such side channels are considered out of scope in this paper (Section III-B)." The SB/LLC-SB themselves are argued safe because entries are allocated at issue and never reused by a younger USL (§VII, p10).
- **Allowed state changes**: the validation/exposure at the visibility point "will make all the side effects of the USL in the memory hierarchy apparent" (§IV, p4). A fill at exposure is **not** a leak.

### B. What AMuLeT checks

- Paper: contract CT-SEQ, InvisiSpec **Futuristic** (§3.1 p5; §4.1 p8: "For InvisiSpec and STT, we run them in their Futuristic mode"). µarch trace = "the final state of the L1D-cache and D-TLB" (§3.5 p7), with a 1-page sandbox "as the TLB is not protected" (§3.5 p7, contradicting InvisiSpec §VI-E3). L1I was included only in "previous campaigns", which found KV1 (p10). The UV2 amplification used a 2-way L1D and 2 MSHRs, down from 256 (Table 6, p10).
- Code: `src/executor.py:294-303` selects `--scheme=SpectreSafeInvisibleSpec`, swapped for `FuturisticSafeInvisibleSpec` when `InvisiSpec_FuturisticSpec`. `executor.py:214-219` sets `--ruby` with `--L1_TBEs/--L2_TBEs={tbe_count}`, default 256 (`config.py:255`). Trace sources in the Table 4 config: `docker/docker_invisispec/docker_gem5_v1_final_cache_and_tlb.yaml:60` `["data_cache", "dtlb"]`. `executor.py:471-486` reads the L1D as `system.ruby.l1_cntrl0.L1Dcache` addresses. `executor.py:519-532` keeps in-sandbox tags exact and collapses out-of-sandbox tags to their set index, so an eviction of a primed line shows up by set. `executor.py:533-534` keeps only in-sandbox D-TLB entries.
- **Mismatch with A**: L2/LLC presence, the directory, coherence state and replacement state are claimed but never observed by AMuLeT. The D-TLB is claimed but effectively untested (1-page sandbox).

### C. Our runs

- `STT_6_invisispec` (`run_config.jsonc`, `run_invisispec.py:96-104`): InvisiSpec binary `X86_MESI_Two_Level/gem5.opt`. gem5 args are `--caches` (from `gem5_common.py:167`) plus the extra_args above, with **no `--ruby`**. That gives classic L1I 32kB/2-way and L1D 16kB/8-way (InvisiSpec `configs/common/Options.py:104-109` defaults), **no L2, no directory**. See finding 1.
- `STT_6_invisispec_compound` (`run_invisispec_compound.py:81-92`): `--ruby` plus Spectre scheme, `--needsTSO=1`, `--allowSpecBuffHit=1`, `--l1d_size=1kB --l1d_assoc=2`, optional `--apply-spec-eviction-patch`. Ruby MESI_Two_Level, so L1I 32kB/2, L1D 1kB/2, one L2 2MB/8 (`Options.py:102,106,110`), a directory, and `L1_TBEs = L2_TBEs = 2` (Ruby defaults, `configs/ruby/Ruby.py:85,87`). AMuLeT's default is 256, so **every** compound run sits in AMuLeT's "amplified" MSHR configuration.

## 3. SpecLFB (Cheng et al., USENIX Security 2024)

### A. What it protects

- **Levels**: p632 (§1): the LFB check prevents "potentially unsafe speculative loads from being reloaded from lower-level cache into adjacent upper-level cache (e.g. from L2 cache into L1 data cache (L1D cache))". It is implemented "in the L1D cache of open-source RISC-V core SonicBOOM … and both cache levels of X86 O3 CPU model in Gem5". p637 (§6.1): "SpecLFB can be reused with the same defense mechanism in the LFBs of different cache levels." p640 (§7): "SpecLFB is applied to both levels of the cache in the O3 CPU model in Gem5." Gem5 Table 2 (p640): L1D 32KB 8-way with 4 MSHRs, L2 2MB 16-way with 20 MSHRs. Build check: the hook is in `BaseCache` (`src/mem/cache/base.cc:484-612`, `[speclfb] Determine whether a usl is a musl`), so it applies to every classic cache level that exists.
- **State**: presence only. Threat model §4, p635: "eliminating cache side channels in speculative execution established by flush- and conflict-based cache side-channel attacks, which require pre-evicting the cache lines to be leaked." §5, p635: "the speculative loads causing cache misses are considered unsafe and should be protected." §6.1, p637: "Only when the security check mechanism determines that it is safe, can the data be refilled into the L1D cache." In background §2.2 (p633) the fill and its eviction happen at refill from the LFB, so holding the refill also holds the victim eviction. On squash, p639: "the relevant data in LFB will become invalid before changing the state of the L1D cache."
- **Explicitly out of scope**: §9, p643: "Leakage through speculative loads under cache hits is out of the current defense scope of SpecLFB." Also: "because LFB cannot intercept the data loaded by speculative instructions under cache hits, it does not prevent speculative changes to cache metadata." §4, p635: "We do not consider other speculative side channels, such as TLB [20], port contention [4,7], etc." Non-speculative and physical channels are excluded. Coherence: p637, "since the cache line already exists in the L1 upon a cache hit, no additional coherence mechanism is required". Coherence is not otherwise discussed. L1I is not mentioned.
- p642 (§8.3) summarizes the narrowing: "SpecLFB specifically protects speculative loads causing cache misses … [and] specifically blocks covert channels through cache."

### B. What AMuLeT checks

- Paper §4.7, p12: tested against CT-SEQ, "the most intuitive contract based on the security guarantees described in the SpecLFB paper". Trace = final L1D + D-TLB (§3.5 p7). For SpecLFB the cache reset uses a simulator hook (p7).
- Code: `executor.py:281-286` adds `--bp-type=BiModeBP --scheme=Speclfb`. `executor.py:220-221` adds `--caches --l2cache`. `docker/docker_speclfb/yamls/ct-seq.yaml:75` sources are `["data_cache","instr_cache","dtlb"]`. The classic L1D is read from `system.cpu.dcache` (`executor.py:473-474`). The empty-TLB assert is skipped for SpecLFB (`executor.py:503-504`). The SpecLFB `configs/revizor/ipc.py:114-121` hands `system.l2` to the IPC object (used for reset), but the trace never reads L2.
- **Mismatch with A**: L2, which the gem5 implementation protects, is not observed. The D-TLB is observed even though the paper puts the TLB out of scope (§4 p635), though the 1-page sandbox keeps that from mattering much.

### C. Our run

- `STT_6_speclfb` (`run_speclfb.py:96-103`, no `run_config.jsonc`): binary `amulet-gem5-SpecLFB_AE-v1.1/build/X86/gem5.opt`, `--caches`, auto `--scheme=2` → `Speclfb` in `se.py`, no extra args. That gives classic L1I 32kB/2 and L1D 64kB/2 (`Options.py:184-189`) and **no L2**. See finding 2.

## 4. CleanupSpec (Saileshwar & Qureshi, MICRO 2019)

### A. What it protects

- **Levels and the split between undo and randomize**, p2 (§1): "CleanupSpec uses randomization for L2/LLC (and for the directory [61]), and consequently only needs to rollback evictions from L1 data caches … CleanupSpec executes transient loads while tracking their cache side-effects (L1/ L2/ LLC installs and L1 eviction-victim line address). On a mis-speculation … CleanupSpec invalidates the line in the L1 cache if it was installed speculatively and fetches the evicted line from L2 cache to restore the original line. For changes to the L2/LLC, CleanupSpec merely invalidates the copy there if it was installed speculatively (as L2/LLC evictions leak no information)."
- **Replacement and coherence**, p2: "To protect the replacement state, it uses Random Replacement policy for the L1 data cache (any replacement policy can be safely used for a randomized L2 or LLC). For coherence state changes, CleanupSpec delays loads that cause such changes (M/E to S) until they are unsquashable on the correct path." §3.2, p6: "replacement state updates for both L1 and L2 caches leak no information." §3.5, p7: "Note that transient changes like I -> E or adding S-sharers (even in remote directories), that do not affect the state of a line cached by a remote core, are allowed and reversed." A transient `clflush` is also delayed (p7).
- **The six components** (§3.1, p5-6): (1) L2 address randomization, (2) remove L1/L2 installs, (3) restore L1 evictions, (4) random L1 replacement, (5) delay M/E→S, (6) protect lines in the speculation window by serving cross-thread/cross-core hits with dummy misses (§3.6 p7-8).
- **Data-cache-only threat model**, §2.1, p3: "We only consider attacks exploiting the data-cache hierarchy, including private data caches (e.g. L1-D cache) and shared caches (L2/LLC), as other structures like instruction caches, TLB, etc. can be protected with a low overhead with prior works [40, 58]. The adversary may transiently access the cache and modify its state through installs [63], evictions [34], updates to replacement [26] and coherence [62] state."
- **Explicitly out of scope**, §2.1 p3: "speculation-attacks using AVX side-channels … We also assume speculative hardware prefetching is disabled … we assume a close-page row-buffer policy … We further consider out-of-scope side-channels due to SMT port-contention [1], network [49] or DRAM [56] contention, EM radiation or power." p1 footnote: "I-Cache, TLB or Branch Predictor can also be used to leak information, but delaying [40] or buffering [25, 58] transient changes to these structures can prevent this. Port-contention [1] is out-of-scope."
- **Configuration assumed**: "a 2-level inclusive cache-hierarchy" (§5.3 p9). Table 4 (p9): L1D 64KB 8-way, L2 2MB/core 16-way including 2-cycle address encryption, directory-based MESI. Restoration is "serviced from the inclusive L2" (§4(b) p8).

### B. What AMuLeT checks

- Paper: CT-SEQ (§3.1 p5), final L1D + D-TLB (§3.5 p7), 1-page sandbox. unXpec (KV2) was found only "in campaigns where we included the L1I-cache state" (p12). UV3/UV4/UV5 are L1D tag differences (p11-12).
- Code: `executor.py:288-292` adds `--needsTSO=0 --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2`. `docker/docker_cleanupspec/docker_gem5_v1_final_cache_ipc.yaml:62` sources are `["data_cache", "instr_cache"]`. `src/cleanupspec_analysis.py:90-97` diffs `[system.ruby.l1_cntrl0.L1Dcache]` / `L1Icache` tag sets between the two runs. Its UV5 test (`:138-152`) is "exactly one extra tag, which was both loaded and CLEANUP'd in the other run's protocol trace".
- **Mismatch with A**: L2 install invalidation (`InvL2_CLEANUP`) is claimed by the paper and enabled by `Cleanup_FOR_L1L2`, but AMuLeT never checks it.

### C. Our run

- `STT_6_cleanupspec_residue` (`run_cleanupspec_residue.sh`, no `run_config.jsonc`): `--ruby --l2cache --l1d_size=2kB --l1d_assoc=4 --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2 --needsTSO=0`. That gives Ruby MESI_Two_Level with L1D 2kB/4, L1I 32kB/2, L2 2MB/8, a directory, and TBEs = 2 by default.
- Build check of the scheme: `configs/common/Scheme.py:76-82`. `Cleanup_FOR_L1L2` sets `rand_L2`, `cleanupLQExecd_on_Squash`, `cleanupLQInflight_on_Squash`, `l1d_mshr_tracking`, `random_repl_L1`, `L2Inv`, and `InternalInterferenceHit`. `configs/ruby/MESI_Two_Level.py:75-78` passes `is_index_randomized = options.rand_L2` to the L2. `:124-130` gives the L1D a `RandomReplacementPolicy()`. `Scheme.py:133-134` sets `cpu.L2inv_on_Squash`. So our build does run the paper's randomized-L2 and random-L1-replacement design. That matters for the criterion: L2 victims are benign by design, and L1 replacement bits carry no information.

### E. Undo rules the paper specifies (input to the criterion)

- **What gets undone, at which level** (§3.3-3.4, p6): installs are tracked per load in a SEFE with `L1-Fill` and `L2-Fill` bits and an `L1-Evict Lineaddr`. On squash, "the LQ-Entry SEFE is referred to decide whether to send invalidation message to L1/L2 based on L1-Fill/L2-Fill values, or if it can be skipped – if the load was not issued or if there was a L1-Hit (L1-Fill=0 and L2-Fill=0)." The L1 victim "is restored from the L2 by issuing a normal demand access for this address to L2, and installing it in place of the invalidated line." **L2 victims are not restored** (randomized L2, p2).
- **In-flight loads** (p6): a cleanup request "is sent to L1/L2-MSHR to squash pending loads and increment the current active EpochID … any cache changes like install and victim replacement are made only when a load returns and is for the current EpochID." So a dropped in-flight load should leave **no** footprint. That gives `cleanup_drop` a checkable meaning: no later `fill` from that request.
- **Ordering** (p6-7): wait for older in-flight loads to retire first. "We ensure cleanup operations for loads are issued in the reverse of the order in which they executed … removal/restoration effectively reverses time for the cache and no illegal state is retained."
- **Reordered correct-path loads** (p7): changes by older non-squashed loads that executed after squashed ones "need to be preserved and not reversed … corresponding invalidations / restorations are skipped." See finding 6: UV5 violates this.
- **The intended end state** (p2): "the perceived cache state after these operations is as if the transient loads did not access the cache." §4(c), p9: "After cleanup, all lines are invalidated from the cache levels where they were transiently installed into, and the evicted lines are restored for L1 and randomized for L2 … the coherence state of the restored/invalidated lines is updated based on presence in other private caches, such that it is independent of the transient access." This is a **net-state** spec. It favours the state-replay check over per-event pair counting, which settles open question 3 in `TRANSMISSION_CRITERIA_FORMAT.md` (intra-window churn) in favour of net presence.
- **Stores**: §4(a), p8: "the L2 copy never becomes stale transiently as RFOs are issued non-speculatively to prevent Spectre-Prime[44] attacks." By design a speculative store never changes cache state, so UV3 is an implementation deviation. AMuLeT found it via missing `writeCallback()` metadata (p11). Our explainer says squashed stores never reach the cache on our build. Both statements are consistent with the paper's intent.
- **Cleanup timing**: §4(b), p8 argues the cleanup stall is hard to exploit because it is mostly waiting for in-flight correct-path loads. It ends with "Future work can explore making the cleanup-operations incur a constant-time stall to make this theoretically impossible to exploit." So the paper claims cleanup "does not practically leak" but explicitly does not guarantee constant time. unXpec breaks that argued claim. Whether that makes it in scope is a decision (§4b(2)). Either way a single-run footprint criterion cannot express it.
- **Left to other mechanisms**: I-cache, TLB, BP (p1 fn.); SMT L1 evictions are left to way-partitioning (NoMo), "that is anyway required for preventing non-speculative L1 cache side-channel attacks" (§3.6 p8). Neither applies to our single-thread runs.

## 4b. unXpec

This section answers items 1–3 of [`UNXPEC_MISS.md`](UNXPEC_MISS.md). Source: `~/Documents/quail/sources/papers/li-2022-unxpec.pdf` (Li, Miao, Yang, Bu; author copy, 15 pp.). The title is verified from the PDF. The venue, **HPCA 2022** (pp. 98-112, DOI 10.1109/HPCA53966.2022.00016), is confirmed from the IEEE Xplore/HPCA 2022 listings and the Zenodo artifact "Artifact Evaluation for HPCA 2022"; the PDF itself has no venue line. Page numbers are PDF pages.

**(1) What unXpec observes: the rollback latency.** It does not look at leftover state.

- Abstract, p1: "It exploits the secret-dependent timing channel exhibited through the rollback operations of Undo defenses. Specifically, the rollback process requires both invalidating cache lines brought into the cache by transient instructions and restoring evicted cache lines … This opens up a channel that encodes secret via the timing difference between when rollback involves much invalidation and restoration or not."
- **Magnitude**: "A single transient load can trigger a secret-dependent timing difference of 22 cycles (without eviction sets) [or] 32 cycles (with eviction sets)" (p1). With eviction sets it reaches 32∼64 cycles (p8), at 140 Kbps with over 90% accuracy in gem5 with CleanupSpec enabled (p1).
- **Timer and measured interval**: the attack design (Fig. 4, p6) is `obtain_first_timestamp()` → mistrained branch → `load(P[secret*64*k])` → `memory_fence()` → `obtain_second_timestamp()`. "The receiver measures the sender execution time and the rollback time using instructions such as rdtscp" (p6). The attacker runs in the **same thread** (p4: "the sender and receiver code run in the same thread"). The fence is used "to eliminate the interference of inflight loads" (p4).
- **Which levels**: the paper's model follows CleanupSpec. L1 does invalidation and restoration; lower levels do "invalidation and randomized address mapping" (p4). Under secret 1, "CleanupSpec at least invalidates the transiently installed lines and restores the original lines evicted from the L1 cache if necessary. In this case, the CPU core stalls for a longer time" (p6). Invalidation alone is enough: "only the secret-dependent invalidation operations suffices to construct the timing channel and the secret-dependent restoration operations helps to enlarge the timing difference" (p4).
- **Gadget**: preparation makes "the sender program under secret 0 yield[] all-hits of P[0] and the sender program under secret 1 yield[] all-misses of P[64∗1]…P[64∗n]" (p7). So secret 0 triggers no cleanup at all (p2), and secret 1 triggers invalidate and restore. This is the same hit-vs-miss split as our `unxpec_demo`.
- **Mitigation cost**: "Simply enforcing constant-time rollback to mitigate unXpec may induce an over 70% performance overhead" (p1).

**(2) Is cleanup timing inside CleanupSpec's own claimed protection?** It is **not claimed as constant-time**. The paper argues the timing is *practically* hard to exploit and leaves constant-time cleanup to future work, which puts it in a grey zone: the claim is there, but only as an argument.

- CleanupSpec §4 security property (b), p8: "During cleanup operations (t2 to t3), the process of restoration of cache state does not practically leak information." Its reasoning, p8: "all non-squashed loads that are inflight are completed before cleanup operations begin and no new instructions are fetched until cleanup finishes … the actual time taken for cleanup operations to make up only a small portion of the stall … and hence hard to exploit for the SameThread adversary … restoration cache accesses are pipelined and serviced from the inclusive L2". It then says: "**Future work can explore making the cleanup-operations incur a constant-time stall to make this theoretically impossible to exploit.**"
- So CleanupSpec does **claim** that cleanup does not "practically" leak against a same-thread adversary. That is the very adversary unXpec uses. But it **explicitly declines** a constant-time guarantee. unXpec (p4) targets both premises of that argument: "While CleanupSpec states that the cleanup operations may increase the stall time, it fails to uncover the associative vulnerability". The fence removes the in-flight-load noise, and invalidation alone creates the difference.
- **What this means for "exactly what the paper protects"**: cleanup timing is a *stated security property backed by an argument*, not a *guaranteed mechanism*. Under a strict reading of what the paper claims, unXpec breaks property (b), so it is in scope as a claim violation. Under the reading "only what the mechanism enforces", it is a known, acknowledged limitation (the future-work sentence). **This is your call.** In either case it needs a timing or relational term. The footprint-count/net-state criterion of §7 cannot express it, which confirms the UNXPEC_MISS claim.

**(3) What AMuLeT's "unXpec" result is: the timing channel, seen indirectly through residue in L1I.** It is not leftover L1D state.

- AMuLeT paper, KV2, p12: "In campaigns where we included the L1I-cache state in the µarch trace, we detected violations similar to the unXpec vulnerability [21]. In these violations, the inputs had different L1I-cache states at the end. The root cause was a difference in cleanup operations causing varying execution times and the instruction fetch speculatively installing extra lines in the L1I-cache." Table 10 (p12) shows the case: input A's speculative load is an L1 hit with no Undo, input B's is a miss with an Undo. "As cleanup is on the critical path of execution, this increases the execution time for Input B … the fetch unit speculatively fetches addresses beyond the end of the test, installing these in the L1I-cache."
- So the *cause* is the unXpec timing difference. The *observable AMuLeT compares* is final-state **L1I tags** (a single-thread, end-of-test snapshot), which act as a timing-to-state amplifier. L1D tags are identical between the two inputs.
- Code: `/work/amulet-repo/src/cleanupspec_analysis.py:90-101` diffs the L1D and L1I tag sets of the two runs. If L1D is equal and L1I differs, it prints `'difference in ICache caused violation - UnXpec variant?'` (`:100`). No AMuLeT config observes timing for CleanupSpec. The `access_timing` source exists only in an InvisiSpec yaml (`docker/docker_invisispec/docker_gem5_v1_access_timing.yaml:61`). The CleanupSpec yamls use `["data_cache","instr_cache"]` (`docker/docker_cleanupspec/docker_gem5_v1_final_cache_ipc.yaml:62`).
- **This resolves the inconsistency UNXPEC_MISS flags**: `AMULET_BUGS_DETECTION_ACCOUNTING.md` §0's "leftover spec-installed addresses" description is wrong for unXpec. The residue AMuLeT saw is in **L1I**, caused by **cleanup time**. The data cache was cleaned correctly. The project log and demo description ("the undo itself is the channel") are the right one.
- **Note:** both the L1I residue AMuLeT used and the I-cache itself are outside CleanupSpec's stated scope (I-cache excluded, p1 fn.; §2.1 p3). AMuLeT's detection path therefore relies on an out-of-scope structure to reveal an in-scope (arguable) timing claim.

## 5. Speculation / threat-model audit vs the STT_6 base model

**Confirmed: all three use the STT base model.** `specs/defense_units.json` units 4, 6 and 7 all have `"alloy_model": "STT_6"`. `results/STT_6_invisispec/run_config.jsonc` has `"model": "STT_6"`, `speculation.control_flow: true`, `data_flow: false`. The other three launchers stage from `testsets/STT_6`.

**What STT_6 encodes** (`STAGE1_alloy/models/STT_6.als`, read-only):

- Speculative instructions: `speculation_contract_p = uncommitted_p & has_unresolved_brs_p` (`:325`), meaning uncommitted and after an unresolved branch. A memory-order alternative is commented out at `:324`.
- Protection set starts as all memory (`hardware_protection_policy = Mem_s`, `:326`). A load's data becomes public once no unresolved branch precedes it (`prot_set_propagation_p`, `:331`).
- Transmitters: `leakage_function = Loads.inaddr + Branchxs.inreg` (`:328`). Stores and ALU ops are not transmitters.
- A test exists only if the transmitter's operand is in, or flows from, the protection set (`tag_xm`, `:270-273`; `gen_useful_litmus`, `:301-311`). So every STT_6 test is an **access→transmit chain**: a speculatively loaded memory value feeds a speculative transmitter's address.

**STT's own definitions** (yu-2019-stt, PDF p5): "In the Spectre model, an instruction has reached the visibility point if all older control-flow instructions have resolved. In the Futuristic model, an instruction has only reached this point if it cannot be squashed." STT_6 is the Spectre model with a taint requirement.

**Each paper's definition, and how it compares:**

| defense | paper's "unsafe/speculative" load | speculative window vs STT_6 | leak precondition vs STT_6 | effect of using STT_6 |
|---|---|---|---|---|
| InvisiSpec | §IV-A1 p4: "In the Spectre attack model, USLs are the speculative loads that follow an unresolved control-flow instruction. As soon as the control-flow instruction resolves, the USLs that follow it in the correct path … transition to safe loads." "In our Futuristic attack model, USLs are all the speculative loads that can be squashed by an earlier instruction." IS-Fu conditions: p10 | **Same** as STT_6 for IS-Spectre, which is what our runs use. **Narrower** than IS-Futuristic, which is what AMuLeT used | InvisiSpec hides **every** USL, secret-dependent or not. STT_6 needs taint, so it is **stricter** | No invalid tests, but **under-generates**: single-load gadgets whose address is a register or committed value (AMuLeT's UV1 example, Fig. 4 p10, keys the speculative address on input `rbx`), non-branch speculation (Futuristic), and store transmitters |
| SpecLFB | §5 p635-638: MUSL = "an unsafe speculative load that causes cache miss". Sources: unresolved control flow, unresolved memory access order (memory dependency and consistency), unresolved value (not implemented), other exceptions. Control-flow MUSLs are safe "if there are no older control instructions that are unresolved" (p638) | **Broader** sources than STT_6 (memory order, exceptions). The control-flow part equals STT_6. Narrowed to **misses only** | No secret-dependence needed. STT_6 is **stricter** | **Under-generates**: Spectre-v4-style memory-order tests (SpecLFB evaluates v4, p641) and register-secret single loads (AMuLeT UV6 gadget, Fig. 8b p13: "RBX is secret", one speculative load). STT_6 tests whose transmitter **hits** are generated but have nothing to protect under SpecLFB. The criterion has to drop them (presence-only, fills only) |
| CleanupSpec | §2.1 p3: "We deem all transient instructions potentially 'unsafe' until they retire … unlike others [31, 43] that only focus on Spectre variants." "The secret may be accessed from the memory or from a register, or computed, transiently." p3: "a threat model where any mis-speculated load could leak information (like prior work [58])". Undo happens only for loads that are actually **squashed** | **Broader** than STT_6 (any squash cause). The undo obligation attaches to squashed loads, which every STT_6 wrong-path transmitter is | Explicitly **no** taint requirement, register secrets included. STT_6 is **stricter** | **Under-generates**: register/computed-secret single loads, memory-dependence squashes, speculative **stores** (UV3; not transmitters in STT_6), and split loads only if concretization happens to misalign (UV4) |

**Answer to Anna's question ("why wouldn't the speculative definition be the same as STT?").** For the *window*, it largely **is** the same as long as we run the Spectre variants. InvisiSpec-Spectre's USL definition is word-for-word STT's Spectre visibility point (InvisiSpec p4; STT p5). SpecLFB's control-flow MUSL rule is the same. CleanupSpec's "until retire" is broader, but in practice it bites only on squashed loads, and all our wrong-path transmitters are squashed. The real difference is the **leak precondition**. STT protects only *speculatively accessed data*, so STT_6 requires a taint chain. All three footprint defenses claim that *any* unsafe speculative load leaves no footprint, whatever its address depends on. So STT_6 is a **sound but incomplete** generator for them: every test it produces has an unsafe speculative load transmitter under all three papers' definitions (no over-generation of invalid tests), but it can never produce the single-load and non-taint gadgets that AMuLeT's UV1 and UV6 examples are. Two smaller differences: AMuLeT tested InvisiSpec in **Futuristic** mode while we ran **Spectre** mode, and SpecLFB protects only **misses**, so hit-transmitter STT_6 tests are out of its scope.

## 6. Options for the speculation definition (pinned; not decided)

1. **Keep STT_6 as-is.** It stays sound for the Spectre window. Write up the under-generation (single-load, register-secret, memory-order and store gadgets are structurally absent) as a stated limitation next to the AMuLeT scope argument.
2. **A footprint variant of the model.** Drop the taint precondition so that any load in `speculation_contract` is a transmitter. One way is to make `tag_xm` key on `speculation_contract.operands & leakage_function` instead of the protection set. **This is an `.als` change and needs your sign-off.** I have not drafted a diff.
3. **A Futuristic/memory-order contract.** The commented-out line at `STT_6.als:324` already sketches `no_unresolved_mem`. That would cover InvisiSpec-Futuristic (AMuLeT's setting), SpecLFB's memory-order MUSLs, and CleanupSpec's "until retire". It needs `data_flow` speculation in the harness too. Also an `.als` change.
4. **Add stores as footprint transmitters** for CleanupSpec (UV3) and InvisiSpec. `leakage_function` currently has no `Stores`. An `.als` change.
5. **Harness-only, no model change:** run InvisiSpec with `--scheme=FuturisticSafeInvisibleSpec` to match AMuLeT. The window then becomes broader than the model's, which keeps the tests valid but means the model's window and the defense's window no longer match.

## 7. Implications for the criterion JSONs (`specs/leakage/<defense>.json`)

These values come only from the papers. The "in our runs" notes say what our simulated hierarchy can actually show.

**InvisiSpec**

```jsonc
"observation": {
  "structures": ["L1D", "L2", "DIR", "DTLB"],   // "any level of a multiprocessor data cache hierarchy" + "data TLB state" (§III-B p3); L2 is the LLC in our 2-level Ruby runs
  "granularity": "line",                          // DTLB: page
  "state": ["presence", "replacement", "coherence"] // "occupancy … replacement information, and coherence information" (§III-B p3; p5)
},
"allowed": ["SB", "LLC-SB", "expose", "validate"], // visibility-point re-access is the defined legal footprint (§IV p4)
"not_covered": ["L1I/ITLB: not described (fn. 2 p3) — KV1",
                "MSHR/TBE contention: out of scope (orig. §VII p10) — UV2",
                "execution units / NoC / DRAM / SMT (§III p3)"],
"actors": {"spec": "USL under the scheme run: Spectre = after an unresolved control-flow instr (§IV p4); Futuristic = squashable (p4, p10)"}
```

The `SSEV` vocabulary needs a `DTLB` struct (fill/evict). `repl_touch` must be in scope for InvisiSpec because the paper claims replacement state. Known limit in our runs: the directory and coherence states are single-core, so only the directory's own state changes (owner/sharer bits) are observable.

**SpecLFB**

```jsonc
"observation": {
  "structures": ["L1D", "L2"],     // L1D in the design/RTL; "both levels of the cache" in the gem5 implementation (p632, p640)
  "granularity": "line",
  "state": ["presence"]            // fills, and the victim evictions they cause; flush-/conflict-based attacks (§4 p635)
},
"allowed": ["LFB"],
"not_covered": ["speculative hits / replacement (LRU) metadata (§9 p643)",
                "TLB, port contention (§4 p635)", "value prediction (p637)"],
"actors": {"spec": "MUSL: unsafe speculative load that MISSES; unsafe = unresolved control flow | memory order | exceptions (§5 p635-638)"}
```

Our run has no L2, so in practice only L1D is checked until the L2 is added (finding 2). `spec` is the paper's definition, not the implementation's `isUnsafe`. UV6 is the implementation clearing `isReallyUnsafe` for the first speculative load (AMuLeT Fig. 8, p13).

**CleanupSpec**

```jsonc
"observation": {
  "structures": ["L1D", "L2"],     // L1D: invalidate install + restore victim; L2/LLC: invalidate install only (p2; §3.3-3.4 p6)
  "granularity": "line",
  "state": ["presence"]            // replacement made benign by random L1 replacement + randomized L2 (§3.2 p6); coherence M/E->S delayed (§3.5 p7)
},
"undo_obligations": {
  "L1D": ["invalidate spec install", "restore spec-evicted victim"],
  "L2":  ["invalidate spec install"]   // L2 victims NOT restored by design (randomized L2, p2)
},
"preserve": "changes by older non-squashed loads reordered after squashed ones must NOT be undone (p7)", // UV5
"window": {"undo": {"from": "squash(sq)", "to": "cleanup_done(sq) | sim_end"}},
"leak": "net presence in OBS at cleanup_done differs from presence at the window start, beyond committed instructions' effects", // "as if the transient loads did not access the cache" (p2); reverse-order undo "reverses time" (p7)
"not_covered": ["cleanup timing (unXpec): claimed only as 'does not practically leak', constant-time left to future work (§4(b) p8); needs a timing/relational term — see §4b, decision pending",
                "I-cache, TLB, branch predictor (p1 fn.; §2.1 p3)", "prefetcher (assumed disabled, §2.1 p3)",
                "SMT L1 evictions: delegated to way-partitioning (§3.6 p8)"],
"actors": {"spec": "squashed (any transient cause) load; secrets from memory, register or computation (§2.1 p3)"}
```

`DIR` is arguably in scope: the paper randomizes the directory (p2), and "adding S-sharers (even in remote directories) … are allowed and reversed" (p7). I left it out of `structures` because our single-core runs cannot show a remote-core effect. Including it is your call. The paper's net-state wording supports resolving the format doc's open question 3 as net presence.

**Needs your decision**

1. Whether the InvisiSpec criterion should flag UV2-type MSHR/TBE contention. The paper puts MSHR contention out of scope. AMuLeT counts it because it shows up in L1D state.
2. Whether to include `DIR` for CleanupSpec and InvisiSpec given single-core runs.
3. Whether to re-run `STT_6_invisispec` under `--ruby` (the current campaign did not exercise the defense) and `STT_6_speclfb` with `--l2cache`, and whether to give both a canonical `run_config.jsonc`. These are run-config changes. Nothing was launched.
4. Spectre vs Futuristic for InvisiSpec. We run Spectre; AMuLeT ran Futuristic.
5. Whether unXpec (cleanup timing) counts as an in-scope CleanupSpec violation (§4b(2)) and so needs a timing/relational criterion term.
6. Which of the §6 model options, if any. All except option 5 are `.als` changes.
7. Fix `specs/defense_units.json` unit 4 ("Ruby MESI" → classic) and units 6 and 7 (`leakage: stt.json`), once the criteria exist.
