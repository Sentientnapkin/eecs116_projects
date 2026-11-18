"""Train matched warm-started controls on ephemeral raw-stream variants."""
import json
import shutil
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from common import Flight, ate
from learned_probe import inputs, open_run, pose, tensor, write
from pairs import digest, variant_rows
from robust_replay import camera_config, cropped, prepare_pixels
from seq_heads import Joint
from streaming import Inputs


VARIANTS = {
    "ssm-nominal": ("ssm", False, False, False),
    "ssm-expanded": ("ssm", True, False, False),
    "ssm-reliability": ("ssm", True, True, False),
    "ssm-zero-initial": ("ssm", True, True, True),
    "ema-expanded": ("ema", True, False, False),
}
DISTURBANCES = ("clean", "constant", "changing", "gaps", "jitter", "combined")


def flight_row(flight, cfg, condition="clean", sensor_seed=651):
    camera = camera_config(flight)
    state = Inputs(cfg, camera, flight.delivery_shape, flight.T_bc[:3,:3])
    images, imu, rotations, _ = map(np.stack, zip(*[
        state.step(t, frame, packet)
        for t, frame, packet in variant_rows(flight, condition, sensor_seed)]))
    return dict(images=images, imu=imu, R=rotations, R_truth=flight.R, v=flight.v_body,
                times=flight.ft, T_bc=flight.T_bc, cam_gt=flight.cam_gt, path=flight.path,
                scene=flight.scene, tier=flight.tier, crop=flight.realized_crop)


def camera_loss(pred, row, horizons):
    """Body velocity plus displacement of the predicted camera in camera-0 axes."""
    target, times = tensor(row["v"]), tensor(row["times"])
    R, extrinsic = tensor(row["R"]), tensor(row["T_bc"])
    loss = F.smooth_l1_loss(pred, target, beta=.1)
    world = (R @ pred[...,None]).squeeze(-1)
    steps = .5 * (world[1:] + world[:-1]) * torch.diff(times)[:,None]
    body_positions = torch.cat((torch.zeros_like(world[:1]), steps.cumsum(0)))
    offset = extrinsic[:3,3]
    camera = (body_positions + R @ offset-offset) @ extrinsic[:3,:3]
    error = camera-tensor(row["cam_gt"])
    for duration in horizons:
        past = torch.searchsorted(times, times-duration+1e-6, right=True)-1
        keep = past>=0
        if keep.any():
            residual = (error[keep]-error[past[keep]])/duration
            loss = loss+F.smooth_l1_loss(residual, torch.zeros_like(residual), beta=.1)/len(horizons)
    return loss


def select_segment(flight, rng, expanded, options):
    low, high = options["window_frames"]
    duration = int(rng.integers(low, high+1))
    nominal = rng.random() < options["nominal_fraction"]
    a, b = options["crop_start_s"]
    stop = max(a, min(b, flight.ft[-min(duration,len(flight.ft))]))
    offset = float(rng.uniform(a, stop))
    condition = DISTURBANCES[int(rng.integers(len(DISTURBANCES)))]
    sensor_seed = int(rng.integers(2**31))
    if not expanded or nominal:
        offset, condition = 0., "clean"
    return cropped(flight, offset, duration), condition, sensor_seed


def prepare(parents, cfg):
    prepared = []
    for parent in parents:
        if digest(parent["path"]) != parent["sha256"]:
            raise ValueError(f"parent changed: {parent['path']}")
        prepared.append(prepare_pixels(Flight(parent["path"]), cfg))
    return prepared


def validation(flights, cfg, stress):
    rows = []
    for flight in flights:
        rows.append((0, "clean", flight_row(flight,cfg)))
        for start in stress["crops_s"][1:]:
            segment = cropped(flight,start)
            for condition in ("clean","original-combined"):
                rows.append((start, condition, flight_row(segment,cfg,condition,stress["sensor_seed"])))
    return rows


