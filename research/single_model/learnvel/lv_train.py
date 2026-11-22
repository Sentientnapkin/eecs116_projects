"""learnvel training: learned_c recipe (train2/train3) generalised: nf frames (stride gap anchors = 5*gap video frames), width, extra pools.
Train rows: learned_c split2 rows role 'train' (folds 0-2) + learnvel/gen/lv_rows.json, EXCLUDING st2 scenes (dev+conf), holdout scenes, fold 3/4.
Val (selection): fold-3 fast+speed (as learned_c) ; report: st2dev eval cache (lv_cache) direct error by speed/texture.
  CUDA_VISIBLE_DEVICES=5 python -B lv_train.py --name x --nf 3 --gap 1"""
import argparse, json, sys, time, glob, hashlib
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'learned_c')); sys.path.insert(0, str(HERE.parent / 'learned')); sys.path.insert(0, str(HERE))
import train as T, split2
from train2 import bin_weights, val_report, SBINS
from lv_eval import EvalData, texture
LCC = Path('/data/backups/rganapa/Sebastian/tmp/lc_cache'); LVC = Path('/data/backups/rganapa/Sebastian/tmp/lv_cache_train'); EVC = Path('/data/backups/rganapa/Sebastian/tmp/lv_cache')
OUT = HERE / 'runs'
ST2 = {f['scene'] for f in json.load(open(HERE.parent / 'servertail/gen/st2.json'))['flights']}

def train_files(pools):
    out = []
    for r in split2.load_rows():
        if r['role'] != 'train' or r['pool'] not in pools or r['scene'] in ST2: continue
        f = LCC / f"{r['name']}.npz"
        if f.exists(): out.append(f)
    if 'lv' in pools and (HERE / 'gen/lv_rows.json').exists():
        for n, r in json.load(open(HERE / 'gen/lv_rows.json')).items():
            assert r['scene'] not in ST2 and r['fold'] in (0, 1, 2)
            f = LVC / f'{n}.npz'
            if f.exists(): out.append(f)
    return out

class Multi(EvalData):
    """EvalData over several phases + the train2 bins"""
    def __init__(self, files, dev, phases):
        parts = [EvalData(files, dev, p) for p in phases]
        for k in ['frames', 'R', 'V', 'f', 'g', 'vb', 'K', 'fx', 'fid', 'len']:
            setattr(self, k, torch.cat([getattr(p, k) for p in parts]))
        # positions must not cross phase/flight boundaries: offset pos by a large gap per phase block -> use per-block pos, valid_starts checks pos+span<len
        self.pos = torch.cat([p.pos for p in parts]); self.Rbc = parts[0].Rbc; self.Tbc = parts[0].Tbc; self.names = parts[0].names
        self.N = len(self.pos); sp = self.vb.norm(dim=1); axis = self.Rbc[:, 2]
        ang = torch.rad2deg(torch.acos(((self.vb @ axis) / (sp + 1e-9)).clamp(-1, 1)))
        self.sbin = torch.bucketize(sp, torch.tensor(SBINS[1:-1], device=dev))
        self.abin = torch.where(sp > 0.3, torch.bucketize(ang, torch.tensor([30, 60, 90, 135.], device=dev)), torch.full_like(sp, -1, dtype=torch.long))

