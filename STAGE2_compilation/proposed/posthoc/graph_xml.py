#!/usr/bin/env python3
"""graph_xml.py -- graph-checker design prototype (2026-11-08, wiki/design/POSTHOC_GRAPH_CHECKER.md).

A tiny execution-graph IR for SimSpect programs, plus:
  * load(inst.xml)      Alloy instance XML -> Graph
  * Graph.to_xml(tmpl)  Graph -> Alloy instance XML (re-uses an instance XML of the SAME model as the
                        sig/field skeleton), so PosthocEval.java can evaluate the model's own predicates on it
  * mutations that mirror Stage-2 insertions: splice (value-preserving ALU on the xm edge),
    filler (reads two live registers, writes a fresh one), nonspec_reload (a committed load of the
    transmitter's source location before the window).
  * fold_exprs(n, kind)  the protection-set fold of the shared skeleton (STT_6.als:232-243) unrolled to
                        depth n, plus the insecure condition (STT_6.als:262-265 / SPT_6_oneLP_v2.als:286-297)
                        over it, as Alloy expression strings; needed because the model hard-codes 7 fold steps.
Read-only on everything in the repo; writes only the output dir given on the command line.

Usage: graph_xml.py <inst.xml> <outdir> [--model-kind state|operand]
  writes <outdir>/<stem>__{orig,splice,filler,reload,splice2_reload}.xml and <outdir>/exprs_<n>.txt
"""
import copy, sys, os, argparse
import xml.etree.ElementTree as ET

SLOTS = ('inreg', 'inaddr', 'inmem', 'outreg', 'outmem')
SLOT_SIG = {'inreg': 'Inreg', 'inaddr': 'Inaddr', 'inmem': 'Inmem', 'outreg': 'Outreg', 'outmem': 'Outmem'}
KIND_ATOM = {'ld': 'TLoad$0', 'str': 'TStore$0', 'br_n': 'TBranchn$0', 'br_x': 'TBranchx$0',
             'other_n': 'TOthern$0', 'other_x': 'TOtherx$0'}
ATOM_KIND = {v: k for k, v in KIND_ATOM.items()}


class Graph:
    """instrs: list (program order) of dict(kind, committed, resolved, xm, ops=[(slot, op_id)])
    ops: op_id -> dict(slot, state)  (state = 'Reg_s$k' | 'Mem_s$k');  rf, ddi: sets of (op_id, op_id)."""
    def __init__(self):
        self.instrs, self.ops, self.rf, self.ddi = [], {}, set(), set()
        self._n = 0

    def new_op(self, slot, state):
        self._n += 1
        oid = f'o{self._n}'
        self.ops[oid] = dict(slot=slot, state=state)
        return oid

    def states(self):
        return sorted({o['state'] for o in self.ops.values()})

    def fresh_state(self, kind):
        k = 0
        while f'{kind}${k}' in self.states():
            k += 1
        return f'{kind}${k}'

    def owner(self, oid):
        for i, ins in enumerate(self.instrs):
            if any(o == oid for _, o in ins['ops']):
                return i
        raise KeyError(oid)

    def xm_index(self):
        return [i for i, ins in enumerate(self.instrs) if ins['xm']][0]

    def leak_op(self):
        """The transmitter's leak operand (leakage_function: Loads.inaddr + Branchxs.inreg [+ Stores.inaddr])."""
        ins = self.instrs[self.xm_index()]
        want = 'inaddr' if ins['kind'] in ('ld', 'str') else 'inreg'
        return [o for s, o in ins['ops'] if s == want]

    # ---------------- XML emit ------------------------------------------------------------------
    def to_xml(self, template_path, out_path):
        tree = ET.parse(template_path)
        root = tree.getroot()
        inst = root.find('instance')
        N = len(self.instrs)
        iat = [f'Instruction${k}' for k in range(N)]
        oat, cnt = {}, {}
        for oid, o in self.ops.items():
            sig = SLOT_SIG[o['slot']]
            oat[oid] = f'{sig}${cnt.get(sig, 0)}'
            cnt[sig] = cnt.get(sig, 0) + 1
        sig_atoms = {'this/Instruction': iat,
                     'this/Reg_s': [s for s in self.states() if s.startswith('Reg_s')],
                     'this/Mem_s': [s for s in self.states() if s.startswith('Mem_s')]}
        for sig in SLOT_SIG.values():
            sig_atoms[f'this/{sig}'] = [oat[o] for o in self.ops if SLOT_SIG[self.ops[o]['slot']] == sig]
        tuples = {
            'kind': [(iat[i], KIND_ATOM[x['kind']]) for i, x in enumerate(self.instrs)],
            # idx: Alloy has only IX0..IX5; positions >= 6 reuse IX5 (violates the symmetry facts only)
            'idx': [(iat[i], f'IX{min(i, 5)}$0') for i in range(N)],
            'spo': [(iat[i], iat[i + 1]) for i in range(N - 1)],
            'isresolved': [(iat[i], 'rBool$0') for i, x in enumerate(self.instrs) if x['resolved']],
            'iscommitted': [(iat[i], 'cBool$0') for i, x in enumerate(self.instrs) if x['committed']],
            'isxm': [(iat[i], 'tBool$0') for i, x in enumerate(self.instrs) if x['xm']],
            'opstate': [(oat[o], self.ops[o]['state']) for o in self.ops],
            'rf': [(oat[a], oat[b]) for a, b in sorted(self.rf)],
            'ddi': [(oat[a], oat[b]) for a, b in sorted(self.ddi)],
        }
        for s in SLOTS:
            tuples[s] = [(iat[i], oat[o]) for i, x in enumerate(self.instrs) for sl, o in x['ops'] if sl == s]
        for el in inst:
            lab = el.get('label')
            if el.tag == 'sig' and lab in sig_atoms:
                for a in list(el.findall('atom')):
                    el.remove(a)
                for k, name in enumerate(sig_atoms[lab]):
                    e = ET.Element('atom', label=name)
                    el.insert(k, e)
            if el.tag == 'field' and lab in tuples:
                types = el.find('types')
                for t in list(el.findall('tuple')):
                    el.remove(t)
                for k, tup in enumerate(tuples[lab]):
                    t = ET.Element('tuple')
                    for a in tup:
                        ET.SubElement(t, 'atom', label=a)
                    el.insert(k, t)
        # drop skolem entries (they refer to the old atoms)
        for sk in list(inst.findall('skolem')):
            inst.remove(sk)
        tree.write(out_path)


