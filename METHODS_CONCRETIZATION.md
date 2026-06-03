# SimSpect — the enumeration & concretization phase (an alternative overview)

*A design-rationale walkthrough of how a symbolic Alloy leak instance becomes a runnable gem5
litmus test — written to explain **why each piece exists**, not just what it does. This is offered
as an alternative to the existing internal writeup; it leans on the constraints and the empirical
findings that shaped each decision. Source of truth: `STAGE1_alloy/models/*.als` (enumeration) and
`STAGE2_compilation/parsexml.py` (concretization). Companions:
[`PAPER_RESULTS.md`](PAPER_RESULTS.md), [`METHODS_LEAKAGE_KNOBS.md`](METHODS_LEAKAGE_KNOBS.md),
[`METHODS_INSTRUMENTATION.md`](METHODS_INSTRUMENTATION.md).*

---

## 0. The central design decision: enumerate symbolically, concretize separately

The pipeline is deliberately split into a **symbolic enumeration** phase (Alloy → XML) and a
**concretization** phase (XML → LLVM → asm + annotation). The single most important thing to
understand is *why* it is split, because almost every downstream behavior — good and bad — follows
from it.

**Alloy reasons about equivalence classes of dataflow, not programs.** A model instance is a
*symbolic* graph: instructions of a kind (`TLoad`, `TBranchx`, …), operands (`Inreg`, `Inaddr`, …),
and an abstract **state** each operand reads or writes (`Reg_s$3`, `Mem_s$1`), tied together by
reaching-definition (`rf`), data-influence (`ddi`), and program-order (`spo`) edges, plus three
booleans per instruction (committed / resolved / is-transmitter). It says *"a value produced here
reaches a transmitter there while speculative"* **without committing to which physical register
carries it, which x86 opcode implements the ALU op, or what concrete address the load uses.**

That abstraction buys three things, and they are the reason the split exists:

1. **The model stays small, defense-agnostic, and checkable.** Security is one predicate
   (`secure_speculation_scheme_p`) over the symbolic graph; the SAT solver can enumerate *minimal,
   necessary* leak shapes (`gen_useful_litmus`) without ever modeling a CPU. One model serves every
   defense — gem5 is the only place a specific defense's behavior enters.
2. **One symbolic instance fans out to many concrete tests.** The same XML is concretized once per
   **branch mode** (`mispredict_not_taken`, `mispredict_taken`) and, with interleaving on, into
   several `_v<k>` variants — different *programs* that all realize the one modeled leak. The XML is
   shared (`testsets/<model>/xml/`); only Stage-2 outputs are per-mode.
3. **It localizes "is the test real?" to the concretization layer.** Because Alloy works over
   equivalence classes, *which* realization Stage-2 picks decides whether the running program
   actually carries the modeled dataflow. This is the origin of the two big artifacts (C1 rf-clobber,
   C2 const-addr): they are **concretization choices with consequences**, not model errors per se.

So: **the enumerator decides *what leak shape to test*; the concretizer decides *what program
realizes it*; gem5 decides *whether that program actually leaks*.** Keep those three responsibilities
separate when reading anything below.

---

## 1. Enumeration (Stage 1, Alloy → XML)

### 1.1 What an instance is, and why it is symbolic

Each `inst-NNNNNN.xml` is one satisfying assignment of the model: a set of instructions with kinds
and the three booleans, a set of operands with their `opstate`, and the `rf`/`ddi`/`spo` relations.
There are **no registers, no opcodes, no addresses** — only the dataflow skeleton and the speculative
state. That is exactly the information the leak predicate needs and nothing more, which is what keeps
the search tractable and the model reusable.

### 1.2 Why the tests are *minimal and necessary* (`gen_useful_litmus`)

Alloy could emit any leaking sequence; instead `gen_useful_litmus` (the Tier-2 conjunction in
`METHODS_LEAKAGE_KNOBS.md`) demands the instance **leak** *and* that **every load-bearing part be
necessary** — resolving any still-unresolved branch (`RR`) or removing any state (`RS`) must break
the leak. The design intent is a corpus of *tight* litmus tests: no dead branches, no no-op padding,
each test isolating a distinct dataflow reason a defense could fail.

The grounding is empirical. The `RS` ("every state necessary") clause is what removes no-op padding:
fresh enumeration with it active gives **0% isolated no-op ops, 1.4× redundancy, 45 distinct leak
dataflows**; without it, **38% isolated, 8.6× redundancy, only 2 dataflows**
(`project_stale_stt_testsets`). The shipped `STT_6` testsets predate the *effective* `RS` clause and
therefore under-cover — they cover 2 of ~45 dataflows — which is the documented reason a from-XML
regen is recommended (C4). The minimizer deliberately uses **only `RR`/`RS`, never `RI`/`RO`** (remove
instruction / operand): extra `other` ops and *unspecified operands* are allowed to survive, because
those are the slots interleaving later fills.

