#!/usr/bin/env python3
# Usage: python3 spt_semantics.py <dir-with-inst-*.txt> [--max N] [--show K] [--json out.json]
"""spt_semantics.py -- independent Python re-implementation of the SPT defense semantics on Alloy instance
dumps (SPT agent, ultimate-models round, 2026-11-09). Read-only on the dumps.

Semantics (flat models: the perturbations gen_useful_litmus uses are no_p, RR->i, RC+RR->first_uncommitted,
RS->s; no RI/RO, so fix_rf_hole_p is empty and i_p = Instruction):
  v2   SPT_6_oneLP_v2.als:375-396   7-position program-order fold from the near-total seed, then the
                                    skeleton check (P & spec_xmit) + (P.^(rf+ddi) & spec_xmit)
  u    proposed/ultimate/SPT_6_u.als  least fixpoint of the SPT untaint rules (declassification of
                                    non-speculative load/store addresses, register identity over rf,
                                    forward ALU, backward on InvOp, STL with STLPublic + store uncommitted);
                                    flagged = tainted speculative transmitter operands
Per instance: useful (= gen_useful_litmus and tag_xm) under each semantics, the fixpoint depth u needed,
and for every v2/u disagreement the first clause that differs, classified by mechanism:
  S1_declass    xm's value is the address of a non-speculative load/store (same physical register)
  B1_branch     xm's value is the predicate of a non-speculative br_x (v2 declassified it, u does not)
  P3_const      xm's value has no load in its rf/ALU backward cone (forward untaint to the fixpoint)
  BWD_inv       u untainted xm's value through an InvOp (backward rule)
  STL           a store->load rf on xm's backward cone (STLPublic gate / transitive cancel)
  other         none of the above (printed in full)"""
import re, sys, json, glob, os, collections

pat = re.compile(r'this/([A-Za-z_]+(?:<:[A-Za-z_]+)?)=\{(.*)\}')


def parse(path):
    R = {}
    for line in open(path):
        m = pat.match(line.strip())
        if not m:
            continue
        body = m.group(2).strip()
        R[m.group(1)] = [tuple(x.strip() for x in t.split('->')) for t in body.split(',')] if body else []
    return R


def B(a): return a.split('$')[0]


