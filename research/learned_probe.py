"""Train matched causal visual inputs and score full trajectories."""
import argparse
import json
import platform
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from common import Flight, ate, integrate_body_velocity, sim3_ate
from pairs import CONFIG, build, config, digest
from streaming import CHANNELS

N_FEATURES = 32


class Net(nn.Module):
    def __init__(self, variant, compact=False, model_cfg=None):
        super().__init__()
        self.variant = variant
        model_cfg = model_cfg or {}
        count = len(CHANNELS[variant])
        c1,c2,features = (4,6,16) if compact else (8,12,N_FEATURES)
        self.packet_mode = model_cfg.get("packet_mode")
        if model_cfg:
            features=model_cfg["embedding"]
            scale=model_cfg.get("capacity",1)
            c1,c2=int(8*scale),int(12*scale)
        w,h=model_cfg.get("width",32),model_cfg.get("height",24)
        self.sensor = nn.Linear((51 + 4*bool(model_cfg.get("reliability"))) if self.packet_mode=="ordered" else 23, 24) if self.packet_mode in ("summary","ordered") else None
        self.conv = nn.Sequential(nn.Conv2d(count, c1, 5, 2, 2), nn.ReLU(),
                                  nn.Conv2d(c1, c2, 3, 2, 1), nn.ReLU(), nn.Flatten()) if count else None
        self.encode = nn.Linear((c2*((w+3)//4)*((h+3)//4) if count else 0)
                                + (24 if self.sensor is not None else 15 if self.uses_imu else 1),features)
        self.head = nn.Linear(features, 3)

    @property
    def uses_imu(self):
        return self.variant == "imu" or self.variant.endswith("+imu")

    def features(self, images, imu):
        if self.sensor is not None:
            packet = imu if self.packet_mode=="ordered" else torch.cat((imu[:,:15],imu[:,-8:]),dim=-1)
            aux = torch.relu(self.sensor(packet))
        else:
            aux = imu[:,:15] if self.uses_imu else imu[:,14:15]
        if self.conv is not None:
            aux = torch.cat((self.conv(images), aux), dim=1)
        return torch.relu(self.encode(aux))

    def forward(self, images, imu):
        return self.head(self.features(images, imu))


def open_run(kind, cfg, sources):
    directory = Path("results") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") +
                                   f"-{kind}-{uuid4().hex[:8]}")
    directory.mkdir(parents=True)
    manifest = {"status": "running", "metric": "unaligned_first_camera_ate_m", "config": cfg,
                "config_hash": digest(CONFIG), "sources": {p.name: digest(p) for p in sorted(Path(".").glob("*.py"))},
                "python": platform.python_version(), "torch": str(torch.__version__), "numpy": np.__version__,
                "opencv": cv2.__version__, "datasets": sources}
    write(directory / "manifest.json", manifest)
    return directory, manifest


def write(path, data):
    tmp = path.with_suffix(".partial")
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def split_paths(cfg, tier=None, limit=None):
    tier = tier or cfg["training_tier"]
    groups = {}
    for split, folder in (("train", "train"), ("development", "val")):
        by_scene = defaultdict(list)
        for path in sorted(Path(f"data/{folder}").glob(f"{tier}-*.npz")):
            with np.load(path) as data:
                scene = str(data["scene"])
                if scene not in cfg.get("reserved_scenes", []):
                    by_scene[scene].append(path)
        selected = [(scene, p) for scene, paths in sorted(by_scene.items())
                    for p in paths[:cfg["parents_per_scene"]]]
        groups[split] = selected[:limit] if limit else selected
        if not groups[split]:
            raise ValueError(f"empty {split} split")
    if {s for s, _ in groups["train"]} & {s for s, _ in groups["development"]}:
        raise ValueError("overlapping scenes")
    groups = {split: [{"scene": s, "path": str(p), "sha256": digest(p)} for s, p in paths]
              for split, paths in groups.items()}
    hashes = [row["sha256"] for rows in groups.values() for row in rows]
    if len(set(hashes)) != len(hashes):
        raise ValueError("duplicate parent identities")
    return groups


def read_inputs(rows, cfg, crop=0.):
    data = []
    for row in rows:
        path = row["path"]
        if digest(path) != row["sha256"]:
            raise ValueError(f"parent content changed: {path}")
        cached = build(path, cfg, crop)
        with np.load(cached) as archive:
            data.append({**dict(archive), "path": path, "cache": str(cached), "crop": crop})
    if len(rows) != len(data):
        raise RuntimeError("planned parent count differs from loaded count")
    return data


def tensor(array):
    return torch.as_tensor(array, dtype=torch.float32)


def inputs(row, variant, selection):
    return tensor(row["images"][selection][:, CHANNELS[variant]]) / 255 - .5, tensor(row["imu"][selection])


def displacement_loss(pred, target, rotation, times, cfg, start=0):
    error = pred - target
    loss = F.smooth_l1_loss(error[start:], torch.zeros_like(error[start:]), beta=.1)
    world = (rotation @ error[..., None]).squeeze(-1)
    step = .5 * (world[1:] + world[:-1]) * torch.diff(times)[:, None]
    integral = torch.cat((torch.zeros_like(world[:1]), step.cumsum(0)))
    for duration in cfg["horizons"]:
        past = torch.searchsorted(times, times - duration + 1e-6, right=True) - 1
        keep = (past >= start) & (torch.arange(len(times)) >= start)
        if keep.any():
            delta = integral[keep] - integral[past[keep]]
            loss = loss + F.smooth_l1_loss(delta / duration, torch.zeros_like(delta), beta=.1) / len(cfg["horizons"])
    return loss


def fit(net, dataset, cfg, seed, epochs, feature_key=None, teacher_weight=0.):
    opt = torch.optim.AdamW(net.parameters(), lr=.002)
    rng = np.random.default_rng(seed)
    history = []
    for _ in range(epochs):
        values = []
        for index in rng.permutation(len(dataset)):
            row = dataset[index]
            for start in range(0, len(row["v"]), cfg["chunk"]):
                end = min(start + cfg["chunk"], len(row["v"]))
                if end-start < 2:
                    continue
                burn = min(start, cfg["burn_in"]) if feature_key else 0
                sl = slice(start-burn, end)
                times = tensor(row["times"][sl] - row["times"][sl][0])
                if feature_key:
                    model_dt = np.diff(row["times"], prepend=row["times"][0])[sl]
                    pred = net(tensor(row[feature_key][sl]), tensor(model_dt))
                else:
                    pred = net(*inputs(row, net.variant, sl))
                loss = displacement_loss(pred, tensor(row["v"][sl]), tensor(row["R_truth"][sl]), times, cfg, burn)
                if teacher_weight:
                    loss = loss + teacher_weight * displacement_loss(
                        pred, tensor(row["teacher"][sl]), tensor(row["R_truth"][sl]), times, cfg, burn)
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 1.)
                opt.step()
                values.append(float(loss.detach()))
        history.append(float(np.mean(values)))
    return history


