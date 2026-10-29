#!/usr/bin/env python3
"""Unit + regression tests for STAGE3_gem5/check_footprint.py.

Synthetic O3PipeView + SimSpect snippets (line format: wiki/design/SIMSPECT_HOOKS.md)
cover each criterion term; fixtures/ holds real hooked-build traces copied from
cafe2 /work/amulet/simspect_hooks_verify/<case>/new/pipeview.txt (2026-10-28,
gem5-hooks/verify/run_all_verify.sh) with their resolved PCs in <case>.meta.json.

Run:  python3 STAGE3_gem5/tests/test_check_footprint.py      (or python3 -m pytest STAGE3_gem5/tests)
"""
import gzip
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import check_footprint as cf  # noqa: E402
import gem5_common as gc      # noqa: E402

CRIT = {n: cf.load_criterion(REPO / "specs" / "leakage" / f"{n}.json")
        for n in ("invisispec", "speclfb", "cleanupspec")}

LC_PC, FNC_PC = 0x1000, 0x1004


class Trace:
    """Builder for a synthetic trace."""

    def __init__(self):
        self.lines = []
        self.next_id = 1000

    def inst(self, seq, pc, fetch, retire, complete=None):
        self.lines += [f"O3PipeView:fetch:{fetch}:{pc:#010x}:0:{seq}:  synthetic",
                       f"O3PipeView:decode:{fetch + 1}", f"O3PipeView:rename:{fetch + 2}",
                       f"O3PipeView:dispatch:{fetch + 3}", f"O3PipeView:issue:{fetch + 4}",
                       f"O3PipeView:complete:{complete if complete is not None else fetch + 5}",
                       f"O3PipeView:retire:{retire}:store:0"]
        return self

    def ev(self, tick, struct, kind, line=None, seq=None, pc=None, victim=None,
           cause=None, sq=None, id=None):
        if id is None:
            id = self.next_id
            self.next_id += 1
        f = lambda v, h=False: "-" if v is None else (hex(v) if h else str(v))
        self.lines.append(
            f"O3PipeView:simspect:{tick}:{struct}:{kind}:line={f(line, True)}:seq={f(seq)}"
            f":pc={f(pc, True)}:victim={f(victim, True)}:cause={f(cause)}:sq={f(sq)}:id={id}")
        return id

    def base(self):
        """lc (seq 10) retires at 1000, fnc branch (seq 11) retires at 5000,
        spec loads 12/13 fetched at 900 and squashed at 3000 by the branch."""
        self.inst(5, 0x0ff0, 100, 400)
        self.inst(10, LC_PC, 800, 1000)
        self.inst(12, 0x1008, 900, 0, complete=0)
        self.inst(13, 0x100c, 900, 0, complete=0)
        self.inst(11, FNC_PC, 850, 5000, complete=1500)
        return self

    def squash(self, tick=3000, seq=11, sq=1):
        return self.ev(tick, "ROB", "squash", seq=seq, sq=sq)

    def run(self, crit, unresolved=(), actor_mode=None, scheme_name=""):
        d = Path(tempfile.mkdtemp(prefix="fp_test_"))
        try:
            p = d / "pipeview.txt"
            # gem5 prints records when instructions are destroyed; events are in tick order
            p.write_text("\n".join(self.lines) + "\n")
            return cf.evaluate_trace(p, CRIT[crit], LC_PC, FNC_PC, list(unresolved), 500,
                                     actor_mode=actor_mode, scheme_name=scheme_name)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestParser(unittest.TestCase):
    def test_parse_line(self):
        ev = gc.parse_simspect_line(
            "O3PipeView:simspect:356000:L1D:evict:line=0x4000:seq=35:pc=0x401043:victim=0x3000:cause=89:sq=-:id=90\n")
        self.assertEqual((ev["tick"], ev["struct"], ev["kind"], ev["line"], ev["seq"], ev["pc"],
                          ev["victim"], ev["cause"], ev["sq"], ev["id"]),
                         (356000, "L1D", "evict", 0x4000, 35, 0x401043, 0x3000, 89, None, 90))
        sq = gc.parse_simspect_line("O3PipeView:simspect:0:ROB:squash:line=-:seq=0:pc=-:victim=-:cause=-:sq=1:id=2")
        self.assertIsNone(sq["line"]); self.assertEqual(sq["sq"], 1)
        self.assertIsNone(gc.parse_simspect_line("O3PipeView:fetch:1:0x1:0:1: x"))
        with self.assertRaises(ValueError):
            gc.parse_simspect_line("O3PipeView:simspect:1:L1D:fill:garbage")

    def test_parse_pipeview_unchanged_by_simspect_lines(self):
        t = Trace().base(); t.squash(); t.ev(2000, "L1D", "fill", line=0x40, seq=12)
        d = Path(tempfile.mkdtemp()); p = d / "pv.txt"
        p.write_text("\n".join(t.lines) + "\n")
        q = d / "pv_plain.txt"
        q.write_text("\n".join(l for l in t.lines if not l.startswith("O3PipeView:simspect:")) + "\n")
        self.assertEqual(gc.parse_pipeview(p), gc.parse_pipeview(q))
        by_seq = gc.parse_pipeview_by_seq(p)
        self.assertEqual(by_seq[11]["retire"], 5000); self.assertEqual(by_seq[12]["retire"], 0)
        shutil.rmtree(d)

    def test_scheme_selection(self):
        self.assertEqual(cf.scheme_name_from_args(["--ruby", "--scheme=SpectreSafeInvisibleSpec",
                                                   "--scheme=FuturisticSafeInvisibleSpec"]),
                         "FuturisticSafeInvisibleSpec")
        self.assertEqual(cf.select_actor_mode(CRIT["invisispec"], "FuturisticSafeInvisibleSpec"), "futuristic")
        self.assertEqual(cf.select_actor_mode(CRIT["invisispec"], "SpectreSafeInvisibleSpec"), "spec")
        self.assertEqual(cf.select_actor_mode(CRIT["cleanupspec"], "2"), "spec")


