#!/usr/bin/env python3
"""Tests for STAGE3_gem5/cache_setup.py (run_config gem5.cache_setup, 2026-11-08;
random 2026-11-09).

Fixtures (fixtures/cache_setup/<case>/inst-*.{s,ann.json}) are real tests copied from
cafe2 /tests/simspect_fixed_20261030/testsets_latest (rmw_frame = STT_6_rmw
not_taken inst-000003, frame-pointer shape; recon_redzone = Recon_6 not_taken
inst-000092, leaf/red-zone shape; stt_taken = STT_6 mispredict_taken inst-000005,
BTB-forced targets) and /tests/simspect/testsets/STT_6_stl/stl_bypass inst-000001
(stl_annotations store/load addrs).

The build tests need GNU as/ld/objdump/nm for x86-64 ELF (cafe2 gem5_dev); they
are skipped elsewhere. Run: python3 -m pytest STAGE3_gem5/tests
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.pop("SIMSPECT_CACHE_SETUP", None)
import cache_setup as cs   # noqa: E402
import gem5_common as gc   # noqa: E402

FIX = HERE / "fixtures" / "cache_setup"
CASES = sorted(p for p in FIX.iterdir() if p.is_dir())


def _case(d: Path):
    s = next(d.glob("inst-*.s"))
    return s, d / f"{s.stem}.ann.json"


def _gnu_tools() -> bool:
    try:
        return "GNU" in subprocess.run(["as", "--version"], capture_output=True,
                                       text=True).stdout
    except OSError:
        return False


class TransformTests(unittest.TestCase):
    def test_cold_inserts_flush_right_after_barrier(self):
        for d in CASES:
            s, _ = _case(d)
            with self.subTest(case=d.name):
                old = s.read_text().split("\n")
                new_text, info = cs.transform_asm(s.read_text(), s.stem, "cold")
                new = new_text.split("\n")
                at = cs.find_barrier(old, s.stem)
                self.assertEqual(old[:at], new[:at])          # nothing before changes
                self.assertEqual(old[at:], new[at + len(new) - len(old):])  # nor after
                block = new[at:at + len(new) - len(old)]
                self.assertEqual(old[at - 2].strip(), "mfence")
                self.assertIn(f"{cs.BEGIN_LABEL}:", block)
                body = [b.strip() for b in block if b.strip() and not b.strip().startswith(
                    ("#", ".")) and not b.strip().endswith(":")]
                self.assertEqual(body[-1], "mfence")
                fl = [b for b in body if b.startswith("clflush")]
                self.assertEqual(len(fl), info["n_clflush"])
                # one clflush in flight: each is followed by mfence; %rax saved first,
                # restored last, and only lea (no flag writes) touches it in between
                self.assertEqual(body[0], "movq\t%rax, __simspect_cs_save(%rip)")
                self.assertEqual(body[-2], "movq\t__simspect_cs_save(%rip), %rax")
                for i, b in enumerate(body):
                    if b.startswith("clflush"):
                        self.assertRegex(b, r"^clflush\s+-?\d+\(%r(sp|bp),%rax\)$")
                        self.assertEqual(body[i + 1], "mfence")
                self.assertTrue(set(b.split()[0] for b in body) <=
                                {"movq", "leaq", "clflush", "mfence"})
                # cold_burst: same lines, base-relative only, one mfence at the end
                _, ib = cs.transform_asm(s.read_text(), s.stem, "cold_burst")
                self.assertEqual(ib["n_clflush"], info["n_clflush"])
                # every __litmus_ label still follows the inserted block
                labs = [i for i, l in enumerate(new) if l.startswith("__litmus_")]
                self.assertTrue(labs and labs[0] > at + len(block) - 1)

    def test_frame_covers_every_direct_stack_operand(self):
        for d in CASES:
            s, _ = _case(d)
            with self.subTest(case=d.name):
                lines = s.read_text().split("\n")
                fr = cs.frame_region(lines, s.stem, cs.find_barrier(lines, s.stem))
                offs = cs.line_probe_offsets(fr["lo"], fr["hi"])
                # probes are <= 64 apart and span [lo, hi)
                self.assertEqual(offs[0], fr["lo"])
                self.assertEqual(offs[-1], fr["hi"] - 1)
                self.assertTrue(all(b - a <= 64 for a, b in zip(offs, offs[1:])))

    def test_shapes(self):
        shapes = {}
        for d in CASES:
            s, _ = _case(d)
            lines = s.read_text().split("\n")
            shapes[d.name] = cs.frame_region(lines, s.stem, cs.find_barrier(lines, s.stem))
        self.assertEqual(shapes["rmw_frame"]["base"], "rbp")
        self.assertEqual(shapes["rmw_frame"]["hi"], 16)          # saved rbp + return address
        self.assertEqual(shapes["recon_redzone"]["base"], "rsp")
        self.assertEqual(shapes["recon_redzone"]["lo"], -128)    # red zone

    def test_unknown_strategy_and_rip_refused(self):
        s, _ = _case(FIX / "rmw_frame")
        with self.assertRaises(cs.CacheSetupError):
            cs.transform_asm(s.read_text(), s.stem, "lukewarm")
        txt = s.read_text().replace("\txorl\t%eax, %eax\n", "\tmovq\tfoo(%rip), %rax\n", 1)
        with self.assertRaises(cs.CacheSetupError):
            cs.transform_asm(txt, s.stem, "cold")

    def test_unsupported_builds_refused(self):
        with self.assertRaises(cs.CacheSetupError):
            cs.check_build("cold", "/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt")
        cs.check_build("cold", "/work/stt/build/X86/gem5.opt")
        cs.check_build("warm", "/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt")

    def test_warm_is_identity_in_prepare(self):
        calls = []
        s, a = _case(FIX / "rmw_frame")
        out = cs.prepare(s, a, Path("/nonexistent"), lambda *x, **k: calls.append((x, k)) or "B",
                         "warm")
        self.assertEqual(out, ("B", a, None))
        self.assertEqual(calls, [((s, Path("/nonexistent")), {})])   # build_binary(s, workdir)


class RandomTests(unittest.TestCase):
    """cache_setup `random` (2026-11-09): per-test warm/cold from (seed, stem)."""

    def test_deterministic_and_stem_keyed(self):
        stems = [f"inst-{i:06d}" for i in range(2000)]
        a = [cs.choose(s) for s in stems]
        self.assertEqual(a, [cs.choose(s) for s in stems])                   # rerun
        self.assertEqual(a, [cs.choose(s, cs.DEFAULT_SEED) for s in stems])  # explicit default
        self.assertEqual(a, [cs.choose(s + "__sw_0003") for s in stems])     # sweep variant name
        self.assertTrue(set(a) <= {"warm", "cold"})
        self.assertNotEqual(a, [cs.choose(s, "other-seed") for s in stems])  # seed matters
        old = os.environ.get("SIMSPECT_CACHE_SETUP_SEED")
        try:
            os.environ["SIMSPECT_CACHE_SETUP_SEED"] = "other-seed"
            self.assertEqual([cs.choose(s) for s in stems],
                             [cs.choose(s, "other-seed") for s in stems])     # env seed
        finally:
            if old is None:
                os.environ.pop("SIMSPECT_CACHE_SETUP_SEED", None)
            else:
                os.environ["SIMSPECT_CACHE_SETUP_SEED"] = old
        self.assertEqual(cs.resolve("random", "inst-000001"), cs.choose("inst-000001"))
        self.assertEqual(cs.resolve("cold", "inst-000001"), "cold")
        self.assertEqual(cs.resolve("warm", "inst-000001"), "warm")

    def test_about_half_cold(self):
        n = 20000
        cold = sum(cs.choose(f"inst-{i:06d}") == "cold" for i in range(n))
        self.assertLess(abs(cold - n / 2), 4 * (n ** 0.5) / 2)               # 4 sigma
        # the 590-stem samples are not lopsided either
        cold = sum(cs.choose(f"inst-{i:06d}") == "cold" for i in range(0, 59000, 100))
        self.assertTrue(250 <= cold <= 340, cold)

    def test_random_known_and_refused_where_cold_is(self):
        self.assertIn("random", cs.KNOWN)
        for b in cs.CLFLUSH_UNSUPPORTED:
            with self.assertRaises(cs.CacheSetupError):
                cs.check_build("random", f"/work/{b}/build/X86/gem5.opt")
        cs.check_build("random", "/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1/build/"
                                 "X86_MESI_Two_Level/gem5.opt")
        cs.check_build("random", "/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/build/X86/gem5.opt")
        s, a = _case(FIX / "rmw_frame")
        with self.assertRaises(cs.CacheSetupError):                          # must be resolved
            cs.prepare(s, a, Path("/nonexistent"), lambda *x, **k: "B", "random")

    def test_cli_choose(self):
        out = subprocess.run([sys.executable, str(HERE.parent / "cache_setup.py"), "choose",
                              "inst-000001", "inst-000002", "--seed", "s1"],
                             capture_output=True, text=True, check=True).stdout.split("\n")
        self.assertEqual(out[0], f"inst-000001\t{cs.choose('inst-000001', 's1')}")
        self.assertEqual(out[1], f"inst-000002\t{cs.choose('inst-000002', 's1')}")


@unittest.skipUnless(_gnu_tools(), "needs GNU binutils (x86-64 ELF); run on cafe2 gem5_dev")
class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cstest_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_warm_byte_identical(self):
        for d in CASES:
            s, a = _case(d)
            with self.subTest(case=d.name):
                w1, w2 = self.tmp / f"{d.name}_1", self.tmp / f"{d.name}_2"
                w1.mkdir(); w2.mkdir()
                ref = gc.build_binary(s, w1)                       # today's path
                b, ann_p, info = cs.prepare(s, a, w2, gc.build_binary, "warm")
                self.assertIsNone(info)
                self.assertEqual(ann_p, a)
                self.assertEqual(hashlib.md5(ref.read_bytes()).hexdigest(),
                                 hashlib.md5(b.read_bytes()).hexdigest())

    def test_cold_annotation_round_trip(self):
        for d in CASES:
            s, a = _case(d)
            with self.subTest(case=d.name):
                w = self.tmp / d.name
                w.mkdir()
                b, ann_p, info = cs.prepare(s, a, w, gc.build_binary, "cold")
                old, new = json.loads(a.read_text()), json.loads(ann_p.read_text())
                self.assertGreater(info["delta"], 0)
                fo, fn = cs.addr_fields(old), cs.addr_fields(new)
                self.assertEqual(set(fo), set(fn))
                begin = int(info["begin"], 16)
                for p, v in fo.items():
                    exp = v + info["delta"] if (v >= begin and p != ".func_base_addr") else v
                    self.assertEqual(fn[p], exp, p)
                # independent check: each re-resolved address sits on the same
                # __litmus_ label as before (labels via nm on both binaries)
                ref = self.tmp / f"{d.name}_ref"
                ref.mkdir()
                wb = gc.build_binary(s, ref)
                lo = {v: k for k, v in cs._nm(wb).items() if k.startswith("__litmus_")}
                ln = {v: k for k, v in cs._nm(b).items() if k.startswith("__litmus_")}
                for p, v in fo.items():
                    if v in lo:
                        self.assertIn(fn[p], ln, p)
                        self.assertEqual(lo[v], ln[fn[p]], p)
                # hex siblings follow
                x = new["xmit"]
                self.assertEqual(x["addr_hex"], hex(x["addr"]))
                if d.name == "stl_bypass":
                    st = new["stl_annotations"][0]
                    self.assertEqual(st["store_addr"], json.loads(a.read_text())
                                     ["stl_annotations"][0]["store_addr"] + info["delta"])
                if d.name == "stt_taken":
                    self.assertTrue(any("btb_forced_target_addr" in e
                                        for e in new["annotations"]))

    def _random_run(self, seed):
        """process_one under random with gem5 stubbed out (raises after the build)."""
        class _Stop(Exception):
            pass

        def stub(*a, **k):
            raise _Stop("stub: no gem5 in unit tests")
        old = (gc.CACHE_SETUP, gc.run_gem5, os.environ.get("SIMSPECT_CACHE_SETUP"),
               os.environ.get("SIMSPECT_CACHE_SETUP_SEED"))
        recs = {}
        try:
            gc.CACHE_SETUP = "random"
            os.environ["SIMSPECT_CACHE_SETUP"] = "random"
            os.environ["SIMSPECT_CACHE_SETUP_SEED"] = seed
            gc.run_gem5 = stub
            for d in CASES:
                s, a = _case(d)
                recs[d.name] = gc.process_one(s, a, lambda *x, **k: {})
        finally:
            gc.CACHE_SETUP, gc.run_gem5 = old[0], old[1]
            for k, v in (("SIMSPECT_CACHE_SETUP", old[2]), ("SIMSPECT_CACHE_SETUP_SEED", old[3])):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return recs

    def test_random_recorded_per_record(self):
        seen = set()
        for seed in ("s0", "s1", "s2", "s3", "s4", "s5"):
            for name, r in self._random_run(seed).items():
                s, _ = _case(FIX / name)
                with self.subTest(seed=seed, case=name):
                    want = cs.choose(s.stem, seed)
                    self.assertEqual(r["cache_setup"], want)
                    self.assertEqual(r["cache_setup_mode"], "random")
                    self.assertEqual(r["cache_setup_seed"], seed)
                    self.assertIn("stub: no gem5", r["error"] or "")   # built, then stopped
                    self.assertEqual("cache_setup_info" in r, want == "cold")
                    seen.add(want)
        self.assertEqual(seen, {"warm", "cold"})

    def test_random_warm_half_byte_identical(self):
        for d in CASES:
            s, a = _case(d)
            with self.subTest(case=d.name):
                w1, w2 = self.tmp / f"{d.name}_w", self.tmp / f"{d.name}_r"
                w1.mkdir(); w2.mkdir()
                ref = gc.build_binary(s, w1)                       # warm run's path
                old = (gc.CACHE_SETUP, os.environ.get("SIMSPECT_CACHE_SETUP"))
                try:
                    gc.CACHE_SETUP = "random"
                    os.environ["SIMSPECT_CACHE_SETUP"] = "random"
                    b, ann_p, info = cs.prepare(s, a, w2, gc.build_binary, "warm")
                finally:
                    gc.CACHE_SETUP = old[0]
                    if old[1] is None:
                        os.environ.pop("SIMSPECT_CACHE_SETUP", None)
                    else:
                        os.environ["SIMSPECT_CACHE_SETUP"] = old[1]
                self.assertIsNone(info)
                self.assertEqual(ann_p, a)
                self.assertEqual(hashlib.md5(ref.read_bytes()).hexdigest(),
                                 hashlib.md5(b.read_bytes()).hexdigest())

    def test_build_binary_guard(self):
        s, _ = _case(FIX / "rmw_frame")
        old = gc.CACHE_SETUP
        try:
            gc.CACHE_SETUP = "cold"
            with self.assertRaises(RuntimeError):
                gc.build_binary(s, self.tmp)
        finally:
            gc.CACHE_SETUP = old


if __name__ == "__main__":
    unittest.main()
