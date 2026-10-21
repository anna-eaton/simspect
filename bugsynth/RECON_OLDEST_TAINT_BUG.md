# The recon "getOldestTaint" (OTB) bug in STT — what it is, why it leaks, and where we're at

*Conceptual writeup of the bug + current status. For the full reproduction (Alloy/concretization changes,
the resolve-stall fix, the validity matrix) see `OTB_BUG_REVIEW.md`. Source: recon's
`src/cpu/o3/secure_scheme/taint_tracker.cc` on `/work/gem5-recon-modded`; original report in
`reconresults.md` (Bug 1).*

## One line
When an ALU op has **two tainted (speculative-load) source operands**, recon's taint tracker associates the
result with only the **oldest** source. When that oldest source's branch resolves first, the result is
**un-tainted early** — even though a younger, still-speculative source also fed it — so a transmitter using
that result (e.g. a load whose address is the ALU output) is allowed to access cache while the younger
secret is still speculative.

## The vulnerable scenario
```
   ba:  correctly-not-taken branch (resolves EARLY, no squash; slow to resolve — e.g. cache-miss condition)
     la   load_A   (OLDER, under ba)            ── speculative, tainted
   bb:  mispredicting branch (stays SPECULATIVE long)
     lb   load_B   (YOUNGER, under bb)          ── speculative, tainted
     o  = ALU(la, lb)      e.g. leaq (%rax,%rcx)   ── 2 tainted sources
     x  = load(o)          movq (..,o)              ── TRANSMITTER, secret-dependent address
```
`la` and `lb` are both speculative loads (both taint their destinations). The ALU `o` merges them; the
transmitter `x` is a load whose **address** is `o`'s result — so its address depends on the (younger,
still-secret) `lb`.

## The mechanism (recon source)
`src/cpu/o3/secure_scheme/taint_tracker.cc`:
```cpp
getOldestTaint(inst):                 // line 119
    for each src reg of inst:
        if isTainted(reg) && taints[reg]->seqNum < oldest->seqNum:
            oldest = taints[reg];     // BUG: picks the OLDEST taint source
    return oldest;

propagateTaints(inst):                // line 108
    const oldest = getOldestTaint(inst);
    for each dest reg: insertTaint(dest, oldest);   // dest tracks ONLY that single oldest source

freeTaints():                         // line 134
    for (reg, srcInst) in taints:
        if !srcInst->isSpeculative(): erase(reg);   // free when that source is non-speculative
```
So the ALU dest `o` is made to track **only `la`** (the oldest source). When `ba` resolves, `la` becomes
non-speculative → `freeTaints` erases `o`'s taint → `x`'s address is treated **untainted** → the
transmitter load issues to cache. But `lb` (younger, under the still-unresolved `bb`) is **still
speculative**, and it genuinely feeds the address. The "correct" behaviour is to track the **youngest**
source (which resolves last), or to free a dest's taint only when **all** contributing sources are
non-speculative.

## Why it leaks — and the precise severity (our validity matrix)
The transmitter `x` accesses cache with a **secret(`lb`)-dependent address while `lb` is still
speculative** — the classic speculative cache side channel STT is meant to prevent. Running the *same*
gadget under three conditions (xmit cache-access tick = when it leaks):

| condition | xmit accesses cache | meaning |
|---|---|---|
| **scheme 0** (unsafe), OTB timing | **2677500** (immediate) | no protection (baseline) |
| **scheme 2** (STT), OTB timing (`la` resolves first) | **3924500** (= `la`-resolve, *before* `lb`-resolve 7174500) | **BUG: getOldestTaint frees at the OLDER load → leaks while `lb` speculative** |
| **scheme 2** (STT), control (`la` & `lb` resolve together) | **7174500** (= `lb`-resolve) | **STT fully protects** |

This **refines** reconresults.md's "STT provided no additional protection": STT *does* protect in general
(the control holds the xmit from 2677500 → 7174500, i.e. until `lb` resolves). The bug is **specifically**
that the dest taint is freed at the **older** `la`'s resolution (3924500) rather than the younger `lb`'s
(7174500). The control — STT fully protecting the same gadget when there's no OTB timing — is the decisive
evidence that this is a real defense failure, not a checker artifact.

## How we demonstrate it (SimSpect)
Differential on /work/gem5-recon-modded scheme 2 + `allow_leaked`: the transmitter is **released
earlier** under OTB timing (`la` resolves first) than under the same-stall control (`la` & `lb` together),
by a clear margin, while `lb` is still speculative. **30/30** generated gadgets leak at the pipeline's
default mispredict stall; robust across the timing band (5/5 at every tested stall pair; control 0/5).
Run: `python3 bugsynth/otb_check.py 30 2500 5000`. The reference hand-crafted test
(`oldest_taint_bug/debug_out/inst-oldest-taint-bug.s`) leaks identically. Full reproduction + the key
pipeline fix: `OTB_BUG_REVIEW.md`.

