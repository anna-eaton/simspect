# BUG: STT visibility-point ↔ squash-drain race (speculative load→load cache leak)

**Build:** `/work/stt/build/X86/gem5.opt` (DerivO3CPU, `--scheme=2` = STT, `implicitChannel`).
**Testset:** STT_6 (and STT_6_interleave) load→load gadgets. **Found by:** the slow_comm_squash1
experiment. **Verdict: a real STT defense weakness** (timing-parameter-dependent), NOT a check_ld
false positive, NOT a model over-approximation, NOT a SimSpect hook artifact, NOT stock-config.

## What leaks

A speculative load whose **address is produced by an older speculative load** (load→load) on a
**mispredicted** path performs a **real, observable L1 cache access** (sends a packet) and is *then*
squashed — i.e. the classic speculative cache side-channel that STT is supposed to prevent. The Alloy
model correctly puts the xmit address in the protection set (231/231 sampled hits are
`addr_from_load`, see `../sample/xml_shape.json`), and `diag_ld_cache_reach.py` confirms the access is
real (`reached_cache`, not a delay/spec-read/never-executed false positive).

## Root cause (mechanism, from /work/stt source)

STT's load taint is rooted and cleared in the ROB walk:
- `rob_impl.hh:compute_taint()` (812–814): a load's dest is tainted iff `isAccess() && !isUnsquashable()`.
- `rob_impl.hh:updateVisibleState()` (519–520): `isUnsquashable ⟺ isPrevBrsResolved()` (non-futuristic),
  and a branch keeps `prevBrsResolved=true` for *younger* insts while it is `readyToCommit() && !isSquashed()`
  (489–495).

So while the controlling mispredict branch is unresolved → producer load is squashable →
`isDestTainted=true` → the xmit's `address_flow` sees a tainted producer → xmit `isArgsTainted` →
`readyToExpose=false` → **held** (STT working). The instant the branch **resolves**, `isPrevBrsResolved`
propagates to the *younger wrong-path* insts → producer becomes `isUnsquashable` → its dest-taint drops
→ xmit address untainted → `readyToExpose=true` → **the load re-issues and accesses the cache.**

But that branch resolution is exactly what *squashes* the wrong-path load — and the squash is **not
instantaneous**: it propagates commit→IEW over `commitToIEWDelay` cycles and drains the ROB at
`squashWidth`/cycle. **In the gap between branch-resolution (taint cleared) and squash-completion, the
freshly-untainted wrong-path load performs its cache access.** STT's visibility point treats "previous
branches resolved" as "safe to expose," which is true for *correct-path* insts but false for a
*wrong-path* inst during the squash drain. The mechanism never enforces "squash-before-expose."

**IQ smoking gun (inst-047231, slow-comm):** sn:571 had all operands ready and was first issued at
2,931,500 (data was *not* the bottleneck), held ~29 cyc, **re-issued at 2,946,000** right after the
branch `0x401c51` resolved at 2,945,500 → cache packet 2,946,500 → squashed 2,947,500.

## Trigger / parameter dependence (rigorously isolated on inst-047231, fnc-hook OFF)

The leak appears when the resolution→squash gap is ≥ ~2–3 cycles. Isolation (squashWidth `sw`,
`commitToIEWDelay` = bwd, `iewToCommitDelay` = fwd):

| sw | bwd | fwd | leak? |
|----|-----|-----|-------|
| 8  | 1   | 1   | no (**stock**) |
| 1  | 1   | 1   | no (squashWidth alone is NOT the driver) |
| 8  | 1   | 30  | no (forward delay alone is NOT the driver) |
| 8  | 2   | 1   | no |
| 8  | **3** | 1 | **LEAK** |
| 8  | 2   | 2   | **LEAK** |
| 8  | 4   | 4   | **LEAK** (realistic squashWidth=8) |

- **Driver = `commitToIEWDelay`** (the backward commit→IEW wire that carries the squash), threshold
  ≈ 2–3 (lower when `iewToCommitDelay` also raised). `squashWidth` and forward-delay-alone do **not**
  cause it; `squashWidth=8` (realistic) still leaks.
- **Per-gadget heterogeneity:** inst-000230 leaks at modest `bwd4/fwd4/sw8`; inst-001204/000816/001133/
  000366 need the *full* slow-comm gap (`sw1`+`fwd30`+`bwd4`). Each gadget's own schedule (when its
  address is ready, how deep it sits) sets how wide a gap it needs. All leak under full slow-comm; none
  at stock.

## Ruled out

- **check_ld false positive:** no — `reached_cache` (real packet), not delay_unit/spec-read/never-exec.
- **Model over-approximation (const/public addr):** no — XML `rf` shows xmit address fed by a speculative
  `TLoad` (231/231 `addr_from_load`); the constant *value* (rax=0, zeroed stack) is harness-only, the
  leak *shape* is real.