def load(path):
    root = ET.parse(path).getroot().find('instance')
    sig = {e.get('label'): [a.get('label') for a in e.findall('atom')] for e in root.findall('sig')}
    fld = {e.get('label'): [tuple(a.get('label') for a in t.findall('atom')) for t in e.findall('tuple')]
           for e in root.findall('field')}
    spo = dict(fld['spo'])
    instrs = sig['this/Instruction']
    first = [i for i in instrs if i not in set(spo.values())][0]
    order = [first]
    while order[-1] in spo:
        order.append(spo[order[-1]])
    G = Graph()
    kind = dict(fld['kind'])
    res = {i for i, _ in fld['isresolved']}
    com = {i for i, _ in fld['iscommitted']}
    xm = {i for i, _ in fld['isxm']}
    st = dict(fld['opstate'])
    amap = {}
    for i in order:
        ops = []
        for s in SLOTS:
            for (ii, o) in fld[s]:
                if ii == i:
                    oid = G.new_op(s, st[o])
                    amap[o] = oid
                    ops.append((s, oid))
        G.instrs.append(dict(kind=ATOM_KIND[kind[i]], committed=i in com, resolved=i in res, xm=i in xm, ops=ops))
    G.rf = {(amap[a], amap[b]) for a, b in fld['rf']}
    G.ddi = {(amap[a], amap[b]) for a, b in fld['ddi']}
    return G


# ---------------- Stage-2-like insertions ----------------------------------------------------------
def splice(G):
    """Value-preserving ALU (e.g. `addq $0, %r`) on the rf edge into xm's leak operand: same Reg_s in
    and out, rf prod->splice.in, splice.out->consumer, ddi in->out. Placed right before the transmitter."""
    G = copy.deepcopy(G)
    leak = G.leak_op()
    edges = [(a, b) for a, b in G.rf if b in leak]
    if not edges:
        return None
    a, b = edges[0]
    st = G.ops[b]['state']
    x = G.xm_index()
    ii, oo = G.new_op('inreg', st), G.new_op('outreg', st)
    G.rf -= {(a, b)}
    G.rf |= {(a, ii), (oo, b)}
    G.ddi |= {(ii, oo)}
    flags = G.instrs[x]
    G.instrs.insert(x, dict(kind='other_n', committed=flags['committed'], resolved=flags['resolved'], xm=False,
                            ops=[('inreg', ii), ('outreg', oo)]))
    return G


def filler(G):
    """Read-only filler: reads the value the transmitter reads, writes a register no Alloy op uses."""
    G = copy.deepcopy(G)
    leak = G.leak_op()
    src = [a for a, b in G.rf if b in leak]
    if not src:
        return None
    x = G.xm_index()
    st = G.ops[src[0]]['state']
    ii, oo = G.new_op('inreg', st), G.new_op('outreg', G.fresh_state('Reg_s'))
    G.rf |= {(src[0], ii)}
    G.ddi |= {(ii, oo)}
    f = G.instrs[x]
    G.instrs.insert(x, dict(kind='other_n', committed=f['committed'], resolved=f['resolved'], xm=False,
                            ops=[('inreg', ii), ('outreg', oo)]))
    return G


