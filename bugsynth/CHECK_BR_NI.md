# `check_br_ni.py` — a general non-interference branch-channel checker (mainline candidate)

*The proposed replacement for the heuristic `check_br.py` (decision #3 in `FINDINGS_SUMMARY.md`,
design in `BRANCH_CHANNEL_CHECK_DESIGN.md`). Consolidates the two bugsynth prototypes
(`check_br_differential.py` + `stt_branch_soundness_audit.py`) into ONE general tool that runs on any
branch testset/model. Isolated under `bugsynth/`; nothing in the live pipeline is touched.*

## Why this exists (the check_br problem, restated)
`check_br.py` flags a branch "leak" whenever the transmitter branch redirects inside the speculative
window. But under a sweep stall STT *legitimately delays a TAINTED branch's squash to window-close* —
which `check_br` miscounts as a leak. That is the entire source of the historical STT br_x "leaks"
(`project_stt_branch_leak_cause`): they are tainted-branch redirects that STT is *supposed* to delay,
not information escaping. A redirect heuristic structurally cannot tell "the defense delaying a secret
branch" from "a secret reaching a public observable." Non-interference can.

## The frame (non-interference, value-flip, with a positive control)
Vary the secret and ask whether any **public, attacker-timeable** observable moves.

- **Secret parameterization — VALUE-FLIP (faithful).** Same binary; rewrite the prologue
  `movq $0, N(%rsp)` → `movq $1, N(%rsp)` so every speculative load returns the secret. A load-fed
  (tainted) branch's *direction* flips; a constant-fed (untainted) branch is unaffected. (This is the
  faithful test that retracted the pending-squash taint-flip reproduction — see
  `PENDING_SQUASH_BUG_REVIEW.md`.)

- **Public observable** = the full fetch-redirect **timeline** (sorted multiset of every squash-broadcast
  tick) **+** every **UNTAINTED** branch's `(made_pending, squash_tick)`. A *tainted* branch's own squash
  is **excluded** from the leak observable — STT may delay it, and that delay is the defense, not a leak.
  The timeline covers branch-channel types **A** (direct-direction), **B** (cross-branch redirect-timing,
  e.g. nmosier pending-squash) and **C** (squash-order); the per-branch projection localizes A/B.

- **Liveness = a scheme-0 (Unsafe) POSITIVE CONTROL.** A SOUND verdict is only meaningful if the secret
  *could* have reached a public observable. In a litmus test the secret only affects the **speculative
  (squashed, never-committed)** path, so the *committed* stream is secret-invariant by construction —
  committed-stream divergence is the **wrong** gate (it marks everything vacuous; verified). Instead we
  run the SAME gadget **unprotected (scheme 0)**: if the public observable (here including the tainted
  branch, since unprotected there is no defense) **moves** with the secret, the channel provably exists.
  Then we ask whether scheme 2 closes it.

### Verdicts
| verdict | condition | meaning |
|---|---|---|
| **SOUND** | live (scheme-0 control moves) **and** scheme-2 public observable INVARIANT | STT closes the channel |
| **LEAK** | live **and** scheme-2 public observable MOVES with the secret | real branch leak under STT |
| **VACUOUS** | scheme-0 control does NOT move | at this stall the secret never reaches a public observable — uninformative, excluded from the score |

The report also prints, per gadget, `scheme2_any_moves(old_check_br)` = whether ANY branch (incl. tainted)
moved under STT — i.e. **what the old `check_br` heuristic would have flagged**. The gap between that and
the taint-gated `LEAK` count is exactly the historical STT br_x false-positive set.

## Usage
```bash
# canonical base STT_6 br_x gadgets (default), /work/stt scheme 2, all gadgets:
python3 bugsynth/check_br_ni.py --model STT_6 --stall 2000
python3 bugsynth/check_br_ni.py --model STT_6 -n 20            # sample first 20
python3 bugsynth/check_br_ni.py --model STT_6_pendsquash       # the synthetic pendsquash gadgets
```
5 gem5 runs per gadget (scheme0×{0,1}, scheme2×{0,1}, +1 self-consistency). Self-consistency (scheme-2
secret-0 run repeated) must reproduce identical observables — guards against measurement noise.

## Result on the canonical base STT_6 br_x gadgets (2026-06-09) — DEFINITIVE
Full sweep, all **73** br_x gadgets of the canonical base `STT_6` testset, `/work/stt` scheme 2,
stall 2000 (log: `/tmp/ni_base_stt6.log`):

