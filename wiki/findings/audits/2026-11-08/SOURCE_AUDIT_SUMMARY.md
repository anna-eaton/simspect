# Source audit 2026-11-08: summary, decisions, and explanations

Rollup for the manual source audit of the official STT, SPT and ReCon gem5 builds (session src-audit, 2026-11-08). The per-defense detail, with `file:line` evidence, is in `SOURCE_AUDIT_STT.md`, `SOURCE_AUDIT_SPT.md` and `SOURCE_AUDIT_RECON.md` in this folder. Everything here comes from reading code; nothing has run in gem5 yet except the fpr-fanout follow-on (see the end). Logs: `claudelog.md` 2026-11-08 17:30 and 18:40.

## What was audited

- STT: upstream `cwfletcher/stt` @ e3283b9 (the commit `/work/stt` uses), tarball at `~/Documents/stanford/trippel/defense_src/stt_e3283b9/`.
- SPT: upstream `FPSG-UIUC/SPT` @ 0d2be0f (the commit `/work/gem5-spt` uses), tarball at `~/Documents/stanford/trippel/defense_src/spt_0d2be0f/`.
- ReCon: the authors' docker tree at `~/Downloads/dockerrecon/gem5-recon` (no git; line numbers run ~11-15 lower than cafe2's `/work/gem5-recon`; unverified that the code is identical).
- Contracts checked against: the `.als` defense blocks (`STT_6.als`, `SPT_6_oneLP.als` + v2 draft, `Recon_6.als`), `specs/leakage/*.json`, `specs/gem5_builds.json`, the papers in `~/Documents/quail/sources/papers/`.

## Findings that count (new, class A unless noted)

| ID | Defense | Finding | Fires in our config today? | Can our pipeline generate it? |
|---|---|---|---|---|
| S1 | STT | Taint dropped through xmm4-low: `rob_impl.hh:229` skips any source with `index()==16` without checking the register class; FP index 16 = xmm4-low (`regs/float.hh:71`). Parent re-checked. | **CONFIRMED in gem5 (2026-11-08, fpr-fanout):** 100 STT_6 load→load tests on `/work/stt` with E3's config: xmm4 routing leaks 98/100, xmm3 control 0/100, GPR baseline 0/100 (check_ld data-obtained gate). Same skip in amulet-STT (`rob_impl.hh:230`). | yes, with the new opt-in fp routing in Stage 2 |
| S4 | STT | One-cycle leak behind a held squash (stock-timing variant of the known VP/squash race A4). | plausibly, narrow | no (needs a mispredicted tainted branch; STT_6 xmit branches are always resolved, `wiki/design/DESIGN.md:5`) |
| R-SA-12 | ReCon | `secure_scheme/taint_tracker.cc:59` skips tainting any value written to physical flat index 16. Parent re-checked. | yes, scheme 2, about 1 in ~220 allocations (agent estimate) | already, by chance; needs a Rename-trace diagnostic to attribute |
| R-SA-13 | ReCon | FP/SSE loads never marked speculative (`decode.cc:691` checks `isFloating()` before `isLoad()`). Parent re-checked. | only with FP loads | not today; fp mode will |
| R-SA-14/15 | ReCon (DoM) | Split loads not made L1-only; speculative L1 hits update replacement state. | scheme 3 | partially |
| A1 | SPT | Backward untaint treats the flags register as an arithmetic input of `inc`, so `cmp secret` flags become public. | needs `inc` + `jb` | no (no flags in model or vocab) |
| A2 | SPT | Backward mov untaint also fires on `cmovcc`/`cmpxchg` with a false condition. | needs cmov | no |
| A3 | SPT | 8/16-bit writes leave the upper bytes marked public while they hold the old secret. | needs 8/16-bit ops | no |

Not counted: STT S2/S3 and ReCon R-SA-16 are store-address leaks. Anna: STT store leaks are known and don't count, and ReCon (built on STT) doesn't protect stores either (`Recon_6.als:320` leakage = `Loads.inaddr + Branchxs.inreg`; the build holds only tainted loads and tainted conditional branches).

## Config and contract findings (class B)

