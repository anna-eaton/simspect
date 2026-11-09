#!/usr/bin/env python3
"""make_s15_model.py — build a Stage-1.5 model at a larger instruction bound and/or with a looser pin.

stage15-bound session, 2026-11-08. SCRATCH/DRAFT TOOLING: writes NEW .als files only (never edits
an existing model). Input = a production model (STT_6.als, Recon_6.als, SPT_6_oneLP_v2.als, ...) and
one Stage-1 core (an inst-*.txt from a6CountModels). Output = a copy of the production model with
ONLY these mechanical, scope-tied edits:

  --n N           'exactly 6 Instruction' -> 'exactly N Instruction'.
                  IX symmetry-breaking is regenerated for N positions (IX0..IX{N-1}), or dropped
                  with --ix drop.
                  The protection-set fold last_committed_protset_p (unrolled 7 deep in every
                  production model, i.e. it only visits spo positions 0..6) is regenerated N deep
                  when N > 7 (positions 0..N-1); for N <= 7 the production text is kept verbatim.
                  --fold keep forces the production 7-deep fold (used by the fold-depth query).
                  --fold explicit replaces the nested fold by one relation per perturbation form
                  (PSX.pn / prr / prs / prc, defined step by step along spo, see explicit_fold()):
                  exact at any N, linear-size formula; valid only when no RI perturbation is used
                  (true for every Stage-1.5 / production gen_useful_litmus). The nested fold is kept
                  as last_committed_protset_orig_p for the fold_equiv query.
  --operands K    add 'K Operand' to the scope (production: 'for 9' => at most 9 operands in total).
  --states S      add 'S State' to the scope (production: at most 9 states).
  --pin a|b|c     a = production pin (STAGE1_alloy/stage_seed.py, every core instruction, operand,
                      flag, ddi edge and rf edge pinned exactly; spo relative);
                  b = 'path pin': as (a) but each core rf edge  ob in oa.rf  becomes
                      ob in oa.rf.*(ddi.rf), i.e. the edge may be subdivided through added
                      instructions (ALU ops via Inreg->Outreg ddi, or a store/load memory hop);
                  c = 'leak pin': only the transmitter's kind and an unresolved branch of the core's
                      branch kind before it (the core's other instructions are not pinned).
                  none = no pin (flat production model at the new bound).
  --minimality M prod (default) = the production gen_useful_litmus verbatim (RR + boundary RC/RR + RS);
                  leak_rs = keep only 'not secure[no_p]' + RS (drop RR and the boundary clause);
                  leak = only 'not secure[no_p]'.
  --query NAME    conjoin an extra predicate to the run (see QUERIES below).

QUERIES
  splice_xm   some ALU op lies on the (subdivided) core rf edge into xm's leak operand
              (only meaningful with --pin b; with --pin a it is UNSAT by one_entering_rf)
  s4_shape    the S4 shape (s4-variant's forcing predicate, verbatim from proposed/STT_6_s4.als)
  a3c_shape   the A3c shape (verbatim from proposed/STT_6_a3c.als)
  fold_equiv  facts only: some perturbation form where the explicit fold differs from the nested
              (N-deep) fold. Expect UNSAT (= the two encodings agree). Use with --fold explicit.
  otb_shape   the OTB precursor (wiki/findings/mdsToRead/OTB_GENERATION_GAP.md:8): an ALU op's outreg
              rf-feeds a load transmitter's inaddr
  fold_trunc  the 7-deep production fold says LEAK (gen_useful_litmus as written) but the N-deep
              fold says SECURE at no_p (secure_full_p[no_p]) -> the truncated fold invents a leak.
              Use with --fold keep and N > 7.

Usage:
  python3 make_s15_model.py --model ../../STT_6.als --core core.txt --n 10 --operands 20 \
      --pin b [--query splice_xm] --out out.als
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE1 = HERE.parents[2]          # .../STAGE1_alloy
sys.path.insert(0, str(STAGE1))
import stage_seed  # noqa: E402

KIND_SIG = stage_seed.KIND_ATOM_TO_SIG


def find_block(text, start_pat):
    """Return (start, end) of a top-level block 'start_pat ... { ... }' with balanced braces."""
    m = re.search(start_pat, text, re.M)
    if not m:
        sys.exit(f"anchor not found: {start_pat}")
    i = text.index("{", m.start())
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return m.start(), j + 1
    sys.exit(f"unbalanced block: {start_pat}")


def gen_fold(sig_line, seed_expr, n, name="last_committed_protset_p"):
    expr = seed_expr
    for k in range(n):
        fk = "f[p]" + ".(spo_p[p])" * k
        expr = f"a[p,{fk},\n\t{expr}]"
    sig = re.sub(r"fun \w+\[", f"fun {name}[", sig_line)
    return f"{sig}\n\t// [stage15-bound] fold regenerated {n} deep (spo positions 0..{n-1})\n\t{expr}\n}}"


def fold_parts(text):
    s, e = find_block(text, r"^fun last_committed_protset_p\[")
    block = text[s:e]
    sig_line = block[:block.index("{") + 1]
    m = re.search(r"a\[p,f\[p\],(hardware_protection_policy(?:\[p\])?)\]", block)
    if not m:
        sys.exit("fold seed not found")
    return s, e, sig_line, m.group(1)


def regen_ix(text, n, mode):
    sig_pat = r"(?:one sig IX\d+ \{\}.*\n)+"
    sum_pat = r"\(IX0(?:\s*\+\s*IX\d+)*\)"
    if len(re.findall(sig_pat, text)) != 1 or len(re.findall(sum_pat, text)) != 2:
        sys.exit("IX anchors not found exactly as expected")
    s, e = find_block(text, r"^pred lt_ix\[")
    if mode == "drop":
        text = text[:s] + "// [stage15-bound] lt_ix dropped\n" + text[e:]
        text = re.sub(sig_pat, "// [stage15-bound] IX sigs dropped\n", text)
        text = re.sub(r"^\s*idx: one " + sum_pat + r",.*\n", "", text, flags=re.M)
        text = re.sub(r"^fact idx_bijective.*\n", "", text, flags=re.M)
        text = re.sub(r"^fact idx_surjective.*\n", "", text, flags=re.M)
        s2, e2 = find_block(text, r"^fact idx_matches_spo")
        return text[:s2] + text[e2:]
    ixs = [f"IX{k}" for k in range(n)]
    text = re.sub(sig_pat, "".join(f"one sig {x} {{}} -- spo position {k}\n" for k, x in enumerate(ixs)), text)
    text = re.sub(sum_pat, "(" + " + ".join(ixs) + ")", text)
    ors = [f"(a={ixs[k]} and b in {'+'.join(ixs[k+1:])})" for k in range(n - 1)]
    lt = "pred lt_ix[a, b: univ] { " + "\n\t\tor ".join(ors) + "\n}"
    s, e = find_block(text, r"^pred lt_ix\[")
    return text[:s] + lt + text[e:]


def core_info(rels):
    instrs = sorted({a for (a,) in rels.get("Instruction", [])}, key=lambda s: int(s.split("$")[1]))
    operands = sorted({a for (a,) in rels.get("Operand", [])}, key=lambda s: (s.split("$")[0], int(s.split("$")[1])))
    ivar = {a: f"i{n}" for n, a in enumerate(instrs)}
    ovar = {a: f"o{n}" for n, a in enumerate(operands)}
    return instrs, operands, ivar, ovar


def xm_leak_edge(rels, ovar):
    """The core rf edge (oa, ob) whose target is a leak-function slot of xm (ld inaddr / br_x inreg / st inaddr)."""
    xm = [i for (i, _) in rels.get("Instruction<:isxm", [])][0]
    kind = dict(rels["Instruction<:kind"])[xm].split("$")[0]
    slot = {"TLoad": "inaddr", "TStore": "inaddr", "TBranchx": "inreg"}.get(kind)
    targets = {o for (i, o) in rels.get(f"Instruction<:{slot}", []) if i == xm}
    edges = [(a, b) for (a, b) in rels.get("Operand<:rf", []) if b in targets]
    return [(ovar[a], ovar[b]) for (a, b) in edges]


def pin_pred(rels, mode):
    base = stage_seed.build_pred(rels, "seed_core")
    if mode == "a":
        return base
    if mode == "b":
        out, n = [], 0
        for line in base.splitlines():
            m = re.match(r"^(\s+)(o\d+) in (o\d+)\.rf$", line)
            if m:
                line = f"{m.group(1)}{m.group(2)} in {m.group(3)}.rf.*(ddi.rf)   // [path pin] edge may be subdivided"
                n += 1
            out.append(line)
        return "\n".join(out).replace("// AUTO-GENERATED", f"// [path pin, {n} rf edges relaxed] AUTO-GENERATED")
    if mode == "c":
        kind = dict(rels["Instruction<:kind"])
        res = {i for (i, _) in rels.get("Instruction<:isresolved", [])}
        xm = [i for (i, _) in rels.get("Instruction<:isxm", [])][0]
        spo = dict(rels.get("Instruction<:spo", []))
        # unresolved branches of the core that precede xm in program order
        before, cur = [], xm
        inv = {v: k for k, v in spo.items()}
        while cur in inv:
            cur = inv[cur]
            before.append(cur)
        brs = [b for b in before if kind[b].split("$")[0] in ("TBranchn", "TBranchx") and b not in res]
        if not brs:
            sys.exit("core has no unresolved branch before xm")
        b = brs[0]
        return ("// [leak pin] only the transmitter kind + an unresolved branch of the core's kind before it\n"
                "pred seed_core {\n"
                f"  some disj x, b: Instruction | {{\n"
                f"    x in xm and x in {KIND_SIG[kind[xm].split('$')[0]]}\n"
                f"    b in {KIND_SIG[kind[b].split('$')[0]]} and b not in resolved and x in b.^spo\n"
                "  }\n}")
    raise ValueError(mode)


SHAPES = {
    # verbatim from STAGE1_alloy/models/proposed/STT_6_s4.als (s4-variant, 2026-11-08)
    "s4_shape": """
