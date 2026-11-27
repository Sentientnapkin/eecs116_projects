import sys, json, glob
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
G = Path('/data/backups/rganapa/Sebastian/gen3'); I2 = G / 'research/i2'
meta = {r['id']: r for r in json.load(open(G / 'evals/sw_a1_Ze0__v3val.json'))}
dbg = {r['id']: r for r in json.load(open(G / 'evals/i2_dbg__v3val.json'))}
HZ = [0.25, 0.5, 1, 2, 5, 10, 20, 40, 'end']
rows = []; S = {}
for f in sorted((I2 / 'cache_t').glob('*.npz')):
    fid = f.stem; z = np.load(f, allow_pickle=True); t = z['t']; E = z['E']; n = len(t); up = z['up']; Eu = E @ up
    if fid not in dbg: continue
    r = dict(id=fid, ate=float(np.sqrt(np.mean((E ** 2).sum(1)))), n=n, dur=float(t[-1]))
    pg = z['pg']; pgu = pg @ up; r['path'] = float(np.linalg.norm(np.diff(pg, axis=0), axis=1).sum())
    r['ate_h'] = float(np.sqrt(np.mean(((E - Eu[:, None] * up) ** 2).sum(1)))); r['ate_v'] = float(np.sqrt(np.mean(Eu ** 2)))
    r['gt_zstd'] = float(pgu.std()); r['gt_zrange'] = float(np.ptp(pgu))
    vgw = np.gradient(pg, t, axis=0); r['v0z'] = float(vgw[2] @ up); r['spd0'] = float(np.linalg.norm(vgw[2])); r['vz_rms'] = float(np.sqrt(np.mean((vgw @ up) ** 2)))
    r['spd_mean'] = float(np.linalg.norm(vgw, axis=1).mean())
    acc = np.gradient(vgw, t, axis=0); r['acc_rms'] = float(np.sqrt(np.mean((acc ** 2).sum(1))))
    for h in HZ:
        k = n - 1 if h == 'end' else int(np.searchsorted(t, h))
        if k >= n: continue
        r[f'pos_{h}'] = float(np.linalg.norm(E[k])); r[f'posh_{h}'] = float(np.linalg.norm(E[k] - Eu[k] * up)); r[f'posz_{h}'] = float(Eu[k])
        r[f'vel_{h}'] = float(np.linalg.norm(z['dv'][k])); r[f'tilt_{h}'] = float(z['tilt'][k]); r[f'yaw_{h}'] = float(np.degrees(z['yaw'][k]))
        r[f'bg_{h}'] = float(np.linalg.norm(z['bge'][k])); r[f'ba_{h}'] = float(np.linalg.norm(z['bae'][k]))
        r[f'baz_{h}'] = float(z['bae'][k, 2])
    # growth law: log-log slope of |E|(t) over 2..end using median-smoothed
    m = t > 2; tt = t[m]; ee = np.linalg.norm(E[m], axis=1) + 1e-3
    r['slope'] = float(np.polyfit(np.log(tt), np.log(ee), 1)[0])
    # RPE over 1 s and 5 s windows (translation error of relative motion), plus drift-ratio
    for w, nm in ((1.0, 'rpe1'), (5.0, 'rpe5')):
        k = int(round(w * (n - 1) / t[-1])); d = E[k:] - E[:-k]; r[nm] = float(np.sqrt(np.mean((d ** 2).sum(1))))
        dg = pg[k:] - pg[:-k]; r[nm + '_rel'] = float(np.mean(np.linalg.norm(d, axis=1)) / max(np.mean(np.linalg.norm(dg, axis=1)), 1e-6))
    # scale: LS scale s of (pe-pe0) vs (pg-pg0); and path-length ratio
    pe = z['pe']; a = pe - pe[0]; b = pg - pg[0]
    r['scale'] = float((a * b).sum() / (b * b).sum()); r['plen_ratio'] = float(np.linalg.norm(np.diff(pe, axis=0), axis=1).sum() / max(r['path'], 1e-6))
    # speed error: est speed / gt speed over time via vel error vs gt speed
    vg = z['vg']; dv = z['dv']; sg = np.linalg.norm(vg, axis=1)
    r['spd_err_rms'] = float(np.sqrt(np.mean((np.linalg.norm(vg + dv, axis=1) - sg) ** 2)))
    r['vel_err_rms'] = float(np.sqrt(np.mean((dv ** 2).sum(1))))
    # vel error autocorrelation time (1/e) on |dv| components
    d = dv - dv.mean(0); ac = [(d[:-L] * d[L:]).sum() / (d * d).sum() for L in (5, 10, 20, 40, 80, 160)]
    r['vac'] = [float(x) for x in ac]
    # vertical-motion: vertical vel err
    r['dvz_rms'] = float(np.sqrt(np.mean(dv[:, 2] ** 2))) if False else None
    # tilt/vertical coupling: tilt err mean after 2 s; ba_z err mean after 2 s; corr(E_z, tilt)
    m2 = t > 2
    r['tilt_mean2'] = float(np.nanmean(z['tilt'][m2])); r['baz_abs2'] = float(np.nanmean(np.linalg.norm(z['bae'][m2], axis=1)))
    r['Ez_end'] = float(Eu[-1]); r['Ez_mean'] = float(Eu.mean()); r['Ez_std'] = float(Eu.std())
    # vertical error type: fit offset + linear drift + residual (oscillation) ; compare E_z to -gt vertical motion
    A = np.vander(t, 2); c = np.linalg.lstsq(A, Eu, rcond=None)[0]; res = Eu - A @ c
    r['Ez_drift_rate'] = float(c[0]); r['Ez_off'] = float(c[1]); r['Ez_res_rms'] = float(res.std())
    zg = pgu - pgu[0]; ze = pe @ up - (pe[0] @ up)
    r['vert_gain'] = float((zg * ze).sum() / max((zg * zg).sum(), 1e-9)) if zg.std() > 0.05 else None  # est vertical motion / true
    r['zest_std'] = float((pe @ up).std())
    # horizontal ratio of err
    r['pos_start_share_1'] = r.get('pos_1', np.nan)
    r['live_mean'] = float(np.nanmean(z['trk'][:, 0]))
    r['live_lt5'] = float(np.nanmean(z['trk'][:, 0] < 5))
    # internal tilt err in vertical; yaw drift end
    ep = read_episode(G / 'pools/v3val' / (fid + '.zip'), frames='none')
    imu = ep.imu; r['gyro_rms'] = float(np.sqrt(np.mean((imu[:, 4:7] ** 2).sum(1)))); r['accel_hf'] = float(np.sqrt(np.mean(np.diff(imu[:, 1:4], axis=0) ** 2)))
    m_ = meta[fid]; r.update({k: m_[k] for k in ('setting_class', 'regime', 'start', 'start_fwd_speed', 'fov_deg', 'exposure_s', 'motion_style')})
    r['peak'] = m_['peak']; r['ate_ref'] = m_['ate']
    rows.append(r)
    S[fid] = dict(t=t, E=E)
json.dump(rows, open(I2 / 'perflight_summary.json', 'w'))
print(len(rows), 'flights; mean ATE dbg', np.mean([r['ate'] for r in rows]))
