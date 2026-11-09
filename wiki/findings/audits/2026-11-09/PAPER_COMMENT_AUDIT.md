# Paper comment audit (2026-11-09)

Every comment in the ISCA-27 paper (`~/trippel/ISCA-27` at `2d5554a`) checked against the current state of simspect. Classes: CURRENT (accurate and still needed), STALE (something it refers to changed), RESOLVED (done), DEAD (deletable). Nothing in ISCA-27 was edited; every proposed note is for Anna to paste. Four parts, one per file group; each part's agent compiled or read the paper independently.

## Part 1: bare_conf_compsoc.tex, sections/abstract.tex, main.tex

Throwaway builds: as committed 13 pp, 0 undefined refs; with every note group shown 24 pp; with the `sscolors` line deleted it still compiles.

Counts (48 items, ~445 `%` lines grouped): CURRENT 19, STALE 3 (two preamble comments + the abstract `\labnote`, which prints in the lab PDF), RESOLVED 0, DEAD 26 (23 IEEE-template blocks, the `wrapfig` line, the old abstract, main.tex). Plus 6 outdated claims in the abstract body (Table 2) and 5 format issues.

**main.tex is dead:** the stock ISCA 2026 template; nothing `\input`s it, it has its own `\documentclass`, and its `\bibliography{refs}` points to a nonexistent refs.bib.

### Table 1: every comment

| file:line | comment (excerpt) | class | evidence | proposed replacement / action |
|---|---|---|---|---|
| bare_conf_compsoc.tex:326 | `% packages` | CURRENT | labels the package block | keep |
| :329 | `% \usepackage{wrapfig}` | DEAD | `wrapfigure` only in commented code (model.tex:36-44) and the un-input oldtechnicaldetails.tex | delete |
| :341 | `% figure TODOs (new figures, 2026-11-02)` | CURRENT | `\figtodo` live in pipeline.tex, results.tex, hidden pendingfigures.tex | keep |
| :343 | `% review notes: suggested cuts, rewords and checks` | CURRENT | 22 live `\reviewnote`s | keep |
| :344 | `% red [TODO: ...] tags ...` | CURRENT | `\reviewtag` in 4 sections + ~25 tikz files | keep |
| :346 | `% fine-grained audit notes ... purple term ... orange defense` | STALE (partly) | all 196 `\auditnote` uses are cite/fig/fact/claim/write; no `term` or `defense` note — the term audit landed as `\urgentnote{\textbf{VOCAB}...}` (pipeline.tex:26-38) | `% audit notes (2026-11-03), one color per audit: blue fact, teal claim, green figure, brown writing, olive cite (purple term and orange defense are defined but unused; vocabulary findings are the VOCAB urgent notes)` |
| :347 | `% visible note for lab readers (2026-11-03)` | CURRENT | live in abstract.tex:5, intro (2), results (2) | keep |
| :348 | `% review mode: each note ... on its own line` | CURRENT (caveat) | switch (2) empties `\notebr` but lab notes stay, so they run inline | optional: add `; emptied by switch (2), so lab notes then run inline` |
| :349 | `% big concerns to fix before sending` | CURRENT | 21 live `\urgentnote`s | keep |
| :350-352 | NOTE SWITCHES (1), (2) | CURRENT | verified both ways (24 pp / 13 pp) | keep |
| :353 | `% (3) hides urgent notes ... and Caroline notes` | CURRENT | no live `\caroline` note remains | optional: drop "and Caroline notes" |
| :354 | `% (4) uncomment to also hide the gray [Note: ...]` | CURRENT | off, so lab notes print for the advisor, incl. the stale abstract note | keep; fix the abstract note |
| :361 | `% pipeline figures: load globally` | CURRENT | used by tikz/pipeline_full_8pt1col.tex (pipeline.tex:57) | keep |
| :363 | `% figure palette (2026-11-03) ...` | CURRENT | matches tikz/sscolors.tex:1-9 and URGENT_TODO.md:80; grayscale build works | keep |
| :364 | `% table captions in normal case` | CURRENT | works; caption.sty warning + template note :243-248 | keep; check ISCA 2027 format rules |
| :365-370 | `% B&W visual language (2026-11-02) ...` (×6) | STALE | replaced by the 11-03 palette; these colors are used only by hidden content (`\iffalse` bug table results.tex:54-89, pendingfigures.tex, archived tikz); `cpipe` only by archived files | :365 → `% legacy B&W colors (2026-11-02), used only by hidden content: the old bug table under \iffalse in results.tex, sections/pendingfigures.tex and archived tikz files; new figures use tikz/sscolors`; :366-370 → `% legacy B&W`; drop `cpipe` |
| :460 | `% \input{sections/pendingfigures}` | CURRENT | still hidden; all refs to its figures are inside `\iffalse`; figures carry pre-2026-10-30 numbers (URGENT_TODO.md:106) | optional: append `; its figures hold pre-2026-10-30 numbers, re-run before unhiding` |
| :1-41, :44-49, :56-61, :67-87, :94-125, :131-169, :175-229, :234-302, :307-314 | IEEEtran template boilerplate (legal, testflow, compsoc, ifpdf, cite, graphicx, amsmath, subfig, url) | DEAD | template; class is `[conference]` without compsoc so `\ifCLASSOPTIONcompsoc` always takes the non-compsoc branch | delete (code can collapse to `\usepackage{cite}`) |
| :319-323 | "Do not adjust lengths that control margins" | CURRENT | still applies | keep or trim |
| :371-372 | `\hyphenation{op-tical net-works semi-conduc-tor}` | DEAD | template words, none in the paper | delete or replace with real words |
| :380-386 | title capitalization guidance | CURRENT | title at :387 not title-cased, still "(draft do not share)" | at submission: `SimSpect: Automated Litmus Testing for Simulated Spectre Defenses` |
| :390-438, :453, :463-470, :475-494, :496-548, :551-577, :580-588, :599, :619-625, :644 | template authors, keywords, peer-review, demo sections, figure/table/float examples, appendix, triggeratref, "that's all folks" | DEAD | template | delete |
| :593-594 | `% \section{Conclusion}` | DEAD | shows the paper has no Conclusion (last section is Discussion) | delete; decide whether to add a conclusion |
| :603-610 | acknowledgment comments | DEAD | body at :613 is still the placeholder | hide/delete the acknowledgment for double-blind (main.tex:162-166) |
| :627-636 | bibliography notes + commented duplicates | DEAD | duplicates of :638-639 | delete; ISCA template uses `IEEEtranS` (main.tex:332) |
| sections/abstract.tex:4-6 | `\labnote{InvisiSpec, SpecLFB and CleanupSpec results still to be inserted here.}` | STALE | prints in the lab PDF; results now exist (below); contradicts the abstract, which already states a SpecLFB result (6.5x) | see replacement below |
| sections/abstract.tex:8 | commented older abstract ("... (SCDs) ...") | DEAD | superseded; uses the dropped "SCDs" acronym | delete |
| main.tex (whole file) | ISCA 2026 template | DEAD | not input anywhere; `refs.bib` missing; template 6/27/2024 | delete, or keep as format reference until the ISCA 2027 template is out (11 pp excl. refs :76; all authors :79; double-blind :162) |

Evidence for abstract.tex:4-6: on 2026-11-08 the hooks-v2 STT_6 runs found InvisiSpec UV1 in 2995/3000, CleanupSpec UV4 in 38, SpecLFB UV6 in 1143 and 1142 of 1500 (per mode), and the new verified SpecLFB jmp-shadow bug in 148 (AMULET_BUGS_DETECTION_ACCOUNTING.md:33,37,40,42; STATUS.md:43). CleanupSpec UV3 reproduces cold (407), counting pending (URGENT_TODO.md:163). Nothing is the eval of record yet (EVAL_MANIFEST.md:18).

Proposed replacement for abstract.tex:4-6: `\labnote{Interim results pending the final eval re-run: InvisiSpec UV1, CleanupSpec UV4 and SpecLFB UV6 reproduce on 3,000-test samples through the new trace hooks, and a new SpecLFB bug (a direct jump after an unresolved branch drops the load shadow) has been verified. The SpecLFB comparison with AMuLeT is being re-run with AMuLeT's own configuration.}`

### Table 2: outdated claims in the abstract body

Paste the notes after abstract.tex:3 (switch (2) hides them). intro.tex:64-65 and results.tex:93 repeat the same claims; fix together.

