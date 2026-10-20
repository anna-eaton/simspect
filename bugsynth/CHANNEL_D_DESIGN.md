# Channel D — implicit-flow branch channel: design, soundness argument, and a VERIFIED result

*Remaining item #2 of the robust-branch-checker work (`FINDINGS_SUMMARY.md` / `CHECK_BR_NI.md`). This
closes channel D **conceptually with evidence** (a run, not a hand-wave), the same standard used to retract
pending-squash and confirm STT's branch defense. Isolated under `bugsynth/`; mainline untouched.*

## What channel D is
Channels A/B/C are about a **branch's own** redirect (direction / timing / squash-order) — the transmitter
*is* the branch, and `check_br_ni.py` already audits them (the timeline + untainted-branch projection).
**Channel D is implicit flow:** the transmitter is a **separate, PUBLIC instruction** (e.g. a load whose
**address is untainted**) whose execution is **control-dependent** on a secret branch. STT tracks *explicit
data flow* (it protects a load iff its address is tainted), so a public-address load is **not protected** —
the worry is that the secret leaks *implicitly*, through whether/when that public load runs.

```
   pc1: movq (-8(%rsp)), %rax              # secret load (tainted)
   pc5: movq %rax,%rcx; testq %rcx,%rcx; je .end   # SECRET-dependent branch
   pc6: leaq -16(%rsp),%r11; movq (%r11),%r11      # PUBLIC load, CONSTANT addr, gated by pc5  (transmitter)
```

## The gadget + probe (this directory)
`channel_d/inst-cd-001.s` is the gadget above, built by converting base STT_6 `inst-000012`'s `pc6` `nop`
into a public RSP-relative load (untainted address) and adding a public init slot. `channel_d/channel_d_probe.py`
runs the **non-interference** test: VALUE-FLIP the in-memory secret (0 vs 1) on one binary, observable = the
pc6 load's first cache-touch tick (`execute_tick`/`packet_tick` from `parse_lsq`), under scheme 0 (Unsafe
positive control) and scheme 2 (STT).

## VERIFIED result (2026-06-09, /work/stt, stall 2000)
```
scheme0 (Unsafe, control): secret0 pc6=(exec=199000,pkt=199000)  secret1 pc6=(exec=199000,pkt=199000) -> INVARIANT
scheme2 (STT):             secret0 pc6=(exec=199000,pkt=199000)  secret1 pc6=(exec=199000,pkt=199000) -> INVARIANT
```
The public load's cache access is **secret-invariant even UNPROTECTED (scheme 0)**. So this single-level
implicit gadget forms **no channel at all** — there is nothing for STT to defend, and STT is (trivially) not
the weak point.

## Why — the soundness argument (and what it does NOT cover)
The speculative path is **determined by the branch PREDICTOR, not by the secret.** pc6 is fetched/executed
speculatively (or not) according to how pc5 is *predicted*, which is secret-independent. The secret only
decides whether that speculative execution is later **squashed (secret 0) or committed (secret 1)** — but the
**first cache access already happened** at the same tick either way (199000). A squash-after-access does not
un-touch the cache, and a commit-after-access does not move the access earlier. Hence first-access timing is
invariant: **a single-level implicit branch→public-load gadget cannot leak through the public load's
speculative cache access.** STT's *data-flow* tracking is therefore not unsound here — the absence of a leak
is structural, upstream of the defense.

**Residual risk (the real channel-D, = the coincidence wall).** An implicit channel needs the **secret to
determine WHICH speculative path runs**, not merely whether it is later squashed. That requires the secret
branch to be **mispredicted in a secret-dependent way while itself speculative** — i.e. nested speculation
where the secret steers a younger transmitter's fetch. That is exactly the **secret-dependent-misprediction
coincidence** characterized as structurally blocked in the litmus framework for pending-squash
(`FINDINGS_SUMMARY.md` Q1): bo-taint needs a window-defining older branch, which fixes the resolution tick
independent of the secret. So the only way channel D leaks is via the same coincidence the litmus framework
can't construct — and if it *could* be constructed, `check_br_ni.py`'s observable (the public load's access
tick / the redirect timeline) would already catch it (the probe here is precisely that observable, just
projected onto a load instead of a branch).

## Verdict
- **Single-level implicit-flow (this gadget): NO leak, NO STT unsoundness** — verified, secret-invariant
  even unprotected; the speculative path is predictor-determined.
- **True implicit-flow (secret-steered speculative path): reduces to the pending-squash coincidence**, which
  is structurally blocked in the litmus framework; `check_br_ni.py` already projects the observable that
  would detect it if a deeper-pipeline gadget were built.
- **Channel-D tooling now exists** (`channel_d_probe.py` — a load-cache-access non-interference observable),
  reusable the moment a secret-steered gadget is available.

## To fully discharge channel D in the checker (remaining)
Fold the load-access observable into `check_br_ni.py` as a third projection (`_ld_access_obs`) so a br_x
testset that also carries a downstream public load is audited for implicit flow in the same pass. Low effort;
deferred with the pipeline-fold decision (#1) since it shares the per-test plumbing.
