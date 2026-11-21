"""one.py case ep wasm1 [wasm2 ...] : run stress case on one flight for several wasms (parallel)"""
import sys, json
from multiprocessing import Pool
sys.argv[0] = 'x'; import stress
case, ep, ws = sys.argv[1], sys.argv[2], sys.argv[3:]
eps = ep.split(',')
with Pool(min(8, len(ws) * len(eps))) as p:
    R = p.map(stress.run, [(w, case, e, 1000) for w in ws for e in eps])
for w, r in zip([w for w in ws for e in eps], R):
    print('%-50s %-30s ATE %s peak %s %s' % (w.split('/')[-2], r.get('ep'), round(r.get('ate', -1), 3), round(r.get('peak', 0) / 1e6, 2), r.get('failure') or r.get('error', '')[-200:]))
