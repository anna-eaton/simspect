# Staged Alloy enumeration: minimal cores → STT_6 flesh-out

**For Anna.** New optional XML-production path that decouples *what leak shapes exist*
(few minimal cores) from *how many concrete tests each yields* (capped flesh-out), so
one base instance can't dominate the `max_instances` cap. Built 2026-06-10. **Nothing in
the existing flat pipeline changed** — this is additive (one new `.als` copy + two new
scripts). The existing `STT_6.als` / `pipeline.py xml` path is untouched.

## Why

A flat `run gen_lit ... for 9 but exactly 6 Instruction` fills the 100k cap by
enumerating many variants of whatever shape the solver reaches first (the
`OTB_GENERATION_GAP.md` problem: simple direct shapes crowd out complex ones). Staging
instead enumerates the **minimal leak cores** once, then gives **each** core an equal
budget of fleshed-out concrete tests.

## The two stages

```
STAGE 1  STT_6_core.als  ── a6CountModels ──▶  minimal cores (inst-*.txt/xml)
         (max-minimized: idx/length rules removed, all RO+RI+RC+RR+RS on)
SEED     stage_seed.py: core .txt ──▶ structural Alloy `pred seed_core`
STAGE 2  STT_6.als + seed_core ── a6CountModels ──▶ ≤N fleshed-out tests / core
         (real STT_6: exactly 6, NO RI/RO → free to ADD instructions/operands)
         ──▶ globally-renumbered into testsets/<model>/xml/  (llvm/asm/gem5 unchanged)
```

### Stage 1 — `STAGE1_alloy/models/STT_6_core.als`
A **copy of `STT_6.als`** with exactly three changes (all flagged `[STAGE-1 CORE]` in-file):
1. **Ordering rules removed** — the `idx`/`IX0..IX5` symmetry-breaking field, sigs, and
   facts (`idx_bijective/surjective/matches_spo`, `lt_ix`) are deleted. `spo_*` program-
   order facts are **kept** (they are execution semantics, not symmetry-breaking).
2. **Length restriction removed** — `run ... for 9 but exactly 6 Instruction` →
   `but 6 Instruction` (≤6), so cores aren't pinned to a fixed length.
3. **All relaxations on** — `gen_useful_litmus` adds operand-minimality
   (`all o: Operand | secure[RO->o]`) and instruction-minimality
   (`all i: Instruction | secure[RI->i]`) on top of STT_6's RR+RC+RS. Every operand
   and instruction is now *necessary* → maximally-minimized cores.

Same sigs / same STT defense / same vocabulary as `STT_6.als`, so a core re-imposes on
`STT_6.als` with **zero translation**. Measured: yields **2 canonical 3-instruction
cores** (the Spectre-v1 skeleton: unresolved branch → load1[mem→reg] → load2[xm, addr
`rf`-fed by load1]). Exhausting the search to *prove* no more cores is very slow, so
stage 1 is **wall-clock bounded** (`--core-timeout`, default 120s; cores are written
incrementally so the timeout just stops the fruitless exhaustion proof).

### Seeding — `STAGE1_alloy/stage_seed.py`
Parses a core's `inst-*.txt` and emits a **structural** `pred seed_core` (existential
over distinct `Instruction`/`Operand` vars). It pins: kinds, **relative** spo order
(`b in a.^spo`, so stage 2 may *insert* instructions between core ones), resolved/
committed/xm flags, operand membership + opstate, and the `rf`/`ddi` dataflow edges.
Structural (not atom-pinned) so it is robust to STT_6's idx symmetry-breaking and atom
identity.

### Stage 2 — real `STT_6.als` + `seed_core`
`stage_pipeline.py` splices `seed_core` into STT_6's `run gen_lit` body
(`gen_useful_litmus` **and** `seed_core`) and appends the predicate, then enumerates ≤
`--per-core` instances. **Soundness:** STT_6 has no RI/RO minimality, so the extra
instructions/operands it adds (up to `exactly 6`) are legal "fleshing out"; the result
still satisfies STT_6's own RR/RC/RS minimality + the STT leak. So each fleshed test is
a genuine STT_6-valid litmus test that *contains* the minimal core. Verified: 5 distinct
6-instruction programs from core 1 (extra branches/loads/stores added; load transmitter
preserved).

## Orchestrator — `STAGE1_alloy/stage_pipeline.py`
```bash
python3 stage_pipeline.py \
    --core-model models/STT_6_core.als --flesh-model models/STT_6.als \
    --out-xml-dir ../testsets/STT_6_staged/xml \
    --max-cores 200 --per-core 50 --core-timeout 120 --flesh-timeout 180
```
Stage1 → per-core seed+flesh → copies every extension XML (+`.txt`) globally renumbered
into `--out-xml-dir`, and writes `_staged_manifest.txt` (which inst-range came from which
core). The output dir is a drop-in `testsets/<model>/xml/`: run the normal
`pipeline.py llvm/asm/gem5` (or `testsetgen.py`/`testrun.py`) on it unchanged.

**End-to-end verified 2026-06-10:** 2 cores → 4/core → 8 XMLs → `pipeline.py llvm
--model STT_6_staged` produced 8/8 `.ll` in both branch modes, zero errors.

## Status / open items for Anna
- **`STT_6_core.als` is a new `.als`** — per the repo rule that model edits go through you,
  please eyeball the three flagged changes. It is a pure copy+relax of `STT_6.als`; the
  STT defense/contract is byte-identical.
- Tunables: `--max-cores`, `--per-core`, the two timeouts. Defaults are conservative.
- Removing idx symmetry-breaking in stage 1 means more isomorphic duplicates *would*
  appear, but `a6CountModels` runs Kodkod symmetry breaking (`opt.symmetry=80`) so the 2
  cores are already canonical at this scope.
- Same recipe generalizes to other defenses (SPT/Recon) by pointing `--core-model` /
  `--flesh-model` at a `<X>_core.als` + `<X>.als` pair (would need a matching core copy).
- Not wired into a `run_config.jsonc` yet — it's a standalone producer. If you want it as a
  first-class `pipeline.py` phase, that's a follow-up.
