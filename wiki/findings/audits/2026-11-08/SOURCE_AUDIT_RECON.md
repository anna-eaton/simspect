# Source audit: ReCon (Recon-STT) gem5 implementation vs SimSpect's inferred contract (2026-11-08)

Read-only manual audit, no gem5 runs. Code: `~/Downloads/dockerrecon/gem5-recon/` (the authors' docker tree). **Provenance caveat:** this tree has no git, and it is not byte-identical to `/work/gem5-recon` on the cluster: the cluster's `lsq_unit.cc` and `iew.cc` carry 2026-04-08 mtimes in `gem5-hooks/gem5-recon-modded/recon-modded_src.diff`, and the cluster line numbers quoted in `wiki/design/STT_VS_RECON_STT.md` sit about 11-15 lines below the local ones (`Doing memory access`: local `lsq_unit.cc:2062` vs cluster `:2077`; `Memory request ... was sent`: local `:1535` vs cluster `:1546`). The recon → recon-modded diff touches none of the ReCon reveal code (`commitLoad`, `mem/cache/*`, `taint_tracker.cc`), so every ReCon finding below should carry over, but that is **unverified on the cluster**. All `file:line` refs are to the local tree.

Paper: the local PDF `~/Documents/quail/sources/papers/aimoniotis-2023-recon.pdf` is the full paper. `pdftotext` extracts about 1,300 lines; earlier notes calling it a "3-page extraction" refer to the `.md` stub. Citations are by section.

Contract: `STAGE1_alloy/models/Recon_6.als:313-325` (defense block), skeleton `:186-262`; `specs/leakage/recon.json`; `specs/gem5_builds.json` recon entries. SimSpect runs Recon as `--caches --scheme=2 --allow_leaked` (`STAGE3_gem5/gem5_common.py:385`, `pipeline.py:608`, `specs/defense_units.json:226`). That means classic caches with L1I+L1D only: no `--l2cache`, no `--ruby`.

## Summary

| ID | Class | Confidence | Claim | Known? |
|---|---|---|---|---|
| R-SA-1 | B (headline) | confirmed by reading; runtime effect unverified | In classic-cache mode, ReCon's reveal never marks the right address. The cache's Reveal handler looks up `pkt->req->valueFromAddr`, which `commitLoad` never sets (it is always 0). So SimSpect's Recon runs are Recon-STT with ReCon's un-protection effectively switched off | new. Contradicts claudelog 2026-10-28 item (3), "classic-cache Recon runs do exercise ReCon". Matches the Alloy-side R-1 (reveal is a no-op) |
| R-SA-2 | A (vs paper) + B (vs Alloy) | confirmed by reading (latent) | Stale reveal: a store performed between LD1's commit and LD2's commit is overwritten by LD2's later Reveal, so the *new* stored value is marked revealed although it never leaked | new |
| R-SA-3 | A (vs paper) | confirmed by reading (latent) | Conceal is start-offset only: a store clears the reveal bit only at its first byte (classic) or first word (Ruby). A partial or unaligned store into a revealed word leaves it revealed | new |
| R-SA-4 | A (vs paper) | confirmed by reading (latent) | Reveal ignores width and alignment: the LPT stores only LD1's address. A 1-byte LD1 reveals the start byte or word, and a later 8-byte load from the same start is fully untainted. Ruby also reveals unaligned words and checks only the first word of a word-crossing load | new |
| R-SA-5 | A (vs paper) | confirmed by reading (latent; needs `--l2cache`) | Classic multi-level: an L1-miss/L2-hit load gets L2's bit for word 0 of the line (shared `Request`, block-aligned miss packet), and evictions carry only bit 0. Revealing word 0 un-protects every word in the line | new |
| R-SA-6 | A (vs paper) | plausible (Ruby only) | Ruby: Reveal bypasses the Sequencer's per-line aliasing and overwrites the L1 entry's `accessingAddress`. A store finishing an S→M upgrade then clears the *revealed* word's bit, not the stored word's | new |
| R-SA-7 | A (vs STT/ReCon) | plausible (timing-hard) | Stale taint entries: squash keeps `reg→source` entries for squashed producers whose source load survives, and `std::map::insert` never overwrites. A reallocated phys reg can therefore keep an older, sooner-freed taint source, and a new speculative value gets untainted early | new (STT-inherited, not ReCon-specific) |
| R-SA-8 | A | confirmed by reading | getOldestTaint: an ALU merge keeps only the oldest source. Under ReCon, revealing that oldest source untaints the merge even when both loads share one shadow | **known** (OTB); the ReCon amplification is latent while R-SA-1 holds |
| R-SA-9 | A | confirmed by reading | STL forwarding returns data (`lsq_unit.cc:2019`) before the STT taint check (`:2079`) | **known** (`recon_SLF_stlf_bypass`) |
| R-SA-10 | B | confirmed by reading | Contract-vs-code reveal semantics differ: the contract reveals transitively through ALU/rf chains, at LD2 non-speculation rather than commit, never conceals on a store, and works per location rather than per value | mostly **known** (R-1/R-2, Recon F2); code evidence added here |
| R-SA-11 | C | confirmed by reading | Multi-source reveal: `[base + index*s]` reveals the base (or index) producer's word, though only the sum leaked. The paper's §5.1.1 endorses this | new, low |
| **R-SA-12** | **A (fires in our config, scheme 2)** | confirmed by reading | `insertTaint` skips the **physical** register with flat index 16, meant as a zero-register guard. x86 has no zero register: int phys reg 16 starts as microcode temp `t0`, which is written all the time, and then recycles into the free pool. Any speculative load or ALU result that renames to phys reg 16 is never tainted | new (same family as STT audit S1, different code) |
| **R-SA-13** | **A (fires; schemes 1, 2, 3)** | confirmed by reading | FP/SSE/x87 loads (`ldfp`, `ldfp87`, flagged `IsFloating`) are never marked speculative. `decode.cc:691` matches `isFloating()` before the load branch. So STT never taints them, NDA never delays them, and DoM never makes them L1-only | new |
| **R-SA-14** | **A (DoM, scheme 3)** | confirmed by reading | Speculative loads that cross a cache line (`SplitDataRequest`) are not marked L1-only, so under DoM their misses fill the cache speculatively | new |
| **R-SA-15** | **A (DoM)** | confirmed by reading | Speculative L1 hits update the replacement state right away. The DoM paper says these side effects are delayed until the shadow resolves | new |
| **R-SA-16** | **A (scheme 2, implicit channel)** | confirmed by reading | Stores whose address is tainted are never held: they resolve their address, run `checkViolations` (a memory-order squash) and train the store-set predictor, all secret-dependent | new for this build (same as STT audit S2) |
| **R-SA-17** | B | confirmed by reading | Shadows are cast only by conditional branches and stores. Indirect jumps/returns cast none, and neither do DoM's E- and M-shadows, although the ReCon/NDA/DoM papers include them | new |
| **R-SA-18** | B (affects the STL round) | confirmed by reading | Leak-criterion mismatch for NDA and DoM. Under NDA, store-forwarded speculative loads skip the delay (`WritebackEvent` calls `writeback`, not `completeDataAccess`), and DoM lets speculative L1 hits return data by design. `check_ld`'s data-obtained gate counts both as leaks | new |

The Alloy model cannot generate R-SA-2..6, R-SA-13, R-SA-14 or R-SA-16 (no byte/width/alias granularity, no conceal, R-1 makes reveal a no-op, GPR-only Stage 2, aligned slots, no store-address transmitter). R-SA-2..6 and the ReCon side of R-SA-8 are **latent in SimSpect's current config**, because R-SA-1 keeps reveal bits from being set. **R-SA-12 can already fire in existing corpora**, as a pseudo-random sprinkle wherever a tainted value happens to rename to phys reg 16. Some unexplained "NEW" Recon hits may be this.

## Findings

### R-SA-1 (B, headline): in classic caches, Reveal never marks the right address, so ReCon's untaint is effectively off

**Claim.** Under `--caches` (SimSpect's config), the Reveal packet sent at LD2's commit sets a reveal bit in the block at **physical address 0**, not at LD1's address. Loads therefore essentially never come back with `revealBit=1`, `TaintTracker::freeTaints` never takes the ReCon branch, and Recon-STT behaves like plain Recon-STT.

**Code path.** The sender (`src/cpu/o3/lsq_unit.cc:887-896`, inside `LSQUnit::commitLoad`) builds a fresh Request with the address in `paddr` and never sets `req->valueFromAddr`. The line that used to set it is commented out (`:901`):

```cpp
const Addr addr = inst->valueFromAddr;
const int size = 64;
const Request::Flags flags = Request::REVEAL;
RequestPtr req = std::make_shared<Request>(addr, size, flags, inst->requestorId());
req->setPaddr(inst->valueFromAddr);
PacketPtr pkt = new Packet(req, MemCmd::Reveal);
//inst->savedRequest->mainReq()->valueFromAddr = inst->valueFromAddr;
```

The receiver (`src/mem/cache/base.cc:427-436`, `BaseCache::recvTimingReq`) keys on the field that was never set. It does not use `pkt->getAddr()`; the `pkt->getOffset` variant is commented out:

```cpp
if (pkt->cmd == MemCmd::Reveal) {
  CacheBlk *blk = tags->findBlock(pkt->req->valueFromAddr, pkt->isSecure());
  if(blk){ ... unsigned long int valueFromAddr_offset = pkt->req->valueFromAddr & 63;
           blk->setRevealBit(valueFromAddr_offset, 1); }
  return;
}
```

`src/mem/request.hh:102` defines `unsigned long int valueFromAddr = 0;`, and a grep of `src/` finds no other assignment to `req->valueFromAddr` (only `inst->valueFromAddr` at `lsq_unit.cc:880` and the disabled `rename.cc:778`). The consumers, `lsq_unit.cc:183` (`if(pkt->req->revealBit) inst->revealBit = 1;`) and `taint_tracker.cc:143` (`if(inst->revealBit && !isTaintedInst(inst) && !inst->stlForw && inst->loadCompleted) taints.erase(...)`), only fire when a cache returns a set bit (`base.cc:485`), and that requires a bit set by a Reveal.

**What sits at paddr 0.** In SE mode the first page touched by `Process::initState` → `image.write` (`src/sim/process.cc:305`) gets the first physical page. That is the lowest ELF load segment (ELF headers/text). Litmus data on the stack will not be in block 0, so in practice nothing a litmus test reads is ever revealed. This is plausible but not run-verified.

**Ruby is different.** `Sequencer.cc:890-892` turns the Reveal into a `RubyRequestType_Reveal` on `pkt->getAddr()`, and `MESI_Two_Level-L1cache.sm:588-593` sets the word bit on the real address. So ReCon works only under `--ruby`; this build is `PROTOCOL = 'MESI_Two_Level'` (`build_opts/X86`). The authors' own script `runs/run_benchmark.py:41-43` uses classic `--caches --l2cache --l3cache`, though, so the classic path is what they appear to have run. Whether their evaluation tree differs is unknown.

**What it contradicts.** This is not a leak. It means the "Recon" builds in SimSpect never exercise the ReCon reveal (paper §4.1, §5.2, §5.4). claudelog 2026-10-28 (3) concluded the opposite, "classic-cache Recon runs do exercise ReCon", on the grounds that the bits exist. Together with R-1 (the Alloy reveal is a no-op), both sides of the Recon comparison are currently STT. Recon-vs-STT differences are build differences (Recon-STT store shadows, `getOldestTaint`, SLF), not ReCon signal.

**Cheap runtime check (no new run needed if any scheme-2 `stats.txt` is kept).** In a `--scheme=2 --allow_leaked` run's `stats.txt`, `system.cpu.lsq0.revealRequests > 0` together with `system.cpu.taint_tracker.allowlistedTaintsFromTT == 0` confirms it. The local `m5out/stats.txt` shows 5467 reveal requests and 0 allowlisted, but its `config.ini:133` is `scheme=0`, so the taint tracker isn't used there and it proves nothing.

**Litmus to confirm.** `mov rax,[P]` (P holds a pointer to Q); `mov rbx,[rax]` (commits: reveal P); `lfence`; then a mispredicted branch; on the wrong path `mov rcx,[P]` and `mov rdx,[rcx+probe]`. With working ReCon, the last load issues in-window. With R-SA-1 it is held. `check_ld` detects the difference: an expected "leak" becomes "no leak". Alloy cannot express it, because reveal state is cross-test and history-based.

### R-SA-2 (A vs paper; B vs Alloy): stale reveal across an overwrite

**Claim.** If a committed store to A is performed after LD1 (load A) commits but before LD2 (load [LD1's value]) commits, LD2's Reveal marks A revealed, yet A now holds the store's new value, which was never leaked.

**Code path.** LD1's commit writes `loadPair[dest] = {A, valid}` (`lsq_unit.cc:946-956`). Nothing on the store path touches `loadPair`: the only references are `lsq_unit.cc:245/875/949`, `commit.cc:1047` (non-load dest invalidation) and the disabled `rename.cc:725`. The store write clears the bit (`base.cc:1218-1223`, `blk->setRevealBit(pkt->getOffset(blkSize), 0)`). LD2's commit then sends the Reveal for A (`lsq_unit.cc:870-918`), which sets the bit again. LD2 can only commit after its data returns, so on an LD2 cache miss the older committed store drains first: the natural order is store write, then Reveal. Ruby has the same order (`L1cache.sm:961/975` clear, `:592` set).

**Contradicts.** Paper §4.4: "Once an address is revealed, it is guaranteed to be safe as long as its contents do not change." Paper §4.4.1 ⑦: "Upon commit of a dependent load that uses the contents of the concealed address, the address is marked anew", but LD2 used the *old* contents. The paper's own LPT design (§5.1) has no store→LPT invalidation either, so this looks like a design-level hole that the code inherits. Recon_6 cannot flag it: `Mem_s` is a location, and nothing re-protects a location on a store (`Recon_6.als:316-325`). See Q2.

**Litmus.**

```
mov rax, [A]          ; LD1 (committed), A holds pointer v_old
mov [A], rsi          ; ST: overwrite with v_new (rsi = secret-ish value from a committed path)
mov rbx, [rax]        ; LD2, slow (cache-miss v_old) → commits after ST drains → Reveal(A)
cmp/jcc  (mispredicted, slow to resolve)
  mov rcx, [A]        ; wrong path: gets v_new, revealBit=1 → untainted
  mov rdx, [rcx]      ; transmitter: leaks v_new in-window
```

Only possible under `--ruby` or with R-SA-1 fixed. Alloy cannot generate it, because it has no conceal and a location-based State. `check_ld` would detect the transmitter.

### R-SA-3 (A vs paper): conceal clears only the store's start offset

**Claim.** A store that overwrites part of a revealed word, without starting at the revealed offset, leaves the word revealed.

**Code.** Classic: `base.cc:1218-1223` clears `revealBits[pkt->getOffset(blkSize)]` only; the bits are per byte (`cache_blk.hh:157`), and `updateBlockData` at `base.cc:849` likewise writes only the start offset. Ruby: `CacheMemory.cc:423-432` `clearRevealBit` clears only `(physAddr & 63)/8`, the word of the start address.

**Contradicts.** Paper §4.4: "conceal operations work at any granularity (e.g., byte, sub-word, word,...) ... if any part of a revealed word changes, the whole word becomes concealed."

**Litmus.** After revealing A as in R-SA-1: `mov dword [A+4], esi` (committed). Then mispredict; on the wrong path `mov rcx, qword [A]` (bit at A still set, so untainted; the upper half is new) and `mov rdx, [rcx]`. For Ruby, use an unaligned 8-byte store at A-4, which clears word(A-4) and leaves word(A) revealed. Alloy cannot express it (no sub-location overlap). `check_ld` would detect it.

### R-SA-4 (A vs paper): reveal ignores LD1's width and alignment

**Claim.** `LoadPair` holds `pointer, registerIdx, load, stlForw, valid, prodRevealBit` (`secure_scheme/pair_loads.hh:12-17`), with no size. A 1-byte LD1 (`movzx eax, byte [A]`) feeding LD2 reveals A, and a later speculative `mov rcx, qword [A]` returns `revealBit=1` (classic `base.cc:485`, start byte; Ruby `Sequencer.cc:711-713`, start word), so 7 never-leaked bytes are untainted. In Ruby, an unaligned LD1 at A+4 reveals word(A), and a load at A+4 that crosses into the next word checks only word(A).

**Contradicts.** Paper §4.4: "revealing and using revealed data works only for aligned addresses and at word granularity". The code checks neither alignment nor the size match. The paper doesn't say whether a sub-word LD1 may reveal a whole word; it reads as no, but that is not settled.

**Litmus.** `movzx eax, byte [A]`; `mov rbx, [rax+T]` (commits, reveal A); mispredict; wrong path `mov rcx, [A]`, `mov rdx, [rcx]`. Alloy: no widths. `check_ld` would detect it.

### R-SA-5 (A vs paper; needs `--l2cache`): line-wide over-reveal through L2

**Claim.** In a classic L1+L2 hierarchy, an L1 miss creates a miss packet that shares the CPU's Request (`cache.cc:540`, `new Packet(cpu_pkt->req, cmd, blkSize)`) and is block-aligned (`packet.hh:947`). The L2 hit then writes `pkt->req->revealBit = blk->getRevealBit(pkt->getOffset(blkSize))` (`base.cc:485-486`), which is offset 0. On the response, `serviceMSHRTargets` does not re-read the bit, so the CPU's load gets word 0's bit whatever its own offset. Evictions also carry only bit 0 (`cache.cc:956-957`; the writeback packet is block-aligned). Net effect: if word 0 of a line is revealed and survives eviction to L2, every word in that line comes back revealed on an L1 miss.

**Contradicts.** Paper §5.2 (one bit per word, "mark the data words that have been revealed"). Not reachable in SimSpect's config (no L2), and moot while R-SA-1 holds. It is relevant to the authors' configuration (`runs/run_benchmark.py:41`).

**Litmus.** Reveal word 0 of line X; evict X from L1 (conflict loads); mispredict; wrong path `mov rcx, [X+8]` (L2 hit, untainted) and `mov rdx, [rcx]`.

### R-SA-6 (A vs paper; Ruby only, plausible): Reveal clobbers `accessingAddress`, so the store clears the wrong word

**Claim.** The Sequencer does not enter Reveal packets in `m_RequestTable` (`Sequencer.cc:349-363`, `if(!pkt->isReveal())`), so a Reveal reaches the L1 mandatory queue even while a store to the same line is outstanding. In the L1 in_port, every request on a valid line sets `L1Dcache_entry.accessingAddress := in_msg.PhysicalAddress` before triggering (`MESI_Two_Level-L1cache.sm:518-523`). That includes a Reveal arriving while the line is in SM, since the Reveal transitions cover SM (`:1123`). When the upgrade completes, the store clears the word of `accessingAddress` (`:961`, `:975`), which is now the Reveal's word. The stored word's bit survives.

**Contradicts.** Paper §5.2: "upon the commit of a store instruction, the bit of the corresponding word is cleared". Confidence is plausible: each step is confirmed by reading, but the S→M + Reveal interleaving was not traced.

**Litmus.** Line X shared (S); word W of X revealed earlier; committed `mov [X+W], rsi` (needs upgrade); simultaneously LD2 commits and reveals word V≠W of X; then wrong path `mov rcx, [X+W]` (untainted, new value) and `mov rdx, [rcx]`.

### R-SA-7 (A vs STT/ReCon; plausible, timing-hard): stale taint entries survive squash and block re-taint

**Claim.** The taint map is `std::map<PhysRegIdPtr, DynInstPtr>` (`taint_tracker.hh:27`), keyed by physical register and holding the *source* load. `squashFromInst` erases only entries whose **source** is younger than the squash point (`taint_tracker.cc:186-196`), and `cleanTaints` only those whose source is squashed or committed (`:172-182`). A wrong-path producer P = f(X), with X an older, surviving speculative load, leaves `r_P → X` in the map after P is squashed and `r_P` is freed. If `r_P` is later reallocated as the dest of a speculative load Z, `insertTaint` calls `taints.insert(...)` (`:62`), which does **not** overwrite an existing key, so `r_P` stays mapped to X. When X becomes non-speculative (or revealed), `freeTaints` erases `r_P` (`:138-150`) while Z is still speculative, and a transmitter on `r_P` is released (`delay_unit.cc:82`).

**Reachability (round 2).** The free list is FIFO (`free_list.hh:76-99`), so `r_P` comes back only after every register queued ahead of it. A loop is not strictly required, though. The ROB has 352 entries (`BaseO3CPU.py:156`) and there are only 256 physical int regs (`:145`). When the ROB backs up, for example behind SimSpect's 150-cycle `fnc_commit_stall` at the head, rename runs the int free list close to empty. At that point a register freed by a squash is near the front of a short queue and gets reallocated within a few renames. So a short hand-built gadget can reach it: B0 (slow, correct, makes X speculative) → X → B1 (mispredicted, resolves first; wrong path computes P = f(X)) → correct path B2 (long) → Z → T, with the commit stall filling the ROB. Whether Z actually lands on `r_P` depends on the free-list state, which is deterministic but not predictable by hand.

The standard 6-instruction SimSpect shape does **not** reach it. That shape has one squashing branch, and the window closes at that squash, while this bug needs a squash in the *middle* of the window with an older shadow still open. **Verdict:** confirmed by reading, reachable only in a dedicated multi-branch gadget, not in current corpora.

**Contradicts.** STT's taint invariant (the paper §3.1 keeps the underlying scheme's threat model): a speculatively loaded value stays tainted until its load is non-speculative. Not ReCon-specific.

**Litmus sketch.** A loop with B0 (slow, correct), X = `mov rax,[S]`, then per iteration a mispredicted B1 whose wrong path does `add r?, rax` (allocating fresh regs), until the free list wraps. Then B2 (long), Z = `mov rcx,[secret]`, T = `mov rdx,[rcx]`. B0 resolves before B2 and T issues. The Alloy model cannot generate it (no loops, no physical-register reuse). `check_ld` could detect it if it were hand-built.

### R-SA-8 (A, known): getOldestTaint, plus the ReCon amplification

`taint_tracker.cc:108-131`: the dest maps only to the oldest tainted source, and `freeTaints` erases by source (`:143`). Under ReCon, if the older source is revealed, the merge is untainted even when the younger, unrevealed source is under the same shadow, with no need for staggered branch resolution. **Known** (`bugsynth/RECON_OLDEST_TAINT_BUG.md`, `wiki/findings/mdsToRead/OTB_GENERATION_GAP.md`). The ReCon-specific variant is latent while R-SA-1 holds.

### R-SA-9 (A, known): STL forwarding before the taint check

In `LSQUnit::read` (`lsq_unit.cc:1805`), the full-coverage forwarding path returns at `:2019` before the STT check at `:2079-2090`. **Known** (`wiki/findings/bug/recon_SLF_stlf_bypass/NOTE.md`). ReCon detail: `stlForw` is set only when the store is not yet committed (`:1956-1959`, `!canWB()`). Forwarded loads never get `revealBit` (no cache response), so forwarding never un-protects. That matches paper §4.4.2 ⑨.

### R-SA-10 (B): reveal semantics, contract vs code

Code: reveal happens only at **LD2 commit** (`commitLoad`), only when LD2's **Base or Index** physical source (`renamedSrcIdx(1)`, then `(0)`; x86 order Index=3, Base=4, Data=6, `arch/x86/isa/operands.isa:143-146`) is directly LD1's dest. Any committing non-load that writes that reg clears the entry (`commit.cc:1033-1054`). The reveal is per address/word and persistent until a store or eviction (`base.cc:1754/1771`). The x86 merge source `Data` (src 2) is never consulted, which is conservative.

Contract (`Recon_6.als:316-318`): `Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads - speculation_contract_p[p]))`. That is transitive over rf+ddi (so through ALU ops), LD2 counts once it is merely non-speculative rather than committed, there is no conceal, and it works per location. Mostly **known** as R-1/R-2 (`wiki/findings/audits/2026-10-28/APPROVALS.md:28-29`). New here: the code side is even narrower than R-2's single-hop proposal, because only Base/Index count. See Q1/Q2.

### R-SA-11 (C, low): multi-source reveal over-claims

For `mov rcx, [rbx + rax*8]` with both rbx and rax loaded, the loop reveals rbx's producer address (checked first, `lsq_unit.cc:872-918`), although the committed access exposed only `rbx + 8*rax`. Paper §5.1.1 explicitly allows per-operand reveal ("a load pair can be detected for each operand"), so this is a soundness question about the paper rather than a code-vs-paper bug. Both values were non-speculatively loaded, so under the STT threat model it is arguably moot.

## Round 2 findings (paths that fire in our config: `--caches`, SE, X86O3CPU, schemes 1/2/3)

Papers used in round 2, all local and extracted with pdftotext: DoM `~/Documents/quail/sources/papers/sakalis-2019-dom.pdf` and NDA `weisse-2019-nda.pdf`.

### R-SA-12 (A, fires in our config): taint dropped for whatever value renames to physical int reg 16

**Code.** `secure_scheme/taint_tracker.cc:59-60`:

```cpp
void TaintTracker::insertTaint(const PhysRegIdPtr &regId, const DynInstPtr &load_inst)
{   if (regId->flatIndex() == 16) return;   ...
```

`flatIndex` is the *physical* flat index. Int physical regs come first in the flat space (`regfile.cc:82-86`: `flat_reg_idx` starts at 0 for `IntRegClass`), so this is physical int reg 16. x86 has no zero register: the int arch file is 16 GPRs, then `MicroBegin` = 16 (`t0`), up to `NumRegs` (`arch/x86/regs/int.hh:87-99`). At start-up, physical 16 is simply the 17th register taken from the free list, mapped to arch 16 = `t0` (`cpu.cc:240-250`). `t0` is a common discard destination in microcode (e.g. `andi t0, t10, 0x4, flags=(EZF,)` at `arch/x86/isa/insts/romutil.py:53`), so physical 16 is freed and recycled like any other register. Both `insertTaintInst` (speculative loads) and `propagateTaints` (everything else) go through `insertTaint`.

**Mechanism.**
1. A speculative load (or an ALU op with a tainted source) is renamed with dest = physical 16.
2. No taint entry is created.
3. Consumers see an untainted source (`isTainted`, `taint_tracker.cc:83-87`), so the transmitter load passes `isTaintedInst` (`lsq_unit.cc:2079`) and a tainted branch is not delayed (`inst_queue.cc:1450`).

**Contradicts.** STT's taint invariant, unchanged under ReCon (paper §3.1, "The underlying secure mechanism maintains its entire threat model"). Recon_6's protection set and leakage function both say the value is protected.

**Reach.** Any test, at random. Which physical register a given dest gets depends on the FIFO free-list history (`free_list.hh:76-99`) after libc start-up, so roughly 1 in ~220 dest allocations lands on 16, deterministically per binary and config. Alloy already generates the shapes; `check_ld`/`check_br` detect the result as an ordinary hit.

**Diagnostic idea (for Anna to approve).** Re-run a hit with the `Rename` debug flag. `rename_map.cc:101` prints the arch→phys mapping, and the signature is that the transmitter's source chain contains phys int reg 16. That would be a `PHASE='real_bug'` bucket on all `gem5-recon*` builds (build-specific scope).

**Litmus.** Any STT_6 ld-transmitter shape. To force it on purpose you would have to steer register allocation, which isn't practical; finding it in existing hits via the Rename trace is easier.

### R-SA-13 (A, fires; schemes 1/2/3): FP/SSE loads are never speculative

**Code.** `decode.cc:684-695`:

```cpp
if (inst->isCondCtrl()){ ... insertBranch(inst); }
else if (inst->isStore()) { insertStore(inst); }
else if (inst->isFloating()){ // cpu->shadowTracker.insertException(inst); }
else if (inst->isLoad() && cpu->shadowTracker.hasShadow()) { insertSpecInst(inst); }
```

`Ldfp`/`Ldfp87` are loads with `is_float=True` (`arch/x86/isa/microops/ldstop.isa:512-528`) whose destination is a `FloatReg` operand. That operand adds `IsFloating` unconditionally (`arch/x86/isa/operands.isa:86-88`), and flags are collected from operands (`arch/isa_parser/isa_parser.py:396`). So an FP load hits the `isFloating` branch and is never marked speculative. FP *stores* still cast shadows, because `isStore` is tested first.

**Consequences.**
- STT: rename takes the `propagateTaints` path (`rename.cc:716-720`), so the dest is untainted whenever the address is.
- NDA: the delay needs `isSpeculative()` (`lsq_unit.cc:194-196`), so the value propagates at once.
- DoM: L1-only is set only for speculative loads (`lsq.cc:1443-1446`), so a miss fills the cache.

**Contradicts.**
- STT/ReCon: every load under a shadow is protected (paper §3.1).
- NDA §5.1: "NDA marks all micro-ops dispatched after an unresolved branch or store as unsafe".
- DoM: "shadowed loads" are delayed on a miss (DoM paper, "The L1 behavior for shadowed loads").

**Litmus.** Mispredicted/held `jae out`, then `movq xmm1, [rbx+rdi*8]` (secret, via `ldfp`), then `movq rax, xmm1` (`mov2int`), then `shl rax,6`, then `mov rcx, [rsi+rax]` (the transmitter executes). Control: the same test with a GPR `mov`. Stage 2 can't generate it (GPR-only vocab, like STT audit Q2). `check_ld` detects it on scheme 2. On NDA/DoM, see R-SA-18 for criterion caveats.

### R-SA-14 (A, DoM): line-crossing speculative loads bypass delay-on-miss

**Code.** `LSQ::SingleDataRequest::buildPackets` sets `setL1Only()` for speculative DoM loads (`lsq.cc:1443-1446`). `LSQ::SplitDataRequest::buildPackets` (`lsq.cc:1470-1515`) never does (`grep L1Only cpu/o3` finds only `lsq.cc:1376/1446`). The split packets go down as normal reads: an L1 miss allocates an MSHR, fetches from memory and fills L1.

**Contradicts.** DoM: on a shadowed L1 miss, "the request will simply be dropped" (DoM paper, L1-behavior list).

**Litmus.** Under DoM: shadowed `mov rax, [rbx + 60]` with `rbx+60` 4 bytes before a line boundary and the line uncached. The second line fills speculatively; probe it after the squash. SimSpect's concretization uses aligned i64 slots, so it can't generate this. `check_ld` would see `reached_cache`.

### R-SA-15 (A, DoM): speculative L1 hits update replacement state immediately

**Code.** On an L1 hit, the DoM path is the ordinary `BaseCache::recvTimingReq` → `access()` (`base.cc:474-481`). The L1-only special case (`:461-471`) handles only misses, and no "release" message exists anywhere in the tree (no delayed replacement-update code).

**Contradicts.** DoM paper: "In case of an L1 hit, the cache responds to the request but delays any operations that might cause visible side-effects, such as updating the replacement state." The paper also describes the release request.

**Detection.** None in SimSpect: it would need an LRU/footprint criterion. Out of `check_ld`'s scope.

### R-SA-16 (A, scheme 2 implicit channel): tainted-address stores resolve, squash and train the predictor

**Code.** `LSQUnit::executeStore` → `checkViolations` (`lsq_unit.cc:639`, `:846`) has no taint check. The only taint checks in the LSQ are on loads (`:1778`, `:2079`), and there are none in `iew.cc`, `mem_dep_unit.cc` or `store_set.cc` (grep). A store whose address depends on a speculatively loaded value therefore (1) frees its store shadow (`shadow_tracker.cc:229-235`, `effAddrValid`), (2) squashes a younger load that aliased (a memory-order violation, a secret-dependent pipeline flush), and (3) trains the store-set predictor, which persists after the squash.

**Contradicts.** STT's implicit-channel rule for resolution- and prediction-based channels, which ReCon keeps (§3.1, "RECON does not affect either of them"; §4.5.2, "mitigated by updating the predictor with non-speculative values"). This is the same issue as STT audit S2 on `/work/stt`, but on the Recon-STT code. (1) is harmless on its own, because an older shadow still covers the taint source.

**Litmus.** Held mispredict; L1 `mov rax,[secret]`; younger independent L2 `mov rbx,[X]` executes early; S `mov [rsi+rax*8], rdx`. A squash happens iff `rsi+8*secret == X`; observe via timing or the store-set entry on re-execution. Detection: none (`check_ld`/`check_br` don't observe squashes or predictor state). Alloy has no store-address transmitter.

### R-SA-17 (B): which instructions cast shadows

Code: only `isCondCtrl()` branches and stores (`decode.cc:686-690`). Exceptions are commented out (`:692`), and indirect jumps/returns cast nothing. x86 `jcc` is a conditional `wrip`/`br` microop (`regop.isa:446`, `seqop.isa:162`), so Spectre-v1 shapes are covered. Squash-vs-free ordering is fine: `Commit::commit` processes the IEW squash (`commit.cc:832-866`, `rob->squash` → shadow/taint/delay `squashFromInst`) before `markCompletedInsts` sets `branchResolved(true)` (`commit.cc:1464`, called at `:667`). `shadowTracker.tick` then runs after `commit.tick` (`cpu.cc:484-489`). I found no early-free path in default timing.

What the papers include:
- ReCon §3.1: "speculation cast by control flow and store instructions".
- NDA §5.1: "following a predicted branch (via the BTB, RSB, etc.)".
- DoM: E-, C- ("branches and jumps ... target address"), D- and M-shadows.

Recon_6's `has_unresolved_brs_p` matches the code for conditional branches; the store shadows are the known P1/`STT_6_shadows` item. See Q5.

### R-SA-18 (B, affects the STL round): `check_ld`'s leak criterion vs what NDA and DoM promise

- **NDA (scheme 1).** The forwarded-load path builds a `WritebackEvent` (`lsq_unit.cc:2008-2012`) whose `process()` calls `writeback()` directly (`:77-86`). The NDA delay lives only in `completeDataAccess` (`:194-210`), so a speculative store-forwarded load broadcasts its value at once. Under permissive NDA (secrets in memory, NDA §4.1/§5.2), the forwarded value is register data from the store, so this probably leaks nothing secret. But it is a deviation from "loads ... unsafe until resolved", and `check_ld` scores `store_forward` as a **leak** (`specs/leakage/recon.json` data_obtained), so STL tests on NDA will show these as hits.
- **DoM (scheme 3).** Speculative L1 hits return data and propagate by design (DoM paper; code `base.cc:474-486`), but `check_ld` counts `reached_cache` as a leak. So every DoM test whose transmitter hits L1 in-window will score as a leak, even though DoM only promises that misses are delayed (plus replacement state, R-SA-15).
- See Q6.

## Areas reviewed / not reviewed

Reviewed:

- ReCon reveal end to end: `lsq_unit.cc` (`completeDataAccess` 170-260, `commitLoad` 851-965, `read`/forwarding 1805-2095), `commit.cc` (1000-1060), `rename.cc` (700-800; the LPT-at-rename block is `if(false)`), `inst_queue.cc` (1040-1065, 1445-1470), `secure_scheme/{taint_tracker,shadow_tracker,delay_unit,pair_loads}`, `decode.cc:684-695`.
- Classic caches: `base.cc` (Reveal, hit, write, fill, invalidate, evict), `cache.cc` (createMissPacket, evictBlock), `cache_blk.hh`.
- Ruby: `Sequencer.cc` reveal paths, `CacheMemory.cc` bit helpers, `MESI_Two_Level-L1cache.sm` in_port and the store/reveal actions.
- x86 load micro-op operand order.
- SE physical-page allocation order.
- Paper §1, §3.1, §4.1-4.5, §5.1-5.4 (local PDF via pdftotext).

Round 2 also reviewed:

- The shadow tracker in full, plus the squash/commit/tick ordering (`commit.cc:788-866`, `:1464`, `cpu.cc:470-490`).
- The decode speculative rule.
- The taint tracker in full.
- The NDA path: `completeDataAccess`, the forwarding `WritebackEvent`, `delay_unit` free logic.
- The DoM path: L1-only marking, failed-L1 handling (`lsq.cc:1374-1381`), reissue (`delay_unit.cc:195-215`), DoM branch delay (`inst_queue.cc:1459`, `delay_unit.cc:138`).
- Store execution/violation code for taint checks.
- x86 operand flags (`IsFloating`) and the int register layout.
- Free-list ordering.
- The DoM and NDA papers' protection claims.

Not reviewed (each lower yield, or outside `--caches`):

- Address prediction / Doppelganger (`--address_prediction`, `lsq_unit.cc:1717-1790`, `:2081-2111`, `address_prediction/`). It is compiled in, but SimSpect does not pass the flag, so it is not reachable in our config.
- The NDA/DoM `allow_leaked` reveal branches (`lsq_unit.cc:199-210`, `:242-250`, `inst_queue.cc:1058`). They are inert while R-SA-1 holds.
- DoM M-shadows / TSO load-load ordering on invalidation (single core, so unreachable).
- DoM tainted-branch handling beyond `inst_queue.cc:1459` (all but the oldest branch delayed).
- Ruby: the L2 controller, coherence downgrades, and the R-SA-6 interleaving trace.
- SimSpect resolve hooks near `commit.cc:1464` (hook scope).
- Faulting-load / E-shadows (commented out; listed under R-SA-17).
- Whether the cluster's `base.cc`/`commitLoad`/`taint_tracker.cc`/`decode.cc` match the local copy.
- Prefetchers (not configured).
- Split-load reveal-bit handling.

## Questions for Anna

**Q1 (blocks interpretation of every Recon result). Should SimSpect keep treating `gem5-recon*` + `--allow_leaked` as "ReCon"?** Evidence: R-SA-1 (implementation reveal dead in classic caches) plus R-1 (Alloy reveal is a no-op).

- (a) Relabel the current Recon runs as "Recon-STT, reveal inactive" and stop reading Recon-vs-STT differences as ReCon signal. Costs nothing.
- (b) Also run Recon with `--ruby` (the build is MESI_Two_Level), where reveal does reach the right address. That exposes R-SA-2/3/4/6 as testable, but needs the harness checked under Ruby and an R-2 model to generate reveal-dependent tests.
- (c) Patch the one missing assignment so classic Reveal works. That modifies the defense rather than a hook, which CLAUDE.md forbids, so it is listed only for completeness.
- *Recommendation:* (a) now, after the cheap stats check (`revealRequests > 0`, `allowlistedTaintsFromTT == 0` in any scheme-2 `stats.txt`). Then (b) only if ReCon-specific results matter for the paper.

**Q2 (contract semantics). Should the Recon contract model conceal-on-store and value-versioned reveal?** The paper (§4.4) says a store conceals and only the leaked contents are public. Recon_6 is location-based with no conceal, so it can never flag R-SA-2/3.

- (a) Keep location semantics and no conceal (current state). The contract is then looser than the paper, and stale-reveal bugs are invisible.
- (b) Add a store-commit conceal: R-2 already proposes it.
- (c) (b) plus a single-hop direct-pair reveal restricted to committed LD2 and Base/Index-only addressing, matching the code exactly.
- *Recommendation:* (b) as part of R-2, because it is what the paper claims. (c) is more faithful to this code, but it encodes implementation detail (Base/Index only) that the paper calls a design choice (§5.1.1).

**Q3 (scope). Are R-SA-3/4/5 (granularity and width) in scope for SimSpect at all?** The Alloy model has atomic locations.

- (a) Out of scope for the model. Record them as source-audit-only findings.
- (b) Add width/offset variation in Stage 2 (parsexml) for reveal-dependent tests, which is a concretization change that needs approval.
- *Recommendation:* (a) for now. Revisit only if Q1(b) is chosen.

**Q4. Is R-SA-7 (stale taint after squash) worth a hand-built gadget on `/work/gem5-recon-modded`?** Round 2 found that it does not need a loop: a full ROB (352 entries vs 256 int phys regs) under the commit stall nearly empties the free list. It still needs a squash in the middle of the window with an older shadow open, which current corpora never contain.

- (a) Park it.
- (b) Hand-build one 3-branch gadget as a bugsynth-style probe.
- *Recommendation:* (a), and note it in `BUGS.md` as unconfirmed. R-SA-12 is the better use of a gadget slot.

**Q5 (contract, R-SA-17). Which instructions should cast shadows in the Recon/NDA/DoM contracts?**

- (a) Keep conditional branches only (matches the code for Spectre-v1 shapes; Alloy branches are conditional anyway). Add store shadows via the pending P1/`STT_6_shadows` decision.
- (b) Also model indirect-control shadows (the papers include them), knowing this code would then be expected to fail them.
- (c) For DoM only, also model E-shadows (the DoM paper lists them; the code ignores them).
- *Recommendation:* (a) for this round. Record (b)/(c) as known code-vs-paper gaps rather than generating tests for them.

**Q6 (criterion, R-SA-18; needed before the STL round runs on schemes 1 and 3). What counts as a leak on NDA and DoM?**

- (a) Keep `check_ld` as is. Expect `store_forward` hits on NDA and L1-hit hits on DoM, and bucket them as "allowed by design" with per-scheme diagnostics.
- (b) Write per-scheme criteria: NDA = a speculative load's value reaches a dependent (forwarding included, so the NDA forward bypass becomes a real finding); DoM = a speculative L1 *miss* reaches beyond L1 (and, optionally, an LRU footprint check for R-SA-15).
- (c) Run only scheme 2 for the STL round.
- *Recommendation:* (b). Each criterion should check only what its paper claims (Anna's 2026-11-08 rule, `URGENT_TODO.md`); (a) would flood the results with by-design hits.

**Q7 (R-SA-12, R-SA-13). Should SimSpect add diagnostics and vocabulary for these?**

- (a) Add a `diag_physreg16` bucket for `gem5-recon*` (re-run hits with the `Rename` debug flag; the signature is phys int reg 16 in the transmitter's source chain). Build an `xmm` bugsynth gadget for R-SA-13.
- (b) Also add an SSE load/move to the Stage-2 vocabulary (a concretization change that needs approval).
- (c) Leave them as source-audit findings.
- *Recommendation:* (a). R-SA-12 can contaminate existing Recon hit counts, so a bucket is worth it. One gadget is enough for R-SA-13.
