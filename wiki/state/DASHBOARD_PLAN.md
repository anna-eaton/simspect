# DASHBOARD PLAN — corpora-as-first-class pipeline view

*Drafted 2026-10-20 (cleanuprepo session) from Anna's spec. This is a PLAN + an alignment
assessment + open questions. Nothing built yet — Anna answers the questions first, then we build.*

## The goal (Anna's vision, restated)

One page where the **corpora are first-class citizens**, laid out as **stage columns left→right**, so
you can see at a glance: what corpora exist at each stage, how far each got (progress from a
manifest), whether each is **up to date** with its parent (dirty/stale flags), and what's
**running vs stopped** (one jobs manifest). Links (arrows) connect a corpus to the corpus it came
from. Buttons/launchers kick off new generation. Clicking a corpus opens an **inspector** (its full
generation info + a dropdown to view individual instances). Plus a utility area to inspect the
**sources of truth** (transmitter criteria, timing specs, instruction/decoding tables, config schemas).

---

## Alignment assessment — what matches the repo, what I'm correcting

### ✅ Matches the repo well
- **Stages 1–4 are real and already produce artifacts in canonical places.**
  - Stage 1 (XML): `STAGE1_alloy` Alloy run → `testsets/<model>/xml/inst-*.xml`.
  - Stage 2 (LLVM): `parsexml.py` → `testsets/<model>/<mode>/llvm/*.ll` + bare `ann/`.
  - Stage 3 (ASM): `compile_annotate.py` (llc/clang) → `testsets/<model>/<mode>/asm/*.s` + resolved `ann/`.
  - Stage 4 (gem5): checkers → `results/<results_name>/.../window-results.json`.
- **A jobs manifest already exists** — `jobs_registry.py` → `jobs/manifest.jsonl`: append-only
  start/end records per job, reduced last-wins, pid-liveness marks a job `running`/`stale`/`done`/
  `failed`. Writers: testsetgen (gen), testrun (sweep), the dashboard launch button. **This is
  exactly the "ongoing + stopped jobs" manifest you want** — it just needs richer surfacing.
- **Provenance is already archived** — `pipeline.save_provenance` copies the exact `parsexml.py`,
  `.als`, and run config into the testset. So "what generated this corpus" is recoverable.
- **The "red until unsat / complete" idea is meaningful.** The Alloy run has a `max_instances` cap
  (default 100k). If it enumerates fewer than the cap, it exhausted the space (reached unsat =
  truly complete); if it hits the cap, it's incomplete (more instances exist).

### ⚠️ The one big correction: WHERE fanout happens
Your spec puts fanout (choosing different instructions, interleave) on the **llvm→asm** edge.
**In the code it's the opposite:** all the fanout/diversity is created in `parsexml.py`, which is the
**xml→llvm** step:
- instruction choice: `random.choice(valid)` (parsexml pass2, line ~576)
- operand assignment: random from the free pool (pass3)
- interleave `_v<k>` variants: `pass_interleave` (line ~950)
- branch-mode split (mispredict_not_taken / _taken): `pass2_5_specify_branches`

The **asm step is deterministic** — `llc`/`clang` just compile the already-chosen `.ll`, and the ann
is "resolved" (addresses filled from the compiled binary). No choices are made there.

**Consequence:** the fanout launcher belongs on the edge where `parsexml` runs. Since the `.ll` is a
throwaway intermediate between "make the program" (parsexml, where all choices happen) and "compile
the program" (deterministic), this strongly supports your instinct to **drop LLVM as a tracked stage**.

### ✅ Recommendation: 3 columns, not 4 — drop LLVM as a first-class corpus
```
   COLUMN 1                COLUMN 2                         COLUMN 3
   XML corpus       →      PROGRAMS corpus          →       GEM5 results
   (1 per Alloy model)     (= parsexml-fanout + compile)    (1 per programs corpus × build)
   red until complete      N per XML (timestamped runs)     leak/no-leak per test
   [regen button]          [FANOUT LAUNCHER on the edge]    [run-on-build launcher]
```
- **LLVM `.ll` becomes an internal build artifact** of the PROGRAMS step (kept on disk for
  debugging, but not a tracked corpus with its own box). Fewer things to track — your stated goal.
- A **PROGRAMS corpus** = one fanout configuration (instruction/interleave/mode choices + seed)
  applied to an XML corpus, then compiled. **Many PROGRAMS per XML** (your "multiple asms per llvm",
  now "multiple programs per xml") → these are **timestamped** with a meta.json, since canonical
  naming isn't unique. The fanout launcher is the only way to make one (it's not a plain button).
