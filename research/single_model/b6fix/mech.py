"""Per-flight mechanism analysis from diag stderr + estimate.tum + truth.
usage: python mech.py <fresh_run_dir_or_selected_run_dir> out.json   (run dir = results/single_model/<name>/eval/*)"""
import sys, json, glob, re, os
sys.path.insert(0, '.')
import numpy as np
from research.guard_fusion import traj as T
POOLS = ['/data/backups/rganapa/Sebastian/tmp/fresh_pool', '/data/backups/rganapa/Sebastian/gen/raw-fast/selected']

def quat_ang(q1, q2):
    d = np.abs(np.sum(q1 * q2, 1)).clip(0, 1)
    return np.degrees(2 * np.arccos(d))

def parse(path):
    rows = []
    for ln in open(path, errors='replace'):
        if not ln.startswith('D '): continue
        kv = {}
        for tok in ln[2:].split():
            k, v = tok.split('=')
            kv[k] = [float(x) for x in v.split(',')] if ',' in v else float(v)
        rows.append(kv)
    return rows

def analyse(ep, rundir):
    base = glob.glob(f'{rundir}/{ep}/report/logs/*/')[0]
    tum = np.loadtxt(base + 'estimate.tum')
    rows = parse(base + 'stderr.txt')
    pool = next(p for p in POOLS if os.path.exists(f'{p}/{ep}.zip'))
    t, s, meta = T.load_truth(pool, ep)
    te = tum[:, 0]
    idx = np.searchsorted(t, te).clip(0, len(t) - 1)
    pt = s[idx, 0:3]; err = np.linalg.norm(tum[:, 1:4] - pt, axis=1)
    rot = quat_ang(tum[:, 4:8], s[idx, 3:7])
    tt = te - te[0]
    on = np.where(err > 3.0)[0]
    onset = float(tt[on[0]]) if len(on) else None
    # path lengths
    pe = np.sum(np.linalg.norm(np.diff(tum[:, 1:4], axis=0), axis=1)); pg = np.sum(np.linalg.norm(np.diff(pt, axis=0), axis=1))
    sp_true = np.linalg.norm(s[idx, 7:10], axis=1)
    v = np.array([r['v'] for r in rows]); sp_est = np.linalg.norm(v, axis=1)
    n = min(len(rows), len(tt) - 1)
    def col(k): return np.array([r[k] for r in rows])
    live, live3, used, fbc, fbd, kf, tri, gate, att = (col(k) for k in ('live', 'live3', 'used', 'fbc', 'fbd', 'kf', 'tri', 'gate', 'att'))
    Pv = col('Pv')
    out = dict(ep=ep, ate=float(np.mean(err)), onset=onset, err2=float(err[tt > 2][0]), err5=float(err[tt > 5][0]), err10=float(err[tt > 10][0]),
               rot_max=float(rot.max()), rot5=float(rot[tt > 5][0]), rot_at_onset=float(rot[on[0]]) if len(on) else None,
               path_ratio=float(pe / max(pg, 1e-6)), true_path=float(pg),
               live_med=float(np.median(live)), live_min10=float(np.percentile(live, 10)), live3_med=float(np.median(live3)),
               used_mean=float(used.mean()), fb_drop_frac=float(fbd.sum() / max(fbc.sum(), 1)), klt_fail_per_frame=float(kf.mean()),
               tri_frac=float(tri.sum() / max(att.sum(), 1)), gate_frac=float(gate.sum() / max(att.sum(), 1)),
               sp_true0=float(sp_true[:10].mean()), spratio2=float(sp_est[min(40, len(sp_est) - 1)] / max(sp_true[tt > 2][0], 0.05)),
               ratio_max_speed=float(sp_est.max()), true_speed_max=float(sp_true.max()), Pv_max=float(Pv.max()))
    # windows before onset (or whole flight if none)
    f_on = int(on[0]) if len(on) else n
    lo = max(0, f_on - 100)
    sl = slice(lo, max(f_on, lo + 1))
    out.update(w_live=float(live[sl].mean()), w_live3=float(live3[sl].mean()), w_used=float(used[sl].mean()),
               w_zero_used_frac=float((used[sl] == 0).mean()), w_fbd=float(fbd[sl].sum() / max(fbc[sl].sum(), 1)),
               w_spratio=float(sp_est[sl].mean() / max(sp_true[idx[:1]].mean() * 0 + np.linalg.norm(s[idx, 7:10], axis=1)[lo:f_on + 1].mean(), 0.05)),
               first_used=int(np.argmax(used > 0)) if (used > 0).any() else -1,
               flat=None)
    out['mov'] = int(col('mov')[5]); out['rel'] = int(col('rel')[-1])
    return out

if __name__ == '__main__':
    rundir = glob.glob(sys.argv[1])[0]
    eps = sys.argv[3].split(',') if len(sys.argv) > 3 else sorted(os.path.basename(p) for p in glob.glob(rundir + '/*') if os.path.isdir(p))
    from multiprocessing import Pool
    with Pool(8) as p:
        res = p.starmap(analyse, [(e, rundir) for e in eps])
    json.dump(res, open(sys.argv[2], 'w'))
