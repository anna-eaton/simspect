"""Per-process CPU accounting for gem5 runs (timing-amulet, 2026-11-09).

Loaded automatically by Python only when STAGE3_gem5/timing/timing_driver.py puts
this directory on PYTHONPATH for the pipeline/checker subprocesses. No SimSpect
source file is edited. It wraps subprocess.Popen._try_wait (the single reaping
point of every Popen in CPython 3.8) with os.wait4 so the reaped child's rusage
is captured, and for every child whose argv[0] ends in gem5.opt/gem5.fast/gem5.debug it
appends one JSON line to $TIMING_GEM5_LOG:
  {"t_end", "wall_s", "utime_s", "stime_s", "maxrss_kb", "rc", "argv0", "cmd"}
If TIMING_GEM5_LOG is unset this module does nothing.
"""
import os

_LOG = os.environ.get("TIMING_GEM5_LOG")
if _LOG:
    import json, subprocess, time

    _orig_init = subprocess.Popen.__init__

    def _init(self, *a, **kw):
        self._timing_t0 = time.monotonic()
        _orig_init(self, *a, **kw)

    def _try_wait(self, wait_flags):
        try:
            pid, sts, ru = os.wait4(self.pid, wait_flags)
        except ChildProcessError:
            return (self.pid, 0)
        if pid == self.pid:
            try:
                args = self.args if isinstance(self.args, (list, tuple)) else [str(self.args)]
                a0 = str(args[0]) if args else ""
                if a0.endswith(("gem5.opt", "gem5.fast", "gem5.debug")):
                    rec = dict(t_end=time.time(),
                               wall_s=round(time.monotonic() - getattr(self, "_timing_t0", time.monotonic()), 4),
                               utime_s=ru.ru_utime, stime_s=ru.ru_stime, maxrss_kb=ru.ru_maxrss,
                               rc=(os.WEXITSTATUS(sts) if os.WIFEXITED(sts) else -os.WTERMSIG(sts) if os.WIFSIGNALED(sts) else None),
                               argv0=a0, cmd=[str(x) for x in args if str(x).startswith("--cmd=")])
                    with open(_LOG, "a") as f:
                        f.write(json.dumps(rec) + "\n")
            except Exception as e:  # never break the run; leave a trace of the failure
                try:
                    with open(_LOG + ".err", "a") as f:
                        f.write(f"{time.time()} sitecustomize log error: {e!r}\n")
                except Exception:
                    pass
        return (pid, sts)

    subprocess.Popen.__init__ = _init
    subprocess.Popen._try_wait = _try_wait
