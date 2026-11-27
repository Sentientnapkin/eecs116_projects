"""tilt.py EVALNAME POOLDIR : tilt error (deg) per frame from SG debug lines vs GT (ep.ground_truth body poses, world z up)."""
import sys, glob, json
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import quaternion_to_matrix
G = Path('/data/backups/rganapa/Sebastian/gen3'); name, pool = sys.argv[1], Path(sys.argv[2])
F = (0, 5, 10, 13, 15, 20, 30, 40, 60, 100, 150, 199); out = []
for d in sorted(glob.glob(str(G / 'evals' / name / pool.name / '*' / '*' / 'report/logs/*/stderr.txt'))):
    fid = [p for p in Path(d).parts if p.startswith('s3')][0]
    ep = read_episode(pool / (fid + '.zip'), frames='none'); gt = np.asarray(ep.ground_truth); t = ep.frame_times
    sg = {}
    for l in open(d):
        if l.startswith('SG '): f = l.split(); sg[int(f[1])] = np.array([float(x) for x in f[2:5]])
    row = []
    for k in F:
        if k not in sg: row.append(np.nan); continue
        j = np.argmin(np.abs(gt[:, 0] - t[k])); Rw = quaternion_to_matrix(gt[j, 4:8]); up = Rw.T @ np.array([0, 0, 1.0])
        row.append(np.degrees(np.arccos(np.clip(up @ sg[k] / np.linalg.norm(sg[k]), -1, 1))))
    out.append(row)
A = np.array(out); print(name, 'n', len(A)); print('frame ', ' '.join(f'{k:6d}' for k in F)); print('mean  ', ' '.join(f'{x:6.2f}' for x in np.nanmean(A, 0))); print('p90   ', ' '.join(f'{x:6.2f}' for x in np.nanpercentile(A, 90, 0)))
