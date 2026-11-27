"""Frontend diagnostics for one flight from the instrumented C tracker (AUD_TRK/AUD_STATS stderr) + GT.
python fe_ana.py ZIP STDERR OUT.json [width=320]"""
import sys, json, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from flight import Flight, c_tracks, triangulate

def rot_angle(R): return np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))

def expm(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-12: return np.eye(3) + K
    return np.eye(3) + np.sin(th)/th*K + (1-np.cos(th))/th**2*K@K

def main(zp, se, outp, W=320):
    F = Flight(zp); fx, fy, cx, cy = F.K(W); H = W*3//4
    tr, S = c_tracks(se)
    nf = len(F.fr_t)
    o = dict(id=F.meta['id'], cls=F.meta['setting_class'], start=F.meta['start'], exposure=F.exposure, fov=F.fov, regime=F.meta['regime'])
    L = np.array([len(v) for v in tr.values()])
    o['n_tracks'] = int(len(L)); o['life_mean'] = float(L.mean())
    o['surv'] = {k: float((L >= k).mean()) for k in (2, 5, 10, 20, 40, 80)}
    live = np.zeros(nf); cov = np.zeros(nf)
    occ = np.zeros((nf, 4, 3), bool)
    for v in tr.values():
        f = v[:, 0].astype(int); live[f] += 1
        occ[f, np.clip((v[:, 1] / W * 4).astype(int), 0, 3), np.clip((v[:, 2] / H * 3).astype(int), 0, 2)] = True
    o['live_mean'] = float(live.mean()); o['live_p10'] = float(np.percentile(live, 10)); o['frac_frames_lt10'] = float((live < 10).mean())
    o['coverage12'] = float(occ.reshape(nf, -1).mean())
    # GT-triangulated reprojection residuals
    rms = []; allr = []; bias = []; depth = []; par = []; age_res = [[] for _ in range(6)]
    for k, v in tr.items():
        if len(v) < 5: continue
        idx = np.linspace(0, len(v)-1, min(len(v), 30)).round().astype(int); v = v[idx]
        f = v[:, 0].astype(int)
        if f.max() >= nf: continue
        Rs = [F.frame_pose(i)[0] for i in f]; ps = [F.frame_pose(i)[1] for i in f]
        uv = np.c_[(v[:, 1]-cx)/fx, (v[:, 2]-cy)/fy]
        X, r = triangulate(Rs, ps, uv)
        if X is None: continue
        rp = r * fx; rr = np.sqrt((rp**2).sum(1))
        rms.append(np.sqrt((rr**2).mean())); allr.append(rr); bias.append(rp.mean(0))
        depth.append((Rs[0].T @ (X - ps[0]))[2])
        a = X - ps[0]; b = X - ps[-1]; par.append(np.degrees(np.arccos(np.clip(a@b/np.linalg.norm(a)/np.linalg.norm(b), -1, 1))))
        ages = f - f[0]
        for j, (ag, e) in enumerate(zip(ages, rr)):
            age_res[min(5, np.searchsorted([5, 10, 20, 40, 80], ag, 'right'))].append(e)
    rms = np.array(rms); allr = np.concatenate(allr) if allr else np.zeros(1)
    o['n_tri'] = int(len(rms)); o['reproj_track_rms_med'] = float(np.median(rms)); o['reproj_obs_med'] = float(np.median(allr))
    o['reproj_obs_rms_clip3'] = float(np.sqrt((np.minimum(allr, 3)**2).mean())); o['frac_tracks_rms_gt2px'] = float((rms > 2).mean())
    o['frac_tracks_rms_gt1px'] = float((rms > 1).mean()); o['frac_tracks_rms_lt05px'] = float((rms < .5).mean())
    o['reproj_bias_xy'] = np.median(np.array(bias), 0).tolist()
    o['reproj_by_age'] = [float(np.median(a)) if a else None for a in age_res]  # age bins <5,<10,<20,<40,<80,>=80 frames
    depth = np.array(depth); par = np.array(par)
    o['depth_pct'] = np.percentile(depth, [10, 50, 90]).tolist(); o['frac_depth_gt10'] = float((depth > 10).mean())
    o['parallax_deg_pct'] = np.percentile(par, [10, 50, 90]).tolist(); o['frac_par_lt1deg'] = float((par < 1).mean())
    # rotation: gyro-integrated vs GT relative camera rotation per frame
    e_raw = []; e_px = []; gb_est = []
    Rci = F.R_ci
    rel = []
    for k in range(nf - 1):
        t0, t1 = F.fr_t[k], F.fr_t[k+1]
        m = (F.imu_t >= t0) & (F.imu_t < t1)
        Rb = np.eye(3)
        for w in F.gyr[m]: Rb = Rb @ expm(w * 0.005)
        Rc_meas = Rci @ Rb @ Rci.T
        Rgt = F.frame_pose(k)[0].T @ F.frame_pose(k+1)[0]
        rel.append(rot_angle(Rgt)); e_raw.append(rot_angle(Rc_meas.T @ Rgt))
    e_raw = np.array(e_raw); rel = np.array(rel)
    o['rot_per_frame_deg_med'] = float(np.median(rel)); o['rot_per_frame_deg_p90'] = float(np.percentile(rel, 90))
    o['gyro_resid_deg_med'] = float(np.median(e_raw)); o['gyro_resid_px_med'] = float(np.median(np.radians(e_raw)) * fx)
    o['gyro_resid_px_p90'] = float(np.percentile(np.radians(e_raw), 90) * fx)
    # per-frame flow: total vs de-rotated (GT rotation) of the tracker's tracks
    fl = []; fld = []
    byf = {}
    for v in tr.values():
        for a, b in zip(v[:-1], v[1:]): byf.setdefault(int(a[0]), []).append((a[1], a[2], b[1], b[2]))
    for k, lst in byf.items():
        if k + 1 >= nf: continue
        a = np.array(lst); Rgt = F.frame_pose(k)[0].T @ F.frame_pose(k+1)[0]  # R_c0c1
        b0 = np.c_[(a[:, 0]-cx)/fx, (a[:, 1]-cy)/fy, np.ones(len(a))] @ Rgt  # bearings in c1 (rows: R^T b)
        px = b0[:, 0]/b0[:, 2]*fx+cx; py = b0[:, 1]/b0[:, 2]*fy+cy
        fl.append(np.median(np.hypot(a[:, 2]-a[:, 0], a[:, 3]-a[:, 1]))); fld.append(np.median(np.hypot(a[:, 2]-px, a[:, 3]-py)))
    o['flow_px_med'] = float(np.median(fl)); o['flow_derot_px_med'] = float(np.median(fld)); o['flow_px_p90'] = float(np.percentile(fl, 90))
    # filter counters (AUD_STATS); tc_* are cumulative -> totals = last - first
    if len(S):
        def tot(c):
            x = S[:, c]; d = np.diff(x)
            return float(x[-1] - x[0]) if (d >= 0).all() else float(x.sum())
        att, tri, gate = tot(2), tot(3), tot(4)
        o['msckf_att'] = att; o['tri_rej_rate'] = tri / max(att, 1); o['gate_rej_rate'] = gate / max(att, 1)
        o['klt_fail_per_frame'] = float(S[:, 12].mean()); o['fb_rej_per_frame'] = float(S[:, 11].mean())
        o['det_per_frame'] = float(S[:, 16].mean()); o['detnew_per_frame'] = float(S[:, 17].mean())
        o['rows_per_frame'] = float(np.diff(S[:, 5]).clip(0).mean()) if (np.diff(S[:, 5]) >= 0).all() else float(S[:, 5].mean())
    json.dump(o, open(outp, 'w'), indent=0)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 320)