@torch.no_grad()
def validation_score(net, dataset):
    rows = []
    for start, condition, sample in dataset:
        pred = net(*inputs(sample,net.settings["variant"],slice(None))).numpy()
        error = ate(pose(sample,pred,sample["R"]),sample["cam_gt"])
        rows.append({"scene":sample["scene"], "crop_s":start, "condition":condition, "ate":error})
    nominal = np.mean([row["ate"] for row in rows if row["crop_s"]==0])
    moving = np.mean([row["ate"] for row in rows if row["crop_s"]>0 and row["condition"]=="clean"])
    combined = np.mean([row["ate"] for row in rows if row["condition"]=="original-combined"])
    return {"nominal_ate":float(nominal),"moving_ate":float(moving),"combined_ate":float(combined),
            "stress_ate":float(.5*(moving+combined))}, rows


def resolved_checkpoint(path, reliability, zero_initial_state):
    saved = torch.load(path,weights_only=True,map_location="cpu")
    settings = {**saved["settings"], "reliability":reliability, "zero_initial_state":zero_initial_state}
    config = {**saved["config"], "portable_pixels":True, "reliability":reliability}
    state = dict(saved["state"])
    if reliability:
        state["encoder.sensor.weight"] = F.pad(state["encoder.sensor.weight"], (0,4))
    net = Joint(settings)
    net.load_state_dict(state)
    return net, config


def fit_candidate(directory, name, seed, train, dev, options, parent, max_epochs):
    from time import monotonic
    _, expanded, reliability, zero_initial_state = VARIANTS[name]
    net, cfg = resolved_checkpoint(parent,reliability,zero_initial_state)
    opt = torch.optim.AdamW(net.parameters(), lr=options["learning_rate"])
    working = directory/f"{name}-{seed}-resume.pt"
    checkpoint = directory/f"{name}-{seed}.pt"
    history = []
    best = None
    best_key = (float("inf"),float("inf"))
    selected = None
    if working.exists():
        saved = torch.load(working,weights_only=True,map_location="cpu")
        net.load_state_dict(saved["state"])
        opt.load_state_dict(saved["opt"])
        history, best, best_key, selected = (saved[k] for k in ("history","best","best_key","selected"))
    reference_net, _ = resolved_checkpoint(parent,False,False)
    baseline, _ = validation_score(reference_net,dev[False])
    nominal_limit = baseline["nominal_ate"] + options["nominal_ate_allowance_m"]
    started = monotonic()
    for epoch in range(len(history)+1,max_epochs+1):
        net.train()
        rng = np.random.default_rng([seed,epoch])
        losses, n_frames = [], 0
        counts = {kind:0 for kind in DISTURBANCES}
        moving_starts = 0
        for i in rng.permutation(len(train)):
            segment, condition, sensor_seed = select_segment(train[i],rng,expanded,options)
            row = flight_row(segment,cfg,condition,sensor_seed)
            result = net(*inputs(row,net.settings["variant"],slice(None)))
            loss = camera_loss(result,row,cfg["joint"]["horizons"])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(),1.)
            opt.step()
            n_frames += len(result)
            losses.append(float(loss.detach()))
            counts[condition] += 1
            moving_starts += np.linalg.norm(segment.v[0])>.15
        net.eval()
        scores, rows = validation_score(net,dev[reliability])
        feasible = scores["nominal_ate"]<=nominal_limit
        key = (0.,scores["stress_ate"]) if feasible else (1.,scores["nominal_ate"])
        epoch_data = {"epoch":epoch,"training_loss":float(np.mean(losses)),**scores,
                      "windows":len(losses),"optimizer_steps":len(losses),"frames":n_frames,
                      "variants":counts,"moving_start_windows":int(moving_starts),
                      "elapsed_seconds":monotonic()-started,"within_nominal_limit":bool(feasible)}
        history.append(epoch_data)
        if key<best_key:
            best_key = key
            best = {k:v.detach().clone() for k,v in net.state_dict().items()}
            selected = {**epoch_data, "rows":rows}
        temp = working.with_suffix(".partial")
        torch.save(dict(state=net.state_dict(), opt=opt.state_dict(), history=history, best=best,
                        best_key=best_key, selected=selected), temp)
        temp.replace(working)
        write(directory/f"{name}-{seed}-history.json",history)
        print(name,seed,epoch,round(scores["nominal_ate"],4),round(scores["stress_ate"],4),flush=True)
        if epoch>=options["min_epochs"] and epoch-selected["epoch"]>=options["patience"]:
            break
    if selected is None:
        raise ValueError("no training epoch completed")
    torch.save({"state":best,"settings":net.settings,"config":cfg},checkpoint)
    return {"model":name,"seed":seed,"checkpoint":str(checkpoint),"sha256":digest(checkpoint),
            "initial_checkpoint":str(parent),"initial_sha256":digest(parent),
            "nominal_limit":nominal_limit,"baseline":baseline,"selected":selected,"history":history}


