"""gravity-direction net: one gray128 frame (+ IMU window means) -> gravity unit vector in BODY frame + per-axis log-variance.
Train: learned_c fast/speed train rows + lv rows (folds 0-2, no st2 scenes, no holdout); val: fast/speed fold 3; report: st2dev (honest scenes for this net)."""
import argparse, json, sys, time, glob
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'learned_c')); sys.path.insert(0, str(HERE.parent / 'learned')); sys.path.insert(0, str(HERE))
import train as T, split2
GR = Path('/data/backups/rganapa/Sebastian/tmp/lv_grav'); LCC = Path('/data/backups/rganapa/Sebastian/tmp/lc_cache'); LVC = Path('/data/backups/rganapa/Sebastian/tmp/lv_cache_train'); EVC = Path('/data/backups/rganapa/Sebastian/tmp/lv_cache')
ST2 = {f['scene'] for f in json.load(open(HERE.parent / 'servertail/gen/st2.json'))['flights']}

class G:
    def __init__(self, files, dev, phases):
        fr, gb, fm, gm, K, fid = [], [], [], [], [], []; self.names = []
        for i, f in enumerate(files):
            d = np.load(f); g = np.load(GR / f.name)
            for p in phases:
                n = min(len(d[f'frames{p}']), len(g[f'gb{p}']))
                fr.append(d[f'frames{p}'][:n]); gb.append(g[f'gb{p}'][:n]); fm.append(d[f'fmean{p}'][:n]); gm.append(d[f'gmean{p}'][:n]); K.append(np.tile(d['K'], (n, 1))); fid.append(np.full(n, i))
            self.names.append(f.stem)
        c = lambda x: torch.from_numpy(np.concatenate(x)).float().to(dev)
        self.frames = torch.from_numpy(np.concatenate(fr)).to(dev); self.gb, self.f, self.g, self.K = c(gb), c(fm), c(gm), c(K)
        self.fid = torch.from_numpy(np.concatenate(fid)).to(dev); self.N = len(self.gb)

