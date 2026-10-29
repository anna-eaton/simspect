#!/usr/bin/env python3
"""
check_footprint.py — ONE generic footprint checker for the footprint-hiding
defenses (InvisiSpec, SpecLFB, CleanupSpec), driven by a criterion JSON.

Interface = strictly the O3PipeView trace: the normal per-instruction records
plus the SimSpect hook lines (`O3PipeView:simspect:...`, format in
wiki/design/SIMSPECT_HOOKS.md). No ProtocolTrace / LSQUnit / Cache flags are
read. The criterion schema (`simspect.transmission_criterion/v1`) and the three
predicates are documented in wiki/design/TRANSMISSION_CRITERIA_FORMAT.md
("Criterion JSONs + checker"); the criteria live in specs/leakage/<defense>.json.

Flow per test: build + run gem5 through gem5_common (same path as check_ld.py),
parse pipeview records by seq + simspect events, join events to instructions by
seq, compute the window (lc_retire, fnc_retire, branches unresolved — same as
check_ld), pick the actor mode (from the scheme, see `select_actor_mode`), and
evaluate the criterion's leak form:
  exists           ∃ footprint event in OBS by an actor inside the window
  per_line_balance CleanupSpec: installed−churn−invalidated, evicted−churn−restored
                   per (struct, line), plus a net-state replay cross-check

Usage (same CLI shape as check_ld.py, plus the criterion):
    python3 check_footprint.py <dir-with-.s+.ann.json> --criterion specs/leakage/cleanupspec.json \
        [--jobs N] [--scheme N] [--out results.json] [--actor spec|futuristic]
    # offline, on an existing trace (no gem5):
    python3 check_footprint.py --trace pipeview.txt --meta meta.json --criterion <json> [--out r.json]
      meta.json: {"lc_pc":int|null,"fnc_pc":int|null,"unresolved":[{"pc":int,"stall_cycles":int}],
                  "ticks_per_cycle":500,"cmd":"<gem5 command line, for the scheme>"}
The criterion may also come from env SIMSPECT_CRITERION (pipeline.py sets it
from run_config gem5.criterion) and the actor override from
SIMSPECT_CRITERION_ACTOR (gem5.criterion_actor).
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Only O3PipeView is needed; a run config's explicit debug_flags still win.
os.environ.setdefault("SIMSPECT_GEM5_DBG_FLAG", "O3PipeView")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gem5_common import (best_record, check_branch_resolutions,  # noqa: E402
                         parse_pipeview, parse_pipeview_by_seq,
                         parse_simspect_events, run_batch)

INF = float("inf")
SCHEMA = "simspect.transmission_criterion/v1"


# ── criterion + actor-mode selection ─────────────────────────────────────────

def load_criterion(path) -> dict:
    crit = json.loads(Path(path).read_text())
    if crit.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema is {crit.get('schema')!r}, expected {SCHEMA!r}")
    for k in ("observation", "actors", "window", "terms", "leak"):
        if k not in crit:
            raise ValueError(f"{path}: missing {k!r}")
    crit["_path"] = str(path)
    return crit


def scheme_name_from_args(args: List[str], numeric_scheme=None) -> str:
    """Last-wins `--scheme=<X>` among the gem5 args (same rule as optparse, see
    CLAUDE.md config->env bridge). Falls back to the numeric --scheme."""
    name = None
    for a in args:
        if a.startswith("--scheme="):
            name = a.split("=", 1)[1]
    if name is None and numeric_scheme is not None:
        name = str(numeric_scheme)
    return name or ""


def select_actor_mode(crit: dict, scheme_name: str, override: Optional[str] = None) -> str:
    actors = crit["actors"]
    modes = actors.get("modes", {})
    if override:
        if override not in modes:
            raise ValueError(f"actor mode {override!r} not in criterion modes {sorted(modes)}")
        return override
    return actors.get("select_by_scheme", {}).get(scheme_name, actors.get("default", "spec"))


# ── trace model ──────────────────────────────────────────────────────────────

class TraceModel:
    """Instructions by seq + SimSpect events + squash bookkeeping."""

    def __init__(self, events: List[dict], pv_seq: Dict[int, dict]):
        self.events = sorted(events, key=lambda e: (e["tick"], e["id"] if e["id"] is not None else -1))
        self.pv = pv_seq
        self.fill_ids = {e["id"] for e in events if e["kind"] == "fill" and e["id"] is not None}
        self.squashes = [e for e in self.events if e["struct"] == "ROB" and e["kind"] == "squash"]
        self.done = {}
        for e in self.events:
            if e["kind"] == "cleanup_done" and e["sq"] is not None:
                self.done.setdefault(e["sq"], e["tick"])
        ticks = [e["tick"] for e in events] + [max(r["fetch"], r["retire"]) for r in pv_seq.values()]
        self.sim_end = max(ticks) if ticks else 0
        # (tick, seq) observations: a seq existed at that tick. Seqs are
        # allocated monotonically, so seq <= max-seen-by-t ⇒ allocated by t.
        obs = [(r["fetch"], s) for s, r in pv_seq.items()]
        obs += [(e["tick"], e["seq"]) for e in events
                if e["seq"] is not None and e["kind"] != "squash"]
        obs.sort()
        self._obs_t = [t for t, _ in obs]
        pm, m = [], -1
        for _, s in obs:
            m = max(m, s)
            pm.append(m)
        self._obs_max = pm
        self._sq_cache: Dict[int, Optional[dict]] = {}
        self._vp_cache: Dict[int, tuple] = {}
        retired = sorted((s, r["retire"]) for s, r in pv_seq.items() if r["retire"] > 0)
        self._rob_head = {}
        run_max = 0
        for s, rt in retired:
            self._rob_head[s] = run_max
            run_max = max(run_max, rt)
        self._expose = {}
        for e in self.events:
            if e["kind"] in ("expose", "validate") and e["seq"] is not None:
                self._expose.setdefault(e["seq"], e["tick"])

    def max_seq_by(self, tick: int) -> int:
        import bisect
        i = bisect.bisect_right(self._obs_t, tick)
        return self._obs_max[i - 1] if i else -1

    def retired(self, seq: int) -> bool:
        r = self.pv.get(seq)
        return bool(r and r["retire"] > 0)

    def squash_of(self, seq: Optional[int]) -> Optional[dict]:
        """The ROB:squash that squashed `seq` (first squash, in time, whose
        squashing seq is older and which happened after `seq` was allocated)."""
        if seq is None:
            return None
        if seq in self._sq_cache:
            return self._sq_cache[seq]
        res = None
        if not self.retired(seq):
            for s in self.squashes:
                if s["seq"] is not None and s["seq"] < seq <= self.max_seq_by(s["tick"]):
                    res = s
                    break
        self._sq_cache[seq] = res
        return res

    def vp(self, seq: int):
        """InvisiSpec visibility point: (tick, basis)."""
        if seq in self._vp_cache:
            return self._vp_cache[seq]
        cands = []
        if seq in self._expose:
            cands.append((self._expose[seq], "expose/validate"))
        if seq in self._rob_head:
            cands.append((self._rob_head[seq], "rob_head"))
        res = min(cands) if cands else (INF, "never")
        self._vp_cache[seq] = res
        return res


# ── evaluation ───────────────────────────────────────────────────────────────

def _key(ev: dict, key_spec) -> Optional[int]:
    if isinstance(key_spec, dict):
        k = key_spec.get(ev["kind"], key_spec.get("default", "line"))
    else:
        k = key_spec or "line"
    return ev.get(k)


def _brief(ev: dict) -> dict:
    return {k: (hex(v) if k in ("line", "victim", "pc") and isinstance(v, int) else v)
            for k, v in ev.items() if k in ("id", "tick", "struct", "kind", "line", "seq",
                                             "pc", "victim", "cause", "sq")}


def evaluate(crit: dict, events: List[dict], pv_seq: Dict[int, dict],
             by_pc: Dict[int, list], lc_pc: Optional[int], fnc_pc: Optional[int],
             unresolved: List[dict], ticks_per_cycle: int, actor_mode: str) -> dict:
    tm = TraceModel(events, pv_seq)
    obs_structs = set(crit["observation"]["structures"])
    mode = crit["actors"]["modes"][actor_mode]
    impl = mode["impl"]

    lc_rec = best_record(by_pc.get(lc_pc, [])) if lc_pc else None
    fnc_rec = best_record(by_pc.get(fnc_pc, [])) if fnc_pc else None
    lc_retire = lc_rec["retire"] if lc_rec else 0
    fnc_retire = fnc_rec["retire"] if fnc_rec else 0
    lc_seq = None
    if lc_pc and lc_retire:
        cands = [s for s, r in pv_seq.items() if r["pc"] == lc_pc and r["retire"] == lc_retire]
        lc_seq = max(cands) if cands else None
    disqualified = (lc_pc is not None) and lc_retire == 0

    wspec = crit["window"].get("footprint", {})
    need_unres = wspec.get("branches_unresolved", True)
    _w_cache: Dict[int, bool] = {}

    def in_W(tick: int) -> bool:
        if tick in _w_cache:
            return _w_cache[tick]
        ok = (lc_retire == 0 or tick > lc_retire) and (fnc_retire == 0 or tick < fnc_retire)
        if ok and need_unres:
            ok, _ = check_branch_resolutions(by_pc, tick, unresolved, ticks_per_cycle)
        _w_cache[tick] = ok
        return ok

    def is_actor(seq) -> bool:
        if seq is None:
            return False
        if impl == "squashed_after_lc":
            return tm.squash_of(seq) is not None and (lc_seq is None or seq > lc_seq)
        if impl == "before_visibility_point":
            return True       # per-event test below
        raise ValueError(f"unknown actor impl {impl!r}")

    def actor_event_in_window(ev) -> bool:
        if impl == "before_visibility_point":
            return ev["tick"] < tm.vp(ev["seq"])[0]
        return in_W(ev["tick"])

    n_attr = sum(1 for e in events if e["seq"] is not None)
    unjoined = sorted({e["seq"] for e in events if e["seq"] is not None
                       and e["kind"] not in ("squash", "cleanup_done") and e["seq"] not in pv_seq})
    out = dict(criterion=crit.get("defense"), criterion_path=crit.get("_path"),
               actor_mode=actor_mode, lc_retire=lc_retire, fnc_retire=fnc_retire,
               lc_seq=lc_seq, lc_unretired_but_specified=disqualified,
               n_simspect_events=len(events), n_attributed_events=n_attr,
               n_unjoined_seqs=len(unjoined), unjoined_seqs=unjoined[:20],
               n_squashes=len(tm.squashes))

    form = crit["leak"]["form"]
    if form == "exists":
        res = _eval_exists(crit, tm, obs_structs, is_actor, actor_event_in_window, impl)
    elif form == "per_line_balance":
        res = _eval_balance(crit, tm, obs_structs, is_actor, in_W, lc_retire, fnc_retire, lc_seq)
    else:
        raise ValueError(f"unknown leak form {form!r}")
    out.update(res)
    if disqualified:
        out["leak"] = False
        out["terms_fired"] = []
        out["disqualified"] = "lc specified but never retired (same rule as check_ld)"
    out["issued_in_window"] = out["leak"] if out.get("decided", True) else out["issued_in_window"]
    if disqualified:
        out["issued_in_window"] = False
    out["in_window"] = out.get("in_window", False) and not disqualified
    return out


def _group(evs: List[dict], key_spec) -> List[dict]:
    g: Dict[tuple, dict] = {}
    for e in evs:
        k = (e["struct"], _key(e, key_spec))
        d = g.setdefault(k, dict(struct=k[0], line=hex(k[1]) if k[1] is not None else None,
                                 kinds=[], event_ids=[], seqs=[]))
        if e["kind"] not in d["kinds"]:
            d["kinds"].append(e["kind"])
        d["event_ids"].append(e["id"])
        if e["seq"] not in d["seqs"]:
            d["seqs"].append(e["seq"])
    return list(g.values())


def _eval_exists(crit, tm, obs, is_actor, in_window, impl) -> dict:
    term_name = crit["leak"]["term"]
    term = crit["terms"][term_name]
    kinds = set(term["kinds"])
    foot = [e for e in tm.events if e["struct"] in obs and e["kind"] in kinds and is_actor(e["seq"])]
    inw = [e for e in foot if in_window(e)]
    outw = [e for e in foot if not in_window(e)]
    offending = _group(inw, term.get("key"))
    if impl == "before_visibility_point":
        for d in offending:
            d["vp"] = {str(s): list(tm.vp(s)) for s in d["seqs"] if s is not None}
    return dict(leak=bool(inw), in_window=bool(inw), decided=True,
                terms_fired=[term_name] if inw else [],
                offending=offending,
                footprint_outside_window=_group(outw, term.get("key")),
                n_footprint_events=len(foot))


def _eval_balance(crit, tm, obs, is_actor, in_W, lc_retire, fnc_retire, lc_seq) -> dict:
    terms = crit["terms"]
    oblig = crit.get("undo_obligations", {s: ["install", "victim"] for s in obs})
    k_inst = set(terms["installed"]["kinds"]); k_ev = set(terms["evicted"]["kinds"])
    k_inv = set(terms["invalidated"]["kinds"]); k_rest = set(terms["restored"]["kinds"])
    k_rep = set(terms.get("reported_not_undo", {}).get("kinds", []))

    # undo windows per squash id
    undo = {}
    for s in tm.squashes:
        if s["sq"] is not None and (lc_seq is None or (s["seq"] is not None and s["seq"] >= lc_seq)):
            undo[s["sq"]] = (s["tick"], tm.done.get(s["sq"], tm.sim_end), s)

    def undo_sq_of(ev) -> Optional[int]:
        if ev["sq"] is not None:
            return ev["sq"] if ev["sq"] in undo else None
        for sq, (a, b, _) in undo.items():
            if a <= ev["tick"] <= b:
                return sq
        return None

    # cleanup side effects (excluded from the count; kept in the replay)
    restores = [e for e in tm.events if e["kind"] in k_rest and e["struct"] in obs]
    side = set()
    for e in tm.events:
        if e["kind"] == "fill" and e["struct"] in ("L2", "DIR"):
            for r in restores:
                sq = undo_sq_of(r)
                if sq is None:
                    continue
                a, b, _ = undo[sq]
                if r["line"] == e["line"] and r["tick"] <= e["tick"] <= b:
                    side.add(e["id"]); break
        elif e["kind"] == "evict" and e["struct"] == "L1D" and e["cause"] is not None \
                and e["cause"] not in tm.fill_ids:
            if any(a <= e["tick"] <= b for a, b, _ in undo.values()):
                side.add(e["id"])

    installed = defaultdict(list); evicted = defaultdict(list)
    invalidated = defaultdict(list); restored = defaultdict(list)
    churn = defaultdict(list); skipdrop = []
    live = defaultdict(list)          # (s, line) -> live actor fill events
    window_sqs = set()
    for sq, (a, b, s) in undo.items():
        if (lc_retire == 0 or a > lc_retire) and (fnc_retire == 0 or a <= fnc_retire):
            window_sqs.add(sq)
    actor_ids = set()
    for e in tm.events:
        st = e["struct"]
        if st not in obs:
            continue
        if e["id"] in side:
            continue
        kd = e["kind"]
        if kd in k_inst and is_actor(e["seq"]):
            installed[(st, e["line"])].append(e); live[(st, e["line"])].append(e)
            actor_ids.add(e["id"])
            if in_W(e["tick"]):
                sqd = tm.squash_of(e["seq"])
                if sqd is not None and sqd["sq"] in undo:
                    window_sqs.add(sqd["sq"])
        elif kd in k_ev and is_actor(e["seq"]):
            actor_ids.add(e["id"])
            k = (st, e["victim"])
            if live[k]:
                f = live[k].pop()
                churn[k].append((f, e))
            else:
                evicted[k].append(e)
                if in_W(e["tick"]):
                    sqd = tm.squash_of(e["seq"])
                    if sqd is not None and sqd["sq"] in undo:
                        window_sqs.add(sqd["sq"])
        elif kd in k_inv and undo_sq_of(e) is not None:
            invalidated[(st, e["line"])].append(e)
            live[(st, e["line"])] = []      # cleanup removes the line: later evicts of it can't churn
        elif kd in k_rest and undo_sq_of(e) is not None:
            restored[(st, e["line"])].append(e)
        elif kd in k_rep and undo_sq_of(e) is not None:
            skipdrop.append(_brief(e))

    keys = set(installed) | set(evicted) | set(invalidated) | set(restored) | set(churn)
    per_line, under, over, under_out, over_out = [], [], [], [], []
    for k in sorted(keys, key=lambda k: (k[0], k[1] if k[1] is not None else -1)):
        st, ln = k
        ob = oblig.get(st, [])
        n_ch = len(churn.get(k, []))
        n_inst = len(installed.get(k, [])); n_ev = len(evicted.get(k, []))
        n_inv = len(invalidated.get(k, [])); n_rest = len(restored.get(k, []))
        d_inst = (n_inst - n_ch) - n_inv if "install" in ob else 0
        d_vic = n_ev - n_rest if "victim" in ob else 0
        foot_inw = any(in_W(e["tick"]) for e in installed.get(k, []) + evicted.get(k, []))
        cl_sqs = {undo_sq_of(e) for e in invalidated.get(k, []) + restored.get(k, [])}
        rec = dict(struct=st, line=hex(ln) if ln is not None else None,
                   installed=n_inst, invalidated=n_inv, evicted=n_ev, restored=n_rest,
                   churn_cancelled=n_ch, d_install=d_inst, d_victim=d_vic,
                   footprint_in_window=foot_inw,
                   event_ids=sorted(e["id"] for e in installed.get(k, []) + evicted.get(k, [])
                                    + invalidated.get(k, []) + restored.get(k, [])),
                   victims_benign=(n_ev if "victim" not in ob else 0))
        per_line.append(rec)
        if d_inst > 0 or d_vic > 0:
            (under if foot_inw else under_out).append(rec)
        if d_inst < 0 or d_vic < 0:
            (over if (cl_sqs & window_sqs) else over_out).append(rec)

    count_leak_keys = {(r["struct"], r["line"]) for r in under + over}
    # ── net-state replay cross-check ────────────────────────────────────────
    cleanup_ids = {e["id"] for v in list(invalidated.values()) + list(restored.values()) for e in v}
    actor_l2_evict_benign = {e["id"] for v in evicted.values() for e in v
                             if "victim" not in oblig.get(e["struct"], [])}

    def replay(reference: bool):
        pres = {s: set() for s in obs}
        for e in tm.events:
            st = e["struct"]
            if st not in obs:
                continue
            if reference and (e["id"] in actor_ids or e["id"] in cleanup_ids or e["id"] in side):
                continue
            if not reference and e["id"] in actor_l2_evict_benign:
                continue
            kd = e["kind"]
            if kd in ("fill", "cleanup_restore") and e["line"] is not None:
                pres[st].add(e["line"])
            elif kd == "evict" and e["victim"] is not None:
                pres[st].discard(e["victim"])
            elif kd in ("inv", "cleanup_inv") and e["line"] is not None:
                pres[st].discard(e["line"])
        return pres

    act, ref = replay(False), replay(True)
    net_leak, net_out = [], []
    for st in sorted(obs):
        for ln in sorted(act[st] ^ ref[st]):
            k = (st, ln)
            foot = installed.get(k, []) + evicted.get(k, [])
            if foot and not any(in_W(e["tick"]) for e in foot):
                net_out.append(dict(struct=st, line=hex(ln), present_actual=ln in act[st]))
            else:
                net_leak.append(dict(struct=st, line=hex(ln), present_actual=ln in act[st]))
    net_keys = {(r["struct"], r["line"]) for r in net_leak}
    inconsistent = net_keys != count_leak_keys
    count_leak = bool(under or over)
    net = bool(net_leak)
    fired = (["under_clean"] if under else []) + (["over_clean"] if over else [])
    offending = [dict(struct=r["struct"], line=r["line"], event_ids=r["event_ids"],
                      term=("under_clean" if (r["d_install"] > 0 or r["d_victim"] > 0) else "over_clean"))
                 for r in under + over]
    return dict(leak=count_leak, decided=not inconsistent,
                issued_in_window=(count_leak or net) if inconsistent else count_leak,
                in_window=any(r["footprint_in_window"] for r in per_line),
                terms_fired=fired, offending=offending, per_line=per_line,
                under_clean_outside_window=under_out, over_clean_outside_window=over_out,
                skip_drop=skipdrop, cleanup_side_effects=sorted(side),
                net_state=dict(leak=net, differing=net_leak, outside_window=net_out),
                inconsistent=inconsistent,
                window_squashes=sorted(window_sqs))


# ── trace-level entry points ─────────────────────────────────────────────────

def evaluate_trace(trace_path, crit: dict, lc_pc=None, fnc_pc=None, unresolved=None,
                   ticks_per_cycle: int = 500, actor_mode: Optional[str] = None,
                   scheme_name: str = "") -> dict:
    trace_path = Path(trace_path)
    events = parse_simspect_events(trace_path)
    if actor_mode is None:
        actor_mode = select_actor_mode(crit, scheme_name, os.environ.get("SIMSPECT_CRITERION_ACTOR"))
    if not events:
        return dict(status="warn", leak=None, issued_in_window=None, in_window=None,
                    criterion=crit.get("defense"), actor_mode=actor_mode,
                    error="no O3PipeView:simspect lines in the trace: this gem5 build lacks the "
                          "SimSpect hooks (wiki/design/SIMSPECT_HOOKS.md); cannot decide")
    return evaluate(crit, events, parse_pipeview_by_seq(trace_path), parse_pipeview(trace_path),
                    lc_pc, fnc_pc, list(unresolved or []), ticks_per_cycle, actor_mode)


_CRIT: Optional[dict] = None
_ACTOR_OVERRIDE: Optional[str] = None


def check_footprint(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle,
                    lsq_by_pc=None, squash_by_pc=None, trace_path=None):
    """gem5_common.process_one check_fn (wants_trace=True)."""
    import gem5_common as gc
    extra = [a for a in os.environ.get("SIMSPECT_GEM5_EXTRA", "").split("\x1f") if a]
    scheme = scheme_name_from_args(extra, gc._scheme)
    mode = select_actor_mode(_CRIT, scheme, _ACTOR_OVERRIDE)
    r = evaluate_trace(trace_path, _CRIT, lc_pc, fnc_pc, unresolved, ticks_per_cycle,
                       actor_mode=mode, scheme_name=scheme)
    r["scheme_name"] = scheme
    return r


check_footprint.wants_trace = True


def _pop_opt(argv: List[str], name: str) -> Optional[str]:
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            v = argv[i + 1]; del argv[i:i + 2]; return v
        if a.startswith(name + "="):
            del argv[i]; return a.split("=", 1)[1]
    return None


def main():
    global _CRIT, _ACTOR_OVERRIDE
    argv = sys.argv
    crit_path = _pop_opt(argv, "--criterion") or os.environ.get("SIMSPECT_CRITERION")
    _ACTOR_OVERRIDE = _pop_opt(argv, "--actor") or os.environ.get("SIMSPECT_CRITERION_ACTOR")
    trace = _pop_opt(argv, "--trace")
    meta = _pop_opt(argv, "--meta")
    if not crit_path:
        sys.exit("error: no criterion: pass --criterion specs/leakage/<defense>.json "
                 "or set gem5.criterion in the run config (SIMSPECT_CRITERION)")
    _CRIT = load_criterion(crit_path)
    if trace:
        m = json.loads(Path(meta).read_text()) if meta else {}
        scheme = scheme_name_from_args(m.get("cmd", "").split())
        r = evaluate_trace(trace, _CRIT, m.get("lc_pc"), m.get("fnc_pc"), m.get("unresolved", []),
                           m.get("ticks_per_cycle", 500),
                           actor_mode=select_actor_mode(_CRIT, scheme, _ACTOR_OVERRIDE),
                           scheme_name=scheme)
        out = _pop_opt(argv, "--out")
        txt = json.dumps(r, indent=2, default=str)
        if out:
            Path(out).write_text(txt)
        print(json.dumps({k: r.get(k) for k in ("criterion", "actor_mode", "leak", "decided",
                                                "terms_fired", "inconsistent")}, default=str))
        return
    run_batch(check_footprint, description=f"footprint criterion {_CRIT.get('defense')} "
                                           f"({crit_path})")


if __name__ == "__main__":
    main()
