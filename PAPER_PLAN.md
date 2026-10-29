# SimSpect paper plan: from current draft to a submittable ISCA 2027 paper

*Written 2026-10-27 by a Claude planning session (read-only on code, models, git, and .tex). This file is the plan only. It contains no paper prose. Every factual claim about the project cites a repo path. Where something is unverified it says so.*

**Venue changed: ISCA 2027 (not S&P '27).** The draft of record is `/Users/annaeaton/Downloads/SimSpect_ISCA_2027.pdf` (11 pages, compiled 2026-10-27 13:47).

---

## 0. Read this first: the five facts that shape everything

1. **The deadline is 20 days away.** The official ISCA 2027 CFP (https://iscaconf.org/isca2027/submit/callforpapers.php, fetched 2026-10-27) gives **abstract registration Nov 9, 2026** and **full paper Nov 16, 2026**, both 11:59 PM AoE. Rebuttal runs Feb 16 to Mar 8, 2027, and decisions come out Mar 26, 2027. The CFP says **"title, abstract, and author list must be final at abstract registration"**. That answers Anna's open note in `STATUS.md` ("Figure out if the authors have to be fixed by the time I submit the abstract — if so, do Nick + Prof. Mitchell go on there"): yes, authorship has to be settled by **Nov 9**.
2. **The ISCA 2027 page limit and template are not published yet.** The CFP says page-limit and anonymity instructions "will be published separately". Plan against the ISCA 2026 rules (https://iscaconf.org/isca2026/submit/guidelines.php) and re-check the 2027 guidelines page before Phase 4. The 2026 rules were: **11 pages excluding references**, with appendices counted inside the 11. Two columns, 10 pt Times, US Letter, the IEEE conference template, page numbers, and a confidentiality banner. Double-blind: no author names, clean PDF metadata, own work cited in the third person, anonymized artifact links. A paper already online needs a different title. A paper **previously rejected at ISCA, HPCA, ASPLOS, MICRO "or any other venue"** needs a separate change note of about one page. Nothing in the repo or in Quail mentions ISCA 2027 (searched `simspect/` and `quail/`).
3. **The "current Overleaf" PDF matches the June 10 S&P PDF word for word.** `pdftotext` of `SimSpect_ISCA_2027.pdf` and `SimSpect_S_P_2027__correct_format_.pdf` (created 2026-06-10) gives identical text in both `-layout` and `-raw` modes. Only the compile date differs. So the draft has had **no content edits since June 10**. Everything in the repo since then (Oct 20–26: the minimality, two-stage, and reach-UNSAT analyses, and the June 8–10 AMuLeT reproductions) is not in the paper. The title still says "(draft do not share)" and there is still an Acknowledgments stub. Both break double-blind.
4. **The comprehensiveness claim no longer holds as written.** The draft says that enumeration "will generate all possible leakage path forms" and that "coverage is complete up to the instruction bound" (§4, §4.4). The repo now shows three things. Enumeration **never reached UNSAT** for STT or SPT; it always stopped at the 100k cap (`TODO.md` "Reach UNSAT", `wiki/findings/mdsToRead/REACH_UNSAT_ENUMERATION.md`). The 100k tests collapse to **47 leak-cores, with 98% a 2-instruction src→xmit core** (`claudelog.md` 2026-06-09 "enumeration over-specifies", `wiki/findings/mdsToRead/ENUMERATION_OVERSPECIFICATION.md`). And there are only **10 structural dataflow cores** (same entry, addendum 3). This is the biggest writing risk in the paper. It has to be either re-scoped (writing only) or backed by a new exhaustive-core run (an experiment, owner-gated). See Gap G1.
5. **The bug claims need a falsification protocol and a negative control on the page.** All three internal reviews of the YArch mini-paper came back Weak Reject, and their shared bar was "one discrepancy carried end-to-end through a falsification protocol + a negative control" (`paper_figures/reviews/DISCUSSION_AND_FINAL.md`). Note that these reviewers were simulated by Claude agents (`claudenotes.md` 2026-06-06 "figures"), not real PC reviews. The evidence for this exists in the repo: the disqualifier ordering in `CLAUDE.md` "Systematic hit bucketing", stock-timing 0 leaks, the fnc on/off control, the Unsafe-scheme byte-identical control, and the Fence control (`wiki/results/PAPER_RESULTS.md` §2.2, §6, §7). The current draft says almost none of it. Writing it up is pure writing and high-value.

---

## 1. Where the numbers live (provenance map)

**Important:** `results/` in the local repo is **empty**. Results are gitignored and live on the cafe2 container under `/tests/simspect/results/` and `/work/...`. Locally the numbers survive only as values baked into `paper_figures/make_paper_figures.py`, whose header comments give the container path for each number. They also appear in the wiki docs below. Re-verify any number on cafe2 before final submission (Phase 5).

| Claim / number | Value in draft | Local source | Container source (per the script header and wiki) |
|---|---|---|---|
| STT VP↔squash race instances | "23,966 race instances" | `make_paper_figures.py` F1 block; `wiki/results/PAPER_RESULTS.md` §2.2 | `results/stt_slowcomm_full*/diagnostics/buckets/summary.json` = {stt_vp_squash_race: **19,845**, check_ld_not_real_access: 21, NEW: **4,122**} |
| STT at stock timing | "0 at stock" | `PAPER_RESULTS.md` §2.2; `wiki/results/results.md` | `results/experiments/slow_comm_squash1/sample_stock` (0/600 both modes); STT_6 sttbuild 0 across 11,652 ld + 4,348 br_x per mode |
| Fragility vs commitToIEWDelay | 0/20/41/42 not-taken; 0/0/2/2 taken (per 300) | `PAPER_RESULTS.md` §7; F5 block | `results/experiments/paper_fragility/{frag,fence}_d*/summary.json` |
| Stall sweeps s_U / s_R / fnc | s_U {0:27, 50:0, …}; s_R {0:27, 8:22, 64:22}; fnc {0:16, 150:27, 300:27} (per 200) | `PAPER_RESULTS.md` §6; F4 block | `results/experiments/paper_stalls/stt_*/summary.json` |
| SpecLFB UV6 | 68/300; first detection at test #6; 23% density | `PAPER_RESULTS.md` §4, §8 | `results/STT_6_speclfb` |
| AMuLeT first detection / density | #39; 4/120 = 3.3% | `PAPER_RESULTS.md` §8 | `results/STT_6_speclfb/amulet_compare/fuzz.log` |
| gem5 cost per test | 0.092 vs 0.057 s | `PAPER_RESULTS.md` §8 | `/tmp/time_gem5_only.py` (**in /tmp, may be gone**) |
| AMuLeT corpus targeting | 14% LL, 5% BRX, 17% either (of 500) | `PAPER_RESULTS.md` §5; F3 block | `/work/amulet-repo/stt_corpus_gadgets.json`, `analyze_gadgets.py` |
| SPT-Fence attribution | 67,297 const-addr + 5,503 rf-clobber + 358 + 4,397 NEW (~983 race-shaped) | `PAPER_RESULTS.md` §2.3; F1 block | `results/spt_slowcomm_fence*/diagnostics/buckets/summary.json` |
| Recon SLF | 1 real of 184 ld hits (`inst-014912`) | `wiki/findings/bug/recon_SLF_stlf_bypass/NOTE.md` | `results/Recon_6__20260602_122016/diagnostics/buckets/summary.json` |
| Representative race trace | `inst-047231` ticks 2930000…2947500 | `wiki/findings/bug/stt_slowcomm_vp_squash_race/` (BUG_EXPLAINER.md, example_inst-047231.md, .s/.xml/.ann.json, diag script) | same |
| Enumeration diversity | 47 leak-cores, 98% one 2-instr core; 10 structural cores | `wiki/findings/mdsToRead/ENUMERATION_OVERSPECIFICATION.md`; `claudelog.md` 2026-06-09 | `testsets/STT_6/xml/` (100k) |
| Two-stage exactness | in-use STT_6 == RI-only core ⊕ interleave, 80 = 80 at exactly-3 | `wiki/findings/mdsToRead/TWO_STAGE_STT_FEASIBILITY.md`; `claudelog.md` 2026-10-26 | — |
| STT branch defense sound | 42/42 live gadgets SOUND under value-flip NI audit | `claudenotes.md` 2026-06-09 13:05; `bugsynth/CHECK_BR_NI.md` (container) | `bugsynth/` |
| AMuLeT bug reproductions | 7 demonstrated (UV1, UV6, KV1, KV3, UV4, unXpec, UV2) + 2 why-nots (UV3, UV5) | `wiki/findings/mdsToRead/AMULET_LOAD_DEFENSES_PROJECT_LOG.md`; `AMULET_BUGS_DETECTION_ACCOUNTING.md` | per-demo dirs (`wiki/findings/bug/{uv2,kv1,kv3}_demo/`, `results/STT_6_cleanupspec_residue/*`) |
| Recon OTB | 30/30 forced gadgets leak | `STATUS.md` §bugsynth; `bugsynth/RECON_OLDEST_TAINT_BUG.md` (container) | `bugsynth/otb_check.py` |
| Leakage contract (STT) | Loads.inaddr + Branchxs.inreg; no stores | `PAPER_RESULTS.md` §2.2 cites `STT_6.als:328` (read-only; do not edit) | — |
| Test corpus size | 100k (`alloy.max_instances`) | `PAPER_RESULTS.md` §5 | run configs |
| Methods text sources | — | `wiki/design/METHODS_LEAKAGE_KNOBS.md`, `METHODS_CONCRETIZATION.md`, `METHODS_INSTRUMENTATION.md`, `wiki/design/DESIGN.md`, `wiki/design/docs/COMPOUND_TRANSMISSION_CRITERION.md`, `wiki/design/docs/AMULET_VS_SIMSPECT_SCOPE.md` | — |
| gem5 builds / hooks | — | `specs/gem5_builds.json`, `specs/gem5_hooks.json`, `gem5-hooks/README.md`, `wiki/design/MODELS_AND_BUILDS.md` | `/work/*` |

---

## 2. Section by section

Proposed ISCA structure, with a page budget for 11 pages excluding references. The draft's current numbering is in brackets.

### §1 Introduction [draft §1] (target 1.25 pp)
- **(a) State: rough.** Full paragraphs exist, but they carry `[Anna: stt running mini example figure 1]`, two `[?]` / `[todo: cite]` citations, and results numbers that don't match the repo. "15% percent of AMuLeT's randomly synthesized tests contain the basic components" is wrong: the repo figure is 17% (`PAPER_RESULTS.md` §5). The 15% figure is 6/39 tests-to-detection, which is a different claim. It says "seven" defenses while YArch says "eight". Fig. 1 (three levels of assurance) is done. The framing is security-venue ("HSCA" jargon), not ISCA.
- **(b) Must say:** an architecture-audience hook (simulator-prototyped defenses carry security bugs that invalidate the published overhead; cite AMuLeT and the Mosier STT fix). The gap: there's no defense-specific, targeted validation. The 3 contributions are spec language, directed generator, and gem5 harness plus triage protocol. Then the headline results, with numbers that match §7 exactly: the VP↔squash race in STT (19,845 confirmed, 0 at stock) and the claim about SPT, which **depends on Gap G4**. Next, SpecLFB UV6 found at test #6 vs #39 (6.5×), the 17% vs 100% targeting, and the falsification protocol. Finally, an honest scoping sentence on what "comprehensive" means (Gap G1).
- **(c) Tasks:**
- [ ] Rewrite the contributions paragraph as 3 numbered deliverables whose names match the §3/§4/§5 headings (source: `paper_figures/YARCH_PORT_PLAN.md` Tier 3.1). (30 min)
- [ ] Replace the AMuLeT and "bugs void prototypes" paragraph with YArch's vetted phrasing plus `\cite{amulet}` (YArch PDF p.1, `YARCH_PORT_PLAN.md` 1.4). Fix both `[?]`. (20 min)
- [ ] Write the results-summary paragraph from the §1 provenance table. Fix 15% → 17% for targeting and keep 6.5× for tests-to-detection. (30 min) [blocked on G1 and G4 wording]
- [ ] Write the "scope of comprehensive" sentence, once Anna chooses the G1 option. (15 min) [DECISION D1]
- [ ] Remove the `[Anna: …]` macro and make the defense count consistent (D7). (15 min)
- [ ] Final pass for the ISCA audience: define HSCA/HSCD once or drop the acronyms, and add one sentence on why architects care (the overhead numbers are wrong). (30 min)

### §2 Background and motivating example [draft §2] (target 0.75 pp)
- **(a) State: rough.** §2.1 HSCDs, §2.2 HSCD litmus testing, and §2.3 axiomatic models are paragraphs with `[?]` cites. There's no running example. §2.2 duplicates related work.
- **(b) Must say:** the three axes (protected state, transmitter-operand pairs, speculation sources), using the YArch bridge sentence (YArch PDF §2, `YARCH_PORT_PLAN.md` 2.1). Then STT and SPT in two sentences each (needed for §7), MCM litmus synthesis and minimality (Lustig), and a running STT example. The example's source is `images/examplefigure.png` in the Overleaf (it exists in `/Users/annaeaton/Downloads/S_P__27_SimSpect__old_format_/images/`).
- **(c) Tasks:**
- [ ] Insert the "three axes" bridge sentence and cut §2.2 down to 2 sentences that point to §9. (20 min)
- [ ] Add 2 sentences on SPT (data-taint/DDIFT, untaint at the visibility point) using `claudenotes.md` 2026-06-03 11:40 (SPT untaint audit) and the SPT paper [5]. (25 min)
- [ ] Fix every `[?]` in §2 using `bib.bib` keys from the old_format folder. (20 min)
- [ ] Decide on the running example (D6), then place `examplefigure.png` or a TikZ redraw and write 1 paragraph walking through it. (45 min)

### §3 Specifying a defense [draft §3 "Formal model"] (target 1 pp)
- **(a) State: outline / rough.** There are 3 numbered definitions and an STT example. "§3.2 Execution contracts in practice" and "Scope of defenses" are empty headings in `formalmodel.tex`. The defense table in `casestudies.tex` has 2 rows and isn't included. **No artifact in the repo backs "seven defenses expressed".** Only STT, SPT, and Recon have models (`STAGE1_alloy/models/`). `documentation/docs/defenses.md` lists 9 defenses, but its "SimSpect defense specifications" section is empty.
- **(b) Must say:** the three components (leakage contract, execution contract, protection set plus update rule). The STT instance must match `STT_6.als` (loads' inaddr plus branchx inreg, no store transmitter: `PAPER_RESULTS.md` §2.2). It also needs a table expressing N defenses in the language, where each row is either modeled in Alloy or specified on paper only (mark which). Sources for the rows: `documentation/docs/defenses.md` links and `casestudies.tex` rows. The section also has to say what the language can't express: implicit flow (no cdep edge), store transmitters, and timing/squash-signal channels (`STATUS.md` §bugsynth "future directions", `ENUMERATION_OVERSPECIFICATION.md` fix 5).
- **(c) Tasks:**
- [ ] Reconcile the STT example with `STT_6.als` leakage_function (read the model; do not edit it). The draft says "(branch, condition)", while the YArch version adds "(xmit-reg-op, inaddr)" and "except memory loaded by committed loads". Pick the one that matches the model. (20 min)
- [ ] Build the defense-spec table: one row each for STT, SPT, Recon from their `.als` files. (45 min)
- [ ] Add rows for NDA, SpecShield, DoM, SDO, Doppelganger, Protean from each paper (real sources; `documentation/docs/defenses.md` has the links). About 2 rows per task. (3 × 45 min) [DECISION D7: how many rows]
- [ ] Write 1 paragraph on expressiveness limits, with the 3 inexpressible channels and citations to the repo evidence above. (30 min)
- [ ] Delete the empty subsection headings. (5 min)

### §4 Directed test generation [draft §4.1] (target 1.5 pp)
- **(a) State: near done as prose, wrong in substance.** Execution syntax, the violation definition, Alloy, the relaxations RI/RO/RS/RC/RR, and overlapping interleaving are all written, with Figs 2–5. There are problems. "Figure ??" (the relaxation ref) is broken. The run-on opener, graded C+ according to `YARCH_PORT_PLAN.md` 3.3, says "tunable" three times. The draft says all five relaxations are used. In practice in-use STT_6 uses RR+RC+RS only and has no RI/RO (`claudelog.md` 2026-06-10 staged-enum: "STT_6 has no RI/RO minimality"). Fig. 4's caption describes the OTB taint-tracking leak, which the results no longer mention.
- **(b) Must say:** the execution graph, the violation as a dataflow **path** (not a cycle; `wiki/results/TO_WRITEUP_PAPER.md` item 1), and which relaxations are actually active in the corpus that produced the results. It must state what is complete and what isn't: the honest version is "complete over minimal leak cores at the bound" only if G1 is run, otherwise "targeted, capped, simplest-first". Interleaving as the way to get multi-source shapes (OTB): `CLAUDE.md` "Chain interleaving", `URGENT_TODO.md` #1 option A. The corpus numbers: 100k cap, concretized count per mode, and core diversity.
- **(c) Tasks:**
- [ ] Replace the §4 opener with YArch's sentence "comprehensive across types of leakage paths… heuristic in concretization" plus the comprehensive / semi-enumerated / fixed taxonomy. (20 min)
- [ ] Fix the relaxation list so it matches what was run. Check `gen_useful_litmus` in `STT_6.als` and `SPT_6_oneLP.als` (read-only) against `wiki/design/MODELS_AND_BUILDS.md`. (30 min)
- [ ] Write 1 paragraph defining a minimal leak witness (path, not cycle) and contrasting it with MCM minimal cycles, using `TO_WRITEUP_PAPER.md` item 1 and `SPT_MINIMALITY_MCM.md`. MCM suite sizes must come from Herding Cats or diy sources read this session, otherwise drop the number. (45 min)
- [ ] Write the coverage paragraph, either the G1 re-scoped version or the G1 result. (30 min) [DECISION D1 / EXP-1]
- [ ] Rewrite the Fig. 4 caption so it doesn't depend on the OTB result unless D3 keeps Recon. (15 min)
- [ ] Fix "Figure ??". (5 min)

### §5 Concretization and the gem5 harness [draft §4.2–4.4] (target 1.5 pp; currently about 2.5 pp, so it has to shrink)
- **(a) State: near done, too long.** Instruction choice, speculation-primitive instrumentation (Table 1, Fig. 6), the observation window (Fig. 7), per-transmitter signals (load, branch, other, store), and the nine gem5 source sites are all written. There's also a knobs subsection (§4.4). Over-long items: the nine-file hook list and the store-transmitter bullet. The store bullet describes a checker the repo doesn't have: `wiki/state/OPEN.md` says "24 str hits untriaged… needs a store-transmitter checker".
- **(b) Must say:** the free/locked operand pools, the zero-init prologue and its consequence (index = 0, so a leak demonstrates defense failure, not secret recovery: `PAPER_RESULTS.md` §4, §9 C2). The speculation table. The window `lc_retire < signal < fnc_retire`. The data-obtained gate (reached_cache or store_forward; squash never gates: `CLAUDE.md` "Leak criteria"). That the branch checker is weak and how the NI audit compensates (`STATUS.md` "STANDING NEED"). The 3 control hooks and the rule that the harness only realizes and observes, never alters the defense. The sweep knobs as swept variables.
- **(c) Tasks:**
- [ ] Cut the nine-site hook list to 2 sentences and point to the artifact. (20 min)
- [ ] Delete or caveat the store and "other" transmitter bullets: say whether any results use them. (15 min)
- [ ] Add 2 sentences on the zero-init prologue and what it bounds (`METHODS_CONCRETIZATION.md`, `PAPER_RESULTS.md` §9). (20 min)
- [ ] Add 1 paragraph on the branch-channel checker's limits plus the NI value-flip audit (42/42 sound), from `claudenotes.md` 2026-06-09 and `STATUS.md`. (30 min)
- [ ] Merge §4.4 "knobs" into one compact table: knob, what it does, swept range. Use `METHODS_LEAKAGE_KNOBS.md` and `PAPER_EXPERIMENTS.md` §0. (40 min)

### §6 Triage: from a hit to a bug (falsification protocol) [NEW, not in draft] (target 0.5 pp)
- **(a) State: empty.** This is the section the reviews asked for.
- **(b) Must say:** that a hit can come from (a) a real defense bug, (b) model over-approximation, (c) concretization, or (d) a checker false positive. The ordered disqualifier pipeline is `bucket_hits.py`: XML-only artifacts first, then gem5 checker false positives, then known real bugs, then NEW (`CLAUDE.md` "Systematic hit bucketing"). The controls: stock timing gives 0; fnc on/off; the Unsafe scheme is byte-identical; the Fence control; patch-on for UV1. The attribution funnel numbers come from F1c / `tab:score` in `paper_figures/figures.tex`. Show one worked example end to end: `inst-047231`, from `wiki/findings/bug/stt_slowcomm_vp_squash_race/BUG_EXPLAINER.md`. The race was isolated as "not a checker FP (cache-reach = real packet), not model over-approx (XML 231/231 addr_from_load), not the fnc hook, not squashWidth" (`PAPER_RESULTS.md` §2.2).
- **(c) Tasks:**
- [ ] Write 1 paragraph listing the 4 hit causes and the ordered disqualifier pipeline. (30 min)
- [ ] Write 1 paragraph on the controls, each with its number and source path. (30 min)
- [ ] Put `tab:score` (the F1c attribution table) into the paper and update the SPT row after G4. (30 min)
- [ ] Write the worked example walking `inst-047231` through every disqualifier, cross-referencing Fig. 8. (40 min)

### §7 Evaluation [draft §5 "Results"] (target 3 pp)
- **(a) State: rough draft prose.** §5.1–5.7 exist as paragraphs with Figs 8–12. Problems: the **bug table is missing** ("Table ??"; it exists in `old_format/results-simspect.tex` and `paper_figures/figures.tex` Tab. 1). There's no setup subsection (builds, commits, corpus sizes, runtimes). "[Anna: fixing this still]" sits in §5.4. Recon OTB and SLF were dropped in June (the "two mechanism classes" wording) without a recorded reason. "Every reported leak is gem5-validated" (§5.7) repeats §5.1.
- **(b) Must say (as RQs):**
- RQ1 Bugs: bug table plus race mechanism (Figs 8, 9). Use 19,845 confirmed unless EXP-3 confirms the 4,122. Include SpecLFB UV6 68/300, the SPT claim per G4, and Recon per D3.
- RQ2 Validity: §6 controls, stall sweeps (F4), fragility (F5a) with the justification for changing timing (`PAPER_RESULTS.md` §7 "Why this is allowed"), and the NI branch audit as a positive control.
- RQ3 Targeting and efficiency vs AMuLeT: 17% vs 100% (Fig. 10) with the targeting ≠ realizability caveat (`PAPER_RESULTS.md` §5 caveat), 6 vs 39, 23% vs 3.3%, and gem5 cost comparable (Fig. 12).
- RQ4 Coverage and diversity, stated honestly: core counts, what the cap does, and the two-stage/interleave result (G1).
- Scope vs AMuLeT, after D4.
- Setup table: build path, scheme flags, CPU, timing params (stock vs slow-comm `commitToIEWDelay`), corpus per campaign. Sources: `specs/gem5_builds.json`, run configs on cafe2, `wiki/design/MODELS_AND_BUILDS.md`.
- **(c) Tasks:**
- [ ] Write the setup table from `specs/gem5_builds.json`, `MODELS_AND_BUILDS.md`, and the campaign `run_config.jsonc` files (on cafe2). (45 min)
- [ ] Write a "corpus and runtime" paragraph: 100k cap, concretized per mode, per-test gem5 0.092 s plus trace and boot overheads (`PAPER_RESULTS.md` §8). Total wall-clock is unknown, so find it in the campaign manifests or omit it. (30 min)
- [ ] Port the bug table from `old_format/results-simspect.tex` (the `tab:bugs` table*) after resolving D2/D3/D4/D5, and fix the "Table ??" refs. (45 min)
- [ ] Rewrite §5.1 so its number and class list match the table. (30 min)
- [ ] Merge §5.7 into §6 and delete the duplicate. (15 min)
- [ ] Resolve "[Anna: fixing this still]" in §5.4. It's unclear what was being fixed, so ask Anna (Q5). (15 min)
- [ ] Write the RQ2 paragraph on why timing sweeps are legitimate (4 points from `PAPER_RESULTS.md` §7). (30 min)
- [ ] Write the RQ4 coverage paragraph from `ENUMERATION_OVERSPECIFICATION.md` and `TWO_STAGE_STT_FEASIBILITY.md`. (40 min) [blocked on D1]
- [ ] Write the AMuLeT-scope paragraph per D4, then decide whether `tab:scope` fits the page budget. (30 min)
- [ ] Add the secret-dependence result if EXP-2 runs, otherwise a limitation sentence. (20 min)

### §8 Discussion and limitations [draft §7] (target 0.5 pp)
- **(a) State: rough.** One paragraph on the execution-contract intersection question, plus a stray `[Anna: 2. Alloy abstract LILT…]` note.
- **(b) Must say:** raw vs realizable execution contract (keep the existing paragraph). Limitations: zero-init means the corpus shows defense failure but not secret recovery. The weak single-run branch checker. Inexpressible channels (implicit flow, store/TLB, squash-timing like pending-squash). The cap and diversity limits. And the open question of whether a multi-cycle-squash CPU (`commitToIEWDelay ≥ 2`) is in scope (`claudelog.md` 2026-06-10 10:30). Optionally the cache-size amplification knob (`STATUS.md` TODO, `AMULET_BUGS_DETECTION_ACCOUNTING.md` §4).
- **(c) Tasks:**
- [ ] Delete the stray Anna note and keep the contract-intersection paragraph, trimmed to 120 words. (15 min)
- [ ] Write a 5-bullet limitations paragraph citing the repo evidence above. (40 min)
- [ ] (Optional, if space) Write 1 paragraph on the cache-size amplification knob. (25 min)

### §9 Related work [draft §6] (target 0.75 pp)
- **(a) State: outline.** Bullets only (6.1–6.4).
- **(b) Must say:** the YArch three-thread version: litmus synthesis (memsynth, memalloy, Lustig, PerpLE, TransForm, MC Mutants); HSCD validation and verification (CheckMate, contract shadow logic, LEAVE, Cats vs Spectre, SynthLC/rtl2µpath, Revizor, Pensieve, LCMs); simulator validation (AMuLeT). Also the AMuLeT-limitations list, which is currently in the discussion section.
- **(c) Tasks:**
- [ ] Port the YArch related work as prose (YArch PDF §5; `.tex` at `/tests/YArch-26-SimSpect-new/related-work.tex` on cafe2). Fix the Pensieve/LCM mislabel flagged by Reviewer C. (45 min)
- [ ] Merge the AMuLeT-limitations bullets into one paragraph and cut any that §7 already shows. (30 min)
- [ ] Port the missing bib entries from YArch refs [5], [9], [10], [14], [16], [18], [21]–[27]. (30 min)

### §10 Conclusion [missing] (target 0.15 pp)
- [ ] Write 4 sentences restating the 3 contributions and the headline results. (20 min)

### Abstract
- **(a) State: rough.** It claims "previously unknown bugs in both comprehensive defenses STT and SPT" (G4), "replicate all in-scope previously known security bugs", and "15% of the test count".
- [ ] Rewrite the abstract to match the final §7 numbers. Register the final version on **Nov 9**. (40 min) [blocked on D1–D5]

---

## 3. Figures and tables

### Already in the ISCA draft (numbered as in the PDF)
| Draft fig | What | Verdict | Change |
|---|---|---|---|
| Fig 1 | Three levels of assurance | Near ready | Tighten the caption. Fine for ISCA. |
| Fig 2 | ddi/rf violation (`tikz/alloyviolation.tex`) | Ready | — |
| Fig 3 | 4 relaxation variants (`tikz/relaxation.tex`) | Ready | Fix the "Figure ??" ref in the text. |
| Fig 4 | Alloy interleave (`tikz/interleave.tex`) | Caption problem | The caption describes the OTB taint-tracking bug. Reword it or keep Recon (D3). |
| Fig 5 | State-specification table (`tikz/statetable.tex`) | Ready | — |
| Fig 6 | Two resolutions of I0 (`tikz/resolutiontiming.tex`) | Ready | — |
| Fig 7 | Checker observation window | Ready | — |
| Table 1 | Speculation types (`tikz/sptable.tex`) | Ready | The "Unresolved loads" row claims STL alias forcing. Confirm it was used in the reported runs, or drop the row. 2026-10-28: the direction is false negative (predict no alias, actually alias); the uploaded `tikz/sptable_v2.tex` still says the reverse (fixed copy in `simspect/paper_figures/spec_primitives/`). A generator exists now (`stl_bypass`), but no reported run uses it. |
| Fig 8 | LSQUnit trace, `inst-047231` | Ready | Data from `wiki/findings/bug/stt_slowcomm_vp_squash_race/`. |
| Fig 9 | Race schematic | Ready | It supersedes repo F6. |
| Fig 10 | Targeting 14/5/17 vs 100 | Near ready | Add a caveat in the caption that 100% is by construction (`tag_xm`). Consider repo F3b's loose/tight split. |
| Fig 11 | (a) fragility, (b) s_U | Near ready | Sample sizes (300 / 200) belong in the caption. Consider showing s_R and fnc too (repo F4a) because fnc = 0 still leaking is the key control. |
| Fig 12 | Efficiency, 3 panels | Near ready | Possibly cut to 2 panels for space. |
| Table ?? | Bug table | **Missing** | Port from `old_format/results-simspect.tex` or `paper_figures/figures.tex` Tab. 1 after D2–D5. |

### Repo candidates (`paper_figures/`)
Regenerate PNGs with `python3 paper_figures/make_paper_figures.py`. It writes every `F*.png` next to itself. Numbers are hard-coded in its DATA block, so a changed number means editing that block. TikZ versions: `pdflatex paper_figures/figures.tex` (needs tikz and pgfplots ≥1.16; it compiled as part of the old_format paper per `claudenotes.md` 2026-06-03). **None of the PNGs are paper-ready as-is.** They all have in-figure titles like "F9 — …", and ISCA wants captions only, with readable font sizes (CFP Phase 0 check). Use the TikZ versions.
- **F1 attribution (a/b/c):** use **F1c as the `tab:score` TikZ table** for §6. Fix two things first. The SPT-Fence slow-comm row says "0* (A5 open)" (G4). The STT slow-comm "candidate 4,122" is un-rerun (EXP-3).
- **F2 scope (a/b/c):** it's out of date. It says "1 of 8 in scope", but the repo later reproduced 7 of 9 AMuLeT bugs with bespoke watchers (`AMULET_LOAD_DEFENSES_PROJECT_LOG.md`), and unXpec is a 9th bug missing from the 8. Redo it after D4. Probably a small table, not a figure.
- **F3 targeting (b best):** the draft's Fig 10 already covers it. Optionally add the loose 70% bar.
- **F4 stalls (a best):** three panels. The x-axis shows s_U = 0 plotted at 1 on a log scale, which is a hack, so label it or use categorical ticks. 200 per mode. Paper-usable as TikZ (`fig:stalls`).
- **F5 fragility:** F5a is what draft Fig 11a uses. **Don't use F5b yet.** Its "Fence REAL after const-addr filter" line is 0 at every `commitToIEWDelay` from 1 to 4, which contradicts the claim that SPT-Fence leaks under slow-comm (G4).
- **F6 VP race timeline:** superseded by draft Fig 9. Don't use it.
- **F7 recon bugs:** only if D3 keeps Recon. The SLF panel matches `inst-014912` (store and load to the same tainted address). The old_format TikZ `fig:recon` instead shows a store to a fixed IMM committed before the branch, a **different gadget than inst-014912**, so reconcile before using either.
- **F8 efficiency:** the draft's Fig 12 is the TikZ version. In the PNG (F8a), the "0.092" label is hidden under the annotation box.
- **F9 bug table:** use the LaTeX table, not the PNG. Its verdicts conflict with the draft: KV3 is "real (known)" in F9 but "not a bug" in the draft, and SPT is "candidate" in F9 but presented as a bug in the draft (D2, G4).
- `plots/*.png` (hit rate by n_branches, xmit kind, and so on) and `wiki/findings/bug/graphs/*.png` are older diagnostic charts. Not needed for the paper.

### Missing figures and tables the paper needs
- [ ] **Pipeline overview** (Alloy → concretize → gem5 → triage). `images/pipeline.png` is already in the Overleaf and has never been included (`YARCH_PORT_PLAN.md` 1.1). Add the triage stage as a 4th box or arrow. (30 min)
- [ ] **Running STT example** (`images/examplefigure.png`, D6). (30 min)
- [ ] **Defense specification table** (§3). (see §3 tasks)
- [ ] **Evaluation setup table** (§7). (see §7 tasks)
- [ ] **Bug table** (§7). (see §7 tasks)
- [ ] **Attribution / triage table** `tab:score` (§6). (see §6 tasks)
- [ ] (Optional) Comparison-to-prior-work table: SimSpect vs AMuLeT vs Revizor vs CheckMate, by target (simulator / silicon / RTL / model), generation (directed / random), oracle, and white-box use. Derive the rows from `PAPER_RESULTS.md` §3 table and YArch related work. (40 min)

---

## 4. Gaps

### Results or experiments that block claims
- **G1 (biggest): completeness.** Claims that can't be written today are "generates all minimal leakage backbones up to the bound" and "coverage is complete up to the instruction bound". The reason is that enumeration never reached UNSAT and the corpus is 98% one core (§0 fact 4). There are two ways forward. **Option A, writing only (recommended given 20 days):** re-scope to "targeted: every test contains a transmitter in the protection set; generation is capped". Report core diversity honestly and present the two-stage result (exact at N=3) as the path to completeness. **Option B, experiment:** EXP-1, exhaust minimal cores to UNSAT at bound 6 with the staged-bounds and core-quotient driver (`REACH_UNSAT_ENUMERATION.md`). It needs owner-gated `.als` changes (drop RO clause (e) in `STT_6_core.als`, `URGENT_TODO.md` #2) and an unknown amount of compute. N ≥ 4 was "not locally exhaustible" (`claudelog.md` 2026-10-26).
- **G2: corpus staleness.** The STT_6 testsets "predate the effective RS minimality clause → cover only 2 of ~45 leak dataflows" (`PAPER_RESULTS.md` §9 C4). The 150k regen from June 3 was "launched 06-03, confirm completion" (`STATUS.md`). That leaves open which corpus produced which number. List the corpus behind each result in the setup table. No re-run is needed if the wording is honest.
- **G3: the 4,122 NEW STT slow-comm hits are un-rerun** (`make_paper_figures.py` F1 labels them "NEW (un-rerun)"). The draft's "23,966" seems to count them. Note that 19,845 + 4,122 = 23,967, which doesn't equal 23,966 either. Either report 19,845 (writing only) or run EXP-3, which re-buckets the NEW set with `--with-gem5`.
- **G4: the SPT claim.** Can't be written yet: "previously unknown bugs in both STT and SPT" and "SPT-Fence exhibits the same race". In the repo, F9 calls SPT "candidate", `PAPER_RESULTS.md` says "A5 ⏳ open", the ~983 race-shaped candidates are a manual estimate with an 80/80 sample, and F5b shows Fence-filtered at 0 for every delay. **EXP-4:** run the race diagnostic (`diag_stt_vp_squash_race.py`, adapted for SPT) on the `spt_slowcomm_fence` NEW set, and run SPT through the fragility sweep with the const-addr filter. If it doesn't confirm, the claim becomes "STT only, with SPT sharing the untaint-at-VP logic (source-level)".
- **G5: secret dependence.** Reviewer B wants proof the transmitter leaks data, not just that it fired. Today index = 0 because of the zero-init prologue (`PAPER_RESULTS.md` §4, §9). **EXP-2 (small):** seed a non-zero secret into `inst-047231` (and one UV6 test) and show the touched cache line differs between secret values, value-flip style like `bugsynth/check_br_ni.py`. It's a test-input change, not a model or defense change. Without it, write a limitation sentence.
- **G6: the "seven/eight defenses expressed" claim has no artifact** (§3(a)). Writing only: build the table from papers (and say which rows are paper-only), or reduce the claim.
- **G7: no setup or runtime table.** The data exists on cafe2 (run configs, manifests). It's collection work, not an experiment.
- **G8: whether the race is really "previously unknown".** Nothing in the repo shows a literature or author check. The pending-squash fix by Mosier is a different bug. Ask Anna or Caroline (Q4).

### Inconsistencies between the draft and the repo
- Targeting is 17% in the repo (`PAPER_RESULTS.md` §5), but the draft intro says 15%. The abstract's "15% of the test count" is 6/39. Keep the two numbers apart.
- The race count is 23,966 in the draft, 19,845 confirmed plus 4,122 NEW in the repo (G3).
- KV3 is "not a bug" in the old_format table, but F9 says "real (known)", and `STATUS.md` says "Real STT defense bug" (`wiki/findings/bug/STT_KV3_TLB_REVIEW.md`). D2.
- AMuLeT scope: the draft and F2 say "1 of 8 in scope", but the repo has 7 of 9 reproduced with bespoke watchers, and `AMULET_VS_SIMSPECT_SCOPE.md` (June 10) argues InvisiSpec is out of scope by definition. D4.
- Recon OTB and SLF are in `PAPER_RESULTS.md` and F9, but the June-10/ISCA draft dropped them. D3.
- Old_format `fig:recon` shows a store to a fixed IMM. The real `inst-014912` stores to the same tainted address (`recon_SLF_stlf_bypass/NOTE.md`).
- The draft lists RI/RO/RS/RC/RR as the minimality, but in-use STT_6 has no RI or RO (`claudelog.md` 2026-06-10 staged-enum).
- The draft says seven defenses and YArch says eight (with Protean). Repo models exist for 3.
- The draft's §4.3.1 store-transmitter signal describes a checker that doesn't exist (`wiki/state/OPEN.md`: str hits untriaged).
- The draft says SPT was run, but SPT ran with `freeParam=0`, so forward/backward untaint was inert (`claudelog.md` 2026-06-10 CONFIG BUG). Any SPT result must say "VP-untaint-only configuration", or be re-run with `--freeParam=3`. The June 10 freeParam=3 reruns found 0 NEW load hits, but they didn't use slow-comm timing.
- Leak-core counts: 47 leak-cores (padding projected out) vs 10 structural dataflow cores (`claudelog.md` 2026-06-09 addendum 3). They are different definitions. Pick one and define it.

### Stale content to cut
- [ ] Remove "(draft do not share)" from the title and delete the Acknowledgments stub (double-blind). (5 min)
- [ ] Remove every `[Anna: …]`, `[todo: …]`, and `[?]`. (20 min)
- [ ] Cut duplicated AMuLeT critique (§2.2, §6.1, §7) down to one place (§9). (20 min)
- [ ] Cut §5.7, which duplicates §5.1. (5 min)
- [ ] Cut the nine-file hook list (§4.3.3) to a pointer. (part of the §5 tasks)
- [ ] Don't re-use anything from `technicaldetailsold.tex` or the YArch preliminary results (`YARCH_PORT_PLAN.md` "DO NOT PORT").

---

## 5. Decisions only Anna can make (each blocks writing)
- [ ] **D0 Authors** (by Nov 9, the CFP makes them final): do Nick Mosier and Prof. Mitchell go on? (Anna's own question in `STATUS.md`.)
- [ ] **D1 Completeness framing:** Option A (re-scope, writing only) or Option B (run EXP-1, `.als` changes need your sign-off). Recommendation: A, with the two-stage result as future-proofing.
- [ ] **D2 KV3 verdict in the bug table:** "out of STT's contract (not a bug)" or "real known STT bug (DOLMA), outside SimSpect scope".
- [ ] **D3 Recon:** put OTB (forced via `otb_class`, 30/30) and SLF (1 live instance) back? If yes, decide how to frame "forced" and resolve the SLF gadget figure mismatch. Note that Recon's gem5 is "closed source" per `documentation/docs/defenses.md`, so check what can be disclosed.
- [ ] **D4 AMuLeT scope story:** "1 in-scope bug, found by the mainline pipeline", or also report the 7/9 reproductions with bespoke watchers?
- [ ] **D5 Is slow-comm (`commitToIEWDelay ≥ 2`) in scope as a hardware assumption?** The headline bug depends on it (`claudelog.md` 2026-06-10 10:30). This sets how strongly to word "bug".
- [ ] **D6 Running example:** use `examplefigure.png` as is, or redraw it in TikZ?
- [ ] **D7 Defense table:** how many defenses, and is "specified on paper" acceptable for rows with no Alloy model?
- [ ] **D8 SPT config:** re-run SPT at `--freeParam=3` (paper-faithful) before claiming anything about SPT, or report it as the VP-untaint-only configuration?

---

## 6. "Just follow this" sequence

Legend: **[W]** pure writing · **[D]** needs Anna's decision · **[E]** blocked on an experiment (run on cafe2; any `.als`, `parsexml.py`, or hook change needs Anna's sign-off) · **[X]** external or admin. Dates assume submission on Nov 16, 2026.

### Phase 0: setup (1 session, Oct 27–28)
- [ ] 0.1 [X] Confirm the venue and dates on https://iscaconf.org/isca2027/ and check whether the 2027 submission guidelines (page limit, template) are out yet. Write the result at the top of this file. (15 min)
- [ ] 0.2 [X] In Overleaf, make a new branch or copy named for ISCA 2027 and switch to the ISCA/IEEE conference template (2026 rules: 10 pt, 2-column, US Letter, page numbers, confidentiality banner). Compile, then record the page count. (45 min)
- [ ] 0.3 [W] Remove "(draft do not share)" and the Acknowledgments stub, check the PDF metadata has no author names, and make sure the title isn't the same as the YArch title if YArch is online (Q2). (15 min)
- [ ] 0.4 [W] Put in an empty section skeleton matching §2 of this plan (§1–§10 headings with a one-line `% TODO` under each) and move the existing text into the new homes. Moves only, no rewriting. (45 min)
- [ ] 0.5 [D] Hold a 30-minute decision session to settle D0–D8 (§5 above). Write the answers here. (30 min)
- [ ] 0.6 [E] After D1/D4/D8, start the chosen experiments on cafe2 in the background. In priority order: EXP-4 (SPT race), EXP-3 (re-bucket 4,122), EXP-2 (secret-dependence), EXP-1 (only if D1 = B). The disk is 88% full (`df`, 2026-10-27), so check space first. (45 min)

### Phase 1: skeleton everywhere (Oct 28 – Nov 1)
Goal: every section has full-sentence placeholders and every figure and table is in place, rough. No polish.
- [ ] 1.1 [W] §1: contributions paragraph (30 min)
- [ ] 1.2 [W] §1: AMuLeT and "bugs void prototypes" paragraph, fix `[?]` (20 min)
- [ ] 1.3 [W] §2: three-axes bridge, cut §2.2, add the SPT sentences (45 min)
- [ ] 1.4 [W] §2: fix the citations (20 min)
- [ ] 1.5 [W] §3: reconcile the STT example with `STT_6.als` (20 min)
- [ ] 1.6 [W] §3: defense table rows for STT, SPT, Recon (45 min)
- [ ] 1.7 [W] §3: expressiveness-limits paragraph and delete the empty headings (35 min)
- [ ] 1.8 [W] §4: new opener, fix the relaxation list, fix "Figure ??" (55 min)
- [ ] 1.9 [W] §4: minimal-leak-witness paragraph (45 min)
- [ ] 1.10 [W] §5: cut the hooks list, caveat the store and "other" bullets, zero-init sentences (55 min)
- [ ] 1.11 [W] §5: branch-checker paragraph and the knobs table (70 min, split in two)
- [ ] 1.12 [W] §6: the 4-cause and disqualifier paragraph, then the controls paragraph (60 min)
- [ ] 1.13 [W] §6: worked example for `inst-047231` (40 min)
- [ ] 1.14 [W] §6: insert `tab:score` (from `paper_figures/figures.tex`) with an "SPT TBD" placeholder (30 min)
- [ ] 1.15 [W] §7: setup table, filling in the cafe2 values later (45 min)
- [ ] 1.16 [D] §7: port the bug table with the D2/D3/D4 verdicts and fix the "Table ??" refs (45 min)
- [ ] 1.17 [W] §7: corpus and runtime paragraph (30 min)
- [ ] 1.18 [W] §7: RQ2 timing-legitimacy paragraph (30 min)
- [ ] 1.19 [W] §7: merge §5.7 into §6 and resolve "[Anna: fixing this still]" (30 min)
- [ ] 1.20 [W] §8: trim the discussion, 5-bullet limitations (55 min)
- [ ] 1.21 [W] §9: port the YArch related work and merge the AMuLeT critique (75 min, split in two)
- [ ] 1.22 [W] §9: port the bib entries (30 min)
- [ ] 1.23 [W] §10: conclusion (20 min)
- [ ] 1.24 [W] Figures: include `pipeline.png` and the running example, add the caveats to the Fig 10/11 captions, fix the Fig 4 caption (60 min, split in two)
- [ ] 1.25 [W] Compile and record the page count. If over 11 pp, list the cut candidates here; don't cut yet. (20 min)

### Phase 2: results-dependent text (Nov 1–6, as experiments land)
- [ ] 2.1 [E: EXP-4] Write the SPT row and paragraph, either "confirmed race" or "shares the logic, not confirmed live". Update `tab:score` and the bug table. (40 min)
- [ ] 2.2 [E: EXP-3] Fix the race count everywhere (abstract, §1, §7, Fig 9 caption): 19,845, or the re-bucketed total. (20 min)
- [ ] 2.3 [E: EXP-2] Add the secret-dependence result to §7 RQ1 and §6, or the limitation sentence in §8. (30 min)
- [ ] 2.4 [D1 / E: EXP-1] Write the §4 coverage paragraph and the §7 RQ4 paragraph. (70 min, split in two)
- [ ] 2.5 [D4] Write the AMuLeT-scope paragraph, plus the small scope table if it fits. (30 min)
- [ ] 2.6 [W] Update `make_paper_figures.py` DATA or the `figures.tex` values for any changed numbers, and regenerate (`python3 paper_figures/make_paper_figures.py`; `pdflatex paper_figures/figures.tex`). Give Anna the changed values for Overleaf; **don't push**. (30 min)
- [ ] 2.7 [W] Write the §1 results paragraph and the "scope of comprehensive" sentence with the final numbers. (45 min)
- [ ] 2.8 [W] §3: remaining defense-table rows from the papers, about 2 per sitting. (3 × 45 min) [D7]

### Phase 3: abstract registration (Nov 7–9)
- [ ] 3.1 [W] Rewrite the abstract against the final §7. (40 min)
- [ ] 3.2 [X] Confirm the author list (D0) and the title (Q2). (15 min)
- [ ] 3.3 [X] Register the abstract on the ISCA 2027 submission site by **Nov 9, 11:59 PM AoE**. Anna does this herself. (30 min)
- [ ] 3.4 [X] If the paper was previously submitted and rejected anywhere (Q1), draft the one-page change note. (45 min)

### Phase 4: complete rough draft → refined draft (Nov 9–13)
- [ ] 4.1 [W] Number audit: every number in the PDF against the §1 provenance table of this plan, re-checked on cafe2 at the container paths. (45 min)
- [ ] 4.2 [W] Terminology audit: define transmitter, leakage backbone / leak core / minimal leak witness (pick one name), speculation primitive, lc/fnc, VP. Use them consistently. (30 min)
- [ ] 4.3 [W] Cut to the page limit using the 1.25 list. Cut candidates: Fig 12 to 2 panels, Table 1, the §5 knobs table, and duplicate AMuLeT text. (45 min, may need two)
- [ ] 4.4 [W] Reviewer-lens pass using `paper_figures/reviews/*.md`. Check: is "comprehensive" scoped, is there a falsification protocol, is there a negative control, is reproducibility covered (builds, flags, anonymized artifact)? (45 min)
- [ ] 4.5 [X] Send to Caroline for a read. (—)
- [ ] 4.6 [W] Apply Caroline's comments. (several 45-min blocks)

### Phase 5: final (Nov 14–16)
- [ ] 5.1 [W] Format check against the 2027 guidelines: fonts, figure-text size, banner, page numbers, anonymity, metadata. (30 min)
- [ ] 5.2 [W] Bib cleanup (IEEE style, no `[?]`, no duplicate keys). (30 min)
- [ ] 5.3 [X] Submit by **Nov 16, 11:59 PM AoE**. Anna does this. (30 min)

**Counts:** 6 phases (0–5). 52 checkboxes in §6 (6 + 25 + 8 + 4 + 6 + 3), with time estimates written inline (several are multi-sitting). Section §2 has about 60 finer-grained tasks that the Phase 1–2 steps bundle. 8 decisions (D0–D8). 4 experiments (EXP-1 to EXP-4), of which EXP-1 is optional and the biggest.

---

## 7. Questions only Anna can answer
- **Q1:** Was the June 10 "correct format" version **submitted** to S&P '27? If it was reviewed and rejected, ISCA requires the change note (CFP: "previously reviewed and rejected at … any other venue").
- **Q2:** Is the YArch '26 paper public online (proceedings or arXiv)? If yes, ISCA 2026 rules required a different title. Check the 2027 rules.
- **Q3:** The paper repo is `/tests/SimSpect-S-P-2027/` on cafe2 (`CLAUDE.md` "Paper & figures") plus Overleaf. Which is authoritative now? Should the ISCA version be a new Overleaf project? (The git lock means Claude won't push either.)
- **Q4:** Has anyone (Caroline, the STT or SPT authors) confirmed the VP↔squash race is new and not already known or fixed upstream? Should the STT and SPT authors be contacted before submission? (Anna would do that herself.)
- **Q5:** What was "[Anna: fixing this still]" in §5.4 (targeting) about? Something seemed wrong with the 17% / 14% / 5% analysis.
- Plus decisions D0–D8 above.

*Sources fetched this session for venue facts: [ISCA 2027 Call for Papers](https://iscaconf.org/isca2027/submit/callforpapers.php), [ISCA 2026 Submission Guidelines](https://iscaconf.org/isca2026/submit/guidelines.php).*

---

## 8. Anna's answers (Oct 27) and the Oct 27–30 sprint

**Answers:** D0 authors left blank for now. Q1 the June draft was **not rejected**, so no change note is needed. Q2 unknown whether YArch is online (see open questions below). Q3 the draft of record is the downloaded `SimSpect_ISCA_2027.pdf`; Anna edits on Overleaf. Q4 the VP-squash race **is new**. Q5 unknown, so just re-check the 14/5/17% targeting numbers against `PAPER_RESULTS.md` §5 when you get to §5.4. D3 **Recon goes back in** (OTB + SLF). D4 report **all 7 AMuLeT reproductions**, with all of those defenses tested. D6 figures will be redone in **TikZ**. D7 Anna has specced the other defenses she discussed. The docs site (anna-eaton.github.io/simspect-docs, which is a build of `documentation/docs/`) matches the repo, and its "SimSpect defense specifications" section is still empty. So those specs need to be located (see open questions).

**Defaults used for the schedule until Anna says otherwise:** D1 = option A (re-scope "comprehensive": targeted and capped, report 47 leak-cores honestly). D2 = KV3 is a real, known STT bug, outside SimSpect's scope. D5 = slow-comm (`commitToIEWDelay ≥ 2`) is in scope, stated as an explicit hardware assumption. D8 = re-run SPT at `--freeParam=3` under slow-comm overnight Oct 27.

**Sprint goal:** a solid complete draft by Fri Oct 30 at noon, made of Phase 0, Phase 1, most of Phase 2, the abstract, and a first audit pass. Abstract registration (Nov 9) and Phases 4–5 come after. The schedule is on the local **Quail** calendar as 47 events, each naming its step here and tagged `simspect-sprint-oct27` in its notes. Experiments launch Tue 9:15 pm and their results are folded in Thu 9:30 am. Sleep is 1:00–9:00. Figure blocks: Wed 11 pm–12:30 am (Recon SLF gadget, tab:score), Thu 4:45–6:15 pm (pipeline, running example), Thu 9:15–10:45 pm (clean Figs 10–12 and the stall panels).

**Still open:** Is YArch '26 online (title must differ)? Where are the other defense specs (Overleaf, notebook, cafe2 YArch tex)? For "all 7 AMuLeT defenses tested", are the existing bespoke-watcher reproductions enough, or do you want new SimSpect pipeline runs on InvisiSpec / CleanupSpec / SpecLFB? Confirm or change the defaults for D1, D2, D5, D8.

**Update Oct 27 (later):** YArch is **not online**, so the title can stay. **Other defense specs found:** `STAGE1_alloy/models/old_models/STTcommitted.als` (identical copy in `~/Downloads/STTcommitted.als`, Feb 19), lines ~380–440, as commented-out blocks for STT (two execution-contract variants), SpecShield-ERP, SpecShield-ERP+, NDA-S, NDA-P, and an unfinished SPT. These use the older `State`/`Mem_s` syntax, not the current Operand-based protset, and every block reuses STT's protset-update rule. No Alloy spec was found anywhere on the Mac (or in git history) for DoM, SDO, Doppelganger, or Protean. The Simspect.pptx slide says "all implemented stage 1 except Protean", so those may exist only on cafe2. **SPT freeParam:** see `claudelog.md` 2026-06-10 (two entries). freeParam=0 = VP-untaint-only, stricter than the SPT paper's config (`run_spt.py` pins `--freeParam=3`). The Alloy SPT model does include fwd/bwd untaint rules (`SPT_6_oneLP.als` ~l.345–355). At stock timing, fp0 vs fp3 made no new leaks. Under slow-comm it hasn't been run. **AMuLeT:** only UV1 (InvisiSpec) and UV6 (SpecLFB) came from the Alloy corpus through the pipeline with a per-defense checker. The other 5 were hand-built gadgets with bespoke watchers (`wiki/findings/mdsToRead/AMULET_LOAD_DEFENSES_PROJECT_LOG.md` §0–1).

## 9. Hour-by-hour sprint checklist

The checklist lives in Quail at `~/Documents/quail/lists/schedule/2026-10-27.md`. Each block has a checkbox, pings you when it starts, and asks "did you do it?" if it ends unticked. The per-block cards (where to write, what to cover) are in `sprint/` here.
