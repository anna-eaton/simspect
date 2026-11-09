#!/usr/bin/env python3
"""Synthetic-trace tests for STAGE3_gem5/triage/recon_physreg16_check.analyse (2026-11-08).

Positive: a speculative load (sn 10, under held branch sn 5) renames its dest to IntRegClass phys 16, the
transmitter (sn 12) reads phys 16, gem5's STL_CHECK says isTainted=0 isSpeculative=1 -> full signature.
Negative 1: same, but the load's dest is phys 17 -> sim_with_rule tainted (disagrees with gem5) -> no via16.
Negative 2: the load is OLDER than the held branch -> not an origin -> no signature.
Negative 3: a squash removes the phys-16 producer before the xmit renames -> producer is the older one.
"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "triage"))
import recon_physreg16_check as R

def trace(dest_phys=16, load_sn=10, squash=False):
    L = [
        "   100: system.cpu.rename: [tid:0] Processing instruction [sn:%d] with PC (0x401000=>0x401004).(0=>1)." % load_sn,
        "   100: system.cpu.rename: [tid:0] Looking up IntRegClass arch reg 4, got phys reg 49 (IntRegClass)",
        "   100: system.cpu.rename: [tid:0] Renaming arch reg 0 (IntRegClass) to physical reg %d (%d)." % (dest_phys, dest_phys),
        "   100: system.cpu.rename: [tid:0] [sn:%d] Adding instruction to history buffer (size=1)." % load_sn,
    ]
    if squash:
        L += ["   150: system.cpu.rename: [tid:0] [squash sn:%d] Squashing instructions." % (load_sn - 1)]
    L += [
        "   200: system.cpu.rename: [tid:0] Processing instruction [sn:12] with PC (0x401008=>0x40100c).(0=>1).",
        "   200: system.cpu.rename: [tid:0] Looking up IntRegClass arch reg 0, got phys reg %d (IntRegClass)" % dest_phys,
        "   200: system.cpu.rename: [tid:0] Renaming arch reg 1 (IntRegClass) to physical reg 60 (60).",
        "   300: system.cpu.iew.lsq.thread0: Inserting load PC (0x401000=>0x401004).(0=>1), [sn:%d]" % load_sn,
        "   300: system.cpu.iew.lsq.thread0: Executing load PC (0x401000=>0x401004).(0=>1), [sn:%d]" % load_sn,
        "   300: system.cpu.iew.lsq.thread0: STL_CHECK: load PC 0x401000 isTainted=0 isSpeculative=1",
        "   400: system.cpu.iew.lsq.thread0: Inserting load PC (0x401008=>0x40100c).(0=>1), [sn:12]",
        "   400: system.cpu.iew.lsq.thread0: Executing load PC (0x401008=>0x40100c).(0=>1), [sn:12]",
        "   400: system.cpu.iew.lsq.thread0: STL_CHECK: load PC 0x401008 isTainted=0 isSpeculative=1",
    ]
    f = Path(tempfile.mkdtemp()) / "pipeview.txt"; f.write_text("\n".join(L) + "\n"); return f

BR = {"0x400ff0": {"5": {"resolve_hold": 50, "resolve_visible": 9000}}}

def check(name, o, **want):
    bad = {k: (o.get(k), v) for k, v in want.items() if o.get(k) != v}
    print(("PASS " if not bad else "FAIL ") + name, bad if bad else "")
    return not bad

ok = True
ok &= check("positive", R.analyse(trace(), "0x401008", 400, BR), gem5_untainted=True, sim_with_rule=False,
            sim_without_rule=True, via16=[10], parse_ok=True, origins=[10])
ok &= check("dest17", R.analyse(trace(dest_phys=17), "0x401008", 400, BR), sim_with_rule=True, via16=[])
ok &= check("older_than_branch", R.analyse(trace(load_sn=4), "0x401008", 400, BR), origins=[], sim_without_rule=False)
ok &= check("squashed_producer", R.analyse(trace(squash=True), "0x401008", 400, BR), slice=[12], via16=[])
sys.exit(0 if ok else 1)