### 1.3 Streaming and the cap (and its known side effect)

Enumeration streams in batches (`alloy.batch_size=1000`) up to `alloy.max_instances=100000`, so
Stage-2 can begin concretizing while Alloy is still producing (the producer/consumer
`testsetgen.py`). The cap is a knob with a **designed-in but consequential** side effect: the solver
emits the *simplest* satisfying shapes first, so the 100k cap fills with direct `load→xmit` and
`branchx` instances **before** reaching rarer shapes like the `ld→other→xm` OTB precursor — which is
*legal* (immediately SAT when forced) but **absent** from the capped corpus (C3). The standing lesson
(`OTB_GENERATION_GAP.md`): never read "absent from the capped enumeration" as "the model can't" —
force the shape with a predicate and re-run.

---

## 2. Concretization (Stage 2, `parsexml.py`) — pass by pass, with rationale

`parsexml.py` runs a fixed pass pipeline. Each pass exists to resolve one kind of "don't-care" the
symbolic instance left open, in an order chosen so that later passes can rely on earlier ones.

```
 pass1_specify_state_a   (347)  abstract State atoms  → concrete state slots (reg vs mem, floating vs fixed)
 pass2_specify_instr     (529)  InstrType            → concrete x86 instruction templates (instructions.jsonc)
 pass2_5_specify_branches (633) committed/resolved   → the concrete mispredict per branch_mode (+ fall-through)
 pass_interleave         (950)  [optional]           → inject synthetic chains into the speculative region (_v<k>)
 pass3_assign_operands   (1139) opstate              → physical registers / memory offsets  ← the heart of it
 pass4_ssa               (1400) operand assignments  → SSA / virtual-reg pool / alloca offsets
 pass5_emit_llvm         (1597) the resolved program → inst-*.ll
 emit_branch_annotations (2195) the leak metadata    → inst-*.ann.json  (the bridge to gem5)
```

### 2.1 `pass1_specify_state_a` — give each abstract state a concrete home

The model's `Reg_s`/`Mem_s` atoms become concrete state slots, with operands that the instance left
unspecified marked **floating** so a later pass can fill them. **Why a separate pass:** the
register-vs-memory decision (which `opstate` is a register state vs a memory state) must be fixed
*before* operands are assigned, because it determines whether an operand draws from the register pool
or the memory-offset pool in pass3.

### 2.2 `pass2_specify_instructions` — pick real x86 templates

Each `InstrType` becomes a concrete instruction template drawn from
`STAGE2_compilation/instruction_tables/instructions.jsonc` (e.g. a `TLoad` → a `movq (addr),reg`
form; a `TOtherx` → an ALU op). **Why a table:** it decouples "what operation" from "the model" — the
model only knows kinds, and the table is where x86 reality (operand signatures, the `idivq`
divide-fault idiom, etc.) lives. The D3 `idivq` guard (route the divisor through `%rcx` with
`orq $$1` *except* for xmit divs) lives here, because the noise-vs-leak distinction is an x86-codegen
concern, not a model concern.

### 2.3 `pass2_5_specify_branches` — realize the mispredict, per mode

The abstract "unresolved branch" becomes a concrete mispredicting branch for the chosen
`branch_mode`, and the fall-through path is set up so the speculative region has something to fetch.
**Why it is mode-specific:** `mispredict_not_taken` and `mispredict_taken` open the speculative window
through different control paths and different pipeline timing, so they must be concretized separately
(and `taken` additionally needs the BTB-force annotation from `emit_branch_annotations`).

This pass carries a **cross-stage invariant** worth calling out (full argument in `DESIGN.md`): it
injects a synthetic fall-through NOP after an xmit *branch* when the next instruction is also a
branch — and assigns it `pc = br_pc+1`, which the following branch already owns. That duplicate-PC
path (D1) was a live codegen bug dropping ~6% of br_x tests (`symbol already defined`); it was fixed
by injecting only when the xmit branch is last. The invariant that made it *usually* dormant — "xmit
branches are always resolved in STT_6" — is itself an *emergent* property of the leak predicate
(`speculation_contract_p` + `tag_xm`), not an explicit fact. The lesson the design records: a future
model change that lets an xmit branch be unresolved must re-check this pass.

### 2.4 `pass_interleave` — manufacture multi-source merges (optional)