class TestInvisiSpec(unittest.TestCase):
    def test_in_window_spec_fill_leaks(self):
        t = Trace().base(); fid = t.ev(2000, "L1D", "fill", line=0x3000, seq=12); t.squash()
        r = t.run("invisispec")
        self.assertTrue(r["leak"]); self.assertTrue(r["issued_in_window"])
        self.assertEqual(r["terms_fired"], ["footprint"])
        self.assertEqual(r["offending"][0]["event_ids"], [fid])

    def test_sb_only_no_leak(self):
        t = Trace().base(); t.ev(2000, "SB", "buf_fill", line=0x3000, seq=12); t.squash()
        t.ev(3000, "SB", "buf_release", line=0x3000, seq=12, sq=1)
        r = t.run("invisispec")
        self.assertFalse(r["leak"])

    def test_committed_fill_and_out_of_window_not_leak(self):
        t = Trace().base(); t.ev(300, "L1D", "fill", line=0x2000, seq=5)   # committed
        t.ev(6000, "L1D", "fill", line=0x3000, seq=12)                     # after fnc retire
        t.squash()
        r = t.run("invisispec")
        self.assertFalse(r["leak"]); self.assertEqual(len(r["footprint_outside_window"]), 1)

    def test_branch_resolved_closes_window(self):
        # branch completes 1500 + 2 cycles*500 = 2500: a fill at 2700 is after resolution
        t = Trace().base(); t.ev(2700, "L1D", "fill", line=0x3000, seq=12); t.squash()
        self.assertFalse(t.run("invisispec", unresolved=[dict(pc=FNC_PC, stall_cycles=2)])["leak"])
        t2 = Trace().base(); t2.ev(2400, "L1D", "fill", line=0x3000, seq=12); t2.squash()
        self.assertTrue(t2.run("invisispec", unresolved=[dict(pc=FNC_PC, stall_cycles=2)])["leak"])

    def test_futuristic(self):
        def mk():
            t = Trace().base(); t.squash()
            t.inst(19, 0x2000, 5900, 7000)
            t.inst(20, 0x2004, 6000, 8000)
            t.inst(21, 0x2008, 6000, 8100)
            # load 20: expose at 6500, fill after it → legal
            t.ev(6500, "L1D", "expose", line=0x5000, seq=20)
            t.ev(6600, "L1D", "fill", line=0x5000, seq=20)
            return t
        t = mk()
        r = t.run("invisispec", scheme_name="FuturisticSafeInvisibleSpec")
        self.assertEqual(r["actor_mode"], "futuristic"); self.assertFalse(r["leak"])
        # load 21 fills at 6400, before its expose (6800) and its ROB-head (8000) → leak
        t = mk(); t.ev(6400, "L1D", "fill", line=0x6000, seq=21); t.ev(6800, "L1D", "validate", line=0x6000, seq=21)
        r = t.run("invisispec", scheme_name="FuturisticSafeInvisibleSpec")
        self.assertTrue(r["leak"]); self.assertEqual(r["offending"][0]["line"], "0x6000")
        self.assertEqual(r["offending"][0]["vp"]["21"], [6800, "expose/validate"])
        # same trace under the Spectre scheme: 20/21 committed → not actors
        self.assertFalse(t.run("invisispec", scheme_name="SpectreSafeInvisibleSpec")["leak"])

    def test_no_simspect_lines_is_undecided(self):
        t = Trace().base()
        r = t.run("invisispec")
        self.assertIsNone(r["issued_in_window"]); self.assertEqual(r["status"], "warn")


