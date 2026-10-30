#!/usr/bin/env python3
"""
apply_resolve_hooks.py — add the SimSpect branch-resolution hooks to one gem5 tree.

Three edits, all anchored on the existing SimSpect branch hooks (BTB override,
resolve stall) so they apply to every hooked build (old cwfletcher/SPT/amulet
template trees and the gem5-22 trees recon-modded / SpecLFB):

  1. bpred_unit.cc, in the existing btbForcedTargets override:
       forced target == 1 (SIMSPECT_FORCE_NOT_TAKEN) now forces a NOT-TAKEN
       (fall-through) prediction; any other value still forces taken to it.
       Prints  O3PipeView:simspect:<tick>:BR:predict_force:...:taken=%d:target=%#x
  2. IEW resolve-stall hook: print-only lines
       resolve_hold    when the stall is scheduled (stall, fire tick, mispred)
       resolve_drop    the branch was squashed before release (never resolves)
       resolve_release IEW releases the branch (setExecuted + instToCommit)
       resolve_bcast   the release broadcast a mispredict squash
  3. commit markCompletedInsts, right after setCanCommit(), for control insts:
       resolve_visible the tick the defense sees the branch resolved
                       (upc, mispred, stall registered for this PC)

Edits 2-3 only print. Edit 1 changes behaviour only for target==1, which no
annotation used before 2026-10-30 (a real PC is never 1). Lines follow
wiki/design/SIMSPECT_HOOKS.md and parse with gem5_common.parse_simspect_line.

Usage:  apply_resolve_hooks.py <gem5-root> [--dry-run]
Idempotent: a file that already carries the marker is left alone.
Design + verification: wiki/design/RESOLUTION_HOOKS.md.
"""

import re
import sys
from pathlib import Path

MARK = "SimSpect resolve hooks (2026-10-30)"
SIM = 'O3PipeView:simspect:%llu:BR:'
COMMON = ':line=-:seq=%llu:pc=%#llx:victim=-:cause=-:sq=-:id=-'


def _pr(kind, extra_fmt, args, indent):
    """One DPRINTFR line; args are C expressions after tick/seq/pc."""
    fmt = SIM + kind + COMMON + extra_fmt + '\\n'
    return (f'{indent}DPRINTFR(O3PipeView, "{fmt}",\n{indent}         '
            + ",\n{indent}         ".replace("{indent}", indent).join(args) + ");\n")


def _sub_once(text, pattern, repl, what, flags=0):
    new, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"anchor not found: {what}")
    return new


def patch_bpred(text):
    inc = ('#include "debug/O3PipeView.hh"  // ' + MARK + '\n'
           '#include "sim/core.hh"\n')
    text = _sub_once(text, r'(#include "debug/Branch.hh"\n)', r'\1' + inc, "bpred include")
    tick = "(unsigned long long)curTick()"
    seq = "(unsigned long long)seqNum"
    bpc = "(unsigned long long)pc.instAddr()"
    # Old template trees: TheISA::PCState target.
    old = re.search(r'\n(\s*)target\.set\(it->second\);\n\s*pred_taken = true;\n'
                    r'\s*predict_record\.predTaken = true;\n', text)
    if old:
        i = old.group(1)
        pr = _pr("predict_force", ":taken=%d:target=%#llx",
                 [tick, seq, bpc, "(int)pred_taken",
                  "(unsigned long long)target.instAddr()"], i)
        body = (f"\n{i}// {MARK}: forced target 1 = predict not-taken (fall-through).\n"
                f"{i}if (it->second == 1) {{\n"
                f"{i}    target = pc;\n{i}    TheISA::advancePC(target, inst);\n"
                f"{i}    pred_taken = false;\n{i}    predict_record.predTaken = false;\n"
                f"{i}}} else {{\n"
                f"{i}    target.set(it->second);\n{i}    pred_taken = true;\n"
                f"{i}    predict_record.predTaken = true;\n{i}}}\n" + pr)
        return text[:old.start()] + body + text[old.end():]
    # gem5-22 trees: std::unique_ptr<PCStateBase> target.
    tgt = "(unsigned long long)target->instAddr()"
    rec = re.search(r'\n(\s*)target->setInstAddr\(forced\);\n\s*pred_taken = true;\n'
                    r'\s*predict_record\.predTaken = pred_taken;\n', text)
    lfb = re.search(r'\n(\s*)target->as<X86ISA::PCState>\(\)\.set\(it->second\);\n'
                    r'\s*pred_taken = true;\n\s*predict_record\.predTaken = true;\n', text)
    m = rec or lfb
    if not m:
        raise SystemExit("anchor not found: btbForcedTargets override")
    i = m.group(1)
    taken_stmt = ("target->setInstAddr(forced);" if rec
                  else "target->as<X86ISA::PCState>().set(it->second);")
    pr = _pr("predict_force", ":taken=%d:target=%#llx",
             [tick, seq, bpc, "(int)pred_taken", tgt], i)
    body = (f"\n{i}// {MARK}: forced target 1 = predict not-taken (fall-through).\n"
            f"{i}if (it->second == 1) {{\n"
            f"{i}    target.reset(pc.clone());\n{i}    inst->advancePC(*target);\n"
            f"{i}    pred_taken = false;\n{i}    predict_record.predTaken = false;\n"
            f"{i}}} else {{\n"
            f"{i}    {taken_stmt}\n{i}    pred_taken = true;\n"
            f"{i}    predict_record.predTaken = true;\n{i}}}\n" + pr)
    return text[:m.start()] + body + text[m.end():]


