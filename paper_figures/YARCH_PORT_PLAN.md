# YArch → SimSpect-S&P-2027 Porting Plan

Source (vetted): `/tests/YArch-26-SimSpect-new/` (ACM sigplan, ~4pp mini-paper, Caroline-reviewed).
Target (new): `/tests/SimSpect-S-P-2027/` (IEEEtran compsoc, full paper with real results).

**Big picture.** The new paper is *ahead* on results (real bug table, VP↔squash race, efficiency-vs-AMuLeT,
targeting %, gem5-validated leaks) and on the technical pipeline (model.tex + pipeline.tex + 6 tikz figs).
What it is *behind* on is exactly what the YArch version had vetted: tight, reviewer-approved **prose** in the
intro / background / related-work, a clean **abstract**, the **pipeline.png** overview figure, and the
**examplefigure.png** running-STT walkthrough. The job is mostly to port *framing and prose*, not data.
Do NOT port YArch's results/eval text — it is stale (smaller, pre-bug-table).

---

## TIER 1 — Port (high value, low risk)

### 1.1 The pipeline overview figure (`images/pipeline.png`)
- **Status in new paper:** the PNG is already copied into `/tests/SimSpect-S-P-2027/images/pipeline.png` but is
  **never `\includegraphics`'d** anywhere. This is the single highest-leverage missing asset.
- It is the 3-stage block diagram (Stage 1 Alloy: exec model + 3 contracts + minimality → n abstract tests;
  Stage 2 Python/LLVM/Java: 4 passes; Stage 3 C++/python: instrument + run + inspect → leak?). It maps 1:1 onto
  the new paper's `methodology.tex`→`model.tex`+`pipeline.tex` structure.
- **Action:** add it as a top-of-section `figure*` at the start of `sections/methodology.tex` (or intro), labeled
  `fig:pipeline`, and reference it from the pipeline-section intro (`pipeline.tex` L2) and the intro's
  "(1) formal language (2) test generator (3) validator harness" sentence (`intro.tex` L24). It visually anchors
  the 3 deliverables the prose already promises.

### 1.2 The running-STT example figure (`images/examplefigure.png`)
- The 4-panel STT walkthrough: (1) contract specification, (2) model enumeration (ddi+rf graph), (3) abstract
  litmus test, (4) specify instructions / interleave — built around the "Known bug in STT Recon" snippet.
- **Status in new paper:** PNG copied in; `model.tex` has it **commented out** (two dead `\includegraphics`
  blocks at L18–32). Both `intro.tex` (L24 `\anna{stt running mini example figure 1}`) and `discussion.tex`
  (L29) explicitly call for exactly this figure.