def batch(D, ix, res, train):
    X = D.frames[ix].float()[:, None]; B = len(ix)
    m = X.mean((2, 3), keepdim=True); s = X.std((2, 3), keepdim=True)
    X = (X - m) / (s + 5.0)
    if train: X = X + 0.03 * torch.randn_like(X)
    ca = torch.linspace(-1, 1, 128, device=X.device).view(1, 1, 1, 128).expand(B, 1, 96, 128); cb = torch.linspace(-1, 1, 96, device=X.device).view(1, 1, 96, 1).expand(B, 1, 96, 128)
    img = torch.cat([X, ca, cb], 1)
    if res != 128: img = F.avg_pool2d(img, 128 // res)
    vec = torch.cat([D.f[ix] / 9.81, D.g[ix], (D.K[ix, 0:1] / 100.0)], 1)
    return img, vec, D.gb[ix]

def flip(img, vec, y):
    img = torch.cat([img[:, :1].flip(3), img[:, 1:]], 1)
    sv = torch.tensor([1, -1, 1.], device=y.device); sa = torch.tensor([-1, 1, -1.], device=y.device)
    vec = vec * torch.cat([sv, sa, torch.ones(1, device=y.device)]); return img, vec, y * sv

def angerr(mu, y):
    mu = mu / mu.norm(dim=-1, keepdim=True).clamp(min=1e-6); return torch.rad2deg(torch.acos((mu * y).sum(-1).clamp(-1, 1)))

def predict(net, D, res, bs=4096):
    net.eval(); out = []
    with torch.no_grad():
        for i in range(0, D.N, bs):
            ix = torch.arange(i, min(D.N, i + bs), device=D.gb.device); img, vec, y = batch(D, ix, res, False); mu, lv = net(img, vec); out.append((mu[:, 0], lv[:, 0]))
    return torch.cat([o[0] for o in out]), torch.cat([o[1] for o in out])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--res', type=int, default=64); ap.add_argument('--width', type=float, default=1.0)
    ap.add_argument('--epochs', type=int, default=40); ap.add_argument('--steps', type=int, default=400); ap.add_argument('--bs', type=int, default=256); ap.add_argument('--lr', type=float, default=3e-3); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(); dev = 'cuda'; torch.manual_seed(a.seed)
    out = HERE / 'runs' / a.name; out.mkdir(parents=True, exist_ok=True)
    tr_f, va_f = [], []
    for r in split2.load_rows():
        f = LCC / f"{r['name']}.npz"
        if r['pool'] in ('fast', 'speed') and (GR / f.name).exists() and f.exists() and r['scene'] not in ST2:
            (tr_f if r['role'] == 'train' else va_f if r['role'] == 'val' else []).append(f)
    if (HERE / 'gen/lv_rows.json').exists():
        for n, r in json.load(open(HERE / 'gen/lv_rows.json')).items():
            if (GR / f'{n}.npz').exists() and (LVC / f'{n}.npz').exists(): tr_f.append(LVC / f'{n}.npz')
    ev_f = sorted(f for f in EVC.glob('st2*.npz') if (GR / f.name).exists())
    tr, va, ev = G(tr_f, dev, (0, 2)), G(va_f, dev, (0,)), G(ev_f, dev, (0,))
    print(a.name, 'train flights', len(tr_f), tr.N, 'val', len(va_f), va.N, 'st2dev', len(ev_f), ev.N, flush=True)
    net = T.Net(a.res, a.width, 1, 7).to(dev); print('params/MACs', T.count(net, 1, 7, a.res), flush=True)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4); sch = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=a.epochs * a.steps, pct_start=0.1)
    best = 1e9
    for ep in range(a.epochs):
        net.train(); tl = 0
        for _ in range(a.steps):
            ix = torch.randint(0, tr.N, (a.bs,), device=dev); img, vec, y = batch(tr, ix, a.res, True)
            fl = torch.rand(a.bs, device=dev) < 0.5
            i2, v2, y2 = flip(img[fl], vec[fl], y[fl]); img = img.clone(); vec = vec.clone(); y = y.clone(); img[fl], vec[fl], y[fl] = i2, v2, y2
            mu, lv = net(img, vec); mu, lv = mu[:, 0], lv[:, 0]
            loss = (T.nll(mu, lv, y).sum(-1) if ep >= 1 else ((mu - y) ** 2).sum(-1)).mean()
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sch.step(); tl += loss.item()
        mv, _ = predict(net, va, a.res); me, le = predict(net, ev, a.res)
        av, ae = angerr(mv, va.gb), angerr(me, ev.gb)
        z = ((me - ev.gb) / torch.exp(0.5 * le)); zr = float(z.pow(2).mean().sqrt())
        if ep % 5 == 0 or ep == a.epochs - 1: print(f'ep {ep} train {tl/a.steps:.3f} val ang mean {av.mean():.2f} med {av.median():.2f} | st2dev mean {ae.mean():.2f} med {ae.median():.2f} p90 {ae.quantile(.9):.2f} zrms {zr:.2f}', flush=True)
        if ep >= 3 and float(av.mean()) < best: best = float(av.mean()); torch.save(net.state_dict(), out / 'best.pt')
    net.load_state_dict(torch.load(out / 'best.pt')); me, le = predict(net, ev, a.res); ae = angerr(me, ev.gb)
    np.savez(out / 'st2dev_pred.npz', mu=me.cpu().numpy(), lv=le.cpu().numpy(), y=ev.gb.cpu().numpy(), fid=ev.fid.cpu().numpy(), names=np.array(ev.names))
    res = dict(args=vars(a), val_best=best, st2_mean=float(ae.mean()), st2_med=float(ae.median()), st2_p90=float(ae.quantile(.9)))
    json.dump(res, open(out / 'result.json', 'w')); print('DONE', json.dumps(res), flush=True)
main()
