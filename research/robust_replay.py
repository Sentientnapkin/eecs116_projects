"""Paired raw-observation development replay and trajectory measurements."""
import csv
from pathlib import Path

import numpy as np

from common import Flight, ate
from decompose import joint_payload
from learned_probe import open_run, write
from pairs import digest, variant_rows
from streaming import Estimator


def cropped(flight, crop, count=None):
    """Select an observed prefix, resetting packets and truth gauge at its first frame."""
    from copy import copy
    first = np.searchsorted(flight.ft, crop-1e-8)
    stop = len(flight.ft) if count is None else first+count
    window = slice(first, stop)
    segment = copy(flight)
    segment.realized_crop = float(flight.ft[first])
    segment.ft = flight.ft[window]-flight.ft[first]
    segment.frames = flight.frames[window]
    segment.win = [np.empty((0,7))]
    for packet in flight.win[first+1:stop]:
        relative = packet.copy()
        relative[:,0] -= flight.ft[first]
        segment.win.append(relative)
    for name in ("p", "R", "v", "w", "v_body"):
        setattr(segment, name, getattr(flight, name)[window])
    segment.cam_gt = segment.camera_positions(segment.p, segment.R)
    return segment


def prepare_pixels(flight, cfg):
    """Memoize only per-image conversion, preserving sensor delivery intrinsics."""
    import cv2
    flight.delivery_shape = flight.frames[0].shape[:2]
    size = cfg["width"], cfg["height"]
    flight.frames = np.stack([
        cv2.resize(cv2.cvtColor(frame,cv2.COLOR_RGB2GRAY) if frame.ndim==3 else frame,
                   size, interpolation=cv2.INTER_AREA) for frame in flight.frames])
    return flight


def camera_config(flight):
    h, w = flight.delivery_shape if hasattr(flight, "delivery_shape") else flight.frames[0].shape[:2]
    T = np.eye(4)
    T[:3,:3] = flight.T_bc[:3,:3].T
    T[:3,3] = -T[:3,:3] @ flight.T_bc[:3,3]
    return {**flight.K, "width": w, "height": h, "T_cam_imu": T}


def replay(flight, rows, model, config):
    estimator = Estimator(camera_config(flight), model, config)
    orient = estimator.inputs.orient
    states, R, velocity, bias, cal, memory = [], [], [], [], [], []
    previous_state = None
    for t, frame, packet in rows:
        output = estimator.step(t, frame, packet)
        states.append(output)
        R.append(orient.R.copy())
        velocity.append(estimator.last_velocity)
        bias.append(np.r_[orient.bias, orient.learned_bias])
        cal.append(orient.activated)
        hidden = estimator.model.head.state if estimator.model.head else None
        if hidden is not None:
            update = hidden if previous_state is None else hidden-previous_state
            memory.append([np.linalg.norm(hidden), np.linalg.norm(update)])
            previous_state = hidden.copy()
        else:
            memory.append([0., 0.])
    states, R, velocity = map(np.asarray, (states, R, velocity))
    if len(states) != len(flight.ft) or not np.isfinite(states).all():
        raise ValueError("incomplete or nonfinite replay")
    angle = (np.einsum("nij,nij->n", R, flight.R[0].T @ flight.R)-1)/2
    translation = np.linalg.norm(states[:,:3]-flight.cam_gt, axis=1)
    attitude = np.arccos(np.clip(angle,-1,1))
    speed_error = np.linalg.norm(velocity-flight.v @ flight.R[0], axis=1)
    trajectory = {"t":flight.ft, "position_error_m":translation, "attitude_error_rad":attitude,
                  "velocity_error_m_s":speed_error, "bias_rad_s":np.asarray(bias),
                  "calibration":np.asarray(cal), "memory_norm":np.asarray(memory)}
    def rms(values):
        return float(np.sqrt(np.mean(values**2)))
    score = {"ate":ate(states[:,:3],flight.cam_gt), "velocity_rmse_m_s":rms(speed_error),
             "attitude_rmse_rad":rms(attitude), "first_1s_ate":rms(translation[flight.ft<=1]),
             "first_3s_ate":rms(translation[flight.ft<=3]), "duration_s":float(flight.ft[-1]),
             "accepted_s":orient.accepted_at, "calibration_accepted":bool(orient.activated),
             "calibration_rejections":orient.rejected_windows,
             "calibration_checks":orient.checked_windows,
             "initial_speed_m_s":float(np.linalg.norm(flight.v[0])),
             "initial_yaw_rate_rad_s":float(flight.w[0,2])}
    return score, trajectory


