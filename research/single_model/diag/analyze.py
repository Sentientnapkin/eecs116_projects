"""E1 diagnostics: parse DIAG stderr from the diag build and compare with truth. Search slice (folds 0-2) and val (fold 3) only.
Usage: venv-teacher python -B research/single_model/diag/analyze.py <run_name>
Writes research/results/single_model/<run_name>/diag_table.csv
"""
import sys, json, re, hashlib
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.guard_fusion import traj as T
from research.single_model import run_variant as RV
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices

G = 9.81


def quat_to_R(q):  # xyzw
    x, y, z, w = q
    return np.array([[1 - 2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1 - 2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1 - 2*(x*x+y*y)]])


def parse(path):
    d0 = None; rows = []
    for line in Path(path).read_text(errors='replace').splitlines():
        if line.startswith('DIAG0'):
            m = re.search(r'f=([-\d.e]+),([-\d.e]+),([-\d.e]+) R0=(.*)', line)
            d0 = dict(f=np.array([float(m.group(i)) for i in (1, 2, 3)]), R0=np.array([float(x) for x in m.group(4).split(',')]).reshape(3, 3))
        elif line.startswith('DIAG '):
            kv = {}
            for tok in line[5:].split():
                k, v = tok.split('=')
                kv[k] = [float(x) for x in v.split(',')] if ',' in v else float(v)
            kv['R'] = np.array(kv['R']).reshape(3, 3)
            rows.append(kv)
    return d0, rows


def truth_info(ep):
    """body-0 frame truth: R_t (body t -> body 0), true gravity direction in body 0 (LS), true accel bias (LS)."""
    e = read_episode(T.DEFAULT_RAW / f'{ep}.zip', frames='none')
    ft = np.asarray(e.frame_times)
    gt = e.ground_truth
    pose_t = gt[:, 0]
    # accel from GT position (central second difference, 200 Hz), in body-0 frame
    p = gt[:, 1:4]; dt = np.median(np.diff(pose_t))
    k = 4  # smooth over +-k samples
    acc = np.zeros_like(p)
    acc[k:-k] = (p[2*k:] - 2 * p[k:-k] + p[:-2*k]) / (k * dt) ** 2
    Rs = np.array([quat_to_R(q) for q in gt[:, 4:8]])
    imu = e.imu
    n = min(len(imu), len(gt))
    sel = np.arange(k, n - k)
    sel = sel[pose_t[sel] < 20.0]
    # f = R^T (a - g)  ->  f - R^T a = -R^T g + b  ; unknowns g (3), b (3)
    A = []; y = []
    for i in sel:
        Ri = Rs[i]
        rhs = imu[i, 1:4] - Ri.T @ acc[i]
        A.append(np.hstack([-Ri.T, np.eye(3)])); y.append(rhs)
    A = np.vstack(A); y = np.concatenate(y)
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)
    g_W = sol[:3]; b_true = sol[3:]
    # GT is in the simulator world W (z up, gravity-aligned), NOT in body 0. Express everything in the body-0 frame
    # (the frame the filter's R0 maps into): X_b0 = Rs0^T X_W.
    Rs0 = Rs[0]
    g_b0 = Rs0.T @ g_W
    v = np.gradient(p, pose_t, axis=0) @ Rs0
    p_b0 = (p - p[0]) @ Rs0
    Rrel = np.einsum('ji,njk->nik', Rs0, Rs)  # Rs0^T Rs[t]
    return dict(ft=ft, pt=pose_t, Rs=Rrel, g_b0=g_b0, g_W=g_W, b_true=b_true, v_b0=v, p=p_b0, imu=imu, acc=acc, e=e)


def ang(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    return float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))


