# Criteria provenance audit: invisispec / speclfb / cleanupspec leakage specs (2026-10-28)

Audit only. No spec or doc was edited. Audited files: `specs/leakage/invisispec.json`, `specs/leakage/speclfb.json`, `specs/leakage/cleanupspec.json`. Every quote in `source.claims`, `out_of_scope[].claim`, `not_covered[].claim` and the quoted bits of `amulet_checks` / `by_design` was searched in the cited PDF in `~/Documents/quail/sources/papers/`, one page at a time (`pdftotext -f N -l N`, whitespace and line-break hyphens normalized, then fragment-by-fragment search with `…` / `[...]` as splice points). Two-column PDFs interleave lines in pdftotext output, so every first-pass miss was re-checked by hand with `grep` context. Method script: the scratchpad `chk.py` (not kept in the repo).

**Bottom line.** 39 quoted items checked (13 InvisiSpec, 10 SpecLFB, 16 CleanupSpec). 38 are VERIFIED on the cited page; several needed a manual check because of column interleaving, and one InvisiSpec splice has its fragments in reverse order. The remaining 1 is a paraphrase stored in a `quote` field (SpecLFB MUSL). No WRONG PAGE and no fabricated quotes. SpecLFB's "printed page = PDF page + 629" mapping holds for every SpecLFB citation. The main substantive findings are about what `observation` leaves out (CleanupSpec's "allowed and reversed" coherence/directory promise, U2; InvisiSpec page-table A/D bits, U1), not about the quotes themselves.

## InvisiSpec (`yan-2018-invisispec.pdf`, PDF pages; original MICRO copy where cited)

| # | Field / section | Cited page | Verdict | Note |
|---|---|---|---|---|
| 1 | claims §III-B Channels Protected | p3 | VERIFIED | Verbatim on p3 of both versions. |
| 2 | claims §V-B "USLs do not modify the cache coherence states…" | p5 | VERIFIED | Verbatim on p5 (split by column interleave), under "B. InvisiSpec Operation". |
| 3 | claims §VI-E1 Spec-GetS | p9 | VERIFIED (splice order reversed) | Both fragments are on p9 under "E. Other Implementation Aspects / 1) Changes to the Coherence Protocol". In the paper "without changing any cache or coherence states" comes first (describing the Spec-GetS transaction) and "a Spec-GetS obtains the line from the directory if the directory owns it" follows as the example. The quote's `A … B` order puts them backwards. The meaning survives, but the splice should be reordered. |
| 4 | claims §VI-E3 D-TLB | p9 | VERIFIED | p9 "3) Securing the D-TLB". See under-claim U1 below: the quote stops at the miss half. |
| 5 | claims §IV "[…] will make all the side effects of the USL in the memory hierarchy apparent" | p4 | VERIFIED | p4: "InvisiSpec takes an action that will make the USL visible—i.e., will make all the side effects of the USL in the memory hierarchy apparent to all other threads." The bracket is a fair paraphrase, since the next sentence says the action is re-loading the data (validation/exposure). |
| 6 | claims §IV-A1 Spectre-model USLs | p4 | VERIFIED | Verbatim. |
| 7 | claims §IV-A1 Futuristic-model USLs | p4 | VERIFIED | Verbatim (the first pass missed it only because "(i)" sits on its own line). |
| 8 | claims §V visibility point | p5 | VERIFIED | Verbatim on p5 (column interleave). |
| 9 | out_of_scope footnote 2 (L1I/ITLB) | p3 | VERIFIED | Verbatim. |
| 10 | out_of_scope §VII MSHR contention | p10 (original) | VERIFIED | Original p10, "VII. Security Analysis / A. Proof-of-Concept Defense Analysis". The same sentence is also on p10 of the corrected version, so the citation could point at the main paper. |
| 11 | out_of_scope §III "We also do not protect microarchitectural channels other than those listed above" | p3 | VERIFIED | Verbatim. The same paragraph also says "Physical side channels (e.g., power [19] or EM [20]) are out of scope". NoC, DRAM and SMT are not named in the paper; they come in only through this catch-all. |
| 12 | amulet_checks "For InvisiSpec and STT, we run them in their Futuristic mode" | AMuLeT p8 | VERIFIED | `fu-2025-amulet.pdf` p8. |
| 13 | amulet_checks "as the TLB is not protected" (1-page sandbox) | AMuLeT p7 | VERIFIED, context note | p7: "For InvisiSpec, CleanupSpec, and SpecLFB, we use a sandbox with 1 physical page (as the TLB is not protected)". This conflicts with the InvisiSpec paper itself, which claims D-TLB protection (§VI-E3 p9). AMuLeT's 1-page sandbox means it never really tests InvisiSpec's D-TLB claim. `never_observed` could list DTLB for that reason. |

