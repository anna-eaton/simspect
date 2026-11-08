#!/usr/bin/env python3
"""
make_rmw_corpus.py: derive the disjoint RMW corpus (STT_6_rmw) from an existing
concretized testset by post-processing its .s files. parsexml.py, the
instruction tables and the source testset are never touched.

Design: wiki/design/VOCAB_TABLES.md, "RMW agent findings (2026-11-08)" route (d)
and "### RMW disjoint corpus (2026-11-08)" (how to regenerate). Decided by Anna
2026-11-08: RMW tests are a separate testset that never mixes into STT_6.

Rewrite rule (only rule): for a test whose transmitter kind is `ld`, the single
instruction inside the transmitter's inline-asm block, right after the marker
label __litmus_<stem>_pc<xmit.pc>:, must be `movq <mem>, %<reg64>`. It becomes
`orq $0, <mem>` (value-neutral RMW on the same address: gem5 OR_M_I =
limm; ldst; or; st). The marker label stays on the instruction.

Gates (a test failing any gate is SKIPPED with a reason, never guessed):
  * xmit kind is ld; the bare annotation (llvm/<stem>.ann.json) and the XML exist;
  * the marker label occurs exactly once and its asm block holds exactly one
    instruction of the form above;
  * XML: no rf edge leaves the transmitter's outreg (no Alloy-level consumer);
  * asm liveness: the destination register (any alias) is not read on any path
    from the transmitter before being fully overwritten (32/64-bit write, xor
    idiom); `ret` counts as a read of %rax; an unknown mnemonic on a path skips;
  * annotation re-resolution is faithful: re-resolving the ORIGINAL .s with
    compile_annotate's own functions reproduces the stored annotation exactly
    (after dropping the `atom` keys today's compile_annotate keeps but the stored
    STT_6 annotations lack; see strip_atoms_like);
  * after the rewrite: the disassembly at the new xmit address is an `or` with a
    zero immediate, every annotation field that existed before exists again,
    func_base is unchanged, and every absolute address shifts by exactly the
    same constant (the length change) iff it lies after the transmitter.

Annotations are re-resolved with compile_annotate.py (build_binary,
pc_offsets_from_nm, commit_offsets_from_nm, disassemble_instrs,
update_annotations), i.e. the exact procedure the asm phase uses: absolute
post-link addresses from the pc-marker labels via nm + objdump.

Usage (on cafe2, inside gem5_dev):
  python3 make_rmw_corpus.py --repo-root /tests/simspect_fixed_20261030 \
      --src testsets_latest/STT_6 --dst testsets_latest/STT_6_rmw \
      --modes mispredict_not_taken mispredict_taken --jobs 24 [--git-rev <mac HEAD>]
Writes <dst>/<mode>/{asm,ann}/, <dst>/provenance.json, <dst>/make_rmw_corpus.log.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import shutil
import socket
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RULE = ("ld transmitter `movq <mem>, %reg64` at the xmit pc marker -> `orq $0, <mem>` "
        "(value-neutral RMW, same address); only when the destination register has no "
        "consumer (XML rf + asm liveness); annotations re-resolved with compile_annotate.py")

REG64 = ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp"] + [f"r{i}" for i in range(8, 16)]


def _family(r64: str) -> dict:
    """alias -> width for one 64-bit register."""
    if r64.startswith("r") and r64[1:].isdigit():
        return {r64: 64, r64 + "d": 32, r64 + "w": 16, r64 + "b": 8}
    b = r64[1:]                       # ax, cx, si, sp ...
    d = {r64: 64, "e" + b: 32, b: 16}
    if b in ("ax", "bx", "cx", "dx"):
        d[b[0] + "l"] = 8; d[b[0] + "h"] = 8
    else:
        d[b + "l"] = 8
    return d


ALIAS_TO_64 = {a: r for r in REG64 for a in _family(r)}
XMIT_RE = re.compile(r"^movq\s+([-\w]*\(%\w+(?:,%\w+(?:,[1248])?)?\)),\s*%(\w+)$")
LABEL_RE = re.compile(r'^("?[\w.$-]+"?):\s*$')
COND_J = {"je", "jne", "jl", "jle", "jg", "jge", "jb", "jbe", "ja", "jae", "jo", "jno",
          "js", "jns", "jp", "jnp", "jz", "jnz"}
KILL_MOVS = {"movq", "movl", "leaq", "leal", "popq", "movabsq", "movzbl", "movzwl", "movslq",
             "movzbq", "movzwq", "movsbq", "movswq", "movsbl", "movswl"}
SAFE_PREFIX = ("mov", "lea", "add", "sub", "and", "or", "xor", "not", "neg", "inc", "dec",
               "test", "cmp", "sh", "sa", "ro", "push", "pop", "mfence", "lfence", "sfence",
               "nop", "set", "cmov", "bt")


def _ops(s: str) -> list:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_func(lines: list):
    """-> (instrs[(lineno, mnem, ops)], label->instr index). Function body only."""
    instrs, labels, pending = [], {}, []
    for ln, raw in enumerate(lines):
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        m = LABEL_RE.match(s)
        if m:
            pending.append(m.group(1).strip('"'))
            continue
        if s.startswith("."):
            continue
        parts = s.split(None, 1)
        for p in pending:
            labels[p] = len(instrs)
        pending = []
        instrs.append((ln, parts[0].lower(), _ops(parts[1]) if len(parts) > 1 else []))
    for p in pending:
        labels[p] = len(instrs)
    return instrs, labels


def classify(mnem: str, ops: list, fam: dict, r64: str) -> str:
    """'read' | 'kill' | 'none' | 'unknown' for register family `fam`."""
    if mnem in ("ret", "retq"):
        return "read" if r64 == "rax" else "none"
    pat = re.compile(r"%(" + "|".join(sorted(fam, key=len, reverse=True)) + r")\b")
    hits = [i for i, o in enumerate(ops) if pat.search(o)]
    if mnem.startswith("j"):
        return "none" if not hits else "read"
    if not mnem.startswith(SAFE_PREFIX) or (mnem.startswith("imul") and len(ops) < 2):
        return "unknown"
    if not hits:
        return "none"
    last = ops[-1] if ops else ""
    lm = re.fullmatch(r"%(\w+)", last)
    full_w = lm and fam.get(lm.group(1)) in (32, 64)
    if mnem in KILL_MOVS and full_w and hits == [len(ops) - 1]:
        return "kill"
    if mnem in ("xorl", "xorq", "subl", "subq") and len(ops) == 2 and ops[0] == ops[1] and full_w:
        return "kill"
    return "read"


def dst_live_after(instrs, labels, xi: int, r64: str):
    """True if r64 may be read after instruction xi; None if an unknown mnemonic is reachable."""
    fam = _family(r64)
    seen, stack = set(), [xi + 1]
    while stack:
        i = stack.pop()
        if i in seen or i >= len(instrs):
            continue
        seen.add(i)
        _, m, ops = instrs[i]
        c = classify(m, ops, fam, r64)
        if c == "unknown":
            return None
        if c == "read":
            return True
        if c == "kill":
            continue
        if m in ("ret", "retq"):
            continue
        if m.startswith("j"):
            tgt = ops[0].strip('"') if ops else None
            if tgt not in labels:
                return None
            stack.append(labels[tgt])
            if m in COND_J:
                stack.append(i + 1)
            continue
        stack.append(i + 1)
    return False


def xml_outreg_consumed(txt: str, atom: str):
    def rel(n):
        m = re.search(r"^this/(?:Instruction|Operand)<:%s=\{(.*)\}$" % n, txt, re.M)
        d = collections.defaultdict(set)
        if m:
            for a, b in re.findall(r"([\w$]+)->([\w$]+)", m.group(1)):
                d[a].add(b)
        return d
    outreg, rf = rel("outreg"), rel("rf")
    return any(rf.get(o) for o in outreg.get(atom, ()))


def addr_fields(obj, path=""):
    """Flatten every integer *addr field (absolute address) with its path."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if isinstance(v, (dict, list)):
                out.update(addr_fields(v, p))
            elif (k == "addr" or k.endswith("_addr")) and isinstance(v, int):
                out[p] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(addr_fields(v, f"{path}[{i}]"))
    return out


