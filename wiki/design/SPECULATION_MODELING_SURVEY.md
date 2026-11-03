# Survey: how prior work models speculation and leakage

Started 2026-11-02 (paper-figs session) to replace an earlier agent survey that was never saved to disk. Living doc: fill rows as papers are read. **Rule:** a cell is filled only from a source actually read (cite section/page); otherwise it says *to read*. Cells marked *(search summary)* come from a web-search summary and must be checked against the paper before use. Local PDFs: `~/Documents/quail/sources/papers/` and `paper_figures/reference_papers/` (PDFs gitignored).

## Questions asked of every paper

1. **Speculation model:** what executions are allowed (which instructions may run speculatively, under which predictions), and is it operational or axiomatic?
2. **Leakage model:** what counts as leaking: what the attacker observes (observation), and which instructions transmit (transmitters)?
3. **Secrets / protection:** what data is secret or protected, and how protection propagates.
4. **Use:** specification, verification (proof/model checking), testing (random or directed), or software analysis/repair.
5. **Level:** program/ISA, microarchitecture model, simulator, or RTL.
6. **Relation to SimSpect:** what we reuse, where we differ.

## Terminology anchors (see also the glossary in `paper_figures/FIGURES.md`)

- **Contracts with observation and execution clauses** *(search summary)*: introduced by Guarnieri, Köpf, Reineke, Vila, "Hardware-Software Contracts for Secure Speculation", IEEE S&P 2021; the clause names are used by Revizor (ASPLOS 2022): the observation clause says what each instruction exposes to the attacker; the execution clause says what speculation is allowed (e.g. CT-SEQ: observe load/store addresses and control flow, empty execution clause; MEM-COND: branches may mispredict). A CPU satisfies a contract if executions with equal contract traces are indistinguishable in hardware.
- **Anna (2026-11-02):** the observation clause is attacker-visible µarch state, not what is fundamentally leaked, so it is not SimSpect's transmitter function; "execution contract" is the established term for the allowed execution; naming SimSpect's transmitter component is open (see `URGENT_TODO.md`).

## Catalogue

