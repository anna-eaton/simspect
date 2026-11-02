# Minifig (a): execution graph syntax ("graph on instructions")

Plan for minifig (a). It follows [`VISUAL_LANGUAGE.md`](VISUAL_LANGUAGE.md); the reference implementation is `paper_figures/drafts/_standalone_pipeline_vertical.tex` (byte-identical to the scratchpad `_standalone_pipeline.tex` named in VISUAL_LANGUAGE). Written 2026-11-02. No paper text, `.als`, or `parsexml.py` was edited.

**Anna's ask (handwritten note):** one box listing three things: "Instructions: list types", "Annotations: list bools", "Relations: list relations". Margin question: "build this in TikZ w/ code or inline?"

## What exists now

- **No dedicated syntax figure exists.** I checked all 24 files in the paper clone's `tikz/` and every `\input` in `sections/*.tex`. None lists the syntax.
- The syntax is given **in prose** at `sections/pipeline.tex:9` (subsubsection "Execution Syntax", `pipeline.tex:7`): instruction types, operands, State (Reg, Mem), "flags for committed/resolved status", rf/ddi edges. A longer older version is at `sections/oldtechnicaldetails.tex:49`, but that file is not `\input` anywhere, so it is not compiled.
- The closest figures are **example instances**, not syntax: `tikz/alloyviolation.tex` (`fig:ddi-rf`, `\input` at `pipeline.tex:13`), `tikz/relaxation.tex` (`fig:four-panes`, `pipeline.tex:21`), and `tikz/interleave.tex` (`fig:interleave`, `pipeline.tex:33`). All three share one notation: typewriter pseudo-assembly rows (`I1: load reg1 <- [mem 1]`), memory in a small box, `ddi`/`rf` arcs labelled in italics, and a right-hand column of bold `r` / `c` letters. They use `Stealth` tips, `semithick` lines, and (interleave) blue. That breaks the new visual language.
- `tikz/threelayer.tex` is the intro's assurance-levels figure. It is unrelated.

## What changes

