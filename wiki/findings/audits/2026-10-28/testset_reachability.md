# STT_6 testset reachability vs the footprint criteria (CleanupSpec / InvisiSpec / SpecLFB)

**Audit, 2026-10-28, read-only, done in about 12 minutes.** This is code reading only. No local testset was available: `testsets/` on this Mac holds only `DEMO_corpus` and `README.md`, and `results/STT_6_*_full/` hold only `run_config.jsonc`. So every "reachable / unreachable" below is inferred from the generator code and the cache geometry. None of it is measured. The cheap way to confirm is listed in the last section.

## Claim up front

Every STT_6 test touches a tiny memory footprint, about 2 KB, all of it on one function's stack, and every byte of it is written by the program's own prologue before the test region runs. So:

- **Unreachable (a 0-hit result on these terms says nothing):** a D-TLB miss or D-TLB fill (InvisiSpec DTLB); an L2 or directory miss that goes to memory (an InvisiSpec/CleanupSpec/SpecLFB `fill` at L2); a coherence change caused by another core (single core, SE mode). A footprint that depends on the secret value is also out: secrets are almost always 0, and the probe array does not give each secret value its own line.
- **Reachable only by accident** (through the prologue overflowing the cache, depending on replacement policy and stack placement, with no generator knob for it): an L1D miss by a speculative load, which every L1D `fill`/`evict` term needs. That covers SpecLFB's whole criterion, CleanupSpec `installed`/`evicted` (d_victim) at L1D, and InvisiSpec `fill`/`evict`/`repl_touch` at L1D and L2.
- **Practically unreachable:** line-crossing (split) loads (UV4). They need a secret ≡ −1…−7 (mod 64), which takes a committed `notq` → store → load chain.

## Evidence (file:line)

### Model scope

- `STAGE1_alloy/models/STT_6.als:315-317`: `run gen_lit … for 9 but exactly 6 Instruction`. There are at most 6 instructions, and `Mem_s`/`Reg_s` (`:25-26`) share the scope of 9 `State` atoms. The protected state is `Mem_s` (`:326`, `hardware_protection_policy`).
- The model's memory is *symbolic*: atoms only, with no addresses, lines, sets, pages or cache state. Nothing in the model can ask for "same set", "different page" or "cold line". Whatever cache state a test has comes entirely from concretization.

### Memory layout (parsexml.py)

- Locked `Mem_s$*` atoms map to offsets `i*8` (`STAGE2_compilation/parsexml.py:1476-1478`). Free-pool atoms map to `(n_locked+i)*8` (`:1502-1504`). Each unspecified memory slot gets the next fresh slot, `free_mem_slot*8` (`:1556-1558`). `alloca_total_slots = free_mem_slot` (`:1574-1575`). The result is one contiguous `%mem_base = alloca [N x i64], align 8` (`:1996`), with N ≲ 6–12. That is ≤ ~100 B, so 2 or 3 lines of 64 B.
- `%probe_mem = alloca [256 x i64], align 64` (`:2005`) is emitted only if some load or store has a *specified* `inaddr` (`:1987-1992`). It is **2048 B = 32 lines**. The comment at `:2003` says "256 slots × 64 bytes (cache-line stride) = one cache line per possible byte value". That is **not what is emitted**: the stride is 8 B, the total is 2 KB, and addressing is `(%probe_base, %secret, 1)`, scale 1 (`:2082-2091`, and stores at `:2155-2168`). Secret values 0…63 therefore all land in the *same* line.
- **Every slot is pre-written in the prologue:** `store volatile i64 0` to every `mem_base` slot (`:1997-2000`), then to all 256 `probe_mem` slots (`:2006-2009`), then `mfence` (`:2017`). Registers read before they are written are zeroed (`asm_force(…, "0")`, `:2011-2012`).
- **The secret is almost always 0.** Every `ld` transmitter's address is fed directly by a single load (CLAUDE.md OTB note: 66,512/66,512), and that load reads a slot that was zero-initialized. On zero inputs, the ALU ops give `bitnot`/`notq` → −1 and `add`/`leaq` (and `xor`) → 0. The interleave chain ops are at `:299-309`; I did not re-read the base `other` op table in the time available. A nonzero secret (−1, −2, …) needs a committed `notq` feeding a store into the slot the secret-load reads.
- **Pages:** the footprint is about 2.1 KB of contiguous stack, so it sits in one 4 KB page, or two if it straddles a boundary. The prologue touches all of it.

### Cache geometry (the run configs)

| campaign | L1D | lines / sets / ways | set stride | prologue vs L1D |
|---|---|---|---|---|
| `results/STT_6_cleanupspec_full/run_config.jsonc:36` | 2 kB / 4-way | 32 / 8 / 4 | 512 B | probe_mem (32 lines) = exactly the L1D capacity, plus mem_base |
| `results/STT_6_invisispec_full_spectre/run_config.jsonc:38` (futuristic `:37`) | 1 kB / 2-way | 16 / 8 / 2 | 512 B | probe_mem is 2× the L1D capacity |
| `results/STT_6_speclfb_full/run_config.jsonc:35` | 1 kB / 2-way | 16 / 8 / 2 | 512 B | probe_mem is 2× the L1D capacity |

