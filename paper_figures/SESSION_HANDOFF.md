# Paper-figures session handoff (2026-11-02): START HERE to resume

This is the single resume doc for the 2026-11-02 "paper-figs" session. A new Claude should read this file top to bottom, then `paper_figures/FIGURES.md` (all drafts + proposed captions) and `paper_figures/plans/VISUAL_LANGUAGE.md` (style rules). Everything else is linked from here.

## Rules the next Claude must follow (from Anna, this session)

- **Token thrift (Anna, 2026-11-02, important):** agents ran up huge usage. Use few agents, give them `effort: low` or `medium` unless Anna asks otherwise, and do small edits yourself. Never run more than 2 agents at once.
- **Fewer md files (Anna, 2026-11-02):** consolidate; put new notes into existing files (this file, `FIGURES.md`, `VISUAL_LANGUAGE.md`, `URGENT_TODO.md`) rather than creating new mds. Add this as a directive to the repo `CLAUDE.md` (not done yet; see the TODO list).
- **Git:** the git write lock still applies. Pushing to the paper repo needs Anna's explicit OK in the current message. Read-only git is fine. She authorized one push this session (done, below).
- **Paper text:** still read-only for Claude, EXCEPT what Anna authorized this session: swapping figure `\input` lines to new figure files, and adding `\figtodo{...}` markers (pink, color `C2185B`, defined in `bare_conf_compsoc.tex`) where she must paste captions or update text. Never change prose otherwise.
- **Captions:** previews do NOT render captions; proposed captions live in `FIGURES.md` (Captions section) and `paper_figures/drafts/captions/<name>.tex`. In the paper, each new figure file has `\caption{\figtodo{...}}` for Anna to fill.
- Never edit `.als` models or `parsexml.py` without Anna's per-change sign-off. Markdown: one line per paragraph, no hard wrapping. Final message of every turn must contain everything important (Anna doesn't scroll up).

## Where things are

- **Paper repo:** `git@github.com:anna-eaton/test-paper.git` (Overleaf-synced, root `bare_conf_compsoc.tex`, figures in `tikz/`, text in `sections/`). Claude's clone was in a session scratch dir (gone after the session); **re-clone fresh** into a new scratch dir. Claude pushed commit `a469b46`; Anna pushed more after that, so pull the latest.
- **Figure drafts:** `paper_figures/drafts/` (body `<name>.tex`, preview `_standalone_<name>.tex` + `-1.png`). Older/rejected versions: `paper_figures/drafts/old/`. Shape-design mocks: `paper_figures/drafts/design_mocks/` (`mock_A`, `mock_B`, `mock_C`, `mock_A_full`, shared `mock_macros.tex`).
- **Plans (citations + open decisions per figure):** `paper_figures/plans/` — `fig_a_execgraphsyntax.md`, `fig_b_relaxation.md`, `fig_c_interleave.md`, `fig_d_instrtable.md`, `fig_e_checkerwindow.md`, `fig_f_xmitcriteria.md`, `AUDIT_existing_figures.md` (audit of every old paper figure), `BIGFIG_FACT_AUDIT.md` (**IMPORTANT**: fact audit of the pipeline figure, 43 claims), `BIGFIG_SHAPE_DESIGN.md` (shape vocabulary + mocks A/B/C/A_full), `TRIPPEL_FIGURE_STYLE.md` (conventions from 13 Caroline Trippel papers; crops in `paper_figures/reference_papers/crops/`).
- **Concretization pass order (verified):** `wiki/design/CONCRETIZATION_PASSES.md`.
- **Decisions + TODOs:** `URGENT_TODO.md`, section "📄 Paper figures".

## What's in the paper now (test-paper `a469b46`)

- `tikz/pipeline_vertical.tex` replaces `tikz/threelayer.tex` in `sections/intro.tex` (label `fig:pipeline`).
- `tikz/instrtable_v2.tex` replaces `tikz/sptable.tex`; `tikz/resolutiontiming.tex` input commented out (its `\ref` at `pipeline.tex:46` now prints ??; marker explains). Table carries labels `tab:instrtable` and `tab:sptable`.
- `tikz/checkerwindow_v4.tex` replaces `tikz/checkerwindow.tex` (same label `fig:checkerwindow`).
- `tikz/gem5logo.pdf` (official B&W gem5 logo, CC0, from github.com/gem5/website).
- Old figure files are all kept. Paper built cleanly to 10 pages before pushing.

## Status of every figure

