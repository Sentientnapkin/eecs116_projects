"""Train the startup-velocity net. One process per GPU (CUDA_VISIBLE_DEVICES).
  python -B train.py --name n64w1_s0 --res 64 --width 1 --nf 3 --gap 1 --seed 0
Data: cache from prep.py, roles train (fold 0-2, unselected) / val (fold 3). search_sel and sealed are never used for fitting.
Inputs: gyro-derotated gray frames (reference + warped later frames), coord channels, validity masks, plus an IMU vector
(mean specific force/gyro, preintegrated specific force, relative rotation, fx). Outputs: velocity (body frame) + log-variance
at the first window frame (head0) and at the last window frame (headK).
"""
import argparse, json, math, os, sys, time
from pathlib import Path
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, str(Path(__file__).parent))
import split

CACHE = Path('/data/backups/rganapa/Sebastian/tmp/learned_cache')
OUT = Path(__file__).parent / 'runs'


class Data:
    def __init__(self, roles, dev, names=None):
        rows = [r for r in split.load_rows() if r['role'] in roles and (names is None or r['name'] in names)]
        self.rows = rows
        fr, Rc, Vi, fm, gm, vb, fid, off, K, fx = [], [], [], [], [], [], [], [], [], []
        o = 0; self.Tbc = None; self.flight_len = []
        for i, r in enumerate(rows):
            d = np.load(CACHE / f"{r['name']}.npz")
            assert r['role'] != 'sealed' and r['fold'] != 4
            if self.Tbc is None: self.Tbc = d['Tbc']
            assert np.allclose(self.Tbc, d['Tbc'])
            A = len(d['frames'])
            fr.append(d['frames']); Rc.append(d['Rcum']); Vi.append(d['Vint']); fm.append(d['fmean']); gm.append(d['gmean'])
            vb.append(d['vb'][::5][:A]); fid.append(np.full(A, i)); off.append(np.full(A, o)); K.append(np.tile(d['K'], (A, 1)))
            fx.append(np.full(A, float(d['fx320']))); o += A; self.flight_len.append(A)
        c = lambda x, dt=torch.float32: torch.from_numpy(np.concatenate(x)).to(dev).to(dt)
        self.frames = torch.from_numpy(np.concatenate(fr)).to(dev)
        self.R, self.V, self.f, self.g, self.vb, self.K, self.fx = c(Rc), c(Vi), c(fm), c(gm), c(vb), c(K), c(fx)
        self.fid = torch.from_numpy(np.concatenate(fid)).to(dev); self.off = np.concatenate(off); self.N = o
        self.Rbc = torch.tensor(self.Tbc[:3, :3], dtype=torch.float32, device=dev)
        self.pos = torch.from_numpy(np.concatenate([np.arange(a) for a in self.flight_len])).to(dev)
        self.len = torch.from_numpy(np.concatenate([np.full(a, a) for a in self.flight_len])).to(dev)

    def valid_starts(self, nf, gap, positions=None):
        span = (nf - 1) * gap
        m = self.pos + span < self.len
        if positions is not None:
            m &= torch.isin(self.pos, torch.as_tensor(positions, device=self.pos.device))
        return torch.nonzero(m).squeeze(1)


H0, W0 = 96, 128
VEC_MIN = False  # habit-free variant: the IMU vector keeps only fx (no specific force / gyro rates / preintegration); derotation still uses the gyro
def pixel_grid(dev):
    v, u = torch.meshgrid(torch.arange(H0, device=dev, dtype=torch.float32), torch.arange(W0, device=dev, dtype=torch.float32), indexing='ij')
    return u, v


