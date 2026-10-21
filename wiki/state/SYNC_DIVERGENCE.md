# Mac ↔ cafe2 divergence + gem5-hook durability audit

*Built by the cleanup-agent session, 2026-10-20.*

> **✅ PART 1 (repo divergence) RESOLVED 2026-10-20.** Mac = origin/main = cafe2 container =
> `e652da1`. cafe2 June work committed (`cafe2-june-work`/`9338bea`), Mac Oct work (`207d75e`),
> merged (`e652da1`), pushed, container reset. No data lost. Container GitHub auth fixed via a
> repo-scoped deploy key (see INFRA.md). Verified: dashboard selftest PASS.
> **PART 2 (gem5 hook durability) still OPEN** — deferred workstream.

## TL;DR

1. **The simspect repo has a true two-way divergence.** Mac and cafe2 both sit on the same commit
   (`4f3bb1a`, Jun 8) but moved forward in **different directions, and both edited the same files.**
   It is **NOT** a one-way "Mac is source of truth, force push" — doing that would destroy real
   June research work that exists only on cafe2 (incl. 2 protected `.als`).
2. **The gem5 hooks are NOT tracked durably.** Two key builds (`gem5-recon`, `gem5-recon-modded`)
   are **not git repos at all** — the Recon instrumentation exists only as raw files inside the
   ephemeral docker container, no history, no backup. The other builds (`stt`, `gem5-spt`) have the
   hooks as **uncommitted** diffs against upstream.

---

## Part 1 — simspect repo divergence

Both trees: `HEAD = 4f3bb1a 2026-06-08 "idek anymore"`, remote `origin git@github.com:anna-eaton/simspect.git`.
Mac is 0 ahead / 0 behind origin. cafe2 is the docker container `gem5_dev:/tests/simspect`.

### Mac moved forward on (uncommitted, not on cafe2)
- **Dashboard rewrite:** `dashboard.py` rewritten to import split modules; new untracked
  `dashboard_data.py`, `dashboard_ui.py`, `jobs_registry.py`, `simspect_paths.py`.
- **The sim rig:** `scripts/sim`, `scripts/simspect.env` (connect-or-create Slurm→docker→tmux).
- **The wiki scaffold:** `wiki/` (README, INFRA, this audit, REPO_MAP, COMMANDS).
- Modified tracked: `.gitignore`, `CLAUDE.md`, `Makefile`, `pipeline.py`, `sweep_monitor.py`,
  `testrun.py`, `testsetgen.py`.
- Local stray: `STAGE1_alloy/models/SPT_6_oneLP 2.als` (stale Jun-1 dup — delete, see Part 3).

### cafe2 moved forward on (uncommitted, NOT on Mac) — ~96 non-generated items
- **`bugsynth/` (60 files)** — a whole bug-synthesis workspace: `check_br_differential.py`,
  `check_br_ni.py`, channel-D probe, OTB checks, design/review `.md`s
  (NMOSIER_PENDING_SQUASH_BUG, OTB_BUG_REVIEW, PENDING_SQUASH_BUG_REVIEW, FINDINGS_SUMMARY, …),
  plus a nested STAGE2/STAGE3 snapshot + configs. **Entirely absent on Mac.**
- **`bug/` demos (14)** — `kv1_demo/`, `kv3_demo/`, `uv2_demo/` (runnable PoCs + .s/.ann.json),
  `STT_KV3_TLB_REVIEW.md`.
