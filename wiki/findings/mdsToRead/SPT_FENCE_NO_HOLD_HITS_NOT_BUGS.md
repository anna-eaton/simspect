# Why the SPT-Fence `stt_no_hold` hits are NOT real bugs — deep analysis

**Run:** `results/experiments/spt_slowcomm_fence__20260602_121858/` (SPT_6_oneLP, gem5-spt
`--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy`,
slow-comm timing `se_slowcomm.py`).
**Subject:** the 64 ld hits the official race diagnostic (`diag_stt_vp_squash_race.py`) left as
`stt_no_hold` — i.e. the transmitter obtained its cache data *before* the controlling mispredict
resolved, and the Fence did **not** hold it. These are the cases I initially could not dismiss, and
that you (correctly) refused to let me hand-wave. This doc is the full argument, grounded in the gem5
traces, for why all 64 are harmless over-approximations rather than defense failures.

Companion data: `…/diagnostics/no_hold_resolution.json`, `…/diagnostics/race_<mode>.json`,
`…/diagnostics/stt_vp_squash_race.md`. Taint-model reference: memory `reference_spt_taint_model`.

---

## 0. TL;DR — it is neither a pipeline bug nor a gem5 bug; it is **model over-approximation**

"`no_hold`" is not an explanation — it is the diagnostic's *residual* verdict ("the Fence didn't hold
this and I can't attribute it to the race"). The real question is **why didn't the Fence hold the
transmitter**, and whether that points to (a) the model over-approximating, (b) a concretization/
pipeline bug, (c) a gem5 hook bug, or (d) a real gem5 bug. The answer for all 64 is **(a)**, and it is
provable from the model's own predicates (§1) plus the gem5 traces (§5):

- **The Fence didn't hold because the transmitter's address operand is genuinely untainted in gem5** —
  `fenceDelay = isAddrTainted()` and the address was not tainted at execute.
- **It is untainted because its producer is safe**, in one of two ways: the producer load sits *before*
  the unresolved branch (correct path → reaches its visibility point → untainted), or the producer is
  an "other"/ALU op whose input the model left **unspecified** (→ free-pool constant → no taint source).
- **The model flagged it anyway** because the model's protection policy (`hardware_protection_policy`,
  line 341) protects *any* rf-fed address operand of a *speculative* transmitter (`speculation_contract`,
  line 337 = "after an unresolved branch") — **without requiring the producer to itself be unsafe**.
  The real STT/SPT defense only taints/holds when the producer *is* unsafe. So model-says-protect vs
  gem5-correctly-doesn't-hold is the model being **deliberately conservative** — exactly the
  over-approximation that gem5 exists to filter — not an error in our pipeline or in gem5.

| subcat | n | producer of the xmit address | why gem5 (correctly) doesn't hold it |
|---|---|---|---|
| **A** | 40 | a load **before** the unresolved branch (retires, correct path) | reaches its visibility point → untainted; its value is architectural, exposed by the program anyway |
| **B** | 19 | a `TOtherx`/ALU op whose **input is unspecified** in the model → concretized to a prologue-zero free-pool reg | no taint source feeds it → output untainted; address is effectively a constant |
| **C** | 5 | dual-instance load PC; the **leaking** xmit consumed the **retired** (correct-path) instance | same as A, after picking the right dynamic instance |

**0 of the 64 have an address derived from a *squashed (wrong-path)* load** — that is the exact
signature that *would* make one a real defense failure, and it tested zero (§6).

This is categorically different from the 4,502 `stt_vp_squash_race` hits (§8), where the producer load
**is** under the unresolved branch (genuinely speculative), so gem5 *does* taint and hold the
transmitter — and only the VP↔squash *timing* race lets it slip. (Caveat: that race/no_hold split is
made on *timing* alone, not taint; see §8.)

---

## 0b. Root cause in the model's own predicates (`STAGE1_alloy/models/SPT_6_oneLP.als`)

The discrepancy is fully explained by three model definitions (read-only; not edited):

