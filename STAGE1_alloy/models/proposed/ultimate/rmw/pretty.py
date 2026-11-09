import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze import parse, model, SLOTS
def show(path):
    m = model(parse(Path(path)))
    pc = {i: n for n, i in enumerate(m["order"])}
    sn = lambda o: m["st"][o].replace("Reg_s$", "R").replace("Mem_s$", "M")
    lines = []
    for i in m["order"]:
        fl = ("C" if i in m["com"] else ("R" if i in m["res"] else "u")) + (" XM" if i in m["xm"] else "")
        ops = []
        for s in SLOTS:
            for o in m["ops"][s].get(i, []):
                src = [a for (a, b) in m["rf"] if b == o]
                ops.append(f"{s}={sn(o)}" + (f"<-pc{pc[m['owner'][src[0]][0]]}.{m['owner'][src[0]][1]}" if src else ""))
        lines.append(f"pc{pc[i]} {m['kind'][i]:5s} [{fl}] " + " ".join(ops))
    return "; ".join(lines)
for p in sys.argv[1:]:
    print(Path(p).parent.name, Path(p).name, "::", show(p))