- XML→PROGRAMS edge has the **FANOUT LAUNCHER** (configure enumeration axes: which instructions,
  interleave on/off + variants, modes, exhaustive-vs-random per axis, seed, cap).
- PROGRAMS→GEM5 edge has a **run launcher** (pick gem5 build + scheme + transmitter-criteria json +
  timing-config json). Each PROGRAMS corpus can be run against several builds → several gem5 blocks.

> If you'd rather keep 4 columns (XML|LLVM|PROGRAMS|GEM5), we can — but then the fanout launcher sits
> on **xml→llvm** (where parsexml runs) and **llvm→asm is a plain deterministic "compile" button**.
> I recommend the 3-column collapse. **← decision needed (Q1).**

---

## Canonical layout + manifests

### Corpora locations (canonical, parent-referencing)
- **XML**: `testsets/<model>/xml/` — named by the Alloy model stem (so all children reference it).
- **PROGRAMS**: `testsets/<model>/programs/<fanout-id>/` where `<fanout-id>` is a timestamp+label
  (e.g. `20261020_143000_exhaustive`). Holds `asm/`, `ann/`, the internal `llvm/`, and a `meta.json`.
  *(Today asm lives at `testsets/<model>/<mode>/asm/`; moving to a per-fanout dir is the main layout
  change — needs care + a migration. ← Q2.)*
- **GEM5**: `results/<results_name>__<ts>/` (already timestamped by testrun) with its `run_config.jsonc`.

### Two manifests
- **Jobs manifest** — `jobs/manifest.jsonl` (EXISTS). Surface every job (gen/fanout/sweep) with
  status running/stale/done/failed, started/ended, pid, model, config. Already powers the dashboard's
  jobs panel; the new view reads the same source.
- **Corpora manifest** — NEW: `jobs/corpora.json` (or derived live). For each corpus: stage, id,
  parent id, created-at, file counts / progress, completeness (unsat-reached?), and a **dirty flag**
  (child older than parent → stale). Two ways to build it (← Q3):
  - **Now (fast, no generator changes):** derive it by scanning the tree — counts, mtimes
    (child mtime < parent mtime ⇒ dirty), cap-vs-count for completeness. Read-only.
  - **Authoritative (robust, later):** each generator writes a `meta.json` at completion
    (model, config, parent, started/ended, reached_unsat, instance count, fanout axes). Small
    additive change to pipeline/testsetgen/testrun. The dashboard then trusts meta.json over mtimes.

### Completeness ("reached unsat") signal (← Q4)
Today we can only infer: `count < max_instances` ⇒ exhausted (complete/green); `count == cap` ⇒
incomplete (red). To make it **authoritative**, the Alloy enumerator (`a6*Models.java`) should emit
an explicit `reached_unsat: true/false` into the xml corpus meta. Proposal: heuristic now, explicit
marker later.

---

## The view (what gets built)

Left→right columns, each box = a corpus:
- **Col 1 XML** — one box per `testsets/<model>/xml`. Status bar = instance count + completeness;
  **red until complete (unsat/under-cap)**, green when complete. [Regen] button → launches an Alloy
  job (writes jobs manifest).
- **Col 2 PROGRAMS** — boxes per fanout run, arrow from the XML it came from. Progress bar = how many
  instances concretized+compiled. Green when done AND up-to-date with its XML (dirty flag if the XML
  regenerated later). The XML→PROGRAMS arrow carries the **[Fanout launcher]**. Dirty corpora show ⚠️.
- **Col 3 GEM5** — one box per (PROGRAMS corpus × gem5 build), arrow from its PROGRAMS corpus.
  Shows leak/no-leak progress. Click → the run's transmitter-criteria json + timing-config json + build.
- **Inspectors** (click any box) — generation info for that corpus + a dropdown to view individual
  instances. **For now the per-instance viewer is a STUB** (shows raw file); richer viz comes later.
- **Utility / sources-of-truth panel** — easy-to-find inspectors for: transmitter-criteria specs
  (the per-kind checker criteria, already in `dashboard_data.CHECKERS`), timing-config schema, the
  instruction/decoding table (`STAGE2_compilation/instruction_tables/instructions.jsonc`), and
  run_config schema. **Stubs where a rich viewer is wanted; real where data already exists.**

### Build scope for NOW (proposed)
Real: the 3-column view, reads jobs manifest + derived corpora manifest, dirty/completeness flags,
arrows, the **[Fanout launcher]** (launches a real fanout job), the **[Regen XML]** button, the
**[Run on build]** launcher, click-to-inspect popups showing generation metadata + an instance
dropdown. Stub: the deep per-instance visualizers and the fancier source-of-truth viewers.

---

