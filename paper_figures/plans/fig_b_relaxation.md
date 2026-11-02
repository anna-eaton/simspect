# Figure (b): relaxation / minimality (redo of `tikz/relaxation.tex`)

**Draft:** `paper_figures/drafts/_standalone_relaxation_v3.tex` + `_standalone_relaxation_v3-1.png` (300 dpi). **Rendered size:** 246 x 110pt as a standalone with newtx fonts (page 248.2 x 112.3pt incl. the 1pt border); 247.2 x 111.1pt with the paper's own fonts and preamble (IEEEtran ptm/pcr, CM math; measured with `paper_figures/drafts/audit/wrap_template.tex`). One column is 252pt (`VISUAL_LANGUAGE.md`). Nothing in the paper clone, any `.als`, or `parsexml.py` was touched; the paper text changes below are proposals for Anna to paste.

Anna's note: "relaxation figure: go from [stacked graphs a, b, c collapsing onto one minimal graph] **to 1 prog! with the redundant components in red with italicized explanations on the right**", and "incorporate this as old fig 2 as well, show graph."

## 1. What exists now

- `tikz/relaxation.tex` (`\input` at `sections/pipeline.tex:21`, label `fig:four-panes`; the text at `pipeline.tex:20` refers to it as `fig:relaxation`, which is not defined anywhere, so that reference is currently broken).
- Four stacked panes of 3–4-line programs in `\ttfamily`: (d) is the boxed "backbone" `branch_n; load reg0 <- mem 0; load ? <- [reg0]` (branch unresolved, nothing committed); (a) the same program but the transmitter's destination is specified as `reg1`; (b) a second transmitter `load ? <- [reg0]`; (c) the middle load also left unresolved. Thick gray arrows route (a), (b), (c) into (d). The caption says all three pass the violation predicate but reduce to (d) under the relaxations, so Alloy does not synthesize them.
- None of the four programs is a real Alloy instance; they are illustrative.
- In the paper's fonts it measures **228.6 x 381.9pt** (`paper_figures/drafts/audit/audit_relaxation.log`), more than half the 672pt column. The audit render (`drafts/audit/audit_relaxation.png`) shows the bold `r` labels colliding with the `mem 0` boxes and `rf` labels over the text, because the paper's typewriter font is Courier (`IEEEtran.cls:496`), which is wider than the font the figure was drawn for. It also breaks the visual language: bold labels, typewriter for non-code, gray used for arrows (gray is reserved for defense-specific), and a rounded frame.
- Old Fig. 2 (`tikz/alloyviolation.tex`, label `fig:ddi-rf`, `\input` at `pipeline.tex:13`) is a 4-line listing (`branch_n; load reg1 <- mem 1; other_n reg2 <- reg1, reg0; load ? <- [reg2]`) with ddi/rf arrows showing the path from protected `mem 1` to the transmitter's address; 192.7 x 81.7pt in paper fonts.

## 2. What minimality means in the model (sources)

