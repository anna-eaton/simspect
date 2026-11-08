"""Scratch harness: run parsexml passes (unmodified) with a given instruction table over XMLs,
mirroring batch_generate.run_pipeline, write .ll to an out dir, compile with clang for x86-64 Linux.
Reports: per table, success/fail counts, unknown-concrete warnings, candidate counts per kind,
theoretical vocab combos per instance, distinct combos actually drawn over N seeds."""
import sys, os, glob, json, random, zlib, subprocess, collections, math, traceback
R = '/Users/annaeaton/Documents/stanford/trippel/simspect/'
sys.path.insert(0, R + 'STAGE2_compilation')
sys.dont_write_bytecode = True
import parsexml as P

def run(table, xmls, modes, out_dir, n_seeds, compile_some=True):
    P.reload_tables(table)
    os.makedirs(out_dir, exist_ok=True)
    stats = collections.Counter()
    cand_hist = collections.defaultdict(collections.Counter)   # kind -> |valid| histogram
    chosen_hist = collections.defaultdict(collections.Counter) # kind -> chosen name
    combos_theory = []
    combos_seen = []
    errors = []
    for xp in xmls:
        stem = os.path.basename(xp)[:-4]
        txt = open(xp).read()
        inst = P.parse_alloy_xml(txt)
        r1 = P.pass1_specify_state_a(inst, write_out=False)
        for mode in modes:
            seen = set()
            theory = None
            for v in range(n_seeds):
                vseed = zlib.crc32(f"{stem}_v{v}".encode())
                random.seed(vseed)
                try:
                    r2 = P.pass2_specify_instructions(r1, write_out=False)
                    r25 = P.pass2_5_specify_branches(r2, branch_mode=mode, write_out=False)
                    if mode == 'stl_bypass':
                        r25 = P.pass2_6_specify_stl(r25)
                    r_il = P.pass_interleave(r25, None, random.Random(vseed ^ 0xABCD1234))
                    r3 = P.pass3_assign_operands(r_il, write_out=False)
                    r4 = P.pass4_ssa(r3, write_out=False)
                    vstem = f"{stem}_{mode[:6]}_v{v}"
                    ir = P.pass5_emit_llvm(r4, func_name=vstem.replace('-', '_'), write_out=False)
                except ValueError as e:
                    stats['skip_valueerror'] += 1
                    errors.append((stem, mode, v, 'ValueError: ' + str(e)[:160]))
                    break
                except Exception as e:
                    stats['pass_error'] += 1
                    errors.append((stem, mode, v, traceback.format_exc(limit=2)[-300:]))
                    break
                # vocab bookkeeping (after pass2_5 so branch overrides are reflected)
                combo = []
                th = 1
                for rec in r25['instructions']:
                    if rec.get('synthetic'):
                        continue
                    k = rec['kind']
                    nvalid = len(rec.get('candidates') or [])
                    if k in ('br_n', 'br_x'):
                        nvalid_eff = 1   # pass2_5 forces br_bez / br_cond
                    else:
                        nvalid_eff = nvalid
                    if v == 0:
                        cand_hist[k][nvalid_eff] += 1
                    th *= max(nvalid_eff, 1)
                    combo.append(rec.get('concrete_instruction'))
                    if v == 0:
                        pass
                    chosen_hist[k][rec.get('concrete_instruction')] += 1
                theory = th
                seen.add(tuple(combo))
                if 'unknown concrete_instruction' in ir:
                    stats['unknown_concrete'] += 1
                if 'WARNING' in ir:
                    stats['ir_warning'] += 1
                llp = os.path.join(out_dir, vstem + '.ll')
                open(llp, 'w').write(ir + '\n')
                stats['ll_written'] += 1
                if compile_some and (stats['ll_written'] % int(os.environ.get('COMPILE_EVERY','1')) == 0):
                    sp = llp[:-3] + '.s'
                    rr = subprocess.run(['clang', '--target=x86_64-unknown-linux-gnu', '-O2', '-S', llp, '-o', sp],
                                        capture_output=True, text=True)
                    if rr.returncode != 0:
                        stats['clang_fail'] += 1
                        errors.append((stem, mode, v, 'clang: ' + rr.stderr[:300]))
                    else:
                        stats['clang_ok'] += 1
                        s = open(sp).read()
                        # each Alloy pc marker must survive
                        npc = sum(1 for rec in r4['instructions'])
                        nmk = s.count('__litmus_' + vstem.replace('-', '_').replace('.', '_') + '_pc') // 2
                        if nmk < npc:
                            stats['marker_missing'] += 1
            if theory is not None:
                combos_theory.append(theory)
                combos_seen.append(len(seen))
    return stats, cand_hist, chosen_hist, combos_theory, combos_seen, errors

if __name__ == '__main__':
    table, out_dir, n_seeds = sys.argv[1], sys.argv[2], int(sys.argv[3])
    modes = sys.argv[4].split(',')
    xmls = sys.argv[5:]
    st, ch, cho, th, seen, errs = run(table, xmls, modes, out_dir, n_seeds)
    def summ(xs):
        if not xs: return {}
        xs2 = sorted(xs)
        return {'n': len(xs), 'min': xs2[0], 'median': xs2[len(xs2)//2], 'max': xs2[-1],
                'mean': round(sum(xs)/len(xs), 2), 'geomean': round(math.exp(sum(math.log(x) for x in xs)/len(xs)), 2)}
    print(json.dumps({'table': os.path.basename(table), 'stats': st,
                      'valid_candidates_hist_per_kind': {k: dict(v) for k, v in ch.items()},
                      'chosen_hist_per_kind': {k: dict(v) for k, v in cho.items()},
                      'combos_theoretical_per_instance_mode': summ(th),
                      'combos_seen_over_seeds': summ(seen),
                      'errors_first5': errs[:5], 'n_errors': len(errs)}, indent=1, default=str))
