"""lv3.py: stage-3 fine-tuning / retraining of the GSLV learned-velocity net (same architecture as learnvel v700b: nf=2, res 64, width 1).
Frames live on the CPU (pinned uint8) so old + new data fit; everything else on the GPU.
Data groups (sampling weight per group, then speed x direction bins inside a group, alpha-tempered):
  old  = learned_c lc_cache train rows + learnvel lv_cache_train (stage-1/2 forward flights)
  new  = agents/net/cache/train (HF viobench-stage3 TRAIN split only)
Augment: mirror (body y), TIME REVERSAL (frames swapped, gyro negated, preintegral re-expressed, targets negated) -> backwards motion.
Validation / selection: agents/net/cache/val (local v3 val zips), head K (the one GSLV uses), phase 0, every anchor.
  CUDA_VISIBLE_DEVICES=5 python -B lv3.py --name ft1 --init v700b --lr 1e-3 --epochs 30
"""
import argparse, json, sys, time, glob
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
SM = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model')
sys.path.insert(0, str(SM / 'learned_c')); sys.path.insert(0, str(SM / 'learned'))
import train as T, split2
A = Path('/data/backups/rganapa/Sebastian/gen3/agents/net')
LCC = Path('/data/backups/rganapa/Sebastian/tmp/lc_cache'); LVC = Path('/data/backups/rganapa/Sebastian/tmp/lv_cache_train')
RUNS = A / 'runs'; G3 = Path('/data/backups/rganapa/Sebastian/gen3')
H0, W0 = 96, 128

def old_files():
    out = []
    for r in split2.load_rows():
        if r['role'] != 'train' or r['pool'] not in ('fast', 'speed', 'new'): continue
        f = LCC / f"{r['name']}.npz"
        if f.exists(): out.append(f)
    rows = json.load(open(SM / 'learnvel/gen/lv_rows.json'))
    out += [LVC / f'{n}.npz' for n, r in rows.items() if r['fold'] in (0, 1, 2) and (LVC / f'{n}.npz').exists()]
    return out

def new_files():
    meta = {}
    if (A / 'cache/train_meta.jsonl').exists():
        for l in open(A / 'cache/train_meta.jsonl'):
            r = json.loads(l); meta[r['id']] = r
    return [A / f'cache/train/{n}.npz' for n in sorted(meta) if (A / f'cache/train/{n}.npz').exists()], meta

def val_meta():
    m = {}
    for p in glob.glob(str(G3 / 'out/up/s3v3va*.json')) + glob.glob(str(G3 / 'out/ep/s3v3va*.json')):
        r = json.load(open(p)); m[r['id']] = r
    return m

class D:
    """anchors of several flights x phases. frames on CPU (pinned), rest on dev."""
    def __init__(self, files, dev, phases, group=None):
        fr, Rc, Vi, fm, gm, vb, K, fx, fid, pos, ln, grp = ([] for _ in range(12)); self.names = []
        for i, f in enumerate(files):
            d = np.load(f); self.Tbc = d['Tbc']; self.names.append(Path(f).stem)
            for p in phases:
                if f'frames{p}' not in d: continue
                n = len(d[f'frames{p}'])
                fr.append(d[f'frames{p}']); Rc.append(d[f'Rcum{p}']); Vi.append(d[f'Vint{p}']); fm.append(d[f'fmean{p}']); gm.append(d[f'gmean{p}'])
                vb.append(d[f'vb{p}']); K.append(np.tile(d['K'], (n, 1))); fx.append(np.full(n, float(d['fx320'])))
                fid.append(np.full(n, i)); pos.append(np.arange(n)); ln.append(np.full(n, n)); grp.append(np.full(n, 0 if group is None else group[i]))
        c = lambda x: torch.from_numpy(np.concatenate(x)).float().to(dev)
        self.frames = torch.from_numpy(np.concatenate(fr))
        if dev == 'cuda' and self.frames.numel() < 3e9: self.frames = self.frames.pin_memory()
        self.R, self.V, self.f, self.g, self.vb, self.K, self.fx = c(Rc), c(Vi), c(fm), c(gm), c(vb), c(K), c(fx)
        L = lambda x: torch.from_numpy(np.concatenate(x)).long().to(dev)
        self.fid, self.pos, self.len, self.grp = L(fid), L(pos), L(ln), L(grp)
        self.Rbc = torch.tensor(self.Tbc[:3, :3], dtype=torch.float32, device=dev)
        self.N = len(self.pos)
    def starts(self):
        return torch.nonzero(self.pos + 1 < self.len).squeeze(1)

