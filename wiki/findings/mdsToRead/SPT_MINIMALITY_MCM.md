# Minimality for SPT vs. the MCM critical-cycle tradition — cycle-vs-path, a crisp definition, and the SPT relax/not-relax decision

> **STATUS: PROPOSAL / ANALYSIS ONLY.** No `.als` model, no `parsexml.py`, no driver was edited —
> everything below is from **reading** the canonical models and the papers. Every model/predicate
> change proposed here is **owner-gated** (root `CLAUDE.md` → Alloy models STRICT): show Anna the diff
> and wait. MCM claims are grounded in sources **read this session** (local PDFs + web); repo claims
> cite `file:line`.
>
> **For:** Anna — *"Think about minimality for SPT and what we relax vs. not. The inspirational MCM
> work is all based on CYCLES, so it's clearer what 'minimal' means. We might need to be a bit
> different in our minimality definition."*
> **Date:** 2026-10-26
> **Cross-refs:** [`../../state/ALLOY_MODEL_CHANGES.md`](../../state/ALLOY_MODEL_CHANGES.md) (B2 joint-minimality, B3 instr-minimality),
> [`ENUMERATION_OVERSPECIFICATION.md`](ENUMERATION_OVERSPECIFICATION.md) (per-branch minimality forbids multi-source),
> [`REACH_UNSAT_ENUMERATION.md`](REACH_UNSAT_ENUMERATION.md) (exhaust the core/skeleton quotient to UNSAT),
> [`OTB_GENERATION_GAP.md`](OTB_GENERATION_GAP.md) (the getOldestTaint target shape),
> [`POTENTIAL_MODEL_FIX_constaddr_taint.md`](POTENTIAL_MODEL_FIX_constaddr_taint.md) + [`SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md`](SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md) (SPT taint scope),
> `MINIMALITY_TAGALONG_FIX.md` (companion agent — the irredundant-set predicate; **not yet written** as of this date).

---

## TL;DR — the three headline answers