- Perturbation tags: `RO` remove operand, `RC` make committed, `RR` make resolved, `RI` remove instruction, `RS` remove state (`STAGE1_alloy/models/STT_6.als:191-195`). Their effect: `committed_p`/`resolved_p` add the tagged instructions to the committed/resolved sets (`:204`, `:206`); `i_p` drops `RI` instructions (`:213`); `o_p` drops `RO` operands and every operand whose state is tagged `RS` (`:214`).
- `secure_speculation_scheme_p[p]` (`:262-265`): no operand on protected state, and nothing reachable from one through rf/ddi edges, is a leaked operand of a speculative transmitter, under perturbation `p`. "Violating" = `not secure_speculation_scheme_p[no_p]`.
- `gen_useful_litmus` (`:301-311`): the instance violates (`:302`); every unresolved instruction except the commit boundary is necessary, i.e. resolving it alone makes the program secure (`:306`); the boundary (`first_uncommitted`, `:139`) is necessary when committed and resolved together (`:308`); every state element is necessary (`:310`). **STT_6 has no RI/RO clause** (`CLAUDE.md`; `wiki/findings/mdsToRead/ENUMERATION_OVERSPECIFICATION.md` "root cause 3"), which matches the paper: the interleaving round "turn[s] off the remove instruction relaxation, and the remove operand" (`pipeline.tex:34`). `fact no_extra_inst` (`:313`) only forbids operand-less non-branch instructions.
- The full five-relaxation minimality that the paper's list describes (`pipeline.tex:17-29`) is `STAGE1_alloy/models/STT_6_core.als`, which adds `all o: Operand | secure[RO->o]` (`STT_6_core.als:301`) and `all i: Instruction | secure[RI->i]` (`:303`). Per `wiki/findings/mdsToRead/STAGED_ENUMERATION.md` ("Stage 1"), it yields 2 canonical 3-instruction cores: unresolved branch, then load1 (mem to reg), then load2 (transmitter, address rf-fed by load1). That is old pane (d), the fig (a) draft's example, and the black part of this figure.
- STT defense block used to judge the example: speculative = uncommitted and after an unresolved branch (`speculation_contract_p`, `STT_6.als:325`, via `has_unresolved_brs_p` `:245`); protection set = all memory (`hardware_protection_policy`, `:326`); leaked operands = load address and `Branch_x` input register (`leakage_function`, `:328`).

## 3. The example (real instance)

**Source:** `testsets/STT_6/xml/inst-047231.xml` (the STT_6 testset on cafe2; provenance in `wiki/findings/bug/stt_slowcomm_vp_squash_race/provenance.json`). Local byte-identical copies (checked with `cmp`): `testsets/DEMO_corpus/xml/inst-047231.xml` and `wiki/findings/bug/stt_slowcomm_vp_squash_race/inst-047231.xml`. Its concretized program is `.../inst-047231.s` in the same bug folder. This is also the test behind the STT visibility-point/squash race result (`wiki/findings/bug/stt_slowcomm_vp_squash_race/example_inst-047231.md`), so the figure reuses a test the paper already discusses.

Decoded (rows in spo order via the `idx` field; nothing omitted: all 6 instructions, 6 operands, 3 states, 2 rf + 1 ddi edges, all flags):

| Row | Alloy atom | Kind | Operands (atom → state) | Flags | Edges |
|---|---|---|---|---|---|
| I0 | Instruction$5 (IX0) | TOthern | Outreg$0 → Reg_s$1 (r1) | resolved, committed | rf Outreg$0 → Inreg$0 (I4) |
| I1 | Instruction$4 (IX1) | TOtherx | Outreg$1 → Reg_s$0 (r0) | none (first uncommitted) | none |
| I2 | Instruction$3 (IX2) | TBranchn | none | none | none |
| I3 | Instruction$2 (IX3) | TLoad | Inmem$0 → Mem_s$0 (m0), Outreg$2 → Reg_s$0 (r0) | resolved | ddi Inmem$0 → Outreg$2; rf Outreg$2 → Inaddr$0 (I5) |
| I4 | Instruction$1 (IX4) | TBranchx | Inreg$0 → Reg_s$1 (r1) | resolved | none |
| I5 | Instruction$0 (IX5) | TLoad | Inaddr$0 → Reg_s$0 (r0) | xm (target transmitter) | none |

**How each mark was checked.** A scratch Java tool (Alloy 6 API, `STAGE1_alloy/alloy6.jar`, Java 17) loads a read-only copy of the current `STT_6.als`, reads the XML with `A4SolutionReader`, and evaluates expressions on it. A component is redundant iff `secure_speculation_scheme_p[<its perturbation>]` is **false**, i.e. the program still violates without it.

