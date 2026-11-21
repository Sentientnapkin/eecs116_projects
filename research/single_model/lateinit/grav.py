"""Gravity (tilt) error of the filter's camera-0 frame vs truth over time, from LI_LOG 'G' lines.  python grav.py RUN POOL"""
import sys, glob, json
import numpy as np
sys.path.insert(0, '.')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
run, pool = sys.argv[1:3]
L = 'research/single_model/lateinit'
D = {r['episode']: r for r in json.load(open(f'{L}/diag_tc_b16r_r0_all.json'))}
rows = []
for z in sorted(glob.glob(f'{L}/pool_{pool}/*.zip')):
    ep = z.split('/')[-1][:-4]
    e = read_episode(z, frames='none')
    Twc = poses_to_matrices(e.camera_poses_world()); up = Twc[0, :3, :3].T @ np.array([0, 0, 1.0])
    f = glob.glob(f'research/results/single_model/{run}/eval_{pool}/*/{ep}/report/logs/*/stderr.txt')[0]
    G = np.array([[float(x) for x in l.split()[1:5]] for l in open(f) if l.startswith('G ')])
    ang = np.degrees(np.arccos(np.clip(G[:, 1:4] @ up, -1, 1)))
    def at(s): return ang[min(np.searchsorted(G[:, 0], s), len(ang) - 1)]
    d = D.get(ep, {})
    rows.append((ep, d.get('ate', np.nan), d.get('start', '?'), at(0.05), at(0.5), at(1.0), at(1.5), at(2), at(3), at(5), at(10), at(30), at(59)))
rows.sort(key=lambda r: -r[1])
print('episode ate start | tilt-err deg at 0.05 0.5 1 1.5 2 3 5 10 30 59')
for r in rows: print(f'{r[0][:34]:34s} {r[1]:5.2f} {r[2][:2]} | ' + ' '.join(f'{x:5.1f}' for x in r[3:]))
a = np.array([r[3:] for r in rows]); print('median', ' '.join(f'{x:5.1f}' for x in np.median(a, 0)))
