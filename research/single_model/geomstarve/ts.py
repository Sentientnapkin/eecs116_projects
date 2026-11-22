"""ts.py RUNDIR POOL EP [bin_s]: time series of error / velocity error / live / black / rows / Pv per bin (analysis only)."""
import sys, glob, re, numpy as np
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
RUN, POOL, ep = sys.argv[1:4]; B = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
d = f'{RUN}/{ep}'; est = glob.glob(f'{d}/report/logs/*/estimate.tum')[0]; se = est.replace('estimate.tum', 'stderr.txt')
e = read_episode(f'{POOL}/{ep}.zip', frames='none'); t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); n = len(t)
E = fill_missing_states(load_estimates(est, t)); Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
err = Te[:, :3, 3] - Tg[:, :3, 3]; vt = np.gradient(S[:, :3], t, axis=0); ve = np.gradient(Te[:, :3, 3], t, axis=0)
RG = re.compile(r'G f=(\d+) live=(\d+) lo=(\d+) mean=([\d.]+) black=([\d.]+) g8=([\d.]+) g20=([\d.]+) edges=(\d+) rows=(\d+) used=(\d+)')
RD = re.compile(r'D f=(\d+) t=([\d.]+) live=(\d+) used=\d+ u20=\d+ att=(\d+) gate=(\d+) tri=(\d+) nis=([\d.]+) .* fire=(\d+) Pv=([\d.]+)')
G = np.full((n, 9), np.nan); D = np.zeros((n, 5))
for line in open(se):
    m = RG.match(line)
    if m:
        f = int(m.group(1)) - 1
        if 0 <= f < n: G[f] = [float(m.group(k)) for k in range(2, 11)]
        continue
    m = RD.match(line)
    if m:
        f = int(m.group(1)) - 1
        if 0 <= f < n: D[f] = [int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(8)), float(m.group(9))]
tt = t - t[0]
print('t    |err|  ex    ey    ez   |vt|  vexy  vez  live  lo blk  g20  edges rows att acc fire Pv')
for b0 in np.arange(0, tt[-1], B):
    m = (tt >= b0) & (tt < b0 + B); i = np.where(m)[0][-1]
    dv = (ve - vt)[m].mean(0)
    print('%4.0f %5.2f %5.2f %5.2f %5.2f %4.2f %5.2f %5.2f %4.0f %3.0f %.2f %.3f %4.0f %4.0f %3.0f %3.0f %d %.3f' % (b0, np.linalg.norm(err[i]), *err[i], np.linalg.norm(vt[m], axis=1).mean(),
          np.linalg.norm(dv[:2]), dv[2], np.nanmean(G[m, 0]), np.nanmean(G[m, 1]), np.nanmean(G[m, 3]), np.nanmean(G[m, 5]), np.nanmean(G[m, 6]), np.nansum(G[m, 7]),
          D[m, 0].sum(), (D[m, 0] - D[m, 1] - D[m, 2]).sum(), D[m, 3].sum(), D[m, 4].mean()))