| Component | Perturbation | Result | Verdict |
|---|---|---|---|
| I0 `Other_n r1 <- ?` | `RI->Instruction$5` | false | redundant (red) |
| I1 `Other_x r0 <- ?` | `RI->Instruction$4` | false | redundant (red) |
| I4 `Branch_x r1` | `RI->Instruction$1` | false | redundant (red) |
| state r1 | `RS->Reg_s$1` | false | redundant (red, tag RS on I4) |
| I5 unresolved | `RR->Instruction$0` | false | redundant flag (red hollow dot) |
| operands of I0, I1, I4 | `RO->Outreg$0`, `RO->Outreg$1`, `RO->Inreg$0` | false each | redundant (already red via RI) |
| commit boundary I1 | `RC->Instruction$4 + RR->Instruction$4` | false | redundant (already red via RI) |
| I2 unresolved | `RR->Instruction$3` | true | necessary (black) |
| I2, I3, I5 | `RI->` each | true each | necessary (black) |
| m0, r0 | `RS->` each | true each | necessary (black) |
| ddi/rf operands of I3, I5 | `RO->Inmem$0`, `RO->Outreg$2`, `RO->Inaddr$0` | true each | necessary (black) |

The reduced program (delete I0, I1, I4; resolve I5) still violates (`RI->(I0+I1+I4) + RR->I5`: false), and from it every remaining component is necessary (each further `RI`, `RO`, `RS`, and `RR->I2` gives true). Facts behind the explanations: the only rf out of I0 goes to I4; I5 reads r0 from I3 (rf `Outreg$2 -> Inaddr$0`), and I1's write of r0 has no rf; the protected-reachable operands are only `{Outreg$2, Inaddr$0}`, so I4's r1 carries no protected data; `speculation_contract_p[no_p] = {I3, I4, I5}`, all after unresolved branch I2, so I5 is speculative whatever its own resolved flag.

**Provenance caveat (verified, partly already known).** This instance does **not** satisfy STT_6's own `gen_useful_litmus`, neither the current one nor the one at the provenance commit `d8b6caa`: `all i: unresolved | secure[RR->i]` fails on I1 and I5, and `all s: State | secure[RS->s]` fails on r1, while every model fact holds. `claudelog.md` (2026-06-02, "STT_6 / STT_6_interleave TESTSETS ARE STALE (pre-effective-RS)") already records that `testsets/STT_6/xml` was generated on 2026-05-19 from a model state without an active RS clause. This check adds that the RR clause was not effective either. The XML also carries a skolem `$gen_lit_s = Mem_s$0`, which hints that the generating command quantified `s` existentially; that part is unverified. So the example is a real enumerated instance, but one the current model would prune. That is why it shows redundancy, and it is also why it needs a Decision below.

Evaluator (scratch, re-runnable):

```java
// EvalInst.java  —  javac -cp alloy6.jar EvalInst.java
// echo 'secure_speculation_scheme_p[RR->Instruction$0]' | java -cp alloy6.jar:. EvalInst STT_6.als inst-047231.xml
import edu.mit.csail.sdg.alloy4.*; import edu.mit.csail.sdg.ast.*; import edu.mit.csail.sdg.parser.*;
import edu.mit.csail.sdg.translator.*; import java.io.*;
public class EvalInst { public static void main(String[] a) throws Exception {
  CompModule w = CompUtil.parseEverything_fromFile(new A4Reporter(), null, a[0]);
  A4Solution s = A4SolutionReader.read(w.getAllReachableSigs(), new XMLNode(new File(a[1])));
  for (ExprVar v : s.getAllAtoms()) w.addGlobal(v.label, v);
  BufferedReader r = new BufferedReader(new InputStreamReader(System.in)); String l;
  while ((l = r.readLine()) != null) if (!l.isBlank()) System.out.println(l + " ==> " + s.eval(w.parseOneExpressionFromString(l)));
}}
```

## 4. What changes (the redesign)

