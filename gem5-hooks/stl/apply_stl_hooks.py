#!/usr/bin/env python3
"""
apply_stl_hooks.py — insert the SimSpect-STL hooks into a gem5 O3 tree.

Two hooks (design: wiki/design/STL_SPECULATION.md):

  1. Store address-generation hold (--stl-ann-file + --stl-store-stall-cycles).
     In IEW::executeInsts, an annotated store PC is not allowed to compute its
     address until N cycles after it first issues. It goes back to the memory
     dependence unit's replay list (IEW::rescheduleMemInst, the same path the LSQ
     uses for a load it can't execute yet) and a scheduled event replays it when
     the hold ends. While it is held its store-queue entry has size 0, so a
     younger load's forwarding scan skips it (LSQUnit::read): the bypass. When it
     finally executes, LSQUnit::checkViolations finds the aliasing load and IEW
     squashes from it (squashDueToMemOrder): the window end.

  2. Memory-dependence prediction override (--stl-alias-pred), per annotated
     bypass load PC, in MemDepUnit::insert:
       no_alias  (1) the predictor's answer is ignored, the load never waits:
                     the false-negative alias prediction (the primitive).
       alias     (2) the store and its paired loads are put in one store set
                     before the store enters the LFST, so the load waits for the
                     store: the false-positive control (no window should open).
       off       (0) unmodified store sets.

Print-only trace lines (O3PipeView flag, wiki/design/SIMSPECT_HOOKS.md format):
  O3PipeView:simspect:<tick>:STL:stl_hold:...:seq=<store sn>:pc=<store pc>:...
  O3PipeView:simspect:<tick>:STL:stl_release:...                     (hold over, store executes)
  O3PipeView:simspect:<tick>:STL:pred_no_alias|pred_alias:...:seq=<load sn>:pc=<load pc>:...:cause=<dep sn>
  O3PipeView:simspect:<tick>:STL:mem_order_squash:...:seq=<violator load sn>:pc=<load pc>:...:cause=<store sn>
(mem_order_squash prints for every memory-order violation, annotated or not.)

Each edit is located by an anchor string, not a line number, so the script works
on drifted trees (Recon's o3 files are heavily modified). Every inserted block
carries the marker "SimSpect-STL"; a file that already has it is skipped, so the
script is idempotent. Nothing is written unless every anchor in every file is
found exactly once.

Usage:
  apply_stl_hooks.py <gem5_root> --dry-run     # check anchors, change nothing
  apply_stl_hooks.py <gem5_root>               # apply; originals saved as <file>.pre-stl
After applying: rebuild (scons build/X86/gem5.opt). The new CLI flags are inert
unless --stl-ann-file is given, so other runs on the same binary are unaffected.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

MARK = "SimSpect-STL"

# (relative file, anchor, mode, text). mode: "after" inserts text after the
# anchor, "before" inserts it before, "replace" swaps the anchor for text.
EDITS: list[tuple[str, str, str, str]] = [
    # ---- params ------------------------------------------------------------
    ("src/cpu/o3/BaseO3CPU.py",
     '    SSITSize = Param.Unsigned(1024, "Store set ID table size")\n',
     "after",
     '''
    # SimSpect-STL hooks (gem5-hooks/stl/, wiki/design/STL_SPECULATION.md)
    stlStallStorePCs = VectorParam.Addr([], "SimSpect-STL: store PCs whose "
        "address generation is held for stlStoreStallCycles")
    stlStoreStallCycles = Param.Unsigned(0, "SimSpect-STL: cycles to hold an "
        "annotated store before it computes its address (0 = off)")
    stlAliasLoadPCs = VectorParam.Addr([], "SimSpect-STL: annotated bypass "
        "load PCs, index-paired with stlAliasStorePCs")
    stlAliasStorePCs = VectorParam.Addr([], "SimSpect-STL: the store PC each "
        "annotated load truly aliases")
    stlAliasPred = Param.Unsigned(0, "SimSpect-STL: memory-dependence "
        "prediction for annotated loads: 0 = unmodified store sets, "
        "1 = no alias (false negative), 2 = alias (false positive control)")
'''),

    # ---- hook 1: store address-generation hold (IEW) -------------------------
    ("src/cpu/o3/iew.hh",
     "#include <set>\n",
     "after",
     "#include <unordered_map>  // SimSpect-STL\n#include <unordered_set>  // SimSpect-STL\n"),
    ("src/cpu/o3/iew.hh",
     "    bool fetchRedirect[MaxThreads];\n",
     "after",
     '''
    /** SimSpect-STL: store PCs whose address generation is held. */
    std::unordered_set<Addr> stlStallStorePCs;
    /** SimSpect-STL: hold length (0 = hook off). */
    Cycles stlStoreStallCycles;
    /** SimSpect-STL: held store seqNum -> tick its hold ends. */
    std::unordered_map<InstSeqNum, Tick> stlHoldUntil;
'''),
    ("src/cpu/o3/iew.cc",
     "    // Setup wire to read instructions coming from issue.\n",
     "before",
     '''    // SimSpect-STL: store address-generation hold (--stl-ann-file)
    stlStallStorePCs.insert(params.stlStallStorePCs.begin(),
                            params.stlStallStorePCs.end());
    stlStoreStallCycles = Cycles(params.stlStoreStallCycles);

'''),
    ("src/cpu/o3/iew.cc",
     "            } else if (inst->isStore()) {\n"
     "                fault = ldstQueue.executeStore(inst);\n",
     "replace",
     '''            } else if (inst->isStore()) {
                // SimSpect-STL: hold an annotated store's address generation
                // for stlStoreStallCycles after it first issues. It goes back
                // to the mem-dep replay list (as the LSQ does for a load it
                // can't execute yet); an event replays it when the hold ends.
                // An early replay (MemDepUnit::replay replays every waiting
                // mem op) just re-defers it until then.
                if (stlStoreStallCycles > 0 &&
                        stlStallStorePCs.count(inst->pcState().instAddr())) {
                    auto held = stlHoldUntil.find(inst->seqNum);
                    if (held == stlHoldUntil.end()) {
                        Tick until = cpu->clockEdge(stlStoreStallCycles);
                        stlHoldUntil[inst->seqNum] = until;
                        DPRINTFR(O3PipeView, "O3PipeView:simspect:%llu:STL:"
                            "stl_hold:line=-:seq=%llu:pc=%#x:victim=-:"
                            "cause=-:sq=-:id=-\\n", curTick(), inst->seqNum,
                            inst->pcState().instAddr());
                        auto *ev = new EventFunctionWrapper(
                            [this, inst]() {
                                if (inst->isSquashed())
                                    return;
                                replayMemInst(inst);
                                cpu->wakeCPU();
                            },
                            "iew.simspectStlStoreRelease",
                            true);  // deleteOnFire
                        cpu->schedule(ev, until);
                        rescheduleMemInst(inst);
                        continue;
                    } else if (curTick() < held->second) {
                        rescheduleMemInst(inst);
                        continue;
                    }
                    DPRINTFR(O3PipeView, "O3PipeView:simspect:%llu:STL:"
                        "stl_release:line=-:seq=%llu:pc=%#x:victim=-:"
                        "cause=-:sq=-:id=-\\n", curTick(), inst->seqNum,
                        inst->pcState().instAddr());
                }
                fault = ldstQueue.executeStore(inst);
'''),
    ("src/cpu/o3/iew.cc",
     "                squashDueToMemOrder(violator, tid);\n",
     "before",
     '''                // SimSpect-STL: window end for store-to-load speculation
                DPRINTFR(O3PipeView, "O3PipeView:simspect:%llu:STL:"
                    "mem_order_squash:line=-:seq=%llu:pc=%#x:victim=-:"
                    "cause=%llu:sq=-:id=-\\n", curTick(), violator->seqNum,
                    violator->pcState().instAddr(), inst->seqNum);
'''),

    # ---- hook 2: memory-dependence prediction override (MemDepUnit) ----------
    ("src/cpu/o3/mem_dep_unit.hh",
     "    StoreSet depPred;\n",
     "after",
     '''
    /** SimSpect-STL: prediction override for annotated loads
     * (0 = off, 1 = no alias, 2 = alias). */
    unsigned stlAliasPred = 0;
    /** SimSpect-STL: annotated bypass load PCs. */
    std::unordered_set<Addr> stlAliasLoadPCs;
    /** SimSpect-STL: store PC -> the bypass load PCs it truly aliases. */
    std::unordered_multimap<Addr, Addr> stlAliasStoreToLoads;
'''),
    ("src/cpu/o3/mem_dep_unit.cc",
     '#include "debug/MemDepUnit.hh"\n',
     "after",
     '#include "debug/O3PipeView.hh"  // SimSpect-STL\n'),
    ("src/cpu/o3/mem_dep_unit.cc",
     "    depPred.init(params.store_set_clear_period, params.SSITSize,\n"
     "            params.LFSTSize);\n",
     "after",
     '''
    // SimSpect-STL: memory-dependence prediction override (--stl-alias-pred)
    stlAliasPred = params.stlAliasPred;
    if (params.stlAliasLoadPCs.size() != params.stlAliasStorePCs.size())
        fatal("SimSpect-STL: stlAliasLoadPCs and stlAliasStorePCs differ in "
              "length (%u vs %u)", params.stlAliasLoadPCs.size(),
              params.stlAliasStorePCs.size());
    for (size_t i = 0; i < params.stlAliasLoadPCs.size(); ++i) {
        stlAliasLoadPCs.insert(params.stlAliasLoadPCs[i]);
        stlAliasStoreToLoads.emplace(params.stlAliasStorePCs[i],
                                     params.stlAliasLoadPCs[i]);
    }
'''),
    ("src/cpu/o3/mem_dep_unit.cc",
     "MemDepUnit::insert(const DynInstPtr &inst)\n{\n    ThreadID tid = inst->threadNumber;\n",
     "after",
     '''
    // SimSpect-STL (alias control): put an annotated store and its paired
    // loads in one store set BEFORE the store enters the LFST (insertStore
    // below), so the paired load's checkInst returns this store.
    if (stlAliasPred == 2 && inst->isStore()) {
        auto range =
            stlAliasStoreToLoads.equal_range(inst->pcState().instAddr());
        for (auto it = range.first; it != range.second; ++it)
            depPred.violation(it->first, it->second);
    }
'''),
    ("src/cpu/o3/mem_dep_unit.cc",
     "        InstSeqNum dep = depPred.checkInst(inst->pcState().instAddr());\n",
     "after",
     '''        // SimSpect-STL: forced prediction for an annotated bypass load
        if (stlAliasPred != 0 && inst->isLoad() &&
                stlAliasLoadPCs.count(inst->pcState().instAddr())) {
            if (stlAliasPred == 1)
                dep = 0;  // no alias (false negative): never wait
            DPRINTFR(O3PipeView, "O3PipeView:simspect:%llu:STL:%s:line=-:"
                "seq=%llu:pc=%#x:victim=-:cause=%llu:sq=-:id=-\\n", curTick(),
                stlAliasPred == 1 ? "pred_no_alias" : "pred_alias",
                inst->seqNum, inst->pcState().instAddr(), dep);
        }
'''),
    ("src/cpu/o3/mem_dep_unit.cc",
     "        producing_stores.insert(std::end(producing_stores),\n"
     "                                std::begin(loadBarrierSNs),\n"
     "                                std::end(loadBarrierSNs));\n",
     "after",
     '''        // SimSpect-STL: a load barrier (the litmus setup mfence) is in
        // flight, so gem5 makes this load wait on the barrier and never asks
        // the predictor. Apply the forced prediction here too: alias mode adds
        // the store-set dependence the predictor branch would have added;
        // no_alias has nothing to drop (a barrier wait is not a prediction).
        if (stlAliasPred != 0 && inst->isLoad() &&
                stlAliasLoadPCs.count(inst->pcState().instAddr())) {
            InstSeqNum dep = 0;
            if (stlAliasPred == 2) {
                dep = depPred.checkInst(inst->pcState().instAddr());
                if (dep != 0)
                    producing_stores.push_back(dep);
            }
            DPRINTFR(O3PipeView, "O3PipeView:simspect:%llu:STL:%s:line=-:"
                "seq=%llu:pc=%#x:victim=-:cause=%llu:sq=-:id=-:via=barrier\\n",
                curTick(), stlAliasPred == 1 ? "pred_no_alias" : "pred_alias",
                inst->seqNum, inst->pcState().instAddr(), dep);
        }
'''),

    # ---- configs -------------------------------------------------------------
    ("configs/common/Options.py",
     "def addFSOptions(parser):\n",
     "before",
     '''    # SimSpect-STL hooks (gem5-hooks/stl/). Inert unless --stl-ann-file is set.
    parser.add_argument("--stl-ann-file", default="",
                        help="SimSpect-STL: test .ann.json; its "
                             "stl_annotations give (store_addr, load_addr) pairs")
    parser.add_argument("--stl-store-stall-cycles", type=int, default=0,
                        help="SimSpect-STL: cycles each annotated store's "
                             "address generation is held (0 = no hold)")
    parser.add_argument("--stl-alias-pred", default="no_alias",
                        choices=["off", "no_alias", "alias"],
                        help="SimSpect-STL: memory-dependence prediction for "
                             "the annotated loads: no_alias = false negative "
                             "(the primitive), alias = false positive (control)")


'''),
    ("configs/example/se.py",
     "    system.cpu[i].createThreads()\n",
     "before",
     '''    # SimSpect-STL hooks (gem5-hooks/stl/)
    if args.stl_ann_file:
        import json as _stl_json
        with open(args.stl_ann_file) as _f:
            _stl = _stl_json.load(_f).get("stl_annotations", [])
        _st = [int(e["store_addr"]) for e in _stl if "store_addr" in e and "load_addr" in e]
        _ld = [int(e["load_addr"]) for e in _stl if "store_addr" in e and "load_addr" in e]
        if len(_st) != len(_stl):
            warn("--stl-ann-file: %d stl_annotations entries lack store_addr/"
                 "load_addr (run compile_annotate.py); skipped" %
                 (len(_stl) - len(_st)))
        system.cpu[i].stlStallStorePCs = sorted(set(_st))
        system.cpu[i].stlStoreStallCycles = args.stl_store_stall_cycles
        system.cpu[i].stlAliasLoadPCs = _ld
        system.cpu[i].stlAliasStorePCs = _st
        system.cpu[i].stlAliasPred = {"off": 0, "no_alias": 1, "alias": 2}[args.stl_alias_pred]
        print("[se.py] SimSpect-STL: %d store/load pairs from %s, store hold "
              "%d cycles, alias pred %s" % (len(_st), args.stl_ann_file,
              args.stl_store_stall_cycles, args.stl_alias_pred))

'''),
]


def apply(root: Path, dry_run: bool) -> int:
    by_file: dict[str, list] = {}
    for rel, anchor, mode, text in EDITS:
        by_file.setdefault(rel, []).append((anchor, mode, text))

    plans: dict[Path, str] = {}
    problems: list[str] = []
    for rel, edits in by_file.items():
        path = root / rel
        if not path.exists():
            problems.append(f"missing file: {rel}")
            continue
        src = path.read_text()
        if MARK in src:
            print(f"[skip] {rel}: already has {MARK} hooks")
            continue
        new = src
        for anchor, mode, text in edits:
            n = new.count(anchor)
            if n != 1:
                problems.append(f"{rel}: anchor found {n}x (need 1): {anchor.strip()[:70]!r}")
                continue
            if mode == "after":
                new = new.replace(anchor, anchor + text)
            elif mode == "before":
                new = new.replace(anchor, text + anchor)
            else:
                new = new.replace(anchor, text)
        plans[path] = new

    if problems:
        print("NOT APPLIED — fix these first:")
        for p in problems:
            print("  " + p)
        return 1
    for path, new in plans.items():
        print(f"[{'would edit' if dry_run else 'edit'}] {path.relative_to(root)}")
        if not dry_run:
            backup = path.with_name(path.name + ".pre-stl")
            if not backup.exists():
                shutil.copy2(path, backup)
            path.write_text(new)
    print("dry run: nothing written" if dry_run else "done — rebuild gem5")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gem5_root", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.exit(apply(args.gem5_root.resolve(), args.dry_run))


if __name__ == "__main__":
    main()