- **fnc-commit-stall hook:** no — leak is identical with the hook ON (150) and OFF (0) across all tested.
- **squashWidth artifact:** no — leaks at realistic `squashWidth=8`.
- **Concretization:** no — the asm faithfully realizes the load→load address dependence.
- The **BTB-force** hook only realizes the modeled misprediction (the test's premise); it is not the bug.

## The squash machinery — why `squashWidth` is irrelevant (and what it's for)

On a branch mispredict there are **three separate squash operations**, and only one is bounded by
`squashWidth`:

1. **IQ flush** — `InstructionQueue::doSquash` (`inst_queue_impl.hh`): `while (seqNum > squashedSeqNum)
   {...}` — a plain unbounded loop. **One-shot, one cycle. No `squashWidth`.**
2. **LSQ flush** — `LSQUnit::squash` (`lsq_unit_impl.hh`): `while (loads && seqNum > squashed_num)
   { setSquashed(); }` — also unbounded. **One-shot.** ← *this is what cancels the wrong-path load.*
3. **ROB unwind** — `ROB::doSquash` (`rob_impl.hh:381`): `for (numSquashed=0; numSquashed < squashWidth
   && ...; ++numSquashed) { setSquashed(); setCanCommit(); }` — **the only `squashWidth`-bounded loop.**
   It paces how fast already-squashed insts *drain out of the ROB* (slot/rename/phys-reg reclaim).

When IEW receives the commit squash signal (`commitToIEWDelay` cycles after commit broadcasts) it runs
`instQueue.squash()` **and** `ldstQueue.squash()` — both flush *every* younger-than-branch entry **in
that one cycle**. So the wrong-path load is `setSquashed()` and can no longer issue, gated purely by
`commitToIEWDelay`. The `squashWidth`-paced ROB unwind runs in parallel but is just bookkeeping;
it never keeps the load alive in the LSQ. **`squashWidth` is a recovery-throughput / performance knob
(rate of ROB unwind & resource reclaim), NOT a gate on speculative memory accesses** — which is why
this LSQ-cache-touch leak is insensitive to it. (It *would* matter for a transmitter gated on
commit/retirement-side lingering, which these load→load gadgets are not.)

## Real-world relevance / caveat

It does **not** manifest at gem5's default O3 timing (`commitToIEWDelay=1`, `squashWidth=8`) — verified
0/1200 in a bare stock-config sample. The race window is the latency from **"branch resolves → STT
un-taints the load"** to **"squash flushes the load from the LSQ."** In gem5 that window = `commitToIEWDelay`
(because the LSQ flush is one-shot once the signal arrives); the load's own un-taint→re-issue→access
path is ~2–3 cycles, so the leak appears at `commitToIEWDelay ≳ 3`. Window *depth* does not contribute
(tested to 300 extra wrong-path insts at stock → no leak), because the LSQ flush is not
`squashWidth`-bounded. **No zero-stretch PoC exists on this gem5 O3.** Minimal PoC = stock +
`commitToIEWDelay=3` (a single param; realistic `squashWidth=8`, fnc-hook off) → inst-047231 leaks.

**Is the window realistic on real silicon?** Two reasons to think gem5 *under*-states it, i.e. the bug
is plausibly realizable on a real STT core:

- **Redirect latency.** The window's gem5 proxy `commitToIEWDelay=1` is optimistic. A real OoO core has a
  multi-cycle distance from where a branch resolves to where the squash takes effect at the LSQ (the
  mispredict-redirect/recovery penalty) — commonly ≥2–3 cycles in deep pipelines. So `commitToIEWDelay`
  2–3 is arguably *more* faithful than gem5's default 1.
- **Bounded squash bandwidth (the user's point).** gem5's IQ/LSQ flush is **unbounded/one-shot** — an
  idealization. Real hardware cannot invalidate an arbitrary number of in-flight entries per cycle for
  free; squash/recovery bandwidth is finite. A faithful bounded-squash model would keep a **deep**
  wrong-path load alive for *extra* cycles after resolution — *widening* the window without any redirect
  stretching. So the deep-window idea is the right intuition for **real** hardware; it simply can't be
  shown in this gem5 because gem5 bounds only the ROB unwind (`squashWidth`), not the LSQ/IQ flush.
  (Caveat the other way: many real designs invalidate issuability by branch-tag in ~1 cycle even while
  resource reclaim is slow, so the dominant real-HW window is usually the redirect latency, not flush
  bandwidth — but either way it is **nonzero and multi-cycle**, not the 0–1 gem5 default implies.)

**Net:** the vulnerability is a genuine design-level race — STT clears taint at the visibility point
(`isPrevBrsResolved`) *without excluding instructions that are themselves about to be squashed*, so any
nonzero resolution→squash window lets a wrong-path tainted load touch the cache. A real STT
implementation shares that design property; whether it's *exploitable* depends on its concrete
resolution→squash window vs. the load's un-taint→access latency. gem5's defaults make that window
artificially small (fast redirect + free LSQ flush), so a clean gem5 demo needs `commitToIEWDelay≳3`;
on real silicon the window is plausibly already large enough. **To demonstrate the bounded-squash route
in-sim would require a bounded LSQ/IQ-squash model gem5 lacks (a gem5 change — out of scope).**

## Reproduce

```
# leak (commitToIEWDelay≥3, realistic squashWidth=8, fnc hook OFF):
SIMSPECT_SQUASH_WIDTH=8 SIMSPECT_COMMIT_IEW_DELAY=3 SIMSPECT_IEW_COMMIT_DELAY=1 \
SIMSPECT_BACK_COM_SIZE=10 SIMSPECT_FWD_COM_SIZE=10 \
/work/stt/build/X86/gem5.opt --debug-flags=LSQUnit,Commit \
  /work/stt/configs/example/se_exp.py --cmd=<inst-047231 binary> --cpu-type=DerivO3CPU --caches \
  --scheme=2 --branch-ann-file=<ann> --branch-ann-base=<base> --abs-max-tick=50000000
# → "successfully sent out packet(s) for inst [sn:<xmit>]" before that load's "squashed" line.
# stock (commitToIEWDelay=1): xmit never executes → no packet → no leak.
```

Diagnostic that buckets a hit as this bug: `diag_stt_vp_squash_race.py` (same dir).
