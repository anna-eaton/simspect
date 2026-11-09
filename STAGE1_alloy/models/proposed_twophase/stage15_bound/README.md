# stage15_bound — Stage 1.5 at larger bounds and with looser pins (stage15-bound session, 2026-11-08)

Scratch/draft tooling for Anna's question "can Stage 1.5 have a looser skeleton with more instructions?". Write-up and numbers: `wiki/design/TWO_PHASE_MODELS.md`, section "Stage 1.5: looser skeleton and larger bounds (2026-11-08)". Nothing here edits an existing `.als`; every model is generated as a new file.

## Files

- `make_s15_model.py`: builds one Stage-1.5 model from a production model plus one Stage-1 core. Only scope-tied edits: `exactly N Instruction`, optional `K Operand` / `S State`, IX symmetry-breaking regenerated for N positions (or dropped), the protection-set fold `last_committed_protset_p` regenerated N deep when N > 7. Pins: `a` (production `stage_seed.py`), `b` (path pin: each core rf edge may be subdivided, `ob in oa.rf.*(ddi.rf)`), `c` (leak pin: transmitter kind + an unresolved branch of the core's kind before it), `none`. Minimality: `prod` (production `gen_useful_litmus`), `leak_rs` (leak + RS only), `leak`. Queries: `splice_xm`, `fold_trunc`, `s4_shape`, `a3c_shape` (the last two verbatim from `proposed/STT_6_s4.als` and `proposed/STT_6_a3c.als`). See its docstring.
- `a6Bench.java`: the production solver settings (SAT4J, symmetry 80) plus timing: parse, Kodkod translation, CNF size, time to first instance, instances in a fixed window, peak JVM heap. Build: `javac -cp ../../../alloy6.jar:. a6Bench.java` (ASCII source).
- `bench_grid.py`: the measurement grid (sets `main`, `queries`, `shapes`, `minimality`, `extra`), resumable, logs to `<ws>/bench/bench.log`, one JSON line per job in `<ws>/bench/results.jsonl`, the exact model of every job in `<ws>/bench/models/`.
- `census.py`: shape census of the first 300 dumped instances of each job (operands, states, Reg_s, unresolved branches, spacer branches, ALU on the transmitter path).
- `xmlgen.sh` + `stage2_check.py`: enumerate 100 XMLs from a few seeded models at N = 6/10/12 with the production driver `a6CountModels`, then run Stage 2 unchanged (`batch_generate.py` both modes, plain and fanout v2 from `specs/fanout/stt.json`, then `compile_annotate.py`).
- `cores/`: the six Stage-1 RI-only cores used (copied read-only from simspect-c8's cafe2 run `/tests/simspect_alloy_20261108/out/<family>/<partition>/stage1_xml/`; file name = `<family>__<partition>_<inst>.txt`).
- `results/`: copies of `results.jsonl`, `census.json`, `stage2_summary.json` and `bench.log` from the cafe2 run.

## Where it ran

cafe2 `gem5_dev` container, workspace `/tests/stage15_bound_20261108/` (tmux session `stage15_bound`), 6 Java processes at a time, `-Xmx16g`, 1500 s hard timeout per job, under holder job 18374614. The workspace holds copies of `STT_6.als` (sha256 `7a6ac4c0…`), `Recon_6.als` (`01252c82…`), `SPT_6_oneLP_v2.als` (`acb1f2e2…`), `stage_seed.py` (`f796ba7c…`) and the repo's `STAGE2_compilation/` from this Mac. Re-run: `python3 STAGE1_alloy/models/proposed_twophase/stage15_bound/bench_grid.py --ws <ws> --set main --jobs 6` (then `queries`, `shapes`, `minimality`, `extra`).
