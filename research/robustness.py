"""Reproducible development experiments for the selective estimator."""
import argparse
import base64
import json
from pathlib import Path

import cv2
import numpy as np

from decompose import CLASSICAL, archived_model, bundle_model
from learned_probe import open_run, write
from pairs import digest
from streaming import Estimator

HISTORICAL = Path("results/20261118T012810Z-joint-final-46206627")
FINALISTS = Path("results/20261118T005559Z-joint-finalists-5d4b4de0")
RUNTIME = CLASSICAL/"build/runtime.wasm"
TOLERANCE = {
    "time": 1e-12, "packet": 0., "integration_intervals": 1e-12,
    "intrinsics": 1e-12, "resized": 0., "image_difference": 1e-7,
    "homography_0": 1e-7, "homography_1": 1e-7, "images": 0.,
    "cal_bias": 1e-7, "learned_bias": 1e-7, "rotation": 1e-7, "imu": 1e-6,
    "embedding": 2e-5, "state": 2e-5, "prediction": 2e-5,
    "body_position": 5e-4, "camera": 5e-4, "output": 5e-4,
}
TRACE_ORDER = ("time", "delivered", "packet", "intrinsics", "resized", "image_difference",
               "integration_intervals", "accepted", "calibrated", "cal_bias", "rotation",
               "homography_0", "homography_1", "images", "imu", "embedding", "state",
               "prediction", "learned_bias", "body_position", "camera", "output")


def decode(value):
    if isinstance(value, list):
        dtype, shape, encoded = value
        return np.frombuffer(base64.b64decode(encoded), dtype=dtype).reshape(shape)
    return value


def read_roster():
    manifest = json.loads((FINALISTS/"manifest.json").read_text())
    return manifest["datasets"], manifest["validation_roster"]


def parity(args):
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.runner.engine import Engine
    from viobench.tools.runner.sandbox import Sandbox
    _, development = read_roster()
    parents = development[:args.flights]
    model, cfg, identity = archived_model(HISTORICAL/"ssm")
    if args.fixed:
        cfg["portable_pixels"] = "remap" if args.fast else True
    directory, manifest = open_run("robust-parity", cfg, {"development": parents})
    manifest.update(frozen_weights=identity, runtime_sha256=digest(RUNTIME), tolerances=TOLERANCE)
    print(directory, flush=True)
    engine = Engine()
    wasm = bundle_model(directory/"diagnostic", model, cfg, RUNTIME, diagnostic=True)
    for parent in parents:
        if digest(parent["path"]) != parent["sha256"]:
            raise ValueError("development archive changed")
    records = []
    for parent in parents:
        ep = read_episode(parent["path"])
        guest = Sandbox(wasm, engine, log_dir=directory/parent["scene"])
        camera, frames = ep.adapt(guest.resolution)
        guest.init(camera)
        host = Estimator(json.loads(json.dumps(camera)), model, cfg)
        traces, poses, wasm_poses = {}, [], []
        for i, (t, frame, packet) in enumerate(ep.steps(frames)):
            host.trace = {} if i < 24 or i % 20 == 0 else None
            host.inputs.trace = host.model.trace = None
            output = host.step(t, frame, packet)
            result = guest.step(t, frame, packet)
            poses.append(output)
            wasm_poses.append(np.r_[result.pose, result.twist])
            if host.trace is not None:
                traces[i] = {**host.trace, "output": output}
        rows = [json.loads(line.removeprefix("TRACE ")) for line in guest.stdout_path.read_text().splitlines()
                if line.startswith("TRACE ")]
        if set(i for i, _ in rows) != traces.keys():
            raise RuntimeError("guest trace incomplete")
        differences, maxima, image_channels = {}, {}, []
        for i, fields in rows:
            for key in TRACE_ORDER:
                a = traces[i].get(key)
                b = decode(fields.get(key))
                if a is None or b is None or key == "delivered":
                    error = float(a != b) if not (isinstance(a, np.ndarray) or isinstance(b, np.ndarray)) else 1.
                else:
                    error = float(np.max(np.abs(np.asarray(a, dtype=float)-np.asarray(b, dtype=float)), initial=0.))
                if key == "images":
                    channel_error = np.max(np.abs(np.asarray(a,dtype=int)-np.asarray(b,dtype=int)),axis=(1,2))
                    if not image_channels and np.any(channel_error):
                        image_channels = {"frame":i,"max_abs_by_channel":channel_error.tolist()}
                maxima[key] = max(maxima.get(key, 0.), error)
                if error > TOLERANCE.get(key, 0.) and key not in differences:
                    differences[key] = {"frame": i, "max_abs": error}
        poses, wasm_poses = np.stack(poses), np.stack(wasm_poses)
        serialization = max(float(np.max(np.abs(decode(f["output"])-wasm_poses[i]))) for i,f in rows)
        error = np.linalg.norm(poses[:, :3]-wasm_poses[:, :3], axis=1)
        record = {"scene":parent["scene"], "sampled_frames":len(rows),
                  "first_by_stage":differences, "first_differing_image_channels":image_channels, "max_abs_by_stage":maxima,
                  "serialization_max":serialization, "position_delta_max_m":float(error.max()),
                  "position_delta_rms_m":float(np.sqrt(np.mean(error**2)))}
        records.append(record)
        write(directory/"parity.json", records)
        np.savez_compressed(directory/f"{parent['scene']}.npz", host=poses, guest=wasm_poses)
        print(parent["scene"], differences, record["position_delta_max_m"], flush=True)
    manifest["status"] = "completed"
    write(directory/"manifest.json", manifest)