| Figure | Current draft | In paper? | Status / next step |
|---|---|---|---|
| Pipeline (big) | `drafts/pipeline_vertical.tex` (main) and `design_mocks/mock_A_full` (text-rich A, 252×642 pt) | yes (main version, in intro) | Anna: switch to text-rich A, fix chevrons, move to methodology (TODO 1–2) |
| Intro figure | none yet | (pipeline sits there now) | Anna wants a cleaner, better version of the ORIGINAL first figure (`tikz/threelayer.tex`) in our visual language, no info lost (TODO 2) |
| (a) Execution-graph syntax | `drafts/_standalone_execgraphsyntax` (old: boxes + r/c/t dots) | no (paper only has prose at `pipeline.tex:9`) | DECIDED: make it a vocab table (TransForm Table I style); redo was paused before producing output |
| (b) Relaxation | `drafts/_standalone_relaxation_v3` (real instance inst-047231, redundant parts red) | no: paper still has the OLD `tikz/relaxation.tex` (Fig 3) and `tikz/alloyviolation.tex` (Fig 2) | redraw in shared graph notation (v4), then swap into paper; merge old Fig 2 into it? (decision) |
| (c) Interleave | `drafts/_standalone_interleave_v3` (pre-decision) | no: paper still has OLD `tikz/interleave.tex` | DECIDED: show Stage 2 interleaving and say so; v4 redraw paused before output |
| (d) Instrumentation table | `drafts/instrtable_v2` (one column) | yes | caption + text update (markers in paper) |
| (e) Checker window | `drafts/checkerwindow_v4` (real InvisiSpec trace) | yes | window name decision; caption |
| (f) Transmission criteria table | `drafts/_standalone_xmitcriteria` (full width) | no | Anna: "kind of insane, leave it for now" |
| Results figures | none redone | old ones in `sections/results.tex` | TODO 6 (redo + Recon STL bug example) |

**Why the old relaxation/interleave figures are still in the paper:** only the three finished figures (pipeline, d, e) were pushed. The (a)/(b)/(c) redo agent was paused for usage before it produced files, so the old figures were not replaced.

## TODO list (everything Anna asked for that is not done), in priority order

