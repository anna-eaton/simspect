# Big pipeline figure: shape vocabulary and three directions

*Written 2026-11-02 by a design-consultant agent. Mocks: `paper_figures/drafts/design_mocks/mock_{A,B,C}.tex` + `-1.png` (300 dpi), shared macros in `mock_macros.tex`. The main figure (`paper_figures/drafts/pipeline_vertical.tex`, being edited by another session) was read but not touched; the mocks use its wording as of 01:27 (Stage 2 "(Python, LLVM)", "one pair per branch mode × interleave variant", "parallelizable SAT solving", the SimSpect-goal line). Follows [`VISUAL_LANGUAGE.md`](VISUAL_LANGUAGE.md) except where Anna's newer feedback overrides it (see D6).*

## The diagnosis in one paragraph

In the current figure every component is the same shape: a rectangle holding a numbered text list, next to a smaller rectangle. A constraint set, a compiler pass list, a simulator and a harness all look alike, so the only way to tell them apart is to read them, and that is what "walls of text" means. The fix is a fixed **shape vocabulary**: each component *type* gets one shape that says what kind of thing it is, gray says "defense-specific", and text is cut down to the component's name. Once the shape carries the type, words like "Constraints on execution graphs:", "Concretization passes, per graph:", "Defense-agnostic" and "Same as Stage 1" can go.

## Three rules

1. **Shape = type.** One shape per kind of thing, used everywhere it occurs (both Alloy runs use the same stadium, so the reader sees "same tool" without being told).
2. **Gray = defense-specific, and only that.** Because gray already says it, the words "defense-specific" / "defense-agnostic" come out of every label.
3. **Text = the name only.** Qualifiers (multiplicity, mode, arrow labels) are one 7 pt italic line; explanations go to the caption.

## Shape vocabulary

| Component type | Shape and treatment | Why the shape carries meaning |
|---|---|---|
| Stage container | Rounded blob (7 pt radius, 0.6 pt line). The title sits **on** the top border (bold "Stage n", roman name, italic tool). Blobs span only the process lane, with gaps between them where the data travels. | A blob is a unit you can point at. Because blobs stop at the left lane and are separated by gaps, they no longer read as rules across the figure. A title on the border costs no row. |
| Constraint set (clauses that all hold at once) | Stacked rounded slabs gathered by a collector bar (A), or pills joined by ∧ with a brace (B), feeding the solver with one arrow. A changed clause gets a prime (2′). An unchanged clause is a **dashed ghost** slab ("as Stage 1"). C uses a clause *matrix* instead (rows = clauses, columns = Stage 1 / 1.5). | Stacking with no arrows between items says "unordered, simultaneous", which sets constraints apart from passes (ordered). The ghost shows "same as before" without repeating it, and the matrix shows the 1-versus-1.5 delta in one glance. |
| Solver / engine | Stadium (fully rounded ends), 0.6 pt line, with the tool name and at most one sub-line ("Kodkod + SAT" or *non-exhaustive*). | It is the only pill-ended shape in the figure, so it reads as "the thing that runs". Using the same shape twice says "same tool". |
| Ordered compiler passes | Chevrons (arrow-shaped boxes): a two-row snake with labels inside (A), metro stations on the data spine (B), or one horizontal timeline with labels alternating above and below (C). Numbers stay, for references from the text. | An arrow shape is ordered and directional by itself, so "1 then 2 then 3" needs no words. |
| Data set passed between stages | A card stack with a glyph on the front card: the execution-graph glyph (three nodes in program order plus one rf arc, matching minifig a), program text lines, `{ }` for annotations; a program + annotation **pair** is two half-cards clipped together. Multiplicity: the stack is visibly plural, plus one italic line; B also deepens the stack (3, 4, 5 cards) as the counts grow. | A stack reads as "many" before any words are read, which is what Anna asked of the outputs. The glyph says which data it is. |
| Simulator (gem5) | Rounded container carrying the official gem5 logo instead of a text title; it holds the defense build as a gray **die**. | Containment says the build runs inside gem5, and the logo names the tool without a word. |
| Harness | A thin ring around the die with probe ticks that touch the die (A, B), or pins on a chip package (C). Directives arrive at the ring; the trace leaves from it. | The harness wraps the build and observes it but is not part of it, so "non-invasive" becomes visible. See D4 about how literal the pin version is. |
| Artifact (pipeline info) | A single card with staggered bars (an O3PipeView-like trace glyph). | One card per run; the bars hint at pipeline stages. |
| Inspection program | A rounded box with a magnifier glyph. | The magnifier is the most common sign for "inspect" and needs no label beyond the name. |
| Finding (Bug?) | A black badge with a white bug and white "Bug?" (A); a starburst around the bug (B); or the bug under a magnifier lens (C). | It is the end point of the figure, so it should be the highest-contrast element; in A it is the only black-filled shape. |
| Defense-specific sources of truth | Gray folded documents in a left lane, label underneath, one short horizontal arrow into the exact element they feed (clause 3, the die, the harness + inspection). The legend sits at the top of the lane: swatch + *defense-specific sources of truth*. The dashed SimSpect-goal arrow (specification → implementation) runs down the otherwise empty part of the lane. | One column, one treatment, one legend: "unified and not over the top". The goal line turns the lane's empty middle into content. |
| Arrows | Solid `->` for data; a junction dot where a line splits; arrow labels in 7 pt italic next to the line. | Same as the minifigs. |

