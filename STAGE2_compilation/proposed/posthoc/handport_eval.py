#!/usr/bin/env python3
"""handport_eval.py -- option (a) side of the graph-checker prototype: evaluate the leak condition at no_p
with the existing hand-port STAGE3_gem5/triage/model_audit_20261108/mf_semantics.py on Graph .txt dumps.
Prints: <file> <sem> insecure=<bool> xm_flagged=<bool> (one line per file and semantics)."""
import sys, glob, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../STAGE3_gem5/triage/model_audit_20261108'))
import mf_semantics as M
t = time.time(); n = 0
for f in sorted(glob.glob(os.path.join(sys.argv[1], '*.txt'))):
    I = M.Inst(f); V = I.view()
    for sem in sys.argv[2].split(','):
        fl = I.flags(sem, V)
        print(os.path.basename(f)[:-4], sem, 'insecure=%s' % bool(fl), 'xm_flagged=%s' % any(I.owner[o] in I.xm for o in fl))
    n += 1
print('# %d files, %.3f ms/file' % (n, (time.time() - t) * 1e3 / max(n, 1)), file=sys.stderr)
