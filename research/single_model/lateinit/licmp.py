"""Compare LI closed-form (up, velocity, position at solve time; camera-0 axes) and filter vs truth.  python licmp.py RUN pool[,pool]"""
import sys, glob, json
import numpy as np
sys.path.insert(0, '.')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
run, pools = sys.argv[1], sys.argv[2].split(',')
L = 'research/single_model/lateinit'
D = {r['episode']: r for r in json.load(open(f'{L}/diag_tc_b16r_r0_all.json'))}
out = []
for pool in pools:
    for z in sorted(glob.glob(f'{L}/pool_{pool}/*.zip')):
        ep = z.split('/')[-1][:-4]
        f = glob.glob(f'research/results/single_model/{run}/eval_{pool}/*/{ep}/report/logs/*/stderr.txt')[0]
        lines = [l for l in open(f) if l.startswith('LI ')]
        if not lines: out.append((ep, D[ep]['ate'], None)); continue
        e = read_episode(z, frames='none')
        t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); Tg = poses_to_matrices(S)
        Twc = poses_to_matrices(e.camera_poses_world()); up = Twc[0, :3, :3].T @ np.array([0, 0, 1.0])
        vg = np.einsum('nij,nj->ni', Tg[:, :3, :3], S[:, 7:10])
        for l in lines:
            kv = dict(x.split('=') for x in l.split('|')[0].split()[1:])
            nums = l.split('|')
            a = [float(x) for x in nums[1].split()[1:4] + nums[1].split()[5:8] + nums[1].split()[9:12]]
            b = [float(x) for x in nums[2].split()[1:4] + nums[2].split()[5:8] + nums[2].split()[9:12]]
            ts = float(kv['t']); k = int(np.argmin(np.abs((t - t[0]) - ts)))
            def ang(u): return np.degrees(np.arccos(np.clip(np.dot(u, up) / np.linalg.norm(u), -1, 1)))
            r = dict(ep=ep, ate=D[ep]['ate'], t=ts, ok=int(kv['ok']), gls=float(kv['gls']), sv=float(kv['sv']), sg=float(kv['sg']), used=int(kv['used']),
                     th_cf=ang(np.array(a[0:3])), th_f=ang(np.array(b[0:3])),
                     dv_cf=np.linalg.norm(np.array(a[3:6]) - vg[k]), dv_f=np.linalg.norm(np.array(b[3:6]) - vg[k]),
                     dp_cf=np.linalg.norm(np.array(a[6:9]) - Tg[k, :3, 3]), dp_f=np.linalg.norm(np.array(b[6:9]) - Tg[k, :3, 3]), sp=np.linalg.norm(vg[k]))
            out.append((ep, D[ep]['ate'], r))
print('episode ate | t ok used gls sv sg | tilt cf/filter deg | dv cf/filter | dp cf/filter | speed')
for ep, ate, r in out:
    if r is None: print(f'{ep[:34]:34s} {ate:5.2f} | (no solve)'); continue
    print(f"{ep[:34]:34s} {ate:5.2f} | {r['t']:.2f} {r['ok']} {r['used']:3d} {r['gls']:6.2f} {r['sv']:.3f} {r['sg']:5.2f} | {r['th_cf']:5.1f} {r['th_f']:5.1f} | {r['dv_cf']:5.2f} {r['dv_f']:5.2f} | {r['dp_cf']:5.2f} {r['dp_f']:5.2f} | {r['sp']:.2f}")
