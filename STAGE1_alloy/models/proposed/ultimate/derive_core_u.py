#!/usr/bin/env python3
"""derive_core_u.py — assemble, check and derive models built on SKELETON_u.als.

DRAFT TOOLING (2026-11-09, skeleton agent). Writes NEW files only (refuses to
overwrite) and never edits an existing .als. Nothing here is approved.

SKELETON_u.als is the shared skeleton with marked regions:
  //@@DEFENSE-BEGIN ... //@@DEFENSE-END   the defense-block slot (empty in the skeleton)
  //@@RUN-BEGIN ... //@@RUN-END           the run command(s); the first one is enumerated
  //@@N-BEGIN ix-atoms ... //@@N-END ix-atoms, //@@N-BEGIN fold ... //@@N-END fold
                                          the only text that depends on the max #Instruction

Subcommands
  assemble --block B.als --out M.als [--skeleton S]   skeleton + one defense block -> model
  check M.als [--skeleton S] [--allow-run] [--allow-n] skeleton region of M byte-identical to S?
                                                      + lint of M's defense block
  lint B.als                                          lint a defense block (or a whole model's block)
  core M.als OUT.als [--minimality ri|rori|none]      Stage-1 core: ONLY the RUN block changes,
                                                      to `run gen_lit { gen_core } for 9 but 6 ...`
                                                      (partition_stage1.py-compatible scope text)
  resize M.als OUT.als --max-instr N [--operands K] [--flat|--core]
                                                      regenerate IX atoms + fold depth for N
                                                      (Stage 1.5b; stage15-bound S1/S2/S4)

Why this replaces derive_core.py's three text edits: with SKELETON_u the idx
symmetry break is valid at `but N` ([sk-2]) and the core generator is a named
predicate ([sk-15]), so a core differs from its flat model in the run line only.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SKELETON = HERE / "SKELETON_u.als"

DEF_B, DEF_E = "//@@DEFENSE-BEGIN", "//@@DEFENSE-END"
RUN_B, RUN_E = "//@@RUN-BEGIN", "//@@RUN-END"
N_REGIONS = ("ix-atoms", "fold")

REQUIRED = {
    # name: regex that the definition header must match (perturbation-parameterized)
    "speculation_contract_p": r"fun\s+speculation_contract_p\s*\[\s*p\s*:\s*PTag\s*->\s*univ\s*\]\s*:\s*Instruction",
    "hardware_protection_policy": r"fun\s+hardware_protection_policy\s*\[\s*p\s*:\s*PTag\s*->\s*univ\s*\]\s*:\s*Operand",
    "prot_set_propagation_p": r"fun\s+prot_set_propagation_p\s*\[\s*p\s*:\s*PTag\s*->\s*univ\s*,\s*i\s*:\s*Instruction\s*,\s*o\s*:\s*Operand\s*\]\s*:\s*Operand",
    "prot_flow_p": r"fun\s+prot_flow_p\s*\[\s*p\s*:\s*PTag\s*->\s*univ\s*\]\s*:\s*Operand\s*->\s*Operand",
    "leakage_function": r"^fun\s+leakage_function\s*:\s*Operand\s*\{.*\}\s*$",
}

# Reading the UNperturbed program from a defense block silently ignores RI/RO/RS
# (the 2026-11-07 SPT-seed root cause). These are errors.
FORBIDDEN = [
    (r"\bInstruction\s*\.", "navigates from the whole (unperturbed) program; use i_p[p] / o_p[p]"),
    (r"\bInstruction\s*-(?!>)", "subtracts from the whole (unperturbed) program; use i_p[p]"),
    (r"\b(rf|ddi|spo)\b", "raw relation; use rf_p[p] / ddi_p[p] / op_edges_p[p] / spo_p[p]"),
    (r"\b(committed|uncommitted|resolved|unresolved|first_uncommitted|last_committed|first_instr)\b",
     "unperturbed flag set; use committed_p[p] / uncommitted_p[p] / resolved_p[p] / unresolved_p[p]"),
    (r"#", "cardinality (Int bitwidth can wrap); use lone/one/no"),
]
# Static operand fields are allowed (they are the instance's operand map), but under
# RO/RS they still see removed operands unless clipped with o_p[p]. Warnings.
ADVISORY = [
    (r"(?<![A-Za-z0-9_])(inreg|inaddr|inmem|outreg|outmem)(?![A-Za-z0-9_])",
     "raw operand field; under RO/RS it still sees removed operands (use *_p[p] or & o_p[p])"),
]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def strip_comments(t: str) -> str:
    t = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), t, flags=re.S)
    out = []
    for line in t.split("\n"):
        cut = [k for k in (line.find("//"), line.find("--")) if k >= 0]
        out.append(line[:min(cut)] if cut else line)
    return "\n".join(out)


def region(text: str, b: str, e: str):
    """Return (start, end) offsets of the content strictly between marker lines b and e."""
    lines = text.split("\n")
    bi = [k for k, l in enumerate(lines) if l.strip().startswith(b)]
    ei = [k for k, l in enumerate(lines) if l.strip().startswith(e)]
    if len(bi) != 1 or len(ei) != 1 or ei[0] < bi[0]:
        sys.exit(f"refusing: marker pair {b} / {e} must occur exactly once, in order (found {len(bi)}/{len(ei)})")
    return bi[0], ei[0]


def get_region(text, b, e):
    lines = text.split("\n")
    s, t = region(text, b, e)
    return "\n".join(lines[s + 1:t])


def set_region(text, b, e, content):
    lines = text.split("\n")
    s, t = region(text, b, e)
    new = lines[:s + 1] + (content.split("\n") if content != "" else []) + lines[t:]
    return "\n".join(new)


def skeleton_names(skel_text: str):
    body = strip_comments(set_region(skel_text, DEF_B, DEF_E, ""))
    names = set(re.findall(r"^\s*(?:fun|pred|fact|let|assert)\s+([A-Za-z_][A-Za-z0-9_']*)", body, re.M))
    names |= set(re.findall(r"^\s*(?:abstract\s+|one\s+|lone\s+|some\s+)?sig\s+([A-Za-z_][A-Za-z0-9_']*)", body, re.M))
    return names


def lint_block(block: str, skel_text: str):
    errs, warns = [], []
    code = strip_comments(block)
    for name, pat in REQUIRED.items():
        n = len(re.findall(pat, code, re.M))
        if n != 1:
            errs.append(f"interface: `{name}` must be defined exactly once with the SKELETON_u signature (found {n})")
    defined = re.findall(r"^\s*(?:fun|pred|fact|let|assert)\s+([A-Za-z_][A-Za-z0-9_']*)", code, re.M)
    clash = sorted(set(defined) & skeleton_names(skel_text))
    if clash:
        errs.append(f"redefines skeleton names {clash} (the skeleton must stay verbatim)")
    # which lines belong to a `fact` paragraph: a contract side-condition fact constrains
    # the BASE instance, so it may (must) use the unperturbed relations; only the
    # perturbed-world functions/predicates are held to the FORBIDDEN list.
    in_fact, depth, fact_lines = False, 0, set()
    for ln, line in enumerate(code.split("\n"), 1):
        if depth == 0:
            in_fact = bool(re.match(r"\s*fact\b", line))
        if in_fact:
            fact_lines.add(ln)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            depth, in_fact = 0, False if depth <= 0 and "}" in line else in_fact
    for ln, line in enumerate(code.split("\n"), 1):
        for pat, why in FORBIDDEN:
            if ln in fact_lines and pat != r"#":
                continue
            for m in re.finditer(pat, line):
                errs.append(f"block line {ln}: `{m.group(0)}` {why}")
        if re.match(r"\s*fun\s+leakage_function\b", line):
            continue  # the skeleton clips it: leakage_function_p = leakage_function & o_p[p]
        for pat, why in ADVISORY:
            for m in re.finditer(pat, line):
                warns.append(f"block line {ln}: `{m.group(0)}` {why}")
    return errs, warns


def refuse_overwrite(p: Path):
    if p.exists():
        sys.exit(f"refusing: {p} exists (this tool never overwrites)")


def header(kind, src_desc):
    return ("// =============================================================================\n"
            f"// [{kind} — DRAFT, UNAPPROVED] generated by STAGE1_alloy/models/proposed/ultimate/derive_core_u.py\n"
            f"// {src_desc}\n"
            "// Everything outside the //@@DEFENSE slot is SKELETON_u.als verbatim"
            + (" except the RUN block" if kind.startswith("STAGE-1") else "")
            + (" and the //@@N regions" if "RESIZED" in kind else "") + ".\n"
            "// =============================================================================\n")


def drop_header(text):
    # generated models start with a "// ===...[...] generated by" banner; the skeleton has its own banner
    m = re.match(r"(// =+\n// \[[^\n]*generated by[^\n]*\n(?://[^\n]*\n)*?// =+\n)", text)
    return text[m.end():] if m else text


def cmd_assemble(a):
    skel_p = Path(a.skeleton)
    skel = skel_p.read_text()
    block = Path(a.block).read_text()
    errs, warns = lint_block(block, skel)
    for w in warns:
        print("WARN ", w)
    if errs:
        for e in errs:
            print("ERROR", e)
        sys.exit("refusing: block fails the lint")
    out = Path(a.out)
    refuse_overwrite(out)
    model = set_region(skel, DEF_B, DEF_E, block.rstrip("\n"))
    desc = (f"MODEL = {skel_p.name} (sha256 {sha(skel_p.read_bytes())[:16]}) + block {Path(a.block).name} "
            f"(sha256 {sha(Path(a.block).read_bytes())[:16]})")
    out.write_text(header("MODEL", desc) + model)
    print(f"wrote {out}")


def normalized_skeleton(text, allow_run, allow_n):
    t = drop_header(text)
    t = set_region(t, DEF_B, DEF_E, "")
    if allow_run:
        t = set_region(t, RUN_B, RUN_E, "")
    if allow_n:
        for r in N_REGIONS:
            t = set_region(t, f"//@@N-BEGIN {r}", f"//@@N-END {r}", "")
        t = re.sub(r"idx: one \(IX0[^)]*\)", "idx: one (IX…)", t)
    return t


def cmd_check(a):
    skel = Path(a.skeleton).read_text()
    m = Path(a.model).read_text()
    ns = normalized_skeleton(skel, a.allow_run, a.allow_n)
    nm = normalized_skeleton(m, a.allow_run, a.allow_n)
    ok = True
    if ns != nm:
        ok = False
        import difflib
        print("SKELETON DRIFT (model vs SKELETON_u, slot removed):")
        for l in difflib.unified_diff(ns.split("\n"), nm.split("\n"), "SKELETON_u", a.model, lineterm="", n=1):
            print("  " + l)
    else:
        print("skeleton: byte-identical to SKELETON_u (outside the slot"
              + (", RUN" if a.allow_run else "") + (", N regions" if a.allow_n else "") + ")")
    errs, warns = lint_block(get_region(drop_header(m), DEF_B, DEF_E), skel)
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    if errs or not ok:
        sys.exit(1)


def cmd_lint(a):
    skel = Path(a.skeleton).read_text()
    t = Path(a.file).read_text()
    if DEF_B in t:
        block = get_region(t, DEF_B, DEF_E)
    elif not re.search(r"^\s*sig\s+Instruction\b", strip_comments(t), re.M):
        block = t  # a bare block file
    else:
        # legacy model: the block is everything after the last "Specific defense model" banner
        k = t.rfind("Specific defense model")
        if k < 0:
            sys.exit("no //@@DEFENSE slot and no 'Specific defense model' banner")
        k = t.rfind("/****", 0, k)
        block = t[k:]
        print(f"(legacy model: linting the text after the 'Specific defense model' banner)")
    errs, warns = lint_block(block, skel)
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    print(f"{len(errs)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errs else 0)


def run_scope(n, exact, operands):
    k = f"exactly {n}" if exact else f"{n}"
    ops = f", {operands} Operand" if operands else ""
    return f"for 9 but {k} Instruction{ops}, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool"


def cmd_core(a):
    src = Path(a.model)
    t = src.read_text()
    if a.minimality == "none":   # SPT's "conservative" core: no removal-minimality, only RR/RC/RS
        body, label = "  gen_useful_litmus", "RR + RC + RS (no RI: SPT conservative)"
    else:
        body = "  gen_core" + ("\n  min_RO[Operand]" if a.minimality == "rori" else "")
        label = "RR + RC + RS + RI" + (" + RO" if a.minimality == "rori" else "") + " (gen_core)"
    run = (f"// [STAGE-1 CORE] minimality = {label};"
           f" up to {a.max_instr} instructions; idx symmetry break kept ([sk-2])\n"
           f"run gen_lit {{\n{body}\n}} {run_scope(a.max_instr, False, None)}")
    t2 = set_region(drop_header(t), RUN_B, RUN_E, run)
    out = Path(a.out)
    refuse_overwrite(out)
    out.write_text(header("STAGE-1 CORE", f"from {src.name} (sha256 {sha(src.read_bytes())[:16]}), --minimality {a.minimality}") + t2)
    print(f"wrote {out}")


def cmd_resize(a):
    n = a.max_instr
    if n < 1:
        sys.exit("refusing: --max-instr must be >= 1")
    src = Path(a.model)
    t = drop_header(src.read_text())
    ix = ["// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)"]
    ix += [f"one sig IX{k} {{}} -- spo position {k}" for k in range(n)]
    ix.append("fun IXs : univ { " + " + ".join(f"IX{k}" for k in range(n)) + " }                          -- [sk-2]")
    nxt = " + ".join(f"IX{k}->IX{k+1}" for k in range(n - 1)) or "none->none"
    ix.append(f"fun ix_next : univ -> univ {{ {nxt} }}  -- [sk-2]")
    t = set_region(t, "//@@N-BEGIN ix-atoms", "//@@N-END ix-atoms", "\n".join(ix))
    t = re.sub(r"idx: one \(IX0[^)]*\)", "idx: one (" + " + ".join(f"IX{k}" for k in range(n)) + ")", t)
    lets = " | ".join(["let s = spo_p[p]", "let i0 = f[p]"] + [f"let i{k} = i{k-1}.s" for k in range(1, n)])
    nest = "prot_seed_p[p]"
    for k in range(n):
        nest = f"a[p,i{k}, {nest}]"
    fold = (f"// [sk-8] apply the step at each surviving position 0..{n-1}, in spo order\n"
            "fun protset_p[p: PTag->univ] : Operand {\n"
            f"\t{lets} |\n\t\to_p[p] & {nest}\n}}")
    t = set_region(t, "//@@N-BEGIN fold", "//@@N-END fold", fold)
    ops = a.operands if a.operands else (2 * n if n > 4 else None)
    if a.core:
        run = f"run gen_lit {{\n  gen_core\n}} {run_scope(n, False, ops)}"
    else:
        run = f"run gen_lit {{\n  gen_useful_litmus\n}} {run_scope(n, True, ops)}"
    t = set_region(t, RUN_B, RUN_E, run)
    out = Path(a.out)
    refuse_overwrite(out)
    out.write_text(header("RESIZED", f"from {src.name} (sha256 {sha(src.read_bytes())[:16]}), --max-instr {n}") + t)
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("assemble"); s.add_argument("--block", required=True); s.add_argument("--out", required=True)
    s.add_argument("--skeleton", default=str(DEFAULT_SKELETON)); s.set_defaults(fn=cmd_assemble)
    s = sub.add_parser("check"); s.add_argument("model"); s.add_argument("--skeleton", default=str(DEFAULT_SKELETON))
    s.add_argument("--allow-run", action="store_true"); s.add_argument("--allow-n", action="store_true"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("lint"); s.add_argument("file"); s.add_argument("--skeleton", default=str(DEFAULT_SKELETON)); s.set_defaults(fn=cmd_lint)
    s = sub.add_parser("core"); s.add_argument("model"); s.add_argument("out")
    s.add_argument("--minimality", choices=["ri", "rori", "none"], default="ri"); s.add_argument("--max-instr", type=int, default=6)
    s.set_defaults(fn=cmd_core)
    s = sub.add_parser("resize"); s.add_argument("model"); s.add_argument("out"); s.add_argument("--max-instr", type=int, required=True)
    s.add_argument("--operands", type=int, default=None)
    g = s.add_mutually_exclusive_group(); g.add_argument("--core", action="store_true"); g.add_argument("--flat", action="store_true")
    s.set_defaults(fn=cmd_resize)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
