import subprocess, sys, re
b, name = sys.argv[1], sys.argv[2]
out = subprocess.run(['nm', '-C', '-S', b], capture_output=True, text=True).stdout
for line in out.splitlines():
    p = line.split(' ', 3)
    if len(p) == 4 and p[3] == name:
        a, s = int(p[0], 16), int(p[1], 16)
        d = subprocess.run(['objdump', '-d', '-C', '--no-show-raw-insn', '--start-address=%#x' % a, '--stop-address=%#x' % (a + s), b], capture_output=True, text=True).stdout
        for l in d.splitlines():
            m = re.match(r'\s*[0-9a-f]+:\s+(.*)', l)
            if m:
                x = re.sub(r"<([^>+]*)(\+0x[0-9a-f]+)?>", r"<\1>", m.group(1).split("#")[0])
                x = re.sub(r'0x[0-9a-f]+', 'X', x); x = re.sub(r'\b[0-9a-f]{4,}\b', 'A', x)
                print(x.strip())
        break