def load_models(checkpoints, cfg_override=None):
    models = {}
    for name, seed, path in checkpoints:
        model, config = joint_payload(path)
        if cfg_override:
            config.update(cfg_override)
        models[name,seed] = model, config
        if name == "bias":
            models["bias-disabled",seed] = {**model,"settings":{**model["settings"],"feedback":False}}, config
    return models


def matrix(args, settings, parents, checkpoints):
    plan = settings["stress"]
    if args.fixed:
        settings = {**settings, "portable_pixels": "remap"}
    directory, manifest = open_run("robust-matrix", settings, {"development":parents})
    print(directory, flush=True)
    manifest["checkpoints"] = [{"model":name, "seed":seed, "path":str(path), "sha256":digest(path)}
                               for name,seed,path in checkpoints]
    manifest["diagnostic_bias"] = "feedback on and off use identical weights"
    write(directory/"manifest.json", manifest)
    models = load_models(checkpoints, {"portable_pixels":"remap"} if args.fixed else None)
    records = []
    try:
        for parent in parents:
            if digest(parent["path"]) != parent["sha256"]:
                raise ValueError("development archive changed")
            flight = prepare_pixels(Flight(parent["path"]), next(iter(models.values()))[1])
            clean_bias = {}
            for crop in plan["crops_s"]:
                segment = cropped(flight, crop)
                for condition in plan["conditions"]:
                    # Replay each deterministic stream independently to bound image memory.
                    for (name, seed), (model, cfg) in models.items():
                        stream = variant_rows(segment, condition, plan["sensor_seed"])
                        score, trajectory = replay(segment, stream, model, cfg)
                        row = {"scene":parent["scene"],"model":name,"seed":seed,
                               "crop_s":crop,"realized_crop_s":segment.realized_crop,
                               "condition":condition,**score}
                        score_key = name, seed
                        if condition == "clean":
                            clean_bias[score_key] = trajectory["bias_rad_s"], score["ate"]
                        clean, baseline = clean_bias[score_key]
                        row["ate_increase"] = score["ate"]-baseline
                        if condition in ("constant","changing","original-combined"):
                            from pairs import added_gyro, disturbance_seed
                            added = added_gyro(segment.ft,
                                               "changing" if condition == "original-combined" else condition,
                                               disturbance_seed(segment.path,{"disturbance_seed":plan["sensor_seed"]}))
                            residual = (trajectory["bias_rad_s"]-clean).reshape(-1,2,3).sum(1)-added
                            row["added_bias_rmse_rad_s"] = float(np.sqrt(np.mean(residual**2)))
                        prefix = f"{parent['scene']}-{crop}-{condition}-{name}-{seed}"
                        np.savez_compressed(directory/f"{prefix}.npz", **trajectory)
                        records.append(row)
            write(directory/"flights.json", records)
            print(parent["scene"], "complete", flush=True)
        lookup = {(r["scene"],r["crop_s"],r["condition"],r["seed"]):r["ate"]
                  for r in records if r["model"]=="ema"}
        for r in records:
            control = lookup.get((r["scene"],r["crop_s"],r["condition"],r["seed"]))
            r["paired_delta_vs_ema"] = None if control is None else r["ate"]-control
        with (directory/"paired.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in records for k in r)))
            writer.writeheader()
            writer.writerows(records)
        write(directory/"flights.json", records)
        manifest["status"] = "completed"
    except BaseException as error:
        manifest.update(status="failed", error=repr(error))
        raise
    finally:
        write(directory/"manifest.json", manifest)
