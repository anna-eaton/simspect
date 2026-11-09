import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze import parse, model, canon, relabel_rmw_as_ld, S
from collections import Counter
def load(d):
    return [model(parse(f)) for f in sorted((S/"out"/d).glob("inst-*.txt"))]
for b in (3, 4):
    stt = load(f"C3_stt6core_b{b}"); norm = load(f"C2_core_normws_b{b}"); rmw = load(f"C1_core_pinned_b{b}")
    cs = {canon(m) for m in stt}; cn = {canon(m) for m in norm}
    print(f"b{b}: STT_6 core {len(stt)} (distinct canon {len(cs)}); RMW-model no-RMW cores {len(norm)} (distinct {len(cn)}); sets equal: {cs == cn}")
    imgs = [canon(relabel_rmw_as_ld(m)) for m in rmw]
    inset = sum(1 for c in imgs if c in cs)
    ldx = {c for c in cs if ":ld:" in c and "X" in [p.split(":")[2][-1] for p in c.split("|") if p.count(":")==2 and p.split(":")[1]=="ld"]}
    # STT cores whose xm is a load
    def xmkind(m): return m["kind"][next(iter(m["xm"]))]
    stt_ldx = {canon(m) for m in stt if xmkind(m) == "ld"}
    hit = {c for c in imgs if c in cs}
    print(f"  RMW cores {len(rmw)} -> relabelled ld-xmit image in STT_6 core set: {inset}/{len(rmw)}; distinct images {len(set(imgs))}; STT ld-xmit cores {len(stt_ldx)}, covered by an RMW image {len(hit & stt_ldx)}")
    print("  xm kinds of STT_6 cores:", dict(Counter(xmkind(m) for m in stt)))
    missing = [c for c in imgs if c not in cs][:3]
    for c in missing: print("  NOT IN STT:", c)
    uncovered = sorted(stt_ldx - hit)[:3]
    for c in uncovered: print("  STT ld-xmit core with no RMW image:", c)
