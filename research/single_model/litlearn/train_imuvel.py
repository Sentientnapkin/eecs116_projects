"""TLIO-style IMU-window displacement net (1 s window, 200 Hz, 6ch) trained on 475 raw-fast flights (folds 0-2 unselected), evaluated on 107 unselected fold-3 flights.
Variant A: gravity-aligned local-yaw frame input (uses TRUTH attitude: optimistic vs filter attitude, 0.76 deg tilt / 3.9 deg yaw rms). Variant B: body frame IMU + gravity dir in body.
usage: CUDA_VISIBLE_DEVICES=1 python train_imuvel.py A|B [steps] [winlen_s]"""
import sys, json, glob, numpy as np, torch, torch.nn as nn, time
from pathlib import Path
CACHE = Path('/data/backups/rganapa/Sebastian/tmp/litlearn_cache')
HERE = Path(__file__).resolve().parent
var = sys.argv[1]; STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 8000; WL = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
W = int(round(200 * WL)); dev = 'cuda'
import os; GN = float(os.environ.get('GN', 0)); SUF = os.environ.get('SUF', ''); TGN = float(os.environ.get('TGN', 0))
tr_names = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learned/runs/n_nf2_r64_w1_s0/result.json'))['train_flights']
ev_names = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learned_c/feats.json'))
F3 = sorted(p.stem for p in Path('/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool').glob('*.zip'))

def load(names):
    A, Wg, R, P, off, Ts = [], [], [], [], [0], []
    for n in names:
        z = np.load(CACHE / f'{n}.npz'); A.append(z['a']); Wg.append(z['w']); R.append(z['R'].reshape(-1, 9)); P.append(z['p']); off.append(off[-1] + len(z['a']))
    return [torch.from_numpy(np.concatenate(x)).to(dev) for x in (A, Wg, R, P)], np.array(off)
def batch(D, idx):  # idx: global end index (inclusive end); window = idx-W+1..idx ; returns x (B,6,W), y (B,3) displacement in yaw/body frame
    A, Wg, R, P = D
    ar = torch.arange(-W + 1, 1, device=dev)
    ii = idx[:, None] + ar[None]
    a, w, r = A[ii], Wg[ii], R[ii].reshape(-1, W, 3, 3)
    re = r[:, -1]; psi = torch.atan2(re[:, 1, 0], re[:, 0, 0]); c, s = torch.cos(psi), torch.sin(psi)
    Ry = torch.zeros(len(idx), 3, 3, device=dev); Ry[:, 0, 0] = c; Ry[:, 0, 1] = -s; Ry[:, 1, 0] = s; Ry[:, 1, 1] = c; Ry[:, 2, 2] = 1  # yaw rotation (local-yaw -> world)
    d = P[idx] - P[idx - W + 1]
    if var == 'A':
        M = torch.einsum('bji,bwjk->bwik', Ry, r)  # Ry^T R  (body -> yaw-frame)
        x = torch.cat([torch.einsum('bwik,bwk->bwi', M, a), torch.einsum('bwik,bwk->bwi', M, w)], 2)
        y = torch.einsum('bji,bj->bi', Ry, d)
    else:
        g = r[:, :, 2, :]  # R^T z : gravity dir in body
        x = torch.cat([a, w, g], 2)
        y = torch.einsum('bji,bj->bi', re, d)
    x = x.transpose(1, 2).contiguous()
    return x, y
