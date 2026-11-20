import json, glob, sys, numpy as np, re
from collections import defaultdict
pre = sys.argv[1] if len(sys.argv) > 1 else 'g_'
G = defaultdict(list)
for f in sorted(glob.glob(f'runs/{pre}*/result.json')):
    r = json.load(open(f)); n = f.split('/')[1]; key = re.sub(r'_s\d+$', '', n)
    G[key].append(r)
print('| config | seeds | params | MACs/inference | val vel err m/s (head0 / headK) | ang med deg | NLL0 | cov1 | cov2 |')
print('|---|---|---|---|---|---|---|---|---|')
for k, rs in G.items():
    v = lambda f: np.array([f(r) for r in rs])
    e0 = v(lambda r: r['val']['err'][0]); eK = v(lambda r: r['val']['err'][1])
    print(f"| {k} | {len(rs)} | {rs[0]['params']} | {rs[0]['macs']/1e6:.3f} M | {e0.mean():.3f}+-{e0.std():.3f} / {eK.mean():.3f} | {v(lambda r:r['val']['ang_med'][0]).mean():.1f} | {v(lambda r:r['val']['nll'][0]).mean():.2f} | {v(lambda r:r['val']['cov1'][0]).mean():.2f} | {v(lambda r:r['val']['cov2'][0]).mean():.2f} |")
