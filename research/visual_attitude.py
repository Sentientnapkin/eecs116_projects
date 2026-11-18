"""Causal visual attitude replay with frozen B-D0 body-frame velocity."""
import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
import torch

from odometry_data import load_row, motion_labels
from odometry_eval import integrate, load_weights, metrics, model_velocities
from orientation import exp_so3, fit_visual_rotation
from pairs import digest


def spread(points, shape):
    """Require features spanning both image axes and multiple image quadrants."""
    if len(points) < 20:
        return False
    xy = points / np.array(shape[::-1])
    occupied = np.unique((xy >= 0.5).astype(int), axis=0)
    return len(occupied) >= 3 and np.min(np.std(xy, axis=0)) >= 0.13


def visual_delta(first, last, K, relative):
    """Right-multiplicative camera correction for current-to-anchor rotation."""
    points = cv2.goodFeaturesToTrack(first, 100, 0.015, 4)
    if points is None or not spread(points[:, 0], first.shape):
        return None, "rejected"
    guess = cv2.perspectiveTransform(points, K @ relative.T @ np.linalg.inv(K))
    tracked, found, _ = cv2.calcOpticalFlowPyrLK(
        first, last, points, guess.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW
    )
    if tracked is None:
        return None, "rejected"
    back, returned, _ = cv2.calcOpticalFlowPyrLK(last, first, tracked, points.copy(),
                                                flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    if back is None:
        return None, "rejected"
    error = np.linalg.norm((back - points)[:, 0], axis=1)
    good = found.ravel().astype(bool) & returned.ravel().astype(bool) & (error < 0.8)
    old, new = points[good, 0], tracked[good, 0]
    if not spread(old, first.shape):
        return None, "rejected"

    flow = np.linalg.norm((tracked - guess)[good, 0], axis=1)
    if np.quantile(flow, 0.8) <= 1.25 and np.median(flow) <= 0.65:
        inverse = np.linalg.inv(K)
        rays = [np.c_[p, np.ones(len(p))] @ inverse.T for p in (old, new)]
        fit = fit_visual_rotation(*rays, relative)
        if fit is None or fit[1] > 0.012 or fit[3] < 0.1:
            return None, "rejected"
        return fit[0], "low_parallax"

    essential, mask = cv2.findEssentialMat(
        old, new, K, method=cv2.RANSAC, prob=0.999, threshold=0.6, maxIters=500
    )
    if essential is None or essential.shape != (3, 3):
        return None, "rejected"
    count, old_to_new, _, cheiral = cv2.recoverPose(essential, old, new, K, mask=mask)
    inliers = cheiral.ravel().astype(bool)
    if count < 0.6 * len(old) or not spread(old[inliers], first.shape):
        return None, "rejected"
    inverse = np.linalg.inv(K)
    ray_old = np.c_[old[inliers], np.ones(inliers.sum())] @ inverse.T
    ray_new = np.c_[new[inliers], np.ones(inliers.sum())] @ inverse.T @ old_to_new
    cos_angle = (ray_old * ray_new).sum(1) / (
        np.linalg.norm(ray_old, axis=1) * np.linalg.norm(ray_new, axis=1)
    )
    if np.median(np.arccos(np.clip(cos_angle, -1, 1))) < 0.015:
        return None, "rejected"
    return cv2.Rodrigues(relative.T @ old_to_new.T)[0].ravel(), "essential"


def correct_attitude(images, times, rotation, K, body_from_camera):
    """Keep gyro increments and apply visual updates at causal half-second boundaries."""
    corrected = rotation.copy()
    anchors = np.full(len(times), -1, dtype=np.int64)
    anchor = 0
    count = Counter()
    for k in range(1, len(times)):
        corrected[k] = corrected[k - 1] @ (rotation[k - 1].T @ rotation[k])
        if times[k] - times[anchor] < 0.5 - 1e-8:
            continue
        relative = body_from_camera.T @ (rotation[anchor].T @ rotation[k]) @ body_from_camera
        delta, method = visual_delta(images[anchor], images[k], K, relative)
        if delta is not None and np.linalg.norm(delta) <= 0.12:
            corrected[k] = corrected[k] @ exp_so3(0.35 * body_from_camera @ delta)
            anchors[k] = anchor
            count[method] += 1
        else:
            count["rejected"] += 1
        anchor = k
    return corrected, anchors, dict(count)


def camera_matrix(record, ledger, raw_dev, shape):
    if "parent_file" in record:
        # Read calibration only. The prepared row contains the exact replay frames.
        archive = raw_dev / Path(record["parent_file"]).name
        with ZipFile(archive) as episode:
            metadata = next(name for name in episode.namelist() if name.endswith("/episode.json"))
            config = json.loads(episode.read(metadata))["config"]
        K = config["camera"]
        width, height = config["image"]["width"], config["image"]["height"]
    else:
        K = ledger[record["parent_sha256"]]["K"]
        width, height = K["width"], K["height"]
    sy, sx = shape[0] / height, shape[1] / width
    return np.array([[K["fx"] * sx, 0, (K["cx"] + 0.5) * sx - 0.5],
                     [0, K["fy"] * sy, (K["cy"] + 0.5) * sy - 0.5],
                     [0, 0, 1]])


def summarize(rows):
    groups = {"all": rows}
    for field in ("start", "catalog", "motion"):
        for key in sorted({r[field] for r in rows if r[field]}):
            groups[key] = [r for r in rows if r[field] == key]
    for catalog in sorted({r["catalog"] for r in rows if r["catalog"]}):
        for start in ("static", "moving"):
            groups[f"{catalog}/{start}"] = [r for r in rows if r["catalog"] == catalog and r["start"] == start]
    return {
        key: {method: float(np.mean([r[method] for r in group])) for method in ("control", "visual")}
        for key, group in groups.items() if group
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs=3, type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, default=Path("data/hub-cache/B-D0-ssm-x3-gpu"))
    parser.add_argument("--raw-dev", type=Path, required=True)
    parser.add_argument("--set", choices=("dev", "campaign-dev"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    cv2.setNumThreads(1)
    cv2.setRNGSeed(217)
    torch.set_num_threads(2)
    ledger = {r["sha256"]: r for r in json.loads(Path("data/ledger/ledger.json").read_text())["rows"]}
    if args.set == "dev":
        manifest = args.cache_root / "manifests/teacher-full.json"
        records = json.loads(manifest.read_text())["datasets"]["development"]
        shards = args.cache_root / "shards"
    else:
        campaign = Path("data/native-campaign")
        records = json.loads((campaign / "dev-records.json").read_text())["records"]
        if any(r["split"] != "dev" for r in records):
            raise ValueError("Campaign replay requires dev records")
        shards = campaign / "shards"
    weights = [load_weights(run, "best") for run in args.runs]
    checkpoint_sha256 = {run.name: digest(run / "best.safetensors") for run in args.runs}
    rows = []
    args.output.mkdir(parents=True, exist_ok=True)
    for record in records:
        row = load_row(shards, record)
        if args.set == "campaign-dev":
            keep = np.searchsorted(row["times"], 30 + 1e-6, side="right")
            row = {k: v if k == "T_bc" else v[:keep] for k, v in row.items()}
        images = row["images"][:, 0]
        K = camera_matrix(record, ledger, args.raw_dev, images.shape[1:])
        if not np.isclose(row["imu"][0, 14], K[0, 0] / images.shape[2], atol=1e-6):
            raise ValueError(f"Prepared focal length does not match calibration for {record['file']}")
        rotation, anchors, count = correct_attitude(images, row["times"], row["R"], K, row["T_bc"][:3, :3])
        labels = motion_labels(row["v"], row["times"], row["cam_gt"])
        motion = "backward/lateral" if labels["backward"].mean() > .05 or labels["lateral"].mean() > .1 else "ordinary"
        velocities = []
        for run, checkpoint in zip(args.runs, weights):
            velocity = model_velocities(run, checkpoint, row, args.device)
            velocities.append(velocity)
            control = integrate(velocity, row)
            visual = integrate(velocity, {**row, "R": rotation})
            rows.append({"file": record["file"], "scene": record["scene"], "run": run.name,
                         "catalog": record.get("catalog"), "motion": motion,
                         "start": "moving" if record["crop_s"] else "static",
                         "control": metrics(control, row["cam_gt"], row["times"])["ate"],
                         "visual": metrics(visual, row["cam_gt"], row["times"])["ate"],
                         "updates": count})
        np.savez(args.output / record["file"], velocity=np.stack(velocities), rotation=rotation, anchors=anchors)
        print(record["file"], count, flush=True)
    summary = summarize(rows)
    passed = None
    if args.set == "dev":
        passed = summary["all"]["visual"] <= 0.90 * summary["all"]["control"] and all(
            summary[group]["visual"] <= 1.05 * summary[group]["control"]
            for group in ("ordinary", "static", "moving")
        )
    summary["by_run"] = {run.name: summarize([r for r in rows if r["run"] == run.name])
                         for run in args.runs}
    report = {"set": args.set, "checkpoint_sha256": checkpoint_sha256,
              "dev_gate_passed": passed, "summary": summary, "rows": rows}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