def st2_report(net, E, est, nf, gap, res, tex):
    mu, lv, y = T.predict(net, E, est, nf, gap, res); mu, y, lv = mu[:, 1], y[:, 1], lv[:, 1]
    e = (mu - y).norm(dim=-1); sp = y.norm(dim=-1); z = (mu - y) / torch.exp(0.5 * lv)
    r = dict(all=float(e.mean()), zrms=float(z.pow(2).mean().sqrt()))
    for lo, hi in [(0, .3), (.3, 1), (1, 2), (2, 9)]:
        m = (sp >= lo) & (sp < hi); r[f's{lo}-{hi}'] = float(e[m].mean())
        r[f'scale{lo}-{hi}'] = float(((mu[m] * y[m]).sum(-1) / sp[m] ** 2).mean()) if lo >= 1 else None
    m = tex < 0.07; r['lowtex'] = float(e[m].mean()); r['lowtex_fast'] = float(e[m & (sp > 1)].mean())
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--res', type=int, default=64); ap.add_argument('--width', type=float, default=1.0)
    ap.add_argument('--nf', type=int, default=2); ap.add_argument('--gap', type=int, default=1)
    ap.add_argument('--seed', type=int, default=0); ap.add_argument('--epochs', type=int, default=60); ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--lr', type=float, default=3e-3); ap.add_argument('--steps_per_epoch', type=int, default=400)
    ap.add_argument('--alpha', type=float, default=0.5); ap.add_argument('--pools', default='fast,speed,new,lv'); ap.add_argument('--phases', default='0,2')
    ap.add_argument('--beta', type=float, default=0.0, help='beta-NLL exponent (Seitzer 2022): loss * stopgrad(var)^beta')
    ap.add_argument('--sel', default='st2', help='selection criterion: st2 (st2dev direct err) or f3 (fold-3 balanced)')
    a = ap.parse_args()
    dev = 'cuda'; torch.manual_seed(a.seed); np.random.seed(a.seed)
    out = OUT / a.name; out.mkdir(parents=True, exist_ok=True)
    files = train_files(tuple(a.pools.split(',')))
    tr = Multi(files, dev, tuple(int(x) for x in a.phases.split(',')))
    vrows = [r for r in split2.load_rows() if r['role'] == 'val' and r['pool'] in ('fast', 'speed')]
    va = Multi([LCC / f"{r['name']}.npz" for r in vrows], dev, (0,))
    E = EvalData(sorted(glob.glob(str(EVC / 'st2*.npz'))), dev, 0)
    nf, gap = a.nf, a.gap; trs, vas, est = tr.valid_starts(nf, gap), va.valid_starts(nf, gap), E.valid_starts(nf, gap)
    tex = texture(E.frames)[est + (nf - 1) * gap]
    w = bin_weights(tr, a.alpha, trs); nvec = 13 + 6 * (nf - 1)
    print(a.name, 'train flights', len(files), 'anchors', len(trs), 'val', len(vas), 'st2dev', len(est), flush=True)
    net = T.Net(a.res, a.width, nf, nvec).to(dev); params, macs = T.count(net, nf, nvec, a.res); print('params', params, 'MACs', macs, flush=True)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * a.steps_per_epoch, pct_start=0.1)
    best = (1e9, None); log = []; t0 = time.time()
    for ep in range(a.epochs):
        net.train(); tl = 0
        for _ in range(a.steps_per_epoch):
            g = trs[torch.multinomial(w, a.bs, replacement=True)]
            img, vec, tgt, _ = T.build_batch(tr, g, nf, gap, a.res, True)
            fl = torch.rand(a.bs, device=dev) < 0.5
            if fl.any():
                i2, v2, t2 = T.flip(img[fl], vec[fl], tgt[fl], nf)
                img = img.clone(); vec = vec.clone(); tgt = tgt.clone(); img[fl], vec[fl], tgt[fl] = i2, v2, t2
            mu, lv = net(img, vec)
            loss = ((T.nll(mu, lv, tgt) * (torch.exp(lv.detach()) ** a.beta if a.beta else 1)).sum(-1).mean(-1) if ep >= 1 else (0.5 * (mu - tgt) ** 2).sum(-1).mean(-1)).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step(); tl += loss.item()
        mu, lv, y = T.predict(net, va, vas, nf, gap, a.res); rep = val_report(mu, lv, y, va, vas)
        crit_f3 = float(np.mean([(rep[k]['err0'] + rep[k]['errK']) / 2 for k in rep if k.startswith('ang') and rep[k]]))
        s2 = st2_report(net, E, est, nf, gap, a.res, tex)
        crit = s2['all'] if a.sel == 'st2' else crit_f3
        log.append(dict(epoch=ep, train=tl / a.steps_per_epoch, f3K=rep['all']['errK'], f3bal=crit_f3, st2=s2))
        if ep % 5 == 0 or ep == a.epochs - 1: print(f"ep {ep} train {tl/a.steps_per_epoch:.3f} f3K {rep['all']['errK']:.3f} bal {crit_f3:.3f} st2 {json.dumps({k: round(v, 3) for k, v in s2.items() if v is not None})} ({time.time()-t0:.0f}s)", flush=True)
        if ep >= 3 and crit < best[0]: best = (crit, ep); torch.save(net.state_dict(), out / 'best.pt')
    net.load_state_dict(torch.load(out / 'best.pt'))
    mu, lv, y = T.predict(net, va, vas, nf, gap, a.res); rep = val_report(mu, lv, y, va, vas)
    s2 = st2_report(net, E, est, nf, gap, a.res, tex)
    zK = (mu[:, 1] - y[:, 1]) / torch.exp(0.5 * lv[:, 1])
    res = dict(args=vars(a), params=params, macs=macs, best_epoch=best[1], best_crit=best[0], val=rep, st2=s2, sigma_scale_headK=float(zK.pow(2).mean().sqrt()), log=log, n_train_flights=len(files))
    json.dump(res, open(out / 'result.json', 'w'), indent=1)
    print('DONE', a.name, 'best_ep', best[1], 'f3K %.3f' % rep['all']['errK'], 'st2', json.dumps(s2), flush=True)

if __name__ == '__main__':
    main()