```
line 337  speculation_contract_p[p] = uncommitted_p[p] & has_unresolved_brs_p[p]
          has_unresolved_brs_p[p]   = (unresolved branches).(^spo)         // everything AFTER an unresolved branch
line 341  hardware_protection_policy = Instruction.operands
                                       - ((Inreg+Inaddr) - Instruction.outreg.rf)  // = all rf-FED input addr/regs (+outputs/mem)
line 343  leakage_function          = Loads.inaddr + Branchxs.inreg        // the transmitter operands
          secure iff  NO ( last_committed_protset ∩ speculative_xmit )     // leak iff the speculative xmit operand is in the protset
```

Decoded: the model calls an instruction **speculative** if it comes after *any* unresolved branch, and
it puts an operand in the **protection set** if it is an address/reg **fed by an `rf` edge** from some
prior instruction's output (then propagates that set forward along `rf`/`ddi`/`spo`). A test is a
flagged **leak** iff a speculative transmitter's address operand is in that protection set — i.e.
**"a speculative load whose address is produced by *any* earlier instruction."**

Crucially, the model does **not** require the *producer* of that address to itself be speculative or
unsafe. It is a deliberate GL-IFT-style over-approximation: protect anything data-flow-reachable, then
let gem5 (ground truth) decide which flagged tests actually leak. The real STT/SPT defense is narrower:
it taints a value only while its producing **load is still squashable** (has an older unresolved
branch) and clears the taint at the **visibility point**. So:

> **Model:** "address is rf-produced by a prior instruction" ⇒ protect ⇒ flag.
> **gem5/STT-SPT:** "address depends on a load that is *still unsafe* (under an unresolved branch)" ⇒
> taint ⇒ hold. Otherwise leave untainted.

