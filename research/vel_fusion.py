"""Frozen-velocity translation-direction fusion (predeclared 2026-11-19, before any run).

    PYTHONPATH=/dev/shm/sebastian-vio/viobench python vel_fusion.py --set public|campaign-dev --output <dir> [--workers 48]

Attitude is held FIXED at attitude_bias.py's ungated "kf_grid" arm (the 3-sigma gated arm was worse: public 1.561 vs
1.383). The kf_grid pass is re-run here with an instrumented copy of grid_rotation that consumes the RANSAC RNG
identically and additionally records, per 0.5 s window, the essential-matrix camera translation direction, inlier
count, track count and gyro-compensated median flow (parallax). The recomputed attitude is checked against the saved
kf_grid attitude (results/eval/attitude-bias/<set>/attitudes on odometry/provided-openvins). Velocities are each
model's frozen predictions saved there (B-D0-ssm-x3 s217/218/219, N2-ssm-x3 s217/218/219).

Every fused arm is CAUSAL: a window [a, k] is measured with images a and k, so its correction is applied as a
position offset from frame k onward (frames a..k-1 keep their already-emitted positions). Displacements compared
with vision are CAMERA-centre displacements (body displacement + lever-arm term) in the kf_grid world frame.

Visual direction gate ("vis_ok"): essential branch (not rotation-only), kf_grid's cheirality-count test passed
(as implemented, the |delta| <= 0.05 rad attitude test is NOT applied to the direction; noted after the runs),
inliers >= 30, median gyro-compensated flow >= 2 px, network camera
displacement >= 0.05 m over the window.

Arms (all with kf_grid attitude):
  control      network velocity integrated (= attitude_bias kf_grid arm; must reproduce it)
  a_replace    (a) gated windows: displacement := |D_net| * u_vis (vision direction and sign, network scale)
  a_blend      (a) gated windows: rotate D_net toward the line +-u_vis (sign closest to network), by weight
               w = s_n^2 / (s_n^2 + s_v^2), s_n = 0.35 rad (network window-direction error), s_v = 2 px / flow_px
               rad (clipped to [0.02, 0.5]); magnitude kept; no sign trust
  b_sign       (b) only when cos(D_net, u_vis) < -0.5 on a gated window with inliers >= 60 and flow >= 4 px:
               displacement := |D_net| * u_vis; other windows unchanged
  ab           a_blend, but sign taken from vision when b_sign's condition holds
  c_bias       (c) fixed-lag 2 s least squares for an additive body-frame velocity bias b: residuals
               P_perp(u_i)(D_i + A_i b) / (|D_i| s_v,i) over the gated windows ending in the last 2 s
               (A_i = integral of R_wb dt over window i), prior b ~ N(0, 0.15^2 I) m/s. At each gated window end k,
               that window's displacement becomes network + A_i b (jump at k) and b is added to all later velocities
               until the next solve (causal)
Labelled DIAGNOSTICS (truth used, never deployable):
  o_truevel        true body velocity through kf_grid attitude (velocity ceiling)
  o_truedir_all    every window: |D_net| * u_true (true camera direction in the kf_grid world frame)
  o_truedir_gated  as above, only on vis_ok windows (coverage vs quality split)
Also logged: per-window angle(net, truth) and angle(vision, truth) on vis_ok windows.

Direction measurement (--direction): "essential" (primary, as specified: recoverPose translation) and "knownrot"
(added after a 2-flight public smoke test, BEFORE any campaign run: translation direction re-solved over the essential
inliers with the rotation fixed to the gyro/kf_grid prediction; smoke test median window-direction error 5.7 deg vs
10.3 deg essential vs 8.5 deg network). Both variants are reported; the decision rule applies to each.

Decision (predeclared): a candidate PASSES only if, over 6 models x 120 campaign-dev replays, mean full-length ATE
falls >= 10% vs control AND campaign ordinary 30 s mean ATE rises <= 5% (public ordinary 30 s reported alongside).
Groups reported: all / ordinary / backward-lateral / static / moving start / ProcTHOR / HSSD; full, 30 s, 60 s.
If nothing passes, report the null and the diagnostics; no C++ port.
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
import cv2
import numpy as np

import attitude_bias as ab
from common import Flight

SAVED = Path("/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/provided-openvins/research/results/eval/attitude-bias")
RUNS = ("B-D0-ssm-x3-gpu", "B-D0-ssm-x3-s218-gpu", "B-D0-ssm-x3-s219-gpu", "N2-ssm-x3-gpu", "N2-ssm-x3-s218-gpu", "N2-ssm-x3-s219-gpu")
ARMS = ("control", "a_replace", "a_blend", "b_sign", "ab", "c_bias", "o_truevel", "o_truedir_all", "o_truedir_gated")
S_NET, BIAS_PRIOR, LAG = 0.35, 0.15, 2.0
LOG = []
DIRECTION = "essential"


def grid_rotation_logged(first, last, K, relative):
    """attitude_bias.grid_rotation, line for line, plus a record of the translation geometry (same RNG use)."""
    from orientation import fit_visual_rotation
    rec = {"branch": None, "t": None, "inliers": 0, "tracks": 0, "flow": 0.0}
    LOG.append(rec)
    h, w = first.shape
    points = []
    for gy in range(4):
        for gx in range(4):
            cell = first[gy*h//4:(gy+1)*h//4, gx*w//4:(gx+1)*w//4]
            found = cv2.goodFeaturesToTrack(cell, 10, 0.003, 5)
            if found is not None:
                points.append(found[:, 0] + [gx*w//4, gy*h//4])
    if not points:
        return None, "no corners"
    points = np.concatenate(points).astype(np.float32)[:, None]
    if len(points) < 16:
        return None, "few corners"
    guess = cv2.perspectiveTransform(points, K @ relative.T @ np.linalg.inv(K)).astype(np.float32)
    tracked, found, _ = cv2.calcOpticalFlowPyrLK(first, last, points, guess.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    back, returned, _ = cv2.calcOpticalFlowPyrLK(last, first, tracked, points.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    good = found.ravel().astype(bool) & returned.ravel().astype(bool) & (np.linalg.norm((back - points)[:, 0], axis=1) < 0.8)
    old, new = points[good, 0], tracked[good, 0]
    rec["tracks"] = int(len(old))
    cells = {(int(4*x/w), int(4*y/h)) for x, y in old}
    if len(old) < 16 or len(cells) < 5:
        return None, "few tracks"
    inverse = np.linalg.inv(K)
    flow = np.linalg.norm((tracked - guess)[good, 0], axis=1)
    rec["flow"] = float(np.median(flow))
    if np.median(flow) <= 1.0:
        rec["branch"] = "rotation"
        fit = fit_visual_rotation(np.c_[old, np.ones(len(old))] @ inverse.T, np.c_[new, np.ones(len(new))] @ inverse.T, relative)
        if fit is None or fit[1] > 0.012:
            return None, "rotation fit"
        return fit[0], 0.002
    E, mask = cv2.findEssentialMat(old, new, K, method=cv2.RANSAC, prob=0.999, threshold=1.0, maxIters=500)
    if E is None or E.shape != (3, 3):
        return None, "essential"
    count, old_to_new, t, cheiral = cv2.recoverPose(E, old, new, K, mask=mask)
    rec.update(branch="essential", inliers=int(count), t=(-old_to_new.T @ t.ravel()).tolist())  # new centre in old cam
    rec["t_kr"] = known_rotation_direction(old, new, inverse, relative, mask)
    if count < max(12, 0.5 * len(old)):
        rec["branch"] = "cheirality-fail"
        return None, "cheirality"
    return cv2.Rodrigues(relative.T @ old_to_new.T)[0].ravel(), 0.004


def known_rotation_direction(old, new, inverse, relative, mask):
    """Camera-k centre direction in camera-a axes with the rotation FIXED to the gyro/kf_grid prediction
    (relative maps camera-k vectors to camera-a): c . ((relative x_new) x x_old) = 0 over the essential inliers,
    smallest right singular vector, sign by majority cheirality of two-view depths."""
    keep = mask.ravel().astype(bool)
    if keep.sum() < 8:
        return None
    xo = np.c_[old[keep], np.ones(keep.sum())] @ inverse.T
    xn = (np.c_[new[keep], np.ones(keep.sum())] @ inverse.T) @ relative.T
    rows = np.cross(xn, xo)
    rows /= np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-12)
    c = np.linalg.svd(rows)[2][-1]
    # lambda1 xo - lambda2 xn = c  -> least squares per point; count both depths positive
    good = 0
    for a, b in zip(xo, xn):
        lam = np.linalg.lstsq(np.c_[a, -b], c, rcond=None)[0]
        good += 1 if (lam > 0).all() else (-1 if (lam < 0).all() else 0)
    return (c if good >= 0 else -c).tolist()


ab.grid_rotation = grid_rotation_logged


def windows_of(t):
    """The kf_grid window schedule: anchor advances when >= 0.5 s has elapsed."""
    out, anchor = [], 0
    for k in range(1, len(t)):
        if t[k] - t[anchor] >= 0.5 - 1e-8:
            out.append((anchor, k)); anchor = k
    return out


def unit(x):
    n = np.linalg.norm(x)
    return x / n if n > 1e-12 else x


def rotate_toward(d, u, w):
    """Rotate vector d toward unit u by fraction w of the angle; keep |d|."""
    m = np.linalg.norm(d)
    a = unit(d)
    ang = np.arccos(np.clip(a @ u, -1, 1))
    if ang < 1e-9:
        return d
    perp = unit(u - (a @ u) * a)
    return m * (np.cos(w * ang) * a + np.sin(w * ang) * perp)


def body_positions(v, R, times):
    world = (R @ v[..., None]).squeeze(-1)
    p = np.zeros_like(world)
    p[1:] = np.cumsum(.5*(world[1:]+world[:-1])*np.diff(times)[:, None], axis=0)
    return p, world


def to_output(p, R, T_bc):
    arm, rot = T_bc[:3, 3], T_bc[:3, :3]
    return (p + R @ arm - arm) @ rot


def fuse(v, R, T_bc, times, wins, true_dir):
    """All arms' output positions for one velocity sequence. wins: list of dicts (a, k, u, ok, strong, s_v)."""
    arm = T_bc[:3, 3]
    p, world = body_positions(v, R, times)
    n = len(times)
    out = {"control": to_output(p, R, T_bc)}
    cam = p + R @ arm                                 # camera centre, kf_grid world frame
    for name in ("a_replace", "a_blend", "b_sign", "ab", "o_truedir_all", "o_truedir_gated"):
        offset = np.zeros((n, 3))
        for w in wins:
            a, k = w["a"], w["k"]
            d = cam[k] - cam[a]
            m = np.linalg.norm(d)
            new = None
            if name == "o_truedir_all" or (name == "o_truedir_gated" and w["ok"]):
                new = m * true_dir[(a, k)]
            elif w["ok"] and name != "o_truedir_gated":
                u = w["u"]; c = unit(d) @ u
                if name == "a_replace":
                    new = m * u
                elif name == "a_blend":
                    new = rotate_toward(d, u if c >= 0 else -u, S_NET**2 / (S_NET**2 + w["s_v"]**2))
                elif name == "b_sign":
                    new = m * u if (w["strong"] and c < -0.5) else None
                elif name == "ab":
                    target = u if (c >= 0 or (w["strong"] and c < -0.5)) else -u
                    new = rotate_toward(d, target, S_NET**2 / (S_NET**2 + w["s_v"]**2))
            if new is not None:
                offset[k:] += new - d
        out[name] = to_output(p + offset, R, T_bc)
    # (c) fixed-lag additive body-velocity bias, simulated forward causally
    dt = np.diff(times)
    Rcum = np.zeros((n, 3, 3))                        # A_i = integral of R dt over window (trapezoid)
    Rcum[1:] = np.cumsum(.5 * (R[1:] + R[:-1]) * dt[:, None, None], axis=0)
    gated = {w["k"]: w for w in wins if w["ok"]}
    b, history = np.zeros(3), []
    pc_ = np.zeros((n, 3))
    for j in range(1, n):
        pc_[j] = pc_[j-1] + .5 * (world[j] + world[j-1] + (R[j] + R[j-1]) @ b) * dt[j-1]
        w = gated.get(j)
        if w is None:
            continue
        a, k = w["a"], w["k"]
        d0 = cam[k] - cam[a]                          # network-only camera displacement
        A = Rcum[k] - Rcum[a]
        history.append((times[k], d0, A, w["u"], w["s_v"]))
        history = [h for h in history if h[0] > times[k] - LAG - 1e-6]
        H, g = np.eye(3) / BIAS_PRIOR**2, np.zeros(3)
        for _, di, Ai, ui, svi in history:
            P = np.eye(3) - np.outer(ui, ui)
            s = max(np.linalg.norm(di), 0.05) * svi
            J, r0 = P @ Ai / s, P @ di / s
            H += J.T @ J; g -= J.T @ r0
        b = np.linalg.solve(H, g)
        # jump so this window's body displacement equals network + A b (frames a..k-1 already emitted)
        pc_[k] = pc_[a] + (p[k] - p[a]) + A @ b
    p_c = pc_
    out["c_bias"] = to_output(p_c, R, T_bc)
    return out


