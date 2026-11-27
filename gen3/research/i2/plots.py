import json, numpy as np
from pathlib import Path
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
I2 = Path('/data/backups/rganapa/Sebastian/gen3/research/i2'); R = json.load(open(I2/'perflight_summary.json'))
A = lambda k: np.array([np.nan if r.get(k) is None else r[k] for r in R], float)
ids = [r['id'] for r in R]; ate = A('ate')
# growth curves
T = np.array([.5,1,2,5,10,20,40,59]); Z = {}
cols = {'pos':[], 'vel':[], 'tilt':[]}
for r in R:
    z = np.load(I2/'cache_t'/(r['id']+'.npz'), allow_pickle=True); t = z['t']; up = z['up']; E = z['E']; Eu = E@up
    for nm, v in (('pos', np.linalg.norm(E,axis=1)), ('posh', np.linalg.norm(E-Eu[:,None]*up,axis=1)), ('posv', np.abs(Eu)), ('vel', np.linalg.norm(z['dv'],axis=1)), ('tilt', z['tilt'])):
        Z.setdefault(nm, []).append(np.interp(T, t, np.nan_to_num(v, nan=0)))
fig, ax = plt.subplots(1, 3, figsize=(14, 4))
for nm, a, lab in (('pos', ax[0], 'position error (m)'), ('vel', ax[1], 'velocity error (m/s)'), ('tilt', ax[2], 'gravity/tilt error (deg)')):
    X = np.array(Z[nm]); a.plot(T, np.median(X,0), 'o-', label='median'); a.plot(T, X.mean(0), 's--', label='mean'); a.fill_between(T, np.percentile(X,25,0), np.percentile(X,75,0), alpha=.25, label='IQR'); a.set_xscale('log'); a.set_yscale('log'); a.set_xlabel('time (s)'); a.set_title(lab); a.grid(alpha=.3)
ax[0].plot(T, np.median(np.array(Z['posh']),0), 'k:', label='horizontal median'); ax[0].plot(T, np.median(np.array(Z['posv']),0), 'r:', label='vertical median'); ax[0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(I2/'plots/error_vs_time.png', dpi=110); plt.close()
# good / median / poor flights
o = np.argsort(ate); pick = [o[int(n)] for n in (len(o)*0.05, len(o)*0.5, len(o)*0.95)]
fig, ax = plt.subplots(3, 3, figsize=(14, 9))
for i, k in enumerate(pick):
    z = np.load(I2/'cache_t'/(ids[k]+'.npz'), allow_pickle=True); t = z['t']; up = z['up']; E = z['E']; Eu = E@up; Eh = E-Eu[:,None]*up
    ax[i,0].plot(t, np.linalg.norm(Eh,axis=1), label='horizontal'); ax[i,0].plot(t, Eu, label='vertical (signed)'); ax[i,0].set_title(f"{ids[k]} ATE {ate[k]:.2f}"); ax[i,0].legend(fontsize=7); ax[i,0].set_xlabel('t (s)'); ax[i,0].set_ylabel('pos err (m)')
    ax[i,1].plot(t, np.linalg.norm(z['dv'],axis=1)); ax[i,1].set_ylabel('|vel err| m/s'); ax[i,1].set_ylim(0, 1.5); ax[i,1].set_xlabel('t (s)')
    b = ax[i,1].twinx(); b.plot(t, z['tilt'], 'r', alpha=.6); b.set_ylabel('tilt deg', color='r'); b.set_ylim(0, 10)
    ax[i,2].plot(z['pg'][:,0], z['pg'][:,1], label='GT'); ax[i,2].plot(z['pe'][:,0], z['pe'][:,1], label='est'); ax[i,2].set_aspect('equal'); ax[i,2].legend(fontsize=7); ax[i,2].set_title('top-down c0 x/y axes (not gravity-aligned)', fontsize=8)
plt.tight_layout(); plt.savefig(I2/'plots/good_median_poor.png', dpi=100); plt.close()
# scatter
fig, ax = plt.subplots(1, 4, figsize=(16, 3.8))
for a, k, l in zip(ax, ('path','gyro_rms','rpe5','gt_zstd'), ('GT path length (m)','gyro RMS (rad/s)','RPE over 5 s (m)','GT vertical std (m)')):
    x = A(k); c = {'room':'C0','warehouse':'C1','forest':'C2'}; a.scatter(x, ate, s=6, c=[c[r['setting_class']] for r in R]); a.set_xlabel(l); a.set_ylabel('ATE (m)'); a.grid(alpha=.3)
plt.tight_layout(); plt.savefig(I2/'plots/ate_scatter.png', dpi=100); plt.close()
# h vs v
fig, ax = plt.subplots(1, 2, figsize=(9, 3.8)); ax[0].scatter(A('ate_h'), A('ate_v'), s=6); ax[0].plot([0,1.5],[0,1.5],'k:'); ax[0].set_xlabel('horizontal RMS err'); ax[0].set_ylabel('vertical RMS err')
ax[1].hist([A('ate_h'), A('ate_v')], bins=30, label=['horizontal','vertical']); ax[1].legend(); ax[1].set_xlabel('RMS error (m)')
plt.tight_layout(); plt.savefig(I2/'plots/horiz_vs_vert.png', dpi=100); plt.close()
# velocity autocorr + growth exponent hist
fig, ax = plt.subplots(1, 2, figsize=(9, 3.8)); ax[0].hist(A('slope'), 30); ax[0].set_xlabel('log-log slope of |pos err| vs t (t>2 s)'); ax[1].hist(A('plen_ratio'), 30); ax[1].set_xlabel('est path length / GT path length')
plt.tight_layout(); plt.savefig(I2/'plots/growth_scale.png', dpi=100); plt.close()