1. **Cycle or path? → A SimSpect speculative leak is a PATH, not a cycle.** The MCM critical-cycle
   notion is cycle-based *because an MCM's consistency condition is literally an acyclicity axiom* — a
   violation **is** a cycle (Herding Cats: "our model is defined in terms of irreflexivity and
   acyclicity checks… looking for patterns corresponds here to looking for cycles"). SimSpect's security
   condition is **not** acyclicity; it is **reachability on an acyclic dataflow DAG**: `secure` ⟺ *no
   protected operand reaches a speculative transmitter via `op_edges`* (`STT_6.als:262-265`). A leak is
   the **existence of a forward path** protected-source →(`rf`∪`ddi`)\*→ speculative-transmitter, gated
   by an unresolved branch. The operand graph is a DAG by construction (`unidirectional_rf`,
   `STT_6.als:158`) — there is **no back-edge, no cycle**. So the cycle notion does **not** transfer
   syntactically. The correct analogue of "critical cycle" is a **minimal/irreducible leak witness**
   (a minimal insecure sub-instance), not a cycle. (A genuine *cycle* appears only if you drop to the
   µhb execution-ordering level — CheckMate — which SimSpect deliberately does not model; §3.)

2. **Crisp minimality → "minimal leak witness," defined RELATIVE TO A LEAK-CORE, in two tiers.**
   Tier-1 (mechanism): enumerate distinct **leak-cores** (the transmitter's backward `op_edges`-cone +
   its speculation structure); the two-source OTB merge is a *distinct core* from a single-source leak.
   Tier-2 (no padding, within a core): no instruction / operand / state removable without securing it
   (`RI`/`RO`/`RS`-necessity), genuinely speculative (`RC`-necessity), and **every gating branch is
   irredundant** — each gates a real core-source, none is a tag-along. The operative change is to
   **replace per-branch *individual* necessity** (`all b: secure[RR→b]`, `STT_6.als:306`) with
   **per-branch *irredundancy*** (each branch *influences* security in some resolution context). §4.
   *The key insight behind "we need to be different":* unlike an MCM cycle, a SimSpect leak **can be
   shortened across a mechanism boundary** (dropping one source of an OTB merge still leaks, as a
   *different, single-source* mechanism). So absolute "smallest insecure sub-instance" minimality
   **destroys the OTB mechanism we want to test.** Minimality must therefore be **mechanism-relative**
   (core-relative) — which MCM gets for free from cycle structure and we must impose explicitly.

3. **SPT relax/not-relax → relax branches, keep states; and do it *after* the taint fix.**
   - **RELAX (branches, `RR`):** per-branch individual-necessity → core-relative irredundancy. SPT needs
     this **more** than STT: SPT taint *persists* along the whole dataflow (a load output stays tainted;
     it is **not** declassified at the visibility point the way STT declassifies —
     `POTENTIAL_MODEL_FIX_constaddr_taint.md:48-56`), so SPT's leak paths are longer/deeper and
     **multi-source union-merges keep taint from every live source** — the getOldestTaint/OTB class is
     squarely an SPT-family mechanism (recon is SPT-lineage). Per-branch necessity structurally forbids
     exactly this class (`ENUMERATION_OVERSPECIFICATION.md:33-44`, 103-109).
   - **KEEP (states `RS`, boundary `RC`, single-transmitter form):** states keep **individual**
     necessity — a redundant architectural location is *padding*, not a mechanism (branches compose into
     AND/OR speculation gadgets; locations do not). Keep `RC` (transient-only). Keep
     `one_insecure_speculation_scheme_p` (`SPT_6_oneLP.als:268`) = one witness ↔ one leaking transmitter
     (the clean "one critical cycle ↔ one test" analogue). **Add** `RI`/`RO` core-minimality (SPT
     over-generates padding too).
   - **Order matters:** apply the **A1 source-derived-taint fix first** (`ALLOY_MODEL_CHANGES.md` §A1).
     On the current over-approximating SPT protset (`hardware_protection_policy = Instruction.operands`,
     `SPT_6.als:329`), the minimality predicate is partly guarding against *noise* (const-addr FPs), not
     mechanism; an irredundancy relaxation layered on a broken protset would admit noisy multi-branch
     shapes. §5.

---

## 1. The MCM minimality notion — what "critical cycle" means and why it is canonical

### 1.1 Why MCM witnesses are *cycles*: the property is acyclicity
Axiomatic MCMs define consistency as **irreflexivity/acyclicity axioms** over a composite relation.
Herding Cats states this directly (Alglave, Maranget & Tautschnig, *Herding Cats*, TOPLAS 36(2) 2014,
§9.1.2, local `quail/sources/papers/alglave2014-herding-cats.pdf` p.63):

> *"our model is defined in terms of irreflexivity and acyclicity checks. Thus looking for patterns
> corresponds here to looking for cycles of relations."*

Because the forbidden property **is** `acyclic(R)`, a violating execution **is** a cycle in `R`. The
*minimal* violation is the smallest such cycle; a shorter cycle (a chord) would be a strictly smaller
witness, so minimality = **no chord / irreducible cycle**.

### 1.2 The critical cycle (Shasha–Snir 1988), as recalled verbatim by Herding Cats
Shasha & Snir, *Efficient and correct execution of parallel programs that share memory*, TOPLAS
10(2):282-312, 1988, introduced **critical cycles** for the delay-set problem. (The original is a
scanned-image PDF, not machine-readable; I quote Herding Cats' verbatim recall, §9.1.2.)

Two events are **competing** (`cmp`) if "they are from distinct processors, to the same location, and at
least one of them is a write." A cycle σ ⊆ (`cmp` ∪ `po`) is **critical** when:

> *"(i) per thread, there are at most two memory accesses involved in the cycle on this thread and these
> accesses have distinct locations, and (ii) for a given memory location ℓ, there are at most three
> accesses relative to ℓ, and these accesses are from distinct threads."*

and — the intuition that matters for us —

> *"a critical cycle violates SC in a minimal way."*

A critical cycle **alternates** program order (`po`) with competing accesses (`cmp`), "traverse[s] a
thread only once," and touches each location ≤3 times. These conditions make the notion **finite,
canonical, and enumerable**: the generator (`diy`/`mole`) enumerates *all* static critical cycles of a
program (Herding Cats §9.1.2).

### 1.3 `diy`: a cycle **is** a test; each edge **is** a relaxation
In the `diy`/`litmus` toolchain (Alglave & Maranget; `diy.inria.fr`), test generation is cycle-first:
diy "builds cycles from the candidate relaxations… then generates litmus tests from these cycles."
A cycle is **a sequence of labeled edges**, each edge a **candidate relaxation** — `Rfe`/`Coe`/`Fre`
(communication, internal/external), `Po` (program order, same/different location, R/W directions),
dependency edges (`DpAddr`/`DpData`/`DpCtrl`), and fence edges. Under SC the cycle's edges form a cycle
of ordering constraints (so the outcome is forbidden); the test asks whether hardware **breaks** one of
those edges. **Minimality is relative to the target alphabet:** removing a target edge yields a
*different* test of a *different* relaxation, **not** a simpler version of the same test. (Remember this
for §4 — it is exactly why SimSpect minimality must be mechanism-relative.)

### 1.4 The *other* MCM tradition — Alloy-based **semantic** minimality (the one SimSpect is actually in)
When MCM litmus generation moves into **Alloy** (not hand-enumerated cycles), minimality is stated
**semantically**, not as "no chord":
- **Wickerson, Batty, Sorensen & Constantinides, *Automatically Comparing Memory Consistency Models*,
  POPL 2017** (`memalloy`; PDF read this session). The checked property is still acyclicity
  (e.g. `acyclic((hb ∩ sloc) ∪ rf ∪ co ∪ fr)`, Fig. lines), but **litmus-test minimality** is a
  separate *program-level* predicate — **Definition 15 (Obtaining minimal litmus tests):** a test is
  minimal for execution X when "P behaves like X, **all of its instructions are executed** and all of
  its CAS's succeed… X is a **maximal execution** of P." I.e. *no dead/padding instruction* — every
  instruction participates. memalloy also reports finding distinguishing tests "**in a simpler form**"
  (5 instructions where prior hand-construction used 7).
- The companion ASPLOS-line suites ("Automated Synthesis of Comprehensive Memory Model Litmus Test
  Suites") push minimality to the synchronization axis: a suite where **"no synchronization mechanism in
  the test can be weakened without causing new behaviors to become observable"** (web summary; full text
  not obtained — *marked unverified*).

**Takeaway for Anna's framing.** The "MCM = cycles, crisp minimality" picture is the **diy/Shasha–Snir**
branch, and it is crisp *only because consistency is acyclicity*. The moment MCM work adopts Alloy over
a property that isn't a single acyclicity axiom, it switches to **semantic minimality** — "every
instruction participates" (memalloy Def 15) and "nothing can be weakened without new behavior" (the
exact shape of SimSpect's `secure[RR→i]` / `secure[RS→s]` clauses). **SimSpect is already in the
correct tradition.** It is *not* that we abandoned a clean cycle notion; it is that our property is a
reachability property, for which the cycle notion was never the right tool — and the Alloy-MCM
tradition agrees. What we must *fix* is which semantic-necessity predicate we use (§4), not reach for
cycles.

---

## 2. SimSpect's relation vocabulary (from the canonical `.als`, read-only)

All line refs: `STAGE1_alloy/models/STT_6.als`, `SPT_6.als`, `SPT_6_oneLP.als`.

| relation / predicate | definition (file:line) | role |
|---|---|---|
| `spo` | `Instruction→Instruction`; acyclic, total, ≤1 predecessor (`STT_6.als:129-131`) | **speculative program order** (the only instruction-level order; a chain, not a cycle) |
| `opstate` | `Operand→one State` (`STT_6.als:80`) | maps an operand to its **architectural location** (register/memory); "same location" = same `opstate` |
| `rf` | `Operand→Operand`, `outs→ins`, ≤1 writer per reader, **same `opstate`**, **most-recent writer** (`STT_6.als:156-169`) | inter-instruction **reads-from** dataflow |
| `ddi` | `Operand→Operand`, intra-instruction `ins→outs` (`STT_6.als:155,171-174`) | intra-instruction **data dependence** (GL-IFT-style: `ld` `Inmem→Outreg`, `str` `Inreg→Outmem`, `other` `Inreg→Outreg`) |
| `op_edges` | `rf ∪ ddi` (`STT_6.als:223`) | **the dataflow graph** over operands — *the graph the leak lives in* |
| `committed`/`resolved`/`uncommitted`/`unresolved` | `STT_6.als:66-67,135-136`; committed ⊆ resolved, committed is an `spo`-prefix (`:134,137`) | instruction speculation state |
| `has_unresolved_brs_p` | instrs after any unresolved branch: `(unresolved & branch).^spo` (`STT_6.als:245-247`) | the **speculative region** |
| `speculation_contract_p` | `uncommitted & has_unresolved_brs` (`STT_6.als:325`) | instructions whose transmits are **speculative** |
| `leakage_function` | `Loads.inaddr + Branchxs.inreg` (`STT_6.als:328`); SPT_6_oneLP adds `Stores.inaddr` (`:344`) | **transmitter operands** (what leaks: a load/store address, a branch condition) |
| `speculative_xmit_p` | `leakage_function ∩ speculation_contract.operands` (`STT_6.als:229`) | transmitter operands that are **speculative** |
| `hardware_protection_policy` | STT: `Mem_s` (`STT_6.als:326`). SPT: `Instruction.operands` (`SPT_6.als:329`). SPT_oneLP: all ops minus un-fed `Inreg`/`Inaddr` (`SPT_6_oneLP.als:341`) | the **secret seed** (protection set initial value) |
| `prot_set_propagation_p` | STT declassifies a load's `inmem` once it has **no unresolved branch before it** (`STT_6.als:331`); SPT does **not** (keeps load outputs tainted; union forward-closure; STLF-untaint at `SPT_6_oneLP.als:357`) | **taint transfer function** (forward, monotone) |
| `last_committed_protset_p` | `prot_set_propagation` folded along `spo` (6 nested `a[…]`, `STT_6.als:232-243`) | **final protection set** at the transmitter = a forward taint **fixpoint** |
| `secure_speculation_scheme_p` | `no (protset.~opstate ∩ spec_xmit)` **and** `no (protset.~opstate.^op_edges ∩ spec_xmit)` (`STT_6.als:262-265`; SPT `:255-266`) | **the security property** (see §3) |

Two structural facts to carry forward:
- **The dataflow graph is a DAG.** `unidirectional_rf {acyclic[(operands).rf.(~operands) + spo]}`
  (`STT_6.als:158`) forces `rf` to respect `spo`; `ddi` is intra-instruction (strictly `ins→outs`). So
  `op_edges` lifted to instructions is acyclic — **there is no cycle anywhere in the witness graph.**
- **The protection set is a forward taint fixpoint**, computed by sweeping `prot_set_propagation`
  forward along `spo` (`STT_6.als:232-243`). It is a standard monotone forward dataflow analysis — it
  introduces no cyclic structure into the witness.

---

## 3. The crux — is a speculative leak a CYCLE or a PATH?

### 3.1 The security property is reachability, not acyclicity
Expand `secure_speculation_scheme_p` (`STT_6.als:262-265`):

```
secure  ⟺  no (protset.~opstate            ∩ speculative_xmit)      -- (a) transmitter's own location is protected
      and  no (protset.~opstate.(^op_edges) ∩ speculative_xmit)      -- (b) transmitter reachable from a protected operand
```

Clause **(b)** is a transitive-closure **reachability** test over `op_edges`. Therefore:

> **A leak = `¬secure` = there EXISTS a forward path**
> `protected-source →(rf ∪ ddi)\*→ speculative-transmitter-operand`,
> with the transmitter in `speculation_contract` (gated by an unresolved branch).

This is a **source→sink reachability witness on a DAG** — a **PATH**. It is not, and cannot be, a cycle:
the whole graph is acyclic (`STT_6.als:158`), the protection set is a forward fixpoint, and the security
axiom is "no reachability," not "acyclic(R)."

### 3.2 Why the MCM cycle notion does **not** transfer syntactically
| | MCM (diy/Shasha–Snir) | SimSpect |
|---|---|---|
| safety property | `acyclic(R)` over `po ∪ com` | `no path` secret →`op_edges`\*→ speculative transmitter |
| a violation is… | a **cycle** in `R` | a **path** in a DAG |
| minimal witness | **critical cycle** (no chord; per-thread ≤2, per-loc ≤3) | **minimal leak witness** (irreducible insecure sub-instance) |
| why that shape | the axiom *is* acyclicity | the axiom *is* reachability on a DAG |

Forcing a cycle onto SimSpect would be artificial. The only candidate back-edge — the attacker's
*probe/reload* observing the cache state the transmitter set — **is not modeled**: SimSpect models the
**victim's speculative dataflow only**, never the receiver. There is nothing to close a cycle with.

### 3.3 The honest nuance: a cycle *does* exist — at a different abstraction level (CheckMate)
At the **microarchitectural-happens-before (µhb)** level, a speculative-execution exploit genuinely **is**
a cycle. Trippel, Lustig & Martonosi, *CheckMate* (MICRO 2018; local
`quail/sources/papers/trippel-2018-checkmate.pdf`) builds on the Check/MCM µhb machinery:

> *"cyclic µhb graphs represent impossible executions… a cycle in a µhb graph represents a scenario in
> which a physical event happens before itself… acyclic µhb graphs represent observable executions."*
> Exploit patterns "are µhb sub-graphs"; a security litmus test contains "the **minimal number of
> micro-ops necessary to produce the exploit pattern**."

So the cycle-vs-path split is a **choice of abstraction**, and SimSpect's choice is deliberate and
correct for its purpose:
- **CheckMate / µhb:** object = *ordering* of microarchitectural events (transmit-before-squash,
  observe-after). The property is acyclicity of happens-before → **witness = cycle**.
- **SimSpect / IFT-taint:** object = *information flow* through operands (STT/SPT are IFT defenses). The
  property is non-reachability of a transmitter from a secret → **witness = path**.

SimSpect works at the IFT level **because the defenses it tests are IFT defenses** — it asks "does a
protected value *flow to* a transmitter," which is inherently a dataflow path, not an event-ordering
cycle. **Verdict: PATH.** Pursue cycle-minimality only if the project ever re-bases onto a µhb/CheckMate
event model (a different modeling decision, not a tweak).

---

## 4. A crisp minimality for SimSpect — the **Minimal Leak Witness**, defined mechanism-relative

### 4.1 The obstruction that forces us to "be different" (the OTB non-minimality theorem)
Try the obvious transfer — "minimal = smallest insecure sub-instance" (no single contraction leaves it
insecure). **It destroys the OTB mechanism.** Consider the getOldestTaint/OTB target
(`OTB_GENERATION_GAP.md:31-46`): two tainted loads under two branches merge in an ALU op feeding the
transmitter. Because the model's taint is a **union/OR** closure (a merge is tainted if *either* source
is), you can **drop one source and still leak via the other** — a strictly smaller, *single-source*
insecure sub-instance. So:

> **Theorem (informal).** A multi-source (OTB) leak is **never** minimal under absolute "cannot-shrink-
> while-insecure" minimality: there is always a smaller single-source leak inside it.

Hence absolute irreducibility **collapses every OTB gadget to a single-source leak** — erasing the very
getOldestTaint mechanism we built the testset to exercise. This is the precise, formal sense of Anna's
"we need to be a bit different." MCM does **not** hit this because a critical cycle's minimality is
*already* relative to its target relaxation alphabet (§1.3): a chord that drops a target edge gives a
*different* test, so you never "shrink across a mechanism boundary." We must make that mechanism-
relativity **explicit**, because our witnesses are paths that *can* be shortened across mechanisms.

### 4.2 Definition — two tiers

**Tier 1 — Mechanism (the leak-core).** The **leak-core** of an insecure instance is the subgraph
induced by: the leaking transmitter, its backward `op_edges`-cone up to the protected source(s) (the
leak path(s) and the merge topology), and the set of unresolved branches gating those core
instructions. *Two cores are the same mechanism iff these coincide up to the `idx` symmetry (position-
independent).* Enumeration ranges over **distinct cores** — the single-source leak, the two-source OTB
merge, the deep multi-hop chain are **distinct cores**, each enumerated in its own right. (This is the
`a6DiverseModels` leak-core quotient; `REACH_UNSAT_ENUMERATION.md:231-240`.) *Dropping a core source is
not a contraction — it is a move to a different core.*

**Tier 2 — No padding *within* a fixed core C.** An instance I is a **Minimal Leak Witness for core C**
iff:

- **(W0) Leak.** `¬secure_speculation_scheme_p[no_p]` — I leaks. *(Canonical single-leak form:
  `one_insecure_speculation_scheme_p[no_p]`, `SPT_6_oneLP.als:268`.)*
- **(W1) Genuinely speculative.** `secure[RC→first_uncommitted + RR→first_uncommitted]`
  (`STT_6.als:308`) — committing/resolving the boundary secures it ⇒ the leak is **transient**, not
  architectural.
- **(W2) No structural padding.** Every element **not in C** is load-bearing:
  `∀ i∈Instruction: secure[RI→i]`, `∀ o∈Operand: secure[RO→o]`, `∀ s∈State: secure[RS→s]`
  (= `STT_6_core.als:298,301,303`). Removing any non-core instruction/operand/state secures I ⇒ no
  filler. *(The memalloy Def 15 "every instruction executes / maximal execution" analogue.)*
- **(W3) Irredundant speculation — the tag-along fix.** Let `B` = the unresolved branches. Replace the
  current per-branch *individual* necessity with per-branch *irredundancy*:
  - **(W3a) collectively speculative:** `secure[RR→B]` (`STT_6_multisource.als:320`). *(Near-vacuous —
    resolving all speculation always secures; it merely re-certifies W1. The real content is W3b.)*
  - **(W3b) each branch is relevant (no tag-along):** every `b∈B` **influences** security in some
    resolution context —
    `∀ b∈B: ∃ R ⊆ B∖{b} : secure[RR→(R∪{b})] ≠ secure[RR→R]`.
    A branch that never flips the verdict in any context is a **tag-along** and is excluded (W2 then
    trims it if it is a separate instruction).

### 4.3 Why (W3b) is exactly right, and the current/prototype predicates are not

| predicate | admits AND (two series-gating branches) | admits OR / OTB multi-source | rejects tag-along | verdict |
|---|---|---|---|---|
| **current:** `all b: secure[RR→b]` (`STT_6.als:306`) | ✓ | ✗ (resolving one still leaks via the other ⇒ clause fails ⇒ **pruned**) | ✓ | **forbids the OTB class** (`ENUMERATION_OVERSPECIFICATION.md:103-109`: the probe `some b: ¬secure[RR→b]` is UNSAT in base, SAT relaxed) |
| **prototype:** `secure[RR→unresolved]` (`STT_6_multisource.als:320`) | ✓ | ✓ | ✗ (an irrelevant unresolved branch rides along — resolving *all* still secures) | **too weak — admits tag-alongs** |
| **commented alt:** `some (spec_xmit[∅] − spec_xmit[RR→b])` (`STT_6_multisource.als:328-332`) | ✗ | ✗ | ✓ | **wrong relevance test** — a transmitter stays speculative while *any* older branch is unresolved, so resolving one branch rarely removes it from `speculative_xmit` (fails on both series-AND and OTB) |
| **proposed (W3b):** each branch influential in some context | ✓ | ✓ | ✓ | **correct** |

**(W3b)** is the "no dummy variable of the security Boolean function" condition. It admits **both** the
AND gadget (each branch pivotal in the empty context) **and** the OR/OTB gadget (each branch pivotal in
the context where the *other* is already resolved — e.g. for OTB: with `br_u` resolved the leak survives
only via `br_r`, so resolving `br_r` on top flips it, making `br_r` relevant), and it rejects a
genuinely inert branch.

**Alloy-cost note (for the companion agent).** (W3b) quantifies over subsets `R ⊆ B∖{b}` — a `2^|B|`
quantifier. `|B|` is tiny (≤ a few, at `exactly 6`), so it is finite but awkward. A **core-aware
structural surrogate** avoids the power set: a branch `b` is relevant iff **some core-source load lies
under `b`** (i.e. `b` is among the unresolved branches `spo`-before a load on the transmitter's backward
`op_edges`-cone whose taint is live). A tag-along gates no core-source. This is checkable directly on the
core DAG. **The exact Alloy encoding is the companion `MINIMALITY_TAGALONG_FIX.md`'s to own** (§6); this
doc fixes the *concept* (irredundancy, core-relative) and shows why the three in-tree candidates are
each wrong.

### 4.4 The MCM parallel, made exact
- (W2) "no padding" ↔ critical-cycle **no-chord** / memalloy **maximal-execution** (Def 15).
- (W3) "each branch irredundant" ↔ diy **each cycle edge is a genuine relaxation** (no inert edge on the
  cycle).
- **Tier-1 core enumeration** ↔ diy **enumerate the critical cycles** (each cycle = a mechanism); our
  cores are the mechanisms. The difference — and the whole "be different" point — is that **we must name
  the mechanism (core) explicitly** before minimizing, because our path witnesses shrink across
  mechanism boundaries whereas MCM cycles do not.

---

## 5. SPT specifically — the relax/not-relax decision

### 5.1 What makes SPT different: taint **persists**
STT declassifies a load output at its **visibility point** — `prot_set_propagation` subtracts
`(Loads & no_unresolved_brs_bf_or_is_p & i).inmem.opstate` (`STT_6.als:331`): once a load has no
unresolved branch before it, its loaded value leaves the protection set. **SPT does not.** A load output
is tainted **and stays tainted**; the only legitimate untaint is **STLF from an untainted store**
(`SPT_6_oneLP.als:357`) or being a **genuine constant** (no memory in its cone)
(`POTENTIAL_MODEL_FIX_constaddr_taint.md:48-56`, `SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md:112-120`). SPT's
secret scope is broader (a *non-speculative* loaded value can still be secret).

**Consequence for minimality.** Longer-lived taint ⇒ **longer/deeper leak paths** and ⇒ **multi-source
union-merges that stay tainted while *any* source is live**. The OTB/getOldestTaint class is therefore
**more reachable and more central for SPT than for STT** — so the branch relaxation matters *more* here.

### 5.2 The decision table

| perturbation | STT | **SPT recommendation** | rationale |
|---|---|---|---|
| `RR` (branches) | currently per-branch individual (`STT_6.als:306`) | **RELAX → core-relative irredundancy (W3b)** | multi-branch / OTB is an SPT-family mechanism; persistent union-taint makes it common. Do **not** use the vacuous `secure[RR→unresolved]` alone (tag-alongs). |
| `RS` (states) | per-state individual (`STT_6.als:310`) | **KEEP individual** | a redundant architectural location is **padding**, not a mechanism — there is no "multi-location jointly-necessary leak" to capture. Branches compose into AND/OR speculation gadgets; locations don't. Relaxing `RS` would re-admit location-padding with zero mechanism gain. |
| `RC` (boundary) | boundary clause (`STT_6.als:308`) | **KEEP** | SPT defends **transient** data; a post-commit leak is architectural, not a defense failure. |
| `RI`/`RO` (instr/operand) | **absent** in `STT_6.als`; present in `STT_6_core.als:301,303` | **ADD (core-relative)** | SPT over-generates padding (const-addr FPs, `no_hold` FPs); `RI`/`RO` strip filler. Apply **within a fixed core** so they don't amputate multi-source merges (§4.1). |
| single-transmitter | `not secure` (STT_6) | **KEEP `one_insecure`** (`SPT_6_oneLP.als:268`) | one witness ↔ one leaking transmitter = the clean "one critical cycle ↔ one test" analogue; also keeps cores separable. |

**So: branches and states are handled DIFFERENTLY.** Branches → relax to irredundant (mechanism).
States → keep individual (padding). That asymmetry is the principled core of the SPT answer.

### 5.3 Ordering constraint — fix the taint *before* relaxing minimality
SPT's `hardware_protection_policy = Instruction.operands` (`SPT_6.als:329`; the `oneLP` variant only
subtracts un-`rf`-fed inputs, `:341`) over-approximates "produced under speculation" as "secret" —
`POTENTIAL_MODEL_FIX_constaddr_taint.md` §1 and `SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md` §0b. On that
protset, the current per-branch/per-state necessity clauses are **partly masking const-addr/`no_hold`
noise**, not enforcing mechanism minimality. If you relax `RR` on top of the broken protset, you will
admit **noisy multi-branch shapes** (tag-along-looking branches that only exist because half the operands
are spuriously protected). **Sequence:** land **A1 source-derived-taint closure** (sources = `Loads.outreg`
+ read memory, union-forward; `ALLOY_MODEL_CHANGES.md` §A1) **first**, then the (W3) irredundancy + `RI`/`RO`
core-minimality. Under A1, the core-source set is exactly "load outputs on the cone," so the §4.3 core-
aware relevance surrogate is clean. Batch both into **one** regen (`ALLOY_MODEL_CHANGES.md` §Rerun matrix)
— A1 (protset) + A2 (rf most-recent-writer; `SPT_6_oneLP.als` already has it, `:161-169`) + B2 (this) + B3
(core-min) together, so STT_6 and SPT_6_oneLP are re-enumerated `--force` once.