def run_matrix(args):
    from robust_replay import matrix
    settings = json.loads(Path("robustness.json").read_text())
    _, parents = read_roster()
    checkpoints = [(name, seed, FINALISTS/f"{name}-{seed}.pt")
                   for name in ("ema","ssm","bias") for seed in (0,1,2)]
    matrix(args, settings, parents[:args.flights], checkpoints)


def run_deploy(args):
    from robust_deploy import deploy
    roster = read_roster()
    settings = json.loads(Path("robustness.json").read_text())
    deploy(args, roster[1][:args.flights], HISTORICAL, RUNTIME, settings, roster)


def run_training(args):
    from robust_train import train
    settings = json.loads(Path("robustness.json").read_text())
    train(args, settings, read_roster(), FINALISTS)


def run_start_probe(args):
    from common import Flight
    from robust_replay import cropped, load_models, prepare_pixels, replay
    from pairs import variant_rows
    settings = json.loads(Path("robustness.json").read_text())
    _, parents = read_roster()
    checkpoints = [("ssm", seed, FINALISTS/f"ssm-{seed}.pt") for seed in (0,1,2)]
    models = load_models(checkpoints, {"portable_pixels":"remap"})
    directory, manifest = open_run("robust-start-probe", settings, {"development":parents})
    print(directory,flush=True)
    results = []
    for parent in parents:
        if digest(parent["path"]) != parent["sha256"]:
            raise ValueError("development archive changed")
        flight = prepare_pixels(Flight(parent["path"]), models["ssm",0][1])
        for crop in (0,2,5,12):
            segment = cropped(flight,crop)
            for (name,seed),(model,cfg) in models.items():
                for cold in (False,True):
                    spec = {**model,"settings":{**model["settings"],"zero_initial_state":cold}}
                    score, trace = replay(segment,variant_rows(segment,"clean",651),spec,cfg)
                    results.append({"scene":parent["scene"],"seed":seed,"crop_s":crop,"zero_initial_state":cold,**score})
                    np.savez_compressed(directory/f"{parent['scene']}-{crop}-{seed}-{int(cold)}.npz",**trace)
        write(directory/"flights.json",results)
    manifest["status"] = "completed"
    write(directory/"manifest.json",manifest)


def run_select(args):
    from robust_select import select
    select(args, json.loads(Path("robustness.json").read_text()))


def run_plot(args):
    from robust_plots import plot
    plot(args)


def run_bias_probe(args):
    from common import Flight
    from decompose import joint_payload
    from pairs import variant_rows
    from robust_replay import camera_config, cropped, prepare_pixels, replay
    from robust_train import flight_row
    settings = json.loads(Path("robustness.json").read_text())
    _, parents = read_roster()
    directory, manifest = open_run("robust-bias-probe",settings,{"development":parents})
    print(directory,flush=True)
    rows = []
    for parent in parents:
        if digest(parent["path"]) != parent["sha256"]:
            raise ValueError("development archive changed")
        for seed in (0,1,2):
            model,cfg = joint_payload(FINALISTS/f"bias-{seed}.pt")
            cfg["portable_pixels"] = "remap"
            if seed==0:
                segment = cropped(prepare_pixels(Flight(parent["path"]),cfg),5.)
                cached = flight_row(segment,cfg,"original-combined")
            variants = {}
            count = 0
            for feedback in (False,True):
                spec = {**model,"settings":{**model["settings"],"feedback":feedback}}
                iterator = variant_rows(segment,"original-combined",651)
                score,_ = replay(segment,iterator,spec,cfg)
                variants["closed" if feedback else "open"] = score
                if feedback:
                    estimator = Estimator(camera_config(segment),spec,cfg)
                    for i,(t,frame,packet) in enumerate(variant_rows(segment,"original-combined",651)):
                        estimator.trace = {}
                        estimator.step(t,frame,packet)
                        current = estimator.trace["images"]
                        if not np.array_equal(current[[1,2]],cached["images"][i,[2,3]]):
                            count += 1
            rows.append({"scene":parent["scene"],"seed":seed,"frames":len(segment.ft),
                         "changed_warp_frames":count,**variants})
        write(directory/"ablation.json",rows)
    manifest["status"] = "completed"
    write(directory/"manifest.json",manifest)


