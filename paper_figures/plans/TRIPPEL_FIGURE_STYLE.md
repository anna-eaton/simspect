# How Caroline Trippel's papers present things visually

Written 2026-11-02 so that SimSpect's ISCA figures can follow the house style of Trippel's papers. Everything below comes from the PDFs downloaded into `paper_figures/reference_papers/<shortname>/` and read this session (rendered pages plus `pdftotext`). **Page numbers are PDF page numbers** ("p.N"). These differ from printed proceedings numbers: for example, RTL2MµPATH p.5 is printed page 511, and CheckMate Top Picks p.6 is journal page 89. Companion docs: [`VISUAL_LANGUAGE.md`](VISUAL_LANGUAGE.md) (SimSpect's own rules) and [`fig_a_execgraphsyntax.md`](fig_a_execgraphsyntax.md). No paper text, `.als`, or pipeline code was touched.

## Papers found

All PDFs are official open copies, from Trippel's Stanford page (`cs.stanford.edu/people/trippel/pubs/`, linked from `trippel-lab.stanford.edu/publications.html`) or arXiv.

| Short name (dir) | Paper | Venue | Trippel's role | Source URL |
|---|---|---|---|---|
| `tricheck_asplos17` | TriCheck: Memory Model Verification at the Trisection of Software, Hardware, and ISA | ASPLOS 2017 | first author | https://cs.stanford.edu/people/trippel/pubs/ctrippel_ASPLOS17.pdf |
| `tricheck_toppicks18` | Full-Stack Memory Model Verification with TriCheck | IEEE Micro 38(3) Top Picks, 2018 | first author | https://cs.stanford.edu/people/trippel/pubs/ctrippel_IEEETopPicks18.pdf |
| `checkmate_micro18` | CheckMate: Automated Synthesis of Hardware Exploits and Security Litmus Tests | MICRO 2018 | first author | https://cs.stanford.edu/people/trippel/pubs/ctrippel_MICRO51.pdf |
| `checkmate_toppicks19` | Security Verification via Automatic Hardware-Aware Exploit Synthesis: The CheckMate Approach | IEEE Micro 39(3) Top Picks, 2019 | first author | https://cs.stanford.edu/people/trippel/pubs/ctrippel_IEEETopPicks19.pdf |
| `spectreprime_arxiv18` | MeltdownPrime and SpectrePrime: Automatically-Synthesized Attacks Exploiting Invalidation-Based Coherence Protocols | arXiv:1802.03802, 2018 | first author | https://arxiv.org/pdf/1802.03802 |
| `transform_isca20` | TransForm: Formally Specifying Transistency Models and Synthesizing Enhanced Litmus Tests | ISCA 2020 | co-first author ("The first two authors contributed equally", p.1) | https://cs.stanford.edu/people/trippel/pubs/trippel_ISCA20.pdf |
| `rtl2uspec_micro21` | Synthesizing Formal Models of Hardware from RTL for Efficient Verification of Memory Model Implementations (rtl2µspec) | MICRO 2021 | senior author | https://cs.stanford.edu/people/trippel/pubs/hsiao_MICRO21.pdf |
| `lcm_clou_isca22` | Axiomatic Hardware-Software Contracts for Security (LCMs + Clou) | ISCA 2022 | senior author | https://cs.stanford.edu/people/trippel/pubs/nmosier_ISCA22.pdf |
| `rtl2mupath_synthlc_micro24` | RTL2MµPATH: Multi-µPATH Synthesis with Applications to Hardware Security Verification (introduces **SynthLC**) | MICRO 2024 | senior author | https://cs.stanford.edu/people/trippel/pubs/hsiao_MICRO24.pdf |
| `serberus_sp24` | Serberus: Protecting Cryptographic Code from Spectres at Compile-Time | IEEE S&P 2024 | senior author | https://cs.stanford.edu/people/trippel/pubs/mosier_SP24.pdf |
| `protean_hpca26` | Protean: A Programmable Spectre Defense | HPCA 2026 | senior author | https://cs.stanford.edu/people/trippel/pubs/mosier_HPCA26.pdf |
| `counterpoint_asplos26` | CounterPoint: Using Hardware Event Counters to Refute and Refine Microarchitectural Assumptions | ASPLOS 2026 (Best Paper) | senior author | https://cs.stanford.edu/people/trippel/pubs/lindsay_ASPLOS26.pdf |
| `helium_isca26` | Helium: Quantifying Microarchitectural Side-Channel Leakage with Probabilistic Guarantees | ISCA 2026 | senior author | https://cs.stanford.edu/people/trippel/pubs/archer_ISCA26.pdf |

Corrections to the candidate list:

- TriCheck appeared at **ASPLOS 2017**, not 2016 (lab page and the PDF).
- **SynthLC is not a separate paper.** It is the second tool in the RTL2MµPATH MICRO'24 paper: "RTL2MµPATH (top) and SYNTHLC (bottom) synthesize a complete set of formally-verified leakage signatures" (Fig. 6, p.9).
- The CheckMate MICRO'18 PDF title is "Automated Synthesis of Hardware Exploits and Security Litmus Tests". The lab page lists it under a different title, "Automated Exploit Program Generation for Hardware Security Verification".

Not downloaded: the 2019 Princeton thesis (it compiles the first-author papers above); non-security work (nl2spec, ILA-MCM, RecShard, and others); and the 2025 arXiv microcode-misprediction preprint.

**Most relevant to SimSpect**, in order:

1. **LCM/Clou** (ISCA'22). Security execution graphs with a transient flag; its toolkit is built in Alloy.
2. **TransForm** (ISCA'20). An Alloy synthesis engine producing litmus suites, a vocabulary table, and labelled execution graphs.
3. **CheckMate** (MICRO'18). The flagship µhb security figures; Alloy listings.
4. **RTL2MµPATH/SynthLC** (MICRO'24). Flags as super/subscripts; a dense overview.
5. **Helium** (ISCA'26). The same IEEEtran ISCA template Anna's paper uses.

## Per-paper notes

### CheckMate (MICRO'18), Trippel first author: the canonical µhb security figures

- **(a) Syntax / model definitions.**
  - Code listings as subfigures. Fig. 1(b) (p.2) is a µspec-in-Alloy excerpt: `fact InOrder_Fetch {...}`, with gray line numbers 1–10, blue keywords (`fact`, `all disj`), and a sans monospace font (Consolas is embedded).
  - Fig. 3(a) (p.8) is an 11-line listing of the Alloy `sig` declarations (`sig Address`, `abstract sig Event { po: lone Event }`, `sig Node { event, loc, uhb }`).
  - Fig. 3(b) (p.8) sits directly under that listing: a two-column, full-grid table "Alloy Signature | Set Contains All…", e.g. "sig Read extends MemoryEvent | micro-ops that read memory".
  - The prose uses inline typewriter for relation names (`NodeRel`, `Event→Location`, `uhb_intra`, `uhb_inter`; p.7).
  - No BNF or grammar figure.
- **(b) µhb graphs** (Fig. 1(c–e), p.2; Fig. 4, p.9; Fig. 5, p.10).
  - Layout: a grid. Columns are instructions; rows are µarch locations, labelled in small sans at left (Fetch, Execute, ROB, PC, Commit, L1 ViCL Create, L1 ViCL Expire, Complete).
  - Nodes are small unlabeled circles.
  - Each column header has three lines: the instruction ID as process prefix plus uppercase I plus index from 0 (`A.I0`, `A.I1`, `V.I0`; A = attacker, V = victim, p.10 text), then the operation (`R VA2 (PA1:A)`, `CF VA2 (PA1:A)`, `B PNT, T`), then the cache index (`L1: IDX0`).
  - Columns are grouped under "Core 0" / "Core 1" (or "Victim Thread 0 on Core 0", p.2).
  - **Edges carry no labels.** They are black; the synthesis pattern is red.
  - Flags sit on the instruction text, in red. The privileged address `(PA0:V)` is written in red, and a mispredicted branch is the mnemonic `B PNT, T`.
  - Highlighted instructions get a hatched band behind their column: red horizontal hatching for the flush (CF), gray diagonal hatching for the leaking access. The text explains: "The pattern from Fig. 1c that seeded synthesis is highlighted in red nodes and edges and rectangles shaded with horizontal red lines and diagonal gray lines" (p.9).
  - **No legend box.** The caption defines the notation: "B PNT, T represents a branch that is mispredicted as 'not taken.' CF represents a CLFLUSH micro-op." (Fig. 5, p.10).
  - Fig. 1(f) (p.2) shows the same test as a security litmus test: a small table with a header block ("VA to PA Address Mapping: VA0 (PA1:V)"), columns "Victim T0 on C0 | Attacker T0 on C0", rows `(i0) R [VA0] → r1` with **lowercase** `(i0)`, and red side labels "← Flush", "← Reload".
- **(c) Pipeline / timeline.** None separate. The µhb grid is the pipeline view, with stage rows by instruction columns (p.10).
- **(d) Overview** (Fig. 2, p.7). Full width, one row, about 1.6 in tall.
  - Inputs along the top are folded-corner document shapes with a bold "**Input:** µspec Model" lead and a one-line gloss.
  - Five white step boxes sit inside one light-gray container, labelled "CheckMate" vertically at left.
  - **Every box has a dark-gray §-tab** (§V, §IV.A, §III.B.2).
  - Outputs at the bottom are stacked-document shapes ("**Output:** µhb Graphs / Implementation-Relevant Exploit Executions").
  - Grayscale only. Caption: "Inputs are listed across the top with arrows depicting when given inputs are used. Outputs are listed across the bottom…".
- **(e) Tables.** Table I (p.11): one column, full grid (vertical and horizontal rules), bold header, small-caps attack names, about 7 rows. **Caption below the table** ("TABLE I: …", 8 lines, explains methodology).
- **(f) Fonts, colors, captions.**
  - Figures were drawn in PowerPoint/Visio: Calibri, Consolas and Arial are embedded (`pdffonts`). Body text is Times.
  - Black plus **one red accent** (the attack pattern), plus gray hatching.
  - Captions are long and explanatory, and each sub-caption of Fig. 1 is itself 3–5 sentences (p.2).

### CheckMate Top Picks (IEEE Micro 2019)

- Reuses the MICRO figures verbatim. Fig. 1 is on p.3. Figs. 2–3 on p.6 are the Meltdown/Spectre and MeltdownPrime/SpectrePrime µhb graphs.
- Only the caption style changes: magazine house style with a sans, bold "**Figure 2.**" lead. The text is shortened but keeps the notation key ("CF represents a CLFLUSH micro-op. B PNT, T represents a branch that is mispredicted…", p.6).
- So caption typography follows the venue template; figure content is the same.

### MeltdownPrime/SpectrePrime (arXiv 2018)

- Fig. 2 (p.5), the threat patterns, is a small graph of red ViCL circles, a **red dashed rectangle** for the flush event and a black dashed rectangle for the victim access. Labels ("flush", "reload", "prime", "probe") are rotated next to the nodes.
- Figs. 3–4 (pp.5–6) are the µhb graphs in CheckMate style, stacked in one column.
- Captions are a short bold sans sentence ("Threat patterns for Flush+Reload and Prime+Probe timing-based cache side-channel attacks", p.5).

### TriCheck (ASPLOS'17), Trippel first author

- **(a) Syntax.** Fig. 1 (p.1) is a screenshot of a C11 code listing with blue keywords, plus terminal output with a red oval around the key line. Compiler mappings are tables (Table 1 p.4; Tables 2–3 pp.6–7) with typewriter for code (`ld rlx`, `st sc`) and `f[m,m]` notation defined in the caption.
- **(b) Litmus tests** (Figs. 3–4 p.3; Figs. 8–9 p.8; Figs. 11–14 pp.10–11) are boxed tables:
  - a header row "**Initial conditions**: x=0, y=0";
  - one column per thread (T0, T1, T2);
  - instructions labelled with **lowercase letters** (`a: st(x,1,rlx)`, `b: r0 = ld(x, rlx)`);
  - a bottom row "**Forbidden C11 Outcome**: r0=1, r1=1, r2=0".

  They are captioned as Figures, not Tables.
- **(d) Overview** (Fig. 6, p.6). One column.
  - HLL and ISA litmus suites are stacked-document icons (white). Models and mappings are **gray-filled** boxes.
  - Black circled step numbers ①–④. A 2×2 "Compare Outcomes" grid uses red "Bug" and green-hatched "OK".
  - Big curly-brace loop arrows carry the label "Fix one or more models".
  - Caption: one title sentence, then 3 sentences of explanation ("Numbers correspond to TriCheck steps enumerated in Section 3.2").
- **(e) Tables.**
  - Fig. 7 (p.8) is a checkmark matrix: µSpec models by relaxed features, with grouped column headers (Relaxed PO | Store Atomicity). It is full grid and also captioned as a Figure.
  - Table 2 (p.6): one column, full grid.
- **(f)** Figures in Calibri. ACM SIGPLAN captions with a bold "**Figure 6.**" lead. Captions sit below figures and tables.

### TriCheck Top Picks (IEEE Micro 2018)

- Same litmus-table convention (Fig. 4, p.9: initial conditions, thread columns, `a:`/`b:` labels, "**Forbidden C11 Outcome**").
- Overview (Fig. 1, p.3) has stacked-sheet suites, dark-gray models with ①–④, and a green/red/white outcome grid.
- Figs. 2–3 (pp.6–7) are tall "run ladders" with a green ✓ or red ✗ per run and red bold "**Bug:**" / "**Solution:**" notes. No µhb graphs.

### TransForm (ISCA'20), Trippel co-first author: the closest pipeline analogue (Alloy → candidate executions → litmus suite)

- **(a) Syntax / vocabulary as a table.** **Table I (p.8)** is "Summary of MTM vocabulary".
  - Two columns, "MTM elements | Descriptions", one column wide, full grid.
  - Element names are in typewriter (`Event`, `MemoryEvent`, `address`, `po`, `rf`, `co`, `fr`, `ghost`, `rf_ptw`, `rf_pa`, `co_pa`, `fr_pa`, `fr_va`, `remap`). Each description is one line of prose that uses typewriter for other vocabulary terms ("relates `Write` to `Reads` it sources").
  - **Gray-shaded rows mark inherited baseline elements**, and the caption says so: "The elements in gray are baseline MCM elements that TransForm builds on." The caption is below the table.
  - Relations are also defined in prose with typewriter names (p.3, §II).
- **(b) Execution graphs** (Fig. 2, p.3; Figs. 5–6, p.7–8; Figs. 10–11, p.13).
  - Nodes are **text labels, not shapes**: opcode letter, subscript instruction index from 0, then the access: `W₀ x = 1`, `R₁ y = 2`.
  - Ghost (non-user-visible) instructions take a **type subscript**: `W_db0`, `R_ptw0`, `W_PTE3`.
  - Thread columns are headed in bold (C0, C1).
  - **Every edge is labelled with its relation name** in a small sans font, coloured per relation: po black, rf red, rf_ptw purple, co blue, fr orange, remap brown, rf_pa teal.
  - po is a short vertical arrow with the label beside it ("po↓").
  - An uncertain edge carries a question mark ("rf?", Fig. 6(b), p.8).
  - **Flagging by highlight.** User-facing instructions are highlighted in yellow, and the caption says so ("User-facing instructions are highlighted in yellow", p.3).
  - In tabular litmus tests, ghost instructions are **indented on gray-shaded rows** (Fig. 6(c), p.8).
- **(d) Overview** (Fig. 7, p.9). Full width, one row, about 1.3 in tall.
  - Inputs at the left are gray rounded boxes: "MTM spec in Alloy (§V-A)" and "Synthesis bound". Implicit inputs have a **dotted border**: "Relation placement rules (§IV-A)", "Relaxation rules (§IV-B)".
  - A **dashed rounded container** titled "TransForm Synthesis Engine (§IV)" holds white step boxes with bold names and §-refs.
  - Intermediate artifacts are gray stacked documents labelled with their format: "Candidate Executions (Alloy)", "Pruned Candidate Executions (XML)".
  - **The pruning criteria are a numbered list inside one white box** ("Interesting ELT criteria (§IV-B): 1. #Write > 0  2. Forbidden by MTM  + Minimality criterion (§IV-B)").
  - Output: a stacked document, "Unique ELT suite".
  - Thick black arrows, sans text, grayscale.
  - Caption: 2 sentences, the second explaining the dotted inputs.
- **(e) Tables.** Table I as above.
- **(f)** Nodes are in Times; edge labels are in Helvetica/Arial (`pdffonts`: NimbusSanL, ArialMT). Multi-colour edges, one yellow highlight. Captions are 2–4 sentences ending with a notation sentence.

### rtl2µspec (MICRO'21), senior author

- **(a)** The µspec axioms are typewriter code with coloured keywords, inline in the text (p.5) and as a figure panel (Fig. 3f, p.6). SVA templates (Fig. 4, p.8) are typewriter with blue parameters and green symbolic values. No grammar figure.
- **(b) µhb graphs** (Fig. 1b, p.3; Figs. 3d–e, p.6) are grids of unlabeled hollow circles.
  - Row labels are typewriter (`inst_DX`, `mem`, `regfile`), with stage numbers 0/1/2 between dotted lines.
  - Instruction labels are lowercase typewriter `(i0)`…`(i3)` above the columns.
  - Edge colour encodes the edge type, and the caption is the legend: "Green/blue/pink edges correspond to spatial/temporal/data-flow HBIs. PO denotes program order" (Fig. 3e, p.6). Only PO gets an inline label.
  - The litmus test (Fig. 1a, p.3) is a small ruled table, `(i0) sw x, 1`, with a red bottom row "SC forbids r1 = 1, r2 = 0".
- **(d) Overview** (Fig. 2, p.5; crop). One column, vertical, grayscale.
  - The two inputs are document shapes on top. Each stage is a gray frame with a title and a **§-tag in a dog-eared corner box** (§4.1–§4.4), holding white step boxes.
  - The intermediate artifact is a stacked-document icon ("Proven HBIs").
  - Four stages fit in about a third of a column.
- **(e)** The results "table" is captioned as a figure (Fig. 5, p.12): full width, dense, small sans, gray header cells.
- **(f)** Linux Libertine body text (ACM). Bold ACM captions; the main caption is 1–3 sentences, while Fig. 3's caption walks through panels a→f.

### LCMs / Clou (ISCA'22), senior author: security execution graphs with a transient flag (closest semantics to SimSpect)

- **(a) Syntax.**
  - The vocabulary is defined in prose with typewriter relation names (`xstate`, `comx`, `rfx`, `tfo`; pp.4–6).
  - Examples go from code to graph. Fig. 1 (p.4): (a) a 3-line C listing; (b) an 8-line assembly pseudo-code listing with **bold opcodes** (`R size → r1`, `BEQZ r3, 8`, `W tmp ← tmp&r5`), line numbers, and rules above and below (booktabs style); then (c)/(d) the resulting graphs.
  - Inline code snippets in the running text use the same ruled style (p.7).
  - "We mechanize the LCM vocabulary in a toolkit built in Alloy" (p.7), but no Alloy code is shown.
- **(b) Execution graphs** (Fig. 1(c–d), p.4; Fig. 2, p.5; Figs. 3–5, pp.7–9; Fig. 7, p.10).
  - Nodes are **text labels, no shapes**: number, colon, bold opcode, operands. The number is the line of the pseudo-code listing, from 1: `1: R size → r1`, `5: R A+r2 (RW s1) → r4`.
  - Synthetic ⊤ (initial) and ⊥ (final) nodes.
  - **The transient flag is a subscript S** on both the number and the opcode: `5_S: R_S A+r2 (RW s1) → r4`. The caption says "speculatively-executed source instructions, denoted with subscript S" (Fig. 2b, p.5), and the text "transient (denoted with the subscript S)" (p.7).
  - **Every edge is labelled with its relation name, in the edge's colour**: po/tfo black, rf/rfx red and orange, addr purple, ctrl/data gray (Fig. 1d gray-only, p.4).
  - po/tfo are short vertical arrows with the label at left ("po↓", "po,tfo↓").
  - **Dashed edges mark the leak**: "dashed edges in figures denote com relations with comx inconsistencies—they 'point to' (via a directed edge) receivers" (p.7).
  - The S-AEG (Fig. 7, p.10) puts conditions in edge labels: `po[x1]`, `rf[x1]`, `rfx[x2]`.
  - No legend box. Notation is defined in the text and captions.
- **(d) Overview** (Fig. 6, p.10; crop). Full width, one row.
  - **Ellipses for data** (C source, executable; gray ellipses for configuration parameters, MCM + LCM, witness executions, transmitters). **Rectangles for steps and artifacts** (gray = Clou's own components, white = LLVM-IR).
  - Tool names sit on arrows in typewriter (`clang`), and §-refs sit inside boxes ("abstract CFG (§5.1)").
  - Grayscale. Caption: 3 sentences listing inputs and outputs.
- **(e) Tables.**
  - Table 1 (p.6) is the transmitter taxonomy: a 2-column full grid whose cells are coloured edge patterns (`access --addr--> transmit --rfx--> receiver`).
  - Table 2 (p.12): a tall one-column results table, full grid, typewriter benchmark names, small-caps tool names, bold for timeouts.
  - Listing 1 (p.13): a numbered C listing with key lines in bold, titled "Listing 1:" above it.
- **(f)** The ACM template, so figure text is in the paper's own font (Libertine, Inconsolata; `pdffonts`). Multi-colour edges. Bold ACM captions, 1–3 sentences, often stating a claim ("LCMs detect a transient transmitter and non-transient access", Fig. 3, p.7).

### RTL2MµPATH + SynthLC (MICRO'24), senior author

- **(a) Syntax as boxed pseudo-code** (Fig. 5, p.7; crop).
  - A one-column **light-gray rounded box** holding path-selector functions. Each starts with a green `//` comment with a bold lead ("// **CVA6 Core** `LD` (§IV-A): …"), then a typewriter signature with **yellow highlight** (`dst LD_issue(LD^N i0, ST^D_O i1)`), a blue `return`, and **salmon highlight** for implicit inputs.
  - The caption is the legend, with the same highlight colours applied to the caption words: "Implicit inputs and leakage signature components are highlighted. T^N/T^D_{O|Y}/T^S: intrinsic / older or younger dynamic / static transmitters…".
  - Fig. 3 (p.6) is an unboxed SystemVerilog listing with "+" marking added lines.
- **(b) µPATH graphs** (Fig. 1, p.2; Fig. 2, p.5; Fig. 4, p.6).
  - One column per instruction (ADD, LD, ST); rows are "performing locations" (IF, ID(1), ID(l), issue, scbIss, …). Nodes are small circles.
  - **Orange and blue fill = decision source and destinations** ("Orange/blue nodes in µHB graph figures throughout the paper denote … decision sources/destinations", p.7). A node label gives the visit count.
  - A dashed edge marks an implicit run of nodes, explained by a tiny gray inset key (Fig. 4a, p.6).
  - Instruction instances are `i0`, `i1`, with **type flags as superscripts and subscripts** on the opcode: `ADD^N`, `ST^D_O`, `LD^S` (p.7).
  - Every graph caption repeats the notation ("Row(1/l): 1st/l-th visit to Row. Node label: value of l", pp.2, 5, 6).
- **(d) Overview** (Fig. 6, p.9; crop). Full width but **very dense**, about 1.4 in tall.
  - Two lanes (RTL2MµPATH on top, SynthLC below) inside gray frames. Gray step boxes are each tagged §V-B1 … §V-C.
  - White boxes between steps show **miniature intermediate results** (node lists, ✓/✗).
  - The inputs are a stack of labelled sheets at left ("Instruction Encodings", "§V-A Metadata", "RTL Design"). The output is a folded document ("§IV-D Leakage Contracts").
  - One-line caption.
- **(e) Tables.**
  - Table I (p.8): one column, full grid, **thicker rules between defense groups**, ✓/- cells, typewriter column heads. The **caption is below** and defines the symbols ("a: Arguments. ✓/-: Relevant/irrelevant").
  - Table II (p.9): small, with colour-tinted header cells.
- **(f)** IEEEtran: Times body, Source Code Pro listings. Colour (orange, blue, yellow, salmon) carries meaning. Captions are "Fig. N:", 1–3 sentences, ending with a notation key.

### Serberus (S&P'24), senior author

- **(a)** Syntax is **always inline, never a figure**.
  - The ISA grammar is an inline display: `I ::= JMP d | BNZ r_sec, d | … | LFENCE | LD [r_a+d], r_dst | ST …` (p.5).
  - Semantics are inline inference rules with small-caps rule names (pp.6–7). Sequential parts are blue and transient parts red: "We use color to distinguish sequential and transient semantics" (footnote 11, p.6).
- **(b)** No graphs. Fig. 1 (p.9) is four boxed C snippets.
  - **Flags are typographic on the code**, and the caption is the legend: "Taint primitives are underlined; secrets are highlighted; transmitters are red."
- **(d)** Overview (Fig. 2, p.11, full width, short): a chain of plain rectangles. Arrows are labelled with the pass and its § ("Fence Insertion (§5.1)"). A dashed rounded outline groups the passes.
- **(e)** Table 1 (p.1) and Table 2 (p.5): one column, full grid, glyph cells (●, ◐, ✓/✗), legend in the caption.
- **(f)** IEEE Times, small caps for tool names. "Figure N:" captions, 2–3 sentences, legend included.

### Protean (HPCA'26), senior author

- **(a)** No grammar figure. The PROT prefix is shown inline (`PROT add rax, rdx`, p.6). The colour code is stated once: "We color-code protected/unprotected output registers and unprotected input memory in following examples and figures" (p.6). Blue means protected, orange unprotected.
- **(b)** Code stands in for graphs. Fig. 3 (p.7) is numbered assembly per compiler pass: inserted instructions and PROT prefixes are **bold**, and the caption says so. In Fig. 4a (p.8) the **transient transmitter is gray and underlined**, and the caption reuses the same styling as its legend.
- **(c) Pipeline diagram** (Fig. 4b, p.8; crop).
  - Stage columns with bold headers RN | EX | WB | RT, separated by vertical rules, with a dashed rule before RT.
  - State tags are vertical typewriter (`PC|rcx|rsp|mem`), coloured by protection.
  - Events are short phrases ("predict no access, untaint rcx"). A misprediction is red "misp. (!)"; a squashed wake is struck through.
  - **This is the only pipeline/timeline-style diagram in the set.**
- **(d)** Fig. 1 (p.2): a list inside one box with internal rules, under an italic column header.
- **(e)** Tables I–V (pp.2–13): all one column, gridded, typewriter contract names, bold for emphasis.
- **(f)** Captions are "Fig. N:" / "TABLE N:", 1–3 sentences, legend in the caption.

### CounterPoint (ASPLOS'26, Best Paper), senior author

- **(a)** The model DSL appears only as a typewriter snippet inside the overview (Fig. 2, p.4). Constraints are listed in full-width Table 1 (p.5), with the caption above (ACM).
- **(b)** µpath decision diagrams (Fig. 4, p.7; crop):
  - START is a circle, END a double circle; decisions are pale-yellow diamonds; events are pale-green rounded boxes; hardware counters are pale-blue typewriter pills.
  - A solid thick arrow is causality and a dotted arrow is happens-before.
  - **A boxed gray "Key" strip** shows every glyph. Each µpath has its own tinted panel.
- **(d)** Overview (Fig. 2, p.4): a full-width strip of six rounded panels, each holding a miniature of the real artifact.
- **(f)** Helvetica in figures, pastel fills. Long bold "**Figure N.**" captions (about 8–9 lines).
- This is the most colourful and least minimal paper in the set.

### Helium (ISCA'26), senior author: same IEEEtran ISCA template as SimSpect

- **(a)** "µobs functions" are **gray rounded boxed pseudo-code** (Fig. 1, p.2; Fig. 4, p.6): a green comment with a bold lead, typewriter code, a blue `return`, and math symbols inside the code. Metric definitions are a 3-row equation table (Table I, p.3).
- **(b)** A symbolic-execution tree (Fig. 6, p.7): filled dot = SAT, dashed hollow = UNSAT, a small boxed legend, and typewriter edge labels coloured per branch.
- **(d)** Overview (Fig. 5, p.7; crop).
  - Full width, two lanes (TracerSym, TracerSim). Each lane is a gray frame with a bold name and a §-ref ("(§VI-A1)").
  - Dark-gray rounded step boxes, each over **a white box with the concrete intermediate result** (code, formulas, counts).
  - Inputs and outputs are gray tab shapes, with an example under each input. Arrows are steel blue.
- **(e) Tables** (I–VII, pp.3–11): all one column, very dense, full grid. Group-header rows span the table and are shaded light blue; red cells flag bad results. **Captions below** ("TABLE I: Information-theoretic leakage metrics", p.3, checked with `pdftotext -layout`).
- **(f)** Times body; figures in Calibri/Aptos and Consolas (PowerPoint). Blue accent plus purple, green and yellow highlights. Captions are "Fig. N:", 1–3 descriptive sentences; notation-heavy figures run longer (Fig. 6 is about 9 lines).

## Synthesis: conventions to adopt in SimSpect

Each item names the precedent with page cites. Items marked **DECIDE** are real choices for Anna and are also listed at the end.

### (i) Presenting the execution-graph syntax: figure, table, or inline listing?

The group has three precedents:

- **(A) Vocabulary table.** TransForm Table I (p.8): one column wide, two columns "element | description", typewriter names, gray rows for what is inherited. CheckMate Fig. 3(b) (p.8) is the same idea ("Alloy Signature | Set Contains All…").
- **(B) Alloy code listing.** CheckMate Figs. 1(b) and 3(a) (pp.2, 8): numbered, typewriter, coloured keywords, shown as a subfigure. SynthLC and Helium use boxed pseudo-code in a gray rounded box (p.7; pp.2, 6).
- **(C) Inline only, taught by an example graph.** LCM defines its vocabulary in prose and teaches it through Fig. 1's code → asm → graph progression (p.4). Serberus puts its grammar inline (p.5).

None of the 13 papers uses a BNF or grammar *figure*.

Anna's current draft (`drafts/_standalone_execgraphsyntax-1.png`, one box with three numbered rows plus an example graph) is closest to (A) plus the example from (C). **Recommendation:** keep the one-box, three-row structure, but borrow two things from TransForm Table I. First, set the element names in typewriter exactly as they appear in the `.als` (`TLoad`, `isresolved`, `rf`, `ddi`, `spo`), each with a short gloss. Second, if any row is defense-specific, reuse SimSpect's gray-row convention, which matches TransForm's gray = baseline idea. **DECIDE (1)**: table-style figure (A) vs. Alloy listing (B) vs. inline (C).

### (ii) Graph notation

- **Nodes are text labels, not boxes or circles, for instruction-level graphs.** Precedents: LCM (pp.4–10) and TransForm (pp.3, 7–8). Circles on a grid belong only to µhb/µPATH graphs, whose rows are pipeline locations (CheckMate p.10, rtl2µspec p.3, RTL2MµPATH p.6). SimSpect's graphs relate instructions and operands, so the LCM/TransForm style is the right precedent. The current draft's boxed rows are fine but heavier than the house style.
- **Instruction labels: number from 0 and use a lowercase `i`** (CheckMate litmus `(i0)` p.2; rtl2µspec `(i0)` p.3; SynthLC `i0`, `i1` p.7; TransForm subscript 0 `W₀` p.3). There are two counter-examples. CheckMate's µhb headers use an uppercase `A.I0` with a process prefix (p.10). LCM numbers from 1 because labels equal listing lines (p.4). **DECIDE (2)**: the current draft uses italic `I0`/`I1`, and the older paper figures used `I1`.
- **Flags go on the instruction label, not in a separate column.** The group consistently marks status on the label itself:
  - LCM: subscript S for transient (`5_S: R_S …`, pp.5, 7).
  - SynthLC: superscript/subscript type flags (`ST^D_O`, p.7).
  - TransForm: yellow highlight for user-facing instructions and type subscripts for ghost instructions (p.3).
  - CheckMate: red text for the privileged address and the mnemonic `B PNT, T` for a mispredicted branch (p.10).
  - Serberus and Protean: underline, gray or red text for the transmitter (p.9; p.8).

  None of the papers uses an r/c/t check column. **DECIDE (3)**: keep the r/c/t dot column (clear in B&W, but not house style), or move flags onto the label (e.g. subscripts like LCM's S, or bold/underline for the target transmitter as in Protean p.8).
- **Label every edge with its relation name.** LCM (p.5) and TransForm (p.3) label every edge (rf, addr, po, …) right next to the arrow. In B&W, the label replaces their per-relation colour. Program order is a short vertical arrow with a single "po↓" label (LCM p.5, TransForm p.3), which supports the current draft's single "spo" axis.
- **Dashed means the leak or the uncertain edge.** In LCM, dashed edges are the leaking com edges pointing at receivers (p.7). TransForm writes "rf?" for an ambiguous edge (p.8). If SimSpect keeps dashed for ddi, that is a deliberate departure, worth a sentence in the caption.
- **The legend goes in the caption, not in a key box.** This holds in all the core papers: CheckMate Fig. 5 (p.10), TransForm Fig. 2 (p.3), rtl2µspec Fig. 3e (p.6), Serberus Fig. 1 (p.9), Protean Fig. 3 (p.7), and RTL2MµPATH every graph (pp.2, 5, 6). Newer papers add a small key only when there are more than 4 glyph kinds (CounterPoint p.7, Helium p.7, RTL2MµPATH inset p.6). This fits SimSpect's "one-line legend" rule.
- **Colour: the group uses it, but CheckMate shows that B&W plus one accent works.** CheckMate's µhb graphs are black with red for the attack pattern only (pp.2, 10). LCM and TransForm colour every relation (pp.5, 3). SimSpect's visual language is B&W plus gray for defense-specific. **DECIDE (4)**: stay strictly B&W, or allow one red accent for the leak path / target transmitter, as CheckMate does.

### (iii) Overview figure

- **Section reference on every stage.** This is the strongest house convention, present in all six overviews checked: CheckMate §-tabs (p.7), TransForm "(§IV-A)" in boxes (p.9), rtl2µspec corner §-tags (p.5), LCM "(§5.1)" (p.10), SynthLC §V-B1… (p.9), and Helium "(§VI-A1)" (p.7). SimSpect's current `_standalone_pipeline_vertical.tex` has none (grep found no `\S`). **Recommendation:** add a small 7pt §-ref to each stage once the section numbers are stable.
- **Inputs are document shapes entering from the top or left. Intermediate artifacts are stacked documents labelled with their format. Outputs leave at the bottom or right.** Precedents: CheckMate (p.7, with bold "**Input:**"/"**Output:**" leads), TransForm (p.9: "Candidate Executions (Alloy)", "Pruned … (XML)"), rtl2µspec (p.5), Helium (p.7). SimSpect's icon-plus-multiplicity treatment of outputs is consistent with this.
- **Tool steps are white boxes inside one container named after the tool.** CheckMate uses a light-gray container with a vertical "CheckMate" label (p.7). TransForm uses a dashed rounded container titled with a §-ref (p.9). rtl2µspec gives each stage a gray frame (p.5).
- **A list goes inside one box.** TransForm's pruning criteria are a numbered list in one box (p.9), and Protean Fig. 1 has a list in one box with internal rules (p.2). This matches Anna's rule exactly.
- **Implicit or fixed inputs get a dotted border** (TransForm p.9). This is an option for "relaxation rules" or other fixed pipeline knobs.
- **Grayscale, and 1.3–1.6 in tall at full width** (CheckMate p.7, TransForm p.9, LCM p.10). A vertical one-column flow is also precedented (rtl2µspec Fig. 2, p.5, about a third of a column; TriCheck Fig. 6, p.6), so SimSpect's vertical one-column pipeline is in-house.
- **Optional: a miniature real example in each stage** (SynthLC p.9, Helium p.7, CounterPoint p.4). This is denser and more recent. Use it only if space allows.
- **Caption: 2–3 sentences that say what goes in, what comes out, and what any special border means** (CheckMate p.7, TransForm p.9, LCM p.10).

### (iv) Tables

- **One column wide, full grid (vertical and horizontal rules, not booktabs), small font, dense.** Seen in CheckMate Table I (p.11), TransForm Table I (p.8), LCM Tables 1–2 (pp.6, 12), RTL2MµPATH Table I (p.8), Serberus Tables 1–2, Protean Tables I–V, and Helium Tables I–VII.
- **Thicker rules or shaded spanning rows separate groups** (RTL2MµPATH p.8; Helium pp.10–11). **Gray rows mark a category** (TransForm p.8).
- **Typewriter for code and model names in cells. ✓/- or glyph cells for feature matrices.** The legend goes in the caption ("✓/-: Relevant/irrelevant", RTL2MµPATH p.8).
- **In the group's IEEE-template papers, the caption sits below the table** as "TABLE I: …" (CheckMate p.11, TransForm p.8, RTL2MµPATH pp.8–9, Helium p.3). The ACM papers vary (CounterPoint puts it above, p.5). **DECIDE (5)**: below (house practice) or above (the usual IEEE convention).
- Feature matrices and litmus tests are sometimes captioned as **Figures** (TriCheck Figs. 3, 7, pp.3, 8; rtl2µspec Fig. 5, p.12).

### Fonts, colour, captions (all figures)

- **Font.** Older papers drew figures in PowerPoint with Calibri, Consolas or Arial (CheckMate, TriCheck, Helium; confirmed with `pdffonts`). Only LCM (ACM, Libertine) and TransForm's node text use the paper's own serif. SimSpect's "inherit Times, no font family inside the tikzpicture" rule is *more* consistent than the house practice, and nothing in the precedent argues against it.
- **Captions.** "Fig. N:" (IEEE): a title sentence, then 1–3 explanatory sentences, **ending with a notation or legend sentence**. Sub-captions are descriptive phrases. Precedents: TransForm p.3, RTL2MµPATH pp.2, 5, 6, 7, CheckMate p.10. CheckMate's 3–5-sentence sub-captions (p.2) are the long extreme.
- **Colour** is used for meaning in every paper (red = attack or bug, green = OK, orange/blue = node roles, yellow highlight = the thing to look at). It is never decorative. Pure B&W is the exception in the group, though overviews are almost always grayscale.

## Crops (150 dpi, rendered with `-hide-annotations` so hyperref link boxes are absent)

All are in `paper_figures/reference_papers/crops/`:

| File | What it shows | Why it matters |
|---|---|---|
| `checkmate_micro18_p2.png` | CheckMate Fig. 1: µspec Alloy listing, Flush+Reload pattern, µhb graph, security litmus test | flagship µhb notation; listing as subfigure; long sub-captions |
| `checkmate_micro18_p7.png` | CheckMate Fig. 2 toolflow | inputs/outputs as documents, §-tabs, one gray container |
| `checkmate_micro18_p8.png` | CheckMate Fig. 3(a–b): Alloy `sig` listing + "Alloy Signature \| Set Contains All…" table | syntax-as-listing and syntax-as-table side by side |
| `checkmate_micro18_p10.png` | CheckMate Fig. 5: Meltdown/Spectre/MeltdownPrime/SpectrePrime µhb graphs | B&W + one red accent; flags on labels (`B PNT, T`, red `PA0:V`); legend in caption |
| `tricheck_asplos17_p6.png` | TriCheck Fig. 6 toolflow + Table 2 | one-column flow with numbered steps; full-grid code table |
| `transform_isca20_p3.png` | TransForm Fig. 2: execution graphs with labelled, coloured edges, subscripted ghost instructions, yellow-highlighted user-facing instructions | text-label nodes; every edge labelled; flag-by-highlight with caption legend |
| `transform_isca20_p8.png` | TransForm Table I: MTM vocabulary (typewriter names, gray = baseline) | the closest precedent for a syntax table |
| `transform_isca20_p9.png` | TransForm Fig. 7: Alloy synthesis engine → pruned candidate executions (XML) → unique ELT suite | closest overview analogue to SimSpect; list in one box; dotted implicit inputs |
| `lcm_clou_isca22_p4.png` | LCM Fig. 1: C listing → asm pseudo-code → event-structure graphs | code → graph progression; numbered text-label nodes; labelled edges |
| `lcm_clou_isca22_p5.png` | LCM Fig. 2: microarchitectural vs. speculative semantics; transient nodes with subscript S; dashed leak edges | the flag-as-subscript precedent in a security execution graph |
| `lcm_clou_isca22_p10.png` | LCM Fig. 6: Clou overview (ellipses = data, boxes = steps, gray = Clou's own) | grayscale one-row overview with §-refs |
| `rtl2mupath_synthlc_micro24_p7.png` | SynthLC Fig. 5: boxed path-selector pseudo-code with highlights; caption is the legend | boxed listing; super/subscript type flags on instructions |
| `rtl2mupath_synthlc_micro24_p9.png` | RTL2MµPATH/SynthLC Fig. 6: dense two-lane overview | §-ref on every box; mini examples between steps |
| `rtl2uspec_micro21_p5.png` | rtl2µspec Fig. 2: one-column vertical overview with gray stage frames and §-tags | precedent for SimSpect's vertical one-column pipeline |
| `protean_hpca26_p8.png` | Protean Fig. 4: annotated asm + pipeline-stage diagram (RN/EX/WB/RT) | only pipeline/timeline-style diagram; transient transmitter styled gray+underlined |
| `helium_isca26_p7.png` | Helium Fig. 5: two-lane overview in the ISCA'26 IEEEtran template | same template as SimSpect; §-refs in lanes |
| `counterpoint_asplos26_p7.png` | CounterPoint Fig. 4: µpath decision diagram with boxed Key strip | counter-example: when a key box is used |

## Decisions for Anna (surfaced, not made)

1. **Syntax presentation**: (A) TransForm-style vocabulary table/box with typewriter `.als` names (recommended: closest to your current draft and to Trippel precedent), (B) CheckMate-style Alloy listing, or (C) prose plus example graph only (LCM, Serberus).
2. **Instruction labels**: `i0, i1, …` (lowercase, from 0; the majority of the group papers) vs. the current `I0/I1` (or `I1`-based in the older paper figures).
3. **Flags (resolved / committed / target transmitter)**: keep the r/c/t dot column, or put flags on the label (subscripts like LCM's `5_S`; underline or bold for the transmitter like Protean or Serberus) with the legend in the caption. No Trippel paper uses a check column.
4. **Colour**: strict B&W (current rule) vs. B&W plus one red accent for the leak path, as in CheckMate (pp.2, 10).
5. **Table caption placement**: below (Trippel's IEEE papers) vs. above (the usual IEEE convention).
6. **Housekeeping**: `paper_figures/reference_papers/` holds about 19 MB of third-party PDFs and is not gitignored (`git check-ignore` returned nothing). Before the next `make sync`, decide whether to add `paper_figures/reference_papers/**/*.pdf` to `.gitignore` (crops are about 2 MB).