def episode(job):
    archive, crop, saved_file, row_times, row_T_bc, cam_gt, v_true, meta = job
    from odometry_eval import metrics
    LOG.clear()
    flight = Flight(archive, crop=crop)
    n = len(row_times)
    assert len(flight.ft) >= n and np.allclose(flight.ft[:n], row_times - row_times[0], atol=1e-6), archive
    saved = np.load(saved_file)
    R_all, count, _ = ab.attitudes(flight, "kf_grid")
    R = R_all[:n]
    parity = float(max(np.linalg.norm(ab.log_so3(x.T @ y)) for x, y in zip(R, saved["kf_grid"][:n])))
    t = flight.ft
    sched = windows_of(t)
    assert len(sched) == len(LOG), (len(sched), len(LOG))
    K = np.array([[flight.K["fx"], 0, flight.K["cx"]], [0, flight.K["fy"], flight.K["cy"]], [0, 0, 1.]])
    R_bc, arm = flight.T_bc[:3, :3], flight.T_bc[:3, 3]
    assert np.allclose(flight.T_bc, row_T_bc, atol=1e-6)
    pc = flight.p + np.einsum("nij,j->ni", flight.R, arm)
    wins, true_dir = [], {}
    for (a, k), rec in zip(sched, LOG):
        if k >= n:
            break
        c_true = (flight.R[a] @ R_bc).T @ (pc[k] - pc[a])
        true_dir[(a, k)] = unit(R[a] @ R_bc @ unit(c_true))
        ok = rec["branch"] == "essential" and rec["inliers"] >= 30 and rec["flow"] >= 2.0
        u_e = unit(R[a] @ R_bc @ np.asarray(rec["t"])) if rec["t"] is not None else None
        u_k = unit(R[a] @ R_bc @ np.asarray(rec["t_kr"])) if rec.get("t_kr") is not None else None
        u = u_k if DIRECTION == "knownrot" else u_e
        ok = ok and u is not None
        s_v = float(np.clip(2.0 / max(rec["flow"], 1e-3), 0.02, 0.5))
        wins.append({"a": a, "k": k, "u": u, "ok_vis": ok, "s_v": s_v, "true_cam": c_true,
                     "strong": ok and rec["inliers"] >= 60 and rec["flow"] >= 4.0, "rec": rec, "u_e": u_e, "u_k": u_k})
    rows, angles = [], []
    for run in RUNS:
        v = saved[f"v_{run}"][:n]
        p_net, _ = body_positions(v, R, row_times)
        cam = p_net + R @ arm
        ws = []
        for w in wins:
            d = cam[w["k"]] - cam[w["a"]]
            ok = w["ok_vis"] and np.linalg.norm(d) >= 0.05
            ws.append({**w, "ok": ok})
            if ok and np.linalg.norm(w["true_cam"]) > 0.05:
                tu = true_dir[(w["a"], w["k"])]
                deg = lambda x: float(np.degrees(np.arccos(np.clip(x @ tu, -1, 1)))) if x is not None else np.nan
                angles.append((run, deg(unit(d)), deg(w["u_e"]), meta["motion"], deg(w["u_k"])))
        outs = fuse(v, R, row_T_bc, row_times, ws, true_dir)
        p_t, _ = body_positions(v_true, R, row_times)
        outs["o_truevel"] = to_output(p_t, R, row_T_bc)
        r = {**meta, "run": run, "gated_windows": int(sum(w["ok"] for w in ws)), "windows": len(ws)}
        for arm_name, p in outs.items():
            r[arm_name] = metrics(p, cam_gt, row_times)["ate"]
            for horizon in (30, 60):
                keep = int(np.sum(row_times - row_times[0] <= horizon + 1e-6))
                if row_times[-1] - row_times[0] >= horizon - 0.1:
                    r[f"{arm_name}_{horizon}s"] = metrics(p[:keep], cam_gt[:keep], row_times[:keep])["ate"]
        rows.append(r)
    info = {"parity_rad": parity, "accepted": count["accepted"],
            "branches": {b: sum(1 for w in wins if w["rec"]["branch"] == b) for b in ("essential", "rotation", "cheirality-fail", None)},
            "vis_ok": sum(w["ok_vis"] for w in wins), "windows": len(wins)}
    return rows, {meta["file"]: info}, angles