The `no_hold` hits are precisely the gap between those two criteria: the producer is rf-connected
(so the model protects it) but **not** unsafe (so gem5 doesn't). Worked examples in §1/§5; the
contrast with the genuinely-unsafe producer (the race) in §8.

This is why "is it a pipeline or gem5 error?" is the wrong frame: the test is *correctly* generated
(it satisfies the model's leak predicate) and gem5 *correctly* shows it doesn't leak (the producer is
safe). Both halves are working as designed; the discrepancy is the model's intended conservatism.

---

## 1. The security property — what "real bug" means here

SpectreSafeFence + DDIFT is a *transient-execution* defense. Its contract: **the observable
microarchitectural footprint (here: L1 cache state) of a speculative instruction must not depend on
data that would not be exposed by the program's architectural (committed) execution.** Equivalently:
a transmitter may make a cache access only once its address operand is *safe* — meaning the value can
no longer be a transiently-loaded secret (a value read on a path that will be squashed, or read before
older branches that gate it are resolved).

Two consequences that matter for this analysis:

1. **A correct-path (committed/retiring) load's value is, by the defense's own contract, safe.** The
   architectural program executes that load and uses its value; exposing a function of it via the cache
   leaks nothing the attacker couldn't get by running the program. The defense only owes protection to
   *transient* data.
2. **A data-independent (constant) address leaks nothing.** If the transmitter's address does not
   depend on any loaded value at all, there is no information channel, full stop.

So "real bug" ⇔ *transmitter cache access whose address depends on data from a still-unsafe
(squashable / wrong-path) load*. Everything in §3 fails this test.

---

## 2. The defense mechanism in this build (so we know exactly what "held" means)

Verified by reading `/work/gem5-spt/src/cpu/o3/{rob_impl.hh,lsq_unit_impl.hh,base_dyn_inst_impl.hh}`
and by running gem5 with `--trackInstsFile` (see `reference_spt_taint_model`):

- **Taint source — `rob_impl.hh:240` (speculation-independent):** at ROB insertion,
  `if (inst->isAccess()) inst->setDestTaint(true)` — *"Access instructions always taint their
  destination, regardless of speculative or not."* So **every load taints its destination register.**
  (Shadow-L1 / memory-taint is **OFF** here — `Shadow L1 enabled? no` — so this ROB rule is the *only*
  taint origin. The litmus prologue's `movq $0,N(%rsp)` stores are irrelevant to taint.)
- **Untaint — at the visibility point:** a load's dest taint is cleared when the load becomes
  *unsquashable* (`isUnsquashable()` ⇔ all older branches resolved), via `untaintMemTransmit`
  (`lsq_unit_impl.hh` ~1193–1205). Plus the fwd/bwd untaint optimizations.
- **Fence gate — `lsq_unit_impl.hh:1180`:** `inst->fenceDelay(inst->isAddrTainted())`. A load is
  *held* (not allowed to access cache) iff one of its **address** source registers is tainted.
  `isAddrTainted` (`base_dyn_inst_impl.hh:525`) returns false once the inst is committed.

So the chain is: **producer load taints its dest → if that dest feeds a transmitter's address, the
transmitter `isAddrTainted` → Fence holds it → the hold lifts only when the *producer* reaches its VP
(its older branches resolve) and its dest-taint clears.**

The corollary that drives this whole analysis: **whether a transmitter is held depends on whether its
address-producer is still speculative (taint live) vs. already safe (taint cleared at VP).** A
correct-path producer reaches VP and clears taint quickly; a wrong-path producer keeps taint until the
mispredict resolves (→ the race, §5).

---

## 3. Why `check_ld` flags these at all (the over-approximation)

`check_ld` scores a hit when the transmitter's "Executing load"/cache-access tick lands inside the
speculative window. It does **not** model taint or data dependence. So any speculative load that
touches cache in-window is a "hit" — including one whose address is a constant or an architectural
value. The Alloy model likewise marks the operand "protected" purely by its *position* in the
speculative region, not by whether its concrete value is secret-derived. The `stt_no_hold` hits are
exactly the gap between those positional/window criteria and the *data-dependence* criterion that
actually defines a leak.

---

## 4. The discriminator, measured in gem5 (not from asm structure)

For each of the 64 I ran gem5 under the run's own config and traced, with seqNums and ticks:
the transmitter's **leaking dynamic instance** (the one that executed and obtained data ≤ the
mispredict-resolve tick), then the **source-load instance it actually consumed** (youngest source-load
seqNum older than the leaking xmit), and read **that instance's** fate (retired vs squashed). This is
ground truth from the pipeline trace — it does not rely on where the producer sits in the asm (which I
explicitly distrust; see §7). Scripts: `/tmp/verify_nohold.py` (→ A), `/tmp/verify_nohold2.py`
(→ B + the false-alarm), `/tmp/verify_nohold3.py` (→ C, corrected).

---

## 5. The three subcategories, with concrete traces

### Subcategory A — address from a load that RETIRES (correct path): 40 hits

**Example `inst-021701` (mispredict_not_taken).** Gadget:
```
pc0: movq %r9, %rax          ; %r9 = 0 (prologue) -> rax = 0   (dead: overwritten by pc1)
pc1: movq (%rsi), %rax       ; LOAD  -> rax = *(stack slot)    <-- address producer
pc2: movq (%rsi,%rax), %r8
pc3: movq $1,%rdx ; <branch> ; MISPREDICT (resolves @2,945,500)
pc4: movq (%rsi,%rax), %r8   ; XMIT (address = base + rax)
pc5: xorq %rdx,%rdx
```
Trace (slow-comm):
```
SRC LOAD pc1  sn553  inserted t2,929,000  executed t2,930,000   (retires; never squashed)
XMIT     pc4  sn562  inserted t2,929,500  executed t2,931,500  squashed t2,947,500
MISPREDICT resolve tick                                        t2,945,500
```
The address-producer is `pc1`, which is **older than the mispredict branch `pc3`** → it is on the
correct architectural path and **retires**. Its loaded value is exactly what the committed program
loads. The transmitter `pc4` is itself wrong-path (squashed @2,947,500) and made a speculative cache
access @2,931,500 using `rax` from the retired load. **Leaking a function of an architectural value is
not a transient-secret leak** (§1.1): the defense correctly leaves the producer untainted (it reaches
VP immediately, having no older unresolved branch), so the transmitter is correctly not fenced. Harmless.

> Note the over-approx clearly: the model put `pc4`'s address operand in the protection set because
> `pc4` is positionally speculative, but the *data* in `rax` is architectural.

### Subcategory B — address index is a PROLOGUE CONSTANT (no load on the path): 19 hits

**Example `inst-007654` (mispredict_taken).** Gadget:
```
pc0: movq (%rsi), %rax       ; LOAD (separate; NOT the model's address producer)
pc1: movq %r8, %rax          ; TOtherx, %r8=0 (prologue) -> rax=0   <-- model's rf producer of xmit addr
pc2: movq (%rsi,%rax), %r10
pc3: xorq %rdx,%rdx
pc4: <branch>                ; MISPREDICT (resolves @2,959,500)
pc5: movq (%rsi,%rax), %r12  ; XMIT (address = base + rax = base + 0)
```
Trace:
```
XMIT pc5 sn605  inserted t2,932,000  executed t2,956,500  squashed t2,961,500
MISPREDICT resolve tick                              t2,959,500
```
**This is faithful to the model, not a clobber bug.** The XML shows the model *intends* the xmit
address to be produced by an **`rf` edge from `pc1`** (`rf: Outreg$1→Inaddr$1`, where Outreg$1 belongs
to Instruction$4 = pc1), and `pc1`'s `kind` is **`TOtherx`** — an ALU/"other" op, here `movq %r8,%rax`.
Critically the model leaves `pc1`'s **input operand unspecified** (`inreg` is empty for it). So the
model's leak shape is *"an other-op (in the speculative region) produces the xmit address"*, with the
other-op's input unconstrained. (The separate `pc0` load is a different instruction the model never
connected to the xmit; it is not a clobbered intended-producer.)

At concretization that unspecified input is drawn from the **free pool** — a register the prologue
initialized to 0 (`xorl %eax,%eax; movq %rax,%r8`). So `pc1` computes a **constant**, the xmit address
is `base + 0`, and under DDIFT `pc1` is a non-load whose only source is untainted → its output is
untainted → the Fence has nothing to hold. A constant address carries **zero information**: no channel,
secret or otherwise.

Why the model still flags it: `pc1`'s output is `rf`-fed into the speculative xmit's address, so it is
in `hardware_protection_policy` (§0b) — the model protects it regardless of whether `pc1` has a real
(tainted) input. This is the **under-constrained "other"-operand** shape — the same family as the OTB
generation gap (`mdsToRead/OTB_GENERATION_GAP.md`): to make it a *real* leak the other-op's input would
have to be fed by a genuinely speculative load (the cross-chain merge that chain-interleaving is meant
to manufacture), which this base test does not do. Harmless as generated.

### Subcategory C — dual-instance producer; leaking xmit consumed the RETIRED instance: 5 hits

**Example `inst-040343` (mispredict_taken).** Gadget:
```
pc0: xorq %rdx,%rdx
pc1: movq (%rsi), %rax       ; LOAD  <-- address producer (BEFORE the mispredict)
pc2: movq (%rsi,%rax), %r10
pc3: xorq %rdx,%rdx ; <branch>; MISPREDICT (resolves @2,982,000)
pc4: movq (%rsi,%rax), %r15  ; XMIT
pc5: xorq %rdx,%rdx
```
Because the mispredict causes the gadget region to be fetched on both the wrong and the correct path,
each PC has **multiple dynamic instances**:
```
SRC LOAD pc1 : sn570 (squashed t2,947,500) | sn592 (executed t2,966,500, RETIRES) | sn724 (squashed t3,077,000)
XMIT    pc4 : sn579 (squashed, never executed) | sn601 (executed t2,968,000, squashed t2,984,000) | sn733 (never executed)
MISPREDICT resolve tick t2,982,000
```
The **leaking** transmitter is `sn601` (the one that actually executed, @2,968,000, before resolve).
The source-load instance it consumed is the youngest `pc1` instance older than it: **`sn592`, which
RETIRES** (correct path). So the leaked address is architectural → harmless, identical to subcategory A.

This is the case my first pass got wrong (§7): a heuristic that matched the *latest squashed* xmit
(`sn733`, which never executed) to a *squashed* source (`sn724`) false-flagged all 5 as candidate bugs.
Matching the actually-executing instance corrects it to harmless. All 5 (`inst-040343, 041681, 042209,
042221, 042242`) have the source load **before** the mispredict and the leaking xmit fed by a retired
source instance.

---

## 6. The falsification criterion — what WOULD make a `no_hold` a real bug, and that it's zero

A `stt_no_hold` hit *would* be a genuine (and in fact *stronger-than-the-race*) bug if:

> the **leaking** transmitter instance obtained its data **before** the mispredict resolved **and** its
> address was derived from a **squashed (wrong-path)** source-load instance.

That would mean the Fence let a transmitter expose a wrong-path speculative load's value to the cache
without ever holding it — a taint/fence failure independent of any timing race. `verify_nohold3.py`
checks exactly this predicate on the leaking instance. Result: **0 / 64.** Every leaking transmitter
consumed either a retired source load (A, C) or a constant (B). So the signature of a real bug is
absent from the entire set.

(If you want to keep this honest going forward: re-run the verifier on any future `no_hold` survivors;
a single `CANDIDATE_feeding_src_squashed` from the *executed* instance is the thing to escalate.)

---

## 7. Why I trust the method now (the instance-matching pitfall)

Across a mispredict, the **same static PC executes on both the wrong (squashed) and the correct
(retired) path**, so each load PC has several seqNum instances of differing fate. Any attribution that
keys on "is this PC ever squashed", on `max(seqNum)`, or on the producer's *position in the asm* will
mis-classify. The only correct anchor is the **dynamic instance that actually leaked** — the xmit
instance that executed and obtained data inside the window — and the source instance *it* consumed
(matched by seqNum). The v2→v3 correction in §5-C is a concrete instance of this; it flipped 5 "bugs"
to 0. (This mirrors the dataflow-analysis pitfalls already documented for OTB in
`mdsToRead/OTB_GENERATION_GAP.md`.) Recorded as memory `feedback_dataflow_leaking_instance`.

---

## 8. Contrast: why the 4,502 `stt_vp_squash_race` hits ARE the real signal (and these aren't)

| | `stt_no_hold` (these 64) | `stt_vp_squash_race` (4,502) |
|---|---|---|
| address-producer load | **correct-path (retires)** or constant | **wrong-path speculative** (under the mispredict) |
| was the producer's taint live when xmit ran? | no — cleared at VP / never tainted (constant) | yes — it was tainted; that's why the xmit was held |
| did the Fence hold the xmit? | **no** — correctly, address was safe | **yes** — then released at branch resolution |
| relation of data tick to resolve | **before** resolve | **at/after** resolve (released into the squash-drain gap) |
| address carries transient-secret-dependent data? | **no** | **yes** (mechanistically; concrete value is 0 only because the litmus zeroes memory) |
| verdict | harmless over-approximation | real Fence weakness — **but slow-comm-timing-only** (0/230 reproduce at stock `se.py`; see `stt_vp_squash_race.md`) |

So even the *real* signal here is a timing-parameter-dependent weakness (needs multi-cycle
commit→squash latency), not a stock-config Fence bug — and the `no_hold` set is a different, harmless
thing entirely.

---

## 9. Caveats / limits of this conclusion

- **Concrete values are all 0** (the litmus zeroes its frame), so this analysis is about the *defense
  mechanism* (does Fence protect the right loads), not about a value-level secret transfer. For the
  `no_hold` set that doesn't matter: subcat B has no data dependence at all, and subcats A/C depend only
  on correct-path (architecturally-exposed) loads — both are safe regardless of what value sits in the
  slot. (Contrast the race set, where the dependence is on a wrong-path load — there the zero value is
  incidental and a real attacker could place a secret.)
- This covers **ld** hits only. The ~154 `br_x` hits in this run go through the separate `check_br`
  track and are *not* addressed here.
- Scope is the SPT_6_oneLP testset under this exact Fence+DDIFT config and slow-comm timing. Re-derive
  for other testsets/builds; don't assume it carries over.
