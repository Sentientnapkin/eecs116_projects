"""Build scorecard/feats.json: per-flight class features for fresh711, selected144 (non-fold-4), holdout240.
Sources (no estimator results): sidecars gen/raw-fast/bench/*.json, gen/raw-holdout/bench/*.json (audit fields),
fresh/truth_feats.json and learned_c/feats.json (start speed/angle, camera-frame, optical axis +z), and, for the holdout,
the truth velocity of the first 0.5 s read from each flight's own ground-truth csv (classification only; holdout is OUR generated set).
Fold-4 selected flights are never touched: selected flights are taken from learned_c/feats.json (folds 0-3) intersected with matrix/store/B7.json.
Run: /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B scorecard/make_feats.py"""
import json, io, zipfile, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
SM = Path(__file__).resolve().parents[1]; G = Path('/data/backups/rganapa/Sebastian/gen')

def quat_R(q):
    w, x, y, z = q.T
    R = np.empty((len(w), 3, 3))
    R[:, 0, 0] = 1-2*(y*y+z*z); R[:, 0, 1] = 2*(x*y-z*w); R[:, 0, 2] = 2*(x*z+y*w)
    R[:, 1, 0] = 2*(x*y+z*w); R[:, 1, 1] = 1-2*(x*x+z*z); R[:, 1, 2] = 2*(y*z-x*w)
    R[:, 2, 0] = 2*(x*z-y*w); R[:, 2, 1] = 2*(y*z+x*w); R[:, 2, 2] = 1-2*(x*x+y*y)
    return R

def truth_v0(zpath):
    """Camera-frame start velocity (mean over the first 0.5 s of R_wc^T d p_c/dt from the pose csv); optical axis = camera +z."""
    import yaml
    z = zipfile.ZipFile(zpath); ep = Path(zpath).stem
    rows = np.loadtxt(io.StringIO(z.read(f'{ep}/mav0/state_groundtruth_estimate0/data.csv').decode()), delimiter=',', comments='#')
    T = np.array(yaml.safe_load(z.read(f'{ep}/mav0/cam0/sensor.yaml').decode())['T_BS']['data'], float).reshape(4, 4)
    t = rows[:, 0] / 1e9; p = rows[:, 1:4]; Rb = quat_R(rows[:, 4:8]); Rc = Rb @ T[:3, :3]
    pc = p + np.einsum('nij,j->ni', Rb, T[:3, 3])
    dt = np.diff(t); vw = np.diff(pc, axis=0) / dt[:, None]; tm = 0.5 * (t[1:] + t[:-1])
    vc = np.einsum('nji,nj->ni', Rc[:-1], vw)
    m = (tm >= 0) & (tm <= 0.5 + 1e-9); v = vc[m].mean(0)
    sp = float(np.linalg.norm(v)); ang = float(np.degrees(np.arccos(np.clip(v[2] / max(sp, 1e-9), -1, 1)))) if sp > 1e-6 else None
    return ep, dict(speed0=sp, angle=ang)

def side(p):
    d = json.load(open(p)); a = d['audit']
    return dict(catalog=d['catalog'], scene=d['scene'], setting=d.get('setting'), travel=a['travel_m'], extent=a['zero_motion_ate_m'], sp_p10=a['speed_p10_p50_p90'][0],
                sp_p50=a['speed_p10_p50_p90'][1], sp_p90=a['speed_p10_p50_p90'][2], hover=a['hover_fraction'], back=a['backward_fraction'], lat=a['lateral_fraction'],
                vert=a['vertical_fraction'], turn=a['turning_fraction'], flat=a['flat_fraction'], dark=a['dark_fraction'], crop=d.get('crop_start_s'))

if __name__ == '__main__':
    S = json.load(open(SM / 'matrix/store/B7.json'))
    fr = sorted(S['fresh']); sel = sorted(S['sel'])
    tf = {r['episode']: r for r in json.load(open(SM / 'fresh/truth_feats.json'))}
    lf = json.load(open(SM / 'learned_c/feats.json'))
    out = {}
    for ep in fr:
        f = side(G / f'raw-fast/bench/{ep}.json'); f.update(set='fresh', start='mid' if ep.startswith('fastmid') else 'static', speed0=tf[ep]['speed0'], angle=tf[ep]['angle']); out[ep] = f
    for ep in sel:
        assert lf[ep]['fold'] != 4
        f = side(G / f'raw-fast/bench/{ep}.json'); f.update(set='sel', start='mid' if ep.startswith('fastmid') else 'static', speed0=lf[ep]['speed0'], angle=lf[ep]['angle']); out[ep] = f
    hold = sorted(json.load(open(SM / 'holdout/tags.json')))
    zs = [str(G / f'raw-holdout/final/{e}.zip') for e in hold]
    # validation of the csv reader on 4 fresh flights against fresh/truth_feats.json (needs the fresh pool zips)
    chk = []
    for ep in fr[:2] + [e for e in fr if e.startswith('fastmid')][:8]:
        z = f'/data/backups/rganapa/Sebastian/tmp/fresh_pool/{ep}.zip'
        _, r = truth_v0(z); chk.append((ep, r, tf[ep]['speed0'], tf[ep]['angle']))
    for c in chk: print('validate', c)
    with Pool(8) as p: res = dict(p.map(truth_v0, zs))
    for ep in hold:
        f = side(G / f'raw-holdout/bench/{ep}.json'); f.update(set='holdout', start='mid' if ep.startswith('fastmid') else 'static', **res[ep]); out[ep] = f
    json.dump(out, open(Path(__file__).parent / 'feats.json', 'w'))
    print(len(out), {s: sum(1 for v in out.values() if v['set'] == s) for s in ('fresh', 'sel', 'holdout')})
