# PC Discussion & Final Reviews — SimSpect: Automated Litmus Testing for Simulated Spectre Defenses

## PC Discussion

**Chair:** All three of you landed on Weak Reject, confidence 3. Let's find the real consensus, then the disagreements. Start with what's not in dispute.

**Reviewer B:** Three things are unanimous. (1) There are no empirical results — the "Preliminary Results" section is entirely future tense ("we will," "we are currently implementing"), reports zero leaks, zero test counts, no AMuLeT comparison. (2) "Comprehensive" is overclaimed — the paper itself concedes it's comprehensive over leakage-path backbones but heuristic in concretization and reliant on a separate interleave pass. (3) The draft is visibly unfinished: inline `\caroline{}` TODO macros, an empty `\cite{}` in the results section, duplicated Background sections. None of that is controversial.

**Reviewer C:** Agreed on all three. Where I want to push: is "no results yet" actually *fatal*, or is it expected for a mini-paper / WIP venue? YArch is exactly the kind of venue where a sharp idea with a credible plan can be accepted. The three-axis specification (leakage contract / execution contract / protection set) is genuinely novel and well-differentiated from AMuLeT's random fuzzing. I don't want us to reject a fresh idea purely for being early.

**Reviewer B:** I hear that, but "early" and "no validated oracle" are different problems. My decisive objection isn't the absence of a bug count — it's that the *ground truth itself is undemonstrated*. The whole method rests on gem5 being a trustworthy oracle, yet the leak criterion (transmitter acts inside the annotated window) gets one hand-wavy paragraph. Worse, the method *forces* µarch state — BTB directions, commit stalls. An over-tuned window can make a defended path appear to leak. Without a single negative control — a known-secure case that does *not* trip — I can't tell signal from artifact. That's not a "results will come" gap; it's a "I can't evaluate the core claim" gap.

**Reviewer A:** That connects to my central worry, which is sharper than "no results": the methodology may be *circular*. "Model–gem5 discrepancy = research signal" is only meaningful if the model is independently trusted. A discrepancy can mean (a) a real gem5 bug, (b) an over-/under-approximating Alloy model, (c) a concretization artifact, or (d) a checker false positive. The paper gives no protocol to discharge (b)–(d). So B's "artifact-vs-real-bug" concern and my "circularity" concern are the *same* concern viewed from two ends.

**Reviewer C:** I'll concede that. I came in treating "no results" as the main flaw and novelty as the offset. After hearing A and B, I think the deeper issue is that even *with* a result, the paper as written couldn't convince me the result is real, because there's no falsification protocol. That moves me — the fix isn't merely "add numbers," it's "add numbers *plus* a discharge procedure and a control." That's a higher bar, but it sharpens what an accept would require.

**Reviewer A:** Let me also push back on my *own* harshest framing. I asked for a soundness/completeness theorem. On reflection, that's miscalibrated for the stated scope: the authors explicitly position this as *validation, not verification* — test-suite-based bug-finding for early prototypes. Demanding a proof is the wrong bar; AMuLeT, the comparison point, proves nothing either. What I should demand is a *precise scoping of "comprehensive"* and one fully discharged discrepancy. So I'll soften the theorem ask but harden the "one worked end-to-end example" ask.

**Reviewer B:** That's where we converge. None of us needs a proof or ten bugs. We each need *one* concretely demonstrated discrepancy, root-caused, with the artifact-vs-real-bug verdict shown — and a negative control. That single deliverable answers A's circularity, my oracle-validity, and C's overclaiming all at once.

**Reviewer C:** And it's plausibly within reach — the paper name-drops a "known bug in STT Recon" it never demonstrates. Walk *that* end-to-end and the paper flips.

**Chair:** So: consensus to keep Weak Reject, but a single, shared, achievable bar to flip it. C sharpened (novelty no longer offsets evidence; the bar is result+discharge+control). A sharpened (drop the proof demand, keep the worked-example demand). B holds firm on the oracle.

## Final Reviews

### Reviewer A (formal-methods / modeling) — Final

The problem is real and the MCM/Alloy lineage (Lustig et al., lifted to speculative leakage) is a clean, defensible idea; the three-axis decomposition is intuitive. My core objection stands: the central methodology — "model–gem5 discrepancy = research signal" — is potentially circular, because a discrepancy can equally be a real gem5 bug, an over-/under-approximating Alloy model, a concretization artifact, or a checker false positive, and the paper offers no protocol to discharge the latter three.

