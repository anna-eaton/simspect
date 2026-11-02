# Protection-set re-evaluation (A1): do the Alloy `hardware_protection_policy` definitions match the source papers?

**Status:** Research writeup. PROPOSAL/ANALYSIS only — no `.als` edited (owner-gated). This is the standalone "A1" protection-set concern from [`../../state/ALLOY_MODEL_CHANGES.md`](../../state/ALLOY_MODEL_CHANGES.md) §A1, grounded against the three source papers read this session.
**Date:** 2026-10-30
**Models audited:** `STAGE1_alloy/models/STT_6.als`, `SPT_6_oneLP.als`, `Recon_6.als`.
**Papers read (local, cited by section):** STT = Yu et al., *Speculative Taint Tracking (STT)*, MICRO '52 2019 (`~/Documents/quail/sources/papers/yu-2019-stt.pdf`); SPT = Choudhary, Yu, Fletcher, Morrison, *Speculative Privacy Tracking (SPT)*, MICRO '21 (`.../choudhary-2021-spt.pdf`); ReCon = Aimoniotis, Kvalsvik, Chen, Själander, Kaxiras, *ReCon: Efficient Detection, Management, and Use of Non-Speculative Information Leakage*, MICRO '23 (`.../aimoniotis-2023-recon.pdf`).

---

## TL;DR — the claim

The A1 over-approximation (const-address loads, SPT-Fence `no_hold`) is a property of the **SPT model's operand-based `hardware_protection_policy` ONLY** (`SPT_6_oneLP.als:341`, and `SPT_6.als`). That seed protects *essentially all operands* — including a register written by a speculative ALU op that reads only constants — which no paper supports.

**STT_6.als and Recon_6.als do NOT share that policy.** Both seed the protection set from `Mem_s` (all memory *states*) and let the forward closure carry taint only to operands that are data-flow-reachable from a memory read (`STT_6.als:326`, `Recon_6.als:316-318`). A constant/const-ALU output has no memory in its cone, so it is *never* reached — these two models are already essentially source-derived and do **not** exhibit the const-addr false positive.

This is a **correction to the rerun matrix in `ALLOY_MODEL_CHANGES.md`**, which marks STT_6 and Recon_6 as needing the A1 "shared policy" fix (`✅ (shared policy)`). They do not share SPT's over-approximating operand policy; the A1 seed fix is an **SPT-model fix**. STT_6/Recon_6 need at most a *verification pass*, not a seed rewrite.

The A1 proposed fix (sources = `Loads.outreg` + read memory, forward closure, OR/union semantics) **is faithful to the taint SOURCE and PROPAGATION of both STT and SPT**. Where STT and SPT differ is purely in UNTAINT (STT untaints at the visibility point; SPT does not — it untaints only via declassification). So the fix must be applied per-defense, not as one uniform rule (details per model below).

---

## Background — how a defense is encoded (grounded in the models + `CLAUDE.md`)

A defense is three clauses in each model's "Specific defense model" block: a **speculation contract** (which instructions are speculative), a **protection set** (`hardware_protection_policy` seed + `prot_set_propagation_p` forward propagation, assembled by `last_committed_protset_p`/`a[]`), and a **leakage function** (which operands are transmitters). A test is a flagged leak iff a *speculative transmitter operand* lands in the *protection set* or its forward closure over `op_edges = rf + ddi` (`secure_speculation_scheme_p`).

Base-model facts that matter here (`STT_6.als:79-114`): only memory operands carry `Mem_s` state (`Inmem`/`Outmem`; facts `im_s`/`om_s`), and register operands carry `Reg_s` (`ir_s`/`ia_s`/`or_s`). A load reads `inmem` (Mem_s) and writes `outreg` (Reg_s); a load's *address* is `inaddr` (Reg_s). `rf` flows producer `outs` → consumer `ins`; `ddi` is the intra-instruction def-use edge. This is why a `Mem_s`-seeded protection set can only reach a register operand through a load (there is no other bridge from `Mem_s` into `Reg_s`).

