# Stream `objdump -d -C --no-show-raw-insn` from stdin; emit "hash ninsn name" per function
# whose demangled name matches the regex argv[1]. Addresses/immediates normalized.
import sys, re, hashlib
pat = re.compile(sys.argv[1])
hdr = re.compile(r'^[0-9a-f]+ <(.*)>:$')
cur = None; buf = []
def flush():
    if cur is not None and pat.search(cur):
        h = hashlib.sha1('\n'.join(buf).encode()).hexdigest()[:12]
        print(h, len(buf), cur)
for line in sys.stdin:
    line = line.rstrip('\n')
    m = hdr.match(line)
    if m:
        flush(); cur = m.group(1); buf = []; continue
    if cur is None: continue
    m = re.match(r'\s*[0-9a-f]+:\s+(.*)', line)
    if not m: continue
    s = m.group(1).split("#")[0]
    s = re.sub(r'<([^>+]*)(\+0x[0-9a-f]+)?>', r'<\1>', s)
    s = re.sub(r'0x[0-9a-f]+', 'X', s)
    s = re.sub(r'\b[0-9a-f]{4,}\b', 'A', s)
    buf.append(s.strip())
flush()
