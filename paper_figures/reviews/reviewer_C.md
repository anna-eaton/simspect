# Review C — SimSpect: Automated Litmus Testing for Simulated Spectre Defenses

**Summary.** The paper proposes SimSpect, a pipeline that takes a formal three-part specification of a Spectre defense, enumerates minimal "leakage backbone" litmus tests via Alloy, concretizes them to annotated x86 programs, and replays them on a gem5 prototype to detect whether the defense actually blocks the leak.

## Strengths
- **Important, under-served problem.** Validating *security* of early-stage simulator defense prototypes (vs. functional correctness) is a real gap, and the observation that buggy defenses silently invalidate published performance overheads is a compelling motivation.
- **Genuinely novel angle.** Directed, defense-specific test generation from an axiomatic spec — adapting the Lustig/MCM minimal-litmus methodology to speculative leakage — is a fresh and well-motivated contribution that is clearly differentiated from AMuLeT's random relational fuzzing.
- **Clean conceptual decomposition.** The three-axis specification (leakage contract / execution contract / protection set) is an elegant framing and the strongest idea in the paper.
- The pipeline figure is good and conveys the flow well.

## Weaknesses
- **Overclaiming on "comprehensive."** The central claim that the generator produces *all* leakage forms is asserted, not justified, and is internally contradicted: it is comprehensive over leakage paths but admittedly *heuristic* in concretization and incomplete over interleavings. This must be scoped precisely or it reads as a marketing claim.
- **No actual results.** "Preliminary results" contains essentially zero findings — no bug found, no test counts, no comparison numbers. For a problem framed around catching real security bugs, the paper currently does not demonstrate it catches any. Even one concrete discovered discrepancy would transform the contribution.
- **Unfinished prose.** The draft still contains visible author/reviewer TODO macros, `\cite{}` with empty keys, and future-tense ("we will," "we are currently implementing") throughout the evaluation. This is not submission-ready.
- **Pacing for a non-specialist.** Terms (transmitter, backbone, skeleton, speculation primitive, ddi/rf) arrive faster than they are defined; the relaxation codes (RI/RO/RS/RC/RR) appear without enough intuition. A reader outside uarch-security will struggle.

## Detailed comments
- The two "Background" sections (`background.tex`, `background-motivation.tex`) overlap heavily and should be merged.
- Related work is improving but still mislabels some tools (e.g., Pensieve/LCM described as if simulator-based). Tighten the RTL vs. abstract-model vs. simulator taxonomy — that taxonomy is your positioning, so make it crisp.
- Section/subsection titles ("SimSpect Approach") are generic; align them with the numbered contributions in the intro.
- Figure 1 (STT Recon example) is dense and underexplained in text; walk the reader through it.
- State the instruction bound, test counts, and which gem5 builds you ran in numbers, not prose.

## Recommendation
**Weak Reject.** Confidence: **3**.

A strong, novel idea with real impact potential, but as submitted it overclaims, presents no results, and is visibly unfinished. With a concrete bug-finding result and a scoped "comprehensive" claim, this would be a clear accept.
