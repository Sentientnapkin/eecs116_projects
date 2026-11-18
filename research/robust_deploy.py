"""Measure trained-weight guest fuel and exact delivered-observation parity."""
import csv
import json
from types import SimpleNamespace

import numpy as np

from decompose import archived_model, bundle_model, joint_payload
from learned_probe import open_run, write
from pairs import digest, variant_rows
from streaming import Estimator


def write_paired(path, results):
    by_model = {(r["scene"],r["regime"],r["model"]):r["ate"] for r in results}
    with path.open("w",newline="") as stream:
        fields = ("model","scene","regime","ate","delta_vs_original_ssm","delta_vs_matched_ema",
                  "delta_vs_own_moving_clean","peak_fuel","peak_fuel_frame")
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        ema = "ema-expanded" if any(r["model"]=="ema-expanded" for r in results) else "ema"
        for row in results:
            def delta(model, regime):
                reference = by_model.get((row["scene"],regime,model))
                return row["ate"]-reference if reference is not None else None
            writer.writerow({**{key:row[key] for key in fields if key in row},
                             "delta_vs_original_ssm":delta("ssm",row["regime"]),
                             "delta_vs_matched_ema":delta(ema,row["regime"]),
                             "delta_vs_own_moving_clean":delta(row["model"],"moving-clean")
                             if row["regime"]=="moving-combined" else None})


