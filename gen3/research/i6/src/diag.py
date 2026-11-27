"""i6 Q10 diagnostics (inference only, GPU 5): direct error decomposition of the deployed / candidate velocity nets on val749 (phase 0,
held-out scenes), conditional calibration, train-vs-val gap, and 'speed-only net + geometric direction' hybrids.
out/diag.json, out/pred_<model>.npz"""
import sys, json, time, glob
from pathlib import Path
from argparse import Namespace
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).parent))
import i6lib as L, lv4, lv5
G = Path('/data/backups/rganapa/Sebastian/gen3'); OUT = Path(__file__).resolve().parents[1] / 'out'
torch.set_num_threads(3); dev = 'cuda'
MODELS = {'A160ft': G / 'agents/netv2/runs/A160ft', 'B240': G / 'agents/netv2/runs/B240', 'X80': G / 'agents/netv2/runs/X80',
          'auto_727': G / 'agents/net/runs/auto_727', 'A2_kd': G / 'agents/smallnet/runs/A2_kd'}


def load(name):
    R = MODELS[name]; cfg = json.loads((R / 'result.json').read_text())
    if name == 'A2_kd':
        c = cfg['cfg']; net = lv5.SNet(c)
    else:
        a = dict(chs='16,24,32,48', deep=0, hidden=128); a.update(cfg['args']); net = lv4.make_net(Namespace(**a)); c = None
    net.load_state_dict(torch.load(R / 'best.pt', map_location='cpu', weights_only=True)); net = net.to(dev).eval()
    params = sum(p.numel() for p in net.parameters())
    return net, c, params, cfg


@torch.no_grad()
def predict(net, c, Dd, st, bs=4096):
    mus, lvs, ys = [], [], []
    for i in range(0, len(st), bs):
        g = st[i:i + bs]
        img, vec, t = (lv5.build_any(Dd, g, False, None, c) if c else lv4.build(Dd, g, False))
        mu, lv = net(img, vec); mus.append(mu[:, 1]); lvs.append(lv[:, 1]); ys.append(t[:, 1])
    return [torch.cat(x).cpu().numpy() for x in (mus, lvs, ys)]


def stats(mu, lv, y, up, sel):
    mu, lv, y, up = mu[sel], lv[sel], y[sel], up[sel]
    e = mu - y; en = np.linalg.norm(e, axis=1); sp = np.linalg.norm(y, axis=1); ps = np.linalg.norm(mu, axis=1)
    mv = sp > 0.5
    ang = np.degrees(np.arccos(np.clip((mu * y).sum(1) / np.maximum(ps * sp, 1e-9), -1, 1)))
    ev = (e * up).sum(1); eh = np.linalg.norm(e - ev[:, None] * up, axis=1)
    z = e / np.exp(0.5 * lv)
    sig = np.sqrt(np.exp(lv).sum(1))
    # perfect-speed / perfect-direction oracles (moving only)
    dir_only = np.linalg.norm(sp[:, None] * mu / np.maximum(ps, 1e-9)[:, None] - y, axis=1)   # true speed, net direction
    spd_only = np.linalg.norm(ps[:, None] * y / np.maximum(sp, 1e-9)[:, None] - y, axis=1)    # net speed, true direction
    r = dict(n=int(sel.sum()), err=float(en.mean()), rmse=float(np.sqrt((en ** 2).mean())), p90=float(np.percentile(en, 90)),
             speed_abs_err=float(np.abs(ps - sp).mean()), speed_bias=float((ps - sp).mean()),
             speed_ratio_mv=float(np.median(ps[mv] / sp[mv])) if mv.any() else None,
             dir_err_deg_mean_mv=float(ang[mv].mean()) if mv.any() else None, dir_err_deg_med_mv=float(np.median(ang[mv])) if mv.any() else None,
             vert_abs=float(np.abs(ev).mean()), horiz=float(eh.mean()), vert_bias=float(ev.mean()),
             bias_xyz=e.mean(0).round(4).tolist(), zrms_xyz=np.sqrt((z ** 2).mean(0)).round(3).tolist(),
             cov1=float((np.abs(z) < 1).mean()), cov2=float((np.abs(z) < 2).mean()),
             err_if_true_speed_mv=float(dir_only[mv].mean()) if mv.any() else None, err_if_true_dir_mv=float(spd_only[mv].mean()) if mv.any() else None,
             err_mv=float(en[mv].mean()) if mv.any() else None)
    q = np.quantile(sig, [0, .2, .4, .6, .8, 1.0]); rel = []
    for i in range(5):
        m = (sig >= q[i]) & (sig <= q[i + 1]); rel.append([round(float(np.sqrt((sig[m] ** 2).mean())), 3), round(float(np.sqrt((en[m] ** 2).mean())), 3)])
    r['reliability_sigma_vs_rmse_quintiles'] = rel
    return r


