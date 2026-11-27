"""dbgview.py EVALDIR POOL FLIGHT [maxf]: SD debug lines joined with GT velocity (world) and est vel error"""
import sys, re
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.geometry import quaternion_to_matrix
ev, pool, fid = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]; mx = int(sys.argv[4]) if len(sys.argv) > 4 else 60
d = sorted(ev.glob(f'**/{fid}/report/logs/*/estimate.tum'))[0]
ep = read_episode(pool / (fid + '.zip'), frames='none'); gt = ep.ground_truth_state(); est = load_estimates(d, ep.frame_times)
log = (d.parent / 'stderr.txt').read_text().splitlines()
sd = {}
for l in log:
    if l.startswith('SD '):
        f = l.split(); sd[int(f[1])] = l
    elif l.startswith('LC'): print(l)
for k in range(0, mx):
    e = est[k]; g = gt[k]
    print(k, 'gtv %5.2f %5.2f %5.2f' % tuple(g[7:10]), 'estv %5.2f %5.2f %5.2f' % tuple(e[7:10]), 'verr %.2f perr %.2f' % (np.linalg.norm(e[7:10] - g[7:10]), np.linalg.norm(e[:3] - g[:3])), 'tilt %.1f' % np.degrees(np.arccos(np.clip((quaternion_to_matrix(e[3:7]) @ quaternion_to_matrix(g[3:7]).T)[2,2],-1,1))), 'gta %.2f %.2f %.2f' % tuple((gt[k+1,7:10]-gt[max(k-1,0),7:10])/((ep.frame_times[k+1]-ep.frame_times[max(k-1,0)]))),
          '|', ' '.join(sd.get(k, '').split()[9:]) )
