"""lv5.py (smallnet): train SEVERAL small velocity nets in lockstep on the same batches (one data load), from scratch and/or distilled.
Reuses netv2/tools/lv4.py (data D, sampling weights, report, time-reversal build) -- only the input preprocessing and the net change.

Config string (one per net, '|' separated):  name:key=val;key=val...
  chs=8,12,16,24   conv widths (3x3 stride 2 + BN + ReLU each; any count; multiples of 4)
  pre=ref|lo       ref: the GSLV pipeline (derotate at 128x96, normalise, 2x2 pool -> 48x64)
                   lo : pool the 128x96 gray frames to the net resolution FIRST (== 5x5 / 10x10 box of the 320x240 RGB mean),
                        derotate + normalise at that resolution (4x / 16x cheaper prep, no 128x96 gray)
  res=64|32        net input width (48x64 or 24x32)
  cin=5|3|2        input channels: x0,x1w,mask,(u,v coords)
  hid=128          head hidden width ; fvd=32 vector-embedding width
  gp=0|1           avg-pool the last conv output to 3x4 when it is larger
  kd=0.0           distillation weight (needs --teacher): kd * 0.5 * |mu_s - mu_t|^2 / var_s(detached), both heads
  lr=4e-3 wd=1e-4 seed=0
Example:
  CUDA_VISIBLE_DEVICES=5 python -B lv5.py --tag b1 --cfgs 'a:chs=8,12,16,24|b:chs=8,12,16,24;pre=lo' --teacher netv2:X80
"""
import argparse, json, sys, time, math
from pathlib import Path
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, '/data/backups/rganapa/Sebastian/gen3/research/i6/src')
import lv4
from lv4 import T, D, weights, report, old_files, new_files, val_meta, H0, W0
A3 = Path('/data/backups/rganapa/Sebastian/gen3/agents/smallnet'); RUNS = A3 / 'runs'

DEF = dict(chs='8,12,16,24', pre='ref', res=64, cin=5, hid=128, fvd=32, gp=0, kd=0.0, lr=4e-3, wd=1e-4, seed=0, init='')

def parse(s):
    out = []
    for part in s.split('|'):
        name, _, kv = part.partition(':'); c = dict(DEF)
        for x in filter(None, kv.split(';')):
            k, v = x.split('='); c[k] = type(DEF[k])(v) if k in DEF and not isinstance(DEF[k], str) else v
        c['name'] = name; out.append(c)
    return out

class SNet(nn.Module):
    def __init__(self, c):
        super().__init__()
        chs = [int(x) for x in str(c['chs']).split(',')]; ci = int(c['cin'])
        layers = []
        for co in chs:
            layers += [nn.Conv2d(ci, co, 3, 2, 1, bias=False), nn.BatchNorm2d(co), nn.ReLU(inplace=True)]; ci = co
        self.cnn = nn.Sequential(*layers)
        h = (48 if int(c['res']) == 64 else 24); w = h * 4 // 3
        for _ in chs: h, w = (h + 1) // 2, (w + 1) // 2
        self.gp = int(c['gp']) and (h, w) != (3, 4)
        if self.gp: h, w = 3, 4
        self.hw = (h, w); fvd = int(c['fvd'])
        self.fv = nn.Sequential(nn.Linear(19, fvd), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(ci * h * w + fvd, int(c['hid'])), nn.ReLU(), nn.Linear(int(c['hid']), 12))
    def forward(self, img, vec):
        z = self.cnn(img)
        if self.gp: z = F.adaptive_avg_pool2d(z, (3, 4))
        o = self.head(torch.cat([z.flatten(1), self.fv(vec)], 1)).view(-1, 2, 6)
        return o[..., :3], o[..., 3:].clamp(-7, 4)

def macs(net, c):
    h = 48 if int(c['res']) == 64 else 24; w = h * 4 // 3; m = 0
    for mod in net.cnn:
        if isinstance(mod, nn.Conv2d): h, w = (h + 1) // 2, (w + 1) // 2; m += h * w * mod.in_channels * mod.out_channels * 9
    for mod in net.modules():
        if isinstance(mod, nn.Linear): m += mod.in_features * mod.out_features
    return m