def patch_iew(text):
    tick = "(unsigned long long)curTick()"
    if "[this, stall_inst, stall_tid]" in text:          # old trees + SpecLFB
        v, cyc = "stall_inst", "stall"
        hold_anchor = r'\n(\s*)cpu->schedule\(new EventFunctionWrapper\(\s*\n\s*\[this, stall_inst, stall_tid\]'
        drop_pat = r'(\n(\s*))if \(stall_inst->isSquashed\(\)\) return;'
        rel_pat = r'(\n(\s*))stall_inst->setExecuted\(\); instToCommit\(stall_inst\);'
        bc_pat = r'(\n(\s*))squashDueToBranch\(stall_inst, stall_tid\);'
    elif "[this, inst, tid_local]" in text:               # gem5-recon-modded
        v, cyc = "inst", "stallCycles"
        hold_anchor = r'\n(\s*)auto \*ev = new EventFunctionWrapper\(\s*\n\s*\[this, inst, tid_local\]'
        drop_pat = r'(\n(\s*))if \(inst->isSquashed\(\)\) \{\n\s*return;\n\s*\}'
        rel_pat = r'(\n(\s*))inst->setExecuted\(\);\n\s*instToCommit\(inst\);'
        bc_pat = r'(\n(\s*))squashDueToBranch\(inst, tid_local\);'
    else:
        raise SystemExit("anchor not found: resolve-stall lambda")
    seq = f"(unsigned long long){v}->seqNum"
    pc = f"(unsigned long long){v}->pcState().instAddr()"
    m = re.search(hold_anchor, text)
    if not m:
        raise SystemExit("anchor not found: stall schedule")
    i = m.group(1)
    hold = (f"\n{i}// {MARK}\n" + _pr(
        "resolve_hold", ":stall=%llu:fire=%llu:mispred=%d",
        [tick, "(unsigned long long)inst->seqNum",
         "(unsigned long long)inst->pcState().instAddr()",
         f"(unsigned long long){cyc}", f"(unsigned long long)cpu->clockEdge({cyc})",
         "(int)inst->mispredicted()"], i)).rstrip("\n")
    # The lambda edits below only search after the branch hook, so they can
    # never land on another deferred-event lambda earlier in the file (recon-
    # modded has a dead store-stall placeholder with the same body).
    head, text = text[:m.start()] + hold, text[m.start():]

    def drop_repl(mm):
        ind = mm.group(2)
        return (f"{mm.group(1)}if ({v}->isSquashed()) {{\n"
                + _pr("resolve_drop", "", [tick, seq, pc], ind + "    ")
                + f"{ind}    return;\n{ind}}}")
    text = _sub_once(text, drop_pat, drop_repl, "lambda squashed early return")

    def rel_repl(mm):
        return (mm.group(0) + "\n"
                + _pr("resolve_release", ":mispred=%d", [tick, seq, pc,
                      f"(int){v}->mispredicted()"], mm.group(2)).rstrip("\n"))
    text = _sub_once(text, rel_pat, rel_repl, "lambda release")

    def bc_repl(mm):
        return (mm.group(0) + "\n"
                + _pr("resolve_bcast", "", [tick, seq, pc], mm.group(2)).rstrip("\n"))
    return head + _sub_once(text, bc_pat, bc_repl, "lambda squash broadcast")


def patch_commit(text):
    m = re.search(r'\n(\s*)fromIEW->insts\[inst_num\]->setCanCommit\(\);\n', text)
    if not m:
        raise SystemExit("anchor not found: setCanCommit")
    i = m.group(1)
    x = "fromIEW->insts[inst_num]"
    stall = (f"(unsigned long long)(cpu->getBranchPred() ? (uint64_t)cpu->getBranchPred()"
             f"->getResolveStallCyclesFor({x}->pcState().instAddr()) : 0)")
    body = (f"{m.group(0)}{i}// {MARK}\n{i}if ({x}->isControl()) {{\n"
            + _pr("resolve_visible", ":upc=%d:mispred=%d:stall=%llu",
                  ["(unsigned long long)curTick()", f"(unsigned long long){x}->seqNum",
                   f"(unsigned long long){x}->pcState().instAddr()",
                   f"(int){x}->pcState().microPC()", f"(int){x}->mispredicted()", stall],
                  i + "    ")
            + f"{i}}}\n")
    return text[:m.start()] + body + text[m.end():]


def main():
    root = Path(sys.argv[1])
    dry = "--dry-run" in sys.argv
    o3 = root / "src/cpu/o3"
    files = {
        root / "src/cpu/pred/bpred_unit.cc": patch_bpred,
        (o3 / "iew_impl.hh" if (o3 / "iew_impl.hh").exists() else o3 / "iew.cc"): patch_iew,
        (o3 / "commit_impl.hh" if (o3 / "commit_impl.hh").exists() else o3 / "commit.cc"): patch_commit,
    }
    for path, fn in files.items():
        text = path.read_text()
        if MARK in text:
            print(f"already patched: {path}")
            continue
        new = fn(text)
        print(f"{'would patch' if dry else 'patched'}: {path} (+{new.count(chr(10)) - text.count(chr(10))} lines)")
        if not dry:
            path.write_text(new)


if __name__ == "__main__":
    main()