---

## 6. Reconciliation with the two companion efforts

**(a) Tag-along fix (`MINIMALITY_TAGALONG_FIX.md`, companion agent — not yet written).** This doc's
**(W3)** *is* that predicate's concept: **set-sufficient (W3a) + each-element-necessary (W3b)** = an
**irredundant** unresolved-branch set. This doc contributes (i) the *correct* relevance test — "each
branch influential in some resolution context," and why the three in-tree candidates
(`STT_6.als:306` individual / `STT_6_multisource.als:320` aggregate / `:328-332` removes-a-transmitter)
are each wrong (§4.3 table); and (ii) the insistence that it be applied **core-relative** (§4.1), else
it over-prunes OTB. The **exact Alloy encoding is the companion's to finalize**; the core-aware
structural surrogate (§4.3) is the recommended cheap form. These are consistent — same predicate,
this doc supplies the conceptual spec and the MCM grounding.

**(b) Reach-UNSAT core exhaustion (`REACH_UNSAT_ENUMERATION.md`).** That doc's thesis — *the full
`exactly 6` space is not exhaustible, but the **leak-core / core×control quotient IS** (reach UNSAT over
cores, then flesh out with capped padding)* — is the **enumeration** half of this doc's **definition**
half. They compose exactly:
- This doc's **Tier-1 cores** = their **leak-core quotient** (the space to drive to UNSAT).
- This doc's **(W2)+(W3) minimal-witness** = what makes a core *canonical and padding-free* — i.e. **the
  quotient is well-defined because minimality is mechanism-relative.** "Exhaust the minimal-witness
  space to UNSAT" = reach UNSAT over the (W0-W3) cores.