def build_lo(Dd, g, train, rev, res, cin):
    """'lo' preprocessing: gray frames pooled to (h,w) first, derotated + normalised there. Mirrors the SN C code."""
    dev = g.device; B = len(g); f = 128 // res; h, w = H0 // f, W0 // f
    a, b = (g, g + 1) if rev is None else (torch.where(rev, g + 1, g), torch.where(rev, g, g + 1))
    sgn = (1 - 2 * rev.float()).view(B, 1) if rev is not None else torch.ones(B, 1, device=dev)
    idx = torch.stack([a, b], 1).cpu()
    fr = Dd.frames[idx.view(-1)].to(dev, non_blocking=True).view(B, 2, H0, W0).float()
    fr = F.avg_pool2d(fr, f)
    v_, u_ = torch.meshgrid(torch.arange(h, device=dev, dtype=torch.float32), torch.arange(w, device=dev, dtype=torch.float32), indexing='ij')
    s = 1.0 / f
    fx, fy = [Dd.K[g, i].view(B, 1, 1) * s for i in range(2)]
    cx, cy = [(Dd.K[g, i].view(B, 1, 1) + 0.5) * s - 0.5 for i in (2, 3)]
    ds = torch.stack([(u_ - cx) / fx, (v_ - cy) / fy, torch.ones(B, h, w, device=dev)], -1)
    Rb = Dd.R[a].transpose(1, 2) @ Dd.R[b]; Rc = Dd.Rbc.T @ Rb @ Dd.Rbc
    dk = torch.einsum('bji,bhwj->bhwi', Rc, ds); z = dk[..., 2].clamp(min=1e-3)
    uk = fx * dk[..., 0] / z + cx; vk = fy * dk[..., 1] / z + cy
    gx = (uk + 0.5) / w * 2 - 1; gy = (vk + 0.5) / h * 2 - 1
    out = F.grid_sample(fr[:, 1:2], torch.stack([gx, gy], -1), mode='bilinear', padding_mode='zeros', align_corners=False)[:, 0]
    ok = ((gx.abs() <= 1) & (gy.abs() <= 1) & (dk[..., 2] > 1e-3)).float()
    X = torch.stack([fr[:, 0], out], 1); M = ok[:, None]
    allm = torch.cat([torch.ones(B, 1, h, w, device=dev), M], 1)
    mean = (X * allm).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    var = (((X - mean) * allm) ** 2).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    X = (X - mean) / (var.sqrt() + 5.0) * allm
    if train: X = X + 0.015 * torch.randn_like(X) * allm
    chans = [X, M]
    if cin == 5:
        chans += [torch.linspace(-1, 1, w, device=dev).view(1, 1, 1, w).expand(B, 1, h, w), torch.linspace(-1, 1, h, device=dev).view(1, 1, h, 1).expand(B, 1, h, w)]
    img = torch.cat(chans, 1)[:, :cin]
    Rs = Dd.R[a]
    dv = torch.einsum('bji,bj->bi', Rs, Dd.V[b] - Dd.V[a]) * sgn / (0.05 * 5 * 9.81)
    vec = torch.cat([Dd.f[a] / 9.81, Dd.g[a] * sgn, Dd.f[b] / 9.81, Dd.g[b] * sgn, dv, T.rot_vec(Rs.transpose(1, 2) @ Dd.R[b]), (Dd.fx[g] / 100.0).view(B, 1)], 1)
    tgt = torch.stack([Dd.vb[a], Dd.vb[b]], 1) * sgn.view(B, 1, 1)
    return img, vec, tgt

def build_any(Dd, g, train, rev, c):
    if c['pre'] == 'ref':
        img, vec, tgt = lv4.build(Dd, g, train, rev)
        if int(c['res']) == 32: img = F.avg_pool2d(img, 2)
        return img[:, :int(c['cin'])], vec, tgt
    return build_lo(Dd, g, train, rev, int(c['res']), int(c['cin']))

def flip(img, vec, tgt, cin):
    nimg = 3 if cin >= 3 else cin
    img = torch.cat([img[:, :nimg].flip(3), img[:, nimg:]], 1)
    sv = torch.tensor([1, -1, 1], device=vec.device, dtype=vec.dtype); sa = torch.tensor([-1, 1, -1], device=vec.device, dtype=vec.dtype)
    vec = vec * torch.cat([sv, sa, sv, sa, sv, sa, torch.ones(1, device=vec.device)])
    return img, vec, tgt * sv

def key(c): return (c['pre'], int(c['res']), int(c['cin']))

