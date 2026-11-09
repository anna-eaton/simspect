#!/usr/bin/env python3
"""make_dump_stt.py (STT agent 2026-11-09): sample files for the Stage-2 smoke test of STT_6_u / STT_6_u_stl.
Run each with a6DumpAll (all instances of every command written as XML) under the Alloy lock, then feed the
per-command dirs to STAGE2_compilation/batch_generate.py."""
from pathlib import Path
import make_queries_stt as M
S6 = M.SCOPE6
t = M.base("STT_6_u.als", False) + M.AUX_COMMON + M.AUX_SHAPES
t += f"\nrun dump_gen_first {{ gen_useful_litmus }} {S6}\nrun dump_R1 {{ gen_useful_litmus and u1_shape }} {S6}\n"
(M.HERE / "q_dump.als").write_text(t)
t = M.base("STT_6_u_stl.als", False) + M.AUX_COMMON + M.AUX_SHAPES + M.AUX_STL
t += f"\nrun dump_stl_first {{ gen_useful_litmus }} {S6}\nrun dump_stl_S1 {{ gen_useful_litmus and s1_shape }} {S6}\n"
(M.HERE / "q_dump_stl.als").write_text(t)
print("wrote q_dump.als q_dump_stl.als")