def _set_direction(d):
    global DIRECTION
    DIRECTION = d


def main():
    from odometry_data import load_row, motion_labels
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", choices=("public", "campaign-dev"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--direction", choices=("essential", "knownrot"), default="essential")
    args = parser.parse_args()
    global DIRECTION
    DIRECTION = args.direction
    cv2.setNumThreads(1)
    if args.set == "public":
        root = Path("/data/backups/rganapa/Sebastian/baselines/public-prepared")
        records = json.loads((root / "records.json").read_text())["records"]
        archive = lambda r: next(Path("/data/backups/rganapa/Sebastian/tmp/viobench-public-replay").glob(f"*/{r['parent_file']}"))
    else:
        root = Path("data/native-campaign/shards")
        records = json.loads(Path("data/native-campaign/dev-records.json").read_text())["records"]
        archive = lambda r: Path("/data/backups/rganapa/Sebastian/gen/raw/dev") / r["parent_file"]
    records = records[:args.limit]
    jobs = []
    for record in records:
        row = load_row(root, record)
        lab = motion_labels(row["v"], row["times"], row["cam_gt"])
        meta = {"file": record["file"], "scene": record["scene"], "catalog": record.get("catalog"),
                "start": "moving" if record.get("crop_s") else "static", "seconds": float(row["times"][-1] - row["times"][0]),
                "motion": "backward/lateral" if lab["backward"].mean() > .05 or lab["lateral"].mean() > .1 else "ordinary"}
        jobs.append((archive(record), float(record.get("crop_s", 0)), SAVED / args.set / "attitudes" / f"{record['file']}.npz",
                     row["times"], row["T_bc"], row["cam_gt"], row["v"].astype(np.float64), meta))
    rows, info, angles = [], {}, []
    with ProcessPoolExecutor(args.workers, initializer=_set_direction, initargs=(args.direction,)) as pool:
        for r, i, a in pool.map(episode, jobs):
            rows += r; info.update(i); angles += a
            print(r[0]["file"][:12], r[0]["motion"], list(i.values())[0]["parity_rad"],
                  {x: round(float(np.mean([y[x] for y in r])), 3) for x in ARMS}, flush=True)
    summary = {}
    for group, sel in (("all", lambda r: True), ("ordinary", lambda r: r["motion"] == "ordinary"),
                       ("backward/lateral", lambda r: r["motion"] != "ordinary"),
                       ("static", lambda r: r["start"] == "static"), ("moving", lambda r: r["start"] == "moving"),
                       ("procthor", lambda r: r["catalog"] == "procthor"), ("hssd", lambda r: r["catalog"] == "hssd-val"),
                       ("N2", lambda r: r["run"].startswith("N2")), ("B-D0", lambda r: r["run"].startswith("B-D0"))):
        g = [r for r in rows if sel(r)]
        if g:
            summary[group] = {f"{a}{h}": round(float(np.mean([r[f'{a}{h}'] for r in g if f'{a}{h}' in r])), 4)
                              for a in ARMS for h in ("", "_30s", "_60s") if any(f"{a}{h}" in r for r in g)}
            summary[group]["replays"] = len(g)
    ang = np.array([(x[1], x[2], x[4]) for x in angles]) if angles else np.zeros((0, 3))
    diag = {"windows_angle_deg": {"net_median": float(np.median(ang[:, 0])), "vision_median": float(np.nanmedian(ang[:, 1])),
                                  "knownrot_median": float(np.nanmedian(ang[:, 2])), "knownrot_gt90_frac": float(np.nanmean(ang[:, 2] > 90)),
                                  "vision_better_frac": float(np.mean(ang[:, 1] < ang[:, 0])), "n": len(ang),
                                  "net_gt90_frac": float(np.mean(ang[:, 0] > 90)), "vision_gt90_frac": float(np.mean(ang[:, 1] > 90))},
            "parity_max_rad": max(i["parity_rad"] for i in info.values()),
            "vis_ok_frac": float(np.mean([i["vis_ok"] / max(i["windows"], 1) for i in info.values()]))}
    for motion in ("ordinary", "backward/lateral"):
        m = np.array([(x[1], x[2], x[4]) for x in angles if x[3] == motion])
        if len(m):
            diag[f"angle_{motion}"] = {"net_median": float(np.median(m[:, 0])), "vision_median": float(np.nanmedian(m[:, 1])),
                                       "knownrot_median": float(np.nanmedian(m[:, 2])), "knownrot_gt90_frac": float(np.nanmean(m[:, 2] > 90)),
                                       "net_gt90_frac": float(np.mean(m[:, 0] > 90)), "vision_gt90_frac": float(np.mean(m[:, 1] > 90)), "n": len(m)}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps({"set": args.set, "summary": summary, "diagnostics": diag,
                                                          "rows": rows, "windows": info}, indent=1))
    print(json.dumps({"summary": {k: v for k, v in summary.items()}, "diagnostics": diag}, indent=1))


if __name__ == "__main__":
    main()
