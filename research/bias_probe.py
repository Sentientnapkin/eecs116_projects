"""Non-overlapping visual/gyro rotation updates with controlled sample-level bias."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from common import Flight
from learned_probe import network, open_run, predictions, read_inputs, score, write
from orientation import Orientation, exp_so3, rotation_proposal
from pairs import config, digest

WINDOW = .5


def injected_bias(times, case):
    b = np.array([.018, -.026, .041])
    if case == "constant":
        return np.broadcast_to(b, (len(times), 3))
    if case == "changing":
        return b + .025*np.sin(times[:, None] * np.array([.19, .13, .17]) + [0, 1, 2])
    return np.zeros((len(times), 3))


def rollout(f, cfg, case, method="baseline", coefficients=None):
    R_bc = f.T_bc[:3,:3]
    K = np.array([[f.K["fx"], 0, f.K["cx"]], [0, f.K["fy"], f.K["cy"]], [0,0,1.]])
    state = Orientation(cfg)
    history = []
    events = []
    previous = f.frames[0]
    anchor = 0
    for i, (t, image, raw) in enumerate(zip(f.ft, f.frames, f.win)):
        packet = raw.copy()
        packet[:,4:7] += injected_bias(packet[:,0], case)
        observed = cv2.resize(image, (32,24), interpolation=cv2.INTER_AREA).astype(np.float32)
        preceding = cv2.resize(previous, (32,24), interpolation=cv2.INTER_AREA)
        R = state.step(t, packet, np.abs(observed-preceding).mean()/255)
        previous = image
        if t-f.ft[anchor] >= WINDOW-1e-8:
            relative = history[anchor].T @ R
            local_truth = f.R[anchor].T @ f.R[i]
            target = cv2.Rodrigues(relative.T @ local_truth)[0].ravel()
            record = {"duration": float(t-f.ft[anchor]), "target_rad": target.tolist(), "accepted": False,
                      "speed": float(np.linalg.norm(f.v[i])), "turn_rate": float(np.linalg.norm(f.w[i]))}
            feat, gated, update = rotation_proposal(f.frames[anchor], image, K, R_bc, relative,
                                                       state.bias, record["duration"], method, coefficients)
            if feat is not None:
                record["features"] = feat.tolist()
                if gated and method != "baseline":
                    R = R @ exp_so3(update)
                    state.R = R
                    record["accepted"] = True
                record.update(gate=gated, correction_rad=update.tolist())
            events.append(record)
            anchor = i
        history.append(R)
    return np.asarray(history), events, state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("visual_run", type=Path)
    p.add_argument("--policy", choices=("none","startup","evidence"))
    args = p.parse_args()
    import torch
    from seq_heads import winner
    torch.set_num_threads(4)
    prior = json.loads((args.visual_run/"manifest.json").read_text())
    input_cfg, groups = prior["config"], prior["datasets"]
    cfg = {**input_cfg, "policy": args.policy or input_cfg["policy"]}
    chosen = json.loads((args.visual_run/"scores.json").read_text())
    variant = winner(chosen)
    ck = next(r for r in chosen if r["variant"] == variant and r["seed"] == cfg["seeds"][0])
    net = network(ck["checkpoint"])
    out, m = open_run("rotation", cfg, groups)
    m.update(visual_run=str(args.visual_run), checkpoint_sha256=digest(ck["checkpoint"]))
    print(out, flush=True)
    try:
        x, y = [], []
        for row in groups["train"][::2]:
            f = Flight(row["path"])
            for case in ("constant", "changing"):
                _, events, _ = rollout(f, cfg, case)
                for event in events:
                    if event.get("gate"):
                        x.append([*event["features"], 1.])
                        y.append(event["target_rad"])
        x, y = np.asarray(x), np.asarray(y)
        if not len(x):
            raise RuntimeError("no accepted training rotations")
        ridge = np.eye(x.shape[1]) * .1
        ridge[-1,-1] = 0.
        coef = np.linalg.solve(x.T @ x + ridge, x.T @ y)
        np.save(out/"ridge.npy", coef)
        m.update(rotation_model_sha256=digest(out/"ridge.npy"), training_windows=len(x),
                 rotation_label="Log(R_relative_est^T R_relative_truth), radians",
                 injection="added per sample; constant and time-varying; native physical bias unobserved")
        results = []
        for crop in (0., 5.):
            cached = read_inputs(groups["development"], input_cfg, crop)
            for row in cached:
                f = Flight(row["path"], crop=crop)
                v = predictions(net, row)
                native_bias = None
                for case in ("native", "constant", "changing"):
                    for method in ("baseline", "geometry", "learned"):
                        R, events, state = rollout(f, cfg, case, method, coef)
                        metrics = score(row, v, R)
                        residual = [
                            np.linalg.norm(cv2.Rodrigues(
                                exp_so3(-np.asarray(e.get("correction_rad", [0,0,0]))) @
                                exp_so3(np.asarray(e["target_rad"])))[0])
                            for e in events
                        ]
                        if case == "native" and method == "baseline":
                            native_bias = state.bias.copy()
                        startup = f.imu[:, 0] <= cfg["startup_seconds"]
                        added = injected_bias(f.imu[startup, 0], case).mean(0)
                        # Paired subtraction removes the unknown native calibration contribution.
                        relative = float(np.linalg.norm(state.bias-native_bias-added))
                        metrics.update(method=method, case=case, accepted=sum(e["accepted"] for e in events),
                                       windows=len(events), startup_calibrated=state.activated,
                                       bias_difference_to_injected_rad_s=relative if case != "native" else None,
                                       relative_rotation_residual_rms=float(np.sqrt(np.mean(np.square(residual)))),
                                       accepted_stationary=sum(e["accepted"] and e["speed"] < .15 for e in events),
                                       accepted_turning=sum(e["accepted"] and e["turn_rate"] > .25 for e in events),
                                       accepted_translating=sum(e["accepted"] and e["speed"] >= .15 for e in events))
                        results.append(metrics)
                write(out/"scores.json", results)
            print("finished crop", crop, flush=True)
        m["status"] = "completed"
    except BaseException as e:
        m.update(status="failed", error=repr(e))
        raise
    finally:
        write(out/"manifest.json", m)


if __name__ == "__main__":
    main()