---

## STT — `STT_6.als`

**Paper definition (Yu 2019, §6.1 "Framework & Concepts"):** "The microarchitecture classifies instructions capable of reading secrets under speculative execution as *access instructions*. We focus on the case where access instructions are loads... **STT taints the output of any speculative access instruction.**" Propagation is DIFT-style forward through def-use chains. Untaint: "an instruction has reached the visibility point if all older control-flow instructions have resolved... **STT untaints the output of an access instruction once it becomes safe**" (§6.1, "When can data be untainted?"). So: source = speculative (squashable) **load outputs**; propagate forward; untaint at the visibility point (older branches resolved).

**Current model (`STT_6.als`):**
- Seed: `hardware_protection_policy: State {Mem_s}` (`:326`) — all memory states.
- Propagation/untaint: `prot_set_propagation_p[p,i,s] = s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate` (`:329-332`) — a load with **no unresolved branch before it (or being one)** removes its read-memory state from the set. That is exactly the visibility-point untaint: a *safe* (correct-path / resolved) load drops its taint.
- Leak test: `secure_speculation_scheme_p` (`:262-265`) protects a speculative transmitter operand (`leakage_function = Loads.inaddr + Branchxs.inreg`, `:328`) iff its state is a protected `Mem_s` state **or it is forward-reachable (`^op_edges`) from one**.

