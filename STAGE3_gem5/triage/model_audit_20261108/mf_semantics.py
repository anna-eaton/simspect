#!/usr/bin/env python3
# Usage: python3 mf_semantics.py <dir-with-inst-*.txt> [--max N] [--json out.json]
"""mf_semantics.py -- independent Python re-implementation of four defense semantics on Alloy instance
dumps (model-fixes session, 2026-11-08), for the old-vs-new differentials in
wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".

Semantics (flat models: the perturbations gen_useful_litmus uses are no_p, RR->i, RC+RR->first_uncommitted,
RS->s; no RI/RO, so fix_rf_hole_p is empty):
  stt_old    STT_6.als        protection = Mem_s minus the location of every load with no unresolved
                              branch before it (or being one); lifted to all operands of those states.
  recon_old  Recon_6.als      stt_old with the (no-op) reveal seed Recon_6.als:316-318, literally.
  stt_v2     STT_6_v2.als     protection = Inmem of every speculative load (instance-based).
  recon_v2   Recon_6_v2.als   stt_v2 minus revealed reads (direct committed load pair, no store between).
Per instance it reports useful (= gen_useful_litmus AND tag_xm) under each semantics, the rf-fact
violation (rf_from_most_recent_writer), and an explanation for every useful/not-useful difference.
Only reads the dumps."""
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
        self.kind = {i: B(k)[1:] for i, k in R['Instruction<:kind']}       # Load Store Branchn Branchx Othern Otherx
        spo = dict(R['Instruction<:spo'])
        first = [i for i in self.ins if i not in set(spo.values())][0]
        self.order = [first]
        while self.order[-1] in spo:
            self.order.append(spo[self.order[-1]])
        self.pos = {i: k for k, i in enumerate(self.order)}
        self.resolved = {i for i, _ in R.get('Instruction<:isresolved', [])}
        self.committed = {i for i, _ in R.get('Instruction<:iscommitted', [])}
        self.xm = {i for i, _ in R.get('Instruction<:isxm', [])}
        self.opsof = collections.defaultdict(dict)   # instr -> slot -> [ops]
        self.owner, self.slot = {}, {}
        for sl in ('inreg', 'inaddr', 'outreg', 'inmem', 'outmem'):
            for i, o in R.get('Instruction<:' + sl, []):
                self.opsof[i].setdefault(sl, []).append(o)
                self.owner[o] = i; self.slot[o] = sl
        self.opstate = dict(R['Operand<:opstate'])
        self.rf = [(a, b) for a, b in R.get('Operand<:rf', [])]
        self.ddi = [(a, b) for a, b in R.get('Operand<:ddi', [])]
        self.states = sorted(set(self.opstate.values()))
        self.mem_states = {s for s in self.states if s.startswith('Mem_s')}
        self.ops = list(self.owner)
        self.uncommitted = [i for i in self.order if i not in self.committed]
        lc = [i for i in self.order if i in self.committed]
        self.fu = self.uncommitted[0] if self.uncommitted else None   # first_uncommitted (committed prefix)

    def K(self, i, *ks): return self.kind[i] in ks
    def get(self, i, sl): return self.opsof[i].get(sl, [])
    def before(self, a, b): return self.pos[a] < self.pos[b]

    # ---------------- perturbed views --------------------------------------------------------------
    def view(self, RR=(), RC=(), RS=()):
        RR, RC, RS = set(RR), set(RC), set(RS)
        V = {}
        V['o'] = {o for o in self.ops if self.opstate[o] not in RS}
        V['committed'] = self.committed | RC
        unres_br = [i for i in self.order if i not in self.resolved and i not in RR and self.K(i, 'Branchn', 'Branchx')]
        after = set()
        for b in unres_br:
            after |= {j for j in self.order if self.before(b, j)}
        V['spec'] = {i for i in self.order if i not in V['committed'] and i in after}
        V['nub_bf_or_is'] = {i for i in self.order if i not in after and i not in unres_br}
        leak = set()
        for i in self.order:
            if self.K(i, 'Load'): leak |= set(self.get(i, 'inaddr'))
            if self.K(i, 'Branchx'): leak |= set(self.get(i, 'inreg'))
        V['spec_xmit'] = {o for o in leak if o in V['o'] and self.owner[o] in V['spec']}
        E = collections.defaultdict(set)
        for a, b in self.rf + self.ddi:
            if a in V['o'] and b in V['o']:
                E[a].add(b)
        V['E'] = E
        V['rf_o'] = [(a, b) for a, b in self.rf if a in V['o'] and b in V['o']]
        return V

    def closure(self, V, seeds):
        seen, st = set(), list(seeds)
        while st:
            x = st.pop()
            for y in V['E'].get(x, ()):
                if y not in seen:
                    seen.add(y); st.append(y)
        return seen   # ^edges (transitive, not reflexive)

    # ---------------- defenses: return the flagged speculative transmitter operands -----------------
    def flags(self, sem, V):
        if sem in ('stt_old', 'recon_old'):
            prot = set(self.mem_states)
            if sem == 'recon_old':
                # Recon_6.als:316-318: Mem_s - states of operands that reach (^op_edges) the inaddr of a non-spec load
                tgt = {o for i in self.order if self.K(i, 'Load') and i not in V['spec'] for o in self.get(i, 'inaddr')}
                bad = {self.opstate[o] for o in self.ops if self.closure(V, [o]) & tgt}
                prot -= bad
            for i in self.order:                                       # the 6-step fold, STT_6.als:331
                if self.K(i, 'Load') and i in V['nub_bf_or_is']:
                    prot -= {self.opstate[o] for o in self.get(i, 'inmem')}
            seeds = {o for o in self.ops if self.opstate[o] in prot}
        else:
            seeds = {o for i in V['spec'] if self.K(i, 'Load') for o in self.get(i, 'inmem') if o in V['o']}
            if sem == 'recon_v2':
                seeds -= self.revealed(V)
        return (seeds & V['spec_xmit']) | (self.closure(V, seeds) & V['spec_xmit'])

    def revealed(self, V):
        out = set()
        loads = [i for i in self.order if self.K(i, 'Load')]
        for l3 in loads:
            for m in self.get(l3, 'inmem'):
                if m not in V['o']:
                    continue
                A = self.opstate[m]
                for ld1 in loads:
                    if not self.before(ld1, l3):
                        continue
                    if not any(self.opstate[x] == A and x in V['o'] for x in self.get(ld1, 'inmem')):
                        continue
                    pair = any(a in self.get(ld1, 'outreg') and self.owner[b] in V['committed'] and self.K(self.owner[b], 'Load')
                               and self.slot[b] == 'inaddr' for a, b in V['rf_o'])
                    if not pair:
                        continue
                    conceal = any(self.K(s, 'Store') and self.before(ld1, s) and self.before(s, l3)
                                  and any(self.opstate[x] == A and x in V['o'] for x in self.get(s, 'outmem'))
                                  for s in self.order)
                    if not conceal:
                        out.add(m)
        return out

    def secure(self, sem, **pert): return not self.flags(sem, self.view(**pert))

    def useful(self, sem):
        """gen_useful_litmus AND tag_xm; returns (bool, reason-if-false)"""
        V0 = self.view()
        f0 = self.flags(sem, V0)
        if not f0: return False, 'secure at no_p'
        if not any(self.owner[o] in self.xm for o in f0): return False, 'xm not flagged (tag_xm)'
        for i in self.order:
            if i not in self.resolved and i != self.fu and not self.secure(sem, RR=[i]):
                return False, f'RR->{self.pos[i]} not necessary'
        if self.fu is not None and not self.secure(sem, RR=[self.fu], RC=[self.fu]):
            return False, f'boundary RC+RR->{self.pos[self.fu]} not necessary'
        for s in self.states:
            if not self.secure(sem, RS=[s]):
                return False, f'RS->{s} not necessary'
        return True, ''

    def rf_stale(self):
        n = 0
        for a, b in self.rf:
            pa, pb, st = self.owner[a], self.owner[b], self.opstate[a]
            for o in self.ops:
                if o != a and self.slot[o] in ('outreg', 'outmem') and self.opstate[o] == st \
                        and self.before(pa, self.owner[o]) and self.before(self.owner[o], pb):
                    n += 1; break
        return n

    def r1_witness(self, **pert):
        """(l1, l3) with l1 non-speculative, l3 speculative, same Mem_s, l3's read reaching a flagged xmit under pert."""
        V = self.view(**pert)
        out = []
        for l3 in V['spec']:
            if not self.K(l3, 'Load'): continue
            for m in self.get(l3, 'inmem'):
                if m not in V['o'] or not (self.closure(V, [m]) & V['spec_xmit']): continue
                for l1 in self.order:
                    if self.K(l1, 'Load') and l1 in V['nub_bf_or_is'] and any(self.opstate[x] == self.opstate[m] for x in self.get(l1, 'inmem')):
                        out.append((self.pos[l1], self.pos[l3], self.opstate[m]))
        return out

    def program(self):
        s = []
        for i in self.order:
            k = self.kind[i]; parts = []
            for sl in ('inreg', 'inaddr', 'inmem', 'outreg', 'outmem'):
                for o in self.get(i, sl):
                    parts.append(f'{sl}={self.opstate[o].replace("$", "")}')
            fl = ('C' if i in self.committed else '') + ('R' if i in self.resolved else 'U') + ('*' if i in self.xm else '')
            s.append(f'{self.pos[i]}:{k}[{fl}]({",".join(parts)})')
        rf = [f'{self.pos[self.owner[a]]}.{self.slot[a]}->{self.pos[self.owner[b]]}.{self.slot[b]}' for a, b in self.rf]
        return ' ; '.join(s) + '  rf{' + ' '.join(rf) + '}'

SEMS = ('stt_old', 'recon_old', 'stt_v2', 'recon_v2')

def main():
    d = sys.argv[1]
    mx = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 10**9
    files = sorted(glob.glob(os.path.join(d, 'inst-*.txt')))[:mx]
    rows = []
    for f in files:
        I = Inst(f)
        r = {'inst': os.path.basename(f), 'rf_stale': I.rf_stale(), 'prog': I.program()}
        for s in SEMS:
            u, why = I.useful(s)
            r[s] = u; r[s + '_why'] = why
        rows.append(r)
    c = collections.Counter(tuple(r[s] for s in SEMS) + (r['rf_stale'] > 0,) for r in rows)
    print(f'{len(rows)} instances from {d}')
    print('(' + ', '.join(SEMS) + ', rf_stale) -> count')
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print(' ', k, v)
    if '--json' in sys.argv:
        json.dump(rows, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)

if __name__ == '__main__':
    main()