def episode_features(ep, folder):
    logs = sorted((Path(folder) / ep / 'report/logs').glob('*/stderr.txt'))
    if not logs:
        return None
    d0, rows = parse(logs[0])
    if d0 is None or len(rows) < 100:
        return None
    ti = truth_info(ep)
    out = dict(ep=ep)
    gup_true_b0 = -ti['g_b0'] / np.linalg.norm(ti['g_b0']) * -1  # unit "down"?  g_b0 is the gravity vector in b0 (pointing down) in sign convention f = R^T(a - g)
    # gravity vector g (world, = [0,0,-9.81] direction) in b0:
    gdir_b0 = ti['g_b0'] / np.linalg.norm(ti['g_b0'])  # points down
    # filter: world z = up; R0 = world<-body0, so up in b0 = R0^T z
    R0 = d0['R0']
    up_f_b0 = R0.T @ np.array([0, 0, 1.0])
    out['tilt_err0'] = ang(up_f_b0, -gdir_b0)
    # true vehicle tilt at frame 0: angle between body z and up
    out['true_tilt0'] = ang(np.array([0, 0, 1.0]), -gdir_b0)  # body0 z axis vs up
    # true speed / velocity at start, mean over 0..0.5 s (b0 frame)
    m = ti['pt'] <= 0.5
    v0 = ti['v_b0'][:5].mean(0) if False else ti['v_b0'][1:20].mean(0)
    out['v0_true'] = float(np.linalg.norm(v0))
    # filter velocity at frame 1 (world) -> b0
    f1 = rows[0]
    vf0 = R0.T @ np.array(f1['v'])
    out['v0_est'] = float(np.linalg.norm(vf0))
    out['v0_err'] = float(np.linalg.norm(vf0 - v0))
    out['v0_err_dir_deg'] = ang(vf0, v0) if np.linalg.norm(vf0) > 1e-3 and np.linalg.norm(v0) > 1e-3 else np.nan
    out['v0_mag_err'] = float(np.linalg.norm(vf0) - np.linalg.norm(v0))
    # true angular rate near start
    out['w0_true'] = float(np.linalg.norm(ti['imu'][:40, 4:7].mean(0)))
    # tilt error / velocity error over time (compare at frames)
    ft = ti['ft']
    for T_s, fr in ((1, 20), (2, 40), (5, 100), (10, 200)):
        if fr - 1 >= len(rows):
            continue
        r = rows[fr - 1]
        Rt_est = R0.T @ r['R']  # est body_t -> b0
        # interpolate truth rotation at frame time
        idx = int(np.argmin(np.abs(ti['pt'] - r['t'] + ft[0] * 0)))  # frame times are on GT clock (t from 0)
        Rt_true = ti['Rs'][idx]
        up_est_body = r['R'].T @ np.array([0, 0, 1.0])
        up_true_body = Rt_true.T @ (-gdir_b0)
        out[f'tilt_err_{T_s}s'] = ang(up_est_body, up_true_body)
        v_est_b0 = R0.T @ np.array(r['v'])
        out[f'verr_{T_s}s'] = float(np.linalg.norm(v_est_b0 - ti['v_b0'][idx]))
        out[f'speed_est_{T_s}s'] = float(np.linalg.norm(v_est_b0)); out[f'speed_true_{T_s}s'] = float(np.linalg.norm(ti['v_b0'][idx]))
        out[f'baerr_{T_s}s'] = float(np.linalg.norm(np.array(r['ba']) - ti['b_true']))
    # vision counters
    def first(cond):
        for r in rows:
            if cond(r): return r['f']
        return np.nan
    out['first_msckf_frame'] = rows[-1]['firstmsckf'] if rows[-1]['firstmsckf'] >= 0 else np.nan
    out['first_feat_frame'] = rows[-1]['firstfeat'] if rows[-1]['firstfeat'] >= 0 else np.nan
    for T_s in (1, 2, 5, 10):
        rr = [r for r in rows if r['f'] <= 20 * T_s]
        out[f'live_mean_{T_s}s'] = float(np.mean([r['live'] for r in rr]))
        out[f'live3_mean_{T_s}s'] = float(np.mean([r['live3'] for r in rr]))
        out[f'used_{T_s}s'] = int(sum(r['used'] for r in rr))
        out[f'att_{T_s}s'] = int(sum(r['att'] for r in rr))
        out[f'trifail_{T_s}s'] = int(sum(r['trifail'] for r in rr))
        out[f'gaterej_{T_s}s'] = int(sum(r['gaterej'] for r in rr))
        out[f'dvvis_{T_s}s'] = float(sum(r['dvvis'] for r in rr))
        out[f'dvprior_{T_s}s'] = float(sum(r['dvprior'] for r in rr))
        out[f'zupt_{T_s}s'] = int(sum(1 for r in rr if r['zupt'] > 0))
    out['Pv0'] = float(np.sqrt(np.mean(rows[0]['Pv'])))
    out['Pth0'] = float(np.sqrt(np.mean(rows[0]['Pth'][:2])))
    out['Pv2'] = float(np.sqrt(np.mean(rows[39]['Pv']))) if len(rows) > 39 else np.nan
    out['Pth2'] = float(np.sqrt(np.mean(rows[39]['Pth'][:2]))) if len(rows) > 39 else np.nan
    # NEES-ish: velocity error^2 / trace Pv at 2s
    if 'verr_2s' in out:
        out['vnees_2s'] = out['verr_2s'] ** 2 / sum(rows[39]['Pv'])
        out['tnees_2s'] = (np.radians(out['tilt_err_2s'])) ** 2 / (rows[39]['Pth'][0] + rows[39]['Pth'][1])
    out['ba_true_norm'] = float(np.linalg.norm(ti['b_true']))
    out['g_est_norm'] = float(np.linalg.norm(ti['g_b0']))
    # open-loop decomposition of position error at 2 s / 5 s (body-0 frame, filter's own pos)
    decomp(out, rows, d0, ti, ft)
    return out