fun s4_pred_feed : Instruction -> Instruction {
	(Loads & uncommitted) <: (outreg.rf.(~inreg)) :> (unresolved & (Branchns+Branchxs))
}
fun s4_l1 : Instruction { s4_pred_feed.Instruction }
fun s4_b0 : Instruction { (Branchns+Branchxs) & resolved & uncommitted & (^spo).s4_l1 }
pred s4_shape {
  some b0: s4_b0, l1: s4_l1, b1: (Branchns+Branchxs) & unresolved, l2: Loads & uncommitted, t: Loads & xm |
    l1 in b0.^spo and (l1 -> b1) in s4_pred_feed and l2 in b1.^spo and t in l2.^spo
    and some (t.inaddr & l2.outreg.^(rf + ddi))
}
""",
    # verbatim from STAGE1_alloy/models/proposed/STT_6_a3c.als (s4-variant, 2026-11-08)
    "a3c_shape": """
fun a3c_prot_ops : Operand {
	last_committed_protset_p[no_p].(~opstate) + last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p]))
}
fun a3c_witness : Instruction {
	(Branchns+Branchxs) & unresolved & (xm & Branchxs).^spo - (inreg.a3c_prot_ops)
}
pred a3c_shape {
  some b0: (Branchns+Branchxs) & unresolved, l1: Loads, b1: xm & Branchxs, b2: a3c_witness |
    l1 in b0.^spo and b1 in l1.^spo and b2 in b1.^spo
    and some (b1.inreg & l1.outreg.^(rf + ddi))
}
""",
}


def explicit_fold(sig_line, seed_expr):
    """Return Alloy text: nested fold renamed away is done by the caller; this adds PSX + dispatch."""
    T = re.search(r":\s*(\w+)\s*\{", sig_line).group(1)          # State (STT/Recon) or Operand (SPT)
    seed = (lambda p: f"hardware_protection_policy[{p}]") if seed_expr.endswith("[p]") else (lambda p: "hardware_protection_policy")
    rcp = "(RC->first_uncommitted + RR->first_uncommitted)"
    return f"""