class Inst:
    def __init__(self, path):
        R = parse(path)
        self.path = path
        self.ins = [a for (a,) in R['Instruction']]
        self.kind = {i: B(k)[1:] for i, k in R['Instruction<:kind']}
        spo = dict(R['Instruction<:spo'])
        first = [i for i in self.ins if i not in set(spo.values())][0]
        self.order = [first]
        while self.order[-1] in spo:
            self.order.append(spo[self.order[-1]])
        self.pos = {i: k for k, i in enumerate(self.order)}
        self.resolved = {i for i, _ in R.get('Instruction<:isresolved', [])}
        self.committed = {i for i, _ in R.get('Instruction<:iscommitted', [])}
        self.xm = [i for i, _ in R.get('Instruction<:isxm', [])][0]
        self.invop = {a for (a,) in R.get('InvOp', [])}
        self.opsof = collections.defaultdict(lambda: collections.defaultdict(list))
        self.owner, self.slot = {}, {}
        for sl in ('inreg', 'inaddr', 'outreg', 'inmem', 'outmem'):
            for i, o in R.get('Instruction<:' + sl, []):
                self.opsof[i][sl].append(o)
                self.owner[o] = i
                self.slot[o] = sl
        self.opstate = dict(R['Operand<:opstate'])
        self.rf = [(a, b) for a, b in R.get('Operand<:rf', [])]
        self.ddi = [(a, b) for a, b in R.get('Operand<:ddi', [])]
        self.states = sorted(set(self.opstate.values()))
        self.ops = list(self.owner)
        unc = [i for i in self.order if i not in self.committed]
        self.fu = unc[0] if unc else None

    def K(self, i, *ks): return self.kind[i] in ks
    def get(self, i, sl): return self.opsof[i].get(sl, [])
    def before(self, a, b): return self.pos[a] < self.pos[b]

    # ------------------------------------------------------------------ perturbed view
    def view(self, RR=(), RC=(), RS=()):
        V = {}
        V['o'] = {o for o in self.ops if self.opstate[o] not in set(RS)}
        committed = self.committed | set(RC)
        unres_br = [i for i in self.order if i not in self.resolved and i not in set(RR)
                    and self.K(i, 'Branchn', 'Branchx')]
        after = set()
        for b in unres_br:
            after |= {j for j in self.order if self.before(b, j)}
        V['uncommitted'] = {i for i in self.order if i not in committed}
        V['spec'] = {i for i in self.order if i not in committed and i in after}
        o = V['o']
        leak = set()
        for i in self.order:
            if self.K(i, 'Load', 'Store'):
                leak |= set(self.get(i, 'inaddr'))
            if self.K(i, 'Branchx'):
                leak |= set(self.get(i, 'inreg'))
        leak &= o
        V['spec_x'] = {x for x in leak if self.owner[x] in V['spec']}
        V['nonspec_x'] = {x for x in leak if self.owner[x] not in V['spec']}
        V['leak'] = leak
        V['rf'] = [(a, b) for a, b in self.rf if a in o and b in o]
        V['ddi'] = [(a, b) for a, b in self.ddi if a in o and b in o]
        return V

    # ------------------------------------------------------------------ v2
    def flag_v2(self, V):
        o_p, rf = V['o'], V['rf']
        fed = {b for a, b in rf if self.slot[a] == 'outreg'}
        P = {x for x in o_p if not (self.slot[x] in ('inreg', 'inaddr') and x not in fed)}
        prod = {b: a for a, b in rf}
        for i in self.order[:7]:
            o = set(P)
            rem = set()
            for x in self.opsof[i]['inreg'] + self.opsof[i]['inaddr'] + self.opsof[i]['outreg'] + \
                    self.opsof[i]['inmem'] + self.opsof[i]['outmem']:
                if x in V['nonspec_x']:
                    rem.add(x)
                    if x in prod:
                        rem.add(prod[x])
            if self.K(i, 'Othern', 'Otherx'):
                ins = self.get(i, 'inreg')
                if not ins:
                    rem |= set(self.get(i, 'outreg'))
                if not any(x in o for x in ins):
                    rem |= set(self.get(i, 'outreg'))
            for x in self.get(i, 'inreg') + self.get(i, 'inaddr'):
                if x in prod and prod[x] not in o:
                    rem.add(x)
            if self.K(i, 'Load'):
                for m in self.get(i, 'inmem'):
                    if m in prod:
                        s = self.owner[prod[m]]
                        if self.K(s, 'Store') and self.get(s, 'inreg') and not any(x in o for x in self.get(s, 'inreg')):
                            rem |= set(self.get(i, 'outreg')) | set(self.get(i, 'inmem'))
            P = o - rem
        reach = set(P)
        edges = collections.defaultdict(set)
        for a, b in V['rf'] + V['ddi']:
            edges[a].add(b)
        stack = list(P)
        trans = set()
        while stack:
            a = stack.pop()
            for b in edges[a]:
                if b not in trans:
                    trans.add(b)
                    stack.append(b)
        return (P & V['spec_x']) | (trans & V['spec_x'])

    # ------------------------------------------------------------------ u
    def public_u(self, V, depth_out=None):
        o, rf = V['o'], V['rf']
        regrf = [(a, b) for a, b in rf if self.slot[a] == 'outreg']
        fed = {b for a, b in regrf}
        U = {x for x in o if self.slot[x] in ('inreg', 'inaddr') and x not in fed}
        U |= {x for x in V['nonspec_x'] if self.slot[x] == 'inaddr'}
        adj = collections.defaultdict(set)
        for a, b in regrf:
            adj[a].add(b)
            adj[b].add(a)

        def close(S):
            S = set(S)
            stack = list(S)
            while stack:
                a = stack.pop()
                for b in adj[a]:
                    if b not in S:
                        S.add(b)
                        stack.append(b)
            return S
        mprod = {b: a for a, b in rf if self.slot[a] == 'outmem'}
        g = lambda i, sl: [x for x in self.get(i, sl) if x in o]
        U = close(U)
        steps = 0
        while True:
            new = set(U)
            for i in self.order:
                if self.K(i, 'Othern', 'Otherx') and all(x in U for x in g(i, 'inreg')):
                    new |= set(g(i, 'outreg'))
                if i in self.invop and any(x in U for x in g(i, 'outreg')) and \
                        len([x for x in g(i, 'inreg') if x not in U]) <= 1:
                    new |= set(g(i, 'inreg'))
            for l in self.order:
                if not self.K(l, 'Load'):
                    continue
                for m in g(l, 'inmem'):
                    if m not in mprod:
                        continue
                    s = self.owner[mprod[m]]
                    if not self.K(s, 'Store') or s not in V['uncommitted']:
                        continue
                    between = [s2 for s2 in self.order if self.K(s2, 'Store') and (s2 == s or self.before(s, s2))
                               and self.before(s2, l)]
                    if not all(x in U for x in g(l, 'inaddr')) or \
                            not all(x in U for s2 in between for x in g(s2, 'inaddr')):
                        continue
                    if all(x in U for x in g(s, 'inreg')):
                        new |= set(g(l, 'outreg'))
                    if any(x in U for x in g(l, 'outreg')):
                        new |= set(g(s, 'inreg'))
            new = close(new)
            if new == U:
                break
            U = new
            steps += 1
        if depth_out is not None:
            depth_out.append(steps)
        return U

    def flag_u(self, V, depth_out=None):
        U = self.public_u(V, depth_out)
        return (V['leak'] - U) & V['spec_x']

    # ------------------------------------------------------------------ gen_useful_litmus
    def perts(self):
        yield 'no_p', {}
        for i in self.order:
            if i not in self.resolved and i != self.fu:
                yield f'RR->{self.kind[i]}@{self.pos[i]}', dict(RR=[i])
        if self.fu is not None:
            yield f'RC+RR->fu({self.kind[self.fu]}@{self.pos[self.fu]})', dict(RR=[self.fu], RC=[self.fu])
        for s in self.states:
            yield f'RS->{s}', dict(RS=[s])

    def useful(self, sem, depths=None):
        fl = (lambda V: self.flag_v2(V)) if sem == 'v2' else (lambda V: self.flag_u(V, depths))
        V0 = self.view()
        f0 = fl(V0)
        if not f0 or not (f0 & set(sum((self.opsof[self.xm][s] for s in self.opsof[self.xm]), []))):
            return False, 'tag/no_p'
        for name, kw in self.perts():
            if name == 'no_p':
                continue
            if fl(self.view(**kw)):
                return False, name
        return True, ''

    # ------------------------------------------------------------------ mechanism of a disagreement
    def xm_val(self):
        return [x for sl in ('inaddr', 'inreg') for x in self.get(self.xm, sl)
                if (sl == 'inaddr' and self.K(self.xm, 'Load', 'Store')) or (sl == 'inreg' and self.K(self.xm, 'Branchx'))]

    def mechanism(self):
        V = self.view()
        prod = {b: a for a, b in self.rf}
        readers = collections.defaultdict(set)
        for a, b in self.rf:
            readers[a].add(b)
        tags = set()
        for x in self.xm_val():
            p = prod.get(x)
            if p is None:
                continue
            comp = readers[p]
            if any(y in V['nonspec_x'] and self.slot[y] == 'inaddr' for y in comp):
                tags.add('S1_declass')
            if any(y in V['nonspec_x'] and self.K(self.owner[y], 'Branchx') for y in comp):
                tags.add('B1_branch')
            # backward cone over rf + same-instruction input->output
            cone, stack, loads, stl, inv = set(), [x], False, False, False
            while stack:
                a = stack.pop()
                if a in cone:
                    continue
                cone.add(a)
                if a in prod:
                    stack.append(prod[a])
                    if self.slot[prod[a]] == 'outmem':
                        stl = True
                if self.slot[a] in ('outreg', 'outmem'):
                    j = self.owner[a]
                    if self.K(j, 'Load'):
                        loads = True
                        stack += self.get(j, 'inmem')
                    else:
                        stack += self.get(j, 'inreg')
                    if j in self.invop:
                        inv = True
            if not loads:
                tags.add('P3_const')
            if stl:
                tags.add('STL')
            if inv:
                tags.add('BWD_inv')
        return sorted(tags) or ['other']

    def show(self):
        out = []
        for i in self.order:
            st = lambda x: ('r' if self.opstate[x].startswith('Reg') else 'M') + self.opstate[x].split('$')[1]
            sl = ' '.join(f"{s}={','.join(st(x) for x in self.get(i, s))}"
                          for s in ('inreg', 'inaddr', 'inmem', 'outreg', 'outmem') if self.get(i, s))
            out.append(f"  {self.pos[i]} {self.kind[i]:7s} {'C' if i in self.committed else '-'}"
                       f"{'R' if i in self.resolved else 'u'}{' XM' if i == self.xm else ''}"
                       f"{' InvOp' if i in self.invop else ''} {sl}")
        out.append('  rf: ' + ', '.join(f"{self.pos[self.owner[a]]}.{self.slot[a]}->{self.pos[self.owner[b]]}.{self.slot[b]}" for a, b in self.rf)
                   + ('   ddi: ' + ', '.join(f"{self.pos[self.owner[a]]}.{self.slot[a]}->{self.slot[b]}" for a, b in self.ddi) if self.ddi else ''))
        return '\n'.join(out)