def pose(row, v, R):
    T = row["T_bc"]
    body = integrate_body_velocity(R, v, times=row["times"])
    camera = body + R @ T[:3, 3]
    return (camera-camera[0]) @ (R[0] @ T[:3, :3])


def score(row, v, rotation=None):
    R, true, t = row["R"] if rotation is None else rotation, row["R_truth"], row["times"]
    est, diagnostic = pose(row, v, R), pose(row, v, true)
    target = row["cam_gt"]
    aligned = R[0] @ true[0].T @ true
    cos = (np.einsum("nij,nij->n", aligned, R)-1)/2
    speed = np.linalg.norm(row["v"], axis=1)
    error = np.linalg.norm(est-target, axis=1)
    overlap = np.mean(row["images"][:, 6] > 0, axis=(1, 2))
    def subset(mask):
        return float(np.sqrt(np.mean(error[mask]**2))) if mask.any() else None
    denom = np.sum(est**2)
    scale = float(max(1e-8, np.sum(est*target)/denom)) if denom > 1e-12 else 1.
    return {"path": row["path"], "tier": str(row["tier"]), "scene": str(row["scene"]),
            "ate": ate(est, target), "truth_attitude_ate": ate(diagnostic, target), "sim3": sim3_ate(est, target),
            "startup_ate": subset(t <= 1.), "stationary_ate": subset(speed < .15), "moving_ate": subset(speed >= .15),
            "low_long_overlap_ate": subset(overlap < .6), "mean_long_overlap": float(overlap.mean()),
            "rotation_rmse_rad": float(np.sqrt(np.mean(np.arccos(np.clip(cos,-1,1))**2))),
            "velocity_rmse": ate(v, row["v"]), "positive_scale": scale, "zero_ate": ate(np.zeros_like(target), target),
            "frames": len(t), "duration_s": float(t[-1]), "initial_speed": float(speed[0]), "crop_s": row["crop"],
            "failures": 0}