| file:line | text | issue + evidence | proposed note |
|---|---|---|---|
| abstract.tex:3 | "takes less time to rediscover known bugs ... 6.5x fewer tests than AMuLeT" | 6 vs 39 is from the June run (PAPER_RESULTS.md:485-496), before the harness fix (URGENT_TODO.md:106); it counted cache hits, which SpecLFB scopes out (accounting:63; URGENT_TODO.md:140); AMuLeT comparisons must use AMuLeT's flags (STATUS.md:27-30); the Results subsection with this number is cut under `\iffalse` (results.tex:252-269). "Less time" also fails: at 1.12 s/test (PAPER_RESULTS.md:514-517), 6 tests ≈ 6.7 s vs ≈ 2.2 s of AMuLeT simulation | `\reviewnote{6.5x (first detection at test 6 vs 39) is from the June SpecLFB run, before the 2026-10-30 harness fix, and it counted cache hits, which SpecLFB scopes out; the Results subsection with this number is cut for that reason. Re-run with AMuLeT's own flags or use [N]. Only test counts were compared, so ``takes less time'' needs its own measurement.}` |
| abstract.tex:2 | "previously unknown visibility-point/squash timing race shared by STT and SPT" | STT A4 leaks only with commitToIEWDelay ≥ 3, 0 at stock (BUG_TAXONOMY.md:96-118); counts pre-fix (URGENT_TODO.md:106); SPT side (A5) attribution unresolved (BUG_TAXONOMY.md:120-135), all post-fix SPT hits are artifacts (STATUS.md:45); latency knob is a pending decision (URGENT_TODO.md:67); the 11-08 rule (URGENT_TODO.md:30) makes the race count | `\reviewnote{The STT race needs a raised commitToIEWDelay (0 leaks at stock) and its counts predate the 2026-10-30 harness fix; the SPT side is still open (no fixed-harness rerun, and the post-fix SPT hits are all model or concretization artifacts). Say ``in STT'' and state the latency condition, or re-run both first.}` |
| abstract.tex:2 | "we replicate all in-scope previously known security bugs" | UV5 caught only on a hand-made demo (accounting:38); UV3 only with the cold RMW corpus, pending (URGENT_TODO.md:163); A3c not generated (URGENT_TODO.md:22), its differential detector ruled out (claudelog.md:72); out of scope KV3, UV2, KV1, unXpec (URGENT_TODO.md:11, :174) | `\reviewnote{``All in-scope'' is not yet shown: UV5 was caught only on a hand-made demo, UV3 needs the cold-cache RMW corpus (counting pending), and the pending-squash race (fixed upstream in STT) is not generated yet. Give a count, or list what is in scope.}` |
| abstract.tex:2 | "find two bugs in ReCon's implementation of STT: store-to-load forwarding ... older operand's taint" | A2 confirmed (BUGS.md:30), holds on the fixed harness (STATUS.md:44-45); most A2 hits come from concretization aliasing (claudelog.md:143); OTB comes out only through the opt-in Stage-2 OTB merge, 100/100 vs 0/100 (claudelog.md:42-46) | `\reviewnote{OTB now comes out of the pipeline only with the opt-in Stage-2 OTB merge (100/100 vs 0/100 on Recon-STT); say so in the text.}` |
| abstract.tex:2-3 | (missing) | STT xmm4 taint drop: 98/100, pipeline-found, still in upstream STT master (stt_xmm4_taint_skip/README.md:3; claudelog.md:135-137, :154-157); SpecLFB jmp-shadow verified (speclfb_jmp_shadow/README.md) | `\reviewnote{Two newer pipeline-found bugs are not here: STT drops taint through xmm4 (98/100, still in upstream STT master) and SpecLFB's jump-shadow bug (verified). Add them if they are counted.}` |
| abstract.tex:2 | "proving security properties ... comprehensive litmus test suite" | Stage 1 exhaustive to 6 instructions for STT_6 (129 cores), Recon_6 (129), STT_6_stl (306), Recon_6_stl (858); SPT v2 caps at 200,000 (EVAL_MANIFEST.md:41-46; URGENT_TODO.md:36) | `\reviewnote{Stage 1 is exhaustive up to six instructions for the STT and ReCon families but caps for SPT, and Alloy checks are bounded; consider ``bounded-exhaustive'' and drop ``proving'' unless the paper proves something.}` |

### Fix first (part 1)

1. abstract.tex:5 — the stale lab note the advisor sees.
2. abstract.tex:3 — the pre-fix 6.5x / "less time" sentence.
3. abstract.tex:2 — "shared by STT and SPT".
4. abstract.tex:2 — "replicate all in-scope".
5. abstract.tex:2-3 — xmm4 and jmp-shadow missing (if counted).
6. Same claims at intro.tex:64-65 and results.tex:93.
7. Housekeeping: preamble :346, :365-370; delete :329, template blocks, abstract.tex:8, main.tex.

Format issues: the body + acknowledgment run into page 12 of 13 (ISCA 2026 limit is 11, main.tex:76; check ISCA 2027); title not title-cased and says "(draft do not share)"; acknowledgment is a placeholder (double-blind); no Conclusion; bib style `IEEEtran` vs template `IEEEtranS`.

### Decisions surfaced (part 1)

1. What counts as "found by SimSpect": (a) default pipeline only (A2, A4 slow-comm, UV1, UV4, UV6, jmp-shadow); (b) also opt-in Stage-2/harness finds, each labelled (xmm4 via xmm routing, OTB via the OTB merge, UV3 via RMW + cold cache); (c) also code-read candidates as future work. Evidence URGENT_TODO.md:25, claudelog.md:42-46, :154-157. Recommendation: (b), naming each option (a reviewer may call the OTB merge targeted).
2. "All in-scope previously known bugs": (a) keep once UV5/UV3/A3c settle; (b) "N of M" now; (c) narrow the scope wording. Recommendation: (b) until the eval re-run.
3. The race claim: (a) keep "STT and SPT" pending a slow-comm re-run; (b) "in STT" with the squash-propagation condition; (c) wait for S4 (unapproved draft, URGENT_TODO.md:23). Recommendation: (b) now. Side note: R1 items at URGENT_TODO.md:74, :105 look superseded by :30.
4. AMuLeT efficiency sentence: (a) drop; (b) "[N]x fewer tests" re-run on `runconfigs/amulet_parity/`; (c) keep 6.5x with a caveat. Recommendation: (b).
5. "Proving"/"comprehensive": (a) keep; (b) "bounded-exhaustive up to six instructions" and say SPT caps; (c) drop "comprehensive". Recommendation: (b).
6. ~~Novelty of the two ReCon bugs~~ RESOLVED by Anna (2026-11-09): both are new, so the abstract's "find two bugs" stands. The STL (store-to-load forwarding) bug is Anna's new find; OTB was found by the SimSpect authors and reproduced with SimSpect. The agent's reading of `recon_author_email.txt` was wrong: that email is about something else.

## Part 2: intro.tex, background.tex, model.tex, related.tex

116 comments: 70 CURRENT, 12 STALE, 13 RESOLVED, 21 DEAD. The comments are mostly fine; the bigger problem is body text they show to be outdated (below). Both Recon-STT bugs treated as new findings (Anna, 2026-11-09). All 135 cite keys in these files exist in references.bib. Only the two gray `\labnote`s (intro:70, :74) are visible in the current build. Papers checked are in `~/Documents/quail/sources/papers/`; SpecCheck (McKevitt et al., PACT'23) was fetched and saved there as `mckevitt-2023-speccheck.pdf`; Cheang et al. read from ePrint 2019/310.

| file | comments | current | stale | resolved | dead |
|---|---|---|---|---|---|
| intro.tex | 27 | 9 | 3 | 8 | 7 |
| background.tex | 13 | 10 | 2 | 0 | 1 |
| model.tex | 9 | 3 | 0 | 0 | 6 |
| related.tex | 67 | 48 | 7 | 5 | 7 (commented cut-list blocks, kept on purpose) |

### Table (every comment; similar ones grouped)

| file:line | comment (excerpt) | class | evidence | action / replacement |
|---|---|---|---|---|
| intro:2 | \reviewtag "Reordered the intro… no wording changed" | CURRENT | order now matches the tag | delete once Anna accepts the order |
| intro:3, :6 | outline headings | DEAD | paragraphs :4, :7 written | delete; body :7 says "We consider the class of defenses with some hardware component" twice — cut the last sentence |
| intro:12 | `% not cycle accurate` | DEAD | fragment | delete, or develop into a Discussion point |
| intro:15 | `\todo{cite the spectre benchmarks}` | RESOLVED | :31 cites kocher2018msvc, canella2019systematic | delete; also move :14's \cite{spec2017} after "running benchmarks and checking their architectural outputs" |
| intro:17 | old "three reasons" + \anna notes | DEAD | replaced by :14; term question still open (URGENT_TODO.md:73, :83) | delete |
| intro:19 | \anna{validation not verification} | RESOLVED | :14 says it | delete |
| intro:22-24 | commented VOCAB "KEEP speculation contracts" | RESOLVED | :21 keeps the term | delete |
| intro:25 | `%claude please triple check… citations` | RESOLVED | all 10 keys at :21, :31 are the right papers | **delete now — names Claude in source the advisor reads.** Gap: Pensieve (bib:1848) missing from :21's list |
| intro:26-30 | outline bullets | DEAD | now prose :31-36 | delete |
| intro:32 | \reviewtag "Added these two cites…" | RESOLVED | bib:2935-2938, 2542-2546 | delete. Body :33 misdescribes AMuLeT ("two randomly generated architecturally identical tests"); AMuLeT Def. 2.1 is one program on two inputs with equal contract traces (fu-2025-amulet.pdf §2.3) |
| intro:38 | \reviewnote CUT ONE | CURRENT | :20 and :36 both still there | do it |
| intro:40 | \anna{stt running mini example figure 1??} | STALE (half done) | Fig. 1 is the gap figure, not an STT example | R1 |
| intro:41 | change-log comment | RESOLVED | — | delete when accepted |
| intro:43 | \anna{fix this paragraph its bad} | CURRENT | :44 unchanged | optional: "SimSpect validates a defense's simulated hardware implementation against the defense's own security guarantee, specified as the attacks the defense blocks. The specification is precise to those cases and drives test generation; using it to prove a higher-level security property is future work." |
| intro:46 | \reviewnote ADD "(Fig.~\ref{fig:intro})" | CURRENT | label exists, unreferenced | do it |
| intro:50 | \reviewnote REWORD "Unlike AMuLeT…" | CURRENT | :48 unchanged | do it |
| intro:54 | \reviewnote MOVE future-work paragraph? | CURRENT | open (URGENT_TODO.md:78) | Anna's call |
| intro:67 | \reviewnote FIX (no final period, mixed list) | STALE | form fix still needed; list out of date | R2 |
| intro:70 | \labnote "AMuLeT comparison results are being updated" | CURRENT | parity runs T1-T5 not run (EVAL_MANIFEST.md:225-229) | keep; optionally say "500 of AMuLeT's STT tests" at :72 |
| intro:74 | \labnote "InvisiSpec, SpecLFB and CleanupSpec results still to be inserted" | CURRENT | eval NOT RUN, interim finds exist | optional R13 |
| intro:76 | \anna{bring in the results better} | CURRENT | waits on re-run | keep |
| intro:77, :78 | todo sentences (gem5 runs, defenses expressed) | RESOLVED | done at :64, :63 | delete (but :63-64 content is stale, see body flags) |
| intro:80 | \anna{scope + performance number} | STALE (half) | no speed number supportable yet (URGENT_TODO.md:106; STATUS.md:30) | R3 |
| intro:81-82, :84-91 | fragments; commented Deliverables + \caroline | DEAD | proposal-era | delete |
| bg:5 | \auditnote ADD SPT sentence + REWORD STT ending | CURRENT | quotes verified (SPT, STT abstracts); REWORD also fixes :3 ("until they are non-speculative") | adopt both |
| bg:9 | \reviewnote check ReCon sentence | CURRENT | :7 matches the ReCon abstract | delete after reading |
| bg:13 | \auditnote ADD InvisiSpec/CleanupSpec/SpecLFB + store-bypass | CURRENT (2 caveats) | AMuLeT §4.5-4.7 verified | (a) gem5 SpecLFB bounces/replays misses, never parks them in the LFB (URGENT_TODO.md:176) — keep out of Results; (b) our STT row is branch-only and STL tests run only on Kaxiras-group builds (URGENT_TODO.md:55) — write "All of these designs" |
| bg:15 | \urgentnote VOCAB leakage-contracts paragraph | CURRENT (decision) | AMuLeT §2.2-2.3, rtl2upath verified | decision 4 |
| bg:21 | \auditnote "yaos-micro-paper missing" | STALE (partly) | rtl2upath now cited; bib line refs wrong; unfinished clause + Revizor overclaim remain | R4 |
| bg:25, :28, :34, :36 | \anna (uarch state; cite arm/simner; cite checkmate/LCM; more on modeling executions) | CURRENT | keys exist | add cites / keep |
| bg:30 | \auditnote "Key alloy missing… cite Torlak and Jackson" | STALE (partly) | jackson2002alloy now cited; missing period; no `kodkod` bib entry though Fig. 3 names Kodkod | R5 |
| bg:32 | \anna{replace, cite wickerson} | CURRENT | Lustig's full relaxation set is RI, DMO, DF, DRMW, RD, DS (§3.1-3.2); :32 lists a subset | keep |
| bg:37 | draft bridge sentence | DEAD | — | reuse as :39's closing (updated for two stages) or delete |
| bg:39 | \auditnote WRITE MORE (axiomatic modeling) | CURRENT | — | update "minimal litmus enumeration": Stage 1 enumerates RI-only minimal cores, Stage 1.5 loosens them |
| model:2 | \anna{comprehensive??} | CURRENT | Alloy specs only for STT, ReCon, SPT; InvisiSpec/CleanupSpec/SpecLFB use STT_6 as stimulus; NDA/DoM/Doppelganger no model (EVAL_MANIFEST.md:306) | drop "comprehensive" (decision 2) |
| model:13-18 | commented duplicate definitions | DEAD | — | delete. Body :9 calls the protection set "architectural state (memory and registers)" but SPT_6_oneLP_v2.als:375 protects values (decision 3) |
| model:19, :22 | todo sufficiency / scope of defenses | CURRENT | open (URGENT_TODO.md:88) | merge (decision 2) |
| model:32 | commented STT leakage/protection description | DEAD (stale content) | STT_6.als:327-331 differs | delete; body :26-30 matches STT_6.als today, but :30 is the location-based rule flagged by R-1 (URGENT_TODO.md:37) |
| model:34-50 | empty subsections, commented figures | DEAD | fig:pipeline is now Fig. 3 | delete |
| rel:3, :5, :11, :17 | structure/pass notes | CURRENT | counts verified (33 kept, 82 cut) | keep until VI is prose; delete :17 with :5 |
| rel:7, :58 | SpecCheck "closest gem5-based tool" | CURRENT (sharpen) | SpecCheck = FSM monitor in gem5 O3 commit, flags vulnerable transient windows in programs on an unmitigated core (PACT'23 abstract, §I) | note text: "a gem5 O3 commit-stage monitor that flags vulnerable transient windows in programs on an unmitigated core; it tests programs, not a defense implementation" |
| rel:9 | "…as in SynthLC" | CURRENT (cite trap) | SynthLC is in rtl2upath; bib key `synthlc` is Wang et al. CCS'25 | cite SynthLC as \cite{rtl2upath} |
| rel:13 | (4) execution models | CURRENT | 3 of its 5 papers sit under part (2) | move when writing |
| rel:15 | (5) "…see the intro note" | STALE | no such intro note now | R6 |
| rel:21 | \auditnote structure problems | STALE (refs) | claims hold; line refs moved | R7 |
| rel:26 | \auditnote "leaves out nearest prior work" | RESOLVED | 11-03 triage made every paper a CITE note; `transform` key is now hossain2020transform | delete; keep its SNI point: add \cite{guarnieri2020spectector} at body :90-91 |
| rel:31 | VOCAB "flagging a violation" → "contract violation" | CURRENT | AMuLeT Def. 2.1 | do it |
| rel:50-68 | CITE UPEC, SpecDoctor, IntroSpectre, Scam-V, S&P'26, AMuLeT, Revizor, Hide and Seek, Contract Shadow Logic | CURRENT | bib entries match | keep |
| rel:70, 122, 144, 176, 202, 222, 231 + blocks 72-86, 124-135, 146-169, 178-181, 204-206, 224-230, 233-256 | CUT LIST notes + commented blocks | CURRENT / DEAD on purpose | counts match | delete all once VI is prose |
| rel:92, :187 | reviewtags (S&P 2021 original; SPO→SDO) | RESOLVED | sdo now cited twice (:186, :188) | delete; drop the second sdo |
| rel:94 | VOCAB "Hardware–software leakage contracts" → "Hardware–software contracts" | CURRENT | body :90 unchanged | do it + add Spectector cite for SNI |
| rel:97, :211 | todos (contract/SNI works; litmus + fuzzing cites) | RESOLVED | covered | delete when writing |
| rel:102 | CITE guarnieri2021contracts "clauses mirror its contract notions" | STALE | contradicts bg:15 and FIGURES.md:254 | R8 |
| rel:104 | CITE spectector "semantic baseline for a leak" | STALE | intro:34 contrasts SNI with SimSpect's predicate | R9 |
| rel:106 | CITE cheang2019formal "(trace property)" | STALE (inaccurate) | it defines TPOD, an observational-determinism property (CSF'19) | R10 |
| rel:108-120 | CITE Code That Never Ran, Cats vs Spectre, InSpectre, Cauligi SoK, LCM, LeaVe | CURRENT | venues match | keep |
| rel:118 | CITE synthlc NOTE first author | STALE (partly) | NOTE resolved; key collides with SynthLC | R11 |
| rel:136, :170, :138-142, :172 | proposed subsections; CITE RTLCheck, memalloy, Herding Cats, RTL2MµPATH | CURRENT | — | keep; add "(includes SynthLC)" to :172 |
| rel:174 | CITE pensieve "against contracts" | STALE (imprecise) | Pensieve checks against SNI and targets early-stage defenses | R12 (decision 5) |
| rel:189 | \todo tighten defense citations | CURRENT | SpecShield, DoM uncited at :185-186 | do it; bullet itself stale |
| rel:192-200 | defense breaks / SoKs | CURRENT | venues match; timed STL attack relates to the Recon-STT STL finding | keep |
| rel:214-220 | CITE MeltdownPrime, TransForm, Lustig, CheckMate | CURRENT | — | keep |

### Paste-ready replacements

R1 (intro:40): `\anna{STT running mini example: add it as its own figure or drop the idea (Fig.~1, the gap figure, now sits right below this paragraph)}`

R2 (intro:67): `\reviewnote{\textbf{FIX + UPDATE}: this sentence has no final period and mixes ``finding'', ``as well as'' and ``and reproducing''; write one sentence per bug. Its content is also out of date, and every eval row will be re-run on the two-stage test sets, so treat all counts as interim. (1) The visibility-point--squash race leaks only under the slow-commit latency setting, which is not in the eval set, and whether it counts under the current window is still open; ``shared by STT and SPT'' is not yet confirmed for SPT. (2) The store-to-load forwarding bypass in the ReCon group's STT is re-confirmed on the fixed harness (91 of 94 load tests in the latest sample). (3) The oldest-operand taint bug is now reproduced by the pipeline itself: an opt-in two-source merge in concretization makes 100 of 100 eligible tests leak on the ReCon group's STT, and 0 of 100 leak without it. (4) Not listed yet: STT drops taint through register xmm4 (98 of 100 tests leak, 0 of 100 through xmm3), and a new SpecLFB bug in which a direct jump after an unresolved branch clears that branch's shadow (148 tests). (5) On the AMuLeT builds the interim runs find InvisiSpec UV1, CleanupSpec UV4 (UV3 only with a cold cache) and SpecLFB UV6; ``far fewer tests than prior work'' needs the AMuLeT-parity runs. (6) The runs labelled ReCon used classic caches, where ReCon's reveal never takes effect, so they test the ReCon group's STT, not ReCon.}`

R3 (intro:80): `% \anna{performance number: state one only from the AMuLeT-parity runs (AMuLeT's own flags and cache sizes), which have not run yet; the SpecLFB first-detection counts (test 6 vs 39) predate the harness fix}`

R4 (background:21): `\auditnote{cite}{cite, high}{The sentence before this note still ends in the unfinished clause `due to the wide availability', and Revizor tests commercial black-box CPUs against speculation contracts, not a defense's advertised guarantee. The intro's prior-work sentence (``Existing validation either tests fabricated CPUs\ldots'') now says this with the full cite list, so point back to it or reuse it here. \textbf{PROPOSED TEXT}: Prior work validates side-channel security on fabricated CPUs~\cite{revizor,oleksenko2023hideseekspectresefficient} and on RTL designs~\cite{rtl2upath,contractshadow,hur2022specdoctor}.}`

R5 (background:30): `\auditnote{cite}{cite, high}{The sentence before this note has no final period, and Fig.~3 names the Kodkod model finder, which has no bib entry yet. \textbf{PROPOSED TEXT}: They use the Alloy Analyzer~\cite{jackson2002alloy,kodkod} to generate every minimal test that their MCM forbids. New bib entry \texttt{kodkod}: E.~Torlak and D.~Jackson, ``Kodkod: A relational model finder,'' TACAS 2007 (as cited in Lustig et al., Sec.~4.1, and CheckMate, ref.~[33]).}`

R6 (related:15): `\auditnote{cite}{related}{(5) \emph{Spectre hardware defenses}: the defenses you test, and the classes of the rest (delay or taint-track, invisible speculation, undo, data-oblivious; their cites are in the intro's second paragraph).}`

R7 (related:21): `\auditnote{write}{writing}{Structure problems. Related Work is still bullet points, and AMuLeT is described four times (intro, II-B, V-B, VI-A). The intro's first description still says AMuLeT runs ``two randomly generated architecturally identical tests''; AMuLeT runs one program on two inputs whose contract traces match (its Def.~2.1), as the intro's next sentence already says. The Results split the AMuLeT comparison across V-B, V-C and V-E, and V-F repeats the load gate from IV-C3. The paper has no Conclusion, and the Acknowledgments placeholder must go for double-blind review. \newline \textbf{PROPOSED TEXT}: Write VI as prose. Keep one AMuLeT description in VI-A (move II-B there). Merge V-B, V-C and V-E into `Comparison with AMuLeT' and fold V-F into V-A. Add a short Conclusion and delete the acknowledgments for submission. \newline \textit{Source:} related.tex:17 `\% Bullets for now'; intro.tex:33--34; background.tex:23; results.tex:195--273; fu-2025-amulet.pdf Def.~2.1; bare\_conf\_compsoc.tex:604--613.}`

R8 (related:102): `\auditnote{cite}{related}{\textbf{CITE}~\cite{guarnieri2021contracts}: Published S\&P 2021 hardware--software contracts (an observation clause and an execution clause per instruction). Map our three components onto its two clauses once, in the leakage-contracts paragraph proposed for Sec.~\ref{sec:bg-defenses}, and point back to it here; the protection set has no counterpart in a contract.}`

R9 (related:104): `\auditnote{cite}{related}{\textbf{CITE}~\cite{guarnieri2020spectector}: Defines speculative non-interference (SNI) and checks it on software by symbolic execution. Cite it as the end-to-end relational property that \toolname{}'s per-execution leakage predicate is contrasted with (as the intro does), not as what a leak means in \toolname{}.}`

R10 (related:106): `\auditnote{cite}{related}{\textbf{CITE}~\cite{cheang2019formal}: Early formal definition of secure speculation as an information-flow property, trace-property-dependent observational determinism (TPOD); background for what it means for a defense to prevent speculative leakage.}`

R11 (related:118): `\auditnote{cite}{related}{\textbf{CITE}~\cite{synthlc} (already in the bib): Wang et al., CCS 2025, synthesis of sound and precise leakage contracts for open-source RISC-V processors. Despite its key, this entry is not SynthLC: SynthLC (Hsiao et al., MICRO 2024) is in the RTL2M$\mu$PATH paper, \texttt{rtl2upath}. Consider renaming this key.}`

R12 (related:174): `\auditnote{cite}{related}{\textbf{CITE}~\cite{pensieve} (already in the bib): models early-stage defense designs and checks them against speculative non-interference by bounded model checking. It is the prior work closest to our early-stage framing, so say the difference: it checks a model of the design against a generic property, while \toolname{} tests the simulated implementation against the defense's own guarantee.}`

R13 (optional, intro:74): `\labnote{InvisiSpec, SpecLFB and CleanupSpec results still to be inserted here; interim runs already find InvisiSpec UV1, CleanupSpec UV4 and SpecLFB UV6, plus a new SpecLFB bug.}`

### Body text the comments show to be out of date

- **intro:63** "We have expressed seven hardware defenses… STT, SpecShield, NDA, DoM, SDO, SPT, and ReCon": Alloy specs exist only for STT, ReCon, SPT; NDA/DoM/Doppelganger have no model (EVAL_MANIFEST.md:306); SpecShield and NDA exist only as old-syntax comments (PAPER_PLAN.md:222); SDO never built (EVAL_MANIFEST.md:210-215). Decision 2.
- **intro:64** "gem5 implementations of… ReCon": those runs used classic caches, where ReCon's reveal never takes effect, so they test Recon-STT (BUGS.md:24; EVAL_MANIFEST.md:195). Suggested: "…of STT and SPT, on the ReCon group's implementation of STT, and on the AMuLeT builds…".
- **intro:33** AMuLeT parenthetical → "(running one random program on pairs of inputs whose contract traces match, and checking for differences in a limited part of the $\mu$arch state)". Also move intro:14's spec2017 cite; cut the duplicate sentence at intro:7.
- **background:3** STT sentence inaccurate (adopt bg:5 REWORD); background:19 unfinished clause (R4); background:28 missing period (R5).
- **model.tex:9, :30** depend on decision 3. Option (b) text: at :9 "A protection set is the set of data (the values that instructions read or produce) that the defense promises not to leak speculatively, with an update rule for how each instruction changes it"; at :30 "The value read by every speculative load; nothing is removed", citing STT's "If a load is unsafe, its output is always tainted" (yu-2019-stt.pdf p6).
- **related:90-91** credits SNI to the contracts paper and says "leakage contracts": cite Spectector for SNI; apply rel:94.
- **related:185-188** says SimSpect "expresses and tests" SpecShield, NDA, DoM, SDO and omits ReCon, InvisiSpec, CleanupSpec, SpecLFB, Doppelganger. Option (a) text: "The hardware defenses \toolname{} expresses: STT~\cite{yu2019stt}, ReCon~\cite{recon} and SPT~\cite{spt}; it also tests InvisiSpec~\cite{yan2018invisispec}, CleanupSpec~\cite{saileshwar2019cleanupspec} and SpecLFB~\cite{cheng2024speclfb} with STT's test set and a defense-specific transmission mechanism."

### Fix first (part 2)

1. intro:25 — delete (names Claude; check done).
2. intro:63-67 — findings list out of date (R2); defense count unsupported.
3. related:185-188 — stale defense list.
4. model.tex:9, :30 — protection-set semantics inconsistent across models (decision 3).
5. related:9, :118 — `synthlc` key cites the wrong paper for SynthLC.
6. related:102, :104, :106, :174 — inaccurate characterizations (R8-R12).
7. background:21, :30 — unfinished clause, missing period, missing Kodkod bib entry.
8. intro:33 — AMuLeT misdescription.

### Decisions surfaced (part 2)

1. Which findings the intro claims and how the race is framed (intro:64-67). Options: (a) list every verified bug now, counts marked interim; (b) write it only after the two-stage eval; (c) (a) plus a labelled slow-commit eval row so the race has fixed-harness evidence. Evidence EVAL_MANIFEST.md:210-212, BUGS.md, URGENT_TODO.md:74, :105, :147, :163, BUG_TAXONOMY.md:120-132. Recommendation: (c) — count xmm4 and SpecLFB jump, keep both Recon-STT bugs as new, take final numbers from the eval. (Overlaps Part 1 decisions 1-3.)
2. Defense count and what "expressed" means (intro:63; model:2, :19, :22; related:185). Options: (a) three expressed (STT, ReCon, SPT) + three tested with STT's tests and their own transmission mechanism; (b) write more defense specs before submission (NDA likely dropped under the authorship rule, URGENT_TODO.md:14); (c) keep "seven" as paper-level specs in a Sec. III table, saying only three are Alloy models. Recommendation: (a); it also resolves "comprehensive??".
3. Protection set: locations or values? SPT v2 protects values (SPT_6_oneLP_v2.als:375); STT_6 protects locations and unprotects on any non-spec load, which loses leaks STT forbids (MODEL_AUDIT_SPT_RECON.md:79-82); drafts STT_6_v2/Recon_6_v2 switch to values (URGENT_TODO.md:37, :40, :44). Options: (a) keep locations as a scope choice; (b) approve v2, define the protection set as values; (c) define it abstractly with a per-model table. Recommendation: (b). Ties into the ultimate-model work in `STAGE1_alloy/models/proposed/ultimate/`.
4. Terminology vs Guarnieri/Revizor/AMuLeT (bg:15, rel:9, rel:102). Options: (a) keep our terms + add the bg:15 paragraph citing SynthLC's sense of "leakage contract"; (b) adopt observation/execution clause; (c) code names. Recommendation: (a), and fix discussion.tex:6 (still says speculation contract / leakage function).
5. "First"/"only prior" claims (intro:21, :33, :40; background:23; related:24). Pensieve model-checks early-stage designs against SNI; SpecCheck monitors programs on an undefended core. Options: (a) keep "first… for early-stage prototypes" + contrast sentence; (b) narrow to "first to test a defense's simulated implementation against the defense's own guarantee" (what Fig. 1 already says). Recommendation: (b) + Pensieve/SpecCheck contrast in VI-A.
6. Completeness wording (intro:40, :56, :58). Stage 1 exhausted for STT_6_stl (306) and nearly STT_6 (129); SPT v2 caps at 200,000 at size 4; Stage 1.5 capped by design; OTB needs Stage 2; minimality excludes S4/A3c (claudelog.md:91). Options: (a) bounded-exhaustive over minimal cores for families whose Stage 1 exhausts, no completeness for fleshed-out/concretized/interleaved tests; (b) "targeted and capped"; (c) decide after SPT Stage 1 reruns on v3. Recommendation: (a) with SPT's status stated. (Overlaps Part 1 decision 5.)

## Part 3: pipeline.tex, methodology.tex, oldtechnicaldetails.tex, pendingfigures.tex

> **Line-number drift:** every `URGENT_TODO.md:N` cited in Part 3 (including inside R1-R13) was written before two lines were inserted at :11-12, so add 2 (e.g. :36 → :38, :54 → :56, :174 → :176). Exceptions: "URGENT_TODO.md:31" and ":44" where they quote the paper note's own old reference. Before pasting a note into the paper, cite URGENT_TODO items by title, not line. Also: Part 1 decision 5 ("bounded-exhaustive") needs the STT/ReCon-only qualifier from H3, and Part 1 decision 1 ("found by SimSpect") aligns with H1 — OTB was reproduced only via the opt-in fanout v2 OTB merge.

**Bottom line.** `sections/pipeline.tex` has 98 comments: 43 CURRENT, 15 STALE, 12 RESOLVED and 28 OBSOLETE/DEAD. `methodology.tex` has none; it is only `\input{sections/model}` and `\input{sections/pipeline}` (methodology.tex:1-2). Neither `oldtechnicaldetails.tex` nor `pendingfigures.tex` renders, so every comment in them is DEAD/OBSOLETE.
- **The stale notes cluster around four changes:**
  - the 2026-11-08 decision that Stage 1 minimality is RI-only, plus the Stage 1 and Stage 1.5 runs now on cafe2;
  - the rf fact added to every in-use model (2026-11-09), and SPT v2 becoming the production SPT model;
  - the round-3 OTB merge (2026-11-08): SimSpect now reproduces the getOldestTaint bug through fanout v2, not through chain interleaving;
  - the footprint defenses moving to `check_footprint` with the 2026-11-08 per-paper scope decision.
- **The worst live problem is the stall values at pipeline.tex:226.** The text says s_U = 0 and a commit stall of {0,150}, which contradicts :158 and Table II. The only two notes flagging it (:227, :228) are commented out, so nothing visible marks it.
- **"claude" appears in paper source the advisor can read:** pipeline.tex:169 ("@claude", a commented note) and oldtechnicaldetails.tex:1 and :113 (Anna's own notes, in a dead file).

**Build context.**
- The note-hiding switches at bare_conf_compsoc.tex:351-353 are on, so none of these notes appear in the current PDF; only `\labnote` is shown (:354 is commented out).
- methodology.tex is live (bare_conf_compsoc.tex:456).
- pendingfigures.tex is dead: its `\input` is commented out at bare_conf_compsoc.tex:460.
- oldtechnicaldetails.tex is `\input` nowhere (checked bare_conf_compsoc.tex, all sections, and main.tex, which inputs nothing).

**Coordinator's ReCon-STT correction applied.** Both ReCon-STT bugs are treated as new findings. Nothing below adds a novelty caveat, and recon_author_email.txt is not cited. OTB is described as found by the authors and reproduced by SimSpect.

**Concurrent edit.** URGENT_TODO.md was edited by another session during this audit. Every URGENT_TODO line cited below was re-checked after that edit.

### Summary counts

| file | CURRENT | STALE | RESOLVED | OBSOLETE/DEAD | total |
|---|---|---|---|---|---|
| sections/pipeline.tex | 43 | 15 | 12 | 28 | 98 |
| sections/methodology.tex | 0 | 0 | 0 | 0 | 0 |
| sections/oldtechnicaldetails.tex (dead file) | 0 | 0 | 0 | all (11 grouped rows) | ~50 comment lines |
| sections/pendingfigures.tex (dead file) | 0 | 0 | 0 | 6 | 6 |

Line references: simspect paths are relative to `~/trippel/simspect`; paper paths to `~/trippel/ISCA-27`.

### pipeline.tex

| file:line | comment (excerpt) | class | evidence | action |
|---|---|---|---|---|
| pipeline.tex:3 | `\anna{hardware under test??}` | CURRENT | Anna's open wording question about "defense hardware implementation" (:3) | Anna's call |
| pipeline.tex:4-5 | `\anna{delete commented i think:}` + `% We designate the design dimensions…` | DEAD | the same three classes now live in the knobs subsection (:316) | delete both lines |
| pipeline.tex:7-8 | `% \input{tikz/pipeline_full_8pt1col}`, `% \input{tikz/pipeline_full}` | DEAD | the 8pt figure is input at :57; pipeline_full is the retired 7pt version | delete |
| pipeline.tex:9 | `% \figtodo{two versions of the pipeline figure… keep one}` | RESOLVED | only pipeline_full_8pt1col is input (:57) | delete |
| pipeline.tex:12 | `% Once we have a formal model…` | DEAD | old opening sentence | delete |
| pipeline.tex:20 | auditnote: Recon_6 and SPT_6_oneLP lack rf_from_most_recent_writer; SPT exactly-one-LP; "DECIDE in URGENT_TODO.md:31" | STALE | the rf fact was applied to Recon_6 and 6 other files on 2026-11-09 (URGENT_TODO.md:39, :43; Recon_6.als:163). The production SPT is SPT_6_oneLP_v2 (URGENT_TODO.md:122): it has the fact (:184) and asks for ≥1 leaker ([v2-3], :346). Still different: operand typing (:253-266) and the Recon_6.als:239 `[p]` call site. The DECIDE it cites moved to URGENT_TODO.md:94 | replace with **R1** |
| pipeline.tex:22 | `\anna{add citations}` | CURRENT | only herdingcats and lustig are cited; background.tex:39 proposes a citation thread | Anna's call |
| pipeline.tex:23 | `% \figtodo{cite… Fig.~\ref{fig:ddi-rf} here; … says I3, the figure now says i3}` | OBSOLETE | the figure is cited at :22; the I3/i3 issue is the live note at :52 | delete |
| pipeline.tex:26, :38 | urgentnote VOCAB ADD DEFINITION: spo; rf/ddi | CURRENT | Table I defines spo, rf and ddi (tikz/execvocab_v2_8pt.tex:33), but the text uses them undefined (:24, :36); spo is defined only at :74; URGENT_TODO.md:83 | keep; could be met with "(Table~\ref{tab:execvocab})" |
| pipeline.tex:30 | urgentnote VOCAB ADD DEFINITION resolved/committed | STALE | Table I defines committed but not resolved (execvocab_v2_8pt.tex:28). Anna decided on 2026-11-08 that "a branch that has executed but not yet squashed counts as unresolved" (URGENT_TODO.md:30); the proposed "outcome is known" misses that | replace with **R2** |
| pipeline.tex:34 | auditnote: only resolution is enforced; commit is measured; fnc stall 0 | CURRENT | fnc_commit_stall_cycles is 0 in runconfigs/fixed_20261030/STT_6_sttmaster_fixed_latest.jsonc:47, STT_6_reconmodded_fixed_latest.jsonc:44 and runconfigs/footprint/*; check_ld.py:95-114 is unchanged | keep |
| pipeline.tex:42 | auditnote: "Figure \ref{tab:execvocab}" prints "Figure I" | CURRENT | body :40 is unchanged | keep |
| pipeline.tex:44 | `% \figtodo{new vocabulary table… reference it here}` | RESOLVED | the table is input at :18 and referenced at :40 | delete |
| pipeline.tex:49 | auditnote (high): the protection set is not "as updated by the most recently committed instruction" | CURRENT | STT_6.als:232-243, :330-331 are unchanged. The pending instance-based STT_6_v2 (URGENT_TODO.md:37, :40) would change the definition again | keep; finalize after H5 |
| pipeline.tex:52 | auditnote: I1/I2/I3 in the text vs i1-i3 in the figure | CURRENT | body :50 and :54 still use `\texttt{I3}`, `\texttt{I1}`, `\texttt{I2}` | keep |
| pipeline.tex:56, :101, :165, :255 | trailing provenance `% …` on live `\input` lines | OBSOLETE | harmless housekeeping | optional delete |
| pipeline.tex:59 | auditnote: "non-invasive" overstates; "drop the 'selects hooks' arrow, or label it 'design time'" | STALE | Anna decided the arrow stays, labelled "selects hooks", with the text saying it is design-time (URGENT_TODO.md:97). The "non-invasive" wording is still open (:107). The figure says "+ Non-invasive harness" (tikz/pipeline_full_8pt1col.tex:230). New: per-test hot/cold cache on CleanupSpec and SpecLFB (Anna, 2026-11-09, URGENT_TODO.md:167) | replace with **R3** |
| pipeline.tex:61 | auditnote (high): "bounded-exhaustive" contradicts the results; every testset stops at 100k | STALE | RI-only Stage 1 (up to 6 instructions) reaches UNSAT for STT_6 (129 cores), Recon_6 (129, from the pre-rf-fact core, needs a rerun), STT_6_stl (306) and Recon_6_stl (858); the k6 transmitter partitions were still running as last logged. SPT v2's k4 partition caps at 200,000 (EVAL_MANIFEST.md:40-48; URGENT_TODO.md:36). The flat testsets_latest hold 150,000 per mode, not 100k (EVAL_MANIFEST.md:279) | replace with **R4** |
| pipeline.tex:63 | auditnote (high): Stage 1.5 is an STT-only prototype that produced no results | STALE | Stage 1.5 was decided to be a real stage (URGENT_TODO.md:95) and is running: STT_6_stl is done with 266,946 graphs (306 cores × 981 cap), about 300,000 per family (EVAL_MANIFEST.md:50-58). No paper number comes from it yet | replace with **R5** |
| pipeline.tex:65 | auditnote: harness changes prediction and timing; "open item in URGENT_TODO.md:44" | CURRENT | content holds (RESOLUTION_HOOKS.md §1 edit 4). The open item is now URGENT_TODO.md:107; :44 is a model-fixes DECIDE | keep; fix the cite to :107 and add the 2026-11-09 cache decision |
| pipeline.tex:67 | auditnote: "Inspector" vs "checker"; Stage 1 and 1.5 titles | CURRENT | the figure says "Inspector" (pipeline_full_8pt1col.tex:243) and "Abstract test generation/enumeration" (:151, :179); Fig. 7 says "the checker" (checkerwindow_v4_8pt.tex:172). "Inspector" was decided for the figure (URGENT_TODO.md:100) | keep; align the text with "Inspector" or rename the box |
| pipeline.tex:69 | auditnote: the caption explains only blue | CURRENT | caption unchanged (pipeline_full_8pt1col.tex:269-270) | keep |
| pipeline.tex:76 | auditnote: well-formedness facts are not shared (rf fact missing) | RESOLVED | the rf fact is now in STT_6.als:163, Recon_6.als:163 and SPT_6_oneLP_v2.als:184. Lines 1-200 of STT_6 (comments stripped) are identical to SPT v2 and to Recon_6; operand typing belongs to the leakage machinery, not well-formedness | delete. The body's "defense-agnostic" (:74) now holds for the regenerated testsets; testsets_latest/Recon_6 predates the fact (claudelog 2026-11-09) |
| pipeline.tex:80 | auditnote (high): RI/RO never applied; "DECISION for Anna" | STALE | decided 2026-11-08: Stage 1 = RI on top of RR, RC+RR and RS (URGENT_TODO.md:54; STT_6_core_ri.als:289-302); Stage 1.5 = the production model's RR+RC+RS | replace with **R6** |
| pipeline.tex:84 | auditnote: SPT needs exactly one leaking operand | RESOLVED | SPT_6_oneLP_v2.als:12-14, :346 use `not secure_speculation_scheme_p[no_p]` (≥1) | delete |
| pipeline.tex:87 | `% The model describes a space of executions…` | DEAD | sentence fragment | delete |
| pipeline.tex:90 | auditnote (high): no enumeration reached UNSAT; exactly 6 instructions | STALE | Stage 1 uses `but 6` (STT_6_core_ri.als:310) and reaches UNSAT for STT/ReCon; SPT is capped; Stage 1.5 is capped per core (EVAL_MANIFEST.md:40-58) | replace with **R7** |
| pipeline.tex:92 | `% \urgentnote{No production enumeration reached UNSAT…}` | OBSOLETE | commented duplicate of :90 with stale cites | delete |
| pipeline.tex:95-97 | commented prose ("and make claims…", "we follow MCM work…") | DEAD | superseded by :94 and :98 | delete |
| pipeline.tex:103 | auditnote: pane (c) flag on a load; legend for unflagged rows and the dashed edge | CURRENT | pane (c)'s flag is Anna's deliberate choice (URGENT_TODO.md:76 item 2); the caption (tikz/relaxation.tex:119) still has no legend | keep (legend only) |
| pipeline.tex:105, :107 | auditnote (high) + urgentnote: panes (a)/(b) are RO/RI, evaluated models use RR+RC+RS, "depends on D4" | STALE | D4 is decided: RI-only (URGENT_TODO.md:54). Stage 1 removes (b) by RI (STT_6_core_ri.als:301) and (c) by RR. (a) is removed by RS even in the flat model: `o_p` drops every operand on a removed state (STT_6.als:215), and r1 is used only by the unneeded operand. So "Alloy synthesizes (a)" was wrong. This comes from reading the model, not from a run. The cited MANIFEST.md line no longer exists | replace both with **R8** |
| pipeline.tex:109 | `% \figtodo{new relaxation figure…}` | RESOLVED | input at :101 | delete |
| pipeline.tex:116 | reviewtag "[TODO: RC acts on the first uncommitted instruction (STT_6.als:308)]" | RESOLVED | body :115 already says "first uncommitted"; matches STT_6.als:308 | delete after reading |
| pipeline.tex:118 | auditnote: RC = first uncommitted; tested together with RR; fallback | CURRENT | STT_6.als:139, :306-308; same in STT_6_core_ri.als:294-296; the wording half is already applied | keep the proposed RC wording |
| pipeline.tex:127 | auditnote: Fig. 5 ("cannot express") vs Sec. V ("cap") | STALE | with RI-only Stage 1, "no Stage 1 instance contains" is true by construction. Now the mechanism is wrong: interleave is off in every eval config (VOCAB_TABLES.md:368), put an ALU on the transmitter address path 0/1200 times (claudelog 2026-11-08 19:20), and cannot hook onto RI cores (URGENT_TODO.md:46). SimSpect reproduced OTB through fanout_v2.otb (VOCAB_TABLES.md:369; claudelog 2026-11-08 23:50) | replace with **R9** (H1) |
| pipeline.tex:129 | auditnote: branch flags inconsistent across figures | CURRENT | tikz files unchanged since the 2026-11-04 import (ISCA-27 git log) | keep |
| pipeline.tex:131 | auditnote (high): i0/i1 committed, so c0 is not speculative | CURRENT | figure unchanged. The OTB merge puts its load under a resolved but uncommitted branch, as this note asks (VOCAB_TABLES.md:369) | keep |
| pipeline.tex:133 | `% \figtodo{… Stage 2 interleaving round; update this subsection's text}` | RESOLVED | :134 names the Stage 2 round | delete |
| pipeline.tex:136-137 | `% Figure~\ref{fig:statetable}…`, `% \input{tikz/statetable} moved…` | DEAD | statetable exists only in the dead pendingfigures.tex | delete |
| pipeline.tex:143, :176, :194 | reviewtag "[TODO: Applied your requests in this subsection; check it]" | CURRENT | awaiting Anna's read; each subsection still has open notes (:146/:155; :179/:187; :205/:213/:219/:224) | keep until read |
| pipeline.tex:146 | auditnote: branches not picked at random; LLVM emits the compare and jcc | CURRENT | parsexml.py:760-799 (xmit → br_bez) and :805-817 (others → br_cond); default emission is still `br i1` (:2569-2577); opt-in br_cmp puts the jcc in asm | keep; cites drifted (:789-795 → :805-817; :2426-2484 → :2569-2577) |
| pipeline.tex:155 | auditnote: transmitter branch always mispredicted, stall 0 | CURRENT | parsexml.py:760-799; pipeline.py:456-481 | keep; cites drifted from :738-776 / pipeline.py:404-421 |
| pipeline.tex:161 | auditnote: no evaluated model produces Other_x | CURRENT | Otherxs is commented out at STT_6.als:327-328, Recon_6.als:329-330, SPT_6_oneLP_v2.als:376-378; divide promotion is at gem5_common.py:860-935 | keep; cites drifted (Recon :320, SPT_6_oneLP :344, gem5_common :772-852) |
| pipeline.tex:163 | auditnote: Table II "first uncommitted" vs text/Fig. 7 "first non-committed"; proposes "first non-committed" | STALE | the text (:268), Table II (instrtable_v2_8pt.tex:8) and Fig. 7 (checkerwindow_v4_8pt.tex:173) all say "first uncommitted", the glossary's recommendation (URGENT_TODO.md:73 item 5). The proposal is now backwards; the rest stands | replace with **R10** |
| pipeline.tex:167 | auditnote: Fig. 6 "violation" label | CURRENT | resolutiontiming.tex unchanged | keep |
| pipeline.tex:169 | `% \urgentnote{VOCAB: … "no leak" …} @claude this makes no sense wdym` | OBSOLETE | superseded by the live :167. It contains "@claude" in source the advisor reads (CLAUDE.md paper rule) | delete (answer below) |
| pipeline.tex:171 | auditnote: Fig. 6 vs Fig. 10 drawn differently | CURRENT | figures unchanged | keep |
| pipeline.tex:179, :181 | auditnote (capability, not corpus) + auditnote (high) "This is false… capped enumeration fills first" | STALE | both predate RI-only and round 3. Interleave: 0/1200 ALU-on-path, off in eval, cannot hook RI cores (VOCAB_TABLES.md:344, :368; URGENT_TODO.md:46). Minimality, not the cap, drops the second source (URGENT_TODO.md:185-187). Reproduced by fanout_v2.otb: 100/100 vs 0/100 (VOCAB_TABLES.md:369) | replace both with **R11** |
| pipeline.tex:184 | `% \urgentnote{This is wrong per the repo's own analysis…}` | OBSOLETE | commented duplicate of :181 | delete |
| pipeline.tex:187 | auditnote: only register operands share the pool; memory slots are fresh; an unspecified address is not emitted | CURRENT | parsexml.py:1531-1535 (fresh memory slot), :1598-1614 (pool; inputs sample the full pool), :2620-2624 and :2695-2698 (only rf-specified inaddr). Random register naming is the default since 2026-11-08 (batch_generate.py:74) | keep; cites drifted (:1601, :2146); optionally mention random naming |
| pipeline.tex:191 | reviewtag "[TODO: Added this closing sentence for passes 6--7]" | RESOLVED | matches Fig. 3 passes 6-7 (pipeline_full_8pt1col.tex:198-199) and parsexml.py:1782, :2013, :3114 | delete after reading |
| pipeline.tex:199 | urgentnote VOCAB "detect a violation" → "hit" | CURRENT | body :197 unchanged; glossary item 4 open (URGENT_TODO.md:73) | keep |
| pipeline.tex:205 | reviewnote CHECK: control runs not confirmed | CURRENT | fnc stall is 0 in every eval config; there is no annotation-off control; the Unsafe E1 row has never run (EVAL_MANIFEST.md:190) | sharpen with **R15** |
| pipeline.tex:208 | `% \paragraph{Directives passed from concretization.}` | DEAD | dropped heading | delete |
| pipeline.tex:210 | `% \urgentnote{wrong: Stage~2 writes no timing…}` | OBSOLETE | commented duplicate of :213 | delete |
| pipeline.tex:213 | reviewnote FIX: Stage 2 writes no timing; the pairs don't "incorrectly alias" | CURRENT | stalls are injected at Stage 3 (pipeline.py:456-481); STL has one annotation per aliasing load (parsexml.py:3194-3206; URGENT_TODO.md:138) | keep; refine with **R16** |
| pipeline.tex:219 | reviewnote UPDATE: every annotated branch is forced | CURRENT | gem5_common.py:272-335 (resolved → architectural path, others → the other path); body :217 still says "(taken) path" | keep |
| pipeline.tex:224 | auditnote (high): the verdict is an OR over the sweep | CURRENT | pipeline.py:347-353, :556-616 (any_hit, triggered_points, sweep_triggered) | keep; cites drifted (:330-339, :500-558) |
| pipeline.tex:227-228 | `% \urgentnote{these values do not match…}`, `% \reviewnote{CHECK the numbers…}` | CURRENT (but commented out) | body :226 still says s_U = 0 and commit stall {0,150}. The configs use s_R {0,500,2500}, s_U 5000, fnc 0 (STT_6_sttmaster_fixed_latest.jsonc:47-57; footprint configs use points [0]), as does Table II (instrtable_v2_8pt.tex:56, :62, :77). Body :158 says 5000, so the text contradicts itself and nothing visible flags it | restore a live note: **R14**; delete these two lines |
| pipeline.tex:230 | `% \urgentnote{contradicts Speculation Primitive Instrumentation…}` | RESOLVED | :229 now says false-negative, same address | delete |
| pipeline.tex:232 | reviewnote FIX STL direction, or CUT | RESOLVED | fix applied in :229; the optional cut (it repeats :173) remains | delete, or cut :229 |
| pipeline.tex:236 | reviewtag "[TODO: Added the resolve and STL hooks…]" | CURRENT | the added text says "Every build also carries two later hook sets" (:235). STL hooks exist only on /work/gem5-recon-stl, which predates the resolve hooks (rebuild decided, not started), and there is no STL window checker yet (EVAL_MANIFEST.md:344-349) | keep; add **R17** |
| pipeline.tex:240 | auditnote: observation-only prints exist; "on all 8 hooked builds" | CURRENT | hooks v2 are print-only (SIMSPECT_HOOKS.md:3). Resolve hooks are now on 10 builds: the 8 in RESOLUTION_HOOKS.md §1 plus stt-master and recon-ruby3 (claudelog 2026-11-08 21:30). stt-master's hook also mirrors the pending-squash fix (URGENT_TODO.md:19) | keep; change "8" → "10"; cite gem5_common.py:503-525 (was :455-477) |
| pipeline.tex:246-248 | `% \urgentnote{VOCAB: "we report a violation"…}` + 2× `% \notebr` | RESOLVED | :245 already says "we report a hit" | delete |
| pipeline.tex:252 | reviewnote: pick one window name | CURRENT | the figure still says "Unresolved window" (checkerwindow_v4_8pt.tex:151); the window end is open (URGENT_TODO.md:32, :74, :101; H4) | keep |
| pipeline.tex:257 | urgentnote VOCAB: relabel the Fig. 7 window; "violation" → "hit" | CURRENT | checkerwindow_v4_8pt.tex:151, :172 unchanged | keep |
| pipeline.tex:259 | auditnote (high): the example is InvisiSpec UV1, a collateral channel outside InvisiSpec's guarantee | STALE | since 2026-11-08 each footprint criterion checks only the structures its paper claims: UV2 and KV1 are out, the L1D is in (URGENT_TODO.md:174). UV1 is found in 2995/3000 tests via hooks v2 (AMULET_BUGS_DETECTION_ACCOUNTING.md:33). The outdated text is results.tex:195-204 | replace with **R12** (H6) |
| pipeline.tex:261 | auditnote: check_footprint counts any squashed instruction younger than lc | CURRENT | the actor rule "squashed(i) ∧ lc_seq < i.seq" is in specs/leakage/invisispec.json; D2 is open (URGENT_TODO.md:140). New: in 802 of 2883 UV1 hits only non-transmitter loads leak (AMULET_BUGS_DETECTION_ACCOUNTING.md:74) | keep; add the 802/2883 figure |
| pipeline.tex:263 | `\figtodo{new checker-window figure… check the window name and signals}` | RESOLVED | the figure is input at :255; the checks are the live notes :252, :257, :289 | delete |
| pipeline.tex:266 | `% \textit{Source:} STAGE3_gem5/check_ld.py:110-114; …` | DEAD | a pasted note tail | delete |
| pipeline.tex:270 | reviewnote REWORD: "guarding branches" → "branches the model marks unresolved" | CURRENT | gem5_common.py:950-983 skips correctly_not_taken branches; gate at :1023-1083 | keep |
| pipeline.tex:274 | urgentnote VOCAB "is a violation;" → "is a hit;" | CURRENT | body :272 unchanged | keep |
| pipeline.tex:279-280 | `% \input{tikz/xmitcriteria_8pt}`, `% \figtodo{transmission-criteria table…}` | DEAD | hidden by Anna on 2026-11-03; the criteria-JSON DECIDEs are open (URGENT_TODO.md:85, :99) | Anna's call |
| pipeline.tex:283 | urgentnote VOCAB: define violation / hit / leak / bug | CURRENT | glossary item 4 open (URGENT_TODO.md:73) | keep |
| pipeline.tex:289 | auditnote: the load signal is the Executing-load tick; memaccess/expose belong to separate per-build checkers | STALE | the first part holds (check_ld.py:30-37, 85-87, 130-146). But the footprint rows E12-E14 now use check_footprint over hooks-v2 events (run_config_STT_6_speclfb_footprint.jsonc:44, with `legacy_checker` at :62; EVAL_MANIFEST.md:201-204). New RMW micro-op caveat (URGENT_TODO.md:168) | replace with **R13** |
| pipeline.tex:292 | `% This data-obtained gate is essential…` | DEAD | accurate (check_ld.py:116-129) | delete, or restore as text |
| pipeline.tex:299 | reviewtag "[TODO: Finished this sentence]" | CURRENT | the sentence is accurate (check_other.py:36-41; gem5_common.py:902-935), but no evaluated model has Other_x (:161) | keep; consider cutting the bullet |
| pipeline.tex:300 | `% ; a speculative divide fault is promoted…` | DEAD | folded into :298 | delete |
| pipeline.tex:303 | `% \urgentnote{there is no store checker…}` | OBSOLETE | commented duplicate of :305 | delete |
| pipeline.tex:305 | reviewnote: no store checker; only SPT makes stores transmit | CURRENT | pipeline.py:313-320 (was 296-303); SPT_6_oneLP_v2.als:378 (Stores.inaddr); E11 says `str` has no checker (EVAL_MANIFEST.md:200); STT stores are out of scope (URGENT_TODO.md:11, :26) | keep; refine with **R18** |
| pipeline.tex:310 | reviewnote: typo in the opening quote | CURRENT | :308 still has `''branches` | keep |
| pipeline.tex:313, :317, :319 | `% … optional data-taint gate`, `% The rule that governs the rest…`, `% --- is fixed, while every knob…` | DEAD | no checker has a data-taint gate; :317 is a broken fragment; :319 is the "never tuned" principle | delete (restore :319's idea if wanted). Also :318: a `\notebr` with no note (harmless) |
| pipeline.tex:320 | `\anna{idk}` | CURRENT | Anna's note at the end of the knobs subsection, whose "coverage is complete up to the instruction bound" (:316) is flagged at :90 | Anna's call |

### oldtechnicaldetails.tex (dead file: all DEAD)

| file:line | comment (excerpt) | class | evidence | action |
|---|---|---|---|---|
| oldtechnicaldetails.tex (file) | whole file | DEAD | `\input` nowhere (bare_conf_compsoc.tex:450-460, methodology.tex:1-2, main.tex) | delete it from the paper repo, or move it to simspect as was done with the notes backup (ISCA-27 3ad4c75) |
| :1 | `\anna{have a running example… dumpign into tix with claude…}` | DEAD | mentions "claude" | delete |
| :11, :14, :43-44, :53, :59, :62-63, :77-80, :82 | `% todo these components…`, `% fix this last sentence`, `% fix the resolved definition`, `% (todo: specify exact lengths…)`, `% what length`, `% separate instruction and operand removal`, … | DEAD | drafting notes | delete |
| :19-33, :135-144 | commented wrapfigure/figure blocks (examplefigure.png, pipeline.png, `\label{fig:pipeline}`) | DEAD | old figures | delete |
| :50 | `\anna{right now I am making this into a figure}` | DEAD | done: Table I (tikz/execvocab_v2_8pt.tex) | delete |
| :56 | `\anna{say this better todo}` | DEAD | | delete |
| :110 | live text "Note: each def is different timing for complettion etc" | DEAD | stray marker in a dead file | delete |
| :113 | `\anna{… claude could maybe turn drawings into tex}` | DEAD | mentions "claude" | delete |
| :114-133 | commented old subsection and proposal prose (incl. `% \anna{Finally, we will study…}` :133) | DEAD | | delete |
| :147-153 | live `figure*` (images/pipeline.png) with `\label{fig:pipeline}` | DEAD | would duplicate the live label (tikz/pipeline_full_8pt1col.tex:272) if ever input | delete |
| :157-173 | commented prose with `\caroline{what is meant by a series?}` (:157), `\todo{should I have one more example here?}` (:160), `\caroline{We make it sound like consistency was solved above…}` (:164) | DEAD | not checked against intro/related | read Caroline's two points, then delete |

If any text from this file is reused, several claims are out of date:
- :70 says RC uses the "last uncommitted" instruction; the code uses the first.
- :91 describes the store bypass in the false-positive direction with different addresses, and :101 forces an alias. Current: false-negative, same address, load forced to no-alias.
- :101 "flushing predicates from cache": no such mechanism exists.
- :98 checks "transmitter completion"; current is the LSQ Executing-load tick plus the data-obtained gate.
- :104 dummy instructions and commit stall; the commit stall is 0 in every eval config.

### pendingfigures.tex (dead file)

| file:line | comment (excerpt) | class | evidence | action |
|---|---|---|---|---|
| pendingfigures.tex (file) | whole file | DEAD | `% \input{sections/pendingfigures}` (bare_conf_compsoc.tex:460, lab-review version, 2026-11-03) | delete, or keep as a parking lot (Anna's call) |
| :1 | `% Figures whose placement or content is still undecided (2026-11-02)…` | DEAD | | delete with the file |
| :3 | `\section*{\figtodo{Pending figures…}}` | DEAD | | delete with the file |
| :4 | `\figtodo{… their references in the text still resolve here … re-run numbers and 8pt text}` | DEAD | "still resolve here" is false: the file isn't input, and every ref to these labels sits inside `\iffalse` blocks (results.tex:18-34, :211-221, :226-247, :252-269), so nothing prints ??. The re-run need is still true (URGENT_TODO.md:90) | delete with the file |
| :6 | `% \input{tikz/alloyviolation}% replaced by tikz/dataflow_8pt…` | DEAD | | delete |
| :70, :74 | auditnote: the taken-mode series used the old BTB force; the s_U points predate the resolve-stall fix | OBSOLETE | fig:timing is excluded and its subsection is `\iffalse`'d (results.tex:226-247); its June latency experiments are not in the eval set (EVAL_MANIFEST.md:212); the cited STATUS.md:30 is now another item | delete. Re-run on the fixed harness only if the sweep returns |

### Paste-ready replacement notes

**R1** (replaces pipeline.tex:20):
```
\auditnote{fact}{fact}{\textbf{About the caption of Table~\ref{tab:execvocab}:} Since 2026-11-09 every in-use model has rf\_from\_most\_recent\_writer, and the SPT model (SPT\_6\_oneLP\_v2) asks for an ordinary violation (at least one leaking operand). One difference outside the defense block is left: SPT tracks its protection set per operand, not per state (a, last\_committed\_protset\_p, secure\_speculation\_scheme\_p, tag\_xm), and Recon\_6 passes the perturbation into hardware\_protection\_policy. If the instance-based STT and ReCon drafts are approved, they adopt the same per-operand typing. \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): The defense block (speculation contract, protection set, leakage function) defines each defense; the rest of each model is shared, except that SPT tracks its protection set per operand (Section~\ref{...}). \newline \textit{Source:} STAGE1\_alloy/models/Recon\_6.als:163, :239; SPT\_6\_oneLP\_v2.als:6-17, :184, :253-266, :346; URGENT\_TODO.md:39, :40, :44}
```
**R2** (replaces :30; keeps the trailing `%`):
```
\urgentnote{\textbf{VOCAB}: \textbf{ADD DEFINITION} (new text, insert here): \emph{resolved} (the defense knows a branch's outcome, or with store bypass a store's address; a branch that has executed but not yet squashed its wrong path still counts as unresolved) and \emph{committed} (retired; implies resolved; a prefix of spo).}%
```
**R3** (replaces :59):
```
\auditnote{fig}{figure}{\textbf{About the caption of Fig.~\ref{fig:pipeline}:} 'Non-invasive' (figure and caption) overstates the harness: the branch force, the resolve stall and the store-address hold change prediction and timing on purpose, and the CleanupSpec and SpecLFB runs will also start each test with a hot or cold cache at random (decided 2026-11-09); only the defense logic is untouched (wording still open). The 'selects hooks' arrow stays (decided 2026-11-02), but the caption or text must say that the hooks are chosen at design time: no code passes the transmission mechanism to gem5 at run time. \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): "+ Minimal harness (defense logic untouched): probes; speculation and timing directives"; in the caption, "... under a minimal harness whose hooks are chosen at design time from the defense's transmission mechanisms". \newline \textit{Source:} URGENT\_TODO.md:97, :107, :167; wiki/design/RESOLUTION\_HOOKS.md sec.~1; STAGE3\_gem5/cache\_setup.py}
```
**R4** (replaces :61):
```
\auditnote{fig}{figure, high}{\textbf{About the caption of Fig.~\ref{fig:pipeline}:} 'Bounded-exhaustive' now holds only in part. In the two-stage runs, Stage~1 (up to six instructions) reaches UNSAT for STT and ReCon and their STL variants (the six-instruction transmitter partitions were still running when last checked), but SPT's Stage~1 does not converge: its four-instruction partition is capped at 200,000 graphs. The numbers reported so far come from flat test sets that stop at their instance cap. \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): "Bounded-exhaustive (STT, ReCon) set of minimal violating execution graphs", or keep the label once SPT's Stage~1 is settled. \newline \textit{Source:} wiki/state/EVAL\_MANIFEST.md:40-48 (2026-11-09 05:00Z); URGENT\_TODO.md:36}
```
**R5** (replaces :63):
```
\auditnote{fig}{figure, high}{\textbf{About the caption of Fig.~\ref{fig:pipeline}:} The caption calls Stage~1.5's output minimal, but Stage~1.5 loosens minimality (slab 2': it keeps RR, RC and RS and drops RI). Stage~1.5 is no longer a prototype: it runs one pinned Alloy run per Stage-1 graph, in parallel, at exactly six instructions, with a per-graph cap (about 300,000 graphs per defense), and the final results will come from it; no number in the paper does yet. \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): Stage~1 uses Alloy to enumerate minimal violating execution graphs of up to six instructions; Stage~1.5 grows each one into six-instruction graphs under loosened minimality, a capped number per Stage-1 graph. \newline \textit{Source:} wiki/state/EVAL\_MANIFEST.md:50-58; STAGE1\_alloy/models/proposed\_twophase/STT\_6\_core\_ri.als:289-310; URGENT\_TODO.md:95}
```
**R6** (replaces :80):
```
\auditnote{write}{writing, high}{Decided 2026-11-08: Stage~1 adds instruction minimality (RI) to the models' own RR, RC+RR and RS checks; RO is defined but enforced nowhere; Stage~1.5 drops RI again. The text should say which stage checks which relaxation. \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): In Stage~1, a graph is minimal if removing any instruction (RI) or any state element (RS), resolving any unresolved instruction (RR), or committing and resolving the first uncommitted instruction (RC) makes it non-violating; Stage~1.5 keeps RR, RC and RS but not RI. \newline \textit{Source:} STAGE1\_alloy/models/proposed\_twophase/STT\_6\_core\_ri.als:289-302; STT\_6.als:301-311; URGENT\_TODO.md:54}
```
**R7** (replaces :90):
```
\auditnote{write}{writing, high}{Partly out of date. Stage~1 now enumerates up to six instructions by model-finding and blocking until UNSAT, and reaches UNSAT for STT and ReCon and their STL variants (the six-instruction transmitter partitions were still running when last checked); SPT's Stage~1 is capped at 200,000 graphs, and Stage~1.5 enumerates a capped number of graphs per Stage-1 graph. So only the Stage-1 cores are exhaustive, and only for STT and ReCon. The same claim is in the intro and in the knobs subsection ('coverage is complete up to the instruction bound'). \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): Stage~1 enumerates every minimal violating graph of up to six instructions by repeatedly model-finding and blocking each graph found until the problem is UNSAT (for SPT, up to a cap); Stage~1.5 then enumerates up to a fixed number of six-instruction graphs around each one. \newline \textit{Source:} wiki/state/EVAL\_MANIFEST.md:40-58; STAGE1\_alloy/models/proposed\_twophase/STT\_6\_core\_ri.als:308-310 ('but 6'); URGENT\_TODO.md:36}
```
**R8** (replaces :105 and :107):
```
\auditnote{fig}{figure, high}{\textbf{About Fig.~\ref{fig:relaxation}:} With RI-only Stage~1 (decided 2026-11-08) the caption's claim holds for Stage~1: RI removes (b) and RR removes (c). (a) is removed too, but by RS (r1 appears only in the unneeded operand), because RO is enforced nowhere. Stage~1.5 re-admits graphs like (b) by design; in the flat test sets behind the current numbers, (b) was never removed. \newline \textbf{PROPOSED TEXT}: relabel (a)'s arrow RS, or keep RO and add 'RO is defined but not enforced; RS removes (a)'; end the caption with '... so Stage~1 does not synthesize them.' \newline \textit{Source:} STT\_6.als:215 (o\_p: RS drops every operand on the removed state), :301-311; STAGE1\_alloy/models/proposed\_twophase/STT\_6\_core\_ri.als:301; URGENT\_TODO.md:54, :75}
```
**R9** (replaces :127):
```
\auditnote{fig}{figure}{\textbf{About the caption of Fig.~\ref{fig:interleave}:} With RI-only Stage~1, 'no Stage~1 instance contains' is now true by construction: the second source is redundant for the leakage predicate, so no minimal graph has it. The mechanism is what is out of date. Chain interleaving is off in every evaluation config, put an ALU on a load transmitter's address path in 0 of 1,200 variants (that address is always an Alloy-locked register, and chains write only free registers), and cannot hook onto a Stage-1 core, which has no ALU on its transmitter path. SimSpect reproduces the getOldestTaint bug with the opt-in OTB merge of fanout v2 instead: a second load under an earlier, resolved branch, xor-merged into the transmitter's address (ReCon-STT build: 100 of 100 tests hit, 0 of 100 without the merge). \newline \textbf{PROPOSED TEXT}: redraw the figure and caption around the merge the evaluation uses, or caption this figure as the chain-interleaving capability rather than the route behind the result. \newline \textit{Source:} wiki/design/VOCAB\_TABLES.md:344, :368-369; project log 2026-11-08 fpr-fanout; URGENT\_TODO.md:46, :63}
```
**R10** (replaces :163):
```
\auditnote{fig}{figure, low}{\textbf{About the caption of Table~\ref{tab:instrtable}:} fnc is now 'first uncommitted' everywhere (Table~II, Fig.~\ref{fig:checkerwindow} and the text), as the glossary recommends. Still open: Table~II uses an 'uncommitted' flag word that Table~\ref{tab:execvocab} does not define, and row~5 covers only Branch\_x and Other\_x (called 'Divide'). \newline \textbf{PROPOSED TEXT}: add to row~5 'Load, Store: no special code'; write 'Other\_x (divide)'. \newline \textit{Source:} tikz/instrtable\_v2\_8pt.tex:8, :75, :80-83; tikz/checkerwindow\_v4\_8pt.tex:173}
```
**R11** (replaces :179 and :181; delete :184):
```
\auditnote{fact}{fact}{This is a capability the evaluated pipeline does not use. Chain interleaving is off in every evaluation config, and on 300 STT\_6 load-transmitter instances it put an ALU on the transmitter's address path 0 of 1,200 times, because that address is always an Alloy-locked register and chains write only free registers. 'Which no single Alloy instance can express' is also wrong: the shape is satisfiable when forced; minimality drops the redundant second source, so no Stage-1 core contains it. SimSpect reproduces the getOldestTaint merge with the opt-in OTB merge of fanout v2 (ReCon-STT build: 100/100 tests hit, 0/100 without it). \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): interleaving can feed a transmitter from two independent speculative sources, a shape that minimal graphs never contain; \newline \textit{Source:} wiki/design/VOCAB\_TABLES.md:344, :368-369; STAGE2\_compilation/parsexml.py:1598-1614; wiki/findings/mdsToRead/OTB\_GENERATION\_GAP.md (forcing is SAT); URGENT\_TODO.md:46, :63, :185-187}
```
**R12** (replaces :259):
```
\auditnote{fig}{figure, high}{\textbf{About the caption of Fig.~\ref{fig:checkerwindow}:} This example is now in scope. Since 2026-11-08 each footprint criterion checks only the structures its defense's paper claims (for InvisiSpec, MSHR contention and the I-cache are out, the L1D is in), and UV1 is found in 2,995 of 3,000 tests on the hooked InvisiSpec build. What is out of date is the results section's scope paragraph ('exactly one (SpecLFB UV6) falls in \toolname{}'s leakage model'). \newline \textbf{PROPOSED TEXT}: keep this example, caption it as InvisiSpec's footprint criterion, and update the scope paragraph in the results. \newline \textit{Source:} URGENT\_TODO.md:174; wiki/findings/mdsToRead/AMULET\_BUGS\_DETECTION\_ACCOUNTING.md:33; sections/results.tex:195-204}
```
**R13** (replaces :289):
```
\auditnote{fact}{fact}{check\_ld times the load by its latest LSQ 'Executing load' tick, which fires before the defense decides whether to send the access; the pipeview complete tick is the fallback. The packet and spec\_read ticks only feed the yes/no data-obtained gate and are never compared with the window. If a multi-micro-op transmitter (an RMW) never executes its load micro-op, the fallback scores the first micro-op's complete tick. The footprint defenses (InvisiSpec, CleanupSpec, SpecLFB) do not use this predicate: their runs use the footprint check over SimSpect cache-event lines with a per-defense criterion, and the memaccess and expose checkers are legacy. \newline \textbf{PROPOSED TEXT} (edits the sentence just before this note): The signal is the tick at which the LSQ executes the load (\texttt{Executing load}; \texttt{O3PipeView} \texttt{complete} if absent), and the load counts only if it then obtained data ...; the footprint defenses use their own footprint criteria (Sec.~\ref{...}). \newline \textit{Source:} STAGE3\_gem5/check\_ld.py:30-37, 85-87, 130-146; runconfigs/footprint/*.jsonc (gem5.checker = check\_footprint.py); URGENT\_TODO.md:98, :168}
```
**R14** (new live note after :226; delete the commented :227-228):
```
\notebr
\reviewnote{\textbf{FIX the numbers}: these are the pre-fix settings. The evaluated configs hold unresolved branches for $s_U = 5000$ cycles, sweep $s_R \in \{0, 500, 2500\}$ (footprint rows: 0 only) and set no commit stall (Table~\ref{tab:instrtable}); the claim that a 5000-cycle $s_U$ masks leaks predates the resolve-stall fix. \newline \textbf{PROPOSED TEXT}: ``\ldots{} the resolved-branch stall over $s_R \in \{0, 500, 2500\}$ cycles; unresolved branches are held for $s_U = 5000$ cycles, so they stay unresolved past the transmitter, and the commit stall is off (Table~\ref{tab:instrtable}).''}
\notebr
```
**R15** (replaces :205):
```
\reviewnote{\textbf{CHECK}: no evaluated campaign ran these controls. The fnc stall is 0 in every evaluation config, so its on/off pairing does not apply; there is no branch-annotation-off run; the Unsafe baseline is in the evaluation set but has not run yet. Reword to ``can be paired'', or name only the Unsafe baseline.}
```
**R16** (replaces :213):
```
\reviewnote{\textbf{FIX}: Stage~2 writes no timing, and the pairs do not ``incorrectly alias''. \newline \textbf{PROPOSED TEXT}: ``\ldots{} carrying each element's PC, each branch's mispredict mode and target, the transmitter's kind, and, for store bypass, one (store, load) PC pair per load of the held store's location, each load forced to predict no alias. Stall lengths come from the run configuration.''}
```
**R17** (new note after the reviewtag at :236):
```
\notebr
\reviewnote{\textbf{FIX}: not every build carries both later hook sets. The resolve hooks are on all ten hooked builds; the store-bypass hooks are only on the store-bypass build, which predates the resolve hooks (rebuild planned), and no store-bypass window checker exists yet. \newline \textbf{PROPOSED TEXT}: ``Every hooked build also carries the \emph{resolve hooks} \ldots{}; the store-bypass build adds the \emph{store-bypass hooks} \ldots''}
```
**R18** (replaces :305):
```
\reviewnote{There is no store checker: kinds without their own checker fall back to the load check (pipeline.py:313-320), which scores a store by its completion tick. Only our SPT model makes stores transmit (SPT\_6\_oneLP\_v2.als:378), and store transmitters are out of scope for STT (decided 2026-11-08). CUT this bullet, or \newline \textbf{PROPOSED TEXT}: ``Store transmitters, used only by our SPT model, are scored by the load predicate's fallback, the store's completion tick.''}
```

### Fix first

1. **pipeline.tex:226.** Paste **R14** and delete the commented :227-228. The text states pre-fix stall values that contradict :158 and Table II, and no visible note says so.
2. **Remove "claude" from the paper source** (the advisor reads it):
   - delete pipeline.tex:169;
   - delete oldtechnicaldetails.tex (its :1 and :113 mention claude);
   - outside my files: intro.tex:25 has `%claude please triple check this work…`.
3. **Minimality and exhaustiveness** (:61, :63, :80, :90, :105/:107). Paste R4, R5, R6, R7 and R8; these notes predate the RI-only two-stage decision. The body text they sit on needs two-stage wording too (list below).
4. **OTB / interleave** (:127, :179, :181). Paste R9 and R11. Decision H1 settles the matching body text.
5. **Model-skeleton notes** (:20, :76, :84). Paste R1; delete :76 and :84.
6. **Load-signal note and the checker example** (:289, :259). Paste R13 and R12; the body at :291 and results.tex:195-204 follow from them.
7. **Smaller updates:**
   - paste R3, R2, R10, R17, R15, R16 and R18;
   - fix the cites in :65 (URGENT_TODO.md:44 → :107) and :240 ("8 hooked builds" → "10");
   - refresh the drifted line cites in :146, :155, :161, :187 and :224;
   - delete the RESOLVED and DEAD rows above.

### Body text the notes show to be out of date (pipeline.tex; prose is Anna's to change)

- **:78 and :110-121:** "every relaxation" and the five-item list include RO, which no stage of the evaluation enforces (STT_6_core_ri.als:289-302).
- **:88:** "until the problem is UNSAT" holds only for Stage 1 of STT and ReCon. **:316:** "coverage is complete up to the instruction bound".
- **:316 also:**
  - It lists "the interleaved chains" as a semi-enumerated choice, but interleave is off in every eval config.
  - It omits random register naming (the default since 2026-11-08, batch_generate.py:74) and the opt-in FPR routing and fanout v2. FPR routing is how the pipeline found the STT xmm4 bug (claudelog 2026-11-08 19:20).
- **:124 and :177:** they present chain interleaving as the route to the getOldestTaint merge. That route is off and put an ALU on the transmitter path 0/1200 times; SimSpect reproduced OTB with fanout_v2.otb.
- **:134:** "the models we evaluate enforce only RR, RC and RS" is true of Stage 1.5; Stage 1 adds RI.
- **:173, :229, :235 (STL):** the store-bypass hooks exist only on a stale build, there is no STL window checker (EVAL_MANIFEST.md:344-349), and no STL result exists.
- **:217:** "force the modeled mispredicted (taken) path" (see :219).
- **:222:** "we sweep them", but s_U and the commit stall are fixed in the eval configs; only s_R is swept, and not on the footprint rows.
- **:226:** the stall values (R14).
- **:235:** "Every build also carries two later hook sets" (R17).
- **:238:** "No cache or defense code is instrumented to see a leak". Hooks v2 add cache-event prints on the 3 footprint builds, and the BR lines are on all 10 hooked builds (see :240).
- **:291:** the memaccess/expose description is the legacy checkers'.
- **:298:** the Other_x bullet describes a path no evaluated model exercises (:161).

### Answer to Anna's "@claude this makes no sense wdym" (pipeline.tex:169)

Fig. 6 shows one abstract graph with two resolution timings. The leakage predicate is evaluated on the graph, so both options are violations; what differs is whether ReCon lets i5 transmit, i.e. whether gem5 shows a hit. So label the options by behaviour ("ReCon holds i5" vs "ReCon releases i5 (bug)"), not "violation"/"no violation". The live note at :167 already proposes exactly this, so :169 can go.

### Hard decisions surfaced (Anna's)

- **H1. Which Stage 2 mechanism does the paper present for two-source merges / OTB?** (:124, :127, :177, Fig. 5)
  - Options:
    - (a) Describe what the evaluation will run: random register naming plus fanout v2 (splices, read-only fillers, the OTB merge). Redraw Fig. 5 around the OTB merge, and say the authors found the OTB bug and SimSpect reproduced it with this merge.
    - (b) Keep chain interleaving as Stage 2 and add the OTB merge as a targeted option.
    - (c) Keep Fig. 5 as a capability illustration only.
  - Evidence:
    - chain interleave is off in all eval configs, put an ALU on the path 0/1200 times, and cannot hook onto RI cores;
    - the OTB merge hits 100/100 vs 0/100 on 100 eligible tests (385/2991 STT_6 tests are eligible);
    - fanout v2 is in specs/fanout/stt.json but in no eval run config yet.
  - Open DECIDEs: URGENT_TODO.md:46, :63.
  - **Recommendation:** (a), if the final run configs turn fanout v2 on.
- **H2. How does the paper state minimality?** (:78, :110-121, Fig. 4)
  - Options:
    - (a) Two-stage wording: Stage 1 = RI + RR + RC(+RR) + RS, Stage 1.5 = RR + RC + RS; RO is defined but unused; relabel pane (a) RS.
    - (b) Keep the five relaxations as the intended criterion and say which ones are enforced where.
    - (c) Add RO to Stage 1, a model change. RO+RI makes the STL cores UNSAT and left only 2 STT cores (TWO_PHASE_MODELS.md:387).
  - **Recommendation:** (a). The RS-removes-(a) point comes from reading STT_6.als:215, not from an Alloy run.
- **H3. Exhaustiveness claims** (the figure's "Bounded-exhaustive", :88, :316, the intro).
  - Options:
    - (a) Claim exhaustiveness for STT/ReCon Stage 1 only; qualify SPT and Stage 1.5.
    - (b) Wait for the SPT testset decision (URGENT_TODO.md:36), then claim it for all.
    - (c) Say "bounded, capped" instead.
  - **Recommendation:** (a) now, and revisit after :36. First confirm that the k6 transmitter partitions finished, and that Recon Stage 1 is rerun on the post-rf-fact core.
- **H4. Where does the window end?** (:252, :257, :270)
  - Anna's 2026-11-08 rule (executed-but-not-squashed = unresolved) implies the window ends at the squash. The checkers end it at resolve_visible (gem5_common.py:1023-1083).
  - Options:
    - (a) End the shared window at the squash for every checker, as recommended in SOURCE_AUDIT_INVISISPEC.md:101-108.
    - (b) Keep resolve_visible and add a separate resolve-to-squash term.
    - (c) Keep it as is.
  - **Recommendation:** (a). It applies Anna's rule and settles R1 (the STT squash race then counts), but needs a checker change and a re-score (URGENT_TODO.md:32, :74, :101).
- **H5. The violation definition and the instance-based STT_6_v2** (:48-49).
  - Options:
    - (a) Approve STT_6_v2/Recon_6_v2 and rewrite the definition as a data-dependence path from a speculatively loaded value.
    - (b) Keep the location-based STT_6 and state that scope choice.
  - **Recommendation:** (a), per the model audit, whose one unsound clause found is the location-based fold (URGENT_TODO.md:37, :40). Decide the model first; the paper text follows.
- **H6. How are the footprint defenses framed?** (:259; results.tex:195-204)
  - Options:
    - (a) In scope per each paper's claimed structures (UV1/UV4/UV6 found through hooks v2; UV3 with a cold cache): keep Fig. 7 and rewrite the results scope paragraph.
    - (b) Keep "collateral, out of scope" and swap Fig. 7 for an STT or ReCon example.
  - **Recommendation:** (a), consistent with URGENT_TODO.md:174. Settle the footprint-actor question D2 (:261; URGENT_TODO.md:140) together with it.

## Part 4: results.tex, discussion.tex, tikz/

I made no edits in ISCA-27 and ran no git writes. I applied Anna's correction: both Recon-STT bugs (the STL forwarding bug and OTB) are new findings. I propose no novelty caveats and did not use recon_author_email.txt.

Paths: paper files are relative to ISCA-27/. Evidence paths are relative to simspect/. Abbreviations:
- UT = URGENT_TODO.md. Line numbers are as of 2026-11-09 ~01:10; other sessions are editing it, so lines shift.
- CL = claudelog.md, cited by entry date and label.
- EM = wiki/state/EVAL_MANIFEST.md
- AA = wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md
- BAF = wiki/findings/bug/BRANCH_ANNOTATION_AND_FORCE.md
- BT = wiki/findings/bug/BUG_TAXONOMY.md
- SAS = wiki/findings/audits/2026-11-08/SOURCE_AUDIT_SUMMARY.md
- VT = wiki/design/VOCAB_TABLES.md
- P1 = Part 1 of this audit, wiki/findings/audits/2026-11-09/PAPER_COMMENT_AUDIT.md

### Summary counts

There are 87 entries. Identical or trivial comments are grouped: cut markers, provenance and tuning comments, unused 7pt twins.
- **CURRENT: 44.** Of these, 9 are check markers whose marked text is now out of date: rows 12, 17, 26, 32, 49, 60, 62, 63, 67.
- **STALE: 25**
- **RESOLVED: 5**
- **OBSOLETE/DEAD: 13**

Several commented-out (`%`) notes still carry live concerns but never print, whichever note switches are on (rows 13, 14, 69).

### Table: every comment

| # | file:line | comment (excerpt) | class | evidence | action |
|---|---|---|---|---|---|
| 1 | results.tex:1-13 | header "results-methods.tex … Inserted via \input after results-simspect … Numbers verified … Unverified-compile (no TeX in the authoring env)" | OBSOLETE | file is sections/results.tex, \input at bare_conf_compsoc.tex:457; no paper.tex/results-simspect exists; numbers are pre-fix (UT:108); last line reads as tool-authored in source the advisor can open | delete 1-13 (keep :5 breadcrumb if wanted) |
| 2 | results.tex:16 | `\labnote{results are not finalized.}` | CURRENT | EM:17 "everything is NOT RUN for this eval" | keep |
| 3 | results.tex:18-34 | hidden "[fig todo: results to write up]" list | STALE | :21 superseded by regen-all rule (UT:62); :22 R1 decided (UT:32); :23 SPT hits triaged, 0 new (BAF:100, :169-171); :24 interleave can't make OTB (UT:48), Stage-2 OTB merge does 100/100 (VT:369); STL now 91/94 tests all A2 (BAF:168); :27 UV1 2,995/3,000 (CL 2026-11-08 hooks-v2 InvisiSpec); :28 "UV3–UV5 out of scope" wrong (UT:13, :165; AA:36-38); :31 coverage now exists (EM:47-56) | refresh if restored (R3) |
| 4 | results.tex:26 | `\reviewnote{the transmission-criteria table is hidden … print ??}` | OBSOLETE | inside \iffalse (:18-34): neither refs nor note print | delete |
| 5 | results.tex:39 | `\auditnote{cite}{cite, high}{Three evaluated defenses are never cited …}` | STALE | proposed keys `invisispec/cleanupspec/speclfb` don't exist; bib has yan2018invisispec (references.bib:2641), saileshwar2019cleanupspec (:2650), cheng2024speclfb (:2659), loughlin2021dolma (:2669), sakalis2019delay (:2679); :37 still cites none | replace (R5) |
| 6 | results.tex:41 | `\auditnote{claim}{…leaves out ReCon … classic caches … JSON criteria never run … panics … hand-built gadgets}` | STALE | ReCon now in :36; InvisiSpec ran --ruby through hooks v2 + check_footprint/JSON (CL 2026-11-08 hooks-v2 InvisiSpec; AA:14-27); panic fixed (UT:122); UV4 found in 38 generated tests (AA:37). New caveats: NOT RUN for eval (EM:17); STT_6 tests drive E12-E14 (EM:201-204); leaking load often not the xmit (AA:65); classic Recon runs = Recon-STT (BUGS.md:24) | replace (R6) |
| 7 | results.tex:43,130,148,201,211,224,226,250,252,272 | "LAB-REVIEW CUT" markers; "figure X moved to pendingfigures" breadcrumbs | CURRENT | pendingfigures not \input (bare_conf_compsoc.tex:460) | keep |
| 8 | results.tex:46 | `\reviewnote{the bug table is hidden … prints ??}` | RESOLVED | both refs now inside \iffalse (:43, :201); no other section refs tab:bugs | delete |
| 9 | results.tex:49 | "% THE BUG TABLE -- PARKED AS TODO (rework w/ proper InvisiSpec scoping)" | STALE | InvisiSpec scope decided (UT:176); remaining blocker = bugtable_v3 rows (row 79) | replace: `% Bug table: tikz/bugtable_v3_8pt (working table); refresh rows from wiki/findings/bug/BUGS.md before showing` |
| 10 | results.tex:50-51,53,54-89 | old \iffalse table; `% \input{tikz/bugtable_v2_8pt}`; `% \figtodo{restyled bug table … B\&W …}` | OBSOLETE | superseded by bugtable_v3_8pt; content stale (InvisiSpec/CleanupSpec "all out of scope" :69-71, UV6 "@t6" :74, no Recon/xmm4/jmp-shadow); palette now color (sscolors.tex) | delete |
| 11 | results.tex:52 | `% \input{tikz/bugtable_v3_8pt} … uncomment to show` | CURRENT | rows stale (row 79) | keep commented until refreshed |
| 12 | results.tex:95 | `\reviewtag{[TODO: Added the ReCon class]}` | CURRENT, but marked text is stale | :92-94 "three classes", with SPT-Fence's race as confirmed; A5 is a candidate (BT:120). Missing: STT xmm4 (wiki/findings/bug/stt_xmm4_taint_skip/README.md "Verdict"), SpecLFB jmp-shadow (BUGS.md:48-51), UV1/UV3/UV4 (AA:33-37), OTB reproduced by pipeline (VT:369) | keep tag; rewrite :92-94 (D3) |
| 13 | results.tex:101 | `% \urgentnote{23,966 is a pre-2026-10-30 number …}` (commented) | STALE | still pre-fix; 19,845 + 4,122 never-rechecked = 23,967 (PAPER_PLAN.md:207; claudenotes.md:251); race only in June slow-comm runs, which the approved eval excludes (EM:210-212); UV6 has new counts (row 15) | replace + un-comment (R13) |
| 14 | results.tex:103 | `% \urgentnote{SPT-Fence race … none triaged …}` (commented) | STALE | triaged: round 2 0 new (BAF:100); round 4 ld 57/48, str 74/60, br_x 51/51 all model/concretization (BAF:169-171); A5 open (BT:120-135); SPT race diagnostic never run (PAPER_PLAN.md:208) | replace + un-comment (R14) |
| 15 | results.tex:107 | `\auditnote{claim}{claim, high}{…pre-warmed line … second speculative load … should not be counted as UV6}` | STALE | install-keyed rerun: UV6 1,143/1,142 + walk-order 157/162 of 1,500 per mode (CL 2026-11-08 hooks-v2 first STT_6 runs); Anna 2026-11-09: walk-order = UV6 broader scope (UT:148), so 1,300/1,304; plus jmp-shadow 148 (AA:42); 68/300 counted hits (AA:63) | replace (R15) |
| 16 | results.tex:113 | `\auditnote{claim}{claim, high}{This contradicts STT's paper … stores … 'are defined as transmitters' …}` | STALE | quotes verified in ~/Documents/quail/sources/papers/yu-2019-stt.pdf (§6.1 stores "are defined as transmitters"; §6.4.2 "loads and stores access memory only if their address argument is untainted"); but Anna ruled store transmitters out of scope as our model's choice (UT:13, :28; AA:43); proposed key `{stt}` doesn't exist (yu2019stt, references.bib:1956) | replace (R16) |
| 17 | results.tex:116 | `\reviewtag{[TODO: Proposed this paragraph; check it]}` | CURRENT, but marked text is stale | :117: STL re-confirmed post-fix (BAF:168) and removed by the no-forwarding control, 80→0 of 200 (CL 2026-11-08 21:30 fpr-fanout); OTB "hand-built" → also reproduced by Stage 2's OTB merge, 100/100 vs 0/100 (VT:369) | keep tag; update :117 (no novelty caveat) |
| 18 | results.tex:120,137 | `\reviewtag{[TODO: Made this a subsubsection…]}`, `\reviewtag{[TODO: Proposed this example paragraph…]}` | CURRENT | cycles 49/77/78/79/81 match provenance.json ticks ((tick−2907000)/500) | keep |
| 19 | results.tex:134 | `\reviewnote{the old LSQ-trace figure … citation was cut}` | RESOLVED | cut in place (:130); fig:race defined at squashrace_v2_8pt.tex:192 | delete |
| 20 | results.tex:140 | `\auditnote{claim}{…se_slowcomm.py … iewToCommitDelay=30 …}` | CURRENT | wiki/findings/bug/stt_slowcomm_vp_squash_race/provenance.json ("se_slowcomm_hardcoded", "minimal_poc") | keep |
| 21 | results.tex:144 | `\auditnote{write}{writing, high}{…not a violation … DECISION for Anna (R1)…}` | RESOLVED (decided; follow-ups open) | Anna 2026-11-08: a branch that executed but isn't squashed counts as unresolved; A4/S4 = implementation bugs (UT:32; SAS:38); packet 79 < squash 81. Open: pipeline.tex:265-277 lacks "until squashed"; checker still ends "unresolved" at resolve_visible (STAGE3_gem5/gem5_common.py:1023-1063, used by check_ld.py:110-114); UT:76, :107 still list R1 open | replace (R21) |
| 22 | results.tex:152 | `\urgentnote{VOCAB: … rename … once DECIDE R1 is settled …}` | STALE (condition now met) | R1 settled (row 21); squashrace_v2_8pt.tex:178 still "Committed window" | replace (R22) |
| 23 | results.tex:154 | `\auditnote{fig}{…only commitToIEWDelay=4 … fnc not drawn … E at 49…}` | CURRENT | squashrace_v2_8pt.tex:166-167 (E at 49 and 78), caption :188 | keep |
| 24 | results.tex:156 | `\auditnote{fig}{figure, high}{…adjacent figures contradict … (ties to pending R1)…}` | STALE | R1 decided; drawings still conflict (checkerwindow_v4_8pt.tex:174 ends at resolution; squashrace at fnc retire) | replace (R24) |
| 25 | results.tex:158 | `\figtodo{squash-race figure redrawn in the B\&W visual language …}` | RESOLVED | squashrace_v2_8pt \input at :150 | delete |
| 26 | results.tex:161 | `\reviewtag{[TODO: Proposed this subsubsection; check it]}` | CURRENT, but marked title is stale | title :160 "ReCon:"; classic-cache runs are Recon-STT (BUGS.md:24; EM:195); figure already says ReCon-STT (reconstl_v2_8pt.tex:124) | keep tag; retitle (D7); same for :177 |
| 27 | results.tex:164 | `\auditnote{claim}{claim, low}{…no forwarding line … inferred…}` | CURRENT | still true of trace_excerpt_sn600.txt; new supporting control: store separation removes all 80 A2 hits on 200 tests (CL 2026-11-08 21:30 fpr-fanout) | keep; optionally add the control (R27) |
| 28 | results.tex:169 | `\urgentnote{VOCAB: Fig. reconstl … ``Tainted and speculative until the squash''…}` | CURRENT | reconstl_v2_8pt.tex:114 unchanged; matches until-squash rule | keep |
| 29 | results.tex:171 | `\auditnote{fig}{figure, low}{…do not share a visual vocabulary…}` | CURRENT | F/D/E vs N/E unchanged (checkerwindow_v4_8pt.tex:172; squashrace_v2_8pt.tex:74) | keep |
| 30 | results.tex:173 | `\auditnote{fig}{…store i4 drawn as '? <- [r0]'…}` | CURRENT | reconstl_v2_8pt.tex:70, :49-50 | keep |
| 31 | results.tex:175 | `% \figtodo{new Recon STL bug figure (…candidate … re-run pending)…}` | OBSOLETE | figure + paragraph in; re-confirmed post-fix (BAF:168; UT:123) | delete |
| 32 | results.tex:178 | `\reviewtag{[TODO: Proposed this subsubsection; check it]}` | CURRENT, but marked text is stale | :179 "enumeration does not reach … Stage 2 interleaving is meant to build it": interleave can't reach an RI core's transmitter path (UT:48; CL 2026-11-08 18:42 model-audit); Stage 2's opt-in OTB merge reproduces it (VT:369) | keep tag; update :179 |
| 33 | results.tex:181 | `\reviewnote{the trace shows i5 issuing … Say ``issues''…}` | STALE | generated OTB tests show the transmitter completing while the unresolved branch is held, 100/100 vs 0/100 (VT:369); recon builds never log a sent packet (wiki/findings/bug/recon_cache_reach_gate/README.md) | replace (R33) |
| 34 | results.tex:185 | `\labnote{InvisiSpec, SpecLFB and CleanupSpec results still to be inserted here.}` | CURRENT | first results exist (AA:33-43), reference-only (EM:17) | keep |
| 35 | results.tex:187 | `% \figtodo{new Recon OTB figure … re-run with LSQ tracing pending}` | OBSOLETE | figure + paragraph in; duplicates row 33 | delete |
| 36 | results.tex:189-192 | hidden placeholder + `\reviewtag{[TODO placeholder: InvisiSpec, SpecLFB (UV6) and CleanupSpec…]}` | CURRENT | still unwritten; material in AA:33-43, BUGS.md:48-51 | keep; when written add jmp-shadow + any-squashed-load caveat |
| 37 | results.tex:199 | `\urgentnote{VOCAB: ``inside the speculative window'' → ``violation window''}` | CURRENT | :198 unchanged; pipeline.tex:265 defines violation window | keep (see body item B11) |
| 38 | results.tex:206-209 | commented claim "AMuLeT's random search does not target … race" + `% \urgentnote{This is unfair…}` | OBSOLETE | claim cut; AMuLeT-parity rows still not run (EM:217-226) | delete both |
| 39 | results.tex:212 | `\anna{fixing this still}` (hidden) | CURRENT | Anna's | keep |
| 40 | results.tex:219 | `\urgentnote{The two percentages measure different things … 0 hits…}` | CURRENT | STT 0/0 in round 4 (BAF:167); cite "STATUS.md:33" moved (now :44-45) | keep; fix cite |
| 41 | results.tex:231 | `\urgentnote{…leak appears at commitToIEWDelay ≥ 3…}` | CURRENT | BUG_EXPLAINER.md:104-107; BT A4 | keep |
| 42 | results.tex:239 + 245 | `\auditnote{claim}{…stall sweeps ran before the fix…}` + `\urgentnote{These stall-knob conclusions … pre-fix…}` | CURRENT (duplicates) | still pre-fix; June latency runs excluded from eval (EM:210-212) | merge into one; decide re-run vs drop (D2) |
| 43 | results.tex:258 | `\urgentnote{…pre-fix checker hits … against AMuLeT's…}` | CURRENT | speed numbers must come from runconfigs/amulet_parity T1-T5, none run (EM:217-226; STATUS.md:29-30) | keep; add parity requirement |
| 44 | results.tex:265 + 267 | `\auditnote{write}{…0.55 s … 2.22 s…}` + `\urgentnote{The arithmetic doesn't hold…}` | CURRENT (duplicates) | recomputed 0.552 s vs 2.223 s = 4.0×; note 265's cite ":156-160" now :254-263 | merge into one |
| 45 | results.tex:278 | `\auditnote{claim}{claim, high}{Several counts in the section fail this bar…}` | CURRENT | gate not window-bound (UT:100); race open/not re-verified (BUGS.md:68-78); 68/300 still at :295 | keep; add recon-gate sentence from row 48 |
| 46 | results.tex:282 | `\auditnote{write}{writing, high}{This contradicts the Results todo list … OTB … only an issue…}` | STALE | OTB completion now shown (VT:369); cites ":17", ":115" moved (now :21, :181); proposed text has a "\ref{...}" placeholder | replace (R46) |
| 47 | results.tex:286 | `\urgentnote{VOCAB: speculative → violation window}` | CURRENT | :284 unchanged | keep |
| 48 | results.tex:291 | `% \urgentnote{The repo contradicts this section's bar … omits the ReCon bugs…}` | OBSOLETE | ReCon added (:295); rest duplicates row 45; surviving point (recon builds never log a sent packet, recon_cache_reach_gate/README.md) goes into row 45 | move point, delete |
| 49 | results.tex:296 | `\reviewtag{[TODO: Added ReCon here]}` | CURRENT, but marked text is stale | :292-295 repeat 23,966/0 (row 13), 68/300 (row 15), "STT/SPT race" (row 14); omit OTB, xmm4, jmp-shadow, UV1/UV3/UV4 | keep tag; rewrite after D2/D3 |
| 50 | discussion.tex:2-15 | hidden "[fig todo: major discussion points]" list | STALE (3 items) | :5 Stage 1 exhausts for STT_6_stl (306) and to k5 for STT/ReCon; SPT caps at 200,000 (EM:47-56; UT:38). :9 race is inside the window (UT:32). :11 SimSpect now flags UV1, UV3-UV6 (AA:33-41). :6-8, :10, :12 current (:10 now three STT rows E2-E4, EM:191-193) | update :5, :9, :11 (R50) |
| 51 | discussion.tex:13 | `\auditnote{claim}{claim, low}{Store-to-load forwarding is not done as a primitive…}` | CURRENT | STL Stage-1 cores (306; 858) and Stage 1.5 (266,946) exist (EM:47-57); STL window checker not started (UT:57); gem5-recon-stl stale (UT:136) | keep |
| 52 | discussion.tex:19 | `\urgentnote{VOCAB: … ``still-speculative windows''…}` | CURRENT | :17 unchanged | keep |
| 53 | discussion.tex:23 | `\auditnote{fact}{fact, low}{Unsupported. Every evaluated model uses the same branch-only contract … futuristic … not reviewed or run…}` | STALE (details) | conclusion holds (EM:191-204); Futuristic was checked on 60 tests then parked (STATUS.md:51, :56); STT_6_shadows draft (UT:132); cited lines moved (Recon_6.als +9 lines, CL 2026-11-09 main; SPT model now SPT_6_oneLP_v2, UT:124) | replace (R53) |
| 54 | discussion.tex:25 | `\auditnote{claim}{claim, low}{…one current model per defense (STT_6, SPT_6_oneLP, Recon_6)…}` | STALE (source) | SPT = SPT_6_oneLP_v2 (UT:124); STT_6_v2/Recon_6_v2/SPT v3 drafts pending (UT:42-43); manifest moved to EM | replace (R54) |
| 55 | discussion.tex:29 | `\anna{2. Alloy abstract LILT … windows circled …}` | CURRENT | partly realized (squashrace/reconstl figures pair graph + trace + window); "enumerated, annotated version" not drawn | keep |
| 56 | discussion.tex:31 | `\reviewnote{PROPOSED TEXT (checked guarantees and scope) … exactly the guarantee its authors state, and no more…}` | STALE (partial) | quotes verified (yan-2018-invisispec-original.pdf fn. 2 and §VII; saileshwar-2019-cleanupspec.pdf §4(b) "Future work can explore … constant-time stall"; cheng-2024-speclfb.pdf §4); matches UT:176. But "exactly … no more" overclaims: we leave out SpecLFB exception shadows by choice (CL 2026-11-08 ~21:15 main; UT:35 SL-2) and STT stores (row 16). UV3-UV5 (flagged) are not mentioned (UT:165, :157) | edit first sentence + add one (R56) |
| 57 | discussion.tex:33 | `\reviewnote{PROPOSED TEXT (STT and store addresses) … Check before use: whether STT's transmitter definition names stores…}` | STALE | answered: yes. STT §6.1 names pre-retirement stores as transmitters; §6.4.2 requires untainted addresses for loads and stores; footnote-2 and "TLB, caches, or memory" quotes accurate (yu-2019-stt.pdf). Anna: out of scope as our model's choice (UT:13, :28) | replace last two sentences (R57) |
| 58 | discussion.tex:35 + 37 | `\reviewnote{PROPOSED TEXT (structure sizes)…}`, `\reviewnote{PROPOSED TEXT (cache sizes for the taint defenses)…}` | CURRENT | sizes match E12a 1kB/2 + 2 TBEs, E13 2kB/4 + 8 L1 TBEs, E14 1kB/2 (EM:201-204; UT:158); rationale SAS:55; parity runs not done yet, incl. jmp-shadow (EM:228) | keep; in :37 "speculative window" → "violation window" |
| 59 | tikz/squashrace_v2_8pt.tex:1 (twin squashrace_v2.tex:1) | "% … Pending: window definition (R1) undecided." | STALE | R1 decided (row 21) | `% … Window rule decided 2026-11-08 (unresolved until the squash): draw the violation window to cycle 81.` |
| 60 | squashrace_v2_8pt.tex:187 | `\reviewtag{[TODO: edit caption; replaced the code listing …]}` | CURRENT, but caption is stale | caption :188-190 gives only commitToIEWDelay=4 (provenance.json); "committed window closes when fnc retires at 261" vs until-squash rule; build is /work/stt e3283b9, while SimSpect's STT row is now /work/stt-master (EM:192) | keep; caption per rows 22-24 |
| 61 | reconstl_v2_8pt.tex:123 | `\reviewtag{[TODO: edit caption; replaced the code listing …]}` | CURRENT | caption says ReCon-STT (:124); 5/7/9 match text :162 | keep |
| 62 | recon_otb_v2_8pt.tex:133,135,137 | `\reviewtag{[TODO: edit caption]}`, `{[TODO: Fixed this table ref]}`, `{[TODO: Removed the pipeline timeline…]}` | CURRENT, but caption is stale | :138 "built by hand; our bounded enumeration does not reach this shape": Stage 2 now reproduces it (VT:369); graph marks i0 and i1 "committed" (:70-78), yet the caption calls i1 "speculative under branch i0" (needs the resolutiontiming.tex:109 explanation) | keep; caption R62 |
| 63 | checkerwindow_v4_8pt.tex:171 | `\reviewtag{[TODO: edit caption]}` | CURRENT, but caption is stale | :174 window "to the branch's resolution" vs until-squash rule (UT:32; IS-1 UT:34); "xmit's L1D eviction (★)" while the checker counts any squashed load (UT:112; AA:65) | keep; fix after D1 |
| 64 | instrtable_v2_8pt.tex:1 (twin instrtable_v2.tex:1) | "% … Replaces tikz/sptable.tex and tikz/resolutiontiming.tex" | STALE | resolutiontiming is \input again (pipeline.tex:165) | say "Replaces tikz/sptable.tex" |
| 65 | instrtable_v2_8pt.tex:5,7 | `\reviewtag{[TODO: edit caption; added each element's (mis)prediction…]}`, `{[TODO: Fixed this table ref]}` | CURRENT | "[Draft: store-bypass window check not yet built.]" still true (UT:57, :111); 5000 / 0,500,2500 / no commit stall match fixed configs (stt_xmm4_taint_skip/README.md "Evidence") | keep |
| 66 | "caption lives in captions/…": instrtable_v2_8pt.tex:12, interleave_v4_8pt.tex:6, bugtable_v3_8pt.tex:23, bugtable_v2_8pt.tex:12, execvocab_8pt.tex:10, execvocab.tex:9, instrtable_v2.tex:10, interleave_v4.tex:5 | pointer comments | STALE | no captions/ directory in ISCA-27; captions are inline | delete pointers |
| 67 | interleave_v4_8pt.tex:123 | `\reviewtag{[TODO: Fixed this table ref]}` | CURRENT, but caption is stale | caption :121-126 says interleave builds the getOldestTaint shape. Interleave is off in every eval config (VT:368) and can't reach an RI core's transmitter path (UT:48). The base instance was itself forced with otb_shape (:7-9) | keep; decide figure (D6) |
| 68 | pipeline_full_8pt1col.tex:266 | `\reviewtag{[TODO: Made your VOCAB edits…]}` | CURRENT | nits: :270 "transmission criteria" vs decided "transmission mechanism" (UT:102); caption calls Stage 1.5 output "minimal" (it isn't, :185) | keep; two nits |
| 69 | pipeline_full_8pt1col.tex:268 | `% \urgentnote{The text never mentions a Stage 1.5 … unwired STT prototype … 'Bounded-exhaustive set' … unsupported}` (commented) | STALE | Stage 1/1.5 run on cafe2 for 5 families (EM:21-62; STT_6_stl 266,946); not wired into pipeline.py (UT:98); no gem5 run uses it; exhaustive only where Stage 1 finishes, not SPT (cap 200,000, UT:38) | replace + un-comment (R69) |
| 70 | relaxation.tex:117-118; dataflow_8pt.tex:78-79 | commented-out previous captions | OBSOLETE | superseded by live captions (relaxation.tex:119; dataflow_8pt.tex:80-81) | delete |
| 71 | resolutiontiming.tex:108 | `\reviewtag{[TODO: Redrew your resolution-timing figure…; check it]}` | CURRENT | \input at pipeline.tex:165 | keep |
| 72 | dataflow_8pt.tex:82 | `\anna{check this}` | CURRENT | Anna's; caption's "STT protects all memory … lifts that protection" = STT_6's location rule, which draft STT_6_v2 replaces if approved (UT:39, :42) | keep |
| 73 | execvocab_v2_8pt.tex:11 | "% … shared by Recon_6, SPT_6, SPT_6_oneLP, STT_6_stl" | STALE | SPT model is SPT_6_oneLP_v2 (UT:124), which retypes skeleton lines (CL 2026-11-08 23:00 model-fixes); caption :4 "Only the defense block … differs" needs the same qualifier (UT:96, :109) | update comment; qualify caption |
| 74 | execvocab_v2_8pt.tex:30 | `\auditnote{fig}{figure}{Five captions say … 'in the notation of Table I'…}` | CURRENT | captions still cite tab:execvocab for drawing notation (squashrace_v2_8pt.tex:189, reconstl_v2_8pt.tex:124, recon_otb_v2_8pt.tex:134, interleave_v4_8pt.tex:121, instrtable_v2_8pt.tex:6) | keep |
| 75 | intro_threelayer_v2_8pt.tex:43 | `% \auditnote{fig}{…'no existing method (this work)'…}` | RESOLVED | label is now "SimSpect (this work); no prior method" (:34); arrows unified (tag :44) | delete (caption still doesn't say blue = defense-specific) |
| 76 | intro_threelayer_v2_8pt.tex:44 | `\reviewtag{[TODO: Changed the figure: one arrow style…; check]}` | CURRENT | Anna's check pending | keep |
| 77 | bugtable_v3_8pt.tex:5 | `\reviewtag{[TODO: working table, not for submission]}` | CURRENT | commented out (results.tex:52) | keep |
| 78 | bugtable_v3_8pt.tex:13-14 (+ caption † ‡ at :6) | "% dagger … (decision R1)"; "% ddagger … the defense's own paper leaves out … (STT: stores)" | STALE | † settled (UT:32); ‡ for STT stores contradicts STT §6.1 and the "our model's choice" framing (row 16; AA:43) | drop †; ‡ only for InvisiSpec/CleanupSpec; list KV3 as outside our model |
| 79 | bugtable_v3_8pt.tex rows :49-109 | bug names, statuses, evidence | STALE | see "bugtable_v3 row updates" below | refresh before un-hiding |
| 80 | bugtable_v2_8pt.tex (all comments + :5 tag) | old v2 table | OBSOLETE | superseded by v3; its "InvisiSpec & CleanupSpec … out of scope" (:57) and "STL candidate, one trace" (:55) are wrong now (AA:33-38; BAF:168) | delete or archive |
| 81 | xmitcriteria_8pt.tex:1,5,8-11 | "% … Pending." + `\reviewtag{[TODO: edit caption]}` | CURRENT | hidden (pipeline.tex:279); if revived: CleanupSpec row lacks the ownership rule (UT:157); Window column predates until-squash rule | keep |
| 82 | sscolors.tex:5 | "% … parked in sscolors_clauses.tex" | STALE (low) | file not in ISCA-27/tikz; it is simspect/paper_figures/drafts/sscolors_clauses.tex | fix pointer |
| 83 | provenance/tuning comments in all used files (squashrace_v2_8pt:4-14; reconstl_v2_8pt:1-10; recon_otb_v2_8pt:1-18,126; checkerwindow_v4_8pt:1-14; interleave_v4_8pt:1-5,7-15; pipeline_full_8pt1col:1-11 + markers; relaxation:1-12; resolutiontiming:1-9; dataflow_8pt:1-9; intro_threelayer_v2_8pt:1-7,29-35; execvocab_v2_8pt:1,7-10,12-13; instrtable_v2_8pt:2,11,13-19; sscolors:1-4; every \def knob) | code/provenance notes | CURRENT | spot-checked against sources (race ticks vs provenance.json; reconstl base 2679000; OTB ticks 2803000/2807000/2849000) | keep |
| 84 | unused 7pt/older twins: checkerwindow_v4.tex:1-2,158; execvocab_8pt.tex:1,5,10; execvocab.tex:1,5,9; instrtable_v2.tex:1,6,10; interleave_v4.tex:1,5,115; intro_threelayer_v2.tex:32; pipeline_full.tex:2,259; pipeline_full_8pt.tex:266; reconstl_v2.tex:95; squashrace_v2.tex:1,121; xmitcriteria.tex:1,5 | headers + "[TODO: edit caption]" tags | OBSOLETE | not \input anywhere (grep of sections/, root) | delete or ignore |
| 85 | pipeline_vertical.tex:1-2,217 | "% Replaces tikz/threelayer.tex in sections/intro.tex" + `\figtodo{caption: paste the proposed pipeline caption…}` | OBSOLETE | intro uses intro_threelayer_v2_8pt (intro.tex:41); pipeline uses pipeline_full_8pt1col (pipeline.tex:57) | delete with file |
| 86 | reconbugs.tex:1-11; otb_concrete_x86.tex:1-5; recon_concrete_x86.tex:1-5; _old_race_inline.tex:1 | "SUPERSEDED/ARCHIVED … results.tex now uses tikz/reconstl + otbtwobranch / replaced by squashrace.tex" | OBSOLETE (pointers wrong) | results.tex \inputs reconstl_v2_8pt (:167), recon_otb_v2_8pt (:183), squashrace_v2_8pt (:150) | delete files or fix pointers |
| 87 | drawing comments in old files: squashrace, reconstl, otbtwobranch, checkerwindow, threelayer, alloyviolation, interleave, sptable, sptable_v2 (incl. :3 "not yet generated … 2026-10-28"), statetable, _standalone_{checkerwindow,reconstl,squashrace,threelayer,sptable_v2} | — | OBSOLETE | none in the compiled paper (statetable only via hidden pendingfigures.tex:7; alloyviolation only commented at pendingfigures.tex:6) | archive or delete |

### Paste-ready replacements (no tool names; plain notes; body text given separately)

R3, a shorter refresh of the hidden list. Use it only if Anna restores the list:
```
\item \textbf{STT}: the race (Fig.~\ref{fig:race}) is a violation (a branch counts as unresolved until its squash lands); its count needs a re-run with slowed squash timing. New: taint lost through xmm4 (98 of 100 tests). \item \textbf{SPT-Fence}: after the fix every hit traces to the model or concretization (none new); the race was seen only before the fix. \item \textbf{Recon-STT}: store-to-load forwarding bypass in 91 and 94 load tests per mode (2\% sample); OTB reproduced by the Stage~2 OTB merge (100 of 100, none without). \item \textbf{SpecLFB}: UV6 in 1{,}300 / 1{,}304 of 1{,}500 tests per mode (including the second load); jmp-shadow in 148 taken-mode tests. \item \textbf{InvisiSpec}: UV1 in 2{,}995 of 3{,}000 (Spectre) and 3{,}000 (Futuristic). \item \textbf{CleanupSpec}: UV4 in 38 tests; UV3 in 407 of 590 RMW tests with a cold cache; UV5 on a hand-built case; unXpec not checked. \item \textbf{Coverage}: Stage~1 graphs: STT 129, ReCon 129, STT STL 306, ReCon STL 858; SPT stops at its 200{,}000 cap.
```

R5, note:
```
\auditnote{cite}{cite, high}{InvisiSpec, CleanupSpec and SpecLFB are not cited at first mention, though all three are in the bibliography (yan2018invisispec, saileshwar2019cleanupspec, cheng2024speclfb). DoM (sakalis2019delay) and DOLMA (loughlin2021dolma) are uncited too.}
```
R5, body:
```
AMuLeT artifact builds of InvisiSpec~\cite{yan2018invisispec}, CleanupSpec~\cite{saileshwar2019cleanupspec}, and SpecLFB~\cite{cheng2024speclfb}.
```

R6, note:
```
\auditnote{claim}{claim}{`End-to-end' needs two qualifiers. No number here is from the final evaluation yet: every testset is being regenerated from the two-stage models and every campaign re-run. The AMuLeT builds run tests generated from our STT model, scored by a checker that counts a footprint left by any squashed load, not only the target transmitter. The ReCon runs used classic caches, where ReCon's reveal never takes effect, so they test ReCon's implementation of STT.}
```
R6, body:
```
We run \toolname{} end-to-end on the gem5 implementations of STT and SPT, on ReCon's implementation of STT, and on the AMuLeT artifact builds of InvisiSpec~\cite{yan2018invisispec}, CleanupSpec~\cite{saileshwar2019cleanupspec}, and SpecLFB~\cite{cheng2024speclfb}, which we drive with tests from our STT model.
```

R13, un-comment:
```
\urgentnote{23{,}966 comes from runs made before the harness fix and includes 4{,}122 hits that were never re-checked (19{,}845 + 4{,}122 = 23{,}967). The race appears only with slowed squash timing, which the planned evaluation does not include. Re-run that configuration as its own experiment, or describe the inst-047231 example without a count.}
```

R14, un-comment:
```
\urgentnote{After the harness fix every SPT hit traces to the model or to concretization (none new), so `no independent SPT bug' holds for our runs. The SPT race was seen only before the fix and only with slowed squash timing, and its attribution is still open. Say that SPT-Fence lifts its fence on the same resolution signal as STT, and drop `exhibits the same race' unless it is re-run.}
```

R15, note:
```
\auditnote{claim}{claim, high}{68/300 counted loads that hit the cache, which SpecLFB's paper excludes (Sec.~9). The install-keyed run (1\,kB L1D) finds UV6 in 1{,}300 of 1{,}500 not-taken and 1{,}304 of 1{,}500 taken tests, counting the second-load case as UV6 with a broader scope than AMuLeT reports. A further 148 taken-mode tests leak through a separate mechanism (a direct jump after the unresolved branch); whether to report it as a new bug is open. These runs are not the final evaluation.}
```
R15, body:
```
first speculative load in the LSQ unprotected, so that it installs a cache line inside the window; in our runs the next speculative load is often left unprotected too, so UV6 reaches more cases than AMuLeT reports (1{,}300 and 1{,}304 of 1{,}500 tests per branch mode).
```

R16, note:
```
\auditnote{claim}{claim, high}{Store transmitters are out of scope by our choice, but the sentence must not say STT's own contract excludes stores: STT treats stores that act before retirement as transmitters (Sec.~6.1) and lets loads and stores access memory only with untainted addresses (Sec.~6.4.2).}
```
R16, body:
```
We do not target STT's tainted-store\,$\to$\,TLB leak (KV3): our STT model has only load and branch transmitters, although STT's paper also treats stores as transmitters~\cite[Sec.~6.1]{yu2019stt}, so \toolname{} does not cover this leak.
```

R21:
```
\auditnote{write}{writing}{Decided: a branch that has executed but whose squash has not yet landed still counts as unresolved. So this packet (cycle 79; squash at 81) is inside the violation window and the race is a violation. State the rule in the window definition, redraw both trace figures to match, and re-score once the checker follows the rule (it still treats a branch as resolved when it resolves).}
```

R22:
```
\urgentnote{\textbf{VOCAB}: Fig.~\ref{fig:racev2}: rename ``Committed window (lc retires to fnc retires)'' to ``Violation window''. A branch counts as unresolved until its squash lands, so here the window runs from cycle 0 to the squash at 81; draw it that way and say so in the caption.}
```

R24:
```
\auditnote{fig}{figure, high}{Draw one violation window in both trace figures: from lc's retirement until fnc retires or a guarding branch's squash lands, whichever comes first. Fig.~\ref{fig:checkerwindow} ends it at the branch's resolution and Fig.~\ref{fig:racev2} at fnc's retirement.}
```

R27, an optional sentence to add to the row-27 note:
```
In 200 generated load tests, giving each store its own address removes all 80 such hits, which supports the forwarding explanation.
```

R33:
```
\reviewnote{the hand-built trace shows i5 only issuing, but our generated OTB tests (Stage~2 merges an older load into the transmitter's address; 100 of 100 hit, 0 of 100 without the merge) show the transmitter completing while i2 is still unresolved. Say ``completes'' and cite those tests; this build never logs a sent packet, so a cache access cannot be shown.}
```

R46, note:
```
\auditnote{write}{writing, high}{No count here comes from the final runs yet: every testset is being regenerated and every campaign re-run. The checker also tests only the load's execute tick against the window, not the tick at which it obtained its data. Mark the counts that come from earlier runs.}
```
R46, body:
```
Every count below comes from the per-transmitter checker on the running defense build; counts marked $^\dagger$ come from earlier runs and are being repeated.
```

Row 45, sentence to add:
```
On ReCon's builds the checker cannot see a sent packet at all (they never log one), so only loads that complete count there.
```

R50, updated discussion items:
```
\item \textbf{Bounded exhaustiveness}: complete up to the instruction bound where Stage~1 reaches UNSAT (STT, ReCon and the STL models); SPT's Stage~1 stops at its cap, so SPT is not bounded-exhaustive; Stage~1.5 is non-exhaustive by design. \item \textbf{Window semantics}: a branch counts as unresolved until its squash lands, so a transmission after resolution but before the squash (the race) is a violation. \item \textbf{Complementary to random testing}: \toolname{} reproduces the AMuLeT bugs that break a defense's stated guarantee (UV1, UV3--UV6); the others (MSHR contention, instruction-cache fetch, cleanup timing, the store\,$\to$\,TLB leak) lie outside the stated guarantee or outside our model.
```

R53:
```
\auditnote{fact}{fact, low}{Still unsupported: every model in the evaluation uses the branch-only contract. Broader STT contracts exist only as a draft (store shadows, for ReCon's STT) or are parked (Futuristic). PROPOSED TEXT: for STT we have also written broader execution contracts, which we leave to future work}
```

R54:
```
\auditnote{claim}{claim, low}{The evaluation uses one model per defense, and none comes as a raw/intersected pair. Name such pairs or drop the clause. PROPOSED TEXT: \toolname{} can target either interpretation, and we default to the realizable intersection}
```

R56, edit to discussion.tex:31. Replace its first sentence with:
```
SimSpect checks each defense against the guarantee its authors state: each footprint criterion lists only the structures and state that the defense's paper claims to protect, together with the sentence that claims it, and we name the two places where we test less than the paper claims (SpecLFB's exception shadows and STT's store transmitters).
```
Then add after the CleanupSpec sentence:
```
CleanupSpec's failures to undo a speculative install (UV3--UV5) do violate its stated guarantee, and our checker flags them.
```

R57, edit to discussion.tex:33. Replace from "Unlike InvisiSpec's footnote …" through the "Check before use" sentence with:
```
STT, however, also treats stores that act before retirement as transmitters~\cite[\S 6.1]{yu2019stt} and lets loads and stores access memory only once their address is untainted~\cite[\S 6.4.2]{yu2019stt}, so KV3 falls within STT's stated guarantee; leaving store transmitters out is a choice of our model, and SimSpect does not test for KV3.
```

R62, edit to the recon_otb_v2_8pt.tex caption. Replace the last sentence with:
```
We found this bug with a hand-built test; \toolname{}'s Stage~2 reproduces it by merging a second, older load into a transmitter's address (100 of 100 such tests leak on gem5-recon-modded, none without the merge). i0 and i1 are marked committed because they commit before the observation time; when i4 executes, i0 is still unresolved.
```

R69, un-comment:
```
\urgentnote{Stage~1 and Stage~1.5 now run, but no reported result uses their output yet. ``Bounded-exhaustive set'' holds only where Stage~1 runs to completion (so far the STT store-forwarding model; STT and ReCon have one size left), not for SPT, whose Stage~1 stops at its 200{,}000 cap. Qualify the label per defense, or settle how SPT's testset is built first.}
```

### bugtable_v3 row updates (row 79)

**STT**
- Race: drop † (UT:32). Evidence: "pre-fix, slowed squash timing only; count not re-run" (EM:212).
- Pending-squash: "fixed upstream (18e304f); SimSpect's STT row now runs that fixed build (/work/stt-master, EM:192); no pipeline test reaches it" (UT:24). Anna has ruled out differential testing (CL 2026-11-08 ~21:15 main).
- KV3: "outside our model".
- "Excess mispredict-taken hits": "not seen after the fix (0/0, BAF:167)".
- Add "taint dropped through xmm4, confirmed, 98/100 vs 0/100" (stt_xmm4_taint_skip/README.md).
- Add S4 as suspected (SAS:17).

**SPT-Fence**
- Race: keep it as a candidate, drop †.
- br_x, ld and str "untriaged": "not a bug: model/concretization artifacts (round 2: 0 new; round 4: ld 57/48, str 74/60, br_x 51/51)" (BAF:100, :169-171).
- Optionally add A1–A3 as suspected (SAS:21-23).

**Recon-STT** (rename the header, BUGS.md:24)
- STL evidence: "post-fix 91/94 load tests; removing the store alias removes it (0 of 200)".
- OTB evidence: "hand-built test; reproduced by the Stage-2 OTB merge, 100/100 vs 0/100" (VT:369).
- Merge "Load-transmitter hits 7 of 1,323" into STL (UT:123).
- Add R-SA-12 and R-SA-13 as suspected (SAS:18-19).

**InvisiSpec**
- UV1: "2,995/3,000 Spectre, 3,000/3,000 Futuristic; removed by AMuLeT's patch" (AA:33).
- D-TLB row: "in every UV1 hit (D-1)" (AA:66).
- Add IS-1 as suspected (UT:34).

**CleanupSpec**
- UV4: "38 generated tests (8 TBEs)" (AA:37).
- UV5: "flagged on a hand-built case; not seen at scale" (AA:38).
- UV3: "confirmed: 407 of 590 RMW tests, cold cache" (AA:36; UT:165).
- Add the E→M-upgrade cleanup skip as a candidate (AA:36).

**SpecLFB**
- UV6: "1,300/1,304 of 1,500 per mode, incl. the second load" (UT:148). Fold the "second load" row into UV6.
- Add jmp-shadow: "confirmed, 148 taken-mode tests, reproduced on an unmodified build" (BUGS.md:48-51); whether to count it is still open (UT:149).
- The two LFB-path rows: "unreachable in this build" (AA:62).
- Add SL-1 as suspected (UT:35).

### Outdated body or figure text near comments (no comment yet says so, or the comment only hints)

- B1, results.tex:36-37: run list. Use R6. The approved eval set also splits STT into three builds, E2–E4 (EM:184-205).
- B2, results.tex:92-94: "three mechanism classes" (row 12).
- B3, :96-100 and :292-295: 23,966 / 0 at stock (row 13).
- B4, :102: SPT claim (row 14).
- B5, :109: 68/300 (row 15).
- B6, :109-111: "matching STT's own contract of load and branch transmitters" contradicts STT §6.1 (row 16).
- B7, :117 and :179: the OTB is now reproduced by Stage 2, not only built by hand. Interleaving cannot build it (rows 17, 32).
- B8, :160 and :177: titles "ReCon:" should say Recon-STT (row 26).
- B9, :198 and :284: "speculative window" (rows 37, 47).
- B10, :200-204: "Of the eight bugs AMuLeT reports … exactly one (SpecLFB UV6) … the rest … outside the pipeline trace SimSpect observes" is wrong now:
  - AMuLeT reports nine: "3 known and 6 unknown" in fu-2025-amulet.pdf's abstract, and AA:33-43 lists nine.
  - SimSpect flags UV1, UV3, UV4, UV5 (UV5 only on a hand-built case) and UV6 (AA:33-40).
  - Eviction and post-squash residue are visible in the hook trace (AA:14-27).
- B11, discussion.tex:21: "for several defenses we maintain both the raw and the intersected execution contract" (rows 53, 54).
- B12, figure captions: squashrace (row 60), recon_otb (row 62), checkerwindow (row 63), interleave (row 67), execvocab (row 73), pipeline (row 68).
- B13, relaxation.tex:119: "so Alloy does not synthesize them in its initial pass". This depends on an open decision: gen_useful_litmus checks only RR, RC and RS (UT:77), and Stage 1 is RI-only (UT:56), so pane (a)'s RO relaxation is not applied.
- B14: "STT protects all memory" in the dataflow, relaxation, interleave and squashrace captions must change if STT_6_v2 is approved (UT:39, :42).

### Fix first

1. Bug claims at results.tex:92-117 and :292-295 (rows 12, 17, 49). Add:
   - STT xmm4;
   - jmp-shadow, once Anna decides whether to count it (UT:149);
   - UV1/UV3/UV4 and UV6 at scale;
   - the OTB reproduction.
   Mark the SPT race as a candidate.
2. The AMuLeT scope paragraph, results.tex:195-204 (B10).
3. The window rule (rows 21, 22, 24, 59, 63, 78) in the text, both trace figures and the checker.
4. The KV3 sentence, results.tex:109-111, and discussion.tex:33 (rows 16, 57), including the cite key.
5. Pre-fix numbers at :99, :109 and :295 (rows 13, 15).
6. OTB text and figures (rows 32, 33, 62, 67).
7. The run list and end-to-end caveats (rows 5, 6).
8. bugtable_v3 rows before un-hiding it (rows 78, 79).
9. The "exactly the guarantee" overclaim at discussion.tex:31 (row 56).
10. Un-comment the live hidden notes (rows 13, 14, 69). Delete the dead ones (rows 1, 4, 8, 10, 19, 25, 31, 35, 38, 48, 70, 75, 84-87).

### Unused and superseded tikz files

**In the compiled paper:**
- sscolors (preamble)
- intro_threelayer_v2_8pt (intro.tex:41)
- execvocab_v2_8pt (pipeline.tex:18)
- dataflow_8pt (:56)
- pipeline_full_8pt1col (:57), which uses gem5logo.pdf
- relaxation (:101)
- interleave_v4_8pt (:125)
- instrtable_v2_8pt (:159)
- resolutiontiming (:165)
- checkerwindow_v4_8pt (:255)
- squashrace_v2_8pt (results.tex:150)
- reconstl_v2_8pt (:167)
- recon_otb_v2_8pt (:183)

**Kept but commented out:** bugtable_v3_8pt (results.tex:52), xmitcriteria_8pt (pipeline.tex:279).

**Only in the hidden pendingfigures.tex:** statetable (:7), alloyviolation (commented, :6).

**Superseded twins or older versions, not \input anywhere:** checkerwindow_v4, checkerwindow, execvocab, execvocab_8pt, instrtable_v2, interleave_v4, interleave, intro_threelayer_v2, threelayer, pipeline_full, pipeline_full_8pt, pipeline_vertical, reconstl_v2, reconstl, squashrace_v2, squashrace, xmitcriteria, bugtable_v2_8pt, sptable, sptable_v2, otbtwobranch.

**Self-declared archives:** reconbugs, otb_concrete_x86, recon_concrete_x86, _old_race_inline.

**Previews of superseded figures:** _standalone_{checkerwindow, reconstl, squashrace, threelayer, sptable_v2}.tex and their -1.png files.

Duplicate labels (fig:race, fig:otb, fig:pipeline, tab:sptable, fig:ddi-rf) are harmless only while just one of each file is \input.

### Hard decisions surfaced

These are in addition to P1's decisions 1-5, which already cover "what counts as found by SimSpect", "N of M", the race wording and "bounded-exhaustive".

**D1. Is "unresolved until squashed" the paper's and the checker's violation-window rule?**
Options:
- (a) Adopt it everywhere: pipeline.tex:265-277, both trace figures, and check_ld through gem5_common.py:1023-1063. Then re-score. This may add hits on every build, for example the InvisiSpec trap window, IS-1 (UT:34).
- (b) Keep the checker at resolution and report post-resolution transmissions as a separate class.
- (c) Apply the rule only to mispredicted guarding branches.
Evidence: UT:32, SAS:38.
Recommendation: (a). Also close the R1 entries at UT:76 and :107.

**D2. Where does the race number come from?** It exists only in the June slowed-squash runs. Those predate the fix, include 4,122 hits never re-checked, and are outside the approved eval (EM:210-212).
Options:
- (a) Add a slowed-squash experiment to the eval: the minimal setting is commitToIEWDelay=3 (BUG_EXPLAINER.md:104-107), run on /work/stt-master and /work/stt.
- (b) Present one fully traced example plus the timing condition, with no count.
- (c) Drop it from the headline.
Recommendation: (a) if there is time before submission, else (b).

**D3. Which bugs the results claim, and how they are labelled.**
- xmm4: found with FP routing or the FP corpus.
- OTB: found by the authors, reproduced with the Stage-2 OTB merge.
- UV3: RMW tests plus a cold cache.
- jmp-shadow, UV6-broader, UV1, UV4: default tests.
Whether jmp-shadow counts as a new bug is still open (UT:149).
Recommendation: P1's option (b). Count the opt-in finds, each with its configuration named, and count jmp-shadow as a new SpecLFB bug. This is about labelling only; it puts no novelty caveat on either Recon-STT bug.

**D4. How to frame the comparison with AMuLeT (B10).**
Options:
- (a) Rewrite it around each defense's stated guarantee, using the discussion.tex:31 text: 5 of AMuLeT's 9 bugs flagged; the other 4 are outside the stated guarantee or outside our model.
- (b) Keep "different leakage models" and only fix the counts.
- (c) Cut the subsection.
Recommendation: (a).

**D5. KV3 wording.**
Options:
- (a) Say our STT model omits store transmitters by choice, so KV3 is not covered.
- (b) Add store transmitters to the STT model (an .als change, later).
Recommendation: (a). It matches Anna's scope decision and STT §6.1.

**D6. The interleave figure.** It claims interleaving builds OTB, but interleaving is off in every eval config and cannot reach an RI core's transmitter path.
Options:
- (a) Replace it with the OTB merge, the mechanism actually used.
- (b) Keep it but drop the OTB claim.
- (c) Cut it.
Recommendation: (a).

**D7. Naming of the classic-cache results.**
Options:
- (a) Say "Recon-STT" (ReCon's STT) for every classic-cache result, and keep "ReCon" for runs that exercise the reveal (there are none yet).
- (b) Keep "ReCon" with a footnote.
Evidence: BUGS.md:24, EM:195, UT:138.
Recommendation: (a). Naming does not affect novelty: both bugs stay new.

**D8. The SPT claim at results.tex:102.**
Options:
- (a) Say "no SPT bug found after triage; SPT-Fence lifts its fence on the same resolution signal" (a code-level statement).
- (b) First run the SPT race diagnostic under slowed squash timing (PAPER_PLAN.md:208).
Recommendation: (a), unless (b) can run in time.

### Side findings in simspect docs (outside the paper; flag only)

- UT:76 and :107 still list R1 as open, although UT:32 decided it.
- STATUS.md:391-393 still says the rf fact is not applied; it was applied on 2026-11-09 (CL 2026-11-09 main).
- BUGS.md:
  - It has no entry for STT xmm4.
  - It still says "/work/amulet: no sweep results yet" (BUGS.md:104-107).
  - BT:51 still says OTB is not caught by SimSpect.
- PAPER_RESULTS.md, compiled 2026-06-03, still says "1 of 8 AMuLeT bugs in scope" and 68/300.
- specs/defense_units.json:131 still carries 23,966.
- Many paper notes cite STATUS.md line numbers that have moved: :28-33, :33, :390-396.

Files read: ~/trippel/ISCA-27/sections/results.tex, ~/trippel/ISCA-27/sections/discussion.tex, every file in ~/trippel/ISCA-27/tikz/, ~/trippel/ISCA-27/bare_conf_compsoc.tex, plus the simspect docs cited above and the local papers in ~/Documents/quail/sources/papers/: yu-2019-stt, yan-2018-invisispec-original, saileshwar-2019-cleanupspec, cheng-2024-speclfb, fu-2025-amulet.