- `STT_6_core.als` (RI/RO on) is literally their Stage-1 core base (`REACH_UNSAT_ENUMERATION.md` §5(a-c),
  `STAGED_ENUMERATION.md`). The padding fleshed out in their Stage-2 is exactly the non-core material
  (W2) strips from the *core* but a *capped* number of which is allowed around it.

**(c) Over-specification (`ENUMERATION_OVERSPECIFICATION.md`).** Confirms the diagnosis empirically:
per-branch minimality forbids multi-source (§Root cause 1), and — crucially — **relaxing the predicate
alone does not surface the shapes** (`:98-102`): `sol.next()` still returns the structurally-smallest
witnesses first. So **(W3) is necessary but not sufficient** — it must be paired with the **B1 diversity-
driven (core-blocking) enumeration** (`ALLOY_MODEL_CHANGES.md` §B1) to actually *see* the newly-admitted
multi-source cores. Definition (this doc) + predicate (companion) + enumeration (B1/REACH-UNSAT) are the
three legs; none works alone.

---

## 7. Open questions / owner decisions (for Anna)

1. **Approve the `RR` relaxation direction** (per-branch individual → core-relative irredundancy)? This
   is **B2** and is owner-gated (`.als`). The exact predicate text comes from the companion tag-along
   doc; this doc endorses the **concept** and the **core-aware surrogate** form.