def build(Dd, g, train, rev=None):
    """pair (a=g, b=g+1) -> (img, vec, tgt). rev: bool mask -> time-reversed sample (ref = b, second = a)."""
    dev = g.device; B = len(g)
    a, b = g, g + 1
    if rev is not None:
        a, b = torch.where(rev, g + 1, g), torch.where(rev, g, g + 1)
    sgn = (1 - 2 * rev.float()).view(B, 1) if rev is not None else torch.ones(B, 1, device=dev)
    u, v = T.pixel_grid(dev)
    fx, fy, cx, cy = [Dd.K[g, i].view(B, 1, 1) for i in range(4)]
    ds = torch.stack([(u - cx) / fx, (v - cy) / fy, torch.ones(B, H0, W0, device=dev)], -1)
    idx = torch.stack([a, b], 1).cpu()
    fr = Dd.frames[idx.view(-1)].to(dev, non_blocking=True).view(B, 2, H0, W0).float()
    Rb = Dd.R[a].transpose(1, 2) @ Dd.R[b]; Rc = Dd.Rbc.T @ Rb @ Dd.Rbc
    dk = torch.einsum('bji,bhwj->bhwi', Rc, ds); z = dk[..., 2].clamp(min=1e-3)
    uk = fx * dk[..., 0] / z + cx; vk = fy * dk[..., 1] / z + cy
    gx = (uk + 0.5) / W0 * 2 - 1; gy = (vk + 0.5) / H0 * 2 - 1
    out = F.grid_sample(fr[:, 1:2], torch.stack([gx, gy], -1), mode='bilinear', padding_mode='zeros', align_corners=False)[:, 0]
    ok = ((gx.abs() <= 1) & (gy.abs() <= 1) & (dk[..., 2] > 1e-3)).float()
    X = torch.stack([fr[:, 0], out], 1); M = ok[:, None]
    allm = torch.cat([torch.ones(B, 1, H0, W0, device=dev), M], 1)
    mean = (X * allm).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    var = (((X - mean) * allm) ** 2).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    X = (X - mean) / (var.sqrt() + 5.0) * allm
    if train: X = X + 0.03 * torch.randn_like(X) * allm
    ca = torch.linspace(-1, 1, W0, device=dev).view(1, 1, 1, W0).expand(B, 1, H0, W0)
    cb = torch.linspace(-1, 1, H0, device=dev).view(1, 1, H0, 1).expand(B, 1, H0, W0)
    img = F.avg_pool2d(torch.cat([X, M, ca, cb], 1), 2)
    Rs = Dd.R[a]
    dv = torch.einsum('bji,bj->bi', Rs, Dd.V[b] - Dd.V[a]) * sgn / (0.05 * 5 * 9.81)
    vec = torch.cat([Dd.f[a] / 9.81, Dd.g[a] * sgn, Dd.f[b] / 9.81, Dd.g[b] * sgn, dv, T.rot_vec(Rs.transpose(1, 2) @ Dd.R[b]), (Dd.fx[g] / 100.0).view(B, 1)], 1)
    tgt = torch.stack([Dd.vb[a], Dd.vb[b]], 1) * sgn.view(B, 1, 1)
    return img, vec, tgt

@torch.no_grad()
def predict(net, Dd, st, bs=2048):
    net.eval(); mus, lvs, ys = [], [], []
    for i in range(0, len(st), bs):
        img, vec, t = build(Dd, st[i:i + bs], False); mu, lv = net(img, vec); mus.append(mu[:, 1]); lvs.append(lv[:, 1]); ys.append(t[:, 1])
    return torch.cat(mus), torch.cat(lvs), torch.cat(ys)

def dir_class(y, Rbc):
    """direction of travel vs camera optical axis (body frame): 0 fwd (<45 deg), 1 side (45-135), 2 back (>135); -1 slow (<0.5 m/s)"""
    sp = y.norm(dim=-1); ax = Rbc[:, 2]
    ang = torch.rad2deg(torch.acos(((y @ ax) / (sp + 1e-9)).clamp(-1, 1)))
    c = torch.bucketize(ang, torch.tensor([45., 135.], device=y.device))
    return torch.where(sp > 0.5, c, torch.full_like(c, -1))

def report(mu, lv, y, Dd, st, meta):
    e = (mu - y).norm(dim=-1); sp = y.norm(dim=-1); z = (mu - y) / torch.exp(0.5 * lv)
    r = dict(n=int(len(e)), all=float(e.mean()), fast=float(e[sp > 1.5].mean()), zrms=float(z.pow(2).mean().sqrt()))
    m = sp > 1.0; r['scale_gt1'] = float(((mu[m] * y[m]).sum(-1) / sp[m] ** 2).mean())
    dc = dir_class(y, Dd.Rbc)
    for k, nm in [(0, 'fwd'), (1, 'side'), (2, 'back')]: r[nm] = float(e[dc == k].mean()) if (dc == k).any() else None
    fl = Dd.fid[st].cpu().numpy(); names = Dd.names; en = e.cpu().numpy()
    def by(key, fn):
        out = {}
        for i, n in enumerate(names):
            k = fn(meta.get(n, {})); out.setdefault(k, []).append(i)
        return {k: round(float(en[np.isin(fl, v)].mean()), 4) for k, v in sorted(out.items(), key=lambda x: str(x[0]))}
    r['class'] = by('class', lambda m: m.get('setting_class'))
    r['regime'] = by('regime', lambda m: m.get('regime'))
    r['blur'] = by('blur', lambda m: None if m.get('exposure_s') is None else ('<15ms' if m['exposure_s'] < .015 else '15-35' if m['exposure_s'] < .035 else '>35ms'))
    r['fov'] = by('fov', lambda m: None if m.get('fov_deg') is None else ('<95' if m['fov_deg'] < 95 else '95-115' if m['fov_deg'] < 115 else '>115'))
    return r

