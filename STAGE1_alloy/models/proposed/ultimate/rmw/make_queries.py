#!/usr/bin/env python3
"""Build the Alloy query files behind the STT_6_rmw_u evidence (rmw agent, 2026-11-09).

Writes ./queries/*.als next to this script. STT_6_rmw_u_core_ri.als here was made with
proposed_twophase/derive_core.py --minimality ri from ../STT_6_rmw_u.als (unapproved draft core).
Run: python3 make_queries.py; python3 run_batch.py A (then B, E); python3 analyze.py <outdir>...
"""
from pathlib import Path

S = Path(__file__).parent
REPO = Path("/Users/annaeaton/Documents/stanford/trippel/simspect")
FULL = (REPO / "STAGE1_alloy/models/proposed/ultimate/STT_6_rmw_u.als").read_text()
CORE = (S / "STT_6_rmw_u_core_ri.als").read_text()
STTCORE = (REPO / "STAGE1_alloy/models/proposed_twophase/STT_6_core_ri.als").read_text()

PIN = "fact rmw_pin { some Rmws }\n"
SCOPE6 = "} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"
Q = S / "queries"
Q.mkdir(exist_ok=True)


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def full(name, extra):
    (Q / f"{name}.als").write_text(FULL + "\n// [scratch query]\n" + extra + "\n")


def core(name, bound, extra, pinned=True, base=CORE):
    t = base
    if not pinned:
        t = once(t, PIN, "// rmw_pin removed for this scratch query\n")
    t = once(t, SCOPE6, SCOPE6.replace("but 6", f"but {bound}"))
    (Q / f"{name}.als").write_text(t + "\n// [scratch query]\n" + extra + "\n")


# full model, exactly 6
full("F1_pinned", "")
full("F2_rmw_xm", "fact q { some (Rmws & xm) }")
full("F3_rmw_spec_nonxm", "fact q { some ((Rmws - xm) & uncommitted) }")
full("F4_rmw_committed", "fact q { some (Rmws & committed) }")
full("F5_xm_rmw_memops_irrelevant",
     "fact q { some r: Rmws & xm | secure_speculation_scheme_p[RO->(r.inmem + r.outmem)] }")
full("F6_spec_ld_then_spec_rmw_same_loc",
     "fact q { some l: Loads & uncommitted, r: (Rmws - xm) & uncommitted |\n"
     "  r in l.^spo and r.inmem.opstate = l.inmem.opstate and no r.inaddr }")
full("F7_rmw_stl_source",
     "fact q { some r: Rmws & uncommitted, l: Loads & uncommitted | l.inmem in r.outmem.rf }")
full("F8_rmw_tainted_src",
     "fact q { some r: Rmws & xm | some r.inreg.~rf and r.inreg in Instruction.outreg.rf }")

# Stage-1 RI-only cores
for b in (3, 4):
    core(f"C1_core_pinned_b{b}", b, "")
    core(f"C2_core_normws_b{b}", b, "fact q { no Rmws }", pinned=False)
    t = once(STTCORE, SCOPE6, SCOPE6.replace("but 6", f"but {b}"))
    (Q / f"C3_stt6core_b{b}.als").write_text(t)
core("C4_core_rmw_nonxm_b5", 5, "fact q { some (Rmws - xm) }")
core("C5_core_pinned_b5", 5, "")
print(sorted(p.name for p in Q.glob("*.als")))

# sanity controls for F5 (added after F5 returned 0 with no 'solving' line)
core("K1_core_memops_irrelevant_b4", 4,
     "fact q { some r: Rmws & xm | secure_speculation_scheme_p[RO->(r.inmem + r.outmem)] }")
core("K2_core_inaddr_matters_b4", 4,
     "fact q { some r: Rmws & xm | secure_speculation_scheme_p[RO->r.inaddr] }")
full("K3_full_inaddr_matters",
     "fact q { some r: Rmws & xm | secure_speculation_scheme_p[RO->r.inaddr] }")

# security-relevant CleanupSpec E->M shape: a non-xm speculative RMW after the xm load,
# addressed from the same producer as the xm load's address (same secret-dependent line)
full("F9_rmw_hits_xmit_line",
     "fact q { some x: Loads & xm, r: (Rmws - xm) & uncommitted | r in x.^spo\n"
     "  and some (x.inaddr.~rf & r.inaddr.~rf) }")
