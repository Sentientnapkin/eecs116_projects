"""Paired native OpenVINS stationary-aiding replay on the 30 s campaign development roster."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from viobench.tools.datasets.storage import read_episode

from common import Flight, ate
from odometry_data import motion_labels
from odometry_store import digest
from robust_replay import cropped


def write_observations(path, flight, imu):
    """Binary little-endian camera calibration, then timestamp/IMU/grayscale per frame."""
    h, w = flight.frames[0].shape[:2]
    intrinsics = [flight.K[key] for key in ("fx", "fy", "cx", "cy")] + [0.0] * 4
    rate_scale = np.sqrt(imu["rate_hz"])
    noise = (imu["gyro_noise_std"] / rate_scale, imu["gyro_bias_random_walk"] * rate_scale,
             imu["accel_noise_std"] / rate_scale, imu["accel_bias_random_walk"] * rate_scale)
    with path.open("wb") as out:
        out.write(struct.pack("<III", w, h, len(flight.ft)))
        for values in (intrinsics, flight.T_bc[:3, :3], flight.T_bc[:3, 3], noise):
            out.write(np.asarray(values, dtype="<f8").tobytes())
        for time, packet, image in zip(flight.ft, flight.win, flight.frames, strict=True):
            if (packet[:, 0] > time + 1e-7).any():
                raise ValueError(f"IMU packet includes measurements after frame at {time}")
            packet = np.array(packet, dtype="<f8", copy=True)
            packet[:, 0] = np.minimum(time, packet[:, 0])
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
            out.write(struct.pack("<dI", time, len(packet)))
            out.write(packet.tobytes())
            out.write(gray.tobytes())


def camera_trajectory(positions, rotations, valid, gyro, extrinsic):
    """Use the first usable pose and pre-init gyro rotation to set the causal camera gauge."""
    trajectory = np.zeros_like(positions)
    valid_indices = np.flatnonzero(valid)
    if len(valid_indices) == 0:
        return trajectory
    first = valid_indices[0]
    camera_to_body, lever = extrinsic[:3, :3], extrinsic[:3, 3]
    world_camera0 = rotations[first] @ gyro[first].T @ camera_to_body
    camera_centres = positions[valid] + rotations[valid] @ lever
    relative = (camera_centres - camera_centres[0]) @ world_camera0
    # Emit zero before the first usable estimate. If any later frame is stale, hold the last output.
    latest = np.searchsorted(valid_indices, np.arange(first, len(valid)), side="right") - 1
    trajectory[first:] = relative[latest]
    return trajectory


def replay_parent(job):
    raw, records, shard_root, runner, work_root = job
    if digest(raw) != records[0]["parent_sha256"]:
        raise ValueError(f"Raw archive checksum mismatch: {raw}")
    cv2.setNumThreads(1)
    imu = read_episode(raw).config["imu"]
    flight = Flight(raw)
    rows = []
    with TemporaryDirectory(prefix=raw.stem + "-", dir=work_root) as directory:
        path = Path(directory)
        obs = path / "observations.bin"
        states = path / "states.csv"
        for record in records:
            crop = record["crop_s"]
            first = int(np.searchsorted(flight.ft, crop - 1e-8))
            stop = int(np.searchsorted(flight.ft, flight.ft[first] + 30.0 + 1e-6, side="right"))
            segment = cropped(flight, crop, stop - first)
            with np.load(shard_root / record["file"], allow_pickle=False) as shard:
                keep = int(np.sum(shard["times"] - shard["times"][0] <= 30.0 + 1e-6))
                if len(segment.ft) != keep or not np.allclose(segment.ft, shard["times"][:keep], atol=1e-5):
                    raise ValueError(f"Frame times differ from paired B-D0 crop {raw} at {crop}")
                if not np.allclose(segment.cam_gt, shard["cam_gt"][:keep], atol=1e-4):
                    raise ValueError(f"Truth differs from paired B-D0 crop {raw} at {crop}")
            labels = motion_labels(segment.v_body, segment.ft, segment.cam_gt)
            ordinary = labels["backward"].mean() <= .05 and labels["lateral"].mean() <= .1
            gyro = segment.gyro_attitude()
            write_observations(obs, segment, imu)
            for zupt in (0, 1):
                states.unlink(missing_ok=True)
                result = subprocess.run([runner, obs, states, str(zupt)], capture_output=True, text=True)
                complete = np.loadtxt(states, delimiter=",", ndmin=2) if states.is_file() and states.stat().st_size else np.empty((0, 15))
                n = len(complete)
                if complete.shape != (n, 15) or n > len(segment.ft) or not np.allclose(complete[:, 0], segment.ft[:n]):
                    raise ValueError(f"OpenVINS emitted incomplete or mismatched frames: {raw} {crop} {zupt}")
                if n < len(segment.ft) and result.returncode == 0:
                    raise ValueError(f"OpenVINS exited successfully with missing frames: {raw} {crop} {zupt}")
                # A native failure leaves any already emitted poses intact. Hold the last pose
                # for the remainder so difficult replays stay in the scored roster.
                data = np.zeros((len(segment.ft), 15))
                data[:n] = complete
                valid = data[:, 1].astype(bool)
                if not np.isfinite(data[valid]).all():
                    raise ValueError(f"OpenVINS emitted nonfinite pose: {raw} {crop} {zupt}")
                if zupt == 0 and data[:, 2].any():
                    raise ValueError("OpenVINS reported a stationary update with ZUPT disabled")
                p = camera_trajectory(data[:, 3:6], data[:, 6:].reshape(-1, 3, 3), valid, gyro, segment.T_bc)
                rows.append({"zupt": bool(zupt), "scene": record["scene"], "parent": raw.name,
                             "crop_s": crop, "start": "static" if crop == 0 else "moving",
                             "catalog": record["catalog"], "ordinary": bool(ordinary), "ate": ate(p, segment.cam_gt),
                             "zero_ate": ate(np.zeros_like(p), segment.cam_gt),
                             "first_estimate_s": float(segment.ft[np.argmax(valid)]) if valid.any() else None,
                             "coverage": float(valid.mean()), "zupt_updates": int(data[:, 2].sum()),
                             "runner_error": result.stderr.strip()[-1000:] if result.returncode else None,
                             "emitted_frames": n,
                             "initial_truth_speed_m_s": float(np.linalg.norm(segment.v[0]))})
    return rows


def summarize(rows):
    def mean(items, key="ate"):
        return float(np.mean([row[key] for row in items])) if items else None

    arms = {}
    for flag in (False, True):
        arm = [row for row in rows if row["zupt"] == flag]
        arms["zupt-on" if flag else "zupt-off"] = {
            "equal_flight_mean_ate": mean(arm),
            "ordinary_ate": mean([row for row in arm if row["ordinary"]]),
            "static_start_ate": mean([row for row in arm if row["start"] == "static"]),
            "moving_start_ate": mean([row for row in arm if row["start"] == "moving"]),
            "procTHOR_ate": mean([row for row in arm if row["catalog"] == "procthor"]),
            "hssd_val_ate": mean([row for row in arm if row["catalog"] == "hssd-val"]),
            "no_estimate_replays": sum(row["first_estimate_s"] is None for row in arm),
            "runner_error_replays": sum(row["runner_error"] is not None for row in arm),
            "mean_coverage": mean(arm, "coverage"),
            "zupt_updates": sum(row["zupt_updates"] for row in arm),
        }
    return arms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--raw-dev", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    manifest = json.loads(args.records.read_text())
    by_parent = {}
    for record in manifest["records"]:
        if record["split"] != "dev" or record["crop_s"] not in (0, 5):
            raise ValueError("Expected only the predeclared campaign development crops")
        by_parent.setdefault(record["parent_file"], []).append(record)
    if len(by_parent) != 60 or any(sorted(r["crop_s"] for r in recs) != [0, 5] for recs in by_parent.values()):
        raise ValueError("Expected exactly 60 development parents with both crops")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    shard_root = args.records.parent / "shards"
    jobs = [(args.raw_dev / name, recs, shard_root, args.runner.resolve(), args.work_dir)
            for name, recs in sorted(by_parent.items())]
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for index, pair in enumerate(pool.map(replay_parent, jobs, chunksize=1), 1):
            rows.extend(pair)
            print(f"{index}/{len(jobs)} parents complete", flush=True)

    controls = json.loads(args.baseline.read_text())["summary"]
    baseline = [controls[name] for name in ("B-D0-ssm-x3-gpu", "B-D0-ssm-x3-s218-gpu", "B-D0-ssm-x3-s219-gpu")]
    keys = ("equal_flight_mean_ate", "ordinary_ate", "static_start_ate", "moving_start_ate")
    control = {key: float(np.mean([row[key] for row in baseline])) for key in keys}
    arms = summarize(rows)
    for arm in arms.values():
        arm["advance_to_wasm"] = (arm["equal_flight_mean_ate"] <= .90 * control["equal_flight_mean_ate"]
                                  and arm["ordinary_ate"] <= 1.05 * control["ordinary_ate"])
    summary = {"B-D0-ssm-x3": control, **arms}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