**Observation vs. quotes (InvisiSpec).** `structures` = L1D/L2/DIR/DTLB and `state` = presence/replacement/coherence follow directly from §III-B (any level of the data cache hierarchy, plus occupancy, replacement, coherence and data-TLB state). The ignored MSHR/TBE structures match the MSHR out-of-scope quote (#10), and ignoring L1I/ITLB matches footnote 2. SB/LLC-SB as allowed buffers matches the design.

- **U1 (small under-claim): page-table access/dirty bits.** The p9 to p10 continuation of §VI-E3 reads: "Second, on a D-TLB hit, any observable TLB state changes such as updating D-TLB replacement state or access/dirty bits are delayed to the USL's point of visibility." The spec quotes only the miss half, but most of the hit half is still covered. `wiki/design/SIMSPECT_HOOKS.md` line 51 shows DTLB emits `repl_touch` (`TLB::lookup` with LRU update), and both DTLB and `repl_touch` are in OBS / `terms.footprint.kinds`. What is left is the page-table access/dirty-bit update, which is not in `observation`. Recommendation: quote the hit half too, and list "page-table A/D bits" under `not_covered`.
- Nothing is over-claimed. DIR rests on the coherence-information part of §III-B plus #3.

## SpecLFB (`cheng-2024-speclfb.pdf`; printed page = PDF page + 629, holds for all citations)

| # | Field / section | Cited (printed) | PDF page | Verdict | Note |
|---|---|---|---|---|---|
| 1 | claims §1 LFB check / "both cache levels of X86 O3 CPU model in Gem5" | p632 | 3 | VERIFIED | Both fragments are on p3. The bracketed lead-in is a paraphrase. |
| 2 | claims §7 "SpecLFB is applied to both levels of the cache…" | p640 | 11 | VERIFIED | Verbatim. |
| 3 | claims §4 threat model "flush- and conflict-based…" | p635 | 6 | VERIFIED | Verbatim (the PDF line-breaks "side-channel"). |
| 4 | claims §5 "the speculative loads causing cache misses are considered unsafe…" | p635 | 6 | VERIFIED | Verbatim. |
| 5 | claims §6.1 "Only when the security check mechanism determines that it is safe…" | p637 | 8 | VERIFIED | Verbatim. |
| 6 | claims §5 "MUSL = an unsafe speculative load that causes cache miss; control-flow MUSLs are safe if…" | p635-638 | 7, 9 | NOT FOUND as verbatim (paraphrase in a `quote` field); substance VERIFIED | The definition is at printed p636 (PDF 7): "denote an unsafe speculative load that causes cache miss". The control-flow condition is at printed p638 (PDF 9): "if there are no older control instructions that are unresolved before the instructions, the b_ij of the instruction…". The field should be marked as a paraphrase or replaced with the two real quotes and their exact pages (636, 638). |
| 7 | out_of_scope §9 cache hits / metadata | p643 | 14 | VERIFIED | Both fragments verbatim. |
| 8 | out_of_scope §4 "We do not consider other speculative side channels, such as TLB…, port contention…" | p635 | 6 | VERIFIED | Verbatim. |
| 9 | out_of_scope §6 VP remark | p637 | 8 | VERIFIED | Verbatim. |
| 10 | amulet_checks "CT-SEQ (AMuLeT §4.7 p12)" | AMuLeT p12 | 12 | VERIFIED | p12: "we tested SpecLFB's gem5 implementation against the CT-SEQ…". |

**Observation vs. quotes (SpecLFB).** L1D+L2 follows from #1 and #2. `state` = presence follows from the flush/conflict threat model (#3). Leaving out `repl_touch` matches #7 (hits and metadata are out of scope). Ignoring DTLB matches #8. LFB as the allowed structure matches #5. The memory-order/exception and VP MUSLs are correctly in `not_covered` / `out_of_scope`.

- **Minor (unattested inference):** the out_of_scope item text "(incl. L1I, not claimed)" is not backed by the quote. The paper's cited text never names L1I. The inference is reasonable (the paper's scope is L1D and the data caches), but it should be labelled as an inference.
- Nothing is over-claimed, and nothing the paper promises is missing.

## CleanupSpec (`saileshwar-2019-cleanupspec.pdf`, PDF pages)