- **Action:** un-comment and place it. It satisfies three outstanding `\anna{}`/`\todo` requests for a running
  example. Caveat: the new paper now has *native tikz* versions of pieces of this (`tikz/alloyviolation.tex`,
  `tikz/interleave.tex`, `tikz/relaxation.tex`). Decide: either (a) use examplefigure.png as the single
  end-to-end "Figure 1" running example and let the tikz figs carry the per-concept detail, or (b) rebuild the
  4-panel walkthrough in tikz to match house style. Recommend (a) for now (it's vetted and complete); flag for
  redraw later. **Do not** duplicate the same STT load→load example in both png and tikz without cross-ref.

### 1.3 Abstract — port the *opening*, keep the new *results sentence*
- The two abstracts are nearly identical for the first ~5 sentences (same vetted text). The **new** abstract adds
  the crucial results sentence ("replicate all in-scope previously known bugs ... new bugs in both STT and SPT ...
  15% of the test count of prior work"). **Keep the new one** — it is strictly better.
- **Action:** no port needed; the YArch abstract is fully subsumed. Just confirm the new abstract's "15%" /
  "x known bugs" numbers match the results section (`results.tex` says 17% targeting, SpecLFB #6 vs #39 = ~15%).
  Minor: YArch abstract has a slightly cleaner final clause ("combining into a pipeline for rigorous defense
  validation and iteration") — already present in new. Nothing to do.

### 1.4 Intro paragraph 2 — the "performance-security tradeoff → bugs void the prototype" argument
- YArch `intro.tex` L8–9 states this crisply with the **right citations** and the AMuLeT cite:
  "subtle security bugs may lead to underestimates of defense performance overhead relative to an insecure
  baseline, voiding a prototype's usefulness for predicting viability~\cite{amulet}."
- New `intro.tex` L6 says the same thing but cites `\cite{nickscommittoSTT}` and has a dangling `\cite{?}`.
- **Action:** the *argument* is in both; port YArch's cleaner phrasing + the `\cite{amulet}` anchor, and fix the
  broken `\cite{?}` / `\cite{nickscommittoSTT}` placeholders. Low effort, removes two visible holes.

---

## TIER 2 — Port the vetted prose where the new paper is rougher

### 2.1 Background — the AMuLeT subsection (`background.tex §HSCD litmus testing`)
- The two `background.tex` files are *byte-identical* in the first two subsections. BUT the YArch
  `background-motivation.tex` is a **more developed, Caroline-passed** version of the same material — it has the
  scoped "Spectre defenses vary along three axes" sentence (which directly sets up the 3-component formal model),
  and the cleaned STT/NDA/recon/spt framing.
- **Action:** the new `background.tex` is the *older, weaker* of the two. Port the **"Spectre defenses vary along
  three axes: which architectural state is protected, which transmitter-operand pairs are unsafe, and what types
  of execution initiate speculation"** sentence from YArch `background-motivation.tex` L21 into the new
  background — it is the explicit bridge to `model.tex`'s three components (leakage contract / execution
  contract / protection set) and the new paper currently lacks that bridge. This also addresses the technical
  review's "three-component sufficiency claim reads as fiat" gap.

### 2.2 Related work — port the WHOLE thing
- New `sections/related.tex` is **empty (0 bytes)** and `bare_conf_compsoc.tex` `\input`s it. The bibliography is
  also still the IEEEtran skeleton stub (one `IEEEhowto:kopka` bibitem).
- YArch `related-work.tex` has a vetted, organized related-work section in **three labeled threads**:
  (1) Litmus Test Synthesis and Testing (memsynth, memalloy, lcms, perple, transform, lustig, MCMutants);
  (2) Validation/Verification of HSCDs (checkmate, contractshadow, leave, blackbox, catspectre, SynthLC/rtl2upath,
  revizor, pensieve, lcms); (3) Simulator Validation (amulet — the one direct competitor).
- **Action:** port YArch `related-work.tex` near-wholesale into the empty new `related.tex`. Strip the inline
  `\caroline{}` review comments and the commented-out alt drafts. This is the largest single gap in the new paper.
- **Note:** the new paper's `discussion.tex` L24–27 also has a strong AMuLeT-limitations paragraph (5 numbered
  limitations). That belongs in related work / a "comparison to AMuLeT" para — reconcile so AMuLeT's critique
  isn't split between `related.tex` and `discussion.tex`.

### 2.3 Methodology — the violation definition + ddi/rf figure prose
- YArch `methodology.tex` L42–49 has the **vetted** Execution-Syntax + Test-Generation(Alloy) + violation-
  definition prose. The new `pipeline.tex` L7–18 already contains essentially this same (ported-forward) text plus
  the new tikz `alloyviolation` figure — so this is mostly **already done**. The technical review grades the new
  violation-def paragraph A−.
- **Action:** minimal. Confirm the new paper kept YArch's exact violation sentence ("a data-dependence path from a
  protection-set state element as updated by the most recently committed instruction, to a leaked operand of a
  transmitter, where the transmitter is in the leakage contract and speculative per the execution contract") —
  it did (`pipeline.tex` L10). Nothing to port; this is the one place the new paper already absorbed YArch fully.

---

## TIER 3 — Concepts/framing in YArch worth surfacing (not verbatim prose)

### 3.1 The three numbered deliverables, stated identically in intro and methodology
- YArch `intro.tex` L14 lists (1) formal language (2) directed test generator (3) validator harness, and the
  methodology subsection titles mirror them. New `intro.tex` L24 has the same three but the section titles in
  `model.tex`/`pipeline.tex` don't visibly mirror them (Caroline flagged this exact mismatch in YArch).
- **Action:** make the new paper's section/subsection headings echo the three deliverables, and tie `fig:pipeline`
  (Tier 1.1) to them. Cheap structural coherence win the vetted version implicitly had.

### 3.2 "directed / targeted vs random" thesis
- YArch states the core contribution-vs-AMuLeT contrast tightly: AMuLeT "attempts to validate high-level security
  properties, and has no ability to do directed testing for leakage" (`background.tex` L6) and "does not exploit
  the simulator's white box nature and does not target tests to contain leakage ingredients" (`related-work.tex`
  L10). The new paper makes this point but more diffusely (across intro, results §targeting, discussion).
- **Action:** lift YArch's one-liners as the topic sentences for the new paper's targeting argument
  (`results.tex` §Test targeting and `discussion.tex` related-work para). They are the crisp framing the
  17%/100% bar chart (`fig:target`) needs as a verbal anchor.

### 3.3 Concretization "heuristic vs comprehensive" framing
- YArch `methodology.tex` L26 has the clean one-sentence statement: "comprehensive across types of leakage
  paths ... but heuristic-based in the concretization phase." The new `pipeline.tex` L2 buries this in a 12-line
  run-on (technical review grades C+, "says tunable three times").
- **Action:** replace the new run-on opener with YArch's tighter sentence as the lead, then keep the new paper's
  comprehensive/semi/fixed taxonomy. (This overlaps with the technical-review's own recommendation.)

---

## DO NOT PORT (stale / superseded in YArch)

1. **YArch `preliminary-results.tex`** — entirely superseded. It says "we *will* run" / "currently implementing
   gem5 tuning" / lists STT+SPT+InvisiSpec+CleanupSpec+SpecLFB as future work. The new `results.tex` has the
   actual bug table (`tab:bugs`), the VP↔squash race writeup + trace/schedule figures, efficiency bars, and
   gem5-validated counts. Porting any YArch results prose would *regress* the paper. Ignore it entirely.

2. **YArch abstract's results-free version** — the new abstract already has the results sentence; YArch's is the
   older subset. (Tier 1.3.)

3. **YArch ACM sigplan template scaffolding** (`paper.tex` preamble, `acmart.cls`, ACM-Reference-Format.bst,
   sample-base.bib) — the new paper is **IEEEtran compsoc**. Do not port LaTeX class/preamble. The
   `\newcommand{\toolname}`, `\anna/\caroline/\todo` macros are already in the new `bare_conf_compsoc.tex`.
   (Bibliography *entries* in `sample-base.bib` are still useful as a source to populate the new paper's stub
   `thebibliography` — port citation keys/entries, not the bst.)

4. **YArch's tikz `fig:ddi-rf`** (inline in `methodology.tex` L56–109) — the new paper already has a cleaner,
   reworked equivalent in `tikz/alloyviolation.tex`. Don't port the old one.

5. **Any "validation not verification / early-stage" hedging** is already present in both; no action.

6. **The 3-level "security property → defense spec → implementation" figure** that `intro.tex` L26 and
   `discussion.tex` L29 `\anna{}` ask for does **not exist** in YArch either — it is net-new work, not a port.
   Flag as new-figure TODO, out of scope for this porting pass.

---

## CHECKLIST (ordered by leverage)

1. [ ] `\includegraphics` `images/pipeline.png` as `fig:pipeline` in methodology/intro; reference it. (1.1)
2. [ ] Fill empty `sections/related.tex` from YArch `related-work.tex` (strip review comments). (2.2)
3. [ ] Un-comment / place `images/examplefigure.png` as the running STT example (Fig 1). (1.2)
4. [ ] Port "Spectre defenses vary along three axes" bridge sentence into `background.tex`. (2.1)
5. [ ] Fix intro `\cite{?}`/`\cite{nickscommittoSTT}` using YArch's `\cite{amulet}` + tradeoff phrasing. (1.4)
6. [ ] Replace `pipeline.tex` L2 run-on opener with YArch's "comprehensive over leakage / heuristic over
       concretization" sentence. (3.3)
7. [ ] Make section headings mirror the three deliverables + tie to fig:pipeline. (3.1)
8. [ ] Reconcile AMuLeT critique between `related.tex` and `discussion.tex`; use YArch's "no directed testing /
       doesn't exploit white box" topic sentences. (2.3, 3.2)
9. [ ] Port reusable bib entries from `sample-base.bib` to populate the IEEEtran bibliography stub.
10. [ ] (Out of port scope, flag) new 3-level sec-property figure; redraw examplefigure in tikz if house style
        requires. (1.2 caveat, DO-NOT-PORT #6)

Note: the new paper's own `technical-review.md` independently lists complementary prose/motivation gaps
(execution-not-program/LILT framing from `oldtechnicaldetails.tex`, relaxation qualifiers, hook list). Those are
*internal* to the new paper's drafts, not YArch ports — keep that workstream separate but coordinate (esp. the
LILT framing, which YArch's `methodology.tex` does NOT have, so it must come from `oldtechnicaldetails.tex`).