| Work | Style | Speculation model | Leakage model | Secrets / protection | Use; level | Status / source |
|---|---|---|---|---|---|---|
| Guarnieri et al., HW/SW Contracts, S&P 2021 | operational contracts | execution clause / execution mode *(search summary)* | observation clause *(search summary)* | to read | specification; ISA-level contract vs µarch | to read: https://mguarnieri.github.io/publication/sp2021/sp2021.pdf |
| Revizor (Oleksenko et al.), ASPLOS 2022; Hide and Seek with Spectres, ASPLOS 2023 | operational contracts + model-based relational testing | execution clause, e.g. MEM-COND *(search summary)* | observation clause; hardware traces via L1D Prime+Probe *(search summary)* | to read | random testing of black-box CPUs | to read: arXiv 2105.06872, 2301.07642 |
| AMuLeT (Fu et al.), ASPLOS 2025 | contracts (Revizor's) + relational testing | to read | to read | to read | random testing of simulator defense prototypes (gem5); the work SimSpect compares against | to read: `quail/sources/papers/fu-2025-amulet.pdf` |
| LCM / Clou (Mosier, Lachnitt, Nemati, Trippel), ISCA 2022 | **axiomatic** hardware-software security contracts ("leakage containment models"), derived from axiomatic MCM vocabulary (abstract, §1) | uses a program's speculative semantics to reason about transient leakage (§1); covers out-of-order and multi-core execution (§1 contributions) | microarchitectural information flow via **xstate** and relations rfx/cox/frx/comx; leakage = µarch execution distinguishable from what the architecture implies (§1, §3); **transmitter taxonomy** by severity, focused on cache leakage (§1) | secrets reach transmitters; "access instructions" read secrets (§3.2.4, related work) | static analysis of programs (Clou finds Spectre bugs in crypto libraries) | read (abstract, §1, related work): `paper_figures/reference_papers/lcm_clou_isca22/` |
| CheckMate (Trippel et al.), MICRO 2018 | axiomatic µhb graphs (µspec) | µhb graphs over pipeline locations incl. speculative paths | exploit patterns as µhb subgraphs | to read | synthesis of exploit litmus tests; µarch model | to read: `quail/sources/papers/trippel-2018-checkmate.pdf` |
| TransForm (Hsiao, Trippel et al.), ISCA 2020 | axiomatic (transistency) | to read | to read | to read | litmus synthesis | to read: `paper_figures/reference_papers/transform_isca20/` |
| Serberus (Mosier et al.), S&P 2024 | to read | to read | to read | to read | compile-time Spectre protection for crypto code | to read: `quail/sources/papers/mosier-2024-serberus.pdf` |
| Protean (Mosier et al.), HPCA 2026 | to read | to read | to read | to read | to read | to read: `paper_figures/reference_papers/protean_hpca26/` |
| rtl2µspec (Hsiao et al.), MICRO 2021; RTL2MµPATH / SynthLC, MICRO 2024 | axiomatic models synthesized from RTL | to read | SynthLC: leakage signatures from µpaths (to read) | to read | synthesis from RTL | to read: `quail/sources/papers/hsiao-2021-rtl2uspec.pdf`, `hsiao-2024-rtl2mupath.pdf`; quail wiki `topics/hardware-security-verification/rtl2mupath.md` |
| Contract Shadow Logic (Tan et al.), 2024 | contracts checked on RTL | to read | to read | to read | RTL verification of secure speculation | to read: `quail/sources/papers/tan-2024-contract-shadow-logic.pdf`; quail wiki `contract-shadow-logic.md` |
| Pensieve (Yang et al.), ISCA 2023 | µarch modeling for security evaluation | to read | to read | to read | model checking of defenses at the µarch-model level | to read: `quail/sources/papers/yang-2023-pensieve.pdf`; quail wiki `pensieve.md` |
| CounterPoint (Lindsay et al.), ASPLOS 2026; Helium (Archer et al.), ISCA 2026 | to read | to read | to read | to read | to read | to read: `paper_figures/reference_papers/` |
| Spectector; Cauligi et al. speculative constant-time; InSpectre (cited by LCM §8) | operational semantics of speculation for programs | to read | to read | to read | program analysis | to read (cited in LCM related work) |
| Defense papers' own models: STT (MICRO 2019), SPT (MICRO 2021), Recon (2023), InvisiSpec (MICRO 2018), SpecLFB (2024), CleanupSpec (2019) | informal / prose threat models (what is speculative, what is protected, what transmits) | to read per paper | to read per paper | taint / visibility point (STT, SPT), invisible loads (InvisiSpec) | the source of SimSpect's per-defense specs (manual translation) | PDFs in `quail/sources/papers/` (yu-2019-stt, choudhary-2021-spt, aimoniotis-2023-recon, yan-2018-invisispec, cheng-2024-speclfb, saileshwar-2019-cleanupspec) |

## Where SimSpect sits (draft framing for Anna to check; Claude's reading, not a source)

- Like LCM and CheckMate, SimSpect is **axiomatic** (Alloy over execution graphs with rf/ddi relations), but each defense is a three-part spec: execution contract (what is speculative), protection set (what is secret and how protection propagates), transmitter function (what can transmit).
- Like Revizor and AMuLeT, SimSpect **tests implementations**, but with **directed, enumerated** tests (minimal leaking execution graphs) instead of random programs, and it checks a defense's **own** guarantee rather than a generic contract.
- The target is **simulator prototypes** (gem5), between RTL-level work (Contract Shadow Logic, RTL2MµPATH) and program-level analysis (LCM/Clou, Serberus).

## Next steps (low usage)

- Read each paper's model section only (not the whole paper) and fill its row with section/page cites; start with Guarnieri S&P'21, Revizor, AMuLeT (closest to SimSpect's framing), then CheckMate and Pensieve.
- Pull the related-work paragraph for the paper from this table once the first five rows are filled.