- **R-SA-1, ReCon reveal inactive on classic caches.** The reveal request built in `commitLoad` (`lsq_unit.cc:887-896`) never sets `req->valueFromAddr` (the line is commented out at `:901`), and the cache reads that field (`base.cc:428`; default 0 at `request.hh:102`). So the cache marks block 0 as revealed and no address a test uses is ever un-protected. Our "ReCon" runs (`--caches --allow_leaked`) therefore behave like Recon-STT. Runtime check still owed: a scheme-2 `--allow_leaked` `stats.txt` with `lsq0.revealRequests > 0` and `taint_tracker.allowlistedTaintsFromTT == 0`.
- **SPT B2, the "InvisiSpec" SPT schemes are unprotected.** `SpectreSafeInvisibleSpec` skips every load taint check (`lsq_unit_impl.hh:1142, 1234-1238`) and sends plain reads; with `--configImpFlow=Ignore` branch squashes aren't delayed either. These schemes appear only as leftover run configs (`runconfigs/run_config_SPT_6_*InvisibleSpec*.jsonc`) and a "needs" note in `specs/defense_units.json:383`; they are not eval rows.
- **SPT B1:** gem5 never makes a branch's condition public at the visibility point; paper and model say it does. gem5 is stricter, so it hides no leak.
- **ReCon R-SA-17:** only conditional branches and stores cast shadows (no indirect jumps/returns, no DoM E/M shadows).
- **ReCon R-SA-18:** `check_ld` scores NDA store-forwarded loads and DoM speculative L1 hits as leaks, though both are by design.

## Anna's decisions (2026-11-08)

- STT store leaks are known and don't count.
- A branch that has executed but whose squash hasn't happened yet counts as **unresolved**. So A4 and S4 are implementation bugs, not contract gaps.
- **Only report an audit finding if SimSpect's own pipeline finds it.** No hand-written gadgets for SPT A1-A3 for now; grow the vocabulary and fanout instead.
- Don't run the SPT InvisiSpec schemes (interpretation of "we don't really need to"; to confirm).
- Add an **fp mode** to the fanout, as a separate corpus (not mixed with the normal one).
- Randomize register naming: keep symbolic names through the passes, pick real names randomly at the end.
- Put an agent on a much better fanout: more random interleaving, more instructions, random choice.

## Explanations (for future sessions)

**xmm.** x86-64 has 16 general-purpose integer registers (rax ... r15) and 16 SSE registers, xmm0-xmm15, each 128 bits, used for floating point and SIMD; compilers also use them to hold or move 64-bit values (`movq %rax,%xmm4`). gem5 stores each xmm register as two 64-bit FP registers (low and high) placed after the 8 MMX registers, so xmm k low is FP index 8+2k, and xmm4 low is index 16 (`stt_e3283b9/src/arch/x86/regs/float.hh:71-75`, `x86_traits.hh:57`). STT's "skip the zero register" test checks only the number 16, so it also skips xmm4-low.

**A4 vs S4.** Same root cause: STT counts a branch as resolved as soon as it executes, so when the branch resolves, the instructions on its wrong path become untainted before the squash removes them, and a wrong-path load can touch the cache in that gap. A4 (the known race, `wiki/findings/bug/stt_slowcomm_vp_squash_race/`) starts from a mispredicted branch with an untainted condition; at stock timing the squash and the untaint land in the same commit cycle with the squash first, so it only leaks when commit-to-IEW delay is 2-3+ cycles (the slow-comm experiment). S4 starts from a mispredicted branch with a tainted condition, whose squash STT deliberately holds; when an older branch resolves, commit untaints the wrong path in cycle N (`markCompletedInsts`, `commit_impl.hh:726`) but the held-squash check already ran earlier that cycle (`:964`), so the squash fires in N+1, a one-cycle window at stock timing.

**S4's shape and why we don't generate it.** Needed: (1) an older branch B0, correctly predicted but slow to resolve; (2) a speculative load L1; (3) a branch B1 whose condition depends on L1 (tainted) and which mispredicts; (4) on B1's wrong path, a load L2 that reads a secret; (5) a transmitter T whose address comes from L2, issued in exactly the cycle B0's completion reaches commit. STT_6 never emits a mispredicted branch with a tainted condition: its transmitter branches are always resolved (`wiki/design/DESIGN.md:5`, 9,995/9,995 sampled br_x resolved), and B1 is exactly that kind of branch. Hitting the exact cycle also needs variable padding between L2 and T, which better random interleaving could provide.

**Register randomization and R-SA-12.** Our register names are architectural (rax, rcx, ...). gem5 renames every write onto a physical register taken from a free list, so which physical register a value lands on depends on the history of writes (including microcode temporaries), not on the name we pick. R-SA-12 is about physical register 16, so randomizing our names doesn't target it. Existing corpora probably hit it by chance; to attribute a hit, re-run with the `Rename` debug flag and look for physical int 16 in the transmitter's source chain. S1 is different: it is about the architectural name xmm4, so a random xmm choice hits it about 1 time in 16 per routed value. Today pass 3 maps the locked `Reg_s$*` atoms in sorted order and only randomizes unconstrained slots (`parsexml.py:1455-1461`).

