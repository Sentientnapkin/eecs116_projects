"""Per-flight start velocity in the camera frame (truth, first 2 s) for search/val flights. Output startup/heading_stats.json"""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.guard_fusion import traj as T
from viobench.tools.datasets.storage import read_episode
rows = json.load(open('research/results/single_model/startup_base/report.json'))['rows_visible']
def quat_to_R(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
out = {}
for r in rows:
    e = read_episode(T.DEFAULT_RAW / f"{r['e']}.zip", frames='none')
    gt = np.asarray(e.ground_truth); t = gt[:, 0]; p = gt[:, 1:4]
    Rb = quat_to_R(gt[0, 4:8]); Tbc = np.asarray(e.T_body_camera, float); Rbc = Tbc[:3, :3]
    m = (t >= 0.5) & (t <= 2.5)
    v = np.polyfit(t[m], p[m], 1)[0]            # mean world velocity 0.5-2.5 s
    v0 = np.polyfit(t[(t <= 1.0)], p[(t <= 1.0)], 1)[0]
    Rwc = Rb @ Rbc
    vc = Rwc.T @ v; vc0 = Rwc.T @ v0
    out[r['e']] = dict(speed=float(np.linalg.norm(v)), vc=vc.tolist(), speed0=float(np.linalg.norm(v0)), vc0=vc0.tolist(),
                       ang=float(np.degrees(np.arccos(np.clip(vc[2] / max(np.linalg.norm(vc), 1e-9), -1, 1)))))
json.dump(out, open('research/single_model/startup/heading_stats.json', 'w'))
a = np.array([[v['speed0'], v['vc0'][0], v['vc0'][1], v['vc0'][2], v['ang']] for v in out.values()])
print('n', len(a), 'mean speed0', a[:, 0].mean(), 'mean vc0 xyz', a[:, 1:4].mean(0), 'std', a[:, 1:4].std(0))
