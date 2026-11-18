"""Error budget under UNALIGNED ATE: replace one quantity at a time with truth (Modulo's oracle table, stage-2 metric).

    python oracle.py "data/val/*.npz"
"""
import sys

import numpy as np

from common import ate, integrate_body_velocity, load, sim3_ate
from pairs import config
from streaming import Inputs
from decompose import moving_mean


def rows(f):
    gt = f.cam_gt
    R_gt = f.R
    vb = f.v_body
    sp = np.linalg.norm(vb, axis=1)
    out = {}
    cam = lambda R, v: f.camera_positions(f.p[0] + integrate_body_velocity(R, v, times=f.ft), R)

    out["zero output"] = np.zeros_like(gt)
    out["truth R + truth v (sanity: 0)"] = cam(R_gt, vb)
    inputs = Inputs(config(), f.K, f.frames.shape[1:], f.T_bc[:3,:3])
    R_gyro = np.stack([inputs.step(t, frame, packet,"imu")[2]
                       for t,frame,packet in zip(f.ft,f.frames,f.win)])
    out["gyro R (causal evidence calibration) + truth v"] = cam(R_gyro, vb)
    R_gyro_raw = f.gyro_attitude(bias=np.zeros(3))
    out["gyro R (no bias fix) + truth v"] = cam(R_gyro_raw, vb)
    # speed errors with true direction
    d = vb / np.maximum(sp[:, None], 1e-6)
    out["truth R, mean speed (per flight), true dir"] = cam(R_gt, d * sp.mean())
    out["truth R, speed x0.8, true dir"] = cam(R_gt, vb * 0.8)
    out["truth R, speed x1.2, true dir"] = cam(R_gt, vb * 1.2)
    for centered in (False, True):
        label = "centered noncausal" if centered else "trailing causal"
        out[f"truth R, speed 1 s {label}, true dir"] = cam(R_gt,d*moving_mean(sp[:,None],f.ft,1.,centered))
    # direction prior: fly along body x (forward) at true speed, horizontal only
    fwd = np.zeros_like(vb); fwd[:, 0] = 1.0
    out["truth R, true speed, body-forward dir"] = cam(R_gt, fwd * sp[:, None])
    # noise: white speed noise 30% at 20 Hz (averages out?) vs a 10% bias
    rng = np.random.default_rng(0)
    out["truth R, true v + 30% white noise"] = cam(R_gt, vb * (1 + 0.3 * rng.standard_normal((len(vb), 1))))
    out["gyro R (causal evidence calibration), speed x0.9"] = cam(R_gyro, vb * 0.9)
    return gt, out


def main():
    fl = load(sys.argv[1])
    acc = {}
    for f in fl:
        gt, out = rows(f)
        for k, est in out.items():
            acc.setdefault(k, []).append((ate(est, gt), sim3_ate(est, gt)))
    print(f"{len(fl)} flights; columns: unaligned ATE (scored), Sim(3) ATE (diagnostic)")
    for k, v in acc.items():
        v = np.array(v)
        print(f"  {k:46s} {v[:,0].mean():6.3f} m   {v[:,1].mean():6.3f} m")


if __name__ == "__main__":
    main()
