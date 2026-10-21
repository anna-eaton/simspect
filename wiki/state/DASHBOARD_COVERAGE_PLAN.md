# DASHBOARD COVERAGE PLAN — make the dashboard cover the WHOLE repo

*Drafted 2026-10-20 (cleanuprepo). Goal (Anna): the dashboard surfaces literally every piece of
information in the repo, locked to canonical source, nothing invisible. This closes the gaps found in
the coverage audit (see REPO_WALKTHROUGH / chat). Build is file-edits only — deploy is Anna's git.*

## Principle
One canonical source per thing; the dashboard reads it directly (or a summary that regenerates when
its source changes). Nothing lives only on disk-but-invisible. Every corpus, model, config, build,
hook, spec, and finding has a home on the dashboard.

## The gaps → the additions

### A. Model inventory + `.als` viewer + enumerate  (HIGHEST VALUE)
**Gap:** the Pipeline XML column only lists models that already have a testset; **10 `.als` models are
invisible** (never enumerated), and you can't view a model's source.
- **Backend** `model_inventory()`: scan `STAGE1_alloy/models/*.als` → `{name, bytes, symlink_target,
  instr_scope (exactly N Instruction), transmitters (leakage_function), defense_family
  (STT=State / SPT=Operand / Recon=param), enumerated (has testsets/<name>/xml), xml_count}`.
  Also flag `old_models/` separately (archived). `/api/models`.
- **Backend** `model_source(name)`: return the `.als` text + the above metadata + vscode link. `/api/model`.
- **Frontend:** the XML column = the UNION of (every model on disk) + (testsets). Un-enumerated models
  render greyed with an **[Enumerate]** button (launches the xml phase job; stub the launch at first).
  Click any model box → inspector shows the `.als` source + scope/transmitters/defense + open-in-VSCode.

### B. Sources-of-truth viewers (Utilities) — one generic "catalog" pattern
A reusable "file catalog" renderer: given a list of files, show name + description + open-in-VSCode +
inline text/markdown. Apply to:
- **Run configs** — `runconfigs/*.jsonc` (the build/scheme/timing library). `/api/catalog?kind=runconfigs`.
- **gem5 hooks** — `gem5-hooks/**` (patches + README; the instrumentation). `kind=gem5hooks`.
- **Findings** — `wiki/findings/**` (bug writeups, `mdsToRead/`) + `bugsynth/*.md` (KV1/KV3/OTB/
  pending-squash). Rendered markdown. `kind=findings`.
- Existing `specs()` (transmitter-stage-mapping, timing-directives, instruction table) stays.

### C. gem5 builds inventory
**Gap:** the GEM5 column shows past campaigns, not which builds exist to run against.
- **Backend** `gem5_builds()`: query the container `/work/*` → `{name, is_git, remote, scheme_map}`
  (best-effort; cache it). `/api/gem5builds`. Feeds the "Run on build" launcher's build picker.

### D. Corpus provenance inspection
**Gap:** dashboard shows "provenance ✓" but can't open it.
- **Backend** `provenance(model)`: list `testsets/<model>/provenance.tar.gz` contents (the exact
  `.als` + `parsexml.py` + run config that made the corpus). Show in the corpus inspector.

### E. Diagnostics / hit bucketing
**Gap:** `results/<run>/diagnostics/` known-vs-new attribution isn't shown.
- **Backend:** per gem5 campaign, read `diagnostics/buckets/<mode>/` → counts per known cause + NEW.
  Show in the GEM5 box inspector. (Later — depends on diagnostics being present.)

## Build order
1. **A (model inventory + `.als` viewer)** — the biggest "cover everything" win. Backend + XML-column
   frontend + inspector.
2. **B (catalog viewers: runconfigs, gem5-hooks, findings)** — cheap, high value, one generic pattern.
3. **C (gem5 builds)** — feeds the run launcher.
4. **D (provenance), E (diagnostics)** — inspector enrichments, later.

## Stubs (unchanged from DASHBOARD_PLAN)
Launch actions (enumerate / fanout / run-on-build) remain stubs until wired end-to-end; granular
per-process progress still a stub. Everything here is read/aggregate only — safe, no pipeline changes.

## Deploy note
All of this is dashboard-only (dashboard_data.py + dashboard_ui.py + endpoints). Per the GIT WRITE
LOCK, Anna commits/pushes; the container pulls + restarts (`make dash`) to go live.