def groups(names, meta, fid):
    def binf(key, fn):
        lab = np.array([str(fn(meta.get(n, {}))) for n in names]); return lab[fid]
    g = {}
    g['class'] = binf('c', lambda m: m.get('setting_class'))
    g['blur'] = binf('b', lambda m: None if m.get('exposure_s') in (None, '') else ('<15ms' if float(m['exposure_s']) < .015 else '15-35' if float(m['exposure_s']) < .035 else '>35ms'))
    g['fov'] = binf('f', lambda m: None if m.get('fov_deg') in (None, '') else ('<95' if float(m['fov_deg']) < 95 else '95-115' if float(m['fov_deg']) < 115 else '>115'))
    g['start'] = binf('s', lambda m: m.get('start'))
    g['motion'] = binf('m', lambda m: m.get('motion_style'))
    g['scene'] = binf('sc', lambda m: m.get('scene'))
    return g


def main():
    t0 = time.time(); out = {}
    vm = lv4.val_meta()
    vk = [l.strip() for l in open(G / 'agents/netv2/lists/val749.txt') if l.strip()]
    vfiles = [G / f'agents/net/cache/val/{n}.npz' for n in sorted(vk)]
    va = L.D(vfiles, dev, (0,)); st = va.starts()
    fid = va.fid[st].cpu().numpy(); stc = st
    up = (va.f[st + 1] / va.f[st + 1].norm(dim=-1, keepdim=True)).cpu().numpy()   # approx gravity-up in body b (specific force direction)
    gyr = va.g[st + 1].norm(dim=-1).cpu().numpy()
    gr = groups(va.names, vm, fid)
    print('val anchors', len(st), f'{time.time()-t0:.0f}s', flush=True)
    preds = {}
    for name in MODELS:
        net, c, params, cfg = load(name)
        mu, lv, y = predict(net, c, va, st); preds[name] = (mu, lv, y)
        np.savez_compressed(OUT / f'pred_{name}.npz', mu=mu.astype(np.float32), lv=lv.astype(np.float32), y=y.astype(np.float32), fid=fid)
        sp = np.linalg.norm(y, axis=1); al = np.ones(len(y), bool)
        r = dict(params=params, all=stats(mu, lv, y, up, al))
        r['speed_bins'] = {k: stats(mu, lv, y, up, m) for k, m in [('<0.3', sp < .3), ('0.3-1', (sp >= .3) & (sp < 1)), ('1-1.5', (sp >= 1) & (sp < 1.5)), ('1.5-2.5', (sp >= 1.5) & (sp < 2.5)), ('>2.5', sp >= 2.5)]}
        r['gyro_bins'] = {k: stats(mu, lv, y, up, m) for k, m in [('<0.3', gyr < .3), ('0.3-1', (gyr >= .3) & (gyr < 1)), ('>1', gyr >= 1)]}
        for gk in ('class', 'blur', 'fov', 'start', 'motion'):
            r[gk] = {k: stats(mu, lv, y, up, gr[gk] == k) for k in sorted(set(gr[gk]))}
        sc = gr['scene']; per = {k: float(np.linalg.norm(mu - y, axis=1)[sc == k].mean()) for k in sorted(set(sc))}
        r['scene_err'] = dict(n=len(per), min=min(per.values()), max=max(per.values()), sd=float(np.std(list(per.values()))), per=per)
        out[name] = r; print(name, json.dumps(r['all'])[:400], flush=True)
        (OUT / 'diag.json').write_text(json.dumps(out, indent=1))
    # train-vs-val gap for A160ft (150 of its own training flights, phase 0)
    cfg = json.loads((MODELS['A160ft'] / 'result.json').read_text()); tn = [n for n in cfg['new_names'] if (G / f'agents/net/cache/train/{n}.npz').exists()]
    rng = np.random.default_rng(0); tn = [tn[i] for i in sorted(rng.permutation(len(tn))[:150])]
    tr = L.D([G / f'agents/net/cache/train/{n}.npz' for n in tn], dev, (0,)); tst = tr.starts()
    upt = (tr.f[tst + 1] / tr.f[tst + 1].norm(dim=-1, keepdim=True)).cpu().numpy()
    for name in ('A160ft', 'B240', 'auto_727'):
        net, c, _, _ = load(name); mu, lv, y = predict(net, c, tr, tst)
        out[name]['train150'] = stats(mu, lv, y, upt, np.ones(len(y), bool))
    print('train gap', out['A160ft']['train150']['err'], out['A160ft']['all']['err'], flush=True)
    del tr
    # geometric direction from derotated LK flow vs net direction; hybrids
    tb, q, par = [], [], []
    with torch.no_grad():
        for i in range(0, len(st), 2048):
            g = st[i:i + 2048]; t_, q_, p_ = L.trans_dir(va, g, g + 1); tb.append(t_); q.append(q_); par.append(p_)
    tb, q, par = [torch.cat(x).cpu().numpy() for x in (tb, q, par)]
    np.savez_compressed(OUT / 'geodir_val.npz', t=tb.astype(np.float32), q=q.astype(np.float32), par=par.astype(np.float32))
    mu, lv, y = preds['A160ft']; sp = np.linalg.norm(y, axis=1); ps = np.linalg.norm(mu, axis=1)
    tg = tb * np.sign((tb * mu).sum(1, keepdims=True) + 1e-12)
    yd = y / np.maximum(sp, 1e-9)[:, None]; md = mu / np.maximum(ps, 1e-9)[:, None]
    ang = lambda u, v: np.degrees(np.arccos(np.clip((u * v).sum(1), -1, 1)))
    hyb = ps[:, None] * tg
    geo = {}
    for nm, m in [('mv>0.5', sp > .5), ('fast>1.5', sp > 1.5)]:
        ql = q[m] < np.quantile(q[m], 0.5)
        geo[nm] = dict(n=int(m.sum()), net_dir_deg=float(ang(md[m], yd[m]).mean()), geo_dir_deg=float(ang(tg[m], yd[m]).mean()),
                       geo_dir_deg_med=float(np.median(ang(tg[m], yd[m]))), net_dir_deg_med=float(np.median(ang(md[m], yd[m]))),
                       geo_dir_deg_bestq50=float(ang(tg[m], yd[m])[ql].mean()), net_dir_deg_bestq50=float(ang(md[m], yd[m])[ql].mean()),
                       err_net=float(np.linalg.norm(mu[m] - y[m], axis=1).mean()), err_hybrid=float(np.linalg.norm(hyb[m] - y[m], axis=1).mean()),
                       err_true_speed_geo_dir=float(np.linalg.norm(sp[m, None] * tg[m] - y[m], axis=1).mean()),
                       err_net_speed_true_dir=float(np.linalg.norm(ps[m, None] * yd[m] - y[m], axis=1).mean()),
                       median_parallax_px=float(np.median(par[m])))
        for th in (5., 10., 20.):  # gated hybrid: use geometric direction only if it agrees with the net within th deg (cheap outlier gate)
            ok = ang(tg[m], md[m]) < th; h = np.where(ok[:, None], hyb[m], mu[m])
            geo[nm][f'err_hybrid_gate{int(th)}'] = float(np.linalg.norm(h - y[m], axis=1).mean()); geo[nm][f'gate{int(th)}_frac'] = float(ok.mean())
    out['geodir'] = geo; print('geodir', json.dumps(geo), flush=True)
    (OUT / 'diag.json').write_text(json.dumps(out, indent=1)); print('DIAG DONE', f'{time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
