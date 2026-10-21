import xml.etree.ElementTree as ET, json, sys
from pathlib import Path

base     = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("alloy-out/STT_4")
hits_f   = base / "window-hits.txt"
xml_dir  = base / "xml"
asm_dir  = base / "asm"
out_file = base / "hits_overview.txt"

hits = hits_f.read_text().strip().splitlines()

def get_field(root, label):
    for f in root.findall('field'):
        if f.get('label') == label:
            return [(t[0].get('label'), t[1].get('label') if len(t) > 1 else None)
                    for t in f.findall('tuple')]
    return []

idx_order = {'IX0$0': 0, 'IX1$0': 1, 'IX2$0': 2, 'IX3$0': 3}

lines = []
for name in hits:
    xml_path = xml_dir / f"{name}.xml"
    ann_path = asm_dir / f"{name}.ann.json"
    if not xml_path.exists():
        continue

    tree = ET.parse(xml_path)
    root = tree.find('instance')

    kind        = dict(get_field(root, 'kind'))
    idx         = dict(get_field(root, 'idx'))
    inreg_map   = {}
    for i, r in get_field(root, 'inreg'):
        inreg_map.setdefault(i, []).append(r)
    inaddr_map  = {}
    for i, r in get_field(root, 'inaddr'):
        inaddr_map.setdefault(i, []).append(r)
    outreg      = dict(get_field(root, 'outreg'))
    outmem      = dict(get_field(root, 'outmem'))
    inmem       = dict(get_field(root, 'inmem'))
    isresolved  = {k for k, _ in get_field(root, 'isresolved')}
    iscommitted = {k for k, _ in get_field(root, 'iscommitted')}
    isxm        = {k for k, _ in get_field(root, 'isxm')}
    rf          = get_field(root, 'rf')
    ddi         = get_field(root, 'ddi')
    opstate     = dict(get_field(root, 'opstate'))

    instrs = sorted(kind.keys(), key=lambda i: idx_order.get(idx.get(i, ''), 99))

    lines.append('=' * 60)
    lines.append(f'  {name}')
    lines.append('=' * 60)
    lines.append('Instructions (program order):')
    for i in instrs:
        flags = []
        if i in iscommitted: flags.append('committed')
        if i in isresolved:  flags.append('resolved')
        if i in isxm:        flags.append('XMIT')
        ir   = [f"{r}({opstate.get(r, '-')})" for r in inreg_map.get(i, [])]
        ia   = [f"{r}({opstate.get(r, '-')})" for r in inaddr_map.get(i, [])]
        or_  = outreg.get(i)
        om   = outmem.get(i)
        im   = inmem.get(i)
        lines.append(f"  {idx[i].replace('$0','')} | {i} | {kind[i].replace('$0','')}")
        lines.append(f"    flags  : {', '.join(flags) or 'none'}")
        lines.append(f"    inreg  : {ir or '-'}")
        lines.append(f"    inaddr : {ia or '-'}")
        lines.append(f"    inmem  : {f'{im}({opstate.get(im, chr(45))})' if im else '-'}")
        lines.append(f"    outreg : {f'{or_}({opstate.get(or_, chr(45))})' if or_ else '-'}")
        lines.append(f"    outmem : {f'{om}({opstate.get(om, chr(45))})' if om else '-'}")

    if rf:
        lines.append('Register forwarding (rf):')
        for src, dst in rf:
            lines.append(f'  {src} -> {dst}')
    if ddi:
        lines.append('Addr dep (ddi):')
        for mem, reg in ddi:
            lines.append(f'  {mem} addr depends on {reg}')

    if ann_path.exists():
        ann  = json.loads(ann_path.read_text())
        cb   = ann.get('commit_boundary', {})
        xmit = ann.get('xmit', {})
        lc   = cb.get('last_committed')
        fnc  = cb.get('first_noncommitted')
        lines.append('Window:')
        lines.append(f"  xmit           : pc={xmit.get('pc')} kind={xmit.get('kind')} x86={xmit.get('x86_offset_hex')}")
        lc_str  = f"pc={lc['pc']} x86={lc.get('x86_offset_hex')}"  if lc  else 'none'
        fnc_str = f"pc={fnc['pc']} x86={fnc.get('x86_offset_hex')}" if fnc else 'none'
        lines.append(f"  last_committed : {lc_str}")
        lines.append(f"  first_noncomm  : {fnc_str}")
    lines.append('')

lines.append(f'Total hits: {len(hits)}')
out_file.write_text('\n'.join(lines) + '\n')
print(f"Written {len(hits)} hits to {out_file}  ({len(lines)} lines)")
