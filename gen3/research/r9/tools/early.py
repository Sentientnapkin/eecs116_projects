"""early.py EVALNAME POOL [out.json]: per flight ATE, early errors, and 'what-if' ATEs:
 ate_fixK = ATE if the estimate's error state (pos offset + velocity error) at frame K were zeroed by a rigid shift of the
 remaining trajectory (pos only), i.e. sensitivity of ATE to the start window.  Uses cached eval outputs."""
import sys, json, glob
from pathlib import Path
from multiprocessing import Pool
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.geometry import quaternion_to_matrix
G = Path('/data/backups/rganapa/Sebastian/gen3')
name, pool = sys.argv[1], sys.argv[2]
meta = {r['id']: r for r in json.load(open(G / 'evals' / f'{name}__{pool}.json'))}
def one(d):
    fid = [p for p in Path(d).parts if p.startswith('s3')][0]
    z = G / 'pools' / pool / (fid + '.zip')
    if not z.exists(): return None
    ep = read_episode(z, frames='none'); gt = ep.ground_truth_state(); est = load_estimates(Path(d), ep.frame_times)
    e = est[:, :3] - gt[:, :3]; n = len(e)
    ate = float(np.sqrt(np.mean(np.sum(e ** 2, 1))))
    r = {'id': fid, 'ate': ate, 'n': n}
    for k in (5, 10, 20, 40, 60, 100):
        k2 = min(k, n - 1)
        r[f'p{k}'] = float(np.linalg.norm(e[k2])); r[f'v{k}'] = float(np.linalg.norm(est[k2, 7:10] - gt[k2, 7:10]))
        Re = quaternion_to_matrix(est[k2, 3:7]); Rg = quaternion_to_matrix(gt[k2, 3:7])
        dR = Re @ Rg.T  # world-frame rotation error
        r[f'yaw{k}'] = float(np.degrees(np.arctan2(dR[1, 0], dR[0, 0])))
        r[f'tilt{k}'] = float(np.degrees(np.arccos(np.clip(dR[2, 2], -1, 1))))
        r[f'spd{k}'] = [float(np.linalg.norm(est[k2, 7:10])), float(np.linalg.norm(gt[k2, 7:10]))]
    # what-if: subtract the error growth of the first K frames extrapolated? simple: remove position+velocity error at K
    t = ep.frame_times - ep.frame_times[0]
    for k in (10, 20, 40, 60):
        dv = est[k, 7:10] - gt[k, 7:10]
        corr = e.copy(); corr[k:] -= e[k] + np.outer(t[k:] - t[k], dv) * 0  # pos offset only
        r[f'ate_fixp{k}'] = float(np.sqrt(np.mean(np.sum(corr ** 2, 1))))
    # tail share: error in first 3 s vs rest
    k3 = min(60, n)
    r['rms_first3'] = float(np.sqrt(np.mean(np.sum(e[:k3] ** 2, 1))))
    m = meta.get(fid, {}); r.update({k: m.get(k) for k in ('setting_class', 'start', 'start_fwd_speed', 'regime', 'fov_deg', 'exposure_s')})
    return r
if __name__ == '__main__':
    ds = sorted(glob.glob(str(G / 'evals' / name / pool / '*' / '*' / 'report/logs/*/estimate.tum')))
    with Pool(8) as p: R = [x for x in p.map(one, ds) if x]
    out = sys.argv[3] if len(sys.argv) > 3 else f'/data/backups/rganapa/Sebastian/gen3/agents/startup/ana/{name}__{pool}.json'
    Path(out).parent.mkdir(exist_ok=True); json.dump(R, open(out, 'w'))
    print(len(R), 'flights ->', out)