1. **Pipeline figure → text-rich A.** Use `design_mocks/mock_A_full` as the pipeline figure. Make the Stage 2 chevrons less subtle/weird (they look bad: stronger outline/shape, clearer arrow form). Keep the old version (don't delete `drafts/pipeline_vertical.tex` or the mock). Also apply the agent's optional trims only if Anna agrees (drop italic list headers; move enumeration notes to strip captions; thinner stripes → ~570 pt). Confirm with Anna that the pin slab may move to the top of the Stage 1.5 stack.
2. **Move the big pipeline figure from the intro to the methodology section** (`sections/methodology.tex` or the pipeline section; check which is `\input`) and put a **new intro figure** there: a cleaner, better version of the original first figure (`tikz/threelayer.tex`, Fig 1) in our visual language, losing no information. (Interpretation of Anna's words; confirm.) Needs a push with Anna's OK, `\input` swaps + `\figtodo` markers only.
3. **3-pronged DSL in Stage 1:** show the defense's three DSL clauses inside Stage 1 clause 3 (gray sub-rows): speculation contract (what is speculative), protection set (what is protected and how it propagates), leakage/transmitter function (what can transmit) — per repo `CLAUDE.md` "Alloy model structure" section. Worst case, put it by the "Defense specification / manual translation to DSL" source. Apply to whichever pipeline version is current, re-push.
4. **Write up the visual language:** update `plans/VISUAL_LANGUAGE.md` into a proper writeup: the shape vocabulary from `BIGFIG_SHAPE_DESIGN.md` (shape = type, gray = defense-specific only, text = name; rounded stage blobs; slabs for constraints; stadium for the solver; chevrons for ordered passes; card stacks for data sets with multiplicity under them; gem5 container + harness ring; single bold bug icon), left sources-of-truth column with a small "Defense sources of truth" header, 8pt body + 7pt italic qualifiers, full 252pt column, captions outside previews, Trippel conventions (flags on labels, lowercase i0, labelled edges, legend in caption). It's out of date in 4 places (no-left-column, sharp-corners-only, 7pt-only, legend top right).
5. **Middle figures:** (a) vocab table; (b) relaxation v4 and (c) interleave v4 (Stage 2 round; fix reg0→reg1) in one shared graph notation; then swap (b)/(c) into the paper (and decide on old Fig 2 `alloyviolation`). Recommendation already given: one graph is enough — the relaxation figure's black backbone is the base form, red = what loosening adds.
6. **Results figures:** redo them in our visual language (current ones use colors, 5pt text, overflow; see `AUDIT_existing_figures.md`), include the Recon results, and **show an example of the novel Recon STL bug we found** (store-to-load forwarding bypass on Recon; `specs/defense_units.json` unit 5 "STL/SLF store-forward bypass found"; see `wiki/design/STL_SPECULATION.md`, `wiki/results/reconresults.md`) in the same visual language as the checker window / graph figures, showing the bug mechanism. Check which numbers predate the 2026-10-30 harness fix (STATUS.md says earlier campaigns are suspect) and mark them. Bug table v2 with Recon rows; Recon OTB figure restyled.
7. **Suggested paper text → bottom of `FIGURES.md`:** add a "Suggested paper text" section collecting: `plans/fig_d_instrtable.md` "Suggested paper text" paragraph; `fig_a` prose trim (`pipeline.tex:9`); `fig_b` and `fig_c` caption fixes (reg0→reg1); `fig_d` and `fig_f` "paper text disagrees with code" lists (e.g. `pipeline.tex:46,48,55,63,70,73,83,86,90`); the DSL note (say "DSL" in the paper).
8. **Flag `plans/BIGFIG_FACT_AUDIT.md` as IMPORTANT in `STATUS.md`** (paper-figures section) and keep it as the fact-audit doc. Anna will go through D3, D4, D5, D7, D8 later.
9. **Add the "use fewer md files; consolidate when possible" directive** to the repo `CLAUDE.md` (Anna asked for it).
10. **Criterion JSONs for STT, Recon, SPT** (`specs/leakage/stt.json`, `recon.json`, `spt.json`): encode exactly what `check_ld.py` / `check_br.py` / `check_other.py` decide today (same schema as `invisispec.json`), with known quirks as notes (data-obtained check not window-bound, `check_ld.py:56-75`; Recon gate bug). Explain to Anna how a criterion JSON reaches a run today (run config → `pipeline.py:296-314` → checker) and propose (don't implement) one JSON-driven path for all checkers.
11. **Glossary** of terms the paper defines (into `FIGURES.md` or this file, not a new md), incl. a precise **window name**: the paper says "committed window" = `(lc_retire, fnc_retire)` + guarding branches still unresolved (`pipeline.tex:57`); figures use "violation"/"unresolved"/"speculative". Give options + recommendation. Decided vocab so far: "transmission mechanism", "SimSpect DSL", "Inspector", "Kodkod model finder", "bounded exhaustive" (Stage 1) / "non-exhaustive" (Stage 1.5), lowercase i0.
12. **Defenses out of scope** (low-effort agent or by hand): a paragraph on which defenses are out of scope because there's no gem5 build or they're irrelevant, plus proposed paper text. Put it in `FIGURES.md` (Suggested paper text) rather than a new md. Defense list (from `specs/defense_units.json`, marked "first pass, confirm with Anna"): run = STT (own build `/work/stt`), STT on Recon build, SPT-Fence, SpecLFB / InvisiSpec / CleanupSpec (AMuLeT builds; InvisiSpec and CleanupSpec marked out of scope, collateral channels), Recon; to run = Recon OTB, STT on SPT sub-implementation, SPT variants, Delay, DoM.
13. **Stage 1.5 as a real pipeline stage** (Anna will do the code soon): wire `STAGE1_alloy/stage_pipeline.py` into `pipeline.py` / `testsetgen.py` / Makefile, make per-graph runs parallel, run a staged campaign; Stage 1 must reach UNSAT at the bound for "bounded exhaustive" to be true.
14. Housekeeping: Anna to run `make sync`; and `! git rm --cached paper_figures/reference_papers/*/*.pdf` (PDFs are now gitignored but were committed earlier).

## Open decisions for Anna (also in `URGENT_TODO.md`)

- Fact audit D3 (clauses 1–2 differ across models: align vs qualify), D4 (Stage 1 minimality RO+RI vs RI-only), D5 (footprint defenses reuse STT_6: say so vs per-defense models), D7 (shade "build + config"), D8 ("non-invasive" wording).
- Window name; "transmission mechanism" everywhere (decided) — apply to fig (e), which still says "criterion".
- Fig (e): only the transmitter's footprint counts, or any squashed load (today: any)?
- Fig (f): JSON criteria vs the older checkers that produced the numbers; checker finding that the data-obtained gate isn't window-bound; no reported result used the JSON criteria.
- Fig (b): merge old Fig 2; OK to use stale-testset instance inst-047231.
- Model skeleton: `rf_from_most_recent_writer` missing from Recon_6, SPT_6*, pincommit, modified_protset.
- Probe array comment wrong (`parsexml.py:2079`): fix comment vs change stride.