def main():
    d = sys.argv[1]
    mx = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 10 ** 9
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 2
    files = sorted(glob.glob(os.path.join(d, 'inst-*.txt')))[:mx]
    C, EX, depths, rows = collections.Counter(), collections.defaultdict(list), [], []
    for f in files:
        I = Inst(f)
        dl = []
        uu, ur = I.useful('u', dl)
        uv, vr = I.useful('v2')
        depths += dl
        key = f"u={'Y' if uu else 'n'} v2={'Y' if uv else 'n'}"
        mech = ''
        if uu != uv:
            mech = '+'.join(I.mechanism())
            key += f" | u-fails-at={ur or '-'} v2-fails-at={vr or '-'} | {mech}"
        C[key] += 1
        EX[key].append(f)
        rows.append(dict(f=os.path.basename(f), u=uu, v2=uv, u_fail=ur, v2_fail=vr, mech=mech, xm=I.kind[I.xm]))
    print(f"{len(files)} instances from {d}")
    for k, n in C.most_common():
        print(f"{n:5d}  {k}")
        for f in EX[k][:show]:
            if '|' in k:
                print('       ' + os.path.basename(f))
                print(Inst(f).show())
    if depths:
        print(f"u fixpoint depth (steps after the initial closure) over all evaluated views: max={max(depths)} "
              f"histogram={dict(sorted(collections.Counter(depths).items()))}")
    if '--json' in sys.argv:
        json.dump(rows, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)


if __name__ == '__main__':
    main()
