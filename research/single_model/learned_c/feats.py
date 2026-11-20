"""Start speed / angle between true start velocity (mean body-frame truth velocity over the first 0.5 s) and the camera axis, for fold 0-3 flights of
the 171 selected (never fold 4) and the 107 unselected fold-3 flights. Output feats.json {episode: {...}}."""
import json, sys, os
from multiprocessing import Pool
from pathlib import Path
import numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, '/dev/shm/sebastian-vio/viobench'); sys.path.insert(0, 'research/single_model/learned_c')
from research.guard_fusion import traj as T
import split2
def one(args):
    d, ep, scene, catalog, fold, sel = args
    t, s, meta = T.load_truth(d, ep)
    from viobench.tools.datasets.storage import read_episode
    e = read_episode(f'{d}/{ep}.zip', frames='none')
    axis = np.array([0.0, 0.0, 1.0])  # load_truth states are camera-frame (fresh/NOTES CORRECTION): optical axis = +z
    n = int(np.sum(t - t[0] <= 0.5 + 1e-9)); v = s[:n, 7:10].mean(0); sp = float(np.linalg.norm(v))
    ang = float(np.degrees(np.arccos(np.clip(v @ axis / max(sp, 1e-9), -1, 1)))) if sp > 1e-6 else None
    return ep, dict(speed0=sp, angle=ang, scene=scene, catalog=catalog, fold=fold, selected=sel, start='mid' if ep.startswith('fastmid') else 'static')
if __name__ == '__main__':
    rows = [r for r in split2.load_rows() if r['pool'] == 'fast' and r['fold'] != 4 and (r['selected'] or r['role'] == 'val')]
    SEL = '/data/backups/rganapa/Sebastian/gen/raw-fast/selected'
    jobs = [((SEL if r['selected'] else '/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool'), r['name'], r['scene'], r['catalog'], r['fold'], r['selected']) for r in rows]
    with Pool(12) as p: res = dict(p.map(one, jobs))
    json.dump(res, open('research/single_model/learned_c/feats.json', 'w')); print(len(res))