def build_batch(D, g, nf, gap, res, train, derotate=True):
    """g: (B,) global anchor indices -> image tensor (B,C,h,w), vector (B,nv), targets (B,2,3), flip flags."""
    dev = g.device; B = len(g)
    u, v = pixel_grid(dev)
    fx, fy, cx, cy = [D.K[g, i].view(B, 1, 1) for i in range(4)]
    ds = torch.stack([(u - cx) / fx, (v - cy) / fy, torch.ones(B, H0, W0, device=dev)], -1)  # (B,H,W,3)
    ims = [D.frames[g].float()]; masks = []
    rots = []
    for j in range(1, nf):
        gk = g + j * gap
        Rb = D.R[g].transpose(1, 2) @ D.R[gk]
        Rc = D.Rbc.T @ Rb @ D.Rbc
        rots.append(Rb)
        img = D.frames[gk].float()[:, None]
        if derotate:
            dk = torch.einsum('bji,bhwj->bhwi', Rc, ds)  # Rc^T d
            z = dk[..., 2].clamp(min=1e-3)
            uk = fx * dk[..., 0] / z + cx; vk = fy * dk[..., 1] / z + cy
            gx = (uk + 0.5) / W0 * 2 - 1; gy = (vk + 0.5) / H0 * 2 - 1
            grid = torch.stack([gx, gy], -1)
            out = F.grid_sample(img, grid, mode='bilinear', padding_mode='zeros', align_corners=False)[:, 0]
            ok = ((gx.abs() <= 1) & (gy.abs() <= 1) & (dk[..., 2] > 1e-3)).float()
        else:
            out = img[:, 0]; ok = torch.ones_like(out)
        ims.append(out); masks.append(ok)
    X = torch.stack(ims, 1)  # (B,nf,H,W)
    M = torch.stack(masks, 1) if masks else torch.zeros(B, 0, H0, W0, device=dev)
    # per-frame normalisation (valid region), brightness invariance
    allm = torch.cat([torch.ones(B, 1, H0, W0, device=dev), M], 1)
    mean = (X * allm).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    var = (((X - mean) * allm) ** 2).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    X = (X - mean) / (var.sqrt() + 5.0) * allm
    if train:
        X = X + 0.03 * torch.randn_like(X) * allm
    ca = torch.linspace(-1, 1, W0, device=dev).view(1, 1, 1, W0).expand(B, 1, H0, W0)
    cb = torch.linspace(-1, 1, H0, device=dev).view(1, 1, H0, 1).expand(B, 1, H0, W0)
    img = torch.cat([X, M, ca, cb], 1)
    if res != W0:
        s = W0 // res
        img = F.avg_pool2d(img, s)
    # vector features
    last = g + (nf - 1) * gap
    Rs = D.R[g]
    parts = [D.f[g] / 9.81, D.g[g], D.f[last] / 9.81, D.g[last]]
    for j in range(1, nf):
        gk = g + j * gap
        dv = torch.einsum('bji,bj->bi', Rs, D.V[gk] - D.V[g]) / (0.05 * 5 * gap * j * 9.81)  # ~ unit along up, scale ~1
        rv = rot_vec(Rs.transpose(1, 2) @ D.R[gk])
        parts += [dv, rv]
    parts.append((D.fx[g] / 100.0).view(B, 1))
    vec = torch.cat(parts, 1)
    if VEC_MIN:
        keep = torch.zeros(vec.shape[1], device=dev); keep[-1] = 1; vec = vec * keep
    tgt = torch.stack([D.vb[g], D.vb[last]], 1)
    return img, vec, tgt, last


def rot_vec(R):
    tr = (R[:, 0, 0] + R[:, 1, 1] + R[:, 2, 2] - 1) / 2
    th = torch.acos(tr.clamp(-1 + 1e-6, 1 - 1e-6))
    w = torch.stack([R[:, 2, 1] - R[:, 1, 2], R[:, 0, 2] - R[:, 2, 0], R[:, 1, 0] - R[:, 0, 1]], 1)
    return w / (2 * torch.sin(th) + 1e-6)[:, None] * th[:, None]


def flip(img, vec, tgt, nf):
    """mirror about the vertical image axis == body y -> -y"""
    img = torch.cat([img[:, :-2].flip(3), img[:, -2:]], 1)  # coordinate channels stay
    B = vec.shape[0]
    sgn_vec = torch.tensor([1, -1, 1], device=vec.device, dtype=vec.dtype)
    sgn_ax = torch.tensor([-1, 1, -1], device=vec.device, dtype=vec.dtype)  # pseudo-vector
    s = [sgn_vec, sgn_ax, sgn_vec, sgn_ax]
    for j in range(1, nf):
        s += [sgn_vec, sgn_ax]
    s.append(torch.ones(1, device=vec.device, dtype=vec.dtype))
    vec = vec * torch.cat(s)
    tgt = tgt * sgn_vec
    return img, vec, tgt


