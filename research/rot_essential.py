"""Classical check: how well does a 5-point essential-matrix fit (LK tracks, 1 s baseline, 160x120) recover rotation?

Compares the camera rotation between frames k-20 and k from vision against truth, and against the gyro chain with the
causal evidence calibration. If vision's rotation error over 1 s is well below the bias-induced error (~0.005-0.02 rad), vision can
correct the bias (Modulo's 'turn seen vs view 1.5 s back').

    python rot_essential.py "data/val/*.npz"
"""
import glob, sys
import cv2, numpy as np
from common import Flight
from pairs import config
from streaming import Inputs

LAG = 20
lk = dict(winSize=(15, 15), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.01))
errs_v, errs_g, used = [], [], 0
for p in sorted(glob.glob(sys.argv[1]))[::3]:
    f = Flight(p)
    Kc = np.array([[f.K["fx"], 0, f.K["cx"]], [0, f.K["fy"], f.K["cy"]], [0, 0, 1.0]])
    R_bc = f.T_bc[:3, :3]
    stream = Inputs(config(), f.K, f.frames.shape[1:], R_bc)
    Rg = np.stack([stream.step(t,frame,packet,"imu")[2] for t,frame,packet in zip(f.ft,f.frames,f.win)])
    for k in range(LAG + 20, f.F, 10):
        a, b = f.frames[k - LAG], f.frames[k]
        pts = cv2.goodFeaturesToTrack(a, 150, 0.01, 5)
        if pts is None or len(pts) < 20: continue
        R_gyro = R_bc.T @ Rg[k - LAG].T @ Rg[k] @ R_bc  # cam_k -> cam_{k-LAG}
        Hm = Kc @ R_gyro.T @ np.linalg.inv(Kc)
        guess = cv2.perspectiveTransform(pts, Hm)
        q, st, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, guess.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
        ok = st.ravel() == 1
        if ok.sum() < 20: continue
        E, inl = cv2.findEssentialMat(pts[ok], q[ok], Kc, cv2.RANSAC, 0.999, 1.0)
        if E is None or E.shape != (3, 3): continue
        _, Rv, t, _ = cv2.recoverPose(E, pts[ok], q[ok], Kc, mask=inl)
        R_true = R_bc.T @ f.R[k - LAG].T @ f.R[k] @ R_bc
        # recoverPose returns R mapping points from frame a to frame b: x_b = R x_a + t  ->  cam_a->cam_b; truth R_true is cam_b->cam_a
        ang = lambda R: np.linalg.norm(cv2.Rodrigues(R)[0])
        errs_v.append(ang(Rv @ R_true)); errs_g.append(ang(R_gyro.T @ R_true)); used += 1
ev, eg = np.array(errs_v), np.array(errs_g)
print(f"{used} pairs (1 s apart): vision rotation error median {np.median(ev):.4f} rad, p90 {np.percentile(ev,90):.4f}; "
      f"gyro(causal evidence) error median {np.median(eg):.4f} rad, p90 {np.percentile(eg,90):.4f}")
print(f"fraction of pairs where vision beats gyro: {(ev < eg).mean():.2f}")