When `interleave.enabled`, this pass (between 2.5 and 3) injects 1–2 synthetic instruction chains
(`other`/`ld`/`str` steps) into the *uncommitted/speculative* region, with every injected operand
pinned to **free-pool atoms** (`Reg_s$fr*`, `Mem_s$fr*`). **Why it exists:** a single Alloy instance
is one dataflow chain, so it cannot express a transmitter fed by *two independent* speculative chains
— the recon OTB / `getOldestTaint` shape. Interleaving is the mechanism to build exactly that, by
arranging for an injected chain's terminal to collide with a base instruction's *blank* operand in
the shared pool (pass3). It shifts PCs, so it also rewrites the branch annotations to match. (As
noted in `OTB_GENERATION_GAP.md`, in practice the collisions tend to land off the transmitter's
address path, so even interleaving needs a forcing predicate to actually assemble OTB — but the
mechanism is here.)

### 2.5 `pass3_assign_operands` — the heart: opstate → physical registers/offsets

This is where symbolic dataflow becomes a real register/memory program, and where the two big
artifacts originate. It maintains three assignment sources (lines ~1201–1292):

- **`locked_reg_map` (deterministic).** Operands connected by an `rf` edge — i.e. dataflow the model
  *specified* — are assigned a fixed physical register so the producer and consumer genuinely share
  it. **Why deterministic:** if the modeled dependency is to be realized, the consumer *must* read the
  producer's register; sampling would break the leak. This is `locked_registers` in the output.
- **`free_pool` (sampled).** Operands the instance left **unspecified** ("floating") are filled by
  sampling `free_pool` (the tail of the virtual register pool). **Why sampled:** the model didn't
  constrain them, so any realizable value is fine — but the *choice* matters (below).
- **`fr_reg_map` / `fr_mem_map` (interleave).** The injected free-pool atoms (`Reg_s$fr*`) map onto
  `free_pool` registers. **The deliberate collision:** because *both* a base instruction's blank
  operand and an injected chain's operand draw from the **same** `free_pool`, the map can assign them
  the same physical register → a natural cross-chain data dependency. That collision is the entire
  point of interleaving — it is how an injected load "hooks onto" a base ALU's blank argument.

**Why one shared pool** (rather than separate pools): the collision *is* the feature. The same
mechanism that fills an ordinary unspecified operand is what lets an injected chain merge into the
base program, so OTB-style merges fall out of the normal assignment path instead of needing bespoke
wiring.

**Where the artifacts come from — be precise about which layer:**
- **C1 (rf-clobber)** is a *Stage-1* gap surfacing here: because `rf` is not pinned to the
  most-recent same-state writer (`rf_from_most_recent_writer` not enforced), a state can have two
  writers and pass3 will assign the register deterministically — but a *newer* same-state write then
  clobbers it, so the consumer reads the wrong value. ~58% of the testset carries ≥1 such edge. The
  fix is in the model (Option A), not pass3 — pass3 is faithfully realizing an under-constrained
  graph.
- **C2 (const-addr)** is the *model's* protection over-approximation realized as a concrete address:
  a load whose address operand is "protected" but is in fact produced from constants concretizes to a
  fixed scratch address, which gem5 correctly does not treat as secret. pass3 is again faithful; the
  fix is the model's protection-set definition.

The honest framing the design keeps: **pass3 does exactly what the symbolic graph says; when that
graph is under-constrained (C1) or over-broad (C2), the realized program diverges from the intended
leak, and gem5 — correctly — doesn't leak.** That is why gem5 is the ground-truth filter and why
"hit" ≠ "bug."

### 2.6 `pass4_ssa` — SSA, the virtual-register pool, and alloca offsets

The assigned operands are put in SSA form and threaded through a virtual-register pool with concrete
memory offsets and total `alloca` size. **Why:** LLVM IR is SSA, so emitting clean `.ll` (next pass)
needs single-assignment form and a stable mapping from the abstract memory states to real stack
offsets.

### 2.7 `pass5_emit_llvm` — emit portable IR (and the prologue that becomes a stimulus limiter)

The resolved program is emitted as `inst-*.ll`, then `llc`/`clang` lower it to `inst-*.s`. **Why LLVM
IR rather than asm directly:** it is a portable, well-formed intermediate that the toolchain lowers
to correct x86 (register allocation, calling convention, the `bb_<pc>:` label scheme the branch
annotations reference). The function prologue **zero-initializes the stack frame**
(`movq $0, N(%rsp)`) to give every test a clean architectural baseline.

