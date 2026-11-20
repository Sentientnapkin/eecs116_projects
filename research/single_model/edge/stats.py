"""Per-flight truth statistics for pool flights (truth used for classification only). Writes edge/flightstats.json.
Excludes fold-4 scenes entirely."""
import json, hashlib, sys, glob
from pathlib import Path
import numpy as np
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects')
from research.guard_fusion.traj import load_truth
from research.single_model.run_variant import tags, fold
RAW = '/data/backups/rganapa/Sebastian/gen/raw-fast/selected'
BENCH = '/data/backups/rganapa/Sebastian/tmp/fresh_pool'
def quat_to_R(q):
    x,y,z,w = q.T; n=np.sqrt(x*x+y*y+z*z+w*w); x,y,z,w=x/n,y/n,z/n,w/n
    R=np.empty((len(x),3,3))
    R[:,0,0]=1-2*(y*y+z*z);R[:,0,1]=2*(x*y-z*w);R[:,0,2]=2*(x*z+y*w)
    R[:,1,0]=2*(x*y+z*w);R[:,1,1]=1-2*(x*x+z*z);R[:,1,2]=2*(y*z-x*w)
    R[:,2,0]=2*(x*z-y*w);R[:,2,1]=2*(y*z+x*w);R[:,2,2]=1-2*(x*x+y*y)
    return R
def stats(raw, ep):
    t, gt, meta = load_truth(raw, ep)
    p = gt[:, :3]; q = gt[:, 3:7]; vb = gt[:, 7:10]; w = gt[:, 10:13]
    R = quat_to_R(q); vw = np.einsum('nij,nj->ni', R, vb)
    dt = np.diff(t)
    dist = float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))
    rms0 = float(np.sqrt(np.mean(np.sum((p - p[0])**2, 1))))
    sp = np.linalg.norm(vb, axis=1)
    n05 = t <= t[0] + 0.45
    v0 = vb[n05].mean(0); s0 = float(np.linalg.norm(v0))
    ang0 = float(np.degrees(np.arccos(np.clip(v0[0] / max(s0, 1e-9), -1, 1)))) if s0 > 0.2 else float('nan')  # off camera axis (+x body)
    # yaw rate (world z) and tilt
    wz = np.einsum('nij,nj->ni', R, w)[:, 2]
    zax = R[:, :, 2]  # body z in world
    tilt = np.degrees(np.arccos(np.clip(zax[:, 2], -1, 1)))
    # total rotation angle between consecutive frames
    rot = np.linalg.norm(w, axis=1)
    # tilt at start, vertical velocity share
    vz_share = float(np.mean(np.abs(vw[:, 2]) / np.maximum(np.linalg.norm(vw, axis=1), 1e-3)))
    return dict(dist=dist, rms0=rms0, v0=s0, ang0=ang0, speed_mean=float(sp.mean()), speed_max=float(sp.max()),
                speed_p95=float(np.percentile(sp, 95)), yawrate_max=float(np.degrees(np.abs(wz).max())),
                yawrate_rms=float(np.degrees(np.sqrt(np.mean(wz**2)))), tilt_max=float(tilt.max()), tilt0=float(tilt[:5].mean()),
                rotrate_rms=float(np.degrees(np.sqrt(np.mean(rot**2)))), vz_share=vz_share, dur=float(t[-1]-t[0]),
                acc_rms=float(np.sqrt(np.mean(np.sum((np.diff(vw,axis=0)/dt[:,None])**2,1)))),
                meta={k: meta.get(k) for k in ('camera','intrinsics','fx','imu') if k in meta})
if __name__ == '__main__':
    out = {}
    tg = tags()
    for ep in sorted(p.stem for p in Path(RAW).glob('*.zip')):
        t = tg[ep]; f = fold(t)
        if f == 4: continue
        s = stats(RAW, ep); s.update(pool='sel', fold=f, start=t['start'], scene=t['scene'], catalog=t['catalog']); out[ep] = s
    ft = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/fresh/tags.json'))
    for ep, t in sorted(ft.items()):
        f = int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5
        if f == 4: continue
        try: s = stats(BENCH, ep)
        except Exception as e: print('skip', ep, e); continue
        s.update(pool='fresh', fold=f, start=t['start'], scene=t['scene'], catalog=t['catalog']); out[ep] = s
    json.dump(out, open('research/single_model/edge/flightstats.json', 'w'))
    print(len(out))
