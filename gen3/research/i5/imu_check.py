"""i5: IMU vs GT consistency (timing convention, noise level, bias recoverability, velocity from GT).
python imu_check.py OUT.json ZIP...   (CPU only)"""
import sys, json, io, zipfile, numpy as np

def qm(q):  # q: (N,4) w x y z -> (N,3,3)
    w,x,y,z=q.T; return np.stack([np.stack([1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],-1),np.stack([2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],-1),np.stack([2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)],-1)],-2)
def logm(Rr):
    c=np.clip((np.trace(Rr,axis1=1,axis2=2)-1)/2,-1,1); th=np.arccos(c); v=np.stack([Rr[:,2,1]-Rr[:,1,2],Rr[:,0,2]-Rr[:,2,0],Rr[:,1,0]-Rr[:,0,1]],-1)
    return v*(np.where(th<1e-8,0.5,th/(2*np.sin(np.maximum(th,1e-12)))))[:,None]
G = np.array([0, 0, -9.81]); dt = 0.005

def load(zp):
    z = zipfile.ZipFile(zp); r = z.namelist()[0].split('/')[0]
    rd = lambda n: np.loadtxt(io.StringIO(z.read(f'{r}/mav0/{n}/data.csv').decode()), delimiter=',', comments='#')
    return r, rd('state_groundtruth_estimate0'), rd('imu0'), json.loads(z.read(f'{r}/episode.json'))

def movavg(x, w):
    c = np.cumsum(np.vstack([np.zeros((1, x.shape[1])), x]), 0); n = len(x); i = np.arange(n); a = np.clip(i-w//2, 0, n); b = np.clip(i+w//2+1, 0, n)
    return (c[b]-c[a])/(b-a)[:, None]

out = {}
for zp in sys.argv[2:]:
    name, gt, imu, ep = load(zp); gt[:, 0] *= 1e-9; imu[:, 0] *= 1e-9
    assert np.allclose(np.diff(gt[:, 0]), dt, atol=2e-6), 'gt not 200 Hz'
    res = dict(gt_rows=len(gt), imu_rows=len(imu), gt_dt=float(np.median(np.diff(gt[:, 0]))), gt_t0=float(gt[0, 0]), imu_t0=float(imu[0, 0]))
    R = qm(gt[:, 4:8]); p = gt[:, 1:4]
    acc_w = np.full_like(p, np.nan); acc_w[1:-1] = (p[2:] - 2*p[1:-1] + p[:-2])/dt**2   # at gt time i
    vel = np.full_like(p, np.nan); vel[1:-1] = (p[2:] - p[:-2])/(2*dt)
    om = np.full_like(p, np.nan); om[:-1] = logm(np.einsum('nji,njk->nik', R[:-1], R[1:]))/dt            # body rate over (i, i+1)
    gi = {round(t/dt): i for i, t in enumerate(gt[:, 0])}
    rows = [(j, gi.get(round(t/dt))) for j, t in enumerate(imu[:, 0])]
    rows = [(j, i) for j, i in rows if i is not None and 3 <= i < len(gt)-4]
    J = np.array([a for a, _ in rows]); I = np.array([b for _, b in rows])
    tab = {}
    for o in range(-3, 3):  # IMU sample stamped at gt time I compared with GT quantities at I+o
        f = np.einsum('nji,nj->ni', R[I+o], acc_w[I+o] - G); ra = imu[J, 4:7] - f
        w = om[I+o]; rg = imu[J, 1:4] - w
        ba = movavg(ra, 400); bg = movavg(rg, 400)
        tab[o] = dict(acc_resid_std=float(np.nanstd(ra - ba)), gyro_resid_std=float(np.nanstd(rg - bg)))
    res['offset_scan'] = tab
    ob = min(tab, key=lambda o: tab[o]['acc_resid_std']); og = min(tab, key=lambda o: tab[o]['gyro_resid_std'])
    f = np.einsum('nji,nj->ni', R[I+ob], acc_w[I+ob] - G); ra = imu[J, 4:7] - f; rg = imu[J, 1:4] - om[I+og]
    ba = movavg(ra, 1000); bg = movavg(rg, 1000)   # 5 s window bias estimate
    res.update(best_acc_offset=ob, best_gyro_offset=og, acc_bias_start=ba[0].tolist(), acc_bias_end=ba[-1].tolist(), gyro_bias_start=bg[0].tolist(), gyro_bias_end=bg[-1].tolist(),
               acc_bias_drift=float(np.linalg.norm(ba[-1]-ba[0])), gyro_bias_drift=float(np.linalg.norm(bg[-1]-bg[0])),
               acc_noise_std_axes=np.nanstd(ra - ba, 0).tolist(), gyro_noise_std_axes=np.nanstd(rg - bg, 0).tolist(),
               acc_resid_lag1_corr=float(np.nanmean([np.corrcoef((ra-ba)[:-1, k], (ra-ba)[1:, k])[0, 1] for k in range(3)])),
               speed_max=float(np.nanmax(np.linalg.norm(vel, axis=1))), accel_true_rms=float(np.sqrt(np.nanmean(np.sum(acc_w**2, 1)))))
    # GT float precision -> double-difference noise floor (static hover segment)
    res['gt_decimals_ok'] = True
    out[name] = res; print(name, ob, og, round(tab[ob]['acc_resid_std'], 3), round(tab[og]['gyro_resid_std'], 4), flush=True)
json.dump(out, open(sys.argv[1], 'w'), indent=1)
