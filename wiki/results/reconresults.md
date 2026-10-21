# Recon gem5: Two Bugs in STT Taint Tracking

## Overview

Investigation of the Recon gem5 implementation (`/work/gem5-recon`) revealed two bugs in its STT (Speculative Taint Tracking) defense that allow speculative loads to access the cache despite having tainted source operands. Both bugs are present in Recon's STT-base mode (`--scheme=2`).

## Bug 1: OTB — `getOldestTaint` Picks Wrong Taint Source

### Summary

When an ALU instruction has multiple tainted source operands, Recon's taint tracker picks the **oldest** (lowest `seqNum`) taint source to associate with the destination register. If that oldest source's speculation resolves first (its branch commits), the taint is freed — even though a younger, still-speculative taint source also contributed to the result.

### Mechanism

**File:** `src/cpu/o3/secure_scheme/taint_tracker.cc`

```cpp
DynInstPtr
TaintTracker::getOldestTaint(const DynInstPtr &inst)
{
    DynInstPtr oldest = inst;
    for (int i = 0; i < inst->numSrcRegs(); i++) {
        PhysRegIdPtr reg = inst->renamedSrcIdx(i);
        if (isTainted(reg) &&
            taints.at(reg)->seqNum < oldest->seqNum) {   // BUG: picks OLDEST
            oldest = taints.at(reg);
        }
    }
    assert(oldest->seqNum < inst->seqNum);
    return oldest;
}
```

`propagateTaints()` (line 108) calls `getOldestTaint()` and stores only that single taint source for all destination registers:

```cpp
void TaintTracker::propagateTaints(const DynInstPtr &inst)
{
    if (!hasTaintedSrc(inst)) return;
    const DynInstPtr oldest = getOldestTaint(inst);
    for (int i = 0; i < inst->numDestRegs(); i++) {
        insertTaint(inst->renamedDestIdx(i), oldest);
    }
}
```

`freeTaints()` (line 134) removes a taint entry when its associated load is no longer speculative:

```cpp
void TaintTracker::freeTaints()
{
    for (auto it = taints.cbegin(); it != taints.cend(); ) {
        DynInstPtr inst = it->second;
        if (!inst->isSpeculative()) {
            taints.erase(it++);
        } else { ++it; }
    }
}
```

### Exploit scenario

The test case (`oldest_taint_bug/debug_out/inst-oldest-taint-bug.s`) constructs:

```
Program order (speculative window):

  branch_outer    correctly NOT-taken, slow condition (cache-miss evicted)
                  → creates wide speculation window (~200+ cycles)
  ┌─────────────────────────────────────────────────────
  │ PC1  movq (%rdi), %rax       load_A → %rax tainted (spec under branch_outer)
  │      movq (%rsi), %rdx       (load branch_inner's evicted condition)
  │
  │ PC2  movq (%rdx), %rsi       branch_inner condition load (slow, cache-miss)
  │      testq %rsi, %rsi
  │      jne   end               branch_inner mispredicts NOT-taken
  │      ┌──────────────────────────────────────────────
  │      │ PC3  movq (%rdi), %rcx   load_B → %rcx tainted (spec under branch_inner)
  │      │ PC4  leaq (%rax,%rcx), %rax   add: getOldestTaint picks load_A (older)
  │      │                                → %rax tainted with load_A, NOT load_B
  │      │ PC5  movq (%rcx,%rax), %rax   TRANSMITTER — tainted address
  │      └──────────────────────────────────────────────
  └─────────────────────────────────────────────────────
```

**Timeline:**

1. Both loads (`load_A`, `load_B`) execute speculatively; both taint their destinations.
2. `leaq (%rax,%rcx), %rax` (PC4) has two tainted sources. `getOldestTaint()` picks `load_A` (lower seqNum).
3. `branch_outer` resolves (correctly not-taken) → `load_A` is no longer speculative.
4. `freeTaints()` sees `load_A` is non-speculative → removes `%rax`'s taint entry.
5. The transmitter load at PC5 now has an **untainted** address operand → STT allows it to access cache.
6. But `load_B` (`%rcx`) is **still speculative** — `branch_inner` hasn't resolved. `%rax = %rax + %rcx` depends on speculative data.

