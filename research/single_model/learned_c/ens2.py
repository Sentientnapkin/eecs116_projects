"""Direct accuracy of single nets vs ensembles on fold-3 val (head K): python ens2.py run1 run2 ...  (ensemble = mean of means, var = mean(var_i)+var(mu_i))"""
import sys, json
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'learned'))
import train as T, train2
dev = 'cuda'
va = train2.Data2(['val'], dev, ('fast', 'speed'), (0,)); vas = va.valid_starts(2, 1)
P = []
for r in sys.argv[1:]:
    net = T.Net(64, float(json.load(open(HERE / 'runs' / r / 'result.json'))['args'].get('width', 1.0)), 2, 19).to(dev)
    net.load_state_dict(torch.load(HERE / 'runs' / r / 'best.pt')); mu, lv, y = T.predict(net, va, vas, 2, 1, 64); P.append((mu[:, 1], lv[:, 1].exp()))
def rep(tag, mu, var, y):
    sp = y[:, 1].norm(dim=-1); e = (mu - y[:, 1]).norm(dim=-1); z = (mu - y[:, 1]) / var.sqrt()
    ab = va.abin[vas]; sb = va.sbin[vas]
    a = ' '.join('%.3f' % e[ab == i].mean() for i in range(5)); s = ' '.join('%.3f(%.2f)' % (e[sb == i].mean(), (z[sb == i].abs() < 1).float().mean()) for i in range(4))
    print(f'{tag:14s} all {e.mean():.4f} cov1 {(z.abs()<1).float().mean():.2f} nll {(0.5*(z**2+var.log())).sum(-1).mean():.3f} ang {a} | spd {s} | opt scale {float(z.pow(2).mean().sqrt()):.2f}')
y = tgt = None
_, _, y = T.predict(net, va, vas, 2, 1, 64)
for r, (m, v) in zip(sys.argv[1:], P): rep(r, m, v, y)
M = torch.stack([p[0] for p in P]); V = torch.stack([p[1] for p in P])
rep('ensemble', M.mean(0), V.mean(0) + M.var(0, unbiased=False), y)
rep('ens var-avg', M.mean(0), V.mean(0), y)