class Net(nn.Module):
    def __init__(s, cin):
        super().__init__()
        def blk(i, o, k, st): return nn.Sequential(nn.Conv1d(i, o, k, st, k // 2), nn.BatchNorm1d(o), nn.ReLU())
        s.f = nn.Sequential(blk(cin, 32, 7, 2), blk(32, 64, 5, 2), blk(64, 96, 5, 2), blk(96, 128, 5, 2), nn.AdaptiveAvgPool1d(8))
        s.h = nn.Sequential(nn.Flatten(), nn.Linear(1024, 128), nn.ReLU(), nn.Linear(128, 6))
    def forward(s, x): return s.h(s.f(x))
def main():
    Dtr, off = load(tr_names)
    # valid end idx: >= W-1 within flight, skip first 0.5s extra (hover start?) keep all
    valid = np.concatenate([np.arange(off[i] + W - 1, off[i + 1]) for i in range(len(tr_names))]); valid = torch.from_numpy(valid).to(dev)
    cin = 6 if var == 'A' else 9
    net = Net(cin).to(dev); print('params', sum(p.numel() for p in net.parameters()))
    # input scale: a ~ 9.8 on z -> subtract nothing, just scale
    sc = torch.tensor([0.1] * 3 + [0.3] * 3 + ([1.0] * 3 if var == 'B' else []), device=dev).view(1, -1, 1)
    opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4); sch = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=STEPS)
    t0 = time.time()
    for it in range(STEPS):
        idx = valid[torch.randint(len(valid), (512,), device=dev)]
        x, y = batch(Dtr, idx)
        if TGN > 0 and var == 'B':
            gx = x[:, 6:9, :] + TGN * np.pi / 180 * torch.randn(x.shape[0], 3, 1, device=dev) * (torch.rand(x.shape[0], 1, 1, device=dev) * 2); gx = gx / gx.norm(dim=1, keepdim=True)
            x = torch.cat([x[:, :6], gx], 1)
        x = x * sc
        if var == 'A':  # random yaw aug is implicit (local-yaw frame). random mirror not used
            pass
        o = net(x); mu, lv = o[:, :3], o[:, 3:].clamp(-8, 4)
        loss = (((mu - y) ** 2) / (2 * torch.exp(lv)) + lv / 2).mean() + 0.5 * (mu - y).abs().mean()
        opt.zero_grad(); loss.backward(); opt.step(); sch.step()
        if it % 1000 == 0: print(it, float(loss), 'rmse', float(((mu - y) ** 2).sum(1).mean().sqrt()), f'{time.time() - t0:.0f}s', flush=True)
    net.eval()
    Dev, offe = load(F3); out = {}
    with torch.no_grad():
        for i, n in enumerate(F3):
            z = np.load(CACHE / f'{n}.npz'); ti = z['ti']; tf = z['tf']
            js = np.arange(int(WL * 20), len(tf), 5)  # window end at frame j (every 0.25 s)
            ends = np.searchsorted(ti, tf[js] + 1e-6, side='right') - 1 + offe[i]
            # window must be [tf[j-20], tf[j]] : use IMU end idx = last sample <= tf[j], length W
            idx = torch.from_numpy(ends).to(dev)
            x, y = batch(Dev, idx)
            if GN > 0 and var == 'B':
                gx = x[:, 6:9, :].mean(2, keepdim=True) + GN * np.pi / 180 * torch.randn(x.shape[0], 3, 1, device=dev); gx = gx / gx.norm(dim=1, keepdim=True)
                x = torch.cat([x[:, :6], gx.expand(-1, -1, x.shape[2])], 1)
            o = net(x * sc)
            # displacement over IMU window ~ truth P(end)-P(end-W+1); evaluated against truth on same window
            out[n] = dict(j=js.tolist(), mu=o[:, :3].cpu().numpy().tolist(), lv=o[:, 3:].cpu().numpy().tolist(), y=y.cpu().numpy().tolist(), t=tf[js].tolist())
    json.dump(out, open(HERE / f'imuvel_pred_{var}_{WL}{SUF}.json', 'w'))
    err = np.concatenate([np.linalg.norm(np.array(v['mu']) - np.array(v['y']), axis=1) for v in out.values()])
    print('F3 window-disp error rms (m per %.2fs window): %.4f median %.4f' % (WL, np.sqrt((err ** 2).mean()), np.median(err)))
    torch.save(net.state_dict(), HERE / f'imuvel_{var}_{WL}{SUF}.pt')
if __name__ == '__main__':
    main()
