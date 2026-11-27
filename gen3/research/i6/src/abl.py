"""i6 input ablations (Q10): one process, data loaded once, variants trained sequentially; resumable via out/abl_<v>.json.
Common recipe (short): same conv trunk as the deployed net (16,24,32,48, hidden 128), scratch, AdamW lr 4e-3 onecycle, 25 ep x 400 x bs 256,
727 stage-3 train flights (netv2 lists/train727.txt), phases 0+2, NO old data, mirror 0.5, NO time reversal (for all variants, so seq3 is
comparable), speed x direction balanced sampling (alpha 0.5), MSE first epoch then beta-NLL (0.5). Selection-free: FINAL epoch reported.
Val = 749 v3val flights (held-out scenes), phase 0, anchors with pos>=1 (so seq3 shares the same anchor set), head K."""
import sys, json, time
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).parent))
import i6lib as L, lv4
G = Path('/data/backups/rganapa/Sebastian/gen3'); I6 = Path(__file__).resolve().parents[1]; OUT = I6 / 'out'
ORDER = ['all', 'imu_only', 'img_only', 'single_img', 'raw2', 'flow_derot', 'flow_raw', 'tracks_imu', 'seq3', 'orient_only',
         'no_intr', 'rays', 'flow_derot_noimu', 'all_s1']
EP, STEPS, BS, LR = 25, 400, 256, 4e-3


def dims(v, Dd, dev):
    g = L.starts3(Dd)[:4]
    img, pts, vec, _ = L.sample(Dd, g, v, False)
    return (img.shape[1] if img is not None else 0), (vec.shape[1] if vec is not None else 0), (pts.shape[1] if pts is not None else 0)


@torch.no_grad()
def predict(net, v, Dd, st, bs=2048):
    net.eval(); mus, lvs, ys = [], [], []
    for i in range(0, len(st), bs):
        img, pts, vec, t = L.sample(Dd, st[i:i + bs], v, False); mu, lv = net(img, pts, vec)
        mus.append(mu[:, 1]); lvs.append(lv[:, 1]); ys.append(t[:, 1])
    return torch.cat(mus), torch.cat(lvs), torch.cat(ys)


def main():
    dev = 'cuda'; torch.set_num_threads(3); t0 = time.time()
    keep = [l.strip() for l in open(G / 'agents/netv2/lists/train727.txt') if l.strip()]
    trf = [G / f'agents/net/cache/train/{n}.npz' for n in keep if (G / f'agents/net/cache/train/{n}.npz').exists()]
    vk = [l.strip() for l in open(G / 'agents/netv2/lists/val749.txt') if l.strip()]
    vaf = [G / f'agents/net/cache/val/{n}.npz' for n in sorted(vk)]
    tr = L.D(trf, dev, (0, 2), [1] * len(trf)); va = L.D(vaf, dev, (0,))
    trs, vas = L.starts3(tr), L.starts3(va)
    w = lv4.weights(tr, trs, 0.5, [0.0, 1.0])
    vm = lv4.val_meta()
    print('train flights', len(trf), 'anchors', len(trs), 'val', len(vaf), len(vas), f'load {time.time()-t0:.0f}s', flush=True)
    variants = [v for v in (sys.argv[1].split(',') if len(sys.argv) > 1 else ORDER)]
    for vn in variants:
        res_p = OUT / f'abl_{vn}.json'
        if res_p.exists(): print('skip', vn, flush=True); continue
        v = vn[:-3] if vn.endswith('_s1') else vn; seed = 1 if vn.endswith('_s1') else 0
        torch.manual_seed(seed); np.random.seed(seed)
        cin, nvec, npts = dims(v, tr, dev)
        net = L.AblNet(cin, nvec, npts).to(dev)
        params = sum(p.numel() for p in net.parameters())
        opt = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=EP * STEPS, pct_start=0.1)
        log = []; t1 = time.time()
        for ep in range(EP):
            net.train(); tl = 0
            for _ in range(STEPS):
                g = trs[torch.multinomial(w, BS, replacement=True)]
                mir = torch.rand(BS, device=dev) < 0.5
                img, pts, vec, tgt = L.sample(tr, g, v, True, mir)
                mu, lv = net(img, pts, vec)
                if ep >= 1: loss = (T_nll(mu, lv, tgt) * torch.exp(lv.detach()) ** 0.5).sum(-1).mean(-1).mean()
                else: loss = (0.5 * (mu - tgt) ** 2).sum(-1).mean()
                opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step()
                tl += loss.item()
            row = dict(epoch=ep, train=tl / STEPS)
            if ep in (4, 12) or ep == EP - 1:
                mu, lv, y = predict(net, v, va, vas); e = (mu - y).norm(dim=-1); row['val'] = float(e.mean())
            log.append(row); print(vn, json.dumps(row), f'{time.time()-t1:.0f}s', flush=True)
        mu, lv, y = predict(net, v, va, vas)
        r = lv4.report(mu, lv, y, va, vas, vm)
        sp = y.norm(dim=-1); ps = mu.norm(dim=-1); mv = sp > 0.5
        ang = torch.rad2deg(torch.acos(((mu * y).sum(-1) / (ps * sp).clamp(min=1e-9)).clamp(-1, 1)))
        r.update(speed_abs_err=float((ps - sp).abs().mean()), speed_bias=float((ps - sp).mean()), dir_err_deg_mv=float(ang[mv].mean()),
                 dir_err_deg_med_mv=float(ang[mv].median()), err_mv=float((mu - y).norm(dim=-1)[mv].mean()))
        # train subset error (generalisation gap), 40k random train anchors, no augmentation
        gi = trs[torch.randperm(len(trs), generator=torch.Generator().manual_seed(0))[:40000].to(dev)]
        mt, _, yt = predict(net, v, tr, gi); r['train_err'] = float((mt - yt).norm(dim=-1).mean())
        np.savez_compressed(OUT / f'ablpred_{vn}.npz', mu=mu.cpu().numpy().astype(np.float16), lv=lv.cpu().numpy().astype(np.float16))
        res_p.write_text(json.dumps(dict(variant=vn, inputs=L.VARIANTS[v], cin=cin, nvec=nvec, npts=npts, params=params, seed=seed,
                                         recipe=dict(ep=EP, steps=STEPS, bs=BS, lr=LR, flights=len(trf)), val=r, log=log,
                                         minutes=(time.time() - t1) / 60), indent=1))
        with open(OUT / 'abl_results.tsv', 'a') as f:
            f.write(f"{vn}\t{r['all']:.4f}\t{r['fast']:.4f}\t{r['speed_abs_err']:.4f}\t{r['dir_err_deg_mv']:.2f}\t{r['zrms']:.3f}\t{r['train_err']:.4f}\t{params}\n")
        with open(I6 / 'NOTES.md', 'a') as f:
            f.write(f"- abl {vn} ({L.VARIANTS[v]}): val err {r['all']:.4f} fast {r['fast']:.4f} speed|e| {r['speed_abs_err']:.3f} dir {r['dir_err_deg_mv']:.1f} deg train {r['train_err']:.4f} ({(time.time()-t1)/60:.0f} min)\n")
        print('DONE', vn, json.dumps(r)[:300], flush=True)
    (OUT / 'ABL_DONE').write_text('ok')


def T_nll(mu, lv, y): return 0.5 * (((y - mu) ** 2) * torch.exp(-lv) + lv)


if __name__ == '__main__':
    main()