def deploy(args, parents, historical, runtime, settings, finalists):
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.runner.engine import Engine
    from viobench.tools.runner.metrics import evaluate_trajectory
    from viobench.tools.runner.sandbox import Sandbox

    models = {}
    if args.confirmation and args.only_new:
        raise ValueError("confirmation needs the fixed reference models")
    references = () if args.only_new else ("ssm", "ema", "previous-ema", "previous-student")
    for name in references:
        model, cfg, identity = archived_model(historical/name)
        if not args.legacy:
            cfg.update(portable_pixels="remap" if args.fast else True)
        models[name] = model, cfg, identity
    if args.confirmation and (args.model or not args.freeze or not args.fast or args.legacy):
        raise ValueError("confirmation requires --freeze and --fast")
    if args.freeze:
        freeze = json.loads(args.freeze.read_text())
        for name, record in freeze["representatives"].items():
            if digest(record["checkpoint"]) != record["sha256"]:
                raise ValueError("frozen checkpoint changed")
            args.model.append(f"{name}={record['checkpoint']}")
    for spec in args.model:
        name, path = spec.split("=", 1)
        model, cfg = joint_payload(path)
        if args.fast:
            cfg.update(portable_pixels="remap")

        models[name] = model, cfg, {"checkpoint":path,"sha256":digest(path)}

    if args.confirmation:
        sources, _ = finalists
        forbidden = {p["scene"] for group in sources.values() for p in group}
        old = json.loads((historical/"manifest.json").read_text())
        forbidden.update(p["scene"] for p in old["datasets"]["evaluation"])
        manifest = json.loads((args.confirmation/"manifest.json").read_text())
        if manifest["status"] != "completed":
            raise ValueError("confirmation archives incomplete")
        parents = manifest["datasets"]["confirmation"]
        if forbidden & {p["scene"] for p in parents}:
            raise ValueError("confirmation scenes overlap prior training or evaluation")
    if not models or not parents:
        raise ValueError("need at least one model and evaluation archive")
    directory, manifest = open_run("robust-guest", settings, {"evaluation":parents})
    manifest.update(selection_sha256=digest(args.freeze) if args.freeze else None,
                    confirmation=bool(args.confirmation), runtime_sha256=digest(runtime), frozen={
        name:{**identity, "config":cfg, "settings":model["settings"]}
        for name,(model,cfg,identity) in models.items()})
    write(directory/"manifest.json", manifest)
    print(directory, flush=True)
    engine = Engine()
    results = []
    try:
        for name, (model, cfg, _) in models.items():
            wasm = bundle_model(directory/name, model, cfg, runtime, gap_adapter=True)
            for parent in parents:
                if digest(parent["path"]) != parent["sha256"]:
                    raise ValueError("archive changed")
                ep = read_episode(parent["path"])
                regimes = [("nominal", 0, "clean")]
                if parent.get("regime") == "long-moving-start":
                    regimes = [("long-clean", 0, "clean"), ("moving-clean", 100, "clean"),
                               ("moving-combined", 100, "combined")]
                elif args.stress and not args.confirmation:
                    regimes.extend([("moving-clean",100,"clean"),("moving-combined",100,"combined")])
                for regime, start, condition in regimes:
                    gaps = condition == "combined"
                    log = directory/f"{name}-{parent['scene']}-{regime}"
                    guest = Sandbox(wasm, engine, log_dir=log)
                    camera, frames = ep.adapt(guest.resolution)
                    guest.init({**camera,"development_gap_adapter":gaps})
                    host = Estimator(camera, model, cfg)
                    fuel, estimates, host_estimates, input_prefix = [], [], [], []
                    calibration_events = []
                    orientation = host.inputs.orient
                    packets = [ep.imu_window(i).copy() for i in range(start,ep.num_frames)]
                    for packet in packets:
                        packet[:,0] -= ep.frame_times[start]
                    stream = SimpleNamespace(ft=ep.frame_times[start:]-ep.frame_times[start],
                                             frames=frames[start:],win=packets,path=parent["path"])
                    for t, frame, packet in variant_rows(stream,condition,settings["stress"]["sensor_seed"]):
                        # The ABI expects RGB every step. This opt-in harness encodes test gaps
                        # on a predetermined frame index; normal bundles always receive RGB.
                        rgb = frame if frame is not None else np.zeros((guest.height,guest.width,3),np.uint8)
                        result = guest.step(t,rgb,packet)
                        estimates.append(np.r_[result.pose,result.twist])
                        checks = orientation.checked_windows
                        rejected = orientation.rejected_windows
                        host_estimates.append(host.step(t,frame,packet))
                        if orientation.checked_windows!=checks:
                            calibration_events.append({"frame":len(fuel), "elapsed_s":float(t),
                                                       "accepted":orientation.rejected_windows==rejected})
                        fuel.append(result.fuel)
                        if len(input_prefix)<160:
                            input_prefix.append((t,rgb,packet))
                    prefix_guest = Sandbox(wasm, engine, log_dir=log/"prefix")
                    prefix_guest.init({**camera,"development_gap_adapter":gaps})
                    prefix = []
                    for t, rgb, packet in input_prefix:
                        result = prefix_guest.step(t,rgb,packet)
                        prefix.append(np.r_[result.pose,result.twist])
                    estimates, host_estimates = np.asarray(estimates),np.asarray(host_estimates)
                    gt = ep.ground_truth_state()[start:].copy()
                    if start:
                        from viobench.tools.geometry import invert, matrices_to_poses, poses_to_matrices
                        poses = poses_to_matrices(gt[:,:7])
                        gt[:,:7] = matrices_to_poses(invert(poses[0]) @ poses)
                    report = evaluate_trajectory(gt,estimates,ep.frame_times[start:]).as_dict()
                    deltas = np.linalg.norm(estimates[:,:3]-host_estimates[:,:3], axis=1)
                    record = {"model":name,"scene":parent["scene"],"regime":regime,"ate":float(report["ate_rmse"]),
                              "peak_fuel":max(fuel),"peak_fuel_frame":int(np.argmax(fuel)),
                              "calibration_events":calibration_events,
                              "frames":len(fuel),"position_delta_max_m":float(deltas.max()),
                              "prefix_identical":bool(np.array_equal(prefix,estimates[:len(prefix)])),
                              "linear_memory_bytes":guest.memory.data_len(guest.store),
                              "artifact_bytes":wasm.stat().st_size,
                              "weights_bytes":(directory/name/"weights.npz").stat().st_size,
                              "wasm_sha256":digest(wasm)}
                    if not record["prefix_identical"]:
                        raise ValueError("guest is not prefix invariant")
                    if cfg.get("portable_pixels") and record["position_delta_max_m"] > .0005:
                        raise ValueError(f"host/guest tolerance exceeded: {record}")
                    results.append(record)
                    write(directory/"guest.json", results)
                    np.savez_compressed(log/"outputs.npz", estimates=estimates,host=host_estimates,fuel=fuel)
                    print(name,parent["scene"],regime,round(record["ate"],4),max(fuel),flush=True)
        write_paired(directory/"paired.csv",results)
        manifest["status"] = "completed"
    except BaseException as error:
        manifest.update(status="failed", error=repr(error))
        raise
    finally:
        write(directory/"manifest.json", manifest)
