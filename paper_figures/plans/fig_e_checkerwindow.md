# Figure (e): pipeline inspection graph (checker violation window)

**Status:** v4 draft, 2026-11-02, revised from Anna's feedback on v3 (see "v4 changes" below). Files in `paper_figures/drafts/`: `checkerwindow_v4.tex` (the body: the `tikzpicture` and its local definitions inside `{ }`, which is what would go into the paper's `tikz/`), `captions/checkerwindow_v4.tex` (the proposed caption alone), and `_standalone_checkerwindow_v4.tex` + `_standalone_checkerwindow_v4-1.png` (the preview, 300 dpi, `border={2pt 24pt 2pt 2pt}` with blank space below for a caption; the caption itself is not rendered). Body size **250.6 × 178.9 pt** (measured with `\sbox` inside IEEEtran; one column is 252 pt). v3 (`_standalone_checkerwindow_v3.tex`, 244.9 × 101.7 pt) is kept unchanged. Nothing in the paper clone was touched.

## v4 changes (2026-11-02)

What Anna asked for on v3, and what v4 does about each:

- **"Is it clear? We might need more of a caption."** There is a new four-sentence caption, below under "Proposed caption (v4)", also in `paper_figures/drafts/captions/checkerwindow_v4.tex`. It opens with a bold title sentence, like the sibling captions.
- **"I'm going to need more labels there."** v4 adds:
  - a key line at the top: "F: fetch, D: decode, E: issue, Dotted: elided cycles", plus the gray "Defense-specific" legend at top right;
  - a gloss under each role: "Last committed", "First non-committed (unresolved branch)", "Transmitter";
  - labels at both window edges: "Retires (window opens)" on i0 and "Resolves (window closes)" on i1;
  - "5000-cycle resolve stall", "Retires", "Squashed", and a labelled criterion source on the left.
- **"Why is capitalization unclear."** One convention, applied everywhere (stated below under "Text convention").
- **"A transmission that is a clearer point."** The transmission is now the only star in the figure: a filled 8.5 pt five-point star on the xmit bar at cycle 70, with a two-line callout, "Transmission (L1D eviction)".
  - The open-circle speculative-buffer fill (cycle 101) is gone from the timeline, so nothing competes with the star. The criterion box says in words that speculative-buffer fills do not count.
  - Dropping it also removed one axis segment, which freed width for the window.
- **"Annotation on the left that this is marked transmitter by a label propagated from the Alloy."** The left column now opens with a white annotation-file icon (`{ }`, the same icon the pipeline figure uses for annotations), headed "Role labels from the Alloy instance". A bus line runs from it to the three row labels (i0: lc, i1: fnc, i2: xmit).
  - All three roles are drawn as coming from Alloy because all three do: xmit from `isxm`, and lc / fnc from `iscommitted` via `commit_boundary`. Citations are in "Label propagation" below.
- **"Transmission criteria come from the defense, so we check for them in the unresolved window."** The logic is drawn left to right and bottom to top:
  - a gray document icon, "Defense transmission criterion" (the defense-specific source of truth, `specs/leakage/invisispec.json`);
  - an arrow from it to the gray criterion box, which starts with "*InvisiSpec, checked inside the window:*";
  - an arrow from the box up into the window frame.
  - The window's edges are labelled with what opens and closes it. This follows the pipeline figure's sources-on-the-left style.
- **"These generally need more margins."**
  - Rows are 30 pt apart (v3: 17 pt).
  - The elided stretches inside the window are 14 pt wide (v3: 9 pt), which widens the window to about 82 pt, so every label inside it clears the frame by at least 5 pt.
  - The window frame sits 13 pt above i0 and 25 pt below i2. The criterion box has 3 pt padding. Glosses sit on a uniform 8 pt baseline grid.
  - Checked at 800–900 dpi: nothing touches. The closest pair is F / D at one-cycle spacing (6.5 pt between centres, about 2 pt between glyphs, a normal word space).
- **Lowercase instruction ids.** i0, i1, i2, so i is not misread as l.

Other changes:

- **Font size.** Everything is `\scriptsize` (7 pt), per `VISUAL_LANGUAGE.md` "one size everywhere". v3 used `\footnotesize` for row labels.
- **Window name.** "Violation window" became **"Unresolved window"**, from Anna's wording in this feedback (Decision 5).
- **Transmitter name.** "Xm" became **xmit**, the annotation key's name.
- **Leak safety.** All helper macros are prefixed `\cw…`. There are no global pgfmath functions (v3's `xa`…`xe` were replaced by `\cwx{segment}{cycle}`), and everything is inside `{ }`.
  - Tested by `\input`-ing the body twice in an IEEEtran document that already defines `\docicon`, `\edges` and `\cyc`: no errors, nothing leaked, and the pre-existing macros were untouched.
  - The knob lines put `%` straight after `}`, so no stray spaces enter in horizontal mode. An earlier draft had 21 of them, which made an `\sbox` measure 324 pt.
- **Libraries.** The body needs TikZ `calc` and `shapes.geometric` (for the star). The paper preamble already loads both.

### Text convention (capitalization and fonts)

- **Sentence case for every prose label.** The first letter is capital and the rest lowercase, except proper names and acronyms (InvisiSpec, Alloy, L1D, L2, D-TLB). Examples: "Unresolved window", "Retires (window opens)", "Squashed", "Cycle", "Defense transmission criterion", "Role labels from the Alloy instance".
- **After a colon, lowercase** (the text continues the label): "F: fetch", "Dotted: elided cycles", "InvisiSpec, checked inside the window: a fill, …".
- **lc, fnc and xmit are fixed abbreviations.** They are always lowercase and always upright roman, set with one macro, `\cwab`, so they stay upright even inside italic text. They are never capitalized, and labels are worded so that no label begins with one.
- **Identifiers keep their fixed form:** i0–i2, the stage letters F / D / E (capitals, as in Anna's sketch), and cycle numbers.
- **Italic is for annotations; upright is for everything else.**
  - Italic: role glosses and timeline events ("Last committed", "Retires", "Resolves", "Squashed", "Transmission", "5000-cycle resolve stall"), and the criterion box's lead-in, which works like the italic list headers in the pipeline figure.
  - Upright: identifiers, names and headings (row ids, the key, the window title, source labels, cycle numbers, the criterion text).
- **No bold** in the figure. Bold is reserved for panel and stage labels, and this figure has none.

### Label propagation (why i2 is "the transmitter")

The xmit label travels from the Alloy instance to the checker as follows:

1. **Alloy.** `STAGE1_alloy/models/STT_6.als:62` declares `isxm: lone tBool` and `:68` declares `fun xm`. `:269` `fact one_xm` requires exactly one transmitter, and `:270-273` `fact tag_xm` makes its operand speculatively protected.
2. **Concretization (parsexml.py).**
   - `STAGE2_compilation/parsexml.py:382` reads the instance's `isxm` field, and `:408` and `:451` set each record's `xm` flag.
   - `emit_branch_annotations` (`:2565`) picks the `xm` record (`:2609-2614`) and writes `payload["xmit"] = {pc, kind, atom}` into `<stem>.ann.json` (`:2636`).
3. **Address resolution.** `STAGE2_compilation/compile_annotate.py:270-281` resolves `xmit.pc` to the x86 address.
4. **Stage 3.**
   - `pipeline.py:296-326` (`_KIND_TO_CHECKER`, `_read_xmit_kind`) routes each test to its checker by `ann["xmit"]["kind"]`.
   - `STAGE3_gem5/gem5_common.py:759` `load_annotation` returns `xmit`, and `:1097-1104` `process_one` resolves `xmit_pc` and hands it to the checker.

lc and fnc follow the same path. `parsexml.py:1902-1927` `commit_boundary` derives them from the Alloy `iscommitted` flags (Alloy instructions only), and `:2622-2643` writes them as `ann["commit_boundary"]`.

**Caveat (Decision 3, still open).** For load, branch and "other" transmitters, `xmit_pc` decides whose signal is timed. `check_footprint.py`, which this InvisiSpec figure uses, receives `xmit_pc` (`:473`) but does not use it to pick the actor. It counts any squashed instruction younger than lc (`:216-223`). The figure, like the paper text, frames the transmission as xmit's.

### Data re-checked this session

- I decompressed the fixture again and parsed it with `gem5_common.parse_pipeview_by_seq`. Seqs 556, 564 and 573 match the table below.
  - The hook lines for seq 573 confirm the L1D eviction at tick 3,192,000 (cycle 70), the SB fill at 3,207,500 (cycle 101), and the squash of seq 564 at 5,661,000 (cycle 5008).
- `check_footprint.evaluate_trace` with `specs/leakage/invisispec.json` and the meta values still returns `leak=True`, `lc_retire=3161000`, `fnc_retire=5663500`, `actor_mode=spec`.

## Proposed caption (v4)

Also in `paper_figures/drafts/captions/checkerwindow_v4.tex`. Paper text is read-only for Claude; Anna pastes it.

\textbf{How the checker decides a violation, on a real gem5 trace} (InvisiSpec build, test inst-002014). Each bar is one instruction from fetch (F) through decode (D) and issue (E) to retirement; dotted stretches are elided cycles. The roles lc (last committed), fnc (first non-committed, here the unresolved branch) and xmit (transmitter) are labels carried from the Alloy instance, and the unresolved window runs from lc's retirement to the branch's resolution. Inside that window the checker applies the defense's transmission criterion (gray): xmit's L1D eviction ($\star$) meets InvisiSpec's criterion before xmit is squashed, so the test is reported as a violation.

## v3 (superseded; kept for reference)

v3 followed `VISUAL_LANGUAGE.md`:

- black on white, with one gray (`black!12`) used only for the defense-specific note;
- bold only for the "Violation window" title;
- `\footnotesize` / `\scriptsize\itshape`, no font family set;
- the calc library only, and a `TUNING KNOBS` block at the top.

The v3 sections below describe the v3 drawing. Where v4 differs, the "v4 changes" section above wins.

## What exists

- `tikz/checkerwindow.tex`, `\input` at `sections/pipeline.tex:59`, with `tikz/_standalone_checkerwindow.tex` and its PNG. It is one horizontal time axis with an `lc` retire tick and an `fnc` retire tick, a green brace and green shading labelled "committed window", three teal "resolved" dots, a blue transmitter dot at $t_o$, four purple "unresolved" dots, and a color legend.
- Caption: a violation is reported when the transmitter's signal (cache touch, redirect, store-forward) occurs at $t_o$ strictly inside `(lc_retire, fnc_retire)` while resolved primitives have resolved and unresolved primitives have not.
- Against the visual language it uses four colors, `\sffamily`, and `\tiny` text (below 7 pt). It shows no instructions and no pipeline stages.
- Against the code: it draws "resolved before $t_o$" as a requirement, but resolved branches are reported, not gated (`wiki/design/RESOLUTION_HOOKS.md:42`, `wiki/design/COMMIT_BOUNDARY.md:60`, `STAGE3_gem5/gem5_common.py:1173`). Its signal list has no footprint signal, which is what the InvisiSpec, SpecLFB and CleanupSpec criteria use.

## What changes (Anna's sketch)

Anna's sketch (e): "Pipeline inspection graph", stage marks "F D E [Xm] …", rows i0, i1, i2, each a staggered interval bar, the transmitter's action marked, "SHOW A VIOLATION window!!", and "criteria determined from defense, e.g. InvisiSpec is …".

- Rows: i0 = lc (last committed), i1 = fnc (first non-committed, which in this test is also the one unresolved branch), i2 = Xm (the transmitter, a load). Each bar runs from fetch to retire (i2: to its squash, ×). Ticks: F = fetch, D = decode, E = issue. Rename, dispatch and complete ticks exist in the trace but are not drawn.
- One linear scale (6.2 pt per cycle) in five axis segments; dotted bar stretches are elided cycles. The x axis is cycles after i0's fetch.
- The violation window is a heavy frame (0.9 pt) from lc's retire to the branch's resolution, titled in bold. Inside it, on the Xm bar: ● = the transmission (an L1D eviction), ○ = the speculative-buffer fill (allowed).
- The gray box states that the transmission signal is defense-specific, with InvisiSpec's criterion and STT's for contrast.
- Not done yet: the `\input` version (`tikz/checkerwindow_v3.tex` with the `figure` environment). When it is made, prefix the helper names (`\edges`, `\tck`, `\longbar`, pgfmath functions `xa`…`xe`) so they cannot clash with other figures in the paper.

## Data source: a real trace (not schematic)

- **Trace:** `STAGE3_gem5/tests/fixtures/inv_uv1.pipeview.txt.gz` with `STAGE3_gem5/tests/fixtures/inv_uv1.meta.json`. Copied from cafe2 `/work/amulet/simspect_hooks_verify/inv_uv1/new/pipeview.txt` (2026-10-28, `STAGE3_gem5/tests/test_check_footprint.py:4-6`).
- **Test:** STT_6 `mispredict_not_taken/inst-002014` (`gem5-hooks/verify/run_all_verify.sh:21`; `wiki/design/SIMSPECT_HOOKS.md:112`).
- **Build and flags (from the meta `cmd`):** `amulet-gem5-InvisiSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt`, `--cpu-type=DerivO3CPU --caches --scheme=2 --branch-ann-file=… --ruby --scheme=SpectreSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1 --l1d_size=1kB --l1d_assoc=2`, unresolved stall 5000 cycles on pc `0x401c53`, 500 ticks/cycle.
- **What kind of run:** this was the SimSpect-hooks verification run, not a campaign. The 1 kB / 2-way L1D is SimSpect's amplification for UV1 (`results/STT_6_invisispec_full_spectre/README.md`, flags table).
- **Is it a real bug?** The L1D eviction is InvisiSpec UV1, confirmed as a real implementation bug: AMuLeT's patch removes exactly these hits (29/30 → 0/30, `wiki/findings/mdsToRead/INVISISPEC_UV1_CONFIRMED.md` §3b, §4).
- **Cycle convention:** cycle = (tick − 3,157,000) / 500. Tick 3,157,000 is i0's fetch.

The three drawn instructions (from `gem5_common.parse_pipeview_by_seq`; for multi-µop instructions the checker uses `best_record`, `gem5_common.py:739-754`, which picks the µop that retires last):

| Row | Role | PC | gem5 macro-op | seq | F | D | R | dispatch | I | C | retire |
|---|---|---|---|---|---|---|---|---|---|---|---|
| i0 | lc | 0x401c42 | MOV_R_R | 556 | 3157000 (0) | 3157500 (1) | 3158000 (2) | 3159000 (4) | 3159000 (4) | 3159500 (5) | 3161000 (8) |
| i1 | fnc = unresolved branch | 0x401c53 | JNZ_I (µop 2 of 3) | 564 | 3157500 (1) | 3158000 (2) | 3158500 (3) | 3159500 (5) | 3160000 (6) | 3160500 (7) | 5663500 (5013) |
| i2 | Xm (load transmitter) | 0x401c6a | MOV_R_M | 573 | 3158000 (2) | 3158500 (3) | 3159000 (4) | 3160000 (6) | 3177000 (40) | 3177500 (41) | 0 (squashed) |

Hook events used (trace lines, `O3PipeView:simspect:` prefix, format in `wiki/design/SIMSPECT_HOOKS.md`):

| Tick (cycle) | Event | Meaning | In the figure |
|---|---|---|---|
| 3192000 (70) | `L1D:evict:line=0x3580:seq=573:pc=0x401c6a:victim=0x3980` | Xm's request evicts L1D line 0x3980 (UV1) | ● "L1D evict", labelled "transmission" |
| 3207500 (101) | `SB:buf_fill:line=0x3580:seq=573:pc=0x401c6a` | Xm's invisible speculative read lands in InvisiSpec's speculative buffer (SB) | ○ "SB fill" |
| 5661000 (5008) | `ROB:squash:seq=564:pc=0x401c53:sq=4` | the branch resolves and squashes younger instructions, Xm included | × "squashed" |
| 3177500 (41) | `DTLB:repl_touch:…:seq=573` | D-TLB replacement update by Xm; counted by the checker, open triage item | not drawn (Decision 2) |
| 3196000 (78) | `L2:coh:line=0x3980:seq=573` | L2 coherence change from the victim writeback; counted, open triage item | not drawn (Decision 2) |

**Window, as the checker computes it.** This pre-2026-10-30 trace has no `BR` resolve lines, so `check_branch_resolutions` uses its estimate, complete + stall × ticks/cycle (`gem5_common.py:992`): 3,160,500 + 5000 × 500 = 5,660,500 (cycle 5007). In-window means lc_retire 3,161,000 < t < fnc_retire 5,663,500 and t < 5,660,500 (`check_footprint.py:207-214`). The effective window is therefore cycles (8, 5007). The drawn right edge is the branch resolution at 5007; fnc retires 6 cycles later, at 5013. The observed squash broadcast is at 5008.

**Checker verdict, rerun locally on the fixture (no gem5):** `check_footprint.evaluate_trace(inv_uv1.txt, invisispec.json, lc_pc=0x401c42, fnc_pc=0x401c53, unresolved=[0x401c53, 5000], 500, scheme_name="SpectreSafeInvisibleSpec")` gives `actor_mode=spec, lc_retire=3161000, fnc_retire=5663500, lc_seq=556, leak=True, decided=True`. Offending, in window: L1D evict 0x39c0 (seq 576), L1D evict 0x3980 (seq 573), L2 coh 0x3b40 (seq 566), 0x39c0 (576) and 0x3980 (573), and DTLB repl_touch (seqs 579, 582, 573). Outside the window: L1D evict 0x3b40 by seq 566 at tick 3,161,000. That tick equals lc_retire, so the strict `>` excludes it. The script is in the session scratchpad (`…/scratchpad/cw/an.py`). To reproduce it, decompress the fixture, then call `check_footprint.load_criterion` and `evaluate_trace` with the meta values.

**What the figure leaves out:** the program's other instructions. Between lc and fnc there are `IMUL_R_R`, `MOV_R_I` and `TEST_R_R`. Between fnc and Xm there are `LEA_R_M`, the earlier speculative load `MOV_R_M` at 0x401c5a (seq 566, which feeds Xm's index, claudelog 2026-06-03 "RE-CORRECTION"), `XOR_R_R`, `TEST_R_R`, `JNZ_I` at 0x401c63 and `LEA_R_M`. It also leaves out rename, dispatch and complete ticks, and the footprints of the other squashed loads.

## Window and criterion as drawn

- **Window (all defenses):** lc_retire < t < fnc_retire (0 means ∞). The specified lc must actually retire. Every annotated unresolved branch must still be unresolved at t: on hooked binaries the observed `resolve_visible` tick, on older ones the estimate. Sources: `check_ld.py:95-114`, `check_br.py:85-99`, `check_other.py:32-42`, `check_footprint.py:207-214`, `gem5_common.py:940-995`, `wiki/design/COMMIT_BOUNDARY.md:55-60`, and the paper text `sections/pipeline.tex:57`.
- **Transmission (defense-specific):** InvisiSpec v1 footprint criterion. A fill / evict / inv / coh / repl_touch event in L1D, L2, DIR or DTLB, caused by a squashed instruction younger than lc, inside the window (`specs/leakage/invisispec.json:70-105` observation, `:107-131` actors, `:132-145` window, `:164-168` leak; `check_footprint.py:273`). SB / LLCSB buffer events and expose / validate are allowed.

## Per-defense transmission criterion

| Defense (build) | Checker the pipeline routes to | Timed signal | Counts | Does not count | Source |
|---|---|---|---|---|---|
| STT, SPT, Recon: load transmitter (`stt`, `gem5-spt`, `gem5-recon-modded`) | `check_ld.py` via `_KIND_TO_CHECKER` (`pipeline.py:296-314`; `specs/leakage/stt.json`, `spt.json`, `recon.json`) | LSQ "Executing load" tick, falling back to pipeview `complete` (`check_ld.py:83-87`) | in window **and** the data was obtained: `reached_cache` (a read packet) or `store_forward` (no packet, but pipeview complete > 0) (`check_ld.py:116-146`, `_xmit_cache_fate` `:39-75`) | `spec_read_only`, `executed_no_packet` that never completes (delay-unit bounce), `never_executed`. Squash timing never gates. | `check_ld.py`; `specs/transmitter_criteria.json` `kinds.ld` |
| STT, SPT, Recon: branch transmitter | `check_br.py` | Commit-trace "Squashing due to branch mispred" tick, falling back to `complete` with no Commit trace (`check_br.py:51-76`; parser `gem5_common.py:716-737`) | the branch redirected (fall-through never retires) inside the window (`check_br.py:85-99`) | resolving without broadcasting the squash (STT "made pending") | `check_br.py:51-58` |
| Variable-latency "other" transmitter | `check_other.py` | pipeview `complete` (`check_other.py:26-42`) | complete inside the window | — | `check_other.py:1-13` |
| SPT store transmitter | none ("NEEDS: store-transmitter checker") | — | — | — | `specs/leakage/spt.json`; `specs/transmitter_criteria.json` `kinds.str` |
| **InvisiSpec** (`amulet-InvisiSpec`, `--ruby`) | `check_footprint.py` + `specs/leakage/invisispec.json` (`results/STT_6_invisispec_full_spectre/run_config.jsonc:28-29`) | each SimSpect hook event's tick | ∃ fill / evict / inv / coh / repl_touch in {L1D, L2, DIR, DTLB} by a squashed instruction younger than lc, inside the window (Spectre mode). Futuristic mode: before the load's visibility point. | SB / LLCSB fills and releases, expose / validate; L1I, ITLB and MSHR / TBE are out of scope | `invisispec.json`; paper p4 §V-A2 and p5 §V-B (quotes below) |
| InvisiSpec, legacy | `check_ld_invisispec.py` | expose / validate tick (`gem5_common.parse_lsq`, `expose_re`, `:606-609`) | expose / validate inside the window (`check_ld_invisispec.py:24-34, 65-96`) | the invisible spec read and its packet | `check_ld_invisispec.py:5-22` |
| SpecLFB (classic `build/X86`) | `check_footprint.py` + `specs/leakage/speclfb.json` | hook event tick | ∃ fill / evict in {L1D, L2} by a squashed instruction younger than lc, inside the window (`speclfb.json:134-137`) | LFB buffer events; repl_touch | `speclfb.json`; legacy `check_ld_speclfb.py:20-30` (L1 miss install, unprotected) |
| CleanupSpec (`--ruby`) | `check_footprint.py` + `specs/leakage/cleanupspec.json` | hook event tick | per (structure, line) in {L1D, L2}: an in-window speculative install or eviction not undone by cleanup, or over-undone (`cleanupspec.json:188`) | L2 victims (randomized L2), replacement state, DIR (by design) | `cleanupspec.json`; legacy `check_ld_cleanupspec.py:1-30` |

## InvisiSpec criterion: where it comes from

- **Paper, read this session** (`~/Documents/quail/sources/papers/yan-2018-invisispec.pdf`, the authors' corrected version):
  - PDF p4, §V-A2 "Making USLs Invisible": a USL "cannot modify the cache hierarchy in any way that is visible to other threads, including the coherence states. A USL loads the data into a special buffer that we call Speculative Buffer (SB), and not into the local caches."
  - PDF p5, §V-B: "The line is only stored in the local SB … USLs do not modify the cache coherence states, cache replacement algorithm states, or any other cache hierarchy state."
  - PDF p4, §IV-A1 (Spectre model): "USLs are the speculative loads that follow an unresolved control-flow instruction."
- **Criterion JSON:** `specs/leakage/invisispec.json` (schema `simspect.transmission_criterion/v1`, 2026-10-28, scope = Anna's 2026-10-28 decision). Its `source.claims` quote the same pages plus p3 §III-B (D-TLB) and p9 §VI-E1 / VI-E3.
- **Evaluated by:** `STAGE3_gem5/check_footprint.py`. Format: `wiki/design/TRANSMISSION_CRITERIA_FORMAT.md`, "Criterion JSONs + checker".

## Stale or contradicting sources noticed (flagged here, not edited)

- `specs/transmitter_criteria.json` `kinds.br_x.not_leak_if` and repo `CLAUDE.md` ("Leak criteria") both say `check_br.py` does not enforce the lc/fnc window. It now does (`check_br.py:85-99`).
- `sections/pipeline.tex:63` says InvisiSpec uses "an `expose` tick". That is the legacy `check_ld_invisispec.py`. The InvisiSpec run configs now route to `check_footprint.py` (Decision 1).
- `sections/pipeline.tex:70` says an "other" transmitter transmits through a fault. `check_other.py:36-42` keys on the `complete` tick and does no fault detection.
- `sections/pipeline.tex:73` describes a store-transmitter signal, but no store checker exists (`specs/transmitter_criteria.json` `kinds.str`).
- `wiki/design/TRANSMISSION_CRITERIA_FORMAT.md:1-3` still says "PROPOSAL, awaiting Anna" and has "placeholders from memory". The section at its end says the criteria are built.
- (Noticed 2026-11-02, v4.) The figure captions use different names for the same things:
  - the window: "committed window" (`sections/pipeline.tex:55-57`), "speculative window" (`paper_figures/drafts/captions/pipeline_vertical.tex`), and v4's "unresolved window";
  - fnc: "first uncommitted" (`paper_figures/drafts/captions/instrtable_v2.tex`) vs "first non-committed" (paper text, `parsexml.py` `first_noncommitted`, and v4).
  - See Decisions 5 and 7.

## Proposed caption (v3, superseded by the v4 caption above)

Pipeline inspection of a real violation (InvisiSpec, STT_6 test inst-002014). Each bar is one instruction from fetch (F) to retire, with decode (D) and issue (E) marked; dotted stretches are elided cycles. The violation window opens when the last committed instruction (lc) retires and closes when the unresolved branch, here also the first non-committed instruction (fnc), resolves. Inside it, the transmitter (Xm) evicts an L1D line (●), which InvisiSpec forbids, before it is squashed. Its fill of the speculative buffer (○) is allowed. What counts as a transmission is defense-specific (shaded).

## Decisions for Anna

1. **Which InvisiSpec criterion does the paper present?**
   - (a) The v1 footprint criterion (`check_footprint.py` + `invisispec.json`, what the `results/STT_6_invisispec_full_*` configs route to). This is drawn.
   - (b) The legacy expose-tick criterion (`check_ld_invisispec.py`, which `sections/pipeline.tex:63` describes).
   - Under (b), this trace is **not** a violation: Xm never exposes, and there is no expose / validate event in the trace.
   - Recommendation: (a), and you update `pipeline.tex:63`.
2. **Which event is "the transmission" on the xmit bar?**
   - Drawn: the L1D eviction at cycle 70 (UV1, confirmed by the AMuLeT-patch differential).
   - The checker also counts xmit's DTLB repl_touch (cycle 41) and L2 coh (cycle 78). Those kinds are open triage (`TRANSMISSION_CRITERIA_FORMAT.md:151`, possible attribution artifacts), so I left them off.
   - Recommendation: keep the L1D eviction until DTLB / coh triage is done.
3. **Per-transmitter framing vs the footprint criterion.**
   - The footprint criterion counts any squashed instruction younger than lc (`check_footprint.py:216-223`, `squashed_after_lc`), not only the Alloy transmitter. In this trace three loads (seqs 566, 573 = xmit, 576) leave in-window footprints. The earliest is L2 coh by seq 566 at cycle 16.
   - The paper (`pipeline.tex:55, 61`) and this figure frame the signal as the transmitter's.
   - Options: keep the framing and say so in the text; restrict the criterion's actor to the transmitter's seq (a semantics change); or reframe the text for footprint defenses.
   - Recommendation: keep the figure as drawn and decide the semantics separately.
4. **Window right edge.**
   - Drawn: the intersection (lc_retire, min(fnc_retire, branch resolution)) = cycles (8, 5007), because that is what the checker gates on.
   - The paper text names `(lc_retire, fnc_retire)` plus the unresolved-branch condition.
   - The 5007 is the checker's estimate (no `BR` lines in this pre-hook trace); the observed squash is at 5008.
   - Recommendation: keep the intersection; the caption explains it.
5. **Name of the window.** Four names are in play:
   - "Violation window" (your sketch, v3);
   - "committed window" (`pipeline.tex:55-57`, the existing figure);
   - "speculative window" (the pipeline-figure caption);
   - "unresolved window" (your v3 feedback wording, **used in v4**).
   - The text, this figure and the pipeline caption should use one name.
   - Recommendation: "unresolved window". It describes what the checker gates on (lc retired, the guarding branch still unresolved). "Committed window" sounds like the committed instructions' window, and "violation window" names the outcome, not the interval.
6. **Real or schematic.**
   - The real trace forces a broken axis (5 segments).
   - It is an amplified config (1 kB L1D) from a hook-verification run, not a campaign.
   - Alternatives: the recon OTB repro trace (`oldest_taint_bug/debug_out/pipeview_scheme2.txt`, a check_ld-style real gem5 bug), or a labelled schematic.
   - Recommendation: keep this one; it matches the "e.g. InvisiSpec" annotation exactly.
7. **Notation.**
   - v4 uses **xmit** (the annotation key) instead of your sketch's "Xm".
   - lc / fnc / xmit are upright roman in v4, through one macro, `\cwab`, per the visual language's "no typewriter except literal code". The paper text sets lc and fnc in `\texttt` (`pipeline.tex:57`).
   - To match the paper, change `\cwab` to `\texttt` (one line in `checkerwindow_v4.tex`); otherwise the paper text should switch to roman.
   - Recommendation: one font in both places. Roman is the lighter choice at 7 pt.
   - E is placed at the issue tick; rename, dispatch and complete are omitted.
8. **Row labels.** Only roles are shown. The trace's gem5 macro-op names (`MOV_R_R`, `JNZ_I`, `MOV_R_M`) were dropped to keep the column width. The AT&T asm is not on this Mac: it is at cafe2 `/tests/simspect/testsets/STT_6/mispredict_not_taken/asm/inst-002014.s`. Should a mnemonic go back in?
9. **STT contrast line in the gray box.** v4 drops it: one defense per minifig, and the box now reads as "the criterion that is checked in this window". Restore it if you want the box to show that the criterion differs per defense; the cost is one more box line.
10. **The speculative-buffer fill (v4: dropped from the timeline).**
    - v3 drew it as ○ at cycle 101 next to the ● transmission. You asked for one clear transmission point, so v4 removes it and says "Speculative-buffer fills do not count" in the criterion box.
    - Restoring it as a small open marker at cycle 101 shows what the criterion rejects, but costs one axis segment (about 28 pt of width) and competes with the star.
    - Recommendation: keep it out.
11. **Name of the defense source of truth.** v4 labels the gray icon "Defense transmission criterion". The pipeline figure labels the same source "Defense transmission mechanisms". The two figures should use one term.
    - Recommendation: "transmission criterion" in both, which matches `specs/leakage/*.json` (schema `simspect.transmission_criterion/v1`) and the pipeline caption's "transmission criteria".
12. **Font size vs the pipeline figure.** v4 is 7 pt throughout, per `VISUAL_LANGUAGE.md` ("one size everywhere: `\scriptsize`"), but the current pipeline-figure draft uses 8 pt (`\footnotesize`) for its main text.
    - If figures should match the pipeline figure, set `\cwfs` to `\footnotesize`. At 8 pt the width (about 250 pt) no longer fits, and the knobs (`\cwcyc`, `\cwbrk`, `\cwtl`) would need retuning.
13. **Height.** v4 is 178.9 pt tall (v3: 101.7 pt), the price of the extra labels, margins and the criterion row.
    - Knobs to shrink it: `\cwrowh` (30), `\cwwbot` (25), `\cwgap` (10). Dropping the key line saves about 13 pt if the caption carries F / D / E.
    - Recommendation: keep it as is unless page budget forces a cut.