def decomp(out, rows, d0, ti, ft):
    """Position error at T (b0 frame) = e_v0*T + int int a_tilt + int int a_bias + int int c, with
    a_tilt = (Rb - Rt) f + (g_est - g_true)   (attitude + gravity direction error acting on the measured specific force)
    a_bias = -Rb b_hat + Rt b_true            (accelerometer bias error)
    c      = everything else the filter did (vision / prior / thrust-model corrections, noise) = actual - model.
    Signed projections on the actual error direction add up exactly to |e_act|."""
    R0 = d0['R0']
    gvec_est = R0.T @ np.array([0, 0, -G])
    gvec_true = G * ti['g_b0'] / np.linalg.norm(ti['g_b0'])
    imu = ti['imu']
    dt = 0.05
    N = min(len(rows), 200)
    v_true0 = ti['v_b0'][1:20].mean(0)
    ev0 = R0.T @ np.array(rows[0]['v']) - v_true0
    vt = np.zeros(3); vb = np.zeros(3)
    ept = np.zeros(3); epb = np.zeros(3)
    for k in range(1, N):
        r = rows[k - 1]
        idx = min(int(round(r['t'] * 200)), len(imu) - 1, len(ti['Rs']) - 1)
        Rb = R0.T @ r['R']; Rt = ti['Rs'][idx]
        f = imu[max(idx - 9, 0):idx + 1, 1:4].mean(0)
        a_t = (Rb - Rt) @ f + (gvec_est - gvec_true)
        if k == 1:
            out['aerr0'] = float(np.linalg.norm(a_t))
            out['aerr0_cos_v0'] = float(a_t @ v_true0 / (np.linalg.norm(a_t) * np.linalg.norm(v_true0) + 1e-9))
            out['aerr0_along_v0'] = float(a_t @ v_true0 / (np.linalg.norm(v_true0) + 1e-9))
        a_b = -Rb @ np.array(r['ba']) + Rt @ ti['b_true']
        vt += a_t * dt; vb += a_b * dt
        ept += vt * dt; epb += vb * dt
        fr = k + 1  # rows[k] is frame k+1
        if fr in (21, 41, 101) and k < len(rows):
            tag = int(round((fr - 1) / 20))
            T_s = (fr - 1) * dt
            ti_idx = min(int(round(rows[k]['t'] * 200)), len(ti['p']) - 1)
            e_act = R0.T @ np.array(rows[k]['p']) - ti['p'][ti_idx]
            n = np.linalg.norm(e_act) + 1e-9
            comp = {'v0': ev0 * T_s, 'tilt': ept.copy(), 'bias': epb.copy()}
            comp['corr'] = e_act - comp['v0'] - comp['tilt'] - comp['bias']
            out[f'ep_act_{tag}s'] = float(n)
            for nme, c in comp.items():
                out[f'ep_proj_{nme}_{tag}s'] = float(c @ e_act / n)
                out[f'ep_norm_{nme}_{tag}s'] = float(np.linalg.norm(c))


def main():
    name = sys.argv[1]
    folder = next((RV.OUT / name / 'eval').glob(name + '-*'))
    folder = folder if folder.is_dir() else folder.parent
    tg = RV.tags()
    scores = RV.ate_rows(Path(folder) / 'scores.json')
    base = RV.ate_rows(RV.BASELINE)
    rows = []
    for ep in sorted(scores):
        f = RV.fold(tg[ep])
        if RV.slice_of(f) == 'sealed':
            continue  # never analysed
        r = episode_features(ep, folder)
        if r is None:
            print('skip', ep); continue
        r.update(start=tg[ep]['start'], scene=tg[ep]['scene'], slice=RV.slice_of(f), ate=scores[ep], ate_base=base[ep])
        a = RV.PERFLIGHT  # audit fields
        rows.append(r)
    (RV.OUT / name / 'diag_table.json').write_text(json.dumps(rows, default=float))
    print(len(rows))


if __name__ == '__main__':
    main()
