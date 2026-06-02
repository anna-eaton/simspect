# Branch enumeration in `pass2_5_specify_branches` (parsexml.py)

> Draft for review. Describes how the three Alloy branch flavors
> (`flagged-xm`, `flagged-resolved`, `flagged-unresolved`) map to enumeration
> modes and what each emits. Line numbers are post-fix (duplicate-PC NOP fix).

## Key insight

**Only `flagged-unresolved` branches actually enumerate across modes.**
`flagged-xm` and `flagged-resolved` each have exactly one fixed shape and
*ignore* the run's `branch_mode` entirely (the xm override `continue`s at
`:756`, the resolved block `continue`s at `:796`, both before the mode split).

## The two axes

- **Branch flag** (from Alloy): `xm` (transmitter), `resolved`, or
  `unresolved`. Checked in that priority — `xm` wins over `resolved`.
- **Run `branch_mode`**: `mispredict_not_taken` | `mispredict_taken`. This is
  the *only* run-level enumeration knob. There is **no** "predicted-taken" run
  mode; the only correctly-predicted shape is the internal `correctly_not_taken`
  that resolved branches always get.

## Master chart

| Branch flag | `branch_mode` | Applies? | `mode` written | concrete | arch outcome (`condition_value`) | `taken_target` | `fallthrough_target` | BTB forced | NOP? | trampoline? |
|---|---|---|---|---|---|---|---|---|---|---|
| **xm** | *(ignored)* | one fixed shape | `mispredict_not_taken` | `br_bez` | **taken** (ZF=1, `True`) | `end_block` | `bb_{pc+1}` (or `end_block` if last) | `fall_through` | only if **last** instr | no |
| **resolved** | *(ignored)* | one fixed shape | `correctly_not_taken` | `br_cond` | **not taken** (`False`) | `end_block` | `bb_{pc+1}` (or `end_block` if last) | `fall_through` (correct) | no | only if `taken==ft` (last pc), to stop SimplifyCFG folding |
| **unresolved** | `mispredict_not_taken` | yes | `mispredict_not_taken` | `br_cond` | **taken** (`True`) | `end_block` | `bb_{pc+1}` | `fall_through` | no | no |
| **unresolved** | `mispredict_taken` | yes | `mispredict_taken` | `br_cond` | **not taken** (`False`) | `bb_{pc+1}` (critical) | `end_block` | `taken` | no | **yes** (`ftbypass_{pc}`) |

So there are **4 distinct shapes** total, not 3×2.

## How each works + final code shape

### 1. flagged-xm — forced fall-through misprediction (the transmitter), mode-independent

The override hardcodes it regardless of `branch_mode` (so even in a
`mispredict_taken` run, the xm branch keeps this shape). Architecturally taken →
`end_block`; BTB forced to fall-through → the CPU speculatively runs the
instructions *after* the branch, then squashes. The transmitter signal is the
branch's own redirect (caught by `check_br.py`); its resolution is **not**
stall-delayed — the window comes from upstream unresolved branches.

```llvm
; condition read from Alloy inreg0 (phys-pinned movq → preserves load→branch taint for STT)
%bez_raw = call i64 asm sideeffect "<mkr>movq $1, $0", "=&r,{<phys_in0>}"(i64 %inreg0)
%bez_i1  = icmp eq i64 %bez_raw, 0          ; eq 0 → ZF semantics
br i1 %bez_i1, label %end_block, label %bb_{pc+1}   ; arch→end_block ; spec fall-through→bb_{pc+1}
```

If Alloy specified no inreg → `xorq`-self fallback (guaranteed ZF=1, no taint).
NOP inserted only when the branch is the last instruction (post-fix); otherwise
the real `bb_{pc+1}` is the fall-through content.

### 2. flagged-resolved — correctly-predicted not-taken (window generator), mode-independent

Not a transmitter and not a mispredictor. It's a correctly-predicted branch
whose **resolution broadcast is delayed** by `resolve_stall_cycles` (gem5
`--branch-ann-file`). While it sits unresolved, everything after it stays
speculative — *that's the speculation window the xm leaks in.*

```llvm
%cond_raw = call i64 asm sideeffect "<mkr>xorq $0, $0", "=&{<vpool>}"()  ; cond=False → ZF=1
%cond_i1  = icmp ne i64 %cond_raw, 0
br i1 %cond_i1, label %end_block, label %bb_{pc+1}   ; jne NOT taken → arch falls through to bb_{pc+1}
```

(If it's a *resolved-xm* with a specified inreg, the init is a phys-pinned `movq`
instead of `xorq`, to keep the taint chain.) If it's the last pc
(`taken==ft==end_block`), an `ftbypass` trampoline is emitted so SimplifyCFG
doesn't fold away the `testq+jne` and misplace the marker.

### 3. flagged-unresolved + `mispredict_not_taken`

Architecturally **taken** → `end_block` (skips the rest of the program). BTB
predicts fall-through → speculatively runs `bb_{pc+1}` (everything after), then
squashes. No trampoline needed — the architectural edge *is* the taken edge to
`end_block`.

```llvm
%cond_raw = call i64 asm sideeffect "<mkr>movq $$1, $0", "=&{<vpool>}"()  ; cond=True → ZF=0
%cond_i1  = icmp ne i64 %cond_raw, 0
br i1 %cond_i1, label %end_block, label %bb_{pc+1}   ; jne taken → end_block ; spec→bb_{pc+1}
```

### 4. flagged-unresolved + `mispredict_taken` (the trampoline case)

Architecturally **not taken**. The critical Alloy section (`bb_{pc+1}`) must be
reachable *only* by the mispredicted taken path, never committed. So the
not-taken edge is routed through an explicit `ftbypass_{pc}` trampoline straight
to `end_block`. BTB forced **taken** → speculatively runs the critical section,
then squashes on resolve.

```llvm
%cond_raw = call i64 asm sideeffect "<mkr>xorq $0, $0", "=&{<vpool>}"()  ; cond=False → ZF=1
%cond_i1  = icmp ne i64 %cond_raw, 0
br i1 %cond_i1, label %bb_{pc+1}, label %ftbypass_{pc}   ; taken edge = critical section
ftbypass_{pc}:
  call void asm sideeffect ".globl <ftb_lbl>\0A<ftb_lbl>:", ""()   ; non-trivial → survives SimplifyCFG
  br label %end_block                                              ; arch not-taken bypasses critical
```

The `.globl` body is mandatory — without it LLVM folds the lone
`br label %end_block` back into the predecessor and the bypass vanishes from the
`.s`, letting the critical section fall through architecturally.

## Why this matters for the NOP-collision bug

The NOP-collision only ever touched the **xm** row (the `xm_nop_inserts` queue
lives only in the xm override and the two dead twins). Notably, the xm branch is
**always `mispredict_not_taken`-shaped**, so its `fallthrough_target` is the
speculative path — and when another instruction already occupies `bb_{pc+1}`,
that real block *is* the fall-through content, which is exactly why the synthetic
NOP was both redundant and a PC collision. The `resolved` and `unresolved` rows
were never affected.

## Open item (needs sign-off)

Stale comment at `:2088-2089` says "mispredict_taken-xm also routes through
br_bez via pass2_5" — that describes the **dead** pre-override path at `:811`.
Post-rework, xm never gets a `mispredict_taken` shape; the override forces the
row-1 shape unconditionally. Correct this comment? (not done yet)