**Gap:** essentially none on the A1 axis. Because the seed is `Mem_s` and only memory operands carry `Mem_s`, a register operand (e.g. a load's `inaddr`) enters the set only via the forward closure from a *protected memory operand* — i.e. its address must be data-flow-fed by an earlier load whose read-memory is still protected (a speculative load). A const-ALU-produced address (`Reg_s`, no memory in its cone) is unreachable → **never flagged**. The VP-untaint (`:331`) matches STT's visibility point. This is a faithful rendering of STT.

**Recommendation:** **No A1 seed change.** STT_6's `Mem_s` seed + safe-load untaint already behaves as "taint speculative load outputs, propagate forward, untaint at VP." Keep the VP-untaint (it is STT-correct and must NOT be removed). Correct the `ALLOY_MODEL_CHANGES.md` matrix: STT_6 does not need the A1 seed rewrite. (A2 `rf`-last-writer and the B-series coverage items are separate and still apply.)

---

## SPT — `SPT_6_oneLP.als`

**Paper definition (Choudhary 2021):** SPT's *base* taint is identical to STT's — "**STT s-taints the output register of a speculative access instruction**... the output register of a non-access instruction is s-tainted **if and only if it has an s-tainted input register**" (§2.2.1 "STT Details"). The gem5 SPT build implements exactly this: "Access instructions always taint their destination, regardless of speculative or not" (SPT-Fence ROB rule, quoted in [`SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md`](SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md) §2, `rob_impl.hh:240`). What SPT *adds* over STT is a more aggressive **untaint** (declassification): "the output is untainted iff the OR of the input taint bits is 0" extended by GLIFT prior-knowledge and declassification events (§5 "Implications of Declassification"), and a *broader protection scope* — SPT also protects **non-speculative secrets** (constant-time code), so it does **not** untaint a load output merely for being safe/at-VP (§3-§4, "our protection scope is broader than STT's"). Source = **all load outputs**, OR-propagated forward; untaint = declassification only (never "it's safe/committed").

**Current model (`SPT_6_oneLP.als`):**
- Seed: `hardware_protection_policy: Operand {Instruction.operands - ((Inreg + Inaddr) - Instruction.outreg.rf)}` (`:341`) — **all operands** except input reg/addr operands with *no* `rf` producer. This includes every `Outreg` (const-ALU outputs included), every `Inmem`/`Outmem`, and any `rf`-fed `Inreg`/`Inaddr`.
- Propagation: `prot_set_propagation_p` (`:345-361`) is a stack of *subtraction* (untaint) clauses — STLF-from-untainted-store, untaint an Other-op's `outreg` when it has no `inreg` / when no input is in the set, de-protect an input whose rf-source left the set, etc. This is the model's attempt at SPT's declassification algebra, layered on top of the over-broad seed.
- Leak test: `one_insecure_speculation_scheme_p` (`:268-272`) / `tag_xm` (`:278-284`) — a speculative transmitter operand in the (propagated) set.

**Gap — this is the real A1 bug.** The seed protects "**any value produced under speculation**," not "any value data-flow-derived from a load." A speculative ALU op reading only constants has its `outreg` in the seed, so a load whose address is fed by that `outreg` is flagged — but its address is a constant and leaks nothing (documented as ~99.9% of SPT `ld` hits in [`POTENTIAL_MODEL_FIX_constaddr_taint.md`](POTENTIAL_MODEL_FIX_constaddr_taint.md) §1, and the 64 SPT-Fence `no_hold` cases in [`SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md`](SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md) §0b). No paper supports an all-operands seed: both STT (§6.1) and SPT (§2.2.1) seed from **load outputs only**. The downstream subtraction clauses (`:345-361`) are a fragile patch trying to claw back the over-approximation after the fact.

**Recommendation (the A1 fix, SPT form):**
1. **Restrict the seed** to load-derived values: sources = `Loads.outreg` (every load's output — not gated on commit/speculation, per the ROB rule) **+** read memory (`Loads.inmem` / the protected memory).
2. **Forward closure, union (OR) semantics** over `ddi + rf`: an operand is protected iff ≥1 input is protected (this matches SPT §2.2.1's "iff it has an s-tainted input register"). The existing `last_committed_protset_p`/`a[]` closure (`:222-236`) is kept; only its seed changes.
3. **Keep SPT's declassification untaint** (STLF-from-untainted-store, GLIFT prior-knowledge). Do **NOT** add a VP/"safe/committed" untaint — that would be STT, not SPT; SPT's scope is deliberately broader (constant-time-code protection, §3).
4. Consequence to validate: const / const-ALU-address outputs fall out automatically (no load in their cone); **load→load address chains stay protected** (a load output is always a source — genuine signal, do not untaint). The `oneLP` STLF-subtraction hack (`:357`) likely becomes redundant.

This is exactly the fix sketched in `ALLOY_MODEL_CHANGES.md` §A1 and `POTENTIAL_MODEL_FIX_constaddr_taint.md` §2 — and it is paper-faithful: it reproduces STT/SPT's source + OR-propagation while leaving SPT's broader untaint intact.

---

## ReCon — `Recon_6.als`

**Paper definition (Aimoniotis 2023):** ReCon is a *performance optimization layered on top of* a secure-speculation scheme (STT or NDA); it "**removes protection from values that are already public information**" (§3). The specific public-information source it exploits is **non-speculative pointer dereferencing by load pairs**: "If two loads execute non-speculatively, where the second load dereferences the value of the first load, then... RECON reveals the value of the first load as public" (§1; the reveal is committed at the second load's commit, §4). A revealed address can then be dereferenced speculatively without protection; a store to it re-"conceals" it. So ReCon = (STT's protection set) **minus** addresses already revealed by a committed non-speculative load-pair dereference.

**Current model (`Recon_6.als`):**
- Seed: `hardware_protection_policy[p]: State {Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads - speculation_contract_p[p]))}` (`:316-318`) — `Mem_s` (the STT base), **minus** memory states that flow (via `op_edges`, backward) into the **addresses of non-speculative loads** (`Loads - speculation_contract_p[p]` = loads outside the speculative region). That is precisely ReCon's "reveal": a non-speculatively dereferenced pointer value is removed from the protected set.
- Propagation/untaint: `prot_set_propagation_p` (`:321-324`) is the **same VP-untaint as STT_6** (safe loads remove their read-memory). So Recon_6 = STT_6 base + the reveal subtraction in the seed.

**Gap:** no A1 over-approximation — it inherits STT_6's `Mem_s`-based (source-derived) policy, so const-ALU addresses are never flagged here either. The one thing to **verify** (not obviously wrong, but worth an owner check) is that the "reveal" set matches the paper on two points: (a) ReCon reveals only on a **committed** (fully non-speculative) load-pair dereference — confirm `Loads - speculation_contract_p[p]` is the intended "non-speculative load" notion (speculation_contract = `uncommitted & has_unresolved_brs`, so its complement includes committed *and* resolved-branch loads; the paper keys on commit, §4 ②); and (b) the **conceal-on-store** behavior (a store to a revealed address re-protects it, §1) — I did not find a conceal clause in the model; check whether the testset scope makes it a no-op or whether it is a genuine coverage gap.

**Recommendation:** **No A1 seed change** (it is already STT-base-derived). Treat as a *verification* item: confirm the reveal predicate's "non-speculative load" matches ReCon's commit-time reveal, and decide whether conceal-on-store needs modeling. Correct the `ALLOY_MODEL_CHANGES.md` matrix entry for Recon ("policy shared? verify") → it is **not** SPT's operand policy; it is STT's `Mem_s` policy plus a reveal subtraction.

---

## Summary table

| model | seed (`hardware_protection_policy`) | paper source | A1 over-approx? | A1 action |
|---|---|---|---|---|
| **STT_6** | `Mem_s` (all memory states), `:326` | speculative load outputs, fwd-closure, untaint@VP (Yu §6.1) | **No** — const-ALU unreachable from `Mem_s` | none; keep VP-untaint; fix matrix |
| **SPT_6_oneLP** | all operands − un-fed inreg/inaddr, `:341` | load outputs, OR-fwd, declassify-untaint (Choudhary §2.2.1, §5) | **Yes** — protects const-ALU outputs | restrict seed to `Loads.outreg` + read mem; keep declassify untaint; no VP-untaint |
| **Recon_6** | `Mem_s` − non-spec load-pair revealed addrs, `:316-318` | STT base − already-public (reveal/conceal) (Aimoniotis §1, §3-4) | **No** — STT-base-derived | none; verify reveal=commit-time + conceal-on-store |

---

## Open questions for Anna

1. **Matrix correction — do you agree?** The paper reading says A1's seed rewrite is an **SPT-only** fix; STT_6 and Recon_6 use a `Mem_s`-based (already source-derived) policy and do not emit const-addr FPs. `ALLOY_MODEL_CHANGES.md`'s rerun matrix marks all three as A1 (`✅ shared policy`). Should I update that matrix (owner-gated doc) to scope A1 to SPT, or is there an STT/Recon run that *did* show const-addr FPs that I should look at first before narrowing it?
2. **SPT untaint, not VP.** The A1 proposed-fix text in both source docs says "load outputs stay tainted, do NOT untaint them; untaint only via STLF/declassification." That is SPT-correct (SPT protects non-speculative secrets). But it would be *wrong* for STT (STT must untaint at VP). Confirm the A1 fix is understood as **SPT-specific**, and that STT_6's existing VP-untaint (`:331`) stays.
3. **Does the SPT seed want `Loads.outreg` or the cleaner `Mem_s` form?** SPT could be fixed either by restricting its operand seed to `Loads.outreg + Loads.inmem`, or by switching it to the `Mem_s`-state style STT_6/Recon_6 already use (plus SPT's declassification untaint instead of VP-untaint). The latter would make all three models share one policy shape and is arguably cleaner — but it is a bigger structural edit. Which do you want?
4. **ReCon conceal-on-store.** I did not find a conceal clause (store to a revealed address → re-protect) in `Recon_6.als`. Is that out of scope for the current testset, or a coverage gap to log under §B?
5. **ReCon reveal = commit vs resolved.** `Recon_6.als:317` reveals via `Loads - speculation_contract_p[p]`; the paper reveals at the second load's **commit** (§4 ②). The complement of `speculation_contract` (`uncommitted & has_unresolved_brs`) includes resolved-but-uncommitted loads. Is that the intended "non-speculative" boundary, or should it key strictly on `committed`?