@torch.no_grad()
def predictions(net, row, features=False):
    method = net.features if features else net
    return torch.cat([method(*inputs(row, net.variant, slice(i, i+256)))
                      for i in range(0, len(row["v"]), 256)]).numpy()


def network(checkpoint):
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    net = Net(saved["variant"], saved.get("compact",False))
    net.load_state_dict(saved["state"])
    return net.eval()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--variant", choices=tuple(CHANNELS), action="append")
    parser.add_argument("--distill-from", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(4)
    if args.distill_from:
        distill(args.distill_from)
        return
    cfg = config()
    if args.smoke or args.epochs:
        cfg["epochs"] = args.epochs or 1
    sources = split_paths(cfg, limit=2 if args.smoke else None)
    directory, manifest = open_run("visual-smoke" if args.smoke else "visual", cfg, sources)
    print(directory, flush=True)
    try:
        train, dev = [read_inputs(sources[k], cfg) for k in ("train", "development")]
        manifest["cache_paths"] = [r["cache"] for r in train+dev]
        results = []
        for seed in cfg["seeds"][:1] if args.smoke else cfg["seeds"]:
            for variant in args.variant or CHANNELS:
                torch.manual_seed(seed)
                net = Net(variant)
                losses = fit(net, train, cfg, seed, cfg["epochs"])
                net.eval()
                path = directory / f"{variant}-{seed}.pt"
                torch.save({"variant": variant, "state": net.state_dict()}, path)
                rows = [score(row, predictions(net, row)) for row in dev]
                summary = {"variant": variant, "seed": seed, "checkpoint": str(path), "sha256": digest(path),
                           "parameters": sum(p.numel() for p in net.parameters()), "loss": losses, "rows": rows}
                results.append(summary)
                write(directory / "scores.json", results)
                print(variant, seed, np.mean([r["ate"] for r in rows]), flush=True)
        manifest["status"] = "completed"
    except BaseException as error:
        manifest.update(status="failed", error=repr(error))
        raise
    finally:
        write(directory / "manifest.json", manifest)


def distill(temporal_run):
    """Keep the accepted teacher fixed and predict training parents only."""
    from seq_heads import Head, predict
    parent = json.loads((temporal_run/"manifest.json").read_text())
    if parent["status"]!="completed":
        raise ValueError("distillation requires a completed temporal comparison")
    candidates = json.loads((temporal_run/"scores.json").read_text())
    reference = min((r for r in candidates if r["variant"]=="ema"),
                    key=lambda r: np.mean([s["ate"] for s in r["rows"]]))
    if digest(reference["checkpoint"])!=reference["sha256"] or digest(reference["encoder"])!=reference["encoder_sha256"]:
        raise ValueError("teacher export chain changed")
    cfg = {**parent["config"],"policy":"startup"}
    groups = parent["datasets"]
    teacher = network(reference["encoder"])
    head = Head("ema")
    saved = torch.load(reference["checkpoint"],map_location="cpu",weights_only=True)
    head.load_state_dict(saved["state"])
    head.eval()
    out,m = open_run("student",cfg,groups)
    m.update(teacher=reference["checkpoint"], teacher_sha256=reference["sha256"], teacher_encoder=reference["encoder"],
             teacher_encoder_sha256=reference["encoder_sha256"], teacher_weight=.5, student_seed=0)
    print(out,flush=True)
    try:
        train,dev = [read_inputs(groups[key],cfg) for key in ("train","development")]
        for r in train:
            r["features"] = predictions(teacher,r,features=True)
            r["teacher"] = predict(head,r)
        scores=[]
        for name,weight in (("labels",0.),("distilled",.5)):
            torch.manual_seed(0)
            student = Net(teacher.variant,compact=True)
            loss = fit(student,train,cfg,0,cfg["epochs"],teacher_weight=weight)
            checkpoint=out/f"{name}.pt"
            torch.save({"variant":student.variant,"state":student.state_dict(),"compact":True},checkpoint)
            scores.append({"variant":student.variant,"student":name,"seed":0,"checkpoint":str(checkpoint),
                           "sha256":digest(checkpoint),"parameters":sum(x.numel() for x in student.parameters()),
                           "loss":loss,"rows":[score(r,predictions(student,r)) for r in dev]})
        write(out/"scores.json",scores)
        m["status"]="completed"
    except BaseException as e:
        m.update(status="failed",error=repr(e))
        raise
    finally:
        write(out/"manifest.json",m)


if __name__ == "__main__":
    main()