The discussion changed two things for me. First, I withdraw my demand for a soundness/completeness *theorem*: the authors explicitly scope this as validation, not verification, and the comparison point (AMuLeT) proves nothing either, so a proof is the wrong bar. Second, B convinced me that my "circularity" concern and his "artifact-vs-real-bug" concern are the same concern — which means a single deliverable resolves both: one fully discharged discrepancy showing how (b)–(d) were ruled out before declaring a gem5 bug.

What I now require to accept: (1) precise scoping of "comprehensive" — over leakage-path backbones, *not* interleavings or concretizations, stated plainly; (2) one end-to-end discrepancy with its falsification protocol shown (e.g., the advertised STT/Recon bug); (3) finished prose — the empty `\cite{}` and inline TODO macros must go. The idea deserves to be in the program once it shows it can discharge its own central ambiguity even once.

**Recommendation: Weak Reject. Confidence: 3.**

### Reviewer B (practical / gem5-systems) — Final

Strong, well-motivated methodology; forcing µarch state rather than hoping speculation arises randomly is the right instinct, and the breadth of expressed defenses (eight) plus gem5 targets (STT/SPT/InvisiSpec/CleanupSpec/SpecLFB) signals real engineering. My decisive objections are unchanged by the discussion, and the discussion actually reinforced the most important one.

The paper has no empirical results, but that alone isn't why I hold. The deeper problem is that the *oracle is undemonstrated*: the leak criterion (transmitter inside the annotated window) gets one paragraph, with no account of how an in-window transmitter is shown to *actually obtain/leak data*, and no assurance that heavy instrumentation (forced BTB, commit stalls) doesn't itself manufacture or mask leaks. A's circularity point is the modeling-side mirror of this — together they mean a reported bug currently wouldn't be checkable, and reproducibility is nil (no gem5 commit, scheme flags, or artifact).

C's argument that novelty offsets the gaps did *not* move me, but the discussion did sharpen the ask into something concrete and shared: one demonstrated discrepancy, root-caused, with the artifact-vs-real-bug verdict explicit, *plus a negative control* (a known-secure path that does not trip). That single result would simultaneously validate the oracle, answer the circularity charge, and bound the "comprehensive" claim. It is plausibly within reach given the paper's own unshown "STT Recon" bug.

**Recommendation: Weak Reject. Confidence: 3.**

### Reviewer C (novelty / impact / writing) — Final

This is the freshest idea in my stack: directed, defense-specific litmus generation from an axiomatic spec, clearly differentiated from AMuLeT's random relational fuzzing, with an elegant three-axis specification framing. The problem — security (not functional) validation of early simulator defense prototypes whose bugs silently void published overheads — is real and under-served.

I came in weighting novelty as an offset for the missing evidence. The discussion changed that. A and B convinced me the gap is not merely "no numbers yet" but "no procedure to make any number believable": without a falsification protocol and a negative control, even a reported bug couldn't be trusted. So my bar for acceptance rose from "add a result" to "add a result *plus* show it survives discharge of model/concretization/checker artifacts." That's harder, but it's the right bar, and it's achievable.

My writing objections persist and compound the problem: "comprehensive" is asserted and internally contradicted (comprehensive over paths, heuristic over concretization, incomplete over interleavings) and must be scoped precisely; the two Background sections overlap and should merge; related work still mislabels some tools; terms (transmitter, backbone, skeleton, RI/RO/RS/RC/RR) outrun their definitions; and the draft carries visible TODO macros and an empty `\cite{}`. None of this is submission-ready.

With one concrete bug-finding result, a scoped "comprehensive" claim, and a cleanup pass, this is a clear accept. As submitted, it overclaims, shows nothing, and is unfinished.

**Recommendation: Weak Reject. Confidence: 3.**

## Meta-Review / Summary

All three reviewers converge on Weak Reject (confidence 3) and agree on the surface flaws: no empirical results, an overclaimed "comprehensive," and unfinished prose (TODO macros, empty `\cite{}`, duplicated Background). The discussion revealed these are symptoms of one root issue: the paper's central premise — "model–gem5 discrepancy = security signal" — is currently unverifiable, because there is no protocol to distinguish a real gem5 bug from a model over-approximation, concretization artifact, or checker false positive, and no validation that the forced µarch oracle doesn't manufacture leaks. A softened the proof demand; C raised the bar from "add numbers" to "add a discharged result"; B held firm on oracle validity. **The single most important thing to flip the decision:** present *one* end-to-end discrepancy (e.g., the unshown STT/Recon bug), fully root-caused with the artifact-vs-real-bug verdict shown, plus a negative control. **Disposition: Weak Reject**, with a clear, shared, achievable path to acceptance.