That prologue is also, honestly, a **stimulus limiter**: it pre-warms the scratch slots, so a load
whose address concretizes to a fixed slot is a cache *hit* on a constant address — no miss, no
secret-dependent install. **What this does and does not block is the subtle point** (`PAPER_RESULTS.md`
§4/§9): it does **not** stop SimSpect from *demonstrating* a speculation-taint defense bug — STT's A4
race and SpecLFB's UV6 are both "the defense let/failed-to-delay a speculative transmitter that acted
in-window," which holds regardless of the address value, and both are demonstrated on this corpus.
What the constant address *does* block is the **end-to-end secret-*recovery* PoC**: a measurable
secret-dependent cache *footprint* needs a secret-derived, cache-missing address, which today's
concretization does not produce. (For the *data-taint* defense SPT-Fence the same const address is a
genuine non-bug — an untainted constant is correctly not fenced.) So the prologue is a correct design
choice for a clean baseline that bounds *secret recovery*, not *bug demonstration* — a tension the
const-addr stimulus fix (`POTENTIAL_MODEL_FIX_constaddr_taint.md`) resolves.

### 2.8 `emit_branch_annotations` — the bridge to gem5 (`inst-*.ann.json`)

The final pass writes the per-test annotation the Stage-3 checkers consume. **Why it exists:** gem5
runs a plain binary; the *leak metadata* — which instruction is the transmitter (`xmit.kind`/`pc`),
the speculation-boundary instruction (`first_noncommitted`), the last-committed instruction
(`last_committed`), and the per-branch annotations (BTB-forced target for `taken` mode, resolve-stall
cycles) — has to ride alongside so the checker knows *what to look for* and *how to reproduce the
window*. Concretely, the annotation is what lets `check_ld` compute `lc_retire < signal < fnc_retire`
and lets `se.py` force the modeled mispredict and stall a branch's resolution (see
`METHODS_INSTRUMENTATION.md`). The transmitter `kind` in this file is what routes each test to the
right per-type checker (`ld`→`check_ld`, `br_x`→`check_br`, `other_x`→`check_other`).

---

## 3. Why the artifacts are concretization decisions, not accidents

It is worth stating plainly which layer each known issue belongs to, because the design intentionally
pushes "is it real?" to this phase:

| issue | layer it actually lives in | what concretization does | fix |
|---|---|---|---|
| **C1 rf-clobber** | Stage-1 `rf` under-constraint | faithfully realizes a graph that allows a stale writer | model `Option A` (owner-gated), regen |
| **C2 const-addr** (disqualifier for *data-taint* defenses only) | Stage-1 protection over-approx | concretizes a "protected" constant to a fixed address → SPT-Fence correctly doesn't fence it (non-bug); does **not** disqualify STT/SpecLFB | model protection-set fix (owner-gated) |
| **const-addr stimulus** (bounds *secret-recovery PoC*, not bug demo) | Stage-2 prologue zero-init | pre-warms the scratch slot → cache hit, no install → blocks a measurable secret footprint (not the UV6/A4 demonstration) | secret-derived, cache-missing address concretization |
| **D1 dup-PC** | Stage-2 `pass2_5` codegen | injected NOP duplicated a PC label | fixed (inject only when xmit branch is last) |
| **D3 idivq noise** | Stage-2 `pass2` template | unguarded divide faulted architecturally | fixed (`orq $$1,%rcx` guard except xmit divs) |

The pattern: **Stage-1 decides the shape; Stage-2 realizes it faithfully; the divergences between
"intended leak" and "running program" are either Stage-1 under/over-constraint (C1/C2) surfacing at
realization, or Stage-2 codegen bugs (D1/D3) that have been fixed.** None of them are gem5 doing the
wrong thing — which is the whole reason the symbolic/concrete split, and gem5-as-ground-truth, is the
right architecture.

---

## 4. The phase in one paragraph

Alloy enumerates **minimal, necessary, symbolic** leak shapes — dataflow graphs where a transmitter
is provably fed a speculative, protected value — streaming up to a 100k cap whose ordering quietly
biases toward the simplest shapes. `parsexml.py` then resolves every don't-care in a fixed order:
states get homes (pass1), kinds get x86 templates (pass2), the mispredict is realized per mode
(pass2.5), optional synthetic chains are injected to manufacture multi-source merges (interleave),
and — the crux — abstract `opstate` becomes physical registers via a **deterministic locked map for
specified dataflow** and a **shared sampled free pool for the rest** (pass3), whose deliberate
collisions are what let injected chains merge. SSA, IR, and asm follow, and a per-test annotation
carries the leak metadata and the BTB-force/resolve-stall hooks that let gem5 reproduce the exact
speculative window. Every divergence between the intended leak and the program that runs lands in
this phase by design — which is exactly why gem5 is left to be the ground truth.