class TestSpecLFB(unittest.TestCase):
    def test_buf_fill_only_no_leak(self):
        t = Trace().base(); t.ev(2000, "LFB", "buf_fill", line=0x3000, seq=12); t.squash()
        self.assertFalse(t.run("speclfb")["leak"])

    def test_l1d_fill_leaks(self):
        t = Trace().base(); t.ev(2000, "L1D", "fill", line=0x3000, seq=12); t.squash()
        r = t.run("speclfb"); self.assertTrue(r["leak"])

    def test_repl_touch_out_of_scope(self):
        t = Trace().base(); t.ev(2000, "L1D", "repl_touch", line=0x3000, seq=12); t.squash()
        self.assertFalse(t.run("speclfb")["leak"])


class TestCleanupSpec(unittest.TestCase):
    def committed_B(self, t):
        t.ev(300, "L1D", "fill", line=0xB000, seq=5)

    def test_correct_cleanup_no_leak(self):
        t = Trace().base(); self.committed_B(t)
        f = t.ev(2000, "L1D", "fill", line=0xA000, seq=12)
        t.ev(2000, "L1D", "evict", line=0xA000, seq=12, victim=0xB000, cause=f)
        t.ev(2000, "L2", "fill", line=0xA000, seq=12)
        t.squash()
        t.ev(3200, "L1D", "cleanup_inv", line=0xA000, seq=12, sq=1)
        t.ev(3300, "L1D", "cleanup_restore", line=0xB000, seq=12, sq=1)
        t.ev(3350, "L2", "cleanup_inv", line=0xA000, seq=12, sq=1)
        t.ev(3400, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertFalse(r["leak"]); self.assertFalse(r["inconsistent"]); self.assertTrue(r["decided"])
        self.assertFalse(r["net_state"]["leak"])

    def test_split_load_two_fills_zero_cleanup_leaks_positive(self):
        t = Trace().base()
        t.ev(2000, "L1D", "fill", line=0x1000, seq=12); t.ev(2010, "L1D", "fill", line=0x1040, seq=12)
        t.squash()
        t.ev(3100, "L1D", "cleanup_skip", line=0x1000, seq=12, sq=1)
        t.ev(3100, "L1D", "cleanup_skip", line=0x1040, seq=12, sq=1)
        t.ev(3200, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertTrue(r["leak"]); self.assertEqual(r["terms_fired"], ["under_clean"])
        self.assertEqual(sorted(p["d_install"] for p in r["per_line"]), [1, 1])
        self.assertEqual(len(r["skip_drop"]), 2); self.assertFalse(r["inconsistent"])

    def test_over_clean_leaks_negative(self):
        t = Trace().base(); self.committed_B(t); t.squash()
        t.ev(3200, "L1D", "cleanup_inv", line=0xB000, seq=12, sq=1)
        t.ev(3400, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertTrue(r["leak"]); self.assertEqual(r["terms_fired"], ["over_clean"])
        self.assertEqual(r["per_line"][0]["d_install"], -1); self.assertFalse(r["inconsistent"])

    def test_intra_window_churn_cancels(self):
        t = Trace().base()
        a = t.ev(2000, "L1D", "fill", line=0xA000, seq=12)
        d = t.ev(2100, "L1D", "fill", line=0xD000, seq=13)
        t.ev(2100, "L1D", "evict", line=0xD000, seq=13, victim=0xA000, cause=d)
        t.squash()
        t.ev(3150, "L1D", "cleanup_skip", line=0xA000, seq=12, sq=1)   # A no longer present
        t.ev(3200, "L1D", "cleanup_inv", line=0xD000, seq=13, sq=1)
        t.ev(3400, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertFalse(r["leak"]); self.assertFalse(r["inconsistent"])
        pa = [p for p in r["per_line"] if p["line"] == "0xa000"][0]
        self.assertEqual(pa["churn_cancelled"], 1)

    def test_skip_and_drop_count_as_uncleaned(self):
        for kind in ("cleanup_skip", "cleanup_drop"):
            t = Trace().base(); t.ev(2000, "L1D", "fill", line=0xA000, seq=12); t.squash()
            t.ev(3100, "L1D", kind, line=0xA000, seq=12, sq=1)
            t.ev(3200, "L1D", "cleanup_done", seq=11, sq=1)
            r = t.run("cleanupspec")
            self.assertTrue(r["leak"], kind); self.assertEqual(r["skip_drop"][0]["kind"], kind)

    def test_l2_victim_is_benign_but_l2_install_must_be_invalidated(self):
        t = Trace().base(); t.ev(300, "L2", "fill", line=0xB000, seq=5)
        f = t.ev(2000, "L2", "fill", line=0xA000, seq=12)
        t.ev(2000, "L2", "evict", line=0xA000, seq=12, victim=0xB000, cause=f)
        t.squash()
        t.ev(3200, "L2", "cleanup_inv", line=0xA000, seq=12, sq=1)
        t.ev(3400, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertFalse(r["leak"]); self.assertFalse(r["inconsistent"])

    def test_count_vs_replay_inconsistent_flag(self):
        # spec fill A, then A removed by an unattributed coherence inv (not cleanup):
        # the count says uncleaned, the replay says the net state is unchanged.
        t = Trace().base(); t.ev(2000, "L1D", "fill", line=0xA000, seq=12)
        t.ev(2500, "L1D", "inv", line=0xA000); t.squash()
        t.ev(3400, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertTrue(r["inconsistent"]); self.assertFalse(r["decided"])
        self.assertTrue(r["leak"]); self.assertTrue(r["issued_in_window"])   # never hide

    def test_late_inflight_fill_after_squash_counts(self):
        # squashed in-flight load (no fetch record) fills after the squash, no cleanup
        t = Trace().base(); t.ev(2000, "L1D", "fill", line=0xA000, seq=12)
        t.ev(2100, "MSHR", "buf_fill", line=0xC000, seq=14)
        t.squash()
        t.ev(3200, "L1D", "cleanup_inv", line=0xA000, seq=12, sq=1)
        t.ev(3300, "L1D", "cleanup_drop", line=0xC000, seq=14, sq=1)
        t.ev(3350, "L1D", "fill", line=0xC000, seq=14)
        t.ev(3400, "L1D", "cleanup_done", seq=11, sq=1)
        r = t.run("cleanupspec")
        self.assertTrue(r["leak"]); self.assertEqual(r["offending"][0]["line"], "0xc000")


class TestRealTraces(unittest.TestCase):
    """Hooked-build traces (fixtures/, from cafe2 simspect_hooks_verify)."""
    CASES = [("inv_uv1", "invisispec", True), ("lfb_uv6x", "speclfb", True),
             ("cln_uv5clean", "cleanupspec", False), ("cln_uv4split", "cleanupspec", True),
             ("inv_fut", "invisispec", True)]

    def _run(self, case, crit):
        meta = json.loads((HERE / "fixtures" / f"{case}.meta.json").read_text())
        d = Path(tempfile.mkdtemp())
        try:
            p = d / "pipeview.txt"
            with gzip.open(HERE / "fixtures" / f"{case}.pipeview.txt.gz", "rb") as g, open(p, "wb") as o:
                shutil.copyfileobj(g, o)
            scheme = cf.scheme_name_from_args(meta["cmd"].split())
            return cf.evaluate_trace(p, CRIT[crit], meta["lc_pc"], meta["fnc_pc"], meta["unresolved"],
                                     meta["ticks_per_cycle"], scheme_name=scheme)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_real_traces(self):
        for case, crit, want in self.CASES:
            with self.subTest(case=case):
                r = self._run(case, crit)
                self.assertEqual(r["leak"], want, case)
                if crit == "cleanupspec":
                    self.assertFalse(r["inconsistent"], case)

    def test_uv1_offending_is_the_spec_eviction(self):
        r = self._run("inv_uv1", "invisispec")
        evicts = [o for o in r["offending"] if o["struct"] == "L1D" and "evict" in o["kinds"]]
        self.assertIn("0x39c0", [o["line"] for o in evicts])     # SIMSPECT_HOOKS.md UV1 example

    def test_uv4split_both_lines_uncleaned(self):
        r = self._run("cln_uv4split", "cleanupspec")
        l1 = sorted(o["line"] for o in r["offending"] if o["struct"] == "L1D")
        self.assertEqual(l1, ["0x1000", "0x1040"])

    def test_uv5clean_balanced(self):
        r = self._run("cln_uv5clean", "cleanupspec")
        pl = {(p["struct"], p["line"]): p for p in r["per_line"]}
        self.assertEqual(pl[("L1D", "0x3000")]["restored"], 1)
        self.assertEqual(pl[("L1D", "0x4000")]["invalidated"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