## Cutting text without losing content

- **Gray replaces words.** Removing "Defense-agnostic" (×2) and "Defense-specific" from the clauses is the largest single saving.
- **Shapes replace headers.** "Constraints on execution graphs:" and "Concretization passes, per graph:" go; the slab stack and the chevrons say it.
- **Tool names live in the tool shape.** The gem5 logo replaces "gem5" text; B also drops "(Alloy)" and "(gem5)" from titles, since the stadium and logo name them.
- **Ghosts replace "Same as Stage 1".** A dashed slab with just its number.
- **Glyphs replace multiplicity sentences.** Card stacks (and stack depth in B) plus one italic line.
- **Glyph reuse replaces long wires.** B redraws the `{ }` card next to the inspection program ("labels") instead of running a wire around gem5. This is a legitimate technique only if the redrawn card is clearly the same artifact; Anna may prefer the wire.
- **Pass labels shrink to 2–4 words** ("pick instructions", "speculation primitives", "interleave chains"); the full pass names go to the caption or text.
- **Into the caption:** "only load-bearing components specified" (clause 2), "manual translation to DSL" (specification), "timing from run config" (harness), the full Stage-2 pass names, and the annotation contents (labels, speculation directives), which the figure shows as two arrow labels.
- **Label hierarchy (two sizes only):** L1 stage title, 8 pt, bold "Stage n" + roman name + italic tool, on the border. L2 component names, 8 pt roman (7 pt inside small shapes such as chevrons and the die). L3 qualifiers, 7 pt italic: multiplicity, mode, arrow labels, "as Stage 1". Bold only for "Stage n" and the item numbers.

Measured (words from `pdftotext | wc -w`, which also counts the lane labels and the goal line; sizes from `pdfinfo`, in TeX pt):

| | Current (latest, `_standalone_pipeline_vertical.pdf`) | Current (8 pt, `old/…nogutter_8pt`) | A | B | C |
|---|---|---|---|---|---|
| Size | 252 × ~506 | 252 × 408 | 252 × 375 | 252 × 415 | 252 × 345 |
| Height / width | 2.0 | 1.62 | 1.49 | 1.65 | 1.37 |
| Share of the 672 pt column | 75% | 61% | 56% | 62% | 51% |
| Words | 214 | 194 | 145 | 144 | 130 |

