"""Cache raw IMU (body frame), truth R_wb at IMU times, truth positions at frame times. Train list = learned run train_flights (folds 0-2, unselected); eval = fold-3 pool lc_fold3_pool (107 unselected f3).
python -B -m research.single_model.litlearn.prep_imu"""
import json, sys, numpy as np
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
RAW = Path('/data/backups/rganapa/Sebastian/gen/raw-fast/bench')
F3 = Path('/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool')
OUT = Path('/data/backups/rganapa/Sebastian/tmp/litlearn_cache'); OUT.mkdir(exist_ok=True, parents=True)
def one(a):
    name, pool = a
    o = OUT / f'{name}.npz'
    if o.exists(): return name
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.geometry import poses_to_matrices, interpolate_poses
    ep = read_episode(f'{pool}/{name}.zip', frames='none')
    gt = ep.ground_truth; imu = ep.imu; t = ep.frame_times
    Tb = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], imu[:, 0]))
    tf = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], t))
    np.savez(o, ti=imu[:, 0], a=imu[:, 1:4].astype(np.float32), w=imu[:, 4:7].astype(np.float32), R=Tb[:, :3, :3].astype(np.float32), p=Tb[:, :3, 3].astype(np.float32), tf=t, pf=tf[:, :3, 3])
    return name
if __name__ == '__main__':
    r = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learned/runs/n_nf2_r64_w1_s0/result.json'))
    tr = [(n, RAW) for n in r['train_flights']]
    ev = sorted(p.stem for p in F3.glob('*.zip'))
    jobs = tr + [(n, F3) for n in ev]
    print(len(tr), len(ev))
    with Pool(8) as p:
        for i, n in enumerate(p.imap_unordered(one, jobs)):
            if i % 50 == 0: print(i, n, flush=True)
