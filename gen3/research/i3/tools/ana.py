import json, glob, re, sys, numpy as np
from pathlib import Path
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
P = Path('/data/backups/rganapa/Sebastian/gen3/research/i3')
D = {Path(f).stem: json.load(open(f)) for f in glob.glob(str(P / 'ana/*.json'))}
base = D['v_b0']['flights']; ks = sorted(base)
def scene(k):
    s = base[k]['scene'] or ''
    return 'rooms' if re.match(r'(proc|room|house|ProcTHOR)', s, re.I) else 'warehouse' if 'ware' in s.lower() else 'forest' if 'forest' in s.lower() else 'other'
sc = {k: scene(k) for k in ks}
rng = np.random.default_rng(0); idx = rng.integers(0, len(ks), (2000, len(ks)))
def ates(n): return np.array([D[n]['flights'][k]['ate'] if D[n]['flights'][k]['ate'] is not None else np.nan for k in ks])
b = ates('v_b0')
def row(n):
    a = ates(n); ok = ~np.isnan(a); d = np.where(ok, a - b, np.nan)
    dd = np.nan_to_num(d); bs = dd[idx].mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
    r = dict(n=n, mean=np.nanmean(a), d=np.nanmean(d), lo=lo, hi=hi, med=np.nanmedian(a), fail=int((~ok).sum() + (a[ok] > 3).sum()),
             peak=max((v['peak'] or 0) for v in D[n]['flights'].values()))
    for s in ('rooms', 'warehouse', 'forest'):
        m = np.array([sc[k] == s for k in ks]); r[s] = np.nanmean(a[m]); r['d_' + s] = np.nanmean(d[m])
    return r
R = {n: row(n) for n in D if n != 'v_b0'}
print('scene counts', {s: sum(v == s for v in sc.values()) for s in set(sc.values())}, 'base mean %.3f' % np.nanmean(b))
hdr = '| name | mean | d vs base [95% CI] | median | rooms d | wareh d | forest d | fail(>3m) | peak (M) |\n|---|---|---|---|---|---|---|---|---|\n'
def md(names):
    return hdr + ''.join('| %s | %.3f | %+.3f [%+.3f,%+.3f] | %.3f | %+.3f | %+.3f | %+.3f | %d | %.2f |\n' % (n, R[n]['mean'], R[n]['d'], R[n]['lo'], R[n]['hi'], R[n]['med'], R['%s' % n]['d_rooms'], R[n]['d_warehouse'], R[n]['d_forest'], R[n]['fail'], R[n]['peak'] / 1e6) for n in names if n in R)
out = ''
for pre in ('rep', 'q3', 'q4', 'q12'):
    names = sorted([n for n in R if n.startswith(pre)])
    out += '\n### %s\n' % pre + md(names)
open(P / 'ana/tables.md', 'w').write(out); json.dump(R, open(P / 'ana/R.json', 'w'), default=float)
# curves
def curve(fig, title, series, xlabel, fn, log=True):
    plt.figure(figsize=(6, 4))
    for lab, pts in series.items():
        pts = [(x, R[n]['mean'], R[n]['lo'] + np.nanmean(b), R[n]['hi'] + np.nanmean(b)) for x, n in pts if n in R]
        if not pts: continue
        x, y, lo, hi = map(np.array, zip(*pts)); plt.plot(x, y, 'o-', label=lab); plt.fill_between(x, lo, hi, alpha=.15)
    plt.axhline(np.nanmean(b), color='k', ls='--', lw=1, label='baseline %.3f' % np.nanmean(b))
    if log: plt.xscale('log')
    plt.xlabel(xlabel); plt.ylabel('mean ATE (m), n=120'); plt.title(title); plt.legend(fontsize=7); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(P / 'plots' / fn, dpi=130); plt.close()
g = lambda pre, vals: [(v, '%s_%g' % (pre, v)) for v in vals]
curve(0, 'Velocity accuracy (every 0.5 s)', {'white': g('q4_vel', (0.05, 0.1, 0.2, 0.5, 1.0)), 'correlated': g('q4_velcorr', (0.05, 0.2, 0.5)), 'bias': g('q4_velbias', (0.05, 0.2, 0.5)), 'outliers': g('q4_velout', (0.05, 0.2))}, 'assumed/actual sd (m/s)', 'vel_accuracy.png')
curve(0, 'Metric depth accuracy (per feature)', {'white': g('q4_dep', (0.02, 0.05, 0.1, 0.2, 0.4)), 'bias': g('q4_depbias', (0.1, 0.2))}, 'relative depth sd', 'depth_accuracy.png')
curve(0, 'Gravity direction accuracy (every frame)', {'all frames': g('q4_grav', (0.1, 0.3, 1, 2, 5)), 'init only': g('q4_gravinit', (0.5, 2))}, 'sd (deg)', 'gravity_accuracy.png')
curve(0, 'Perfect-correspondence pixel noise', {'cor': g('q4_cor', (0.1, 0.25, 0.5, 1.0, 2.0))}, 'pixel sd', 'corr_accuracy.png')
curve(0, 'Clone-relative translation (every 0.5 s)', {'rel err': g('q4_rt', (0.01, 0.03, 0.1, 0.2))}, 'relative sd', 'reltrans_accuracy.png')
curve(0, 'Vertical displacement / altitude', {'dz 0.5 s': g('q4_dz', (0.02, 0.05, 0.1, 0.25, 0.5)), 'alt vs origin': g('q4_alt', (0.02, 0.1, 0.5)), 'vz': g('q4_vz', (0.05, 0.2))}, 'sd (m or m/s)', 'vertical_accuracy.png')
curve(0, 'Velocity frequency (sd 0.1)', {'freq': [(v, 'q4_velfreq_%d' % v) for v in (1, 2, 5, 10, 20, 40)]}, 'frames between updates', 'vel_frequency.png')
curve(0, 'Velocity latency (sd 0.1, every 10 fr, compensated)', {'lat': [(v + .5, 'q4_vellat_%d' % v) for v in (1, 2, 4, 8, 16)]}, 'latency frames (+0.5 offset)', 'vel_latency.png')
# consistency
names = ['v_or0'] + [n for n in ('q3_vel_05s', 'q3_all') if n in D]
lab = 'NEES_v NEES_p NEES_tilt3(th) NEES_bg NEES_ba ntilt'.split()
cons = '\n### consistency (mean over flights, frames>=20; NEES chi2 dof=3 -> expected 3)\n| run | V | P | TH(body) | BG | BA | tilt(dof2) | speed rmse | speed rms-sigma | pos rmse | pos rms-sigma | yaw rmse | yaw sigma |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n'
for n in names:
    O = np.array([v['ors'] for v in D[n]['flights'].values() if v['ors']])
    m = np.nanmean(O, 0); med = np.nanmedian(O, 0)
    cons += '| %s mean | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.3f | %.3f | %.2f | %.2f | %.3f | %.3f |\n' % (n, *m[:6], np.sqrt(m[6]), np.sqrt(m[7]), np.sqrt(m[8]), np.sqrt(m[9]), np.sqrt(m[12]), np.sqrt(m[13]))
    cons += '| %s median | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f |||||||\n' % (n, *med[:6])
open(P / 'ana/tables.md', 'a').write(cons); print(out + cons)
