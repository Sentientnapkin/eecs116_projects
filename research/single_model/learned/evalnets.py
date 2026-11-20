"""Direct accuracy on validation (fold 3) + baselines + ensembling.  python -B evalnets.py <name-prefix list...>
Writes preds/<name>.npz (val anchors: mu, lv, y, flight, pos, moving detector, speed) so fusion analysis needs no GPU."""
import json, sys, os
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).parent))
import train as T, split

OUT = T.OUT
PREDS = Path(__file__).parent / 'preds'; PREDS.mkdir(exist_ok=True)


def load(name, dev='cuda'):
    r = json.load(open(OUT / name / 'result.json')); a = r['args']
    nvec = 3 * 4 + 6 * (a['nf'] - 1) + 1
    net = T.Net(a['res'], a['width'], a['nf'], nvec, deep=bool(a['deep']), use_img=not a['no_img'], use_vec=not a['no_vec']).to(dev)
    net.load_state_dict(torch.load(OUT / name / 'best.pt')); net.eval()
    T.VEC_MIN = bool(a.get('vec_min', 0))
    return net, a


def run(name, role='val', dev='cuda'):
    net, a = load(name, dev)
    D = T.Data([role], dev)
    s = D.valid_starts(a['nf'], a['gap'])
    mu, lv, y = T.predict(net, D, s, a['nf'], a['gap'], a['res'])
    return dict(mu=mu.cpu().numpy(), lv=lv.cpu().numpy(), y=y.cpu().numpy(), flight=D.fid[s].cpu().numpy(), pos=D.pos[s].cpu().numpy(),
                fmean=D.f[s].cpu().numpy(), gmean=D.g[s].cpu().numpy(), names=[r['name'] for r in D.rows], start=[r['start'] for r in D.rows],
                selected=[r['selected'] for r in D.rows])


def detector(f, g):  # same rule as the heading-prior arm (startup/v3.c)
    return (np.linalg.norm(g, axis=1) > 0.2) | (np.linalg.norm(f, axis=1) > 8.8)


HEAD_MU = np.array([0.65, 0.0, 0.0]); HEAD_SD = np.array([0.75, 0.5, 0.35])  # body axes (x fwd = cam z, y = -cam x, z = -cam y)


def stats(mu, lv, y, label):
    e = mu - y; en = np.linalg.norm(e, axis=1); sp = np.linalg.norm(y, axis=1)
    cos = (mu * y).sum(1) / (np.linalg.norm(mu, axis=1) * sp + 1e-9)
    ang = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    z = e / np.exp(0.5 * lv)
    nl = (0.5 * (e ** 2 * np.exp(-lv) + lv)).sum(1)
    return dict(label=label, n=len(y), err=float(en.mean()), rmse=float(np.sqrt((en ** 2).mean())), med=float(np.median(en)),
                ang_med=float(np.median(ang[sp > 0.3])) if (sp > 0.3).any() else float('nan'),
                mag=float(np.abs(np.linalg.norm(mu, axis=1) - sp).mean()), nll=float(nl.mean()),
                cov1=float((np.abs(z) < 1).mean()), cov2=float((np.abs(z) < 2).mean()))


def table(p, head=0):
    """p: output of run (or ensembled). Returns rows for subsets and baselines."""
    mu, lv, y = p['mu'][:, head], p['lv'][:, head], p['y'][:, head]
    det = detector(p['fmean'], p['gmean']); sp = np.linalg.norm(y, axis=1)
    start0 = p['pos'] == 0
    mid0 = start0 & np.array([p['start'][i] == 'mid' for i in p['flight']])
    sub = {'all anchors': np.ones(len(y), bool), 'detector-moving anchors': det, 'real mid starts (frame 0)': mid0,
           'real static starts (frame 0)': start0 & ~mid0, 'speed>1.5 anchors': sp > 1.5}
    rows = []
    zero = np.zeros_like(y); zlv = np.full_like(lv, np.log(1.0))
    hm = np.tile(HEAD_MU, (len(y), 1)); hlv = np.tile(np.log(HEAD_SD ** 2), (len(y), 1))
    for k, m in sub.items():
        if m.sum() == 0: continue
        rows.append((k, stats(mu[m], lv[m], y[m], 'net'), stats(zero[m], zlv[m], y[m], 'zero'), stats(hm[m], hlv[m], y[m], 'heading prior')))
    return rows


def ensemble(ps):
    mu = np.mean([p['mu'] for p in ps], 0)
    var = np.mean([np.exp(p['lv']) + p['mu'] ** 2 for p in ps], 0) - mu ** 2
    q = dict(ps[0]); q['mu'] = mu; q['lv'] = np.log(var); return q


def fmt(rows):
    out = []
    for k, n, z, h in rows:
        out.append(f"{k:30s} n={n['n']:6d} | net err {n['err']:.3f} med {n['med']:.3f} ang {n['ang_med']:.1f} mag {n['mag']:.3f} nll {n['nll']:.2f} cov1 {n['cov1']:.2f} cov2 {n['cov2']:.2f}"
                   f" | zero err {z['err']:.3f} | heading err {h['err']:.3f} ang {h['ang_med']:.1f}")
    return '\n'.join(out)


if __name__ == '__main__':
    for name in sys.argv[1:]:
        p = run(name)
        np.savez(PREDS / f'{name}.npz', **{k: v for k, v in p.items() if isinstance(v, np.ndarray)})
        print('==', name); print(fmt(table(p)))