def nonspec_reload(G):
    """A committed, resolved load of the speculative source location, placed first (before the window).
    Not something Stage 2 does today (rule 2 of MODEL_AUDIT Q3 forbids inserted loads on Alloy memory);
    it is the negative control: STT_6's location-based fold (STT_6.als:331) declassifies the location."""
    G = copy.deepcopy(G)
    mems = [o for i in G.instrs if i['kind'] == 'ld' and not i['committed'] for s, o in i['ops'] if s == 'inmem']
    if not mems:
        return None
    st = G.ops[mems[0]]['state']
    im, orr = G.new_op('inmem', st), G.new_op('outreg', G.fresh_state('Reg_s'))
    G.ddi |= {(im, orr)}
    G.instrs.insert(0, dict(kind='ld', committed=True, resolved=True, xm=False, ops=[('inmem', im), ('outreg', orr)]))
    return G


def fold_exprs(n, model_kind):
    """Unrolled fold a[p, f.spo^k, ...] for k = n-1 .. 0 (STT_6.als:232-243 has k = 6 .. 0 hard-coded)."""
    def step(k):
        return 'f[no_p]' + '.(spo_p[no_p])' * k
    seed = 'hardware_protection_policy' if model_kind == 'state_const' else 'hardware_protection_policy[no_p]'
    e = seed
    for k in range(n):
        e = f'a[no_p, {step(k)}, {e}]'
    P = f'({e})' + ('.(~opstate)' if model_kind.startswith('state') else '')
    insecure = (f'some (({P} & speculative_xmit_p[no_p]) + ({P}.(^(op_edges_p[no_p])) & speculative_xmit_p[no_p]))')
    return insecure


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml'); ap.add_argument('outdir')
    ap.add_argument('--model-kind', default='state_const', choices=['state_const', 'state_p', 'operand'])
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    stem = os.path.basename(a.xml)[:-4]
    G = load(a.xml)
    variants = {'orig': G, 'splice': splice(G), 'filler': filler(G), 'reload': nonspec_reload(G)}
    s = splice(G)
    variants['splice2_reload'] = nonspec_reload(splice(s)) if s is not None and splice(s) is not None else None
    for name, g in variants.items():
        if g is not None:
            g.to_xml(a.xml, os.path.join(a.outdir, f'{stem}__{name}.xml'))
            print(name, len(g.instrs), 'instrs')


if __name__ == '__main__':
    main()


def to_txt(G, path):
    """Graph -> Alloy sol.toString()-style dump, for the hand-port mf_semantics.py (option (a) cross-check)."""
    N = len(G.instrs)
    iat = [f'Instruction${k}' for k in range(N)]
    oat, cnt = {}, {}
    for oid, o in G.ops.items():
        sig = SLOT_SIG[o['slot']]
        oat[oid] = f'{sig}${cnt.get(sig, 0)}'; cnt[sig] = cnt.get(sig, 0) + 1
    def rel(name, tups):
        return f'this/{name}={{' + ', '.join('->'.join(t) for t in tups) + '}'
    L = [rel('Instruction', [(a,) for a in iat]),
         rel('Instruction<:kind', [(iat[i], KIND_ATOM[x['kind']]) for i, x in enumerate(G.instrs)]),
         rel('Instruction<:spo', [(iat[i], iat[i + 1]) for i in range(N - 1)]),
         rel('Instruction<:isresolved', [(iat[i], 'rBool$0') for i, x in enumerate(G.instrs) if x['resolved']]),
         rel('Instruction<:iscommitted', [(iat[i], 'cBool$0') for i, x in enumerate(G.instrs) if x['committed']]),
         rel('Instruction<:isxm', [(iat[i], 'tBool$0') for i, x in enumerate(G.instrs) if x['xm']]),
         rel('Operand<:opstate', [(oat[o], G.ops[o]['state']) for o in G.ops]),
         rel('Operand<:rf', [(oat[a], oat[b]) for a, b in sorted(G.rf)]),
         rel('Operand<:ddi', [(oat[a], oat[b]) for a, b in sorted(G.ddi)])]
    for s in SLOTS:
        L.append(rel(f'Instruction<:{s}', [(iat[i], oat[o]) for i, x in enumerate(G.instrs) for sl, o in x['ops'] if sl == s]))
    open(path, 'w').write('\n'.join(L) + '\n')
