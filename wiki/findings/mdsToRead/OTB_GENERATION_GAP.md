# OTB (`getOldestTaint`) gadget is absent from STT_6 / interleave — it's an ENUMERATION-CAP artifact (the model CAN generate it)

> **Caveat on the corpus numbers below (2026-06-02):** the `rf_shape.py` scan ran on
> `testsets/STT_6_interleave/xml`, which is **STALE** — generated before the `all s: State |
> secure[RS->s]` clause was effective (40% isolated no-op ops; see claudelog "TESTSETS ARE STALE").
> The OTB conclusion is unchanged and was **re-confirmed on fresh current-model output**
> (`other→xmit.inaddr` rf edge = 0/2000 fresh; forcing `otb_shape` = SAT, that test used the current
> model). So "absent in the default enumeration, legal when forced" holds; only the corpus counts
> (66,512/100k) are from the stale testset.


**TL;DR.** The recon **OTB / `getOldestTaint`** bug (reconresults.md Bug 1) is **not present in any
generated STT_6 / STT_6_interleave test**, but **the model CAN generate the precursor shape** — it's a
**`max_instances` enumeration-cap + ordering artifact**, NOT a model-expressivity or minimality limit.

- Empirically: over all 100k base instances, every `ld` transmitter's address is fed by an `rf` edge
  **directly from a single load** (66,512/66,512); **0** route the address through an `other`/ALU op.
- But forcing the shape with a predicate is **immediately SAT**: add
  `pred otb_shape { some x: Loads | (x in xm) and (some o: (Otherns+Otherxs) | some (o.outreg & rf.(x.inaddr))) }`
  to the `run` and Alloy returns `ld → other → xm` instances at once (see `/tmp/otb_test.als`,
  `/tmp/otb_test_out/`). So the `gen_lit` enumeration simply **fills the 100,000-instance cap with the
  simpler direct-`load→xmit` and `branchx` shapes before it ever reaches an `other`-on-path instance.**

Don't re-derive this; if asked "does interleave hit OTB," the answer is: not in the current testset, but
it's a cap/ordering issue, fixable with a forcing predicate (below) — **not** a model gap.

---

## What OTB needs (the target gadget)

From reconresults.md Bug 1: `getOldestTaint` keeps only the **oldest** taint feeding an ALU op. The gadget:

```
br_r                      resolved branch (resolves EARLY)
  ld_inj   <-- injected by interleave, lives under br_r  (speculative for a while, then resolves)
br_u                      unresolved (mispredicting) branch — stays speculative
  ld_base                speculative load under br_u
  other  = f(ld_base, ld_inj)   2-input ALU; ONE operand free/open -> ld_inj hooks here
  xm     = load (other)         transmitter; address = other's result
```

When `br_r` resolves, `ld_inj` (the *oldest* taint) is freed by `getOldestTaint`, even though `ld_base`
(under the still-unresolved `br_u`) is speculative → `other`'s result is treated untainted → `xm` issues.
**Only `ld_inj` comes from interleave**; the base Alloy must emit `br_r … br_u ld_base other xm` where
`other` feeds the transmitter address and carries a fillable second operand.

## Why it's absent today (and why that's NOT a model limitation)

1. **The shape is legal and satisfiable.** `gen_useful_litmus` minimizes only via `RR` (resolve a branch)
   and `RS` (remove a state) — **NOT `RI`/`RO`**, so extra instructions and *unspecified operands are not
   pruned*. An `other` on the path is fine, and its 2nd operand is legitimately left **unspecified**
   (not needed for the base leak) — which is exactly what `pass3`/interleave fills. Verified: forcing
   `otb_shape` → SAT. A representative instance (`/tmp/otb_test_out/inst-000002.xml`):
   `IX0 br(committed) · IX1 ld(committed) · IX2 br(UNresolved) · IX3 ld(spec) · IX4 TOtherx(rf-fed by a
   load, 1 inreg) · IX5 ld XMIT (inaddr ← IX4.outreg)`. The `other` has **1 rf-bound inreg**; its 2nd
   operand is a concretization/interleave fill — the hook point.