- New draft: `paper_figures/drafts/_standalone_execgraphsyntax.tex` + `_standalone_execgraphsyntax-1.png` (300 dpi) + `.pdf`. **Rendered size: 250.4 × 178.9 pt** (one column; `\columnwidth` = 252pt).
- Content: one sharp-cornered box with an italic header and three numbered rows (Instructions / Annotations / Relations, Anna's three items; operands are folded into row 1 because rf and ddi connect operands). Below the box, unframed, is a 3-instruction example graph. It doubles as the **notation key** that the relaxation and concretization figures can reuse, with a 7pt italic reading note beside it.
- Visual-language compliance: no font family set inside the picture; 8pt body, 7pt italics for labels and notes; no bold; no color, and gray is not used because nothing here is defense-specific; 0.4pt lines, sharp corners, `>=latex`; the list sits in one box with numbered rows; hyphenation is off in nodes; a `TUNING KNOBS` block is at the top; all macro and style names carry an `eg` prefix to avoid clashes. One exception: subscripts (Branch\textsubscript{n}, $r_0$) render at 6pt (see Decisions).
- To use it in the paper (Anna does this; paper text is read-only for Claude): copy the code between the `FIGURE BODY` markers into a new `tikz/execgraphsyntax.tex` inside `\begin{figure}[t]\centering … \caption{…}\label{fig:execsyntax}\end{figure}`. Then add `\input{tikz/execgraphsyntax}` after `sections/pipeline.tex:9`. The figure only needs `tikz` + `calc`, both already loaded (`bare_conf_compsoc.tex:332-333`).
- Proposed caption (for Anna to edit/paste): "Execution graph syntax shared by every defense model. An execution is a graph on instructions: typed instruction nodes whose operands name register or memory state, Boolean annotations per instruction, and three relations. Bottom: the graph notation used in all later figures, shown on the leakage backbone of Fig.~\ref{fig:four-panes}(d)."
- Proposed prose trim (for Anna): if the figure goes in, the middle of `pipeline.tex:9` ("typed as transmitters … track information flow to transmitters.") can shrink to one sentence pointing at Fig.~\ref{fig:execsyntax}. That pays back roughly 4 lines of text.

## Syntax inventory (shared skeleton)

All line numbers are `STAGE1_alloy/models/STT_6.als` unless noted. **Shared-skeleton check:** I diffed `STT_6.als` against `Recon_6.als` and `SPT_6.als`. Lines 1–138 are byte-identical in all three (every sig, field, Boolean, and relation below). The first differences are a derived function (`first_uncommitted`, SPT `:139`) and the `rf_from_most_recent_writer` fact (STT_6 `:161-169`, absent from Recon_6/SPT_6; see Decisions). `SPT_6_oneLP`, `STT_6_stl`, and `STT_6_futuristic` match in the syntax region apart from header comments. `STT_6_stl` and `STT_6_futuristic` change what `isresolved` means, not its syntax. `STT_6_commitsplit` adds a variant-only `uBool`.

### Instructions (nodes)

Each instruction has `kind: one InstrType` (`:47`); the kind sets are `:71-76`.

| Type | Alloy atom | Line | Allowed operands (inputs → output) | ddi allowed | Meaning (source) |
|---|---|---|---|---|---|
| Load | `TLoad` | `:30` | inaddr, inmem → outreg (`ld_ops :117`) | inmem → outreg only (`:171`) | "load from memory" (`:30` comment) |
| Store | `TStore` | `:31` | inreg, inaddr → outmem (`str_ops :118`) | inreg → outmem only (`:172`) | "store to memory" (`:31`) |
| Branch\_n | `TBranchn` | `:32` | inreg only (`br_ops :120`); may have no operands (`no_extra_inst :313`) | none (`:174`) | "ctrl/br op, doesnt xmit" (`:32`) |
| Branch\_x | `TBranchx` | `:33` | inreg only (`:120`) | none (`:174`) | "ctrl/br op, xmits" (`:33`) |
| Other\_n | `TOthern` | `:34` | ≤2 inreg → outreg (`other_ops :119`, `:122`) | inreg → outreg (`:173`) | "ALU/reg->reg, doesnt xmit" (`:34`) |
| Other\_x | `TOtherx` | `:35` | ≤2 inreg → outreg (`:119`, `:122`) | inreg → outreg (`:173`) | "ALU/reg->reg, xmits" (`:35`) |

"x = potential transmitter" follows the `.als` comments and `pipeline.tex:9`. Whether an operand actually transmits is decided by each defense's `leakage_function` (STT_6 `:328`, Recon_6 `:320`, SPT_6 `:331`: `Loads.inaddr + Branchxs.inreg`; SPT_6_oneLP `:344` adds `Stores.inaddr`).

### Operands and state (what nodes carry; edges attach here)

| Element | Line | Meaning (source) |
|---|---|---|
| Operand kinds inreg, inaddr, inmem (inputs); outreg, outmem (outputs) | sigs `:85-89`; Instruction fields `:53-57`; `ins`/`outs` `:91-92` | an instruction's input/output slots; inaddr is "only relevant for loads and stores" (`:54`) |
| `opstate: one State` | `:80` | every operand names exactly one state element; inreg/inaddr/outreg name `Reg_s`, inmem/outmem name `Mem_s` (`:110-114`) |
| `State` = `Reg_s`, `Mem_s` | `:24-26` | abstract register / memory locations; every State is used by some operand (`:101`) |
| one owner per operand | `:107` | each operand belongs to exactly one instruction |
| cardinality | `:122-126` | ≤2 inreg, ≤1 inaddr, ≤1 inmem, ≤2 inputs, ≤1 output per instruction |
| unspecified operands | (sets, `:53-57`) | instructions have "some or all" operands specified (`oldtechnicaldetails.tex:49`); the figure shows an unspecified output as `?` (paper convention, `relaxation.tex:129`) |

### Annotations (per-instruction Booleans)

| Flag (figure) | Alloy | Line | Constraints | Meaning (source) |
|---|---|---|---|---|
| resolved $r$ | `isresolved: lone rBool`; `fun resolved` | `:19`, `:60`, `:67` | committed ⊆ resolved (`:134`, `:211`) | "a branch knows its target and condition and a memory instruction knows its address" (`oldtechnicaldetails.tex:49`). In STT_6/Recon_6/SPT_6 only unresolved **branches** open speculation (`speculation_contract_p :325`, `has_unresolved_brs_p :245-247`). STT_6_stl: store address known (`wiki/design/STL_SPECULATION.md:53`). STT_6_futuristic: "completed: can no longer squash younger instructions" (`wiki/design/FUTURISTIC_MODEL.md:36`) |
| committed $c$ | `iscommitted: lone cBool`; `fun committed` | `:20`, `:61`, `:66` | implies resolved; committed instructions are a contiguous prefix of spo (`committed_last :137`); boundary helpers `:138-139` | "has left the ROB, and is non-speculative" (`oldtechnicaldetails.tex:49`) |
| target transmitter $t$ | `isxm: lone tBool`; `fun xm` | `:21`, `:62`, `:68` | exactly one (`one_xm :269`); must hold a speculative leaked operand reachable from the protection set (`tag_xm :270-273`) | "transmitter - if flagged this is the bad spec transmitter" (`:21`); `parsexml.py:2609-2618` copies it into the annotation's `xmit`, which selects the checker |

The figure's letters r / c / t mirror the Alloy sig names `rBool` / `cBool` / `tBool` (`:19-21`).

### Relations (edges)

| Relation | Alloy | Line | Constraints | Meaning (source) |
|---|---|---|---|---|
| spo | `spo: lone Instruction` | `:50` | acyclic `:129`, ≤1 predecessor `:130`, total `:131` → one chain | "speculative program order", "a total order on the Instructions" (`oldtechnicaldetails.tex:49`); "program order" (`wiki/design/MODELS_AND_BUILDS.md:19`) |
| rf | `Operand.rf: set Operand` | `:81` | output → input (`:156`); ≤1 rf into an operand (`:157`); forward in spo, never inside one instruction (`:158`); same state (`:159`); STT_6 lineage only: from the most recent writer (`:161-169`) | "reads-from relationships between output and input operands of different instructions" (`oldtechnicaldetails.tex:49`); "reaching-definition" (`wiki/design/METHODS_LEAKAGE_KNOBS.md:44`) |
| ddi | `Operand.ddi: set Operand` | `:82` | input → output of the same instruction (`constrainddi :155`); per-type restrictions `:171-174` | "data-dependence-internal relationships between input and output operands of the same instruction" (`oldtechnicaldetails.tex:49`); the `.als` header calls them "GL-IFT-ish ddi edges" (`:153`); `METHODS_LEAKAGE_KNOBS.md:44` expands ddi as "direct-data-influence" (conflict, see Decisions) |

### Deliberately left out of the figure

- `kind` as a field rather than subsigs (`:5-9`, `:47`), plus `idx` and `IX0…IX5` (`:38-43`, `:48`, `:280-295`): symmetry-breaking implementation detail, not syntax.
- `PTag` / RO, RC, RR, RI, RS (`:190-198`) and the `_p` perturbed functions: the relaxation machinery, which belongs to the relaxation figure.
- Well-formedness facts (`:98-174`) beyond the one-phrase constraints above, and the defense block (`:320-332`).
- `uBool` / `isuncommitted` (`STT_6_commitsplit.als` only).

## Graph-notation proposal (for reuse by the relaxation and concretization figures)

- **Node = one instruction.** A sharp-cornered 0.4pt box of fixed width, containing the type in roman (Load, Store, Branch\textsubscript{n}/\textsubscript{x}, Other\textsubscript{n}/\textsubscript{x}) followed by its operands in the paper's existing assignment form `out ← in`: state elements as math-italic $r_i$ (Reg) and $m_i$ (Mem), the address operand in brackets `[r_i]`, an unspecified output as `?`, and unspecified inputs omitted. The instruction ID (I0, I1, …) sits left of the box in 7pt italics.
- **spo = row order, top to bottom.** One arrow on the far left labelled *spo*. There are no per-pair spo edges: spo is total (`:131`), so the order already says everything.
- **rf = solid arrow** (0.4pt, `latex` tip) from the producing output token to the consuming input token in a later row.
- **ddi = densely dashed arrow**, a short arc above the tokens inside one box, input → output.
- **Annotations = three dot columns** right of the boxes, headed *r c t* in 7pt italics, with a filled 2.4pt dot when the flag is set. Reading down *c* shows the commit prefix; blanks in *r* are the unresolved instructions.
- Edge labels (*rf*, *ddi*) appear only in this key figure. Later figures may drop them because the line style carries the meaning.
- Code reuse: copy the `eg*` styles (`egtok`, `egrf`, `egddi`, `egflag`, `eglab`) and the knobs `\egnodex`, `\egboxw`, `\egrowh`, `\egboxup`, `\egboxdn`, `\egflagx`, `\egflagdx` from the draft.
- Suggested reuse in the **relaxation figure** (suggestion only; that figure's owner decides): each relaxation becomes one visible edit on this notation. RI removes a box, RO removes a token, RS removes a state name everywhere, RR fills an *r* dot, RC fills a *c* dot. The changed element could be drawn dotted. The five relaxations are listed at `pipeline.tex:22-29` and defined at `STT_6.als:190-198`.
- Suggested reuse in the **concretization figure** (suggestion only): the abstract graph on the left in this notation, and the same rows on the right in typewriter x86. The rf arrows line up with the shared physical register; the *r* column feeds the speculation directives (stage 2 pass "Concretize speculation primitives" in the pipeline figure).
- Gray stays reserved for defense-specific items. If a later graph needs to mark protected state or the leaked operand (both defense-specific), a `black!12` token background is the in-language way to do it.

## Example graph: provenance and check

- Source: the paper's own backbone, `tikz/relaxation.tex` pane (d). Its caption (`relaxation.tex:160`) reads "branch\_n; load reg0 ← mem 0; load ? ← [reg0] … with the branch unresolved and nothing committed", and its `r` labels on I1 and I2 are at `relaxation.tex:138-140`. Renamed reg0 → $r_0$ and mem 0 → $m_0$. The *t* dot on I2 follows from `tag_xm` (`:270-273`): I2's inaddr is the only leakage-function operand.
- Checked against STT_6's predicates by hand: I1 and I2 are uncommitted and follow the unresolved branch, so they are speculative (`:325`). $m_0$ is protected (`:326`) and stays protected because I1 has an unresolved branch before it (`:331`). $m_0$ reaches I2.inaddr via ddi (I1) then rf, and I2.inaddr is in the leakage function (`:328`), so the graph is not secure (`:262-265`). Minimality: resolving or committing I0 (the first uncommitted instruction, `:139`) secures it (`:308`); no other instruction is unresolved (`:306`); removing $m_0$ or $r_0$ secures it (`:310`).
- Caveat: STT_6 enumerates **exactly 6** instructions (`:317`), so this 3-instruction graph is the paper's illustration, not a literal STT_6 output.

## TikZ or inline?

| Option | Height in column | Pros | Cons |
|---|---|---|---|
| (i) TikZ figure (the draft) | 179pt (~27% of a 672pt column) | matches the minifig language; the example doubles as the notation key, so the ddi-rf, relaxation, interleave, and concretization figures need no per-figure legend; floats freely | the list repeats `pipeline.tex:9` unless that prose is trimmed |
| (ii) Inline table in the text (tested: fits 252pt, no overfull, snippet below) | ~80pt (8 lines at 8pt), no float, no figure number | cheapest; can *replace* the prose at `pipeline.tex:9` instead of duplicating it | no graph and no notation key; does not look like the other minifigs |
| (iii) Alloy code listing (one reading of "TikZ w/ code") | ~200pt for the sig block `:19-89` in 7pt typewriter | exact, and shows the model is small | Alloy syntax is unfamiliar to S&P readers; it must be cut (kind/idx/IX), so it is not verbatim anyway; the largest of the three |

**Recommendation (Claude's, for Anna to decide):** choose (i), the TikZ figure *with* the example graph, and trim the prose at `pipeline.tex:9` to one sentence. The example is what earns the float: it defines the graph notation once for every later graph figure. Without the example, (ii) is better. A list alone does not justify a float in a dense paper, and the inline table costs less than half the height. If page budget gets tight later, fall back to (ii) and move the notation key into the first example figure (`fig:ddi-rf`).

Inline snippet for option (ii), tested in the paper's `IEEEtran` at `\columnwidth` = 252pt (`array` is loaded at `bare_conf_compsoc.tex:336`):

```latex
\smallskip
\noindent{\footnotesize\begin{tabular}{@{}l@{\hspace{4pt}}>{\raggedright\arraybackslash}p{\dimexpr\columnwidth-1.75cm\relax}@{}}
\textit{Instructions} & Load, Store, Branch\textsubscript{x}, Other\textsubscript{x} (potential transmitters); Branch\textsubscript{n}, Other\textsubscript{n} (non-transmitters). Operands inreg, inaddr, inmem, outreg, outmem each name a Reg or Mem state element.\\[1pt]
\textit{Annotations} & resolved; committed (implies resolved; committed instructions form a prefix of spo); target transmitter (exactly one).\\[1pt]
\textit{Relations} & spo, total program order; rf, reads-from, output to input operand of a later instruction on the same state; ddi, input to output operand within one instruction.\\
\end{tabular}}
\smallskip
```

## Decisions for Anna

- [ ] **DECIDE: TikZ or inline?** Options (i) TikZ with example, (ii) inline table, (iii) Alloy listing. Recommendation: (i) with the `pipeline.tex:9` prose trimmed; (ii) if the example graph is dropped.
- [ ] **DECIDE: adopt this graph notation for all graph figures?** Boxes, left spo axis, r/c/t dot columns, solid rf / dashed ddi. That would restyle `fig:ddi-rf`, `fig:four-panes`, and `fig:interleave`, which currently use typewriter rows, bold `r c` letters, `Stealth` tips, and blue. Alternative: keep their row notation and only restyle lines and fonts.
- [ ] **DECIDE: example source.** Keep the paper's 3-instruction backbone (`relaxation.tex` pane d, valid under STT_6's predicates but not a literal output, since scope is exactly 6), or switch to a real enumerated 6-instruction instance (about 2× taller)?
- [ ] **DECIDE: show the transmitter flag $t$?** It is a Boolean in the syntax (`:21`, `:62`) and drives checker selection, but it is a labelling flag rather than μarch state. `pipeline.tex:9` mentions only committed/resolved. Recommendation: show it, as drafted.
- [ ] **DECIDE: what "resolved" means in the paper.** The figure prints only the name. Its meaning differs by model: branch outcome (STT_6/Recon_6/SPT_6), store address (STT_6_stl), "completed" (STT_6_futuristic). Should the prose use the generic `oldtechnicaldetails.tex:49` definition ("a branch knows its target and condition and a memory instruction knows its address") or a per-model one?
- [ ] **DECIDE: what ddi stands for.** "data-dependence-internal" (`oldtechnicaldetails.tex:49`) or "direct-data-influence" (`wiki/design/METHODS_LEAKAGE_KNOBS.md:44`). The `.als` only says "GL-IFT-ish" (`:153`). The figure avoids expanding it.
- [ ] **DECIDE: "graph on instructions" wording.** rf and ddi are operand → operand edges (`:81-82`); only spo is instruction → instruction (`:50`). The header "a graph on instructions" is a simplification. Keep it, or say "a graph on instructions and their operands"?
- [ ] **DECIDE: keep Other\_x?** It is in the syntax (`:35`), but no current model's `leakage_function` includes `Otherxs.inreg` (commented out at `STT_6.als:327`). Calling it a "potential transmitter" is accurate to the syntax, yet no test ever uses it as one.
- [ ] **DECIDE (minor): type naming and the 7pt floor.** The draft uses Branch\textsubscript{n} (subscript). The paper uses "Branchn" (`pipeline.tex:9`) and typewriter `branch\_n` (existing figures). Subscripts render at 6pt, below VISUAL_LANGUAGE's 7pt floor. Accept that as standard math typography, or write Branch-n / $r0$?
- [ ] **DECIDE: skeleton drift (model semantics, no `.als` touched).** `rf_from_most_recent_writer` (`STT_6.als:161-169`) is in STT_6 / stl / futuristic / commitsplit / core / multisource but **not** in Recon_6, SPT_6, or SPT_6_oneLP. Meanwhile `specs/alloy_models.json:43,58,63` and `STAGE1_alloy/models/MANIFEST.md` claim Recon_6, STT_6_pincommit, and STT_6_modified_protset carry it, and on disk they do not. This contradicts "everything except the defense block is duplicated verbatim" (CLAUDE.md). It does not change the figure, since it is an axiom rather than syntax, but it affects any paper claim that all models share one skeleton.

## Side findings (not part of this figure)

- Broken reference in the paper: `sections/pipeline.tex:20` cites `Figure~\ref{fig:relaxation}`, but `tikz/relaxation.tex:161` labels the figure `fig:four-panes`, so the PDF shows "Figure ??". Anna fixes this; paper text is read-only for Claude.