class Net(nn.Module):
    def __init__(self, res, width, nf, nvec, ch_extra=True, deep=False, use_img=True, use_vec=True, hidden=128):
        super().__init__()
        cin = nf + (nf - 1) + 2
        n_down = int(math.log2(res / 4))
        base = [16, 24, 32, 48, 64, 64]
        chs = [max(4, int(round(b * width))) for b in base[:n_down]] if n_down <= 5 else None
        self.use_img, self.use_vec = use_img, use_vec
        layers = []; c = cin
        for i, co in enumerate(chs):
            layers += [nn.Conv2d(c, co, 3, 2, 1, bias=False), nn.BatchNorm2d(co), nn.ReLU(inplace=True)]
            if deep and i < n_down - 1:
                layers += [nn.Conv2d(co, co, 3, 1, 1, bias=False), nn.BatchNorm2d(co), nn.ReLU(inplace=True)]
            c = co
        self.cnn = nn.Sequential(*layers)
        h, w = 3, 4
        feat = c * h * w if use_img else 0
        self.fv = nn.Sequential(nn.Linear(nvec, 32), nn.ReLU()) if use_vec else None
        self.head = nn.Sequential(nn.Linear(feat + (32 if use_vec else 0), hidden), nn.ReLU(), nn.Linear(hidden, 12))
        self.res, self.nf = res, nf

    def forward(self, img, vec):
        z = []
        if self.use_img:
            z.append(self.cnn(img).flatten(1))
        if self.use_vec:
            z.append(self.fv(vec))
        o = self.head(torch.cat(z, 1)).view(-1, 2, 6)
        return o[..., :3], o[..., 3:].clamp(-7, 4)  # mean, logvar


def count(net, nf, nvec, res):
    params = sum(p.numel() for p in net.parameters())
    macs = 0
    c_in = nf + (nf - 1) + 2; h = w = None; H = res * 3 // 4; W = res
    for m in net.cnn if net.use_img else []:
        if isinstance(m, nn.Conv2d):
            s = m.stride[0]; H = (H + 2 - 3) // s + 1; W = (W + 2 - 3) // s + 1
            macs += H * W * m.out_channels * m.in_channels * 9
    for m in net.modules():
        if isinstance(m, nn.Linear):
            macs += m.in_features * m.out_features
    return params, macs


def nll(mu, lv, y):
    return 0.5 * (((y - mu) ** 2) * torch.exp(-lv) + lv)


@torch.no_grad()
def predict(net, D, starts, nf, gap, res, bs=2048):
    net.eval(); mus, lvs, tg = [], [], []
    for i in range(0, len(starts), bs):
        g = starts[i:i + bs]
        img, vec, t, _ = build_batch(D, g, nf, gap, res, False)
        mu, lv = net(img, vec); mus.append(mu); lvs.append(lv); tg.append(t)
    return torch.cat(mus), torch.cat(lvs), torch.cat(tg)


