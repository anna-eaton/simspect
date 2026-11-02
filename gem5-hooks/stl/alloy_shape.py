import re, sys, glob, collections
def parse(path):
    t = open(path).read()
    def rel(name):
        m = re.search(r"this/Instruction<:%s=\{([^}]*)\}" % name, t)
        return [tuple(x.strip().split("->")) for x in m.group(1).split(",") if x.strip()] if m else []
    kind = dict(rel("kind")); idx = dict(rel("idx"))
    res = {a for a, _ in rel("isresolved")}; com = {a for a, _ in rel("iscommitted")}; xm = {a for a, _ in rel("isxm")}
    order = sorted(kind, key=lambda i: int(idx[i][2:].split("$")[0]))
    K = {"TLoad$0": "ld", "TStore$0": "str", "TBranchn$0": "brn", "TBranchx$0": "brx", "TOthern$0": "othn", "TOtherx$0": "othx"}
    return [(K[kind[i]], i in res, i in com, i in xm) for i in order]
srcs = collections.Counter(); combo = collections.Counter(); shapes = collections.Counter(); ncom = collections.Counter()
for f in sorted(glob.glob(sys.argv[1] + "/inst-*.txt")):
    p = parse(f)
    un = [k for k, r, c, x in p if not r]
    for k in set(un): srcs[k] += 1
    combo[tuple(sorted(set(un)))] += 1
    ncom[sum(1 for _, _, c, _ in p if c)] += 1
    shapes[" ".join(k + ("!U" if not r else "") + ("*X" if x else "") + ("(C)" if c else "") for k, r, c, x in p)] += 1
n = sum(combo.values())
print(n, "instances")
print("instances with >=1 unresolved of kind:", dict(srcs))
print("unresolved-kind sets:", combo.most_common())
print("committed count:", dict(ncom))
print("top shapes:"); [print(" ", c, s) for s, c in shapes.most_common(12)]