2. **Confirm the branch/state asymmetry** (relax `RR`, keep `RS` individual) — §5.2. Is there any
   intended "multi-location mechanism" I'm missing that would want `RS` relaxed too? I believe not, but
   it's a semantics call.
3. **Confirm ordering** — A1 taint fix *before* B2 minimality relaxation (§5.3). Agree to batch A1+A2+B2+B3
   into one regen?
4. **`RI`/`RO` core-minimality for SPT** — adopt the `STT_6_core.als` clauses into the SPT models, applied
   core-relative? (B3.)
5. **Scope of "mechanism-relative"** — do we accept that OTB/multi-source cores are enumerated as
   *distinct cores* (Tier-1) rather than reduced away (i.e., we explicitly keep non-absolutely-minimal
   witnesses because they test distinct defense code paths)? This is the central conceptual commitment.

---

## Sources

**Repo (read-only, this session):** `STAGE1_alloy/models/{STT_6,SPT_6,SPT_6_oneLP,STT_6_core,STT_6_multisource}.als`;
`wiki/findings/mdsToRead/{ENUMERATION_OVERSPECIFICATION,REACH_UNSAT_ENUMERATION,OTB_GENERATION_GAP,POTENTIAL_MODEL_FIX_constaddr_taint,SPT_FENCE_NO_HOLD_HITS_NOT_BUGS}.md`;
`wiki/state/ALLOY_MODEL_CHANGES.md` (line refs inline).