// [stage15-bound] EXPLICIT protection-set fold (exact for any N; requires no RI perturbation).
// One relation per perturbation form used by gen_useful_litmus/tag_xm; value after instruction i
// = a[p, i, value after spo-predecessor] (seed before the first instruction), i.e. the nested
// production fold without nesting. With p[RI] empty: spo_p[p] = spo and f[p] = first instruction.
one sig PSX {{
  pn:  Instruction -> {T},
  prr: Instruction -> Instruction -> {T},
  prs: State -> Instruction -> {T},
  prc: Instruction -> {T}
}}
fun s15_last : Instruction {{ Instruction - spo.Instruction }}
fact psx_def {{
  all i: Instruction | i.(PSX.pn) = a[no_p, i, (no spo.i) => {seed('no_p')} else (spo.i).(PSX.pn)]
  all j, i: Instruction | i.(j.(PSX.prr)) = a[RR->j, i, (no spo.i) => {seed('RR->j')} else (spo.i).(j.(PSX.prr))]
  all s: State, i: Instruction | i.(s.(PSX.prs)) = a[RS->s, i, (no spo.i) => {seed('RS->s')} else (spo.i).(s.(PSX.prs))]
  all i: Instruction | i.(PSX.prc) = a[{rcp}, i, (no spo.i) => {seed(rcp)} else (spo.i).(PSX.prc)]
}}
fun last_committed_protset_p[p: PTag->univ] : {T} {{
  (no p) => s15_last.(PSX.pn)
  else (some p[RS]) => s15_last.((p[RS]).(PSX.prs))
  else (some p[RC]) => s15_last.(PSX.prc)
  else s15_last.((p[RR]).(PSX.prr))
}}
pred s15_equiv {{
  last_committed_protset_p[no_p] = last_committed_protset_orig_p[no_p]
  all j: Instruction | last_committed_protset_p[RR->j] = last_committed_protset_orig_p[RR->j]
  all s: State | last_committed_protset_p[RS->s] = last_committed_protset_orig_p[RS->s]
  last_committed_protset_p[{rcp}] = last_committed_protset_orig_p[{rcp}]
}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--core")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--operands", type=int, default=0)
    ap.add_argument("--states", type=int, default=0)
    ap.add_argument("--pin", choices=["a", "b", "c", "none"], default="a")
    ap.add_argument("--ix", choices=["regen", "drop"], default="regen")
    ap.add_argument("--fold", choices=["auto", "keep", "explicit"], default="auto")
    ap.add_argument("--query", choices=["none", "splice_xm", "fold_trunc", "s4_shape", "a3c_shape", "fold_equiv", "otb_shape"], default="none")
    ap.add_argument("--minimality", choices=["prod", "leak_rs", "leak"], default="prod")
    ap.add_argument("--shape", choices=["any", "nospacer", "connected"], default="any",
                    help="nospacer: every instruction has >= 1 operand (bans the operand-free Branchn padding that "
                         "no_extra_inst allows); connected: nospacer + every non-branch instruction is linked to "
                         "xm's operands through rf/ddi/same-instruction edges")
    ap.add_argument("--intbits", type=int, default=0,
                    help="add 'B Int' to the scope. REQUIRED once more than 7 operands can sit on one instruction: "
                         "with the default 4-bit Int, '#(i.inaddr) <= 1' wraps (8 -> -8) and the limited_* facts stop binding")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    text = Path(a.model).read_text()
    hdr = [f"// [stage15-bound DRAFT 2026-11-08] generated by proposed_twophase/stage15_bound/make_s15_model.py",
           f"//   from {Path(a.model).name}; core={Path(a.core).name if a.core else None}; n={a.n} operands={a.operands or 'for 9'} "
           f"states={a.states or 'for 9'} pin={a.pin} ix={a.ix} fold={a.fold} query={a.query} minimality={a.minimality} shape={a.shape}",
           "//   Only scope-tied edits (scope, IX, fold depth) + the seed/query; defense block untouched."]

    fs, fe, sig_line, seed_expr = fold_parts(text)
    if a.n > 7 and a.fold in ("auto", "explicit"):
        text = text[:fs] + gen_fold(sig_line, seed_expr, a.n) + text[fe:]
    if a.fold == "explicit":
        fs, fe = find_block(text, r"^fun last_committed_protset_p\[")
        text = text[:fs] + text[fs:fe].replace("fun last_committed_protset_p[", "fun last_committed_protset_orig_p[", 1) + text[fe:]
        text += explicit_fold(sig_line, seed_expr)
    if a.query == "fold_trunc":
        if a.n <= 7:
            sys.exit("fold_trunc needs n > 7")
        full = gen_fold(sig_line, seed_expr, a.n, name="last_committed_protset_full_p")
        ss, se = find_block(text, r"^pred secure_speculation_scheme_p\[")
        sec = text[ss:se].replace("pred secure_speculation_scheme_p[", "pred secure_full_p[").replace(
            "last_committed_protset_p[", "last_committed_protset_full_p[")
        text += "\n\n// [stage15-bound] full-depth fold + secure predicate for the fold_trunc query\n" + full + "\n\n" + sec + "\n"

    if a.minimality != "prod":
        ms, me = find_block(text, r"^let gen_useful_litmus \{")
        body = ["  not secure_speculation_scheme_p[no_p]"]
        if a.minimality == "leak_rs":
            body.append("  all s: State | secure_speculation_scheme_p[RS->s]")
        text = text[:ms] + "let gen_useful_litmus {  // [stage15-bound] minimality=" + a.minimality + "\n" + "\n".join(body) + "\n}" + text[me:]
    if a.n != 6 or a.ix == "drop":
        text = regen_ix(text, a.n, a.ix)

    scope_pat = r"for 9 but exactly 6 Instruction"
    if text.count(scope_pat) != 1:
        sys.exit("scope anchor not found exactly once")
    scope = f"for 9 but exactly {a.n} Instruction"
    if a.operands:
        scope += f", {a.operands} Operand"
    if a.states:
        scope += f", {a.states} State"
    if a.intbits:
        scope += f", {a.intbits} Int"
    text = text.replace(scope_pat, scope)

    conj = []
    extra = ""
    if a.pin != "none":
        rels = stage_seed.parse_txt(a.core)
        extra += "\n\n" + pin_pred(rels, a.pin) + "\n"
        conj.append("seed_core")
        if a.query == "splice_xm":
            _, _, _, ovar = core_info(rels)
            edges = xm_leak_edge(rels, ovar)
            if not edges:
                sys.exit("core has no rf edge into xm's leak operand")
            body = " or ".join(
                f"(some o: (Otherns + Otherxs) | some (o.inreg & {oa}.rf.*(ddi.rf)) and {ob} in o.outreg.rf.*(ddi.rf))"
                for (oa, ob) in edges)
            # the seed's operand variables are local to seed_core, so restate the seed with the query inside
            seed_text = pin_pred(rels, a.pin)
            seed_text = seed_text.replace("pred seed_core {", "pred seed_core_splice {")
            seed_text = re.sub(r"\n  \}\n\}\s*$", f"\n    {body}\n  }}\n}}", seed_text.rstrip() + "\n")
            extra += "\n" + seed_text + "\n"
            conj[-1] = "seed_core_splice"
    if a.query == "fold_trunc":
        conj.append("secure_full_p[no_p]")
    if a.shape != "any":
        extra += "\nfact s15_nospacer { all i: Instruction | some i.operands }\n"
        if a.shape == "connected":
            extra += ("fact s15_connected { all i: Instruction - (Branchns + Branchxs) |\n"
                      "  some i.operands & xm.operands.*(rf + ~rf + ddi + ~ddi + (~operands).operands) }\n")
    if a.query == "otb_shape":
        extra += "\npred otb_shape { some x: Loads | (x in xm) and (some o: (Otherns+Otherxs) | some (o.outreg & rf.(x.inaddr))) }\n"
        conj.append("otb_shape")
    if a.query in ("s4_shape", "a3c_shape"):
        extra += SHAPES[a.query]
        conj.append(a.query)
    needle = "run gen_lit {\n  gen_useful_litmus\n}"
    if text.count(needle) != 1:
        sys.exit("run needle not found exactly once")
    if a.query == "fold_equiv":
        if a.fold != "explicit":
            sys.exit("fold_equiv needs --fold explicit")
        text = text.replace(needle, "run gen_lit {\n  not s15_equiv   // facts only: expect UNSAT\n}")
        extra = ""
    else:
        text = text.replace(needle, "run gen_lit {\n  gen_useful_litmus\n" + "".join(f"  {c}\n" for c in conj) + "}")
    Path(a.out).write_text("\n".join(hdr) + "\n" + text + extra)
    print(a.out)


if __name__ == "__main__":
    main()
