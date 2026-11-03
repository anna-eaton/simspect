# SimSpect paper figures: shared visual language

## CURRENT RULES (2026-11-02; supersede anything older below)

- **Size:** one column (252pt) by default; full width (516pt) only for wide tables. Anna rejected a double-wide pipeline. **All text at least 8pt** (`\footnotesize`), including arc/edge labels, qualifiers, icon glyphs (draw them as paths), and sub/superscripts (write `r0`, not `$r_0$`). Squeeze spacing; never cut words.
- **Color (2026-11-03, Anna; pushed in test-paper `a185e1f`):** light fills only, all text black except red transmitters/bugs. **Blue** `#DCE8F4` (outline/header `#2F5F8F`) = defense-specific / defense sources of truth. **Tan** `#FCEFD6` = speculative: a background band behind the rows after an unresolved branch, with a vertical italic "speculative" label on the band's right edge, and the checker's unresolved window. **Lavender** `#E4DAF1` = protection set: protected state tokens, the 3b slab, and a light highlighter (3.6pt, multiply blend) under the thick protection-set dataflow edges, which stay black on top so grayscale still reads. **Light red** `#F7E0DD` = the 3c slab and transmitter cells; red ink `#B3322C` = transmitters, transmissions, real bugs. Pipeline: 3a tan, 3b lavender, 3c light red, everything else defense-specific blue. Speculation/timing directives never colored. Resolution status (*resolved*/*unresolved*) is shown only on branches and stores. Palette `paper_figures/drafts/sscolors.tex` (paper: `tikz/sscolors.tex`, one preamble line); stronger per-clause palette parked in `sscolors_clauses.tex`; rejected pipeline redesigns kept as `design_mocks/pipe_opt{1,2,3}`. Trippel precedent: overviews grayscale, color only for meaning, red = attack/bug (`TRIPPEL_FIGURE_STYLE.md`).
- **Shapes (shape = type):** rounded stage blobs with the title on the border; stacked slabs for constraints (dashed ghost slab = "same as Stage 1", prime = changed clause, `+` = added clause); stadium for a solver; numbered nested chevrons for ordered passes; card stacks for data sets, with the multiplicity in italics under the caption; gem5 = rounded container with the logo and "processor model", a gray "Defense implementation under test" die, and a thin harness ring (`+ Non-invasive harness`); single bold bug icon.
- **Sources of truth:** gray document icons in a left lane under a small italic "Defense sources of truth" header, each with one short arrow into what it feeds; dashed "SimSpect goal" arrow from specification to implementation. No legend box; the caption explains the gray.
- **Graph figures:** lowercase ids `i0:`; kinds in code font; flags as italic words on the row; every edge labelled (rf, ddi); leak path thick; legend in the caption (see "Graph notation" below).
- **Files:** body `<name>.tex` in `{ }`; caption text in `captions/<name>.tex` and `FIGURES.md`; preview `_standalone_<name>.tex` without the caption; `_8pt` versions are what the paper uses; new paper figures are new files plus `\input` swaps, captions pasted with a red TODO.


Every paper figure (the vertical pipeline figure plus minifigs a–e) follows these rules so the paper reads as one system. Anna's direction (2026-11-02): minimal colors, minimal fonts, very professional, use defaults as much as possible, dense without looking cramped or overlapping, items of a list inside one box (not separate boxes).

Reference implementation: the vertical pipeline figure, `/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/15c53160-c914-4164-9142-cacfcd307bbc/scratchpad/fig/_standalone_pipeline.tex` (a draft; will move to `paper_figures/drafts/`).

## Page geometry (measured, not assumed)

The paper (`test-paper`, `\documentclass[conference]{IEEEtran}`) has `\columnwidth` = 252pt (3.5in), `\textwidth` = 516pt, `\textheight` = 672pt (measured by compiling the repo's `IEEEtran.cls` and printing the lengths). ISCA 2026's rules agree: US Letter, 0.625in side margins, 0.25in column gap, so (8.5 − 1.25 − 0.25)/2 = 3.5in columns; body 10pt Times, captions 8pt; the template is IEEEtran (iscaconf.org/isca2026/submit/guidelines.php, "Paper Formatting"). One-column figures take the **full** 252pt (Anna, 2026-11-02); never scale a figure with `\resizebox` (it shrinks the text unevenly).

## Fonts

- Never set a font family inside the `tikzpicture`, so an `\input` inherits the paper's Times. Standalone previews use `\usepackage{newtxtext,newtxmath}` only to look like the paper.
- **One size everywhere: `\scriptsize` (7pt)**, per Anna 2026-11-02 ("smallest font allowed all around"). Multiplicities, annotations and explanations are the same size in italics. ISCA 2026 states no minimum for figure text, only "Ensure that the figures and tables are legible" (iscaconf.org/isca2026/submit/guidelines.php, "Figures and Tables"); captions are 8pt. 7pt is our floor; nothing smaller except glyphs inside icons.
- Bold only for panel or stage labels (e.g. "**Stage 1:**"). No small caps, no typewriter except for literal code or assembly.
- Turn off hyphenation inside nodes (`execute at begin node={\hyphenpenalty=10000\exhyphenpenalty=10000}`).

## Color

- Black on white. One gray fill, `black!12`, means **defense-specific** (the defense-specific clause, the gem5 defense build, defense sources of truth). Do not use gray for anything else.
- No other colors, except where Anna explicitly asked for one (figure b: redundant components in red). If red is needed, use one muted red for the whole paper and say so.

## Defense-specific sources of truth

- A defense-specific source of truth (defense specification, defense transmission mechanisms, the defense's gem5 code) is a small gray document icon (`\docicon`, fill `black!12`) with a 7pt label to its right, placed **inside** the frame right next to the element it feeds, with one short arrow. No separate left-hand column (it wasted space).
- The element it feeds, if itself defense-specific, is a gray-filled row. A one-line legend ("■ defense-specific") sits top right of the figure; nothing more.

## Tools

- Tools are rounded boxes (`rounded corners=3pt`): Alloy Analyzer, and gem5. gem5 is a rounded container with the official black-and-white gem5 logo (`gem5logo.pdf`, cropped from `gem5bwLong.pdf` in github.com/gem5/website `assets/img/gem5logo/Black+White/noBackground/horizontal/`, CC0) holding the defense build and the harness, so the harness reads as part of gem5. Requires `\usepackage{graphicx}` in the paper (IEEEtran papers normally load it).

## Shapes and lines

- TikZ default line width (0.4pt), sharp corners for boxes and frames. Tool boxes (e.g. Alloy Analyzer) use `rounded corners=3pt`; nothing else is rounded.
- Arrows: `>=latex` with `->`. No shadows, gradients, or font-based icon glyphs; small icons are drawn in TikZ in black and white (document, stack of graph cards, magnifier).
- A list goes in **one** box with numbered rows (`1.~…`); a shaded row marks a defense-specific item. No separate box per item.
- Outputs passed between stages use the same treatment everywhere: an arrow, a small drawn icon, then a caption in 8pt with its multiplicity on the next line in 7pt italics.

## Graph notation (execution graphs in (b), (c), and the (a) vocab table; 2026-11-02)

- **Rows, not boxes.** One text row per instruction in program order (spo), top to bottom, as in LCM/Clou Fig. 1–2 (`reference_papers/crops/lcm_clou_isca22_p4.png`, `_p5.png`): lowercase id `i0:` (roman), kind in code font as in the model (`Load`, `Store`, `Branch_n`, `Branch_x`, `Other_n`, `Other_x`), then operands `out ← in` with registers $r_k$, memory $m_k$, `[r]` for an address and `?` for an unspecified operand. Injected Stage 2 chain steps use ids `c0:` and free-pool registers $f_k$.
- **Flags are short italic words on the row** (*resolved*, *committed*, *xmit*), written only when set; *committed* implies resolved, so it is written alone; a row without a word is unresolved and uncommitted. Why words and not subscripts: LCM's subscript S works for one flag, but we have three, and three letter subscripts are the r/c/t code Anna found "entirely unclear"; at an 8pt base a subscript prints at 6pt, under our 7pt floor; CheckMate already writes flags as words on the instruction text (`B PNT, T`, see `TRIPPEL_FIGURE_STYLE.md` CheckMate (b)); and table (d) already uses flag words.
- **Every edge is labelled** in 7pt italics, *rf* or *ddi*, as in TransForm and LCM. ddi is an arc above the row (input → output); rf runs from an output to a later row's input, through empty space or a gutter right of the operands. No edge crosses text.
- **The leak path is thick** (1.1pt, `latex` tips), not colored: LCM marks its leak edges with a line style (dashed), and we keep dashed for the one Stage 2 edge that may or may not form (the free-pool merge in (c)).
- **Gray** (`black!12` behind the token) only for defense-specific state, i.e. protected memory in STT's protection set. **Red** (`#B3322C`, = the preamble's `ctarget`) only in (b), for the parts minimization removes; explanations stay black.
- **Legend in the caption, not a key box** (TransForm, CheckMate, LCM all do this). The (a) vocab table is the full key; each graph caption repeats the minimum needed to read it alone.
- Body text 8pt (`\footnotesize`), labels/flags/notes 7pt italic (`\scriptsize\itshape`). Each picture pads itself (empty `\path` above and below) so nothing touches the frame.

## Captions and file layout (Anna, 2026-11-02)

- Every figure has a proposed caption, written in `paper_figures/FIGURES.md` (Captions section) and in `captions/<name>.tex`. Previews do NOT render the caption (Anna, 2026-11-02: the minipage wrapper misaligned the figure); they leave blank space where it will go (standalone `border` padding). In the paper the caption goes separately into `\caption{}` (paper text; Anna pastes it).
- Three files per figure in `paper_figures/drafts/`: `<name>.tex` = the body only (the `tikzpicture` plus its local definitions, wrapped in `{ }` so nothing leaks into other figures; this is what goes into the paper's `tikz/`); `captions/<name>.tex` = the caption text alone; `_standalone_<name>.tex` = the preview: `\documentclass[tikz,border={2pt 24pt 2pt 2pt}]{standalone}` + `\input{<name>}` (tikz mode drops stray whitespace outside the picture).
- Margins: ISCA sets page margins only; nothing about padding inside figures. Anna wants comfortable breathing room inside figures; nothing touching.
- The paper preamble already loads TikZ with `arrows.meta, positioning, calc, bending, fit, backgrounds, shapes.geometric`; TikZ loads graphicx.

## Code conventions

- Each figure ships as `_standalone_<name>.tex` (with `\documentclass[tikz,border=1pt]{standalone}`) plus a `-1.png` preview at 300 dpi, matching the paper repo's `tikz/` convention.
- Put a `TUNING KNOBS` block of `\def`s at the top (widths, gaps, padding) so spacing can be tuned without touching the drawing.
- Avoid TikZ key/macro names that clash with built-ins (`\shade`, `cap`, `def` all broke the reference figure).

## Provenance

Every label, number, pass name and mechanism in a figure must come from the codebase, an md note, or a paper, with the source recorded in that figure's plan file. Anything uncertain goes into the plan's "Decisions for Anna" list instead of into the figure.


## 8pt minimum, including arc labels (Anna, 2026-11-02)

- Every figure has an 8pt-minimum version (`<name>_8pt`), and that is what goes in the paper. **All** text is at least 8pt (`\footnotesize`), explicitly including annotations on arcs and edges (rf, ddi, "selects hooks", "speculation directives", "labels"), multiplicities, qualifiers, glyphs inside icons (draw them as paths, not `\tiny` text), and math sub/superscripts (write `r0`, not `$r_0$`, since subscripts render at about 6pt). Check by grepping each body for `\scriptsize`, `\tiny`, `scale=0`, `_digit` and `^` outside comments, and by confirming every edge-label style resolves to `\footnotesize`. Basis: ISCA states no number ("legible"); ASPLOS 2024 asks for at least 8pt.
