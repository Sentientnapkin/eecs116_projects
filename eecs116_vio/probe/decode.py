"""Decode a probe submission's per-episode results (probe.c) into episode statistics.

    python decode.py RESULTS.json [OUT.json]     # server /submissions/<id> JSON, or a local report.json

Two channels (README.md):
  * fuel: frames 590.. burn W + C * (N_g + payload << 2); the median, p95, p99, max and total each carry one payload,
    init carries the intrinsics. W, C and the offsets below were measured locally (calib_check.py) and are exact.
  * metrics: the probe's outputs make each error metric measure one ground-truth quantity.
"""
import json
import math
import sys

FRAMES = 1200
W_BASE = 4496894          # fuel of every ordinary frame before burning
C = 11                    # fuel per burn iteration
R589, R1129 = 314, 819    # extra fuel of the two payload frames
INIT_BASE = 43_500        # init fuel before burning, +-300 with config parsing (quantum 11 * 1024 = 11,264)
N1, N2, N3, N4, NI = 1 << 16, 1 << 23, 1 << 26, 1 << 29, 1 << 12
SH, SHI = 2, 10
VBIG = WBIG = 1.0e6


def unlin(q, lo, hi, levels):
    return lo + q / (levels - 1) * (hi - lo)


def unlog(q, lo2, hi2, bits):
    return 2.0 ** unlin(q, lo2, hi2, 1 << bits)


def bits(x, shift, n):
    return (x >> shift) & ((1 << n) - 1)


def payload(fuel, n_base):
    """(payload, ok): ok means the 2 guard bits are zero and the value is an exact integer."""
    burned = fuel - W_BASE
    if burned % C:
        return None, False
    n = burned // C - n_base
    return n >> SH, n >= 0 and n % (1 << SH) == 0


def unbin(q):
    return None if q == 0 else unlin(q - 1, 0.2, 1.1, 63)