2. **It just isn't in the first 100,000 instances.** `pipeline.py` runs `a6CountModels <model> <out>
   <max_instances>` which enumerates the FIRST `run` command's solutions up to `alloy.max_instances`
   (config; 100000 for STT_6) with symmetry breaking on. The simpler direct-`load→xmit` / `branchx`
   instances come first and **exhaust the cap before any `other`-on-path instance is reached** → 0 in the
   testset.

## How to actually get OTB tests (model/config addition — needs owner approval)

Generate a **dedicated OTB-shaped testset** with a forcing predicate so the enumeration spends its budget
on the gadget shape instead of the common direct shape:

- Copy the model, add `otb_shape` (above) as a conjunct of the `run` command, enumerate (that's all
  `/tmp/otb_test.als` does — it's SAT and produces instances immediately).
- Run it through `llvm`/`asm` with **`interleave.enabled: true`** so `pass_interleave` injects the second
  load that hooks the `other`'s open operand, placed under an earlier-resolving branch (`br_r`), giving the
  two-loads-of-differing-speculation-status merge OTB needs.
- This is an `.als`/config change → **owner sign-off** (CLAUDE.md "DO NOT mess with the alloy models
  lightly"). For a one-off sanity check without generating a testset, run the hand-crafted
  `oldest_taint_bug/debug_out/inst-oldest-taint-bug.s` on `/work/gem5-recon-modded`.

Open sub-question (worth checking when building the testset): whether `pass_interleave` reliably places the
injected `ld_inj` **under an earlier-resolving branch than the base load** (so it's the "oldest" taint and
resolves first). The merge collision is necessary but the *differential resolution* is what triggers
`getOldestTaint`.

Note: `leakage_function` (model line 315) has `Otherxs.inreg` commented out, so there are also **no
`other_x` transmitters** in any STT_6 testset (only `ld` + `br_x`) — unrelated to OTB but good to know.

---

## Analysis pitfalls that produced WRONG intermediate answers (so this doesn't happen again)

This took several wrong turns. If you analyze SimSpect dataflow, avoid these:

0. **Don't assume minimality prunes instructions/operands.** `gen_useful_litmus` uses only `RR` and `RS`
   (resolve branch / remove state). It does **not** remove instructions (`RI`) or operands (`RO`). So
   "extra" ops and unspecified operands are allowed — they are NOT a reason a shape can't be generated.
   (I wrongly claimed minimality forbade the free combiner operand; it does not.)
1. **Base XML is *pre*-interleave.** `testsets/<model>/xml/inst-N.xml` is the shared Alloy instance; the
   interleaved chains exist only in the `_v<k>` **asm/ann**. Scanning base XML for an interleave-created
   merge always finds nothing — look at the variant asm, or reason about `pass3`.
2. **Shared opstate ≠ rf edge.** Multiple instructions can write the *same* abstract state atom; the **rf**
   relation is the real dataflow, and at concretization the **last writer in program order** wins. Use
   `rf`, not shared `opstate`, to decide what feeds an operand.
3. **Alloy atom labels carry a `$N` suffix** (`TLoad$0`, `IX0$0`). Compare on `value.split("$")[0]`.
   (A missed strip silently bucketed all 100k as `branchx`.)
4. **`idx` is program order and is *reversed* from instruction-atom numbering** (`IX0` = first in spo =
   `Instruction$5`). Order by `idx`, never by atom number.
5. **x86 asm dataflow parsing:** split operands at **top-level commas only** (the SIB operand
   `(%rsi,%rax)` contains a comma — naive `split(",")` truncates it to `(%rsi`, tracing only the base and
   missing the load-derived index); and **`lea` is NOT a load** (`leaq 64(%rsp),%rsi` computes an address,
   doesn't dereference — treat as ALU). For `movq (base,index),dst` the speculative value is the **index**.
6. **To answer "can the model generate shape X," force it with a predicate and run Alloy** — don't infer
   "impossible" from "absent in the capped enumeration." Recipe: copy the `.als`, add `pred X {...}` as a
   conjunct of the FIRST `run` (a6CountModels uses `getAllCommands().get(0)`), run
   `java -cp alloy6.jar:. a6CountModels /tmp/copy.als /tmp/out 3`. SAT ⇒ the shape is legal and the
   absence is a cap/ordering artifact.

Authoritative artifacts: `/tmp/rf_shape.py` (rf-true, all 100k base XML → 0 other-on-path) and
`/tmp/otb_test.als` + `/tmp/otb_test_out/` (forcing predicate → SAT, proves it's a cap artifact).
