"""learned_c training on the C-matched cache (prep2.py): mix of raw-fast + raw-speed flights, two start phases per flight, bin-balanced sampling.
Strict split: train = folds {0,1,2} and not among the 171 selected; val = fold 3; fold 4 never read (Data2 asserts it).
  CUDA_VISIBLE_DEVICES=1 python -B train2.py --name x --alpha 0.5 --pools fast,speed
Selection of the best epoch by fold-3 validation only (bin-balanced head0+headK error over moving anchors)."""
import argparse, json, math, sys, time
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'learned'))
import train as T, split2
CACHE = Path('/data/backups/rganapa/Sebastian/tmp/lc_cache')
OUT = HERE / 'runs'
ABINS = [0, 30, 60, 90, 135, 180.01]
SBINS = [0, 0.3, 1.0, 1.5, 99]

class Data2:
    def __init__(self, roles, dev, pools=('fast', 'speed'), phases=(0, 2)):
        rows = [r for r in split2.load_rows() if r['role'] in roles and r['pool'] in pools]
        self.rows = rows
        fr, Rc, Vi, fm, gm, vb, K, fx, fid, pos, ln = ([] for _ in range(11)); self.Tbc = None; vid = 0
        for i, r in enumerate(rows):
            assert r['role'] != 'sealed' and r['fold'] != 4
            d = np.load(CACHE / f"{r['name']}.npz")
            if self.Tbc is None: self.Tbc = d['Tbc']
            for p in phases:
                A = len(d[f'frames{p}'])
                fr.append(d[f'frames{p}']); Rc.append(d[f'Rcum{p}']); Vi.append(d[f'Vint{p}']); fm.append(d[f'fmean{p}']); gm.append(d[f'gmean{p}'])
                vb.append(d[f'vb{p}']); K.append(np.tile(d['K'], (A, 1))); fx.append(np.full(A, float(d['fx320'])))
                fid.append(np.full(A, i)); pos.append(np.arange(A)); ln.append(np.full(A, A)); vid += 1
        c = lambda x: torch.from_numpy(np.concatenate(x)).to(dev).float()
        self.frames = torch.from_numpy(np.concatenate(fr)).to(dev)
        self.R, self.V, self.f, self.g, self.vb, self.K, self.fx = c(Rc), c(Vi), c(fm), c(gm), c(vb), c(K), c(fx)
        self.fid = torch.from_numpy(np.concatenate(fid)).to(dev); self.pos = torch.from_numpy(np.concatenate(pos)).to(dev); self.len = torch.from_numpy(np.concatenate(ln)).to(dev)
        self.N = len(self.pos); self.Rbc = torch.tensor(self.Tbc[:3, :3], dtype=torch.float32, device=dev)
        axis = self.Rbc[:, 2]
        sp = self.vb.norm(dim=1)
        ang = torch.rad2deg(torch.acos(((self.vb @ axis) / (sp + 1e-9)).clamp(-1, 1)))
        self.speed, self.angle = sp, ang
        self.sbin = torch.bucketize(sp, torch.tensor(SBINS[1:-1], device=dev))
        self.abin = torch.where(sp > 0.3, torch.bucketize(ang, torch.tensor(ABINS[1:-1], device=dev)), torch.full_like(sp, -1, dtype=torch.long))

    valid_starts = T.Data.valid_starts

def bin_weights(D, alpha, starts):
    key = (D.sbin[starts] * 6 + (D.abin[starts] + 1)).cpu().numpy()
    cnt = np.bincount(key, minlength=40).astype(float)
    w = cnt[key] ** (-alpha)
    return torch.from_numpy(w / w.sum()).float().to(D.vb.device)

