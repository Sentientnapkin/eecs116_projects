"""Diagnostic video of one flight: camera, top-down map (true vs estimate), and timelines.

    python vio_video.py FLIGHT.zip RUNDIR OUT.mp4 "title"
RUNDIR = a viobench evaluate log dir holding estimate.tum and twist.txt for this flight.
Also writes OUT.png (the last frame).

Layout (1280 x 760):
  top left   camera (640x480), with corners an independent detector finds (cv2.goodFeaturesToTrack): a texture
             gauge, NOT the estimator's own tracks
  top right  top-down map in the first camera's axes (x right, z forward), 1 m grid, true path dark, estimate orange,
             red line = current position error
  bottom     timelines with a cursor: position error (m), speed true vs estimate (m/s), corner count;
             gray bands = "camera starved" (fewer than STARVED corners)
"""
import glob
import os
import sys

import cv2
import numpy as np

from viobench.tools.datasets.sources import episodes

zip_path, run_dir, out_path, title = sys.argv[1:5]
STARVED = 20   # fewer than this many textured 16x16 cells (of 300) = camera starved
FAST_T = 8     # FAST corner contrast threshold (gray levels, absolute)

ep = next(episodes([zip_path]))
gt = ep.ground_truth_state()
est = np.loadtxt(glob.glob(os.path.join(run_dir, "estimate.tum"))[0])
tw = np.loadtxt(glob.glob(os.path.join(run_dir, "twist.txt"))[0])
n = min(len(gt), len(est))
gt, est, tw = gt[:n], est[:n], tw[:n]
t = est[:, 0] - est[0, 0]
p_true, p_est = gt[:, :3], est[:, 1:4]
err = np.linalg.norm(p_est - p_true, axis=1)
ate = float(np.sqrt(np.mean(err ** 2)))
spd_true, spd_est = np.linalg.norm(gt[:, 7:10], axis=1), np.linalg.norm(tw[:, 1:4], axis=1)
len_ratio = np.sum(np.linalg.norm(np.diff(p_est, axis=0), axis=1)) / np.sum(np.linalg.norm(np.diff(p_true, axis=0), axis=1))


def qang(a, b):  # angle between unit quaternions (x y z w), degrees
    d = np.abs(np.sum(a * b, axis=1)).clip(0, 1)
    return np.degrees(2 * np.arccos(d))


rot_err = qang(gt[:, 3:7] / np.linalg.norm(gt[:, 3:7], axis=1, keepdims=True), est[:, 4:8] / np.linalg.norm(est[:, 4:8], axis=1, keepdims=True))

W, HT, HB = 1280, 480, 360
CAM = 640
BG, INK, GRID = (250, 248, 244), (46, 32, 22), (226, 222, 214)
ORANGE, BLUE, RED, GRAY = (42, 105, 217), (176, 111, 47), (40, 40, 200), (150, 150, 150)

# map scaling (x right, z up the page)
allp = np.vstack([p_true, p_est])
lo = np.array([allp[:, 0].min(), allp[:, 2].min()]) - 0.5
hi = np.array([allp[:, 0].max(), allp[:, 2].max()]) + 0.5
MW, MH = W - CAM, HT
scale = min((MW - 60) / (hi[0] - lo[0]), (MH - 90) / (hi[1] - lo[1]))
cx = CAM + 30 + ((MW - 60) - (hi[0] - lo[0]) * scale) / 2
cy = 70 + (MH - 90)


def to_map(q):
    return int(cx + (q[0] - lo[0]) * scale), int(cy - (q[2] - lo[1]) * scale)


map_true = np.array([to_map(q) for q in p_true], np.int32)
map_est = np.array([to_map(q) for q in p_est], np.int32)

