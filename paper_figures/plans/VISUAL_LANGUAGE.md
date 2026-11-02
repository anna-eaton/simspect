# SimSpect paper figures: shared visual language

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