### Pipeline evidence

From `oldest_taint_bug/debug_out/pipeline_scheme2_focused.txt`:

```
                                                                                    disasm               seq_num
[=======================f=dnp================================================================================ic=======]  MOV_R_M  [575]  (XMIT)
```

Seq 575 (the transmitter load at PC5) shows `ic` — it **issued and completed** (accessed cache) despite being in a speculative window. The `=` markers and `r=0` confirm it was eventually squashed, but the cache access already leaked the secret-dependent address.

In the unprotected baseline (`pipeline_scheme0_focused.txt`), the same load shows an identical `ic` pattern — STT provided **no additional protection**.

### Correct behavior

The taint for `leaq (%rax,%rcx)` should track the **youngest** (most recently allocated, highest seqNum) taint source. Alternatively, it should track **all** taint sources and only free the destination's taint when **every** contributing source has resolved. Using youngest-seqNum is the simpler fix: a taint is only freed when its associated load's branch resolves, and the youngest branch always resolves last (or simultaneously).

### Source references

| File | Lines | Description |
|------|-------|-------------|
| `src/cpu/o3/secure_scheme/taint_tracker.cc` | 119-131 | `getOldestTaint()`: picks lowest seqNum |
| `src/cpu/o3/secure_scheme/taint_tracker.cc` | 108-116 | `propagateTaints()`: stores single oldest taint |
| `src/cpu/o3/secure_scheme/taint_tracker.cc` | 134-155 | `freeTaints()`: removes taint when source is non-speculative |

---

## Bug 2: STL — Store-to-Load Forwarding Bypasses STT Taint Check

### Summary

When a load's address matches a prior in-flight store, the LSQ forwards the store's data directly to the load via the STLF (store-to-load forwarding) path. This path returns early from `read()`, **completely bypassing** the STT taint check that would otherwise delay or block the load.

### Mechanism

**File:** `src/cpu/o3/lsq_unit.cc`, function `read()`

The `read()` function has two paths:

1. **STLF path** (line ~1950): If a store in the store queue covers the load's address range, data is copied from the store buffer, a `WritebackEvent` is scheduled, and the function returns `NoFault` at **line 2030**.

2. **Normal cache path** (line ~2072+): If no STLF match, the function continues to the STT taint check at **line 2090**, which delays tainted loads.

```cpp
// STLF path — lines 1950-2030
if (coverage == AddrRangeCoverage::FullAddrRangeCoverage) {
    // ... copy data from store buffer ...
    memcpy(load_inst->memData, store_it->data() + shift_amt,
           request->mainReq()->getSize());

    WritebackEvent *wb = new WritebackEvent(load_inst, data_pkt, this);
    cpu->schedule(wb, curTick());
    ++stats.forwLoads;
    return NoFault;                    // <— EARLY RETURN, bypasses taint check
}

// ... (line 2070: no forwarding case) ...

// STT taint check — lines 2090-2103 (NEVER REACHED for STLF loads)
if (cpu->scheme == CPU::Scheme::STT &&
    cpu->taintTracker.isTaintedInst(load_inst)) {
    // ... delay the load ...
    load_inst->clearIssued();
    cpu->delayUnit.insertTaintedLoad(load_inst);
    return NoFault;
}
```

The `WritebackEvent::process()` handler (line 194) checks for the `Delay` scheme but **not** the `STT` scheme:

```cpp
if (cpu->scheme == CPU::Scheme::Delay &&
     inst->isLoad() &&
     inst->isSpeculative()) {
    // ... insert into delay unit ...
    return;
}
// No STT check here — load writes back normally
```