| # | Field / section | Cited page | Verdict | Note |
|---|---|---|---|---|
| 1 | claims §1 randomization + L1 rollback + L2 invalidate | p2 | VERIFIED | All three fragments are on p2. |
| 2 | claims §1 random replacement / coherence delay | p2 | VERIFIED | Verbatim. |
| 3 | claims §2.1 data-cache hierarchy + installs/evictions/replacement/coherence | p3 | VERIFIED | All fragments are on p3. |
| 4 | claims §2.1 "We deem all transient instructions potentially 'unsafe' until they retire" | p3 | VERIFIED | Verbatim. |
| 5 | claims §3.3-3.4 "any cache changes like install and victim replacement are made only when a load returns and is for the current EpochID" | p6 | VERIFIED | Verbatim. |
| 6 | claims §3.4 non-squashed older loads preserved / "invalidations / restorations are skipped" | p7 | VERIFIED | Both fragments are on p7. |
| 7 | claims §1 "the perceived cache state after these operations is as if the transient loads did not access the cache" | p2 | VERIFIED | Verbatim. |
| 8 | by_design "as L2/LLC evictions leak no information" | p2 | VERIFIED | p2. |
| 9 | by_design §3.2 "replacement state updates for both L1 and L2 caches leak no information" | p6 | VERIFIED | p6. |
| 10 | by_design "(and for the directory [61])" | p2 | VERIFIED | p2. |
| 11 | not_covered §4(b) unXpec / constant-time cleanup as future work | p8 | VERIFIED | Both fragments are on p8. |
| 12 | not_covered §3.5 "allowed and reversed" | p7 | VERIFIED, see U2 | p7: "transient changes like I -> E or adding S-sharers (even in remote directories), that do not affect the state of a line cached by a remote core, are allowed and reversed." |
| 13 | out_of_scope p1 footnote (I-Cache, TLB, Branch Predictor, port contention) | p1, p3 | VERIFIED | The whole quote is on p1 (footnote). p3 is not needed for this text. |
| 14 | out_of_scope §2.1 AVX / prefetch / close-page / SMT port, NoC, DRAM, EM/power | p3 | VERIFIED | All five fragments are on p3. |
| 15 | out_of_scope §3.6 "that is anyway required for preventing non-speculative L1 cache side-channel attacks" | p8 | VERIFIED | p8. Context: "For SMT adversary, a mitigation like way-partitioned L1 cache (e.g. NoMo [14]), that is anyway required…". |
| 16 | amulet_checks CT-SEQ §3.1 p5; unXpec (KV2) only via L1I p12 | AMuLeT p5, p12 | VERIFIED | p5 line lists the CT-SEQ contract. p12 KV2 shows it was found "in campaigns where we included the L1I-cache state". |

**Observation vs. quotes (CleanupSpec).** L1D+L2 with undo obligations L1D{install, victim} and L2{install} follow exactly from #1. Presence-only state, with replacement handled by design, follows from #2 and #9. Not restoring L2 victims follows from #8.

- **U2 (under-claim relative to the paper): reversal of coherence/directory changes.** The §3.5 p7 text (#12) does not only say these changes are "allowed". It says I→E transitions and added S-sharers, "even in remote directories", are allowed **and reversed**. That is a cleanup promise, and it applies in single-core runs too: this core's own I→E and sharer-list changes at its L2/directory. The spec cites the sentence only in `not_covered` (about remote cores), ignores DIR, and has no DIR/coherence undo obligation. So an implementation that fails to reverse a speculative I→E or sharer addition would not be flagged. This follows Anna's 2026-10-28 scope decision (L1D + L2), so it is not an error in the spec. But the spec should say explicitly that the paper promises this reversal and that it is deliberately unchecked, rather than implying it is only a remote-core concern. The by_design entry "directory randomized; DIR not observed" also claims more than its quote: randomizing the directory (#10) covers directory conflict evictions, not the I→E / S-sharer reversal promise.
- **Minor:** item #2's coherence-delay mechanism (M/E→S delayed until unsquashable) is an active mechanism, not a "leaks nothing by design" property. In single-core runs it only concerns remote-core lines, which is why `not_covered` is right to list it.
- Nothing is over-claimed.

## Not checked (out of time box / not in PDFs)

- The AMuLeT *code* references in `amulet_checks` (`executor.py:…`, `docker_gem5_v1_final_cache_and_tlb.yaml:60`, `ct-seq.yaml:75`, `cleanupspec_analysis.py:90-97`, `Scheme.py:76-82`) were not checked. They point to repo files, not PDFs.
- Section labels were spot-checked only (InvisiSpec §V-B, §VI-E1, §VI-E3 and §VII confirmed from headings). The SpecLFB and CleanupSpec section numbers were not checked against headings. Pages were checked for every quote.
- Apart from DTLB `repl_touch` (confirmed in SIMSPECT_HOOKS.md:51), whether the hooks actually emit every event the `observation` lists is a separate hook audit.