def weights(Dd, st, alpha, gw):
    sp = Dd.vb[st + 1].norm(dim=-1); sb = torch.bucketize(sp, torch.tensor([0.3, 1.0, 1.5, 2.5], device=sp.device))
    dc = dir_class(Dd.vb[st + 1], Dd.Rbc) + 1; gr = Dd.grp[st]
    key = (gr * 6 + sb) * 4 + dc; cnt = torch.bincount(key, minlength=int(key.max()) + 1).float()
    w = cnt[key] ** (-alpha)
    for k, wk in enumerate(gw):  # group totals -> gw
        m = gr == k
        if m.any(): w[m] = w[m] / w[m].sum() * wk
    return w / w.sum()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--init', default='v700b'); ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--epochs', type=int, default=30); ap.add_argument('--steps', type=int, default=400); ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--lr', type=float, default=1e-3); ap.add_argument('--beta', type=float, default=0.5); ap.add_argument('--alpha', type=float, default=0.5)
    ap.add_argument('--old', type=float, default=0.5, help='sampling share of old (stage-1/2) data'); ap.add_argument('--old_max', type=int, default=100000)
    ap.add_argument('--rev', type=float, default=0.3, help='time-reversal probability'); ap.add_argument('--nolim', type=int, default=0)
    a = ap.parse_args(); dev = 'cuda'; torch.manual_seed(a.seed); np.random.seed(a.seed)
    out = RUNS / a.name; out.mkdir(parents=True, exist_ok=True)
    nf_, nmeta = new_files(); of = old_files() if a.old > 0 else []
    rng = np.random.default_rng(a.seed); of = [of[i] for i in sorted(rng.permutation(len(of))[:a.old_max])]
    files = of + nf_; grp = [0] * len(of) + [1] * len(nf_)
    t0 = time.time(); tr = D(files, dev, (0, 2), grp)
    vm = val_meta(); vfiles = sorted((A / 'cache/val').glob('*.npz')); va = D(vfiles, dev, (0,))
    trs, vas = tr.starts(), va.starts()
    gw = [a.old, 1 - a.old] if nf_ and of else [1.0, 0] if of else [0, 1.0]
    w = weights(tr, trs, a.alpha, gw)
    print(a.name, 'old', len(of), 'new', len(nf_), 'anchors', len(trs), 'val flights', len(vfiles), 'anchors', len(vas), f'load {time.time()-t0:.0f}s', flush=True)
    net = T.Net(64, 1.0, 2, 19).to(dev)
    if a.init:
        p = Path(a.init) if '/' in a.init else SM / 'learnvel/runs' / a.init
        net.load_state_dict(torch.load(p / 'best.pt' if p.is_dir() else p, map_location=dev))
    r0 = report(*predict(net, va, vas), va, vas, vm); print('init', json.dumps(r0), flush=True)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * a.steps, pct_start=0.1)
    best = (1e9, -1); log = []
    for ep in range(a.epochs):
        net.train(); tl = 0
        for _ in range(a.steps):
            g = trs[torch.multinomial(w, a.bs, replacement=True)]
            rev = torch.rand(a.bs, device=dev) < a.rev
            img, vec, tgt = build(tr, g, True, rev)
            fl = torch.rand(a.bs, device=dev) < 0.5
            i2, v2, t2 = T.flip(img[fl], vec[fl], tgt[fl], 2); img = img.clone(); vec = vec.clone(); tgt = tgt.clone(); img[fl], vec[fl], tgt[fl] = i2, v2, t2
            mu, lv = net(img, vec)
            if a.init or ep >= 1: loss = (T.nll(mu, lv, tgt) * (torch.exp(lv.detach()) ** a.beta if a.beta else 1)).sum(-1).mean(-1).mean()
            else: loss = (0.5 * (mu - tgt) ** 2).sum(-1).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step(); tl += loss.item()
        r = report(*predict(net, va, vas), va, vas, vm); crit = r['all']
        log.append(dict(epoch=ep, train=tl / a.steps, val=r))
        print(f"ep {ep} train {tl/a.steps:.3f} val all {r['all']:.4f} fast {r['fast']:.4f} side {r['side']:.4f} back {r['back']:.4f} fwd {r['fwd']:.4f} zrms {r['zrms']:.2f} ({time.time()-t0:.0f}s)", flush=True)
        if crit < best[0]: best = (crit, ep); torch.save(net.state_dict(), out / 'best.pt')
    net.load_state_dict(torch.load(out / 'best.pt'))
    r = report(*predict(net, va, vas), va, vas, vm)
    json.dump(dict(args=vars(a), res=64, width=1.0, nf=2, gap=1, best_epoch=best[1], init_val=r0, val=r, log=log, n_old=len(of), n_new=len(nf_),
                   new_names=[f.stem for f in nf_]), open(out / 'result.json', 'w'), indent=1)
    print('DONE', a.name, 'best_ep', best[1], json.dumps(r), flush=True)

if __name__ == '__main__':
    main()
