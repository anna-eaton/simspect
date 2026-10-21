# Hit: inst-047231 (STT_6 / mispredict_not_taken / ld) — slow-comm experiment

**Status:** VERIFIED real in-window speculative *cache access* (not a check_ld false positive).
**Open question:** real STT leak vs. model over-approximation — see "Why untainted?" below.
First hit found by the slow_comm_squash1 experiment (/work/stt, scheme=2 STT, se_slowcomm.py:
iewToCommitDelay=30, commitToIEWDelay=4, backComSize=forwardComSize=40, squashWidth=1).

## The flip (baseline vs slow-comm, same check_ld)

| | baseline `se.py` (default O3 timing) | slow-comm `se_slowcomm.py` |
|---|---|---|
| xmit `Executing load` tick (`xmit_signal`) | **0 — never executed** | **2,946,500** |
| sent packet to cache? | no | **yes** ("successfully sent out packet(s)") |
| window `(lc_retire, fnc_retire)` | (2,899,000, 3,025,500) | (2,907,000, 3,037,500) |
| `issued_in_window` | **No** | **Yes** |

At default timing the speculative xmit load is squashed before it ever executes. Under slow-comm
(squashWidth=1 drains the squash one inst/cycle + forward delay 30 delays commit's knowledge), the
load reaches a real cache access *inside* the speculative window before the squash catches it. This
is exactly the timing-fragility the experiment was built to surface.

## The gadget (speculative path after the prologue zeroes all of `%rsp`)

```
pc0 (last_committed):     leaq (%r9,%r15), %rcx        ; r9=r15=0
pc1 (first_noncommitted): movq %r8,%rax; imulq %r10,%rax ; =0
pc2:                      movq $1,%rsi; testq %rsi,%rsi; jne   ; branch_pc2 MISPREDICT_not_taken
                                                                ; (BTB forced fall-through 0x401c58,
                                                                ;  rsi=1 so actually TAKEN → the
                                                                ;  fall-through path below is squashed)
  bb_3 (squashed spec path):
    leaq 48(%rsp),%rdi
pc3:  movq (%rdi),%rax                                  ; PRODUCER load: rax = [48(%rsp)] = 0
pc4:  xorq %rsi,%rsi; testq %rsi,%rsi; jne               ; branch_pc4 correctly_not_taken
  bb_5:
    leaq 64(%rsp),%rdi
pc5 (XMIT):  movq (%rdi,%rax),%r15                       ; addr = 64(%rsp)+rax  → LOAD into r15
```

`xmit.addr = 0x401c68`, depends on `rax` = result of speculative producer load `pc3`. Classic
load→load address dependence.

## gem5 evidence (LSQUnit trace, se_slowcomm.py, scheme=2, abs-max-tick=5e7)

```
2930000  Inserting load PC (0x401c68...) idx:1 [sn:571]
2946500  Executing load PC (0x401c68...) [sn:571]
2946500  Doing memory access (normal load) for inst [sn:571] PC (0x401c68...)
2946500  successfully sent out packet(s) for inst [sn:571]      ← real cache touch
2947500  Load Instruction PC (0x401c68...) squashed, [sn:571]   ← squashed ~2 cyc later
```

- Executes 32 cyc *after* insertion (2930000→2946500) — it genuinely waits on `rax` from `pc3`,
  confirming the address really is producer-load-dependent at the uarch level.
- **No `tainted` / `delay_unit` / `STL_CHECK` lines anywhere in the trace** — STT never bounced *any*
  load in this test. The xmit is scored "normal load," i.e. STT considered its address **untainted**.
- Not the recon-style check_ld false positive (that path is "Inserted tainted load into delay_unit",
  no packet). Here a packet was successfully sent → genuine cache access.

## Why it leaks — and why squash timing does NOT disqualify it

The XML refutes any "over-approximation" reading. The Alloy instance
(`testsets/STT_6/xml/inst-047231.xml`) has the xmit (Instruction$0, isxm, TLoad) read its address
operand `Inaddr$0`=`Reg_s$0`, and `rf: Outreg$2 → Inaddr$0` shows that register is produced by
**Instruction$2, a `TLoad`** sitting *after* the only unresolved branch (Instruction$3 / idx 2). So
the xmit address is a value produced by a **speculative load** — a genuine load→load leak shape STT
must protect. STT has **no STLF-untaint** (that's SPT); taint is defined by the model and only
cleared at the visibility point. So the producer load's result should be tainted and the xmit held.
An xml-shape pass over the whole sample agrees: **231/231 hits are `addr_from_load`** (0 over-approx).

STT nonetheless ran the xmit as a **normal** load and it sent a real cache packet (`reached_cache`
per `diag_ld_cache_reach.py`). **This is a real leak.** The constant *value* (rax=0, zeroed stack)
does not matter — in a real attack the same gadget transmits a real secret; the litmus harness just
doesn't inject one.

**Squash timing is NOT an eliminating factor (per user, 2026-06-02).** The mispredict branch
(0x401c51) broadcasts its Commit squash at tick 2,945,500, and the xmit sends its cache packet at
2,946,500 — i.e. ~2 cyc *after* the redirect is computed but before the LSQ squash (2,947,500)
actually kills the load. A mis-speculated tainted load that **touched the cache and was then
squashed** is exactly the leak: the redirect being broadcast slightly earlier does not undo the
observable cache-state change. So the branch-resolution / squash tick is recorded as *informative*
only; it does **not** gate the verdict.

## Verdict

**Real leak.** A model-protected (`addr_from_load`) speculative tainted load that STT allowed to make
a real, in-window cache access (then squashed). A candidate **real STT discrepancy**, not an
over-approximation and not a check_ld false positive (cache-reach = `reached_cache`).

## ROOT CAUSE (confirmed) — visibility-point taint-clear races the squash drain

STT *did* hold the load correctly while speculative; it **released** it at the visibility point the
instant the branch resolved, and the wrong-path load then hit the cache before the squash removed it.

**Smoking gun (IQ trace, sn:571):** the xmit had all 3 operands ready and was first issued at
**2,931,500** (so `rax`/the address was never the bottleneck), then **held in the LSQ ~29 cycles**
with no cache access, then **re-issued at 2,946,000** → cache packet 2,946,500 → squashed 2,947,500.
The release coincides with the mispredict branch `0x401c51` resolving at **2,945,500**.

**Mechanism (from /work/stt source):**
- `rob_impl.hh:compute_taint()` (812–814) roots a load's taint in `isAccess() && !isUnsquashable()`.
- `updateVisibleState()` (519–520) sets `isUnsquashable ⟺ isPrevBrsResolved()` (all older branches
  resolved); a branch keeps `prevBrsResolved=true` for younger insts while it is
  `readyToCommit() && !isSquashed()` (489–495).
- While `0x401c51` is unresolved → producer load squashable → `isDestTainted=true` → xmit
  `address_flow` sees a tainted producer → xmit `isArgsTainted/isAddrTainted` → `readyToExpose=false`
  → held. ✓
- The instant `0x401c51` resolves → `isPrevBrsResolved` propagates to the younger **wrong-path**
  insts → producer becomes `isUnsquashable` → dest-taint drops → xmit address untainted →
  `readyToExpose=true` → re-issued → cache access.
- The wrong-path load is *supposed* to be squashed at that resolution, but the squash is not
  instantaneous. In the resolution→squash gap the freshly-untainted wrong-path load touches the cache.

**The gap:** `isPrevBrsResolved` = "safe to expose" for *correct-path* insts, but for a *wrong-path*
inst it means "about to be squashed." STT's taint-clear doesn't account for the inst being on the
to-be-squashed path; its security implicitly assumes squash completes atomically with the
visibility-point update. The leak appears once the **resolution→squash gap ≥ ~2–3 cycles.**

**Driver (rigorously isolated — see diagnostics/stt_vp_squash_race.md):** the gap is set by the
**commit→IEW squash-propagation latency `commitToIEWDelay`**, NOT by `squashWidth`. Stock gem5
(`commitToIEWDelay=1`, `squashWidth=8`) → 1-cycle gap → **NO leak** (the xmit is squashed before it
re-issues; bare stock sample = 0/1200). It leaks at `commitToIEWDelay≥3` (or ≥2 with `iewToCommitDelay≥2`)
and **still leaks at realistic `squashWidth=8`**; `squashWidth=1` alone (stock comm) does not leak, and
forward-delay alone does not. The `fnc-commit-stall` hook is ruled out (leak identical with it on/off).
**Window depth does NOT contribute** — inserting up to 300 extra wrong-path insts after the xmit does
not leak at stock (the IQ squashes all younger-than-branch insts in one shot, not drained at
`squashWidth`/cycle), so there is **no zero-stretch PoC**; the *only* lever is `commitToIEWDelay`.
Minimal PoC = stock + `commitToIEWDelay=3` (realistic `squashWidth=8`). Real-world exploitability hinges
solely on whether a real design's commit→issue redirect latency is ≥2–3 cycles (gem5 defaults it to 1).