def decode_episode(e):
    m = e["metrics"]
    out = {"hash": e.get("hash"), "frames": m["frames"], "completed": e.get("completed"), "checks": {}}
    ck = out["checks"]
    if m["frames"] != FRAMES or e.get("frames_attempted", FRAMES) != FRAMES:
        ck["frames"] = False
        return out
    # ---- fuel channel
    med, p95, p99, mx = (int(round(e[k])) for k in ("fuel_per_frame_median", "fuel_per_frame_p95",
                                                     "fuel_per_frame_p99", "fuel_per_frame_max"))
    X1, ck["median"] = payload(med, N1)
    X2, ck["p95"] = payload(p95, N2)
    X3, ck["p99"] = payload(p99, N3)
    X4, ck["max"] = payload(mx, N4)
    ck["max_magic"] = X4 is not None and (X4 & 0xF) == 0xA
    xi = (e["fuel_init"] - INIT_BASE - C * NI) / (C * (1 << SHI))
    XI = int(round(xi))
    ck["init"] = abs(xi - XI) < 0.2
    if None in (X1, X2, X3, X4):
        return out
    n_sum = 540 * (N1 + (X1 << SH)) + 55 * (N2 + (X2 << SH)) + 14 * (N3 + (X3 << SH)) + N4 + (X4 << SH)
    rest = e["fuel_total"] - FRAMES * W_BASE - R589 - R1129 - C * n_sum
    X0 = rest // (C << SH) if rest % (C << SH) == 0 else None
    ck["total"] = X0 is not None and X0 >= 0

    fx = 60 + bits(XI, 0, 15) * 0.01
    out["camera"] = {"fx_320": round(fx, 2), "hfov_deg": round(math.degrees(2 * math.atan(160 / fx)), 3),
                     "T_cam_imu_default": bool(bits(XI, 15, 1)), "centred_square": bool(bits(XI, 16, 1))}
    out["start_1s"] = {"gyro_rms": unlog(bits(X1, 0, 6), -9, 1, 6), "accel_dev_rms": unlog(bits(X1, 6, 5), -8, 3, 5)}
    out["imu_noise"] = {"gyro_sigma": unlog(bits(X1, 11, 7), -11, -1, 7), "accel_sigma": unlog(bits(X3, 18, 7), -10, 0, 7)}
    out["dark_frames_first_half"] = ["0", "1-2", "3-20", ">20"][bits(X1, 18, 2)]
    out["image"] = {"Y_mean": unlin(bits(X2, 0, 6), 0, 255, 64), "chroma_g": unlin(bits(X2, 6, 5), 0.18, 0.50, 32),
                    "chroma_b": unlin(bits(X2, 11, 5), 0.18, 0.50, 32), "grad2_mean": unlog(bits(X2, 16, 7), -2, 12, 7)}
    out["blur_ratio_x_by_px_speed"] = [unbin(bits(X4, 4 + 6 * i, 6)) for i in range(3)]   # bins <60, 60-200, >200 px/s
    out["blur_ratio_y_by_px_speed"] = [unbin(bits(X3, 6 * i, 6)) for i in range(3)]
    out["dynamics"] = {"jerk_rms": unlog(bits(X4, 22, 6), -1, 9, 6)}
    if X0 is not None:
        out["dynamics"] |= {"gyro_rms": unlog(bits(X0, 0, 6), -6, 2, 6), "yaw_rms": unlog(bits(X0, 6, 6), -7, 2, 6),
                            "accel_xy_rms": unlog(bits(X0, 12, 6), -4, 4, 6)}
        out["image"] |= {"Y_top": unlin(bits(X0, 18, 4), 0, 255, 16), "Y_bottom": unlin(bits(X0, 22, 4), 0, 255, 16)}
    out["payloads"] = [XI, X1, X2, X3, X4, X0]

    # ---- metrics channel (ground truth)
    n = FRAMES
    ate, sim3 = m["ate_rmse"], m["sim3_ate_rmse"]
    speed_sq = m["rpe_translation_rmse"] ** 2   # 1 s displacement ~ speed, for the small correction terms only
    out["path"] = {"distance": m["distance_travelled"], "mean_speed": m["distance_travelled"] / e.get("duration_s", 59.95),
                   "rms_dist_from_start": ate, "final_dist_from_start": m["final_drift"], "rms_spread": sim3,
                   "centroid_dist_from_start": math.sqrt(max(ate ** 2 - sim3 ** 2, 0)),
                   "rms_1s_displacement": m["rpe_translation_rmse"]}
    out["start_forward_speed"] = (VBIG ** 2 + n * speed_sq - n * m["velocity_rmse"] ** 2) / (2 * VBIG)
    out["gyro_bias_cam_y"] = (n * m["angular_velocity_rmse"] ** 2 - n * WBIG ** 2) / (2 * WBIG * n)
    out["gyro_drift"] = {"rot_rmse_deg": math.degrees(m["rotation_rmse"]), "rot_max_deg": math.degrees(m["rotation_max"]),
                         "rpe_rot_deg_per_s": math.degrees(m["rpe_rotation_rmse"])}
    ck["sim3_scale_1"] = abs(m["sim3_scale"] - 1) < 1e-9
    return out


def episodes_of(data):
    if "results" in data:
        data = data["results"]
    return data["episodes"]


def main():
    data = json.load(open(sys.argv[1]))
    decoded = [decode_episode(e) for e in episodes_of(data)]
    for d in decoded:
        bad = [k for k, v in d["checks"].items() if not v]
        if "camera" not in d:
            print(f"{str(d['hash'])[:8]} NOT DECODED {bad}"); continue
        c, p, im, dy = d["camera"], d["path"], d["image"], d["dynamics"]
        print(f"{str(d['hash'])[:8]} fov {c['hfov_deg']:6.2f}  dist {p['distance']:5.1f} v0z {d['start_forward_speed']:5.2f} "
              f"Y {im['Y_mean']:5.1f} g {im['chroma_g']:.3f} b {im['chroma_b']:.3f} tex {im['grad2_mean']:7.1f} "
              f"blurX {['-' if v is None else f'{v:.3f}' for v in d['blur_ratio_x_by_px_speed']]} "
              f"sig_g {d['imu_noise']['gyro_sigma']:.4f} sig_a {d['imu_noise']['accel_sigma']:.4f} "
              f"yaw {dy.get('yaw_rms', float('nan')):.2f} b_y {d['gyro_bias_cam_y']:+.5f}  {'BAD ' + str(bad) if bad else 'ok'}")
    if len(sys.argv) > 2:
        json.dump(decoded, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