**Caches.** The eval manifest shrinks caches only on the footprint rows E12-E14 (InvisiSpec, CleanupSpec, SpecLFB), whose channels are evictions and MSHR/TBE contention and need pressure (`wiki/state/EVAL_MANIFEST.md:70`). STT, ReCon and SPT rows (E1-E11) use the authors' configurations. The audit's SPT config is exactly E11's flags; the fpr-fanout test uses E3's run config (`runconfigs/fixed_20261030/STT_6_stt_fixed_latest.jsonc`). For taint defenses this is right: the leak test is whether the transmitter obtained its data inside the window, which doesn't depend on cache pressure, so shrinking would amplify nothing and only invite a reviewer objection.

**Would adding instructions to the fanout produce these shapes?** S1 and R-SA-13: yes, routing load results through xmm touches every load-to-load leak path. SPT A1-A3: mostly not by vocabulary alone, because the ALU op has to sit on the path between the secret and the transmitter, and in the flat STT_6 corpus every ld transmitter's address comes straight from one load (0 of 66,512 via an other op, per CLAUDE.md / `OTB_GENERATION_GAP.md`). So the lever is interleaving that puts ALU ops on the path, plus vocab (8/16-bit ops for A3, cmov for A2). A1 also needs flags as a dataflow edge, which neither the model nor the vocab has.

**ReCon contract accuracy (`Recon_6.als`, the manifest's E6 model; its Stage-1 core `Recon_6_core_ri.als` is running on cafe2).**
- Leakage function (`:320`, loads + branch conditions): matches the build.
- Speculation contract (`:315`, uncommitted and behind an unresolved branch): matches for branches, but the build also treats instructions behind an older store with an unknown address as speculative (`decode.cc:686-695`). The model omits store shadows; that is a coverage gap, not unsoundness, and the STL draft `proposed/Recon_6_stl.als` adds them.
- Propagation (`:323`): a load with no unresolved older branch makes the location it reads public. That is STT's rule and matches the build.
- Protection set / reveal (`:316-318`): inaccurate against both the paper and the code. The model reveals transitively through ALU chains, as soon as LD2 is non-speculative, per location, and never re-protects on a store. The paper and code reveal only for a direct load pair, at LD2 commit, per word, and conceal when a store commits (paper p2 §5.2 and p1 §4.3, quoted in `wiki/design/TWO_PHASE_MODELS.md:371`; code R-SA-10). In practice the clause is a no-op (R-1: Recon cores equal STT's), and the code's reveal is dead on classic caches (R-SA-1), so today both sides behave as STT and agree by accident. Fixing it is the R-2 rewrite plus conceal-on-store, and only worth doing if the gem5 side can actually reveal (`--ruby`, since patching the defense is off the table).
- Skeleton: lacks `rf_from_most_recent_writer` (manifest E6 note; same gap as SPT v2-1).

**ReCon transmission criteria and R-SA-12.** `specs/leakage/recon.json`: a load transmitter leaks if it executes inside the window (after the last committed instruction retires, before the first uncommitted one retires, branches unresolved) and obtains its data (`reached_cache` or `store_forward`); branch transmitters go through `check_br`. An R-SA-12 case is an ordinary load hit under this criterion: the access load's result lands on physical int 16, never gets tainted, so the transmitter isn't held and reaches the cache. So the criterion already sees it. It doesn't surface because on recon-modded the known store-forward bypass (A2) already makes almost every load test hit (91/94 in the round-4 2% sample, all bucketed A2), so a roughly 0.5%-per-test effect is buried, and a 2% sample has under one expected case. Attributing it needs a Rename-trace diagnostic (physical int 16 in the transmitter's source chain), run on hits A2 doesn't explain or on tests where store forwarding can't happen. gem5's free list is a FIFO (`cpu/o3/free_list.hh:76`), so a freed physical 16 is reused only after every other free register, which fits the agent's ~1-in-220 estimate.

## Open questions (also in `URGENT_TODO.md`, "Manual source audit")

- ReCon naming: relabel the ReCon runs "Recon-STT, reveal inactive" after the stats check, or add a `--ruby` ReCon run.
- NDA/DoM leak criteria before the STL round runs schemes 1 and 3 (R-SA-18).
- ReCon phys-reg-16 diagnostic bucket for existing hits (R-SA-12).
- ReCon contract: R-2 reveal rewrite plus conceal-on-store, and whether it's worth it while reveal is inactive.
- Lower priority: R-SA-7 (park), granularity findings R-SA-3/4/5 (out of scope), SPT B1 (record only).

## Follow-on work

- **fpr-fanout agent** (claim in `claudenotes.md`): opt-in xmm routing in `parsexml.py`, byte-identical when off; S1 test on `/work/stt` (xmm4 vs xmm3 vs GPR baseline); then fp mode as a separate corpus, randomized register naming, and a fanout v2 proposal (random interleaving, vocabulary, which shapes become reachable) as a section in `wiki/design/VOCAB_TABLES.md`.