def train(args, settings, roster, baseline_dir):
    import cv2
    torch.set_num_threads(args.threads)
    cv2.setNumThreads(1)
    sources, valid = roster
    opt = settings["training"]
    train_parents = [p for p in sources["train"] if p["domain"]=="benchmark"] if args.native_only else sources["train"]
    source_groups = {"train":train_parents,"development":valid}
    variants = args.variant or list(VARIANTS)
    max_epochs = args.epochs or opt["max_epochs"]
    if args.resume:
        directory = args.resume
        manifest = json.loads((directory/"manifest.json").read_text())
        if manifest["status"] == "completed":
            raise ValueError("completed runs are immutable")
        if (manifest["datasets"] != source_groups or manifest["config"] != settings
                or manifest["variants"] != variants or manifest["max_epochs"] != max_epochs):
            raise ValueError("resume does not match original plan")
    else:
        directory, manifest = open_run("robust-training", settings, source_groups)
        manifest.update(variants=variants,max_epochs=max_epochs,disk_free_before=shutil.disk_usage(".").free,
                        candidate_init="matched historical weights by family and seed",
                        independent_scenes={split:len({r["scene"] for r in rows}) for split,rows in source_groups.items()},
                        selection_rule="minimum mean moving clean and combined ATE under per-seed nominal limit")
    print(directory,flush=True)
    write(directory/"manifest.json",manifest)
    score_path = directory/"scores.json"
    records = json.loads(score_path.read_text()) if score_path.exists() else []
    done = {(r["model"],r["seed"]) for r in records}
    try:
        _, cfg = resolved_checkpoint(baseline_dir/"ssm-0.pt",False,False)
        train_data, dev_data = prepare(train_parents,cfg), prepare(valid,cfg)
        validation_data = {flag:validation(dev_data,{**cfg,"reliability":flag},settings["stress"])
                           for flag in (False,True)}
        from robust_replay import replay
        # The differentiable precomputed no-feedback stream should match the streaming estimator.
        from seq_heads import joint_model
        baseline, _ = resolved_checkpoint(baseline_dir/"ssm-0.pt",False,False)
        streamed, _ = replay(dev_data[0],variant_rows(dev_data[0],"clean",651),joint_model(baseline),cfg)
        batched = validation_score(baseline,validation_data[False])[1][0]
        agreement = abs(streamed["ate"]-batched["ate"])
        if agreement > .0005:
            raise ValueError(f"batch/stream ATE mismatch: {agreement}")
        manifest["batch_stream_nominal_ate_delta"] = agreement
        seeds = args.seed or opt["train_seeds"]
        for seed in seeds:
            for name in variants:
                if (name,seed) in done:
                    continue
                family = VARIANTS[name][0]
                parent = baseline_dir/f"{family}-{seed}.pt"
                record = fit_candidate(directory,name,seed,train_data,validation_data,opt,parent,max_epochs)
                records.append(record)
                write(score_path,records)
        manifest.update(status="completed",disk_free_after=shutil.disk_usage(".").free)
    except BaseException as error:
        manifest.update(status="failed",error=repr(error))
        raise
    finally:
        write(directory/"manifest.json",manifest)
