# SpecLFB "jmp-shadow" bug — adversarial investigation (2026-11-08)

## The claim (what Anna asked me to break)

In the gem5 implementation of SpecLFB, `ROB::updateSafeState` walks the ROB oldest→youngest keeping a single rolling boolean `prevBrsResolved`. When it reaches an older **unresolved conditional branch** it sets `prevBrsResolved = false` (the load shadow is open). When it then reaches a younger **direct unconditional jump or call**, code derived from DOLMA *re-assigns* `prevBrsResolved = true` (direct-unconditional branches resolve at decode, so they are "not unresolved branches"). The claim is that this assignment **overwrites the `false` left by the older unresolved branch**, so every load after a direct `jmp`/`call` in a mispredicted branch's shadow is treated as "prior branches resolved", never gets `CUSL`, is never marked `isUnsafe`, and is free to fill L1D/L2 speculatively. SpecLFB's own rule (paper §6.2.2, p638) makes a load safe only "if there are no older control instructions that are unresolved".

## Verdict

**jmp-shadow is a REAL implementation bug in SpecLFB's gem5 port — a Spectre-v1 cache side channel, distinct from the UV6 bug AMuLeT published — and it is NOT present in the DOLMA code the logic was ported from. Confidence: very high.** It is reproduced from the source behavior (not our hooks) on a pristine, zero-SimSpect build, with a natural Spectre-v1 gadget and a natural misprediction, using gem5's own `Speclfb`/`Cache` debug prints as the oracle; it is relationally confirmed as a secret-dependent leak; and a one-line counterfactual fix removes it while leaving the rest of the defense intact.