def val_report(mu, lv, y, D, starts):
    """metrics per angle bin and speed bin (head0 and headK), calibration coverage and optimal sigma scale."""
    sb, ab = D.sbin[starts], D.abin[starts]
    out = {}
    def blk(m):
        if m.sum() == 0: return None
        e = (mu[m] - y[m]).norm(dim=-1).mean(0); z = (mu[m] - y[m]) / torch.exp(0.5 * lv[m])
        sp = y[m].norm(dim=-1)
        ang = torch.rad2deg(torch.acos(((mu[m] * y[m]).sum(-1) / (mu[m].norm(dim=-1) * sp + 1e-9)).clamp(-1, 1)))
        return dict(n=int(m.sum()), err0=float(e[0]), errK=float(e[1]), ang_med=float(ang[:, 1][sp[:, 1] > 0.3].median()) if (sp[:, 1] > 0.3).any() else None,
                    cov1=float((z.abs() < 1).float().mean()), cov2=float((z.abs() < 2).float().mean()), sig=float(torch.exp(0.5 * lv[m]).mean()))
    out['all'] = blk(torch.ones_like(sb, dtype=torch.bool))
    for i in range(5): out[f'ang{ABINS[i]}-{int(ABINS[i+1])}'] = blk(ab == i)
    for i in range(4): out[f'spd{SBINS[i]}-{SBINS[i+1]}'] = blk(sb == i)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--res', type=int, default=64); ap.add_argument('--width', type=float, default=1.0)
    ap.add_argument('--seed', type=int, default=0); ap.add_argument('--epochs', type=int, default=30); ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--lr', type=float, default=2e-3); ap.add_argument('--steps_per_epoch', type=int, default=400)
    ap.add_argument('--alpha', type=float, default=0.0, help='bin-balancing exponent (0 = uniform anchors)')
    ap.add_argument('--pools', default='fast,speed'); ap.add_argument('--phases', default='0,2')
    a = ap.parse_args()
    dev = 'cuda'; torch.manual_seed(a.seed); np.random.seed(a.seed)
    out = OUT / a.name; out.mkdir(parents=True, exist_ok=True)
    pools = tuple(a.pools.split(',')); phases = tuple(int(x) for x in a.phases.split(','))
    tr = Data2(['train'], dev, pools, phases); va = Data2(['val'], dev, ('fast', 'speed'), (0,))
    nf, gap = 2, 1
    trs, vas = tr.valid_starts(nf, gap), va.valid_starts(nf, gap)
    w = bin_weights(tr, a.alpha, trs)
    print(a.name, 'train flights', len(tr.rows), 'anchors', len(trs), 'val flights', len(va.rows), 'anchors', len(vas), flush=True)
    net = T.Net(a.res, a.width, nf, 19).to(dev)
    params, macs = T.count(net, nf, 19, a.res); print('params', params, 'MACs', macs, flush=True)
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
            loss = ((0.5 * (mu - tgt) ** 2).mean() if ep < 1 else T.nll(mu, lv, tgt).mean()) * 3
            opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step()
            tl += loss.item()
        mu, lv, y = T.predict(net, va, vas, nf, gap, a.res)
        rep = val_report(mu, lv, y, va, vas)
        crit = float(np.mean([(rep[k]['err0'] + rep[k]['errK']) / 2 for k in rep if k.startswith('ang') and rep[k]]))
        log.append(dict(epoch=ep, train=tl / a.steps_per_epoch, val_all0=rep['all']['err0'], val_balanced=crit))
        print(f"ep {ep} train {tl/a.steps_per_epoch:.3f} val all {rep['all']['err0']:.3f}/{rep['all']['errK']:.3f} balanced {crit:.3f} cov1 {rep['all']['cov1']:.2f} ({time.time()-t0:.0f}s)", flush=True)
        if ep >= 3 and crit < best[0]:
            best = (crit, ep); torch.save(net.state_dict(), out / 'best.pt')
    net.load_state_dict(torch.load(out / 'best.pt'))
    mu, lv, y = T.predict(net, va, vas, nf, gap, a.res)
    rep = val_report(mu, lv, y, va, vas)
    # optimal global sigma scale for headK (NLL minimiser: scale^2 = mean(z^2) with z = err/sigma)
    zK = ((mu[:, 1] - y[:, 1]) / torch.exp(0.5 * lv[:, 1])); sig_scale = float(zK.pow(2).mean().sqrt())
    # per-fast-subset (speed pool vs fast pool)
    isspeed = torch.tensor([va.rows[i]['pool'] == 'speed' for i in va.fid[vas].tolist()], device=dev)
    sub = {'speedpool': val_report(mu[isspeed], lv[isspeed], y[isspeed], va, vas[isspeed])['all'], 'fastpool': val_report(mu[~isspeed], lv[~isspeed], y[~isspeed], va, vas[~isspeed])['all']}
    res = dict(args=vars(a), params=params, macs=macs, best_epoch=best[1], val=rep, val_by_pool=sub, sigma_scale_headK=sig_scale, log=log,
               n_train_flights=len(tr.rows), train_flights=[r['name'] for r in tr.rows])
    json.dump(res, open(out / 'result.json', 'w'), indent=1)
    print('DONE', a.name, 'best_ep', best[1], 'sigscale', round(sig_scale, 3), json.dumps(rep['all']), flush=True)

if __name__ == '__main__':
    main()
