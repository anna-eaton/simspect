#!/usr/bin/env python3
# Usage: [NOGEN=1] python3 mkq.py <model.als> <out.als> <pred-file> ["for ... scope"]   Writes a query copy: conjoins `q` into `run gen_lit` (NOGEN=1: facts + q only). Never point <out.als> into STAGE1_alloy/models/.
"""mkq.py MODEL OUT.als PREDFILE [SCOPE]  -- scratch query copy: conjoin `q` into run gen_lit."""
import sys, re
model, out, predfile = sys.argv[1:4]
scope = sys.argv[4] if len(sys.argv) > 4 else None
t = open(model).read()
needle = "run gen_lit {\n  gen_useful_litmus\n}"
assert t.count(needle) == 1, "needle"
import os
nogen = os.environ.get("NOGEN") == "1"
t = t.replace(needle, "run gen_lit {\n  " + ("" if nogen else "gen_useful_litmus\n  ") + "q\n}")
if scope:
    t = re.sub(r"(run gen_lit \{\n  (?:gen_useful_litmus\n  )?q\n\}) for [^\n]*", r"\1 " + scope, t)
t += "\n\n// ---- scratch query (model-audit 2026-11-08) ----\n" + open(predfile).read() + "\n"
open(out, "w").write(t)