**Papers (read this session):**
- Alglave, Maranget, Tautschnig, *Herding Cats: Modelling, Simulation, Testing, and Data Mining for Weak
  Memory*, ACM TOPLAS 36(2), 2014 — §9.1.2 critical cycles (local `quail/sources/papers/alglave2014-herding-cats.pdf`, p.63-64). **Quoted.**
- Shasha, Snir, *Efficient and correct execution of parallel programs that share memory*, ACM TOPLAS
  10(2):282-312, 1988 — critical cycles (original PDF is scanned-image/non-extractable; **quoted via
  Herding Cats' verbatim recall**). Snir group copy: `snir.cs.illinois.edu/listed/J21.pdf`.
- Alglave, Maranget et al., `diy`/`litmus`/`herd7` toolchain — cycle→test, edge=relaxation
  (`diy.inria.fr/doc/`, read this session). **Paraphrased.**
- Wickerson, Batty, Sorensen, Constantinides, *Automatically Comparing Memory Consistency Models*, POPL
  2017 (`memalloy`; PDF read this session, `johnwickerson.github.io/papers/memalloy.pdf`) — **Def. 15
  (minimal litmus test = maximal execution) quoted**; property = acyclicity (quoted).
- Trippel, Lustig, Martonosi, *CheckMate: Automated Synthesis of Hardware Exploits and Security Litmus
  Tests*, MICRO 2018 (local `quail/sources/papers/trippel-2018-checkmate.pdf`) — µhb-cycle framing +
  minimal exploit program. **Quoted.**
- *(Unverified — web summary only, full text not obtained)* "Automated Synthesis of Comprehensive Memory
  Model Litmus Test Suites" (ASPLOS 2017 line): suites where "no synchronization mechanism can be
  weakened without causing new behaviors to become observable."