L2 is 2 MB / 16-way in all of them (cleanupspec `:38`, invisispec `:40`, speclfb `:37`). That is about 1000× the program's data footprint.

## Per-criterion verdict

### CleanupSpec (`specs/leakage/cleanupspec.json` terms `installed`/`evicted`/`invalidated`/`restored`)

- **Set-full, so that a speculative fill evicts a committed victim (d_victim / `evicted`):** the *set-full* half is met by accident. The prologue writes ≥ 32 lines into a 32-line L1D, so every set is full. The *speculative fill* half is the problem. Speculative loads go only to `mem_base` slots or to `probe_mem + secret`, with secret ≈ 0, i.e. probe line 0. Both were written moments earlier, so an L1D miss happens only if the prologue's own overflow evicted that exact line. With LRU, the 32-line probe sweep (written after `mem_base`) would push `mem_base` out and leave probe line 0 resident. With CleanupSpec's random L1 replacement (`cleanupspec.json` `requires.why`, Scheme.py:76-82), which lines survive is seed- and stack-dependent. **Verdict: reachable only by accident.** No test is built to fill a set with chosen lines (a 512 B stride in the model or in concretization). The L2 half of `installed` (an L2 fill) is **unreachable**, because every reachable line is already in the 2 MB L2.
- **Line-crossing loads (UV4):** `mem_base` accesses are 8 B at 8-aligned offsets (`:1477`, `:1557`), and 64 % 8 = 0, so they **never cross**. A `probe_mem` access crosses only when secret mod 64 ∈ [57, 63], e.g. secret = −1 from `notq 0`. That is reachable in principle within 6 instructions (`notq` → `str` → `ld` → xmit), but it is not targeted and probably very rare. **Verdict: practically unreachable.**
- **A warm line for hit vs miss:** warm lines are everywhere (every slot is pre-written). A *cold* line is the hard part, as above. Hit-vs-miss contrast between secrets is **unreachable**, because all small secrets share one line (`:2003` vs `:2005`/`:2091`).

### InvisiSpec (`specs/leakage/invisispec.json` footprint kinds `fill, evict, inv, coh, repl_touch` over OBS = L1D, L2, DIR, DTLB)

- **DTLB:** **unreachable.** The single-function stack footprint of about 2 KB (1–2 pages) is fully touched by the prologue stores, so a speculative load never misses the D-TLB. There is no multi-page layout and no large sandbox.
- **L2 / DIR as separate events:** an L2 *miss* to memory (a DIR fetch) is **unreachable**, since everything is already in L2. An L2 *hit* after an L1D miss (`repl_touch` at L2, and the L2-side record of an L1 Spec-GetS) is **reachable only by accident**. In the 1 kB/2-way L1D, the 2 KB probe sweep overflows each set twice over. With LRU, probe lines 0–15 and the `mem_base` lines are likely evicted to L2 before the test region, unless a committed load re-warms them. That is the likely way an L1D miss happens here. It is unverified.
- **`coh`:** single core, SE mode, so no remote sharers. Coherence changes beyond the core's own E/M grant are **unreachable**.

### SpecLFB (`specs/leakage/speclfb.json` footprint kinds `fill, evict` at L1D and L2)

- **A speculative load misses L1D (cold):** **not always, and not by design.** It depends on the prologue overflow in the 1 kB/2-way L1D, as above, and on whether a committed load re-warmed the line. An L2 refill is **unreachable**, since everything is already in L2. So only L1D `fill`/`evict` can ever fire. `evict` comes for free once a fill happens, because L1D is full after the prologue.

## Consequence

A 0-hit campaign on these three builds is **vacuous** for the DTLB, L2/DIR-miss and remote-`coh` terms, and for split loads (UV4). For the L1D fill/evict terms it is **only meaningful once someone measures how many tests actually have a speculative L1D miss**. Without that count, "0 hits" can't tell "defense held" from "the test never stressed it".

## How to confirm (cheap, read-only on existing outputs)

1. On the cafe2 container's `testsets/STT_6/<mode>/asm`, histogram `alloca_total_slots` and the presence of `probe_mem` from the `.ann.json` / `.s` header (`# alloca …`, `:1599`/`:1802`). Grep for `notq` feeding a store to measure the nonzero-secret and split-load rate.
2. From the existing campaign traces (Ruby/LSQ debug or pipeview), count speculative-window loads with an L1D miss per campaign. That count is the denominator that makes a 0-hit result meaningful.
3. If coverage is needed, raise it as a concretization or prologue change for Anna's approval, not a model edit. Options: a cold or flushed target line, a 512 B-stride eviction-set prologue, a probe stride of 64 B (matching the `:2003` comment), an unaligned or line-straddling slot, and a second page. Per CLAUDE.md, this is a pipeline change that needs sign-off. It is not proposed here as a tuning.