- **`mdsToRead/` (5 NEW, zero overlap w/ Mac's 5)** — `AMULET_BUGS_DETECTION_ACCOUNTING.md`,
  `AMULET_LOAD_DEFENSES_PROJECT_LOG.md`, `ENUMERATION_OVERSPECIFICATION.md`,
  `INVISISPEC_UV1_CONFIRMED.md`, `STAGED_ENUMERATION.md`.
- **`STAGE1_alloy/` tooling (5)** — `a6DiverseModels.java`, `stage_pipeline.py`, `stage_seed.py`,
  **+ 2 PROTECTED `.als`: `STT_6_core.als` (Jun 10), `STT_6_multisource.als` (Jun 9)** — not on Mac.
- **`docs/` (2)** — `make_scope_diagram.py`, `scope_diagram.png`.
- `STAGE3_gem5/check_ld_cleanupspec.py`, `.vscode/settings.json`, `dashboard.log`.

### The genuine conflicts — edited on BOTH sides (neither is a clean superset)
| file | Mac | cafe2 | resolution |
|------|-----|-------|-----------|
| `claudelog.md` | 1868 lines, newest `2026-10-20 16:04 infra` | **2951 lines**, newest `2026-06-10 sptDiscrepancy` | **UNION merge** — Mac has an Oct entry but is MISSING June entries cafe2 has (Mac log was trimmed). Neither dominates. |
| `STATUS.md` | 149 lines, "refreshed 2026-06-07" (stale) | **358 lines, "refreshed 2026-06-10"** (newer) | **cafe2 wins** (newer + fuller), then re-refresh. |
| `claudenotes.md` | 160 lines | 241 lines | ephemeral — union or take cafe2, low stakes. |
| `dashboard.py` | 396 lines, **imports split modules** (new architecture) | 559 lines, monolithic, no split | **Mac wins** — cafe2's dashboard.py edits are superseded by the Mac rewrite. Check cafe2 didn't add a feature worth porting. |
| `check_ld_invisispec_compound.py` | unmodified | modified | **cafe2 wins** (Mac didn't touch it). |
| `check_ld_speclfb.py` | unmodified | modified | **cafe2 wins.** |
| `docs/AMULET_VS_SIMSPECT_SCOPE.md` | unmodified | modified | **cafe2 wins.** |

### Recommended reconciliation (NON-destructive)
**Union everything onto the Mac, then commit+push from Mac, then re-sync cafe2 from origin.**
1. Copy cafe2-only untracked work → Mac (bugsynth/, bug demos, 5 mdsToRead, docs/2, STAGE1 tooling,
   the 2 protected `.als` [owner sign-off], check_ld_cleanupspec.py, .vscode).
2. For the 7 shared files, apply the per-file resolution above (the only one needing care is the
   `claudelog.md` union).
3. Bring cafe2's 3 checker/doc edits (invisispec_compound, speclfb, AMULET scope) to Mac.
4. Commit the union on Mac; push to origin.
5. On cafe2: once its work is safely on Mac+origin, `git fetch && git reset --hard origin/main`
   (after confirming nothing unique is left) OR re-clone — so cafe2 pulls cleanly going forward.
   **cafe2's `/work/*` gem5 trees are outside the repo and untouched by this.**

---

## Part 2 — gem5 hooks: durability gap (Anna's question)

The gem5 builds live in **`/work/*` inside the `gem5_dev` docker container**, separate from the
repo. The hooks (instrumentation we insert) are the project's core gem5 modifications. Status:

| tree | git? | remote | hooks state | risk |
|------|------|--------|-------------|------|
| `/work/gem5-recon` (4.5G) | **NO .git** | — | raw modified files, no history | 🔴 **highest — unbacked, undiffable** |
| `/work/gem5-recon-modded` (4.5G) | **NO .git** | — | the `-modded` BTB-override build (KEY per CLAUDE.md) | 🔴 **highest — unbacked, undiffable** |
| `/work/amulet` (27G) | **NO .git** | — | SPEC + builds | 🟠 huge; hooks unbacked |
| `/work/stt` | yes | cwfletcher/stt (upstream) | **25 uncommitted** src mods | 🟠 uncommitted, diffable |
| `/work/stt-dbg` | yes | cwfletcher/stt | 26 uncommitted | 🟠 |
| `/work/gem5-spt` | yes | FPSG-UIUC/SPT (upstream) | **15 uncommitted** src mods | 🟠 uncommitted, diffable |
| `/work/amulet-repo` | yes | sith-lab/amulet | 5 changed (gen scripts) | 🟢 minor |
| `/work/sdo` | yes | cwfletcher/sdo | clean | 🟢 |

**The actual hooks (uncommitted, in the git trees — stt / gem5-spt):**
`src/cpu/o3/{commit_impl.hh, commit.hh, cpu.cc, cpu.hh, fetch.hh, iew_impl.hh, O3CPU.py}`,
`src/cpu/pred/{bpred_unit.cc, bpred_unit.hh, BranchPredictor.py}`,
`configs/{common/Options.py, example/se.py}`, + untracked `se_exp.py`, `se_slowcomm.py`
(stt also has MESI/MOESI `.sm` protocol edits).

### Why this matters
These diffs are the instrumentation every result depends on (the "reproduce EXACTLY as the config
did" rule). Right now they survive only as uncommitted/untracked files in an **ephemeral container**.
If the container is lost, the Recon hooks (no git) are **unrecoverable**.

### Recommended (needs Anna's go — don't touch gem5 beyond hooks per CLAUDE.md)
- **Capture hook patches into the simspect repo** under e.g. `gem5-hooks/<build>/` — lightweight,
  durable, reviewable, travels with the pipeline:
  - git trees (stt, stt-dbg, gem5-spt, amulet-repo): `git diff` + copy the untracked `se_*.py`.
  - non-git trees (gem5-recon, gem5-recon-modded, amulet): harder — need a pristine gem5 baseline
    to diff against, or at minimum archive the modified source files. **Decide approach with Anna.**
- Each build's hook set gets a short `.md` (what build, which upstream base commit, what the hooks do)
  per the "md as source of truth for builds" rule.

---

## Open decisions for Anna
1. Approve the **union-onto-Mac** reconciliation approach (Part 1) — or a different strategy?
2. The 2 protected `.als` only on cafe2 (`STT_6_core.als`, `STT_6_multisource.als`) — bring to Mac? (owner sign-off)
3. `claudelog.md` union — OK to merge the two by date into one append-only log?
4. gem5 hooks (Part 2): capture patches into `gem5-hooks/`? Priority on the non-git Recon builds?
5. The stale `SPT_6_oneLP 2.als` + broken `SPT_6_full.als` symlink (Part 3 / REPO_MAP) — delete/repoint?