def metrics(mu, lv, y, det=None):
    e = (mu - y)
    en = e.norm(dim=-1)
    sp = y.norm(dim=-1)
    ang = torch.rad2deg(torch.acos(((mu * y).sum(-1) / (mu.norm(dim=-1) * sp + 1e-9)).clamp(-1, 1)))
    z = e / torch.exp(0.5 * lv)
    return dict(err=en.mean(0).tolist(), rmse=(en ** 2).mean(0).sqrt().tolist(), ang_med=[float(ang[sp[:, k] > 0.3, k].median()) for k in (0, 1)],
                mag_err=(mu.norm(dim=-1) - sp).abs().mean(0).tolist(), nll=nll(mu, lv, y).sum(-1).mean(0).tolist(),
                cov1=(z.abs() < 1).float().mean((0, 2)).tolist(), cov2=(z.abs() < 2).float().mean((0, 2)).tolist(),
                sig_mean=torch.exp(0.5 * lv).mean((0, 2)).tolist())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--res', type=int, default=64); ap.add_argument('--width', type=float, default=1.0)
    ap.add_argument('--nf', type=int, default=3); ap.add_argument('--gap', type=int, default=1); ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--epochs', type=int, default=24); ap.add_argument('--bs', type=int, default=256); ap.add_argument('--lr', type=float, default=2e-3)
    ap.add_argument('--deep', type=int, default=0); ap.add_argument('--no_img', type=int, default=0); ap.add_argument('--no_vec', type=int, default=0)
    ap.add_argument('--no_derot', type=int, default=0); ap.add_argument('--vec_min', type=int, default=0); ap.add_argument('--scene_disjoint', type=int, default=0); ap.add_argument('--steps_per_epoch', type=int, default=400)
    a = ap.parse_args()
    global VEC_MIN
    VEC_MIN = bool(a.vec_min)
    dev = 'cuda'; torch.manual_seed(a.seed); np.random.seed(a.seed)
    out = OUT / a.name; out.mkdir(parents=True, exist_ok=True)
    names = None
    if a.scene_disjoint:
        rows = split.load_rows(); bad = {r['scene'] for r in rows if r['selected']}
        names = {r['name'] for r in rows if r['role'] == 'train' and r['scene'] not in bad}
    tr = Data(['train'], dev, names); va = Data(['val'], dev)
    trs = tr.valid_starts(a.nf, a.gap); vas = va.valid_starts(a.nf, a.gap)
    print(a.name, 'train flights', len(tr.rows), 'anchors', len(trs), 'val flights', len(va.rows), 'anchors', len(vas), flush=True)
    nvec = 3 * 4 + 6 * (a.nf - 1) + 1
    net = Net(a.res, a.width, a.nf, nvec, deep=bool(a.deep), use_img=not a.no_img, use_vec=not a.no_vec).to(dev)
    params, macs = count(net, a.nf, nvec, a.res)
    print('params', params, 'MACs/inference', macs, flush=True)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    total = a.epochs * a.steps_per_epoch
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=total, pct_start=0.1)
    best = (1e9, None); log = []
    step = 0; t0 = time.time()
    for ep in range(a.epochs):
        net.train(); tl = 0
        for _ in range(a.steps_per_epoch):
            g = trs[torch.randint(0, len(trs), (a.bs,), device=dev)]
            img, vec, tgt, _ = build_batch(tr, g, a.nf, a.gap, a.res, True, derotate=not a.no_derot)
            fl = torch.rand(a.bs, device=dev) < 0.5
            if fl.any():
                i2, v2, t2 = flip(img[fl], vec[fl], tgt[fl], a.nf)
                img = img.clone(); vec = vec.clone(); tgt = tgt.clone(); img[fl], vec[fl], tgt[fl] = i2, v2, t2
            mu, lv = net(img, vec)
            # warm-up: fixed unit variance for the first epoch, then learned
            if ep < 1:
                loss = (0.5 * (mu - tgt) ** 2).mean() * 3
            else:
                loss = nll(mu, lv, tgt).mean() * 3
            opt.zero_grad(set_to_none=True); loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step()
            tl += loss.item(); step += 1
        mu, lv, y = predict(net, va, vas, a.nf, a.gap, a.res)
        m = metrics(mu, lv, y)
        vnll = float(nll(mu, lv, y).sum(-1).mean())
        log.append(dict(epoch=ep, train=tl / a.steps_per_epoch, val_err=m['err'], val_nll=vnll))
        print(f"ep {ep} train {tl/a.steps_per_epoch:.3f} val err0 {m['err'][0]:.3f} errK {m['err'][1]:.3f} nll {vnll:.3f} cov1 {m['cov1'][0]:.2f} ({time.time()-t0:.0f}s)", flush=True)
        if ep >= 3 and m['err'][0] + m['err'][1] < best[0]:  # selection on val RMS-ish error (not NLL: keep sigma separately calibratable)
            best = (m['err'][0] + m['err'][1], ep); torch.save(net.state_dict(), out / 'best.pt')
    torch.save(net.state_dict(), out / 'last.pt')
    net.load_state_dict(torch.load(out / 'best.pt'))
    mu, lv, y = predict(net, va, vas, a.nf, a.gap, a.res)
    res = dict(args=vars(a), params=params, macs=macs, best_epoch=best[1], val=metrics(mu, lv, y), log=log,
               n_train_flights=len(tr.rows), n_train_anchors=int(len(trs)), n_val_flights=len(va.rows), n_val_anchors=int(len(vas)),
               train_flights=[r['name'] for r in tr.rows])
    json.dump(res, open(out / 'result.json', 'w'), indent=1)
    print('DONE', a.name, json.dumps({k: res[k] for k in ('params', 'macs', 'best_epoch')}), json.dumps(res['val']), flush=True)


if __name__ == '__main__':
    main()
