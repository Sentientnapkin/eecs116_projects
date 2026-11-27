"""decomp.py EVALNAME [POOL=v3val] -> per-flight error decomposition of an existing eval run (no re-run).
Counterfactual oracles on the estimated trajectory (body-frame displacement increments re-integrated):
  ate      : unaligned RMS position error (camera0 frame, as the harness)
  ate_rot  : increments rotated with GT orientation instead of the estimate (perfect rotation)
  ate_yaw  : only the yaw (twist about gravity) error removed
  yaw_end, yaw_rms, tilt_rms : deg
Writes research/r5/evals/decomp_EVALNAME.json and prints class means."""
import sys, json, glob, zipfile, io, numpy as np, collections as C
G = '/data/backups/rganapa/Sebastian/gen3'
name = sys.argv[1]; pool = sys.argv[2] if len(sys.argv) > 2 else 'v3val'
ev = {r['id']: r for r in json.load(open(f'{G}/evals/{name}__{pool}.json'))}

def q2R(q):  # x y z w
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def rotvec(Rm):
    c = np.clip((np.trace(Rm)-1)/2, -1, 1); a = np.arccos(c)
    if a < 1e-9: return np.zeros(3)
    return a/(2*np.sin(a))*np.array([Rm[2,1]-Rm[1,2], Rm[0,2]-Rm[2,0], Rm[1,0]-Rm[0,1]])

def axrot(u, a):
    K = np.array([[0,-u[2],u[1]],[u[2],0,-u[0]],[-u[1],u[0],0]])
    return np.eye(3)+np.sin(a)*K+(1-np.cos(a))*K@K

out = []
for fid, r in ev.items():
    if r['ate'] is None: continue
    est = glob.glob(f'{G}/evals/{name}/{pool}/*/{fid}/report/logs/*/estimate.tum')
    if not est: continue
    E = np.loadtxt(est[0], comments='#')
    z = zipfile.ZipFile(f'{G}/pools/{pool}/{fid}.zip')
    T = np.loadtxt(io.StringIO(z.read(f'{fid}/mav0/state_groundtruth_estimate0/data.csv').decode()), delimiter=',', comments='#')
    ep = json.loads(z.read(f'{fid}/episode.json')); org = int(ep.get('origin_ns', 0))
    Tbc = np.array(ep['config']['imu']['T_imu_cam'], float).reshape(4, 4); Rbc = Tbc[:3, :3]; tbc = Tbc[:3, 3]
    tg = (T[:, 0]-org)*1e-9
    Pb = np.column_stack([np.interp(E[:, 0], tg, T[:, 1+i]) for i in range(3)])
    idx = np.clip(np.searchsorted(tg, E[:, 0]), 1, len(tg)-1); idx -= (E[:, 0]-tg[idx-1]) < (tg[idx]-E[:, 0])
    Rb = np.array([q2R([q[1], q[2], q[3], q[0]]) for q in T[idx, 4:8]])  # file: qw first
    Rg = Rb@Rbc; Pg = Pb+Rb@tbc
    R0 = Rg[0]; Pc = (Pg-Pg[0])@R0  # = R0^T (p - p0)
    Rc = np.einsum('ji,njk->nik', R0, Rg)
    Pe = E[:, 1:4]; Re = np.array([q2R(q) for q in E[:, 4:8]])
    n = len(E)
    ate = np.sqrt(np.mean(np.sum((Pe-Pc)**2, 1)))
    gdir = R0.T@np.array([0, 0, -1.0])  # gravity in cam0 frame
    yaw = np.zeros(n); tilt = np.zeros(n)
    po_r = np.zeros_like(Pe); po_y = np.zeros_like(Pe)
    for k in range(n):
        dR = Rc[k]@Re[k].T  # world(c0) correction: Rc = dR Re
        v = rotvec(dR); yaw[k] = v@gdir; tilt[k] = np.linalg.norm(v-yaw[k]*gdir)
        if k:
            db = Re[k-1].T@(Pe[k]-Pe[k-1])
            po_r[k] = po_r[k-1]+Rc[k-1]@db
            po_y[k] = po_y[k-1]+axrot(gdir, yaw[k-1])@Re[k-1]@db
    # speed oracle: per 10-frame window, scale estimated increments so the window's path length equals GT's (direction kept)
    po_s = np.zeros_like(Pe); W = 10
    dE = np.diff(Pe, axis=0); dG = np.diff(Pc, axis=0)
    for a in range(0, n-1, W):
        le = np.linalg.norm(dE[a:a+W], axis=1).sum(); lg = np.linalg.norm(dG[a:a+W], axis=1).sum()
        sc = lg/le if le > 1e-6 else 1.0
        for k in range(a, min(a+W, n-1)): po_s[k+1] = po_s[k]+sc*dE[k]
    a_s = np.sqrt(np.mean(np.sum((po_s-Pc)**2, 1)))
    a_r = np.sqrt(np.mean(np.sum((po_r-Pc)**2, 1))); a_y = np.sqrt(np.mean(np.sum((po_y-Pc)**2, 1)))
    out.append(dict(id=fid, cls=r['setting_class'], start=r['start'], ate=ate, ate_h=r['ate'], ate_rot=a_r, ate_spd=a_s, ate_yaw=a_y,
                    yaw_end=float(np.degrees(abs(yaw[-1]))), yaw_rms=float(np.degrees(np.sqrt(np.mean(yaw**2)))),
                    tilt_rms=float(np.degrees(np.sqrt(np.mean(tilt**2)))), path=float(np.sum(np.linalg.norm(np.diff(Pc, axis=0), axis=1)))))
json.dump(out, open(f'{G}/research/r5/evals/decomp_{name}.json', 'w'))
D = C.defaultdict(list)
for o in out: D['all'].append(o); D[o['cls']].append(o)
for k, v in D.items():
    m = lambda f: np.mean([o[f] for o in v])
    print(f"{k:10s} n={len(v):3d} ate {m('ate'):.3f} (harness {m('ate_h'):.3f}) oracle-rot {m('ate_rot'):.3f} oracle-yaw {m('ate_yaw'):.3f} oracle-speed {m('ate_spd'):.3f} | yaw_end {m('yaw_end'):.2f} yaw_rms {m('yaw_rms'):.2f} tilt_rms {m('tilt_rms'):.2f} deg path {m('path'):.1f}")