- **One program, not four.** The six rows of inst-047231 in program order. Black = the violation: protected `m0` (gray, since STT's protection set is a defense-specific clause, `STT_6.als:326`) flows by ddi into `r0` in I3 and by rf into the address of target transmitter I5, which is speculative because branch I2 is unresolved. Red = everything the relaxations remove while the program still violates: rows I0, I1, I4 (type, operands, their flag dots), the red rf edge I0 → I4, and a red hollow dot in I5's `r` column (a flag RR would set). A 7pt italic explanation sits to the right of each red row and ends with the relaxation tag(s).
- **Explanations** (black italic, so the red marks only components): I0 "Only feeds I4 (RI)"; I1 "I5 reads r0 from I3, not I1 (RI)"; I4 "Its r1 carries no protected data (RI, RS)"; I5 "Needlessly unresolved: I2 already makes I5 speculative (RR)".
- **Listing with the graph overlaid, not a separate node-link graph.** The rf/ddi edges attach to operands (`Operand.rf`, `Operand.ddi`, `STT_6.als:81-82`) and the rows are spo, so one object shows both program and graph ("1 prog", "show graph"). A separate node-link graph would repeat the program and cost the width needed for the explanations. Instruction boxes (as in the fig (a) draft, `drafts/_standalone_execgraphsyntax.tex`) were not used, because the rf edges I3 → I5 and I0 → I4 skip rows and would cut through the boxes between them.
- **Notation follows the fig (a) draft** so (a) → (b) reads as one system: Roman type names with subscripts as in the paper text (`pipeline.tex:9`), `r_i`/`m_i`, `?` unspecified, `[ ]` address, rf solid, ddi dashed, flag dots under `r c t`. No typewriter (`VISUAL_LANGUAGE.md`: typewriter only for literal code).
- **Changes from the XML, all presentational:** rows numbered by `idx`, atoms renamed (Reg_s$k → r_k, Mem_s$0 → m0); `?` also marks unspecified *inputs* (I0, I1), while fig (a) defines it for outputs only; I4's `r1` sits in the input column, since a branch has no output; I0 shows both `r` and `c` dots, since committed implies resolved (`STT_6.als:134`).
- **Red** = `\definecolor{rlxred}{HTML}{B3322C}`, a knob at the top of the figure body. It is the same hex as the existing `ctarget` in the paper preamble (`bare_conf_compsoc.tex:347`), so the paper keeps a single red.
- **Proposed caption** (for Anna to paste): "A violating STT execution from our enumeration (inst-047231), before minimization. Rows are in program order; solid and dashed arrows are rf and ddi edges; dots mark resolved ($r$), committed ($c$), and the target transmitter ($t$). Black: the violation, a dependence path from $m_0$ (gray: in STT's protection set) through I3 to the address of transmitter I5, which is speculative because branch I2 is unresolved. Red: components whose removal (RI, RS) or flipping (RR; hollow dot) leaves the execution violating. Minimality removes them, leaving the three-instruction backbone I2, I3, I5."
- **If Anna adopts it** (her edits; nothing was changed in the paper): create `tikz/relaxation_v3.tex` from the "FIGURE BODY" block inside `\begin{figure}[t]\centering ... \caption{...}\label{fig:relaxation}\end{figure}`; change `pipeline.tex:21` to `\input{tikz/relaxation_v3}`. Using `\label{fig:relaxation}` also fixes the broken `pipeline.tex:20` reference. If merging with old Fig. 2 (option A below), also delete `\input{tikz/alloyviolation}` at `pipeline.tex:13` and repoint `\ref{fig:ddi-rf}` at `pipeline.tex:8`, `:11`, `:32` (`:11` describes Fig. 2's I1/I2/I3 and would need rewording to "the transmitter load I5 has an address dependency on the load I3").

## 5. Reading of "old fig 2"

Figure numbers follow `\caption` order: Fig. 1 = `tikz/threelayer` (`intro.tex:25`), **Fig. 2 = `tikz/alloyviolation` (`pipeline.tex:13`, `fig:ddi-rf`)**, Fig. 3 = `tikz/relaxation` (`pipeline.tex:21`); `model.tex` has no live figures (all commented out). So "old fig 2" is most likely the ddi/rf violation listing. "Show graph" most likely means keep its dependence-graph overlay. My reading: **the new relaxation figure should also do Fig. 2's job.** Its black part is a violation with the dataflow graph drawn (Fig. 2's role); its red part is the relaxation story (Fig. 3's role). One figure replaces two and saves about 350pt of column height (81.7 + 381.9pt now vs 111pt). Confidence: moderate. Alternatives: (i) "old fig 2" means figure 2 of an older printed draft (the clone has a single commit, `5b6c7fa`, so history can't be checked); (ii) it means "put the new figure where Fig. 2 is". Also note that the separate fig (a) draft (`drafts/_standalone_execgraphsyntax.tex`) already shows the minimal backbone as its example; if fig (a) replaces old Fig. 2, this figure only needs the relaxation role.

## Decisions for Anna

- [ ] **DECIDE: is (b) a merge of old Fig. 2 + Fig. 3?** (A) Merge: this figure replaces both; the black violation path plus gray `m0` carries Fig. 2's message. Text edits are listed in §4. (B) Keep a separate Fig. 2 (or let fig (a) carry it) and make (b) relaxation-only; the gray could then be dropped. (C) Something else meant by "old fig 2". *Recommendation:* A, unless fig (a) is meant to replace Fig. 2, in which case B. Knock-on for either: the interleave figure is built on old Fig. 2's program (`tikz/interleave.tex` rows I2–I5 = Fig. 2's I0–I3; text `pipeline.tex:32`), so if Fig. 2 goes, interleave needs a new base (for example this figure's backbone, or fig (a)'s example).
- [ ] **DECIDE: is a stale-testset instance acceptable?** inst-047231 is real but came from the 2026-05-19 enumeration that lacked effective RS (and, per §3, RR) minimality; the current `STT_6.als` would prune it. (A) Use it; the caption says "from our enumeration, before minimization" (true of how it was produced). (B) Use an instance from a current STT_6 testset. Those can only show RI/RO redundancy, because RS/RR are enforced, so the RS and RR marks would be lost. (C) Generate one from a scratch copy of the model with chosen clauses off. That is a model variant, so it needs your OK. *Recommendation:* A. It is the test behind the paper's VP-squash race result, and every red mark is checked against the current model.
- [ ] **DECIDE: which relaxations to show.** The draft tags RI, RS, RR, each shown on its own component. RO and RC also hold here, but only on parts already red for RI (table in §3), so tagging them adds text without a new component. Keep three, or tag all five (for example I1 "(RI, RO, RC)")? *Recommendation:* keep three and let the list in the text define all five.
- [ ] **DECIDE: notation shared with fig (a).** Unboxed listing (b) vs instruction boxes (a); `?` for unspecified inputs too (fig (a)'s note says outputs only; suggest "? = operand left unspecified" in both); flag dots vs the old figures' `r c` letters. *Recommendation:* pick one for (a), (b), and the interleave redo; dots plus unboxed listing scale best to 6 rows.
- [ ] **DECIDE: red and gray details.** Hex `#B3322C` (= `ctarget`) or a more muted red; explanations black (current) or red; gray on `m0` (protection set is defense-specific) or plain.
- [ ] **Paper text (yours to edit):** `pipeline.tex:27` defines RC as "flip last-uncommitted instruction to committed", but the model perturbs `first_uncommitted` (`STT_6.als:139`), and only together with RR (`:308`). Suggest "RC: commit (and resolve) the first uncommitted instruction". Also, `pipeline.tex:20` cites `fig:relaxation`, but the current figure is labeled `fig:four-panes`.
- [ ] **Semantics note behind the I5 explanation:** in STT_6, resolving a non-branch never changes the predicate. Speculation and protection-set propagation depend only on unresolved *branches* (`:325`, `:245`, `:254`), so RR-minimality (`:306`) forces every non-boundary non-branch to be resolved. "I2 already makes I5 speculative" states that accurately. Say if you prefer the wording "STT ignores load resolution".
