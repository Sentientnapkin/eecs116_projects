"""Video of one flight: the drone's camera next to a top-down map of the true path and our estimates.

    python flight_video.py FLIGHT.zip OUT.mp4 label=libvio_host label2=libvio_sc20 ...
Each label=cache pairs a name with a cached run of diag.py (~/ws_proto/cache/<cache>/<flight>_*.npz).
Also writes OUT.png: the whole flight's map plus each estimate's error over time.
Map: seen from above in the first camera's axes (x = right, z = forward at the start), metres.
"""
import glob
import os
import sys

import cv2
import numpy as np

from viobench.tools.datasets.sources import episodes

zip_path, out_path = sys.argv[1], sys.argv[2]
runs = [a.split("=", 1) for a in sys.argv[3:]]
episode = next(episodes([zip_path]))
gt = episode.ground_truth_state()[:, :3]
times = episode.frame_times - episode.frame_times[0]
est, windows = {}, {}
for label, cache in runs:
    # episode names can repeat (e.g. the HF set): take the cached run whose true path is this flight's
    cands = [np.load(f) for f in glob.glob(os.path.expanduser(f"~/ws_proto/cache/{cache}/{episode.name}_*.npz"))]
    d = next(c for c in cands if c["gt"].shape[0] == len(gt) and np.allclose(c["gt"][:, :3], gt, atol=1e-3))
    est[label] = d["est"][:, :3]
    windows[label] = d["windows"]

COLORS = [(0, 140, 255), (255, 120, 0), (200, 0, 200), (0, 180, 0)]  # BGR: orange, blue, purple, green
TRUE = (40, 40, 40)
W_CAM, H, W_MAP = 640, 480, 480


def to_map(p, lo, scale):
    return int(20 + (p[0] - lo[0]) * scale), int(H - 20 - (p[2] - lo[1]) * scale)  # x right, z up the page


allp = np.vstack([gt] + list(est.values()))
lo = np.array([allp[:, 0].min(), allp[:, 2].min()]) - 0.3
hi = np.array([allp[:, 0].max(), allp[:, 2].max()]) + 0.3
scale = min((W_MAP - 40) / (hi[0] - lo[0]), (H - 40) / (hi[1] - lo[1]))


def draw_map(img, upto, ox=0):
    for x in range(int(np.ceil(lo[0])), int(hi[0]) + 1):  # 1 m grid
        a, b = to_map((x, 0, lo[1]), lo, scale), to_map((x, 0, hi[1]), lo, scale)
        cv2.line(img, (a[0] + ox, a[1]), (b[0] + ox, b[1]), (225, 225, 225), 1)
    for z in range(int(np.ceil(lo[1])), int(hi[1]) + 1):
        a, b = to_map((lo[0], 0, z), lo, scale), to_map((hi[0], 0, z), lo, scale)
        cv2.line(img, (a[0] + ox, a[1]), (b[0] + ox, b[1]), (225, 225, 225), 1)
    s = to_map((0, 0, 0), lo, scale)
    cv2.drawMarker(img, (s[0] + ox, s[1]), (0, 0, 0), cv2.MARKER_STAR, 16, 2)  # start = where "doing nothing" stays
    for i, (label, p) in enumerate([("true path", gt)] + list(est.items())):
        color = TRUE if i == 0 else COLORS[(i - 1) % len(COLORS)]
        pts = np.array([to_map(q, lo, scale) for q in p[:upto + 1]]) + [ox, 0]
        cv2.polylines(img, [pts.reshape(-1, 1, 2).astype(np.int32)], False, color, 2 if i == 0 else 1, cv2.LINE_AA)
        cv2.circle(img, tuple(int(v) for v in pts[-1]), 6, color, -1, cv2.LINE_AA)


def blind(label, t):
    w = windows[label]
    return not np.any((w[:, 0] <= t) & (w[:, 1] >= t) & (w[:, 10] > 0))


writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), 20, (W_CAM + W_MAP, H))
config, frames = episode.adapt((W_CAM, H))
t0 = episode.frame_times[0]
for k, (t, frame, _) in enumerate(episode.steps(frames)):
    img = np.full((H, W_CAM + W_MAP, 3), 255, np.uint8)
    cam = np.ascontiguousarray(frame[..., :3])
    img[:, :W_CAM] = cv2.cvtColor(cam, cv2.COLOR_RGB2BGR)
    draw_map(img, k, ox=W_CAM)
    cv2.putText(img, f"t = {t - t0:4.1f} s", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    y = 24
    for i, (label, p) in enumerate([("true path", gt)] + list(est.items())):
        color = TRUE if i == 0 else COLORS[(i - 1) % len(COLORS)]
        text = label if i == 0 else f"{label}: off by {np.linalg.norm(p[k] - gt[k]):4.2f} m" + ("  (camera blind)" if blind(label, t) else "")
        cv2.putText(img, text, (W_CAM + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        y += 20
    cv2.putText(img, f"star = start; doing nothing is off by {np.linalg.norm(gt[k]):4.2f} m", (W_CAM + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    writer.write(img)
writer.release()

# summary picture: full map + error over time
summary = np.full((H, W_MAP + 640, 3), 255, np.uint8)
draw_map(summary, len(gt) - 1)
gx0, gy0, gw, gh = W_MAP + 50, 40, 560, 380
err_max = max(np.linalg.norm(gt, axis=1).max(), max(np.linalg.norm(p - gt, axis=1).max() for p in est.values()))
cv2.rectangle(summary, (gx0, gy0), (gx0 + gw, gy0 + gh), (180, 180, 180), 1)
curves = [("doing nothing", np.linalg.norm(gt, axis=1), (0, 0, 0))]
curves += [(label, np.linalg.norm(p - gt, axis=1), COLORS[i % len(COLORS)]) for i, (label, p) in enumerate(est.items())]
for j, (label, e, color) in enumerate(curves):
    pts = np.c_[gx0 + times / times[-1] * gw, gy0 + gh - e / err_max * gh].astype(np.int32)
    cv2.polylines(summary, [pts.reshape(-1, 1, 2)], False, color, 2, cv2.LINE_AA)
    rmse = np.sqrt(np.mean(e ** 2))
    cv2.putText(summary, f"{label}: ATE {rmse:.2f} m", (gx0 + 10, gy0 + 20 + 20 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
cv2.putText(summary, f"position error (m, top = {err_max:.1f}) vs time (0-{times[-1]:.0f} s)", (gx0, gy0 + gh + 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
cv2.imwrite(out_path[:-4] + ".png", summary)
print("wrote", out_path, "and", out_path[:-4] + ".png")