def run_data_audit(args):
    from robust_data_audit import audit
    audit(args)


def run_legacy_fuel(args):
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.runner.engine import Engine
    from viobench.tools.runner.run import run_episode
    from viobench.tools.runner.sandbox import Limits

    parents = read_roster()[1][:args.flights]
    directory, manifest = open_run("legacy-fuel",{},{"development":parents})
    print(directory,flush=True)
    engine = Engine()
    rows = []
    try:
        for parent in parents:
            if digest(parent["path"])!=parent["sha256"]:
                raise ValueError("development archive changed")
            episode = read_episode(parent["path"])
            for name in ("ssm","ema","previous-ema","previous-student"):
                module = HISTORICAL/f"{name}.wasm"
                result, _, _ = run_episode(module,episode,engine,Limits(),directory/parent["scene"]/name)
                rows.append({"model":name,"scene":parent["scene"],"sha256":digest(module),**result.as_dict()})
                write(directory/"guest.json",rows)
                if not result.completed:
                    raise ValueError(f"historical guest failed: {result.failure}")
        manifest["status"] = "completed"
    except BaseException as error:
        manifest.update(status="failed",error=repr(error))
        raise
    finally:
        write(directory/"manifest.json",manifest)


def main():
    cv2.setNumThreads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    diagnose = commands.add_parser("parity")
    diagnose.add_argument("--flights", type=int, default=2)
    diagnose.add_argument("--fixed", action="store_true")
    diagnose.add_argument("--fast", action="store_true")
    diagnose.set_defaults(run=parity)
    stress = commands.add_parser("matrix")
    stress.add_argument("--flights", type=int, default=6)
    stress.add_argument("--fixed", action="store_true")
    stress.set_defaults(run=run_matrix)
    guest = commands.add_parser("deploy")
    guest.add_argument("--flights", type=int, default=2)
    guest.add_argument("--legacy", action="store_true")
    guest.add_argument("--fast", action="store_true")

    guest.add_argument("--stress", action="store_true")
    guest.add_argument("--only-new", action="store_true")
    guest.add_argument("--model", action="append", default=[])
    guest.add_argument("--confirmation", type=Path)
    guest.add_argument("--freeze", type=Path)
    guest.set_defaults(run=run_deploy)
    from robust_train import VARIANTS
    training = commands.add_parser("train")
    training.add_argument("--variant", choices=VARIANTS, action="append")
    training.add_argument("--seed", type=int, choices=(0,1,2), action="append")
    training.add_argument("--epochs", type=int)
    training.add_argument("--threads", type=int, default=2)
    training.add_argument("--native-only", action="store_true")
    training.add_argument("--resume", type=Path)
    training.set_defaults(run=run_training)
    start = commands.add_parser("start-probe")
    start.set_defaults(run=run_start_probe)
    selection = commands.add_parser("select")
    selection.add_argument("--screen", type=Path, required=True)
    selection.add_argument("--followup", type=Path, action="append", default=[])
    selection.set_defaults(run=run_select)
    plot = commands.add_parser("plot")
    plot.add_argument("--matrix",type=Path)
    plot.add_argument("--training",type=Path,action="append",default=[])
    plot.add_argument("--guest",type=Path)
    plot.set_defaults(run=run_plot)
    bias = commands.add_parser("bias-probe")
    bias.set_defaults(run=run_bias_probe)
    audit = commands.add_parser("audit-data")
    audit.add_argument("--training",type=Path,action="append",required=True)
    audit.set_defaults(run=run_data_audit)
    legacy = commands.add_parser("legacy-fuel")
    legacy.add_argument("--flights",type=int,default=1)
    legacy.set_defaults(run=run_legacy_fuel)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