```
42/42 LIVE gadgets SOUND,  0/42 LEAK   (31 vacuous, 0 err)
OLD check_br would flag 42/42  — the 42 extra are tainted-branch squashes STT legitimately delays
self-consistency failures (A vs A moved): 0
```

**The headline:** of the 42 gadgets that form a live channel (scheme-0 control moves with the secret),
**every single one is SOUND** under STT — the public observable is secret-invariant — and **every single
one would have been flagged a "leak" by the old `check_br` heuristic** (`old_check_br=1` on all 42, because
the tainted transmitter branch's squash moves, which is exactly what STT is *supposed* to delay). So on the
**native** STT_6 br_x testset:

- **0 real branch leaks** under STT (non-interference: no public observable moves with the secret).
- **42 old-check_br false positives** — i.e. the *entire* historical STT br_x "leak" signal
  (`project_stt_branch_leak_cause`) is check_br artifact, now confirmed on the canonical gadgets, not just
  the synthetic pendsquash ones.
- **0 self-consistency failures** (measurement is noise-free) and **0 errors**.
- 31 VACUOUS = at stall 2000 the secret branch is squashed before it resolves → no public observable either
  way (not all gadgets form a live channel at a fixed stall; a stall sweep would convert some — future work).

This is the definitive, faithful confirmation that STT's branch implicit-channel defense is sound on its
own canonical transmitter-branch gadgets, and the precise quantification of how badly the redirect-based
`check_br` over-reports (42/42 of the live cases).

## Stall-sweep (`--sweep` / `--stalls`) and the structural-vacuity finding (2026-06-09)
Added a stall-sweep: `--sweep` retries each gadget across a band `[500,2000,2500,5000]` (or `--stalls a,b,c`),
taking the **first stall that makes the gadget live** (cheap: the scheme-0 control runs first; the scheme-2
runs only happen once a stall makes it live). Purpose: a gadget VACUOUS at one stall might form a live
channel at another.

Result on the 31 stall-2000-vacuous gadgets: **0/31 became live** across the whole band (log
`/tmp/ni_sweep_vac.log`). So these 31 are **structurally vacuous**, not a stall artifact — the secret never
reaches a public observable in *any* stall regime (their transmitter branch's squash behavior is
secret-independent at every stall). The live set is therefore a genuine **42/73**, and the audit conclusion
is unchanged and robust: **42/42 live → SOUND, 0 LEAK.** (A per-gadget mechanism trace of why each is
structurally vacuous is possible but unnecessary for the soundness conclusion.)

## Pipeline integration — `br_ni_audit.py` (DONE, audit-pass form)
The NI verdict is now consumable by the existing results/diagnostics tooling via **`br_ni_audit.py`**, a
SEPARATE consumer (like `results/_sweep_watcher.py` / `testrun.py`) — **not** an edit to `pipeline.py`. It
imports `check_br_ni.audit_gadget` and writes, per mode:
- `results/<name>_ni/<mode>/window-results.json` — standard schema: `{name, status, issued_in_window}`
  with `issued_in_window = (verdict=="LEAK")`, `status ∈ leak|safe|vacuous` (+ a `vacuous` flag so the
  uninformative no-channel gadgets are excluded from the score).
- `ni_audit.json` (full per-gadget detail) + `manifest.json` (build/scheme/stalls/counts).

**Why a separate pass, not a per-test `_KIND_TO_CHECKER` fold:** the NI verdict needs **5 gem5 runs per
gadget** (value-flip × {scheme-0 control, scheme-2} + self-check), so folding it into every routine br_x
sweep would 5× their gem5 cost. The audit pass keeps the fast `check_br.py` for routine sweeps and runs the
rigorous NI audit on demand, while still emitting the standard schema. Verified end-to-end on STT_6.

```bash
python3 bugsynth/br_ni_audit.py --model STT_6 --sweep            # full br_x NI audit → window-results.json
```

## Remaining (the ONLY owner-gated item)
- **Optional per-test fold into the live `pipeline.py`** (`_KIND_TO_CHECKER['br_x']`). NOT applied — it
  edits mainline AND imposes the 5× cost on every sweep, so the audit-pass above is the recommended form.
  If you still want the per-test fold, the one-line change is:
  ```python
  # pipeline.py:  _KIND_TO_CHECKER = {... 'br_x': 'check_br.py' ...}
  #            →  'br_x': 'check_br_ni.py'    # (requires a single-test CLI shim + accepting the 5× cost)
  ```
- Channel **E** (window-modulation) would need one more observable projection; the timeline already captures
  it partially. Channel **D** (implicit flow) is closed with evidence — see `CHANNEL_D_DESIGN.md`.