> **Key unblock:** for many iterations the transmitter "never issued" on recon-modded. Cause: recon-modded's
> `se.py` reads the *older* ann schema (`branch_pc_addr_hex`/`x86_branch_offset_hex`), not `branch_addr_hex`
> — so it silently skipped every annotation → no resolve-stall → the mispredict branch squashed the gadget
> before it could execute. Fixed by emitting the alias keys in `compile_annotate.py` (bugsynth-only,
> additive; keeps /work/stt working).

## Where we're at (honest status)
- **Reproduced and validated** generally: 30/30, robust across timing, scheme-0-vs-2 + protected-control
  matrix, reference test matches. This is a solid, real-bug reproduction.
- **But it does NOT yet emerge from the unmodified model — we force the shape.** The base model's security
  predicate (`secure_speculation_scheme_p`) *would* correctly flag an OTB gadget as insecure (the xmit
  address is in the protection set). However:
  - The base **enumeration never produces** the `2-load→ALU→xmit` shape: 0/100k instances route a
    transmitter address through an ALU (re-tested 2026-06-09 with the relaxed driver but no forcing →
    0/60). Simpler direct-`load→xmit` / `branchx` shapes exhaust the budget first.
  - The base **RR-minimality prunes** multi-source merges (resolving one load's branch leaves the other
    tainted → "not minimal" → rejected).
  - So `otb_class` (in `models/STT_6_otb2.als`) **hand-specifies the gadget shape**, and the driver drops
    the minimality. The leak is in the model's *definition*; the *generation* is forced.
- **Structural diversity is 1 template** (2 branches + 2 loads + ALU + xmit exactly fill the
  `exactly 6 Instruction` scope; only register/offset assignment varies). Not a tuning artifact — the leak
  is robust — but it is a generation limitation.
- **To make OTB come from the model (the principled path):** (1) relax the per-branch minimality to allow
  **multi-source leaks** in general (a leak may have ≥2 contributing speculative sources), and (2) fix
  enumeration **coverage** so rare/complex skeletons actually appear (e.g. skeleton-stratified enumeration
  with blocking clauses; optionally a larger instruction scope for in-context variation). With those, OTB
  would appear without `otb_class`. See the "future directions" block in `STATUS.md`.

## Verdict
**Real bug** (recon's STT frees a merged taint at the older source's resolution, letting a tainted-address
load reach cache while a younger source is still speculative). Correct fix (per reconresults.md): track the
**youngest** taint, or free a dest taint only when **all** contributing sources are non-speculative.

## Value-flip cross-check (2026-06-09) — OTB SURVIVES the faithful test (unlike pending-squash)
After the pending-squash reproduction failed the value-flip non-interference test, OTB was re-checked the
same way (vary the in-memory secret 0 vs 1 on the SAME binary). OTB **stands**, because it is a
**cache-state channel**, not a timing channel: the transmitter issues + accesses cache at the same tick
regardless of the secret value — and that *speculative tainted-address load reaching cache* IS the leak
(the secret determines *which* line is brought in). The same-binary control (la & lb resolve together →
the xmit is held until lb resolves at ~7174500, vs released at ~3924500 when la resolves first) already
proves the early access is getOldestTaint's wrong early-free, on one fixed binary — so it is NOT the
binary-swap artifact that invalidated the pending-squash taint-flip. Net: OTB is a valid, faithful-test-
consistent reproduction; pending-squash is not (yet).

## Scope nuance (2026-06-09) — OTB demonstrates the DEFENSE FAILURE, not (yet) line-granular exfiltration
Being precise about what OTB shows: the validated leak is the **defense failure** — recon's getOldestTaint
frees the merged taint at the older load's resolution, so the transmitter (a tainted-address load) **reaches
cache speculatively when STT/recon should hold it**. That IS the bug (reconresults Bug 1: "STT allows it to
access the cache"), and it's airtight: the la-first-vs-control differential (same binary), the scheme-0/2
validity matrix, and the reference test all confirm a speculative cache access that should not happen.
What the current litmus gadget does NOT construct is the downstream **secret→cache-line exfiltration**: the
xmit address = ALU(la, lb) of small values, so flipping the in-memory secret 0→1 shifts the address by only
~1-2 bytes — **sub-cache-line**, so the specific 64B line generally does NOT change. A real exploit (and a
fuller demo) needs the secret scaled to line granularity (arr[secret << 6]-style index), which would be a
concretization addition. Net: OTB = a real, validated **defense failure** (the access happens); the
line-granular secret channel on top of it is an exploitation step not yet built. (This is the same level of
rigor applied to retract the pending-squash repro — stated honestly so the claim isn't over-read.)
