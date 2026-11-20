"""Truth/IMU loader for simulator-structure tests. Pool = gen/raw-fast/bench (our own generated flights); fold-4 scenes skipped."""
import sys, json, glob, hashlib, random
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
RAW = Path('/data/backups/rganapa/Sebastian/gen/raw-fast/bench')
def fold(cat, scene): return int(hashlib.sha256((cat + ':' + scene).encode()).hexdigest()[:8], 16) % 5
def roster(kind, n, seed=0):
    out = []
    for f in sorted(RAW.glob('*.json')):
        d = json.load(open(f))
        if fold(d['catalog'], d['scene']) == 4: continue
        if (d.get('crop_start_s') is not None) != (kind == 'mid'): continue
        out.append(d)
    random.Random(seed).shuffle(out)
    return out[:n]
def q2R(q):  # xyzw -> (n,3,3)
    x, y, z, w = q.T
    return np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), 2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], 1).reshape(-1, 3, 3)
def load(d):
    e = read_episode(RAW / d['file'], frames='none')
    return e
def rotvec_rel(R0, R1):
    """log(R0^T R1) for stacks (n,3,3)."""
    M = np.einsum('nji,njk->nik', R0, R1)
    c = np.clip((np.trace(M, axis1=1, axis2=2) - 1) / 2, -1, 1); th = np.arccos(c)
    v = np.stack([M[:, 2, 1] - M[:, 1, 2], M[:, 0, 2] - M[:, 2, 0], M[:, 1, 0] - M[:, 0, 1]], 1) / 2
    s = np.sinc(th / np.pi)  # sin(th)/th
    return v / np.where(s < 1e-9, 1, s)[:, None]
