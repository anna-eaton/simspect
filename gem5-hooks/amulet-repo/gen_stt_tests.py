#!/usr/bin/env python3
"""
Standalone generator for the STT fuzzing corpus, WITHOUT running gem5/STT.

Mirrors the CONF setup that `cli.py fuzz -s x86/isa_spec/base.json --STT
--STT_FuturisticSpec -c <docker_gem5_v1_final_cache_tlb.yaml>` would apply, then
just calls the test-case generator in a loop and writes each program to disk.
The gem5 executor is never invoked (we only construct it to read its fixed
sandbox/code base address constants, which the model needs).

Usage:
  python gen_stt_tests.py -c <yaml> -n <num> --out <dir> [--gen-seed N]
"""
import os
import sys
import argparse
from pathlib import Path
import yaml

from config import CONF
from service import LOGGER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--instruction-set", default="x86/isa_spec/base.json")
    ap.add_argument("-c", "--config", required=True)
    ap.add_argument("-n", "--num-test-cases", type=int, default=10)
    ap.add_argument("--gen-seed", type=int, default=0,
                    help="generator seed (0 = nondeterministic, as the campaign used)")
    ap.add_argument("--out", required=True, help="output dir for .asm test cases")
    args = ap.parse_args()

    # --- replicate cli.py CONF setup (STT campaign) ---
    CONF.config_path = args.config
    with open(args.config) as f:
        for var, value in (yaml.safe_load(f) or {}).items():
            CONF.set(var, value)

    # STT campaign flags (executor selection only; generation is unaffected by
    # which defense build runs, but set them so CONF matches the real run)
    CONF.set("STT", True)
    CONF.set("STT_FuturisticSpec", True)

    if args.gen_seed:
        CONF.set("test_case_generator_seed", args.gen_seed)

    # debug_dir / test_case scaffolding that downstream code expects
    CONF.set("test_case", "gen")
    Path(f"{CONF.debug_dir}/{CONF.test_case}").mkdir(parents=True, exist_ok=True)
    CONF.sanity_check()
    LOGGER.set_logging_modes()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # --- build only the generator (no executor/model needed for generation) ---
    from isa_loader import InstructionSet
    from generator import get_generator

    iset = InstructionSet(args.instruction_set, CONF.supported_categories)
    gen = get_generator(iset)

    print(f"seed={CONF.test_case_generator_seed} clause={CONF.contract_execution_clause} "
          f"obs={CONF.contract_observation_clause} size={CONF.test_case_size} "
          f"bb={CONF.min_bb_per_function}-{CONF.max_bb_per_function} "
          f"mem={CONF.avg_mem_accesses}")
    for i in range(args.num_test_cases):
        asm = str(outdir / f"test_case_{i}.asm")
        gen.create_test_case(asm, i)
        print(f"[{i}] {asm}")
    print(f"Done: {args.num_test_cases} test cases in {outdir}")


if __name__ == "__main__":
    main()