## DECISIONS (2026-10-20, locked)
- 3 columns **XML → PROGRAMS → GEM5** (LLVM is an internal artifact, not tracked).
- Pipeline view = a **grid, one row per model (lineage)**, 3 stage columns (no fragile SVG arrows).
- **3 top-level tabs:** **Pipeline** (the grid + all launchers + folded-in sweep-monitor info),
  **Status** (Code STATUS + Paper STATUS + the old Sweep Monitor's content now lives on Pipeline),
  **Utilities** (instruction/decoding table, transmitter criteria, `specs/` viewers, launch fanout,
  exec graph, annotation viewer, docs).
- PROGRAMS layout: move to `testsets/<model>/programs/<fanout-id>/` **going forward**; the graph
  reads both the new per-fanout layout and the current per-mode layout. (Destructive migration of
  existing container testsets = separate careful step.)
- Corpora manifest: **derive-by-scan now** (dashboard polls `/api/pipeline`); generators write
  authoritative `meta.json` later; handwrite entries for existing corpora.
- Sweep monitor is **deprecated** — all its info (stage progress, defense variant, hits by
  mode×kind) folds into the Pipeline gem5 boxes.

## STUBS & TODO — utils/helpers to build out later (left as stubs for now)
- [ ] **Granular progress bars** — hook real progress out of running Alloy/parsexml/gem5 jobs
      (counter files / log parsing). Today progress = on-disk file counts polled by the dashboard.
- [ ] **Per-stage instance visualizers** — rich viewers for an XML instance, a program (.s+ann),
      a gem5 pipeview/result. Inspector currently just shows the raw constituent file.
- [ ] **Generators write `meta.json`** per corpus (model, config, parent, started/ended,
      reached_unsat, fanout axes) → authoritative manifest instead of mtime heuristics.
- [ ] **Alloy enumerator emits explicit `reached_unsat`** (vs the count-vs-cap heuristic).
- [ ] **Per-fanout disk layout migration** for existing testsets (`<mode>/` → `programs/<id>/`).
- [ ] **Fanout launcher axes** wired end-to-end (exhaustive/random per axis, interleave variants,
      modes, seed, cap) → a real fanout job writing to `programs/<id>/`.
- [ ] **Run-on-build launcher** (pick gem5 build + scheme + transmitter-criteria + timing json).
- [ ] **Fill the spec stubs** — `specs/transmitter_stage_mapping.json`, `specs/timing_directives.json`.
- [ ] **Regen XML button** → launches an Alloy job + marks children dirty.
- [ ] **Collapse asm / llvm / results / sweep into ONE corpus at the end granularity** (Anna, 2026-10-21).
      Right now they read as separate categories; they shouldn't be. `llvm` is an internal build artifact,
      `asm`+`ann` ARE the PROGRAMS corpus (the terminal generation granularity), and `results`/`sweep` are
      just the gem5 output *of* that corpus. Unify the data model + the view so each stage is ONE corpus at
      its end granularity (XML → PROGRAMS → GEM5), no llvm/asm/results/sweep sub-category sprawl.
- [ ] **Unstub the run buttons** (Anna, 2026-10-21). [Enumerate] (xml), the fanout launcher (xml→programs),
      and [Run on build] (programs→gem5) currently just `alert("coming soon")`. Wire them to actually
      launch the real jobs (write the jobs manifest; testsetgen for enumerate/fanout, testrun for run-on-build)
      so the dashboard can drive runs, not just view them.

## Open questions for Anna (answer these, then I build)
1. **Drop LLVM as a tracked stage → 3 columns (XML | PROGRAMS | GEM5)?** (Recommended; matches the
   code since fanout is in parsexml.) Or keep 4 columns with fanout on xml→llvm?
2. **PROGRAMS layout.** OK to move asm/ann under `testsets/<model>/programs/<fanout-id>/` (per-fanout,
   timestamped)? That's the main on-disk change (current layout is per-mode). It needs a small
   migration + touching testsetgen/testrun output paths. Or keep current paths and just *group* them
   in the view for now?
3. **Corpora manifest: derive-by-scan now, authoritative meta.json later?** (Recommended.) Or write
   meta.json from the generators from the start (more upfront change to pipeline/testsetgen/testrun)?
4. **Completeness: heuristic (count vs cap) now, explicit Alloy `reached_unsat` marker later?**
5. **New view = a new "Pipeline" tab in the existing dashboard** (keep current panels), or replace the
   current layout? (Recommended: new primary tab.)
6. **Fanout axes to expose in the launcher** — confirm the list: instruction choice (exhaustive/
   random), interleave (on/off + variants_per_instance), branch modes (nt/taken/both), seed,
   max_instances cap. Anything else?
