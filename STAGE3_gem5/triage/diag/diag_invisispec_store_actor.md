# diag_invisispec_store_actor: Futuristic actor counts store micro-ops (checker artifact)

**Issue and signature.** On InvisiSpec Futuristic, every offending footprint event of the hit belongs to a store micro-op: the event's `req` is `st`, or its seq's micro-op (from the O3PipeView fetch line) is a store (`st`, `stis`, ...). The Futuristic actor does not filter for loads, and a store writes after it commits, which is normal. Evidence: `invisispec_evidence.json` from `rerun_hits_evidence.py --analyzer invisispec`; the faithful rerun must hit with the campaign's offending (struct, kinds) signature.

**Evidence.** `wiki/findings/audits/2026-10-28/invisispec_flagged_events_triage.md` §2 (seq 3 = `CALL_NEAR_I : stis`, seq 25 = `PUSH_R : stis`; seq 532 = `MOV_M_I` store, L1D fill and DIR coh are a normal post-commit write): CHECKER ARTIFACT. 2026-11-09 sample (E12a fv2fp, 24 hits): the 2 non-UV1 hits had only `req=st` events plus DTLB events of seq 3.

**Verdict.** Checker artifact, not a leak (disqualifier). Scope: InvisiSpec Futuristic campaigns only (E12a).

**Scope revised 2026-11-09.** Applied on both InvisiSpec schemes (E12a and E12b): the fv2 2% reruns show `req=st` store-micro-op events on the Spectre scheme too, by the same mechanism (no pipeview record, so the visibility point is infinite).
