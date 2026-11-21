"""learned_c training v3: pools fast+speed+new (generated), hard-example-aware sampling, per-bin calibration, scaling-curve subsets.
  CUDA_VISIBLE_DEVICES=1 python -B train3.py --name x --max_new 400 --epochs 60 --lr 3e-3 --alpha 0.5 --hard 0.3
Strict split as before: roles train (fold 0-2) / val (fold 3); fold 4 never read; holdout scenes are not in the new pool."""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'learned'))
import train as T, train2, split2
from train2 import Data2, bin_weights, val_report, ABINS, SBINS
OUT = HERE / 'runs'

class Data3(Data2):
    def __init__(self, roles, dev, pools, phases, max_new=None, new_rounds=None):
        orig = split2.load_rows
        def patched():
            rows = orig(); new = [r for r in rows if r['pool'] == 'new' and (new_rounds is None or r.get('round') in new_rounds)]
            if max_new is not None: new = new[:max_new]
            return [r for r in rows if r['pool'] != 'new'] + new
        split2.load_rows = patched
        try: super().__init__(roles, dev, pools, phases)
        finally: split2.load_rows = orig

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--res', type=int, default=64); ap.add_argument('--width', type=float, default=1.0)
    ap.add_argument('--seed', type=int, default=0); ap.add_argument('--epochs', type=int, default=60); ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--lr', type=float, default=3e-3); ap.add_argument('--steps_per_epoch', type=int, default=400)
    ap.add_argument('--alpha', type=float, default=0.5); ap.add_argument('--hard', type=float, default=0.0, help='fraction of each batch drawn proportionally to the per-anchor loss EMA')
    ap.add_argument('--pools', default='fast,speed,new'); ap.add_argument('--phases', default='0,2'); ap.add_argument('--max_new', type=int, default=None)
    ap.add_argument('--new_rounds', default=''); ap.add_argument('--dump_hard', type=int, default=0)
    a = ap.parse_args()
    dev = 'cuda'; torch.manual_seed(a.seed); np.random.seed(a.seed)
    out = OUT / a.name; out.mkdir(parents=True, exist_ok=True)
    pools = tuple(a.pools.split(',')); phases = tuple(int(x) for x in a.phases.split(','))
    tr = Data3(['train'], dev, pools, phases, a.max_new, set(a.new_rounds.split(',')) if a.new_rounds else None)
    va = train2.Data2(['val'], dev, ('fast', 'speed'), (0,))
    nf, gap = 2, 1; trs, vas = tr.valid_starts(nf, gap), va.valid_starts(nf, gap)
    w = bin_weights(tr, a.alpha, trs); ema = torch.ones(len(trs), device=dev)
    print(a.name, 'train flights', len(tr.rows), 'anchors', len(trs), 'val flights', len(va.rows), 'anchors', len(vas), flush=True)
    net = T.Net(a.res, a.width, nf, 19).to(dev); params, macs = T.count(net, nf, 19, a.res); print('params', params, 'MACs', macs, flush=True)
    if a.res != 128: pass
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * a.steps_per_epoch, pct_start=0.1)
    best = (1e9, None); log = []; t0 = time.time(); nh = int(a.bs * a.hard)
    for ep in range(a.epochs):
        net.train(); tl = 0
        for _ in range(a.steps_per_epoch):
            ix = torch.multinomial(w, a.bs - nh, replacement=True)
            if nh: ix = torch.cat([ix, torch.multinomial(ema * w, nh, replacement=True)])
            g = trs[ix]
            img, vec, tgt, _ = T.build_batch(tr, g, nf, gap, a.res, True)
            fl = torch.rand(a.bs, device=dev) < 0.5
            if fl.any():
                i2, v2, t2 = T.flip(img[fl], vec[fl], tgt[fl], nf)
                img = img.clone(); vec = vec.clone(); tgt = tgt.clone(); img[fl], vec[fl], tgt[fl] = i2, v2, t2
            mu, lv = net(img, vec)
            lvec = T.nll(mu, lv, tgt).sum(-1).mean(-1) if ep >= 1 else (0.5 * (mu - tgt) ** 2).sum(-1).mean(-1)
            loss = lvec.mean() * 3 / 3
            opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step()
            if a.hard:
                e = (mu.detach() - tgt).norm(dim=-1).mean(-1); ema[ix] = 0.7 * ema[ix] + 0.3 * e.clamp(min=0.02) / e.mean().clamp(min=1e-3) if ep >= 1 else ema[ix]
            tl += loss.item()
        mu, lv, y = T.predict(net, va, vas, nf, gap, a.res); rep = val_report(mu, lv, y, va, vas)
        crit = float(np.mean([(rep[k]['err0'] + rep[k]['errK']) / 2 for k in rep if k.startswith('ang') and rep[k]]))
        log.append(dict(epoch=ep, train=tl / a.steps_per_epoch, val_all0=rep['all']['err0'], val_balanced=crit))
        if ep % 5 == 0 or ep == a.epochs - 1: print(f"ep {ep} train {tl/a.steps_per_epoch:.3f} val all {rep['all']['err0']:.3f}/{rep['all']['errK']:.3f} balanced {crit:.3f} ({time.time()-t0:.0f}s)", flush=True)
        if ep >= 3 and crit < best[0]: best = (crit, ep); torch.save(net.state_dict(), out / 'best.pt')
    net.load_state_dict(torch.load(out / 'best.pt'))
    mu, lv, y = T.predict(net, va, vas, nf, gap, a.res); rep = val_report(mu, lv, y, va, vas)
    zK = (mu[:, 1] - y[:, 1]) / torch.exp(0.5 * lv[:, 1])
    sb = va.sbin[vas]; scale_bins = [float(zK[sb == i].pow(2).mean().sqrt()) if (sb == i).any() else 1.0 for i in range(4)]
    res = dict(args=vars(a), params=params, macs=macs, best_epoch=best[1], best_crit=best[0], val=rep, sigma_scale_headK=float(zK.pow(2).mean().sqrt()), sigma_scale_by_speedbin=scale_bins, log=log,
               n_train_flights=len(tr.rows), n_train_anchors=int(len(trs)), train_flights=[r['name'] for r in tr.rows])
    # hard-example report on the TRAINING distribution (no augmentation): error by speed bin x angle bin x scene
    mu_t, lv_t, y_t = T.predict(net, tr, trs, nf, gap, a.res)
    e = (mu_t[:, 1] - y_t[:, 1]).norm(dim=-1).cpu().numpy(); sb_t = tr.sbin[trs].cpu().numpy(); ab_t = tr.abin[trs].cpu().numpy(); fid = tr.fid[trs].cpu().numpy()
    cells = {f's{s}a{a_}': dict(n=int(((sb_t == s) & (ab_t == a_)).sum()), err=float(e[(sb_t == s) & (ab_t == a_)].mean())) for s in range(4) for a_ in range(-1, 5) if ((sb_t == s) & (ab_t == a_)).sum() > 20}
    scene_err = {}
    for i, r in enumerate(tr.rows):
        m = fid == i
        if m.any(): scene_err.setdefault(f"{r['catalog']}|{r['scene']}", []).append(float(e[m].mean()))
    res['train_cells'] = cells; res['train_scene_err'] = {k: float(np.mean(v)) for k, v in scene_err.items()}
    res['train_err_all'] = float(e.mean())
    json.dump(res, open(out / 'result.json', 'w'), indent=1)
    print('DONE', a.name, 'best_ep', best[1], 'val all', json.dumps(rep['all']), 'train err %.3f' % e.mean(), flush=True)

if __name__ == '__main__':
    main()