(The latest current figure's page is 256 × 532 pt including 2 pt borders and a 24 pt caption pad; ~506 pt is the drawing.)

## Direction A: shape-coded blobs (`mock_A`)

One rounded blob per stage, a left lane of sources, and data stacks on a left-hand spine with a Z reading order (each stage flows left to right, then its output steps down and back to the left, like lines of text). Stage 1.5 is drawn as a *delta* of Stage 1 (pin slab on top, ghost slabs 1 and 3, primed 2′); Stage 2 is a two-row snake of chevrons (1–4 rightward, 5–7 leftward); gem5 holds a gray die in a harness ring; the finding is a black badge.

- Strengths: it meets every constraint Anna gave at once (distinct rounded blobs, left lane with legend, no horizontal spreading, 1 : 1.49 proportions, every component its own shape), and it stays close to the structure readers already know from the current draft.
- Weaknesses: three "return" elbows (solver → stack at the left) add lines; Stage 1.5 still repeats a four-slab stack; the chevron snake holds seven short labels, which is the densest text left.

## Direction B: one spine (`mock_B`)

Every tool and every data set sits on one vertical spine at the right (solver → graphs → solver → graphs → metro stations 1–7 → pairs → gem5 → trace → inspection → bug), what we specify for each tool sits to its left, and the sources sit in the left lane, so the three columns mean "sources | specification | what runs and what flows". Constraints are pills joined by ∧; stack depth grows with multiplicity; the finding is a starburst at the foot of the spine.

- Strengths: all data flow is one straight vertical line with no elbows; the columns give a real overview ("left = defense inputs, right = the machine"); the "per graph" arrow into the Stage-1.5 solver states the pin semantics directly.
- Weaknesses: the tallest (62% of a column); Stage 2 becomes a right-aligned text list beside the stations, which brings back the wall-of-text look and leaves the left half of that blob empty; captions are right-aligned, which reads less naturally.

## Direction C: merged Alloy, clause matrix, chip (`mock_C`)

Stages 1 and 1.5 share one blob because they share the solver and three of four clauses: a clause matrix shows exactly what changes (minimality strict/loosened, pin –/graph), and the exhaustive Stage-1 graphs loop back in as the pin. Stage 2 is a single chevron timeline with labels alternating above and below; gem5 is a chip package whose pins are the harness; the bug sits under a magnifier lens.

- Strengths: the clearest statement of how 1.5 relates to 1 (no repeated stack, and the feedback loop is drawn); the most compact (51% of a column, 130 words).
- Weaknesses: it no longer shows Stage 1.5 as its own stage, which has to match how the paper text talks about it (D2); the loop and the tiny "1" / "1.5" exit labels take a moment to decode; at 1 : 1.37 it may read as "too short", which Anna said to avoid; the chip-pin harness is more metaphorical than accurate (D4).

## Recommendation (mine, for Anna to decide)

**A as the base.** It is the only direction that satisfies all of Anna's stated constraints together, cuts about a third of the words, and gives each component type its own shape without asking readers to learn a new layout. Two optional borrowings: B's growing stack depth (3, 4, 5 cards) for multiplicity, which costs nothing; and, if Anna finds the A Stage-1.5 stack repetitive, C's clause matrix could replace the two constraint stacks *inside A's two separate blobs* (Stage 1 shows column "1", Stage 1.5 shows column "1.5" with the changed cells) — I have not mocked that hybrid. I would **not** borrow C's chip pins (see D4) or B's metro list (it is a text list again).

Tradeoffs of A: about 30 pt taller than C and one blob more; three elbow wires; seven short pass labels remain readable text, but they are chunked into shapes and short enough to scan.

## Decisions for Anna

- [ ] **D1. Direction:** A, B, C, or a hybrid. *Recommendation:* A, optionally with B's stack depth.
- [ ] **D2. Is Stage 1.5 its own stage in the figure?** (a) Separate blob, drawn as a delta of Stage 1 (A, B). (b) Merged with Stage 1 in one blob with a clause matrix and a feedback loop (C). This is a framing question, not just layout: it should match whether the paper presents 1.5 as a stage or as a second mode of Stage 1. *Recommendation:* (a), unless the text treats 1.5 as a mode.
- [ ] **D3. How "exciting" the bug is:** black badge (A, strongest contrast, most professional), starburst (B, most energetic, slightly cartoonish), bug under a lens (C, ties the finding to inspection). *Recommendation:* the black badge.
- [ ] **D4. How literally the harness is drawn.** The hooks are print-only events emitted from *inside* the O3 pipeline and caches ("Print-only: no defense logic, timing, or behavior changed", `wiki/design/SIMSPECT_HOOKS.md`, Status line), while the directives (branch forces, stalls) deliberately steer prediction and timing. C's chip pins suggest observation at the boundary only, which is less accurate; the ring with probe ticks touching the die (A, B) is closer. *Recommendation:* the ring with ticks, and keep "directives" as a separate labeled input.
- [ ] **D5. Wording.** The mocks shorten labels: clauses to "well-formed execution", "minimality", "leakage predicate"; passes to 2–4 words; "Defense's gem5 build" for the implementation source; and they move "only load-bearing components specified", "manual translation to DSL" and "timing from run config" into the caption. The paper text and caption (`paper_figures/drafts/captions/pipeline_vertical.tex`) must match whatever labels survive. A possible caption sentence to append (paper text, so Anna pastes it): "Minimality (clause 2) keeps only load-bearing components. Stage-2 passes: (1) order instructions into PCs and collect state, (2) concretize instructions, (3) concretize speculation primitives (branches, STL), (4) interleave instruction chains, (5) assign registers and memory, reserving registers, (6) SSA and LLVM emission with PC labels, (7) annotations, LLVM to asm, PCs to addresses."
- [ ] **D6. `VISUAL_LANGUAGE.md` is now out of date in four places**, because Anna's newer feedback overrides it: it says sources of truth sit inside the frame with "no separate left-hand column"; "sharp corners … nothing else is rounded"; "one size everywhere: `\scriptsize` (7pt)"; and the legend sits top right. The mocks use a left lane, rounded blobs and slabs, an 8 pt body with 7 pt qualifiers, and the legend at the top of the lane. Once D1 is decided, the language doc (and the minifigs, for consistency of rounding) should be updated; I have not edited it.
- [ ] **D7. Glyph reuse (B only).** Redrawing the `{ }` card next to the inspection program saves a long wire, but some readers may take it for a second artifact. *Recommendation:* use the wire (as in A and C) unless space forces it.

## Building the final from a mock

All mocks set `[x=1pt,y=1pt]`, so every number is in pt; `\useasboundingbox` fixes the width at exactly 252 pt; the knobs (lane centre, blob edges, spine x, slab width) are at the top of each file; shapes and glyphs are macros in `mock_macros.tex` (`\cardstack`, `\pairstack`, `\sot`, `\buggl`, `\magn`, `\gGraph`, `\gAsm`, `\gAnn`, `\gTrace`; styles `blob`, `btitle`, `slab`, `ghost`, `pill`, `tool`, `chev`, `chevL`, `station`, `box`). The macros need `arrows.meta` and `shapes.symbols`/`shapes.misc` in the paper preamble, and B needs `decorations.pathreplacing`. `gem5logo.pdf` is copied next to the mocks. Placeholder wording is marked by the shortened labels above (D5); the structure (components, edges, sources) matches the current figure.

## A_full: A's visual language with all of the main figure's text (added 2026-11-02)

Anna liked A's visual language but wanted the text back, so `paper_figures/drafts/design_mocks/mock_A_full.tex` + `-1.png` carries every word of `pipeline_vertical.tex` as of 01:49 (232 words, the same count as the main figure by `pdftotext | wc -w`). It is 252 × 642 pt, which is 96% of the 672 pt column; the main figure's drawing is about 252 × 546 pt.

What changed from mock A to fit the text: each Alloy stage now flows top-down. The clauses are full-width, one-line slabs, and the solver sits *below* them, so the data spine runs straight down the left with no return elbows. Stage 1.5 stays a delta (ghost slabs 1 and 3, 2′), with "+ 4. Pin" at the top of the stack so the Stage-1 graphs' arrow enters it directly. The seven passes are full-width downward chevrons ("stripes"), one full name per line at 8 pt. In Stage 3, gem5 (logo + "processor model") spans the lane; the gray "Defense implementation under test" die sits in the harness ring, whose full label is set inside the ring. The pipeline info artifact, Inspector and bug sit in a row below gem5, so the transmission-mechanisms line reaches the Inspector and the harness ("selects hooks") without crossing anything.

Small liberties: "+ bound" shares the 7 pt line with "(Kodkod model finder + SAT backend)"; stage titles lose the colon and sit on the blob border, with the language line in italics underneath; there is no gray key, only the "Defense sources of truth" header.

Where the extra ~96 pt comes from: the solver sits below the clauses rather than beside them (about 25 pt per Alloy stage); stripes need about 15.5 pt of pitch against about 10 pt for list rows (about 38 pt); and the artifact/Inspector row sits below gem5 (about 25 pt). Ways to win about 70 pt back if needed: drop the three italic list headers, which the shapes already convey ("per graph" can join the Stage-2 language line); move the two enumeration qualifiers into the strip captions, which already say "Bounded-exhaustive"; make the stripes thinner.