@torch.no_grad()
def predict_multi(nets, cfgs, Dd, st, teacher=None, bs=4096):
    for n in nets: n.eval()
    res = [([], [], []) for _ in nets]
    for i in range(0, len(st), bs):
        g = st[i:i + bs]; cache = {}
        for j, (n, c) in enumerate(zip(nets, cfgs)):
            k = key(c)
            if k not in cache: cache[k] = build_any(Dd, g, False, None, c)
            img, vec, t = cache[k]; mu, lv = n(img, vec)
            res[j][0].append(mu[:, 1]); res[j][1].append(lv[:, 1]); res[j][2].append(t[:, 1])
    return [tuple(torch.cat(x) for x in r) for r in res]

def load_teacher(spec, dev):
    """netv2:RUN or net:RUN or a path to a lv4 run dir (ref preprocessing, 4 convs)."""
    base = {'netv2': '/data/backups/rganapa/Sebastian/gen3/agents/netv2/runs', 'net': '/data/backups/rganapa/Sebastian/gen3/agents/net/runs'}
    p = Path(base[spec.split(':')[0]]) / spec.split(':')[1] if ':' in spec else Path(spec)
    args = json.load(open(p / 'result.json')).get('args', {})
    a = argparse.Namespace(chs=args.get('chs', '16,24,32,48'), deep=args.get('deep', 0), hidden=args.get('hidden', 128))
    net = lv4.make_net(a).to(dev); net.load_state_dict(torch.load(p / 'best.pt', map_location=dev)); net.eval()
    for q in net.parameters(): q.requires_grad_(False)
    return net

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True); ap.add_argument('--cfgs', required=True); ap.add_argument('--teacher', default='')
    ap.add_argument('--epochs', type=int, default=80); ap.add_argument('--steps', type=int, default=400); ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--beta', type=float, default=0.5); ap.add_argument('--alpha', type=float, default=0.5)
    ap.add_argument('--old', type=float, default=0.3); ap.add_argument('--old_max', type=int, default=100000); ap.add_argument('--rev', type=float, default=0.3)
    ap.add_argument('--list', default='/data/backups/rganapa/Sebastian/gen3/agents/netv2/lists/train727.txt'); ap.add_argument('--mirror', type=float, default=0.5)
    ap.add_argument('--valn', type=int, default=0, help='use only the first N val flights for per-epoch selection (0 = all 749)')
    a = ap.parse_args(); dev = 'cuda'; torch.set_num_threads(3); torch.manual_seed(0); np.random.seed(0)
    cfgs = parse(a.cfgs)
    allnew, nmeta = new_files()
    keep = [l.strip() for l in open(a.list) if l.strip()]; have = {f.stem: f for f in allnew}; nf_ = [have[n] for n in keep if n in have]
    of = old_files() if a.old > 0 else []
    rng = np.random.default_rng(0); of = [of[i] for i in sorted(rng.permutation(len(of))[:a.old_max])]
    files = of + nf_; grp = [0] * len(of) + [1] * len(nf_)
    t0 = time.time(); tr = D(files, dev, (0, 2), grp)
    vm = val_meta(); vfiles = sorted((lv4.A / 'cache/val').glob('*.npz'))
    vk = set(l.strip() for l in open(lv4.A2 / 'lists/val749.txt')); vfiles = [f for f in vfiles if f.stem in vk]
    if a.valn: vfiles = vfiles[::max(1, len(vfiles) // a.valn)]
    va = D(vfiles, dev, (0,)); trs, vas = tr.starts(), va.starts()
    w = weights(tr, trs, a.alpha, [a.old, 1 - a.old] if of else [0, 1.0])
    print(a.tag, 'old', len(of), 'new', len(nf_), 'anchors', len(trs), 'val', len(vfiles), len(vas), f'load {time.time()-t0:.0f}s', flush=True)
    teacher = load_teacher(a.teacher, dev) if a.teacher else None
    nets, opts, scheds, best, outs = [], [], [], [], []
    tot = a.epochs * a.steps
    for c in cfgs:
        torch.manual_seed(int(c['seed']))
        n = SNet(c).to(dev)
        if c['init']:
            sd = torch.load(c['init'], map_location=dev); own = n.state_dict(); own.update({k: v for k, v in sd.items() if k in own and own[k].shape == v.shape}); n.load_state_dict(own)
        nets.append(n); o = torch.optim.AdamW(n.parameters(), lr=float(c['lr']), weight_decay=float(c['wd'])); opts.append(o)
        scheds.append(torch.optim.lr_scheduler.OneCycleLR(o, max_lr=float(c['lr']), total_steps=tot, pct_start=0.1))
        best.append((1e9, -1)); out = RUNS / c['name']; out.mkdir(parents=True, exist_ok=True); outs.append(out)
        c['macs'] = macs(n, c); c['params'] = sum(p.numel() for p in n.parameters())
        print('cfg', json.dumps(c), flush=True)
    logs = [[] for _ in cfgs]
    for ep in range(a.epochs):
        for n in nets: n.train()
        tl = [0.0] * len(nets)
        for _ in range(a.steps):
            g = trs[torch.multinomial(w, a.bs, replacement=True)]
            rev = torch.rand(a.bs, device=dev) < a.rev; fl = torch.rand(a.bs, device=dev) < a.mirror
            cache = {}
            if teacher is not None:
                with torch.no_grad():
                    img, vec, tgt = lv4.build(tr, g, False, rev)
                    i2, v2, t2 = T.flip(img[fl], vec[fl], tgt[fl], 2); img[fl], vec[fl] = i2, v2
                    tmu, tlv = teacher(img, vec)
            for j, (n, c) in enumerate(zip(nets, cfgs)):
                k = key(c)
                if k not in cache:
                    img, vec, tgt = build_any(tr, g, True, rev, c)
                    i2, v2, t2 = flip(img[fl], vec[fl], tgt[fl], int(c['cin'])); img = img.clone(); vec = vec.clone(); tgt = tgt.clone()
                    img[fl], vec[fl], tgt[fl] = i2, v2, t2; cache[k] = (img, vec, tgt)
                img, vec, tgt = cache[k]
                mu, lv = n(img, vec)
                if ep >= 1 or c['init']:
                    loss = (T.nll(mu, lv, tgt) * (torch.exp(lv.detach()) ** a.beta if a.beta else 1)).sum(-1).mean(-1).mean()
                else: loss = (0.5 * (mu - tgt) ** 2).sum(-1).mean()
                if teacher is not None and float(c['kd']) > 0:
                    loss = loss + float(c['kd']) * (0.5 * (mu - tmu) ** 2 / torch.exp(lv.detach()).clamp(min=1e-3)).sum(-1).mean()
                opts[j].zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(n.parameters(), 5.0); opts[j].step(); scheds[j].step(); tl[j] += loss.item()
        preds = predict_multi(nets, cfgs, va, vas)
        for j, (n, c) in enumerate(zip(nets, cfgs)):
            r = report(*preds[j], va, vas, vm); logs[j].append(dict(epoch=ep, train=tl[j] / a.steps, val=r))
            print(f"ep {ep} {c['name']:12s} train {tl[j]/a.steps:.3f} val all {r['all']:.4f} fast {r['fast']:.4f} side {r['side']:.4f} back {r['back']:.4f} zrms {r['zrms']:.2f} ({time.time()-t0:.0f}s)", flush=True)
            if r['all'] < best[j][0]: best[j] = (r['all'], ep); torch.save(n.state_dict(), outs[j] / 'best.pt')
            torch.save(n.state_dict(), outs[j] / 'last.pt')
            json.dump(dict(cfg=c, args=vars(a), best_epoch=best[j][1], best=best[j][0], log=logs[j]), open(outs[j] / 'result.json', 'w'), indent=1)
    for j, (n, c) in enumerate(zip(nets, cfgs)):
        n.load_state_dict(torch.load(outs[j] / 'best.pt'))
    if a.valn:  # final full-val report of the best checkpoints
        vfiles = sorted((lv4.A / 'cache/val').glob('*.npz')); vfiles = [f for f in vfiles if f.stem in vk]
        del va; va = D(vfiles, dev, (0,)); vas = va.starts()
    preds = predict_multi(nets, cfgs, va, vas)
    for j, (n, c) in enumerate(zip(nets, cfgs)):
        r = report(*preds[j], va, vas, vm)
        json.dump(dict(cfg=c, args=vars(a), best_epoch=best[j][1], val=r, log=logs[j]), open(outs[j] / 'result.json', 'w'), indent=1)
        print('DONE', c['name'], 'best_ep', best[j][1], 'macs', c['macs'], json.dumps(r)[:400], flush=True)

if __name__ == '__main__':
    main()