# first pass: corner counts (texture gauge)
config, frames = ep.adapt((CAM, HT))
corners, counts = [], []
fast = cv2.FastFeatureDetector_create(threshold=FAST_T, nonmaxSuppression=True)
for k, (_, frame, _) in enumerate(ep.steps(frames)):
    if k >= n:
        break
    g = cv2.cvtColor(np.ascontiguousarray(frame[..., :3]), cv2.COLOR_RGB2GRAY)
    small = cv2.resize(g, (CAM // 2, HT // 2), interpolation=cv2.INTER_AREA)  # the estimator's 320x240
    kp = fast.detect(small, None)
    c = np.array([[q.pt[0] * 2, q.pt[1] * 2] for q in kp], np.float32).reshape(-1, 2)
    # count distinct corners: at most one per 16x16 cell, like a grid-based tracker
    cells = {(int(x) // 32, int(y) // 32) for x, y in c}
    corners.append(c[:300])
    counts.append(len(cells))
counts = np.array(counts + [0] * (n - len(counts)))
starved = counts < STARVED

# timeline panels
PX0, PW = 70, W - 100
panels = [("position error (m)", [(err, RED)], max(err.max(), 0.5)),
          ("speed: true (dark) vs estimate (orange), m/s", [(spd_true, INK), (spd_est, ORANGE)], max(spd_true.max(), spd_est.max(), 0.5)),
          ("orientation error (deg): heading + tilt", [(rot_err, (150, 60, 140))], max(rot_err.max(), 5.0)),
          (f"textured cells (16x16 cells with a FAST corner; gray band = fewer than {STARVED})", [(counts.astype(float), BLUE)], max(counts.max(), STARVED + 5))]
PH = (HB - 30) // 4


def panel_y(i):
    return HT + 15 + i * PH


def draw_static(img):
    for i, (label, series, top) in enumerate(panels):
        y0 = panel_y(i)
        h = PH - 22
        # starved bands
        xs = PX0 + t / t[-1] * PW
        run = None
        for k in range(n + 1):
            s = k < n and starved[k]
            if s and run is None:
                run = k
            if not s and run is not None:
                cv2.rectangle(img, (int(xs[run]), y0 + 16), (int(xs[k - 1]) + 1, y0 + 16 + h), (232, 230, 226), -1)
                run = None
        cv2.rectangle(img, (PX0, y0 + 16), (PX0 + PW, y0 + 16 + h), GRID, 1)
        cv2.putText(img, label, (PX0, y0 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, INK, 1, cv2.LINE_AA)
        cv2.putText(img, f"{top:.1f}", (PX0 - 48, y0 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, GRAY, 1, cv2.LINE_AA)
        cv2.putText(img, "0", (PX0 - 20, y0 + 16 + h), cv2.FONT_HERSHEY_SIMPLEX, 0.4, GRAY, 1, cv2.LINE_AA)
        for s, col in series:
            pts = np.c_[xs, y0 + 16 + h - np.clip(s / top, 0, 1) * h].astype(np.int32)
            cv2.polylines(img, [pts.reshape(-1, 1, 2)], False, col, 1, cv2.LINE_AA)
    for sec in range(0, int(t[-1]) + 1, 10):
        x = int(PX0 + sec / t[-1] * PW)
        cv2.putText(img, f"{sec}s", (x - 8, HT + HB - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, GRAY, 1, cv2.LINE_AA)
    # map grid + full true path (faint)
    for x in range(int(np.ceil(lo[0])), int(hi[0]) + 1):
        cv2.line(img, to_map((x, 0, lo[1])), to_map((x, 0, hi[1])), GRID, 1)
    for z in range(int(np.ceil(lo[1])), int(hi[1]) + 1):
        cv2.line(img, to_map((lo[0], 0, z)), to_map((hi[0], 0, z)), GRID, 1)
    cv2.polylines(img, [map_true.reshape(-1, 1, 2)], False, (214, 210, 204), 1, cv2.LINE_AA)
    cv2.drawMarker(img, to_map((0, 0, 0)), INK, cv2.MARKER_STAR, 14, 1)


base = np.full((HT + HB, W, 3), BG, np.uint8)
draw_static(base)
writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), 20, (W, HT + HB))
config, frames = ep.adapt((CAM, HT))
for k, (_, frame, _) in enumerate(ep.steps(frames)):
    if k >= n:
        break
    img = base.copy()
    img[:HT, :CAM] = cv2.cvtColor(np.ascontiguousarray(frame[..., :3]), cv2.COLOR_RGB2BGR)
    for c in corners[k]:
        cv2.circle(img, (int(c[0]), int(c[1])), 3, (80, 230, 120), 1, cv2.LINE_AA)
    cv2.rectangle(img, (0, 0), (CAM, 34), (30, 30, 30), -1)
    cv2.putText(img, f"t = {t[k]:4.1f} s   textured cells {counts[k]:3d}" + ("   CAMERA STARVED" if starved[k] else ""), (10, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 200, 255) if starved[k] else (255, 255, 255), 1, cv2.LINE_AA)
    # map
    cv2.polylines(img, [map_true[:k + 1].reshape(-1, 1, 2)], False, INK, 2, cv2.LINE_AA)
    cv2.polylines(img, [map_est[:k + 1].reshape(-1, 1, 2)], False, ORANGE, 2, cv2.LINE_AA)
    cv2.line(img, tuple(map_true[k]), tuple(map_est[k]), RED, 2, cv2.LINE_AA)
    cv2.circle(img, tuple(map_true[k]), 6, INK, -1, cv2.LINE_AA)
    cv2.circle(img, tuple(map_est[k]), 6, ORANGE, -1, cv2.LINE_AA)
    cv2.putText(img, title, (CAM + 16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, INK, 1, cv2.LINE_AA)
    cv2.putText(img, f"top-down, 1 m grid | true (dark) vs GSLV (orange) | ATE {ate:.2f} m | est/true path length {len_ratio:.2f}", (CAM + 16, 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRAY, 1, cv2.LINE_AA)
    cv2.putText(img, f"now: off by {err[k]:.2f} m, heading/tilt off {rot_err[k]:.0f} deg, speed {spd_true[k]:.2f} true / {spd_est[k]:.2f} est",
                (CAM + 16, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.42, RED, 1, cv2.LINE_AA)
    # cursor
    x = int(PX0 + t[k] / t[-1] * PW)
    cv2.line(img, (x, HT + 28), (x, HT + HB - 18), (60, 60, 60), 1)
    writer.write(img)
writer.release()
cv2.imwrite(out_path[:-4] + ".png", img)
print(f"wrote {out_path}  ATE {ate:.3f}  path-length ratio {len_ratio:.2f}  median cells {np.median(counts):.0f}  starved {starved.mean() * 100:.0f}% of frames  max err {err.max():.2f} m at {t[err.argmax()]:.1f} s")
