"""active.py SRC.c PREPROCESSED.i OUT.txt : write the original source lines that survive the preprocessor
(from clang -E line markers), prefixed with their original line numbers. A reading aid only."""
import re, sys
src = open(sys.argv[1]).read().split('\n'); name = None; active = set(); ln = 0
for l in open(sys.argv[2], errors='replace'):
    m = re.match(r'^# (\d+) "([^"]*)"', l)
    if m: ln = int(m.group(1)); name = m.group(2); continue
    if name and name.endswith('solution.c'):
        if l.strip(): active.add(ln)
        ln += 1
with open(sys.argv[3], 'w') as f:
    prev = 0
    for i in sorted(active):
        if i - prev > 1: f.write('-----\n')
        f.write('%6d %s\n' % (i, src[i - 1] if i - 1 < len(src) else '')); prev = i
print(len(active), 'active lines')