It is best described as a **porting bug**: DOLMA tracks an unresolved branch with a *sticky* per-walk flag (`foundUnresolvedBranch`, set once and never cleared within the walk) and marks each direct-unconditional branch as simply "not a control inducer". SpecLFB's port collapsed that into a single rolling `prevBrsResolved` that a younger direct-unconditional branch **re-sets to true**, dropping the older branch's shadow. The intent of the DOLMA-derived code (don't *start* a shadow at a direct-unconditional branch) is correct; the realization (letting it *clear* an existing shadow) is wrong.

## How hard decisions should be framed (for Anna)

1. **Count jmp-shadow as a new, separately-reported SpecLFB vulnerability, or fold it into UV6?** They are different code paths and different shapes. Options: (a) report it as a new finding distinct from AMuLeT's UV6 — my recommendation, because UV6 is the first-load `isReallyUnsafe` optimization (paper §4.7, Fig 8a,c) and this is the `prevBrsResolved` control-walk logic, demonstrably independent (see §Direction 7); (b) treat it as "another instance of SpecLFB being insecure under CT-SEQ" and not a separate bug, since AMuLeT already declared the implementation insecure. I recommend (a) with an explicit note that AMuLeT's Fig 8(b) PoC happens to contain a `jmp` but was attributed solely to the first-load optimization.
2. **Whether to contact the SpecLFB / AMuLeT authors.** Out of scope for me to do (no external actions). If Anna wants to, the upstream is `smallcute123/SpecLFB` (no open issues) and `sith-lab/amulet-gem5` (speclfb branch); recommendation deferred to Anna.
3. **Paper framing.** If this goes in the ISCA paper, the one-line counterfactual and the variant matrix below are the figure-ready evidence. Recommendation: present jmp-shadow as a second, independent SpecLFB implementation flaw that SimSpect/this analysis surfaces beyond UV6.

## Provenance — is this logic upstream, in AMuLeT, and/or in DOLMA?

Public repos cloned read-only to cafe2 `gem5_dev:/work/amulet/upstream/` (`clone_*.log` rc=0):

- **(a) Original SpecLFB artifact** — `github.com/smallcute123/SpecLFB` (the repo named in the USENIX'24 paper's README; `SpecLFB-gem5/`). The logic is here verbatim: `SpecLFB-gem5/src/cpu/o3/rob.cc:484` (the DOLMA comment), `:493` (`prevBrsResolved = false` for unresolved control), `:497-501` (`hasCtrlInfo` + the simple-path `prevBrsResolved = inst->isDirectCtrl() && inst->isUncondCtrl();`), `:523`/`:528` (the mnemonic-fallback `prevBrsResolved = true` for a `*_I` CALL / JMP). No GitHub issues on the repo.
- **(b) AMuLeT's copy** — the live tree `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1` is the AMuLeT AE tarball (`/work/SpecLFB_AE-v1.1.tar.gz`, md5 `fb66fa9f…`) plus SimSpect's print-only hooks. I diffed the AE tarball's `src/cpu/o3/{rob,lsq_unit,lsq,dyn_inst}.cc/.hh` against upstream `smallcute123/SpecLFB`: the `updateSafeState` logic is **identical** (only an unrelated `debug/Squashed.hh` include and a squash-filter DPRINTF differ). `sith-lab/amulet-gem5` (speclfb branch, commit `f4ad7a0f "Port SpecLFB"`) carries the same logic. So the bug is in the original artifact and inherited unchanged by AMuLeT.
- **(c) DOLMA** — `github.com/efeslab/dolma`, `src/cpu/o3/rob_impl.hh`. The *same comment* and the *same mnemonic classifier* appear (`:299`, `:308-349`), but they compute a **per-instruction property** `isControlInducer` (direct-unconditional branches are simply *not* inducers; `:314` `isControlInducer = !(isDirectCtrl && isUncondCtrl)`). The shadow is then tracked in `updateSafeStatus` by a **sticky** local `foundUnresolvedBranch` that is set at `:445` (`if (inst->isControlInducer()) foundUnresolvedBranch = true;`) and **never cleared inside the walk**; a load's restriction is cleared only `if (... && !foundUnresolvedBranch)` (`:405-406`). A younger direct-unconditional branch has `isControlInducer()==false`, so it cannot set — and certainly cannot clear — `foundUnresolvedBranch`. **DOLMA is correct; SpecLFB's single rolling `prevBrsResolved` is the mis-port.**

## Exact mechanism

- **Which path runs for `JMP_I` / `CALL_NEAR_I`:** the **`hasCtrlInfo` simple path** (`rob.cc:499-501`), not the mnemonic fallback. The generated X86 decoder sets the flags the fallback was written to compensate for: in `build/X86/arch/x86/generated/decoder-ns.{cc,hh}.inc`, `JMP_I`'s terminal `Wrip` microop is allocated with `IsDirectControl` and its body sets `flags[IsUncondControl]=flags[IsControl]` (no `IsCondControl`/`IsIndirectControl`); `CALL_NEAR_I` adds `IsCall`+`IsUncondControl` via `.function_call` and `IsDirectControl` via `.control_direct` (`src/arch/x86/isa/macroop.isa:230-239`, `isa/insts/.../jump.py`, `call.py`). So for both, `isDirectCtrl()!=isIndirectCtrl()` and `isUncondCtrl()!=isCondCtrl()` are true → `hasCtrlInfo==true` → `prevBrsResolved = isDirectCtrl && isUncondCtrl = true`. The DOLMA comment's "gem5 bug where direct/conditional info isn't provided for X86" is stale for this gem5 version; the mnemonic fallback is dead code for these ops here. (The counterfactual, which patched both paths, confirms the simple path is the live one, since neutralizing it removes the effect.)
- **It is an overwrite of an older branch's shadow, and it needs the jmp between the branch and the load in program order.** Confirmed by the variant matrix: a jmp placed **before** the bounds branch (older) or **after** the transmitter (younger) does not unprotect (S7, S8).
- **The LSQ-side code does not compensate.** `LSQUnit::updateSafeState` (`lsq_unit.cc:826`) only *consumes* `isPrevBrsResolved()`: `if (inst->isPrevBrsResolved()) clearCUSL(); else setCUSL();`. Once the ROB walk left `prevBrsResolved=true` at a load, the LSQ walk clears its `CUSL`, and `isUnsafe()` (`dyn_inst.hh:641` `!isSquashed() && ((isCUSL()||ismUSL()) && isreallyUnsafe())`) is false, so `lsq.cc:1009-1027` tags the request as safe and it proceeds to the cache. No second check re-derives the branch shadow.
- **The jmp's own state does not matter** (it resolves at decode); **it must be direct and unconditional** — indirect jmp (`JMP_R`, S6), a conditional branch (S5), and a return (`ret`, S9; excluded by `if(!inst->isReturn())`) all leave the shadow intact.

## Direction-by-direction results

| # | Direction | Result |
|---|---|---|
| 1 | Provenance (SpecLFB / AMuLeT / DOLMA) | Identical in upstream SpecLFB + AMuLeT copy; **absent** in DOLMA (DOLMA uses a sticky inducer flag). Porting bug. Cited above. |
| 2 | Exact mechanism | `hasCtrlInfo` simple path runs; overwrite of older-branch shadow; LSQ side does not compensate; needs jmp between branch and load; triggered by direct jmp/call (near+far), not indirect/cond/ret. |
| 3 | Rule out our machinery | Reproduced on a **pristine zero-hooks build** with **no branch-ann, no resolve-stall**, natural mispredict, native prints. Not our hooks, force, stall, or harness. (nop-length control S2 rules out the `jmp ftbypass0` epilogue shape.) |
| 4 | Real observable leak | **Yes, relational.** Squashed speculative transmitter installs the secret-dependent line (secret 2/4/7 → paddr d5000/d7000/da000) in L2+L1D **only** with the jmp; without it the line is touched only by the committed reload. |
| 5 | Counterfactual | One-line fix (don't let direct-unconditional branches re-set `prevBrsResolved`) → **every** variant protected, leak gone, UV6 path untouched. |
| 6 | Scope / impact | Direct jmp/call are ubiquitous (every if/else join, every call). Any load after the first such in a mispredicted shadow loses protection. Defense substantially weakened for ordinary compiled code. |
| 7 | Already known? | **No.** AMuLeT's UV6 (paper §4.7, Fig 8) is the first-load `isReallyUnsafe` optimization — a different path. No GitHub issues. Not in the SpecLFB paper. |
| 8 | Alt explanations | All ruled out (see §Alternatives). |

### Direction 3/4/5 — the evidence (pristine, zero hooks; native oracle)

Gadget: `src/gadget.S` + `src/driver.c` (natural Spectre-v1; a cold `sizep` line keeps the bounds branch unresolved for a full memory round-trip; a **sacrificial first speculative load** + 24 nops put the transmitter neither first in the LQ nor in the `PrevNoUnsafe` lag window, so UV6/walk-order cannot explain any hit). Build/run: `src/build.sh`, `src/run.sh`. SHADOW variants 0–10 defined in `gadget.S`. All on cafe2 `gem5_dev:/work/amulet/jmpshadow_probe/` (`LOG.md`, `runs/{pristine,live_v2hooks,cf}/`).

Transmitter `isCUSL/isUnsafe` over the 12–13 speculative instances per run (**pristine build, identical on live**):

| SHADOW | shadow instruction | transmitter CUSL/Unsafe | protected? |
|---|---|---|---|
| 0 | none | 1/1 (12) | yes (baseline) |
| 1 | direct `jmp` → next | **0/0 (11), 0/1 (2)** | **NO** |
| 2 | 2-byte `nop` (same length as 1) | 1/1 (12) | yes (length/layout control) |
| 3 | direct `call`+`ret` | **0/0 (12)** | **NO** |
| 4 | direct `call`, no ret (rsp+=8) | **0/0 (12)** | **NO** |
| 5 | younger conditional branch | 1/1 (12) | yes |
| 6 | indirect `jmp *%r11` | 1/1 (12) | yes |
| 7 | direct `jmp` **before** the bounds branch | 1/1 (12) | yes (must be in shadow) |
| 8 | direct `jmp` **after** the transmitter | 1/1 (12) | yes (must precede the load) |
| 9 | `ret` (push+ret) | 1/1 (10) + noise | yes (returns excluded) |
| 10 | direct far `jmp` (`E9 rel32`) | **0/0 (11), 0/1 (2)** | **NO** |

Relational leak (native `Cache` flag, `what caused <pc>`), pristine S1 vs S0, secret=2, transmitter line paddr `0xd5000`:

```
S1 (jmp):    35449500 dcache access ReadReq [d5000] miss   (what caused 401e74 = transmitter)
             35510000 l2   fill  [d5000]  (what caused 401e74)   <-- squashed spec transmitter installs secret line
             35520500 dcache fill [d5000] (what caused 401e74)
S0 (no jmp): 35739500 dcache access ReadReq [d5000] miss   (what caused 401813 = committed reload)
             35800000 l2 fill / 35810500 dcache fill        (what caused 401813)   <-- only the architectural reload
```

Secret-dependence (live binary; squashed-transmitter fills; `0xd3000` = probe[0] is the committed, non-secret training access present in both arms):

| secret | expected line d3000+s·0x1000 | S1 (jmp) squashed-transmitter fill | S0 (no jmp) |
|---|---|---|---|
| 2 | d5000 | **d5000 (seq 42674)** | none |
| 4 | d7000 | **d7000 (seq 43665)** | none |
| 7 | da000 | **da000 (seq 43665)** | none |

Squash: the fill completes just after the squash of the **`jae` bounds branch** (live simspect trace `ROB:squash seq=42641 pc=0x401e4b @35508000`), i.e. the request was already issued on the wrong path (translate @35449500) and lands despite the squash — the canonical speculative-cache leak.

Counterfactual (`cf/`, scratch copy of pristine; `rob.cc:508/530/535` patched so a direct-unconditional branch leaves `prevBrsResolved` unchanged; build rc=0): every variant 0–10 reverts to `CUSL/Unsafe=1/1` (protected), and the secret line in cf-S1 is filled only by the committed reload (`what caused 401813`), not the transmitter — the jmp-shadow leak disappears. The diff touches only the control-instruction block; the `isReallyUnsafe`/`PrevNoUnsafe` first-load path (UV6) is byte-identical, so UV6 is preserved by construction. (A separate natural-UV6 demo on cf was not run because the existing UV6 demos use `--branch-ann-file`, which the pristine/cf se.py does not support; the surgical diff guarantees UV6 is unchanged.)

### Alternatives explicitly ruled out (Direction 8)

- **Wrong-path / committed:** the leaking load (seq 42674) is younger than the mispredicted `jae` (seq 42641) and is squashed; it never retires.
- **Prefetch / writeback:** `prefetcher=Null` on dcache and L2 (`config.ini`); the fill is a demand `ReadReq`/`ReadSharedReq`/`ReadResp` attributed to the transmitter PC.
- **Fill after the branch resolves:** the request is issued at translate time (35449500) before the squash (35508000); SpecLFB's protection is supposed to *prevent the issue*, which is exactly what fails here.
- **Different-branch squash:** the only squash in the window is the bounds `jae`.
- **Timing/shadow-shape artifact of the jmp:** the 2-byte-nop control (S2), same length and same shadow shape, stays protected — the difference is the jmp's *semantics*, not the extra bytes or a shifted window.
- **ROB/LQ size, older committed instruction:** identical cache/CPU config across all variants; the fill is caused by the transmitter load, not an older committed instruction.

## What is still open

- I did not run a dedicated natural-**UV6** gadget on the `cf` build (the canned UV6 demos need `--branch-ann-file`, unsupported there). The code diff is surgical, so UV6 is preserved by construction, but a positive cf-UV6 demo would be a nice belt-and-suspenders.
- I did not separately rebuild to prove the mnemonic-fallback path is *never* taken for `JMP_I` (the generated decoder shows `hasCtrlInfo==true`, and the counterfactual patched both paths). A one-off DPRINTF build could confirm, but the decoder source is definitive.
- Whether the SonicBOOM RTL version of SpecLFB has the same flaw is untested (this is the gem5 port only; the paper's `br_mask` description §6.2.2 suggests the RTL tracks per-branch masks and may be correct).

## Files (this folder; the one new md + small sources)

- `README.md` — this review.
- `src/gadget.S`, `src/driver.c` — natural Spectre-v1 jmp-shadow gadget (11 SHADOW variants) + driver (rdtsc probe; the gem5 oracle is the debug trace, not rdtsc).
- `src/build.sh`, `src/run.sh` — scratch build + variant-matrix runner (no SimSpect flags).

## cafe2 artifacts (durable scratch, `gem5_dev:/work/amulet/jmpshadow_probe/`)

- `LOG.md` — run log (start/end, commands, results summary).
- `pristine/` — fresh build of the AMuLeT AE SpecLFB tarball, **zero** SimSpect hooks (`build_pristine.log` rc=0).
- `cf/` — counterfactual build (pristine + the 3-line `rob.cc` fix; `rob.cc.orig` kept; `build_cf.log` rc=0). **Diagnostic build only — never for campaign results.**
- `runs/pristine/`, `runs/live_v2hooks/`, `runs/cf/` — s0–s10 traces (secret=2); `runs/sec4_s*`, `runs/sec7_s*` on live.
- `/work/amulet/upstream/{SpecLFB,dolma,amulet-gem5,pristine_amulet_tarball}` — read-only clones + extracted tarball used for the provenance diff.
- The `pristine/` and `cf/` build trees are ~2 GB each; safe to delete after review.
