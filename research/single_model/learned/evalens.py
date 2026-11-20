import sys, numpy as np
sys.path.insert(0, '.')
import evalnets as E
names = sys.argv[1:]
ps = [E.run(n) for n in names]
p = E.ensemble(ps)
print('ensemble of', len(ps), names[0].rsplit('_s', 1)[0])
for head in (0, 1):
    print('head', head); print(E.fmt(E.table(p, head)))