### Exploit scenario

The test case (`STL_bug/inst-008297.s`) constructs:

```
Speculative window (mispredict_not_taken):

  PC1  movq $1, %rdx         (first_noncommitted)
       testq %rdx, %rdx
       jne   end              mispredict → speculative window opens
       ┌──────────────────────────────────────────────
       │ PC2  movq (%rsi), %rax      speculative load → %rax TAINTED
       │ PC3  movq %r8, (%rsi,%rax)  store to tainted address (data = %r8)
       │ PC4  movq (%rsi,%rax), %r10 TRANSMITTER load — same address as PC3
       └──────────────────────────────────────────────
```

**What should happen (correct STT behavior):**
- PC4's source register `%rax` is tainted (from PC2).
- The STT check at line 2090 should detect `isTaintedInst(PC4) == true` and delay the load.
- The transmitter should never access the cache with a secret-dependent address.

**What actually happens:**
- PC4 finds PC3's store in the store queue (same address `(%rsi,%rax)`).
- The STLF path copies PC3's data directly and returns `NoFault` at line 2030.
- The STT taint check at line 2090 is **never reached**.
- PC4 writes back with forwarded data, completing as if untainted.

A second test case (`STL_bug/inst-000637.s`) shows the same pattern with an additional branch layer:

```
  PC1  movq (%rsi), %rax       speculative load → %rax TAINTED
  PC3  movq %r9, (%rsi,%rax)   store to tainted address
  PC5  movq (%rsi,%rax), %r9   TRANSMITTER — STLF from PC3, bypasses taint check
```

### Impact

Any speculative load that gets its data from store-to-load forwarding is immune to STT's taint delay mechanism. An attacker can construct a gadget that:
1. Speculatively loads a secret into a register (tainting it).
2. Stores arbitrary data to a secret-dependent address.
3. Loads from the same secret-dependent address — STLF forwards the data, bypassing the taint check.

The load at step 3 completes immediately with the forwarded data. While the forwarded *data* itself may not be secret, the *address* is secret-dependent, and the cache line brought in reveals the secret through a side channel.

Note: In the STLF case, the data comes from the store buffer, not from cache. However, the load's completion still has microarchitectural side effects (e.g., triggering dependent instructions, affecting the pipeline) that can leak information about the tainted address.

### Interaction with `allowLeaked` / `stlForw` flag

Recon has a separate `allowLeaked` mechanism (for the Delay scheme) that sets `stlForw = true` on forwarded loads (line 1967-1969). This flag is then checked in `freeTaints()` to prevent premature taint freeing. However, `allowLeaked` is a Delay-scheme feature — in STT mode, the fundamental problem is that the taint check at line 2090 is never reached at all.

### Source references

| File | Lines | Description |
|------|-------|-------------|
| `src/cpu/o3/lsq_unit.cc` | 1950-2030 | STLF path: copies data, returns `NoFault` early |
| `src/cpu/o3/lsq_unit.cc` | 2090-2103 | STT taint check: delays tainted loads (unreachable for STLF) |
| `src/cpu/o3/lsq_unit.cc` | 194-212 | `WritebackEvent::process()`: checks Delay but not STT |
| `src/cpu/o3/lsq_unit.cc` | 1967-1969 | `stlForw` flag: only set when `allowLeaked` is true |

---

## Affected builds

Both bugs are present in:
- **Recon gem5** (`/work/gem5-recon`) with `--scheme=2` (STT mode)
- These are structural issues in the taint tracker and LSQ, not configuration-dependent

## Repository

- Recon gem5: `/work/gem5-recon`
- Test cases: `/tests/simspect/oldest_taint_bug/` (OTB), `/tests/simspect/STL_bug/` (STL)
- Pipeline traces: `/tests/simspect/oldest_taint_bug/debug_out/pipeline_scheme{0,2,2_fixed}_focused.txt`