def key_paths(obj, path=""):
    s = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            s.add(f"{path}.{k}"); s |= key_paths(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            s |= key_paths(v, f"{path}[{i}]")
    return s


CA = None  # compile_annotate module (set in worker init)


def _init(repo_root: str):
    global CA
    sys.path.insert(0, str(Path(repo_root) / "STAGE2_compilation"))
    import compile_annotate as ca  # noqa: E402
    CA = ca


def strip_atoms_like(new: dict, ref: dict) -> dict:
    """The stored STT_6 annotations were written by an earlier compile_annotate that
    dropped the Alloy `atom` cross-reference fields; today's keeps them. Drop every
    `atom` key the reference annotation does not have, so the schema is unchanged."""
    def walk(n, r):
        if isinstance(n, dict):
            for k in list(n):
                if k == "atom" and not (isinstance(r, dict) and "atom" in r):
                    del n[k]
                else:
                    walk(n[k], r.get(k) if isinstance(r, dict) else None)
        elif isinstance(n, list):
            for i, v in enumerate(n):
                walk(v, r[i] if isinstance(r, list) and i < len(r) else None)
    walk(new, ref)
    return new


def resolve_ann(s_text: str, stem: str, bare_ann: Path) -> tuple:
    tmp = Path(tempfile.mkdtemp(prefix=f"rmw_{stem}_"))
    try:
        s = tmp / f"{stem}.s"
        s.write_text(s_text)
        binary, base = CA.build_binary(s, tmp)
        pc_map = CA.pc_offsets_from_nm(binary, stem, base)
        commit = CA.commit_offsets_from_nm(binary, stem, base)
        instrs = CA.disassemble_instrs(binary, base)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return CA.update_annotations(bare_ann, pc_map, instrs, base, commit), instrs, base


def process(args: tuple) -> dict:
    stem, src_mode, dst_mode, xml_dir = (args[0], Path(args[1]), Path(args[2]), Path(args[3]))
    try:
        ann_p = src_mode / "ann" / f"{stem}.ann.json"
        s_p = src_mode / "asm" / f"{stem}.s"
        bare_p = src_mode / "llvm" / f"{stem}.ann.json"
        ann = json.loads(ann_p.read_text())
        x = ann.get("xmit") or {}
        if x.get("kind") != "ld":
            return dict(stem=stem, skip="xmit_kind_not_ld")
        if not bare_p.exists():
            return dict(stem=stem, skip="no_bare_ann")
        bare = json.loads(bare_p.read_text())
        atom = (bare.get("xmit") or {}).get("atom")
        xml_txt = xml_dir / f"{stem}.txt"
        if not atom or not xml_txt.exists():
            return dict(stem=stem, skip="no_xml_or_atom")
        if xml_outreg_consumed(xml_txt.read_text(), atom):
            return dict(stem=stem, skip="xml_outreg_consumed")
        text = s_p.read_text()
        lines = text.split("\n")
        safe = stem.replace("-", "_").replace(".", "_")
        lab = f"__litmus_{safe}_pc{x['pc']}:"
        idx = [k for k, l in enumerate(lines) if l.strip() == lab]
        if len(idx) != 1:
            return dict(stem=stem, skip=f"marker_count_{len(idx)}")
        body = []
        for k in range(idx[0] + 1, len(lines)):
            st = lines[k].strip()
            if st == "#NO_APP":
                break
            if st:
                body.append((k, st))
        if len(body) != 1:
            return dict(stem=stem, skip="xmit_block_not_single_instr")
        xl, xs = body[0]
        m = XMIT_RE.match(xs)
        if not m:
            return dict(stem=stem, skip="xmit_operand_form_unusual")
        mem, dst = m.group(1), m.group(2)
        if dst not in REG64:
            return dict(stem=stem, skip="xmit_dst_not_reg64")
        # liveness over the function body
        fstart = next((k for k, l in enumerate(lines) if l.split("#", 1)[0].strip() == f'"{stem}":'), None)
        fend = next((k for k, l in enumerate(lines) if l.strip().startswith(".Lfunc_end0:")), None)
        if fstart is None or fend is None:
            return dict(stem=stem, skip="function_bounds_not_found")
        instrs, labels = parse_func(lines[fstart + 1:fend])
        xi = [i for i, (ln, _, _) in enumerate(instrs) if ln == xl - fstart - 1]
        if len(xi) != 1:
            return dict(stem=stem, skip="xmit_not_in_cfg")
        live = dst_live_after(instrs, labels, xi[0], dst)
        if live is None:
            return dict(stem=stem, skip="liveness_unknown_instr")
        if live:
            return dict(stem=stem, skip="asm_dst_live_after_xmit")
        # 1) faithful re-resolution of the original
        orig_re, _, base0 = resolve_ann(text, stem, bare_p)
        if strip_atoms_like(orig_re, ann) != ann:
            return dict(stem=stem, skip="ann_reresolve_mismatch_original")
        # 2) rewrite + re-resolve
        indent = lines[xl][: len(lines[xl]) - len(lines[xl].lstrip())]
        new_lines = list(lines)
        new_lines[xl] = f"{indent}orq\t$0, {mem}"
        new_text = "\n".join(new_lines)
        new_ann, dis, base1 = resolve_ann(new_text, stem, bare_p)
        new_ann = strip_atoms_like(new_ann, ann)
        if base1 != base0:
            return dict(stem=stem, skip="func_base_changed")
        if key_paths(new_ann) != key_paths(ann):
            return dict(stem=stem, skip="ann_fields_changed")
        xa_old, xa_new = ann["xmit"]["addr"], new_ann["xmit"]["addr"]
        at = [d for d in dis if d[0] + base1 == xa_new]
        if not at or not at[0][1].startswith("or") or not re.match(r"\$(0x)?0,", at[0][2]):
            return dict(stem=stem, skip="disasm_at_xmit_not_or0")
        fo, fn = addr_fields(ann), addr_fields(new_ann)
        deltas = {fn[p] - fo[p] for p in fo if fo[p] > xa_old}
        if len(deltas) > 1 or any(fn[p] != fo[p] for p in fo if fo[p] <= xa_old):
            return dict(stem=stem, skip="addr_shift_irregular")
        (dst_mode / "asm" / f"{stem}.s").write_text(new_text)
        (dst_mode / "ann" / f"{stem}.ann.json").write_text(json.dumps(new_ann, indent=2) + "\n")
        return dict(stem=stem, ok=True, mem=mem, dst=dst, delta=(deltas.pop() if deltas else 0),
                    orig=xs, xmit_addr=hex(xa_new))
    except Exception:
        return dict(stem=stem, skip="exception", tb=traceback.format_exc())


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--src", required=True, help="source testset dir (relative to repo root or absolute)")
    ap.add_argument("--dst", required=True)
    ap.add_argument("--modes", nargs="+", default=["mispredict_not_taken", "mispredict_taken"])
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0, help="first N stems per mode (testing)")
    ap.add_argument("--git-rev", default="unknown", help="Mac repo HEAD the script came from")
    a = ap.parse_args()
    root = Path(a.repo_root)
    src = Path(a.src) if Path(a.src).is_absolute() else root / a.src
    dst = Path(a.dst) if Path(a.dst).is_absolute() else root / a.dst
    dst.mkdir(parents=True, exist_ok=True)
    log = (dst / "make_rmw_corpus.log").open("a")

    def L(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True); log.write(line + "\n"); log.flush()

    me = Path(__file__).resolve()
    L(f"START src={src} dst={dst} modes={a.modes} jobs={a.jobs} limit={a.limit} script_md5={md5(me)}")
    prov = dict(created=time.strftime("%Y-%m-%dT%H:%M:%S"), host=socket.gethostname(),
                source_testset=str(src), dest_testset=str(dst), rule=RULE,
                script=str(me), script_md5=md5(me), script_git_rev_mac=a.git_rev,
                compile_annotate_md5=md5(root / "STAGE2_compilation" / "compile_annotate.py"),
                note="no .o files are written (the checkers build from .s); xml/ is not copied, "
                     "use the source testset's xml/ (same stems)", modes={})
    for mode in a.modes:
        sm, dm = src / mode, dst / mode
        for d in ("asm", "ann"):
            shutil.rmtree(dm / d, ignore_errors=True)
            (dm / d).mkdir(parents=True, exist_ok=True)
        stems = sorted(p.name[:-9] for p in (sm / "ann").glob("*.ann.json"))
        if a.limit:
            stems = stems[: a.limit]
        L(f"mode {mode}: {len(stems)} source stems")
        work = [(s, str(sm), str(dm), str(src / "xml")) for s in stems]
        res = []
        with ProcessPoolExecutor(a.jobs, initializer=_init, initargs=(str(root),)) as ex:
            for i, r in enumerate(ex.map(process, work, chunksize=64)):
                res.append(r)
                if r.get("skip") == "exception":
                    L(f"ERROR {mode}/{r['stem']}:\n{r['tb']}")
                if (i + 1) % 10000 == 0:
                    L(f"  {mode}: {i + 1}/{len(work)}")
        ok = [r for r in res if r.get("ok")]
        skips = collections.Counter(r["skip"] for r in res if "skip" in r)
        prov["modes"][mode] = dict(
            n_source=len(stems), n_written=len(ok), skip_counts=dict(skips),
            delta_bytes=dict(collections.Counter(r["delta"] for r in ok)),
            orig_forms=dict(collections.Counter(re.sub(r"%\w+", "%R", r["orig"]) for r in ok)),
            skipped={k: sorted(r["stem"] for r in res if r.get("skip") == k)
                     for k in skips if k != "xmit_kind_not_ld"},
            skipped_not_ld_count=skips.get("xmit_kind_not_ld", 0))
        L(f"mode {mode}: written={len(ok)} skips={dict(skips)}")
    (dst / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    L(f"END provenance={dst / 'provenance.json'}")


if __name__ == "__main__":
    main()
