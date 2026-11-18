"""Local/MPS or Accelerate/DDP teacher training with resumable checkpoints."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader
from accelerate import Accelerator
from accelerate.utils import set_seed
from safetensors.torch import save_file, load_file

from teacher_models import Teacher
from teacher_data import Windows, PlannedWindows, load_row, write_json, ROOT
from teacher_store import open_store, GroupedSampler, DATA_REPO
from pairs import digest


class Progress:
    def __init__(self):
        self.epoch, self.best, self.history = 0, float("inf"), []

    def state_dict(self):
        return vars(self).copy()

    def load_state_dict(self, state):
        self.__dict__.update(state)


def loss_fn(pred, row, burn, horizons):
    loss = F.smooth_l1_loss(pred[:, burn:], row["v"][:, burn:], beta=.1)
    world = (row["R"] @ pred.unsqueeze(-1)).squeeze(-1)
    times = row["times"]
    steps = .5*(world[:, 1:]+world[:, :-1])*torch.diff(times, dim=1).unsqueeze(-1)
    body = torch.cat((torch.zeros_like(world[:, :1]), steps.cumsum(1)), dim=1)
    offset = row["T_bc"][:, :3, 3]
    rotated_offset = (row["R"] @ offset[:, None, :, None]).squeeze(-1)
    camera = (body+rotated_offset-rotated_offset[:, :1]) @ row["T_bc"][:, :3, :3]
    target = row["cam_gt"]-row["cam_gt"][:, :1]
    error = camera-target
    for duration in horizons:
        indices = torch.searchsorted(times.contiguous(), (times-duration+1e-6).contiguous(), right=True)-1
        valid = indices >= burn
        previous = error.gather(1, indices.clamp(min=0).unsqueeze(-1).expand(-1, -1, 3))
        residual = (error-previous)/duration
        # A zero valid count is possible for a horizon longer than a short smoke window.
        loss = loss+(F.smooth_l1_loss(residual, torch.zeros_like(residual), beta=.1, reduction="none")
                     * valid.unsqueeze(-1)).sum() / (valid.sum().clamp(min=1)*3*len(horizons))
    return loss


def sim3_ate(estimate, truth):
    """Umeyama similarity alignment, as the course scorer does, then position RMSE."""
    mu_e, mu_t = estimate.mean(0), truth.mean(0)
    e, t = estimate-mu_e, truth-mu_t
    u, d, vt = np.linalg.svd(t.T@e/len(e))
    s_fix = np.eye(3); s_fix[2, 2] = np.sign(np.linalg.det(u@vt))
    rotation = u@s_fix@vt
    variance = (e**2).sum()/len(e)
    scale = float(np.trace(np.diag(d)@s_fix)/variance) if variance > 1e-12 else 1.
    aligned = scale*e@rotation.T + mu_t
    return float(np.sqrt(np.mean(np.sum((aligned-truth)**2, axis=1))))


def provenance(args, out):
    """Everything needed to restore this run elsewhere: a copy of the research sources and
    configs (they may be uncommitted), git state, the data repo commit, and the environment."""
    import platform, shutil, subprocess, sys
    snapshot = out/"source"; snapshot.mkdir(exist_ok=True)
    for path in list(ROOT.glob("*.py")) + list(ROOT.glob("*.sh")) + list((ROOT/"configs").glob("*.json")):
        target = snapshot/path.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    def git(*cmd):
        try: return subprocess.run(["git", *cmd], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception as error: return repr(error)
    data_revision = None
    if args.data.startswith("hf:"):
        try:
            from huggingface_hub import HfApi
            data_revision = HfApi().dataset_info(args.data_repo).sha
        except Exception as error:
            data_revision = repr(error)
    versions = {}
    for name in ("torch", "numpy", "accelerate", "safetensors", "huggingface_hub", "cv2"):
        try: versions[name] = __import__(name).__version__
        except Exception: versions[name] = None
    return {"argv": sys.argv, "git_head": git("rev-parse", "HEAD"), "git_uncommitted": git("status", "--porcelain").splitlines(),
            "source_snapshot": "source/", "data_repo": args.data_repo, "data_repo_revision": data_revision,
            "python": sys.version, "platform": platform.platform(), "machine": platform.machine(), "packages": versions}


def apply_overrides(cfg, items):
    """--set training.learning_rate=0.0005 model.hidden=384 (values parsed as JSON)."""
    for item in items or []:
        key, value = item.split("=", 1)
        try: value = json.loads(value)
        except json.JSONDecodeError: pass
        node, parts = cfg, key.split(".")
        for part in parts[:-1]: node = node.setdefault(part, {})
        node[parts[-1]] = value


def schedule(options, steps_per_epoch):
    total = max(1, options["epochs"]*steps_per_epoch)
    warmup = int(options.get("warmup_epochs", 0)*steps_per_epoch)
    floor = options.get("min_lr_fraction", .05)
    def factor(step):
        if step < warmup: return (step+1)/warmup
        if options.get("schedule", "constant") != "cosine": return 1.
        progress = min(1., (step-warmup)/max(1, total-warmup))
        return float(floor + (1-floor)*.5*(1+np.cos(np.pi*progress)))
    return factor


@torch.no_grad()
def evaluate(net, root, records, device, chunk=32):
    net.eval()
    scores = []
    for record in records:
        row = load_row(root, record)
        output, state = [], None
        for begin in range(0, len(row["v"]), chunk):
            im = torch.as_tensor(row["images"][begin:begin+chunk], device=device)[None]
            u = torch.as_tensor(row["imu"][begin:begin+chunk], device=device)[None]
            rot = torch.as_tensor(row["R"][begin:begin+chunk], device=device, dtype=torch.float32)[None]
            pred, state = net(im, u, state, rot)
            output.append(pred[0].cpu().numpy())
        v = np.concatenate(output).astype(np.float64)
        world = (row["R"] @ v[..., None]).squeeze(-1)
        p = np.zeros_like(world)
        p[1:] = np.cumsum(.5*(world[1:]+world[:-1])*np.diff(row["times"])[:, None], axis=0)
        arm, rotation = row["T_bc"][:3, 3], row["T_bc"][:3, :3]
        p = (p+row["R"]@arm-arm)@rotation
        backwards = row["v"][:, 0] < -.2
        scores.append({"scene": record["scene"], "file": record["file"], "crop_s": record["crop_s"],
                       "ate": float(np.sqrt(np.mean(np.sum((p-row["cam_gt"])**2, axis=1)))),
                       "sim3_ate": sim3_ate(p, row["cam_gt"]),
                       "velocity_rmse": float(np.sqrt(np.mean(np.sum((v-row["v"])**2, axis=1)))),
                       "backward_frames": int(backwards.sum()),
                       "backward_sign_accuracy": float(np.mean(v[backwards, 0] < 0)) if backwards.any() else None})
    if not all(np.isfinite(r["ate"]) for r in scores):
        raise ValueError("Nonfinite development replay")
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT/"configs/teachers.json"))
    parser.add_argument("--data", required=True,
                        help="Prepared directory, or hf:<name> to stream from the private data repo")
    parser.add_argument("--data-repo", default=DATA_REPO)
    parser.add_argument("--cache-dir", default=str(ROOT/"data/hub-cache"))
    parser.add_argument("--cache-gb", type=float, default=4.0, help="Disk budget for streamed shards")
    parser.add_argument("--group-size", type=int,
                        help="Parents per shard group (prefetch unit). Required for hf: data")
    parser.add_argument("--output", required=True)
    parser.add_argument("--head", choices=("gru", "ssm", "ema"))
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--teacher", type=Path, help="Frozen teacher run for velocity distillation")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--hub-repo", help="Private HF repo to sync each completed epoch to")
    parser.add_argument("--set", action="append", dest="overrides", metavar="KEY=JSON",
                        help="Override any config value, e.g. training.window_frames=160")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if args.head: cfg["model"]["head"] = args.head
    if args.seed is not None: cfg["seed"] = args.seed
    if args.epochs is not None: cfg["training"]["epochs"] = args.epochs
    apply_overrides(cfg, args.overrides)
    accelerator = Accelerator(cpu=args.cpu, mixed_precision="no",
                              gradient_accumulation_steps=cfg["training"].get("accumulation", 1))
    torch.set_num_threads(cfg["training"].get("cpu_threads", 4))
    set_seed(cfg["seed"])
    data = open_store(args.data, args.cache_dir, args.cache_gb, args.data_repo)
    streaming = args.data.startswith("hf:")
    if streaming and not args.group_size and not cfg["training"].get("sampler"):
        raise ValueError("Streaming needs --group-size so shards can be prefetched in order")
    manifest_path = data.manifest_path()
    manifest = json.loads(manifest_path.read_text())
    if manifest["status"] != "completed": raise ValueError("Data preparation incomplete")
    if not streaming:  # streamed shards are checksummed as they download
        for records in manifest["datasets"].values():
            for r in records:
                if digest(data.path(r)) != r["sha256"]: raise ValueError("Dataset checksum changed")
    out = Path(args.output).resolve()
    if not args.resume and out.exists(): raise ValueError("Use a new run directory or --resume")
    if accelerator.is_main_process: out.mkdir(parents=True, exist_ok=True)
    accelerator.wait_for_everyone()
    identity = {"data_manifest_sha256": digest(manifest_path), "model": cfg["model"],
                "seed": cfg["seed"], "training": {k:v for k,v in cfg["training"].items() if k != "epochs"},
                "world_size": accelerator.num_processes,
                "teacher_sha256": digest(args.teacher/"best.safetensors") if args.teacher else None}
    if args.group_size:  # only present when used, so older runs still resume
        identity["shard_group"] = args.group_size
    if args.hub_repo and accelerator.is_main_process:
        from teacher_hub import ensure_private
        ensure_private(args.hub_repo)  # fail before training, not after the first epoch
    if args.resume:
        old = json.loads((out/"manifest.json").read_text())
        if identity != old["identity"]: raise ValueError("Resume configuration/data/world size changed")
        if not (args.resume/"complete.json").exists(): raise ValueError("Incomplete checkpoint")
    progress = Progress()
    options = cfg["training"]
    dataset = Windows(data, manifest["datasets"]["train"], options["window_frames"],
                      options["burn_in"], options["windows_per_parent"], cfg["seed"])
    sampler = None
    if options.get("sampler"):
        # Planned windows: fixed windows per epoch, so optimizer updates match across datasets.
        data.prefetch(manifest["datasets"]["train"] + manifest["datasets"]["development"])
        dataset = PlannedWindows(data, manifest["datasets"]["train"], options["window_frames"],
                                 options["burn_in"], options["sampler"], cfg["seed"])
        loader = DataLoader(dataset, batch_size=options["batch_size"], shuffle=False, num_workers=0)
    elif args.group_size:
        sampler = GroupedSampler(manifest["datasets"]["train"], options["windows_per_parent"],
                                 args.group_size, cfg["seed"], data,
                                 pinned=manifest["datasets"]["development"])
        loader = DataLoader(dataset, batch_size=options["batch_size"], sampler=sampler, num_workers=0)
    else:
        loader = DataLoader(dataset, batch_size=options["batch_size"], shuffle=True, num_workers=0)
    net = Teacher(cfg["model"])
    opt = torch.optim.AdamW(net.parameters(), lr=options["learning_rate"], weight_decay=.01)
    steps = -(-len(loader)//options.get("accumulation", 1))
    lr_schedule = torch.optim.lr_scheduler.LambdaLR(opt, schedule(options, steps))
    net, opt, loader, lr_schedule = accelerator.prepare(net, opt, loader, lr_schedule)
    accelerator.register_for_checkpointing(progress)
    averaged = None
    if options.get("weight_ema"):
        from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn
        averaged = AveragedModel(accelerator.unwrap_model(net), use_buffers=True,
                                 multi_avg_fn=get_ema_multi_avg_fn(options["weight_ema"]))
        accelerator.register_for_checkpointing(averaged)
    if args.resume: accelerator.load_state(str(args.resume))
    teacher = None
    if args.teacher:
        teacher_cfg = json.loads((args.teacher/"config.json").read_text())
        teacher = Teacher(teacher_cfg["model"]).to(accelerator.device)
        teacher.load_state_dict(load_file(str(args.teacher/"best.safetensors")))
        teacher.eval().requires_grad_(False)
    run = {"status": "running", "identity": identity, "device": str(accelerator.device),
           "parameters": sum(p.numel() for p in net.parameters()), "pilot_data": manifest.get("pilot", False),
           "sources": {n:digest(ROOT/n) for n in ("teacher_train.py", "teacher_models.py", "teacher_data.py")}}
    if accelerator.is_main_process:
        run["provenance"] = provenance(args, out)
        write_json(out/"manifest.json", run); write_json(out/"config.json", cfg)
    sync = None  # background Hub sync (main process only)
    try:
        for epoch in range(progress.epoch, options["epochs"]):
            dataset.epoch = epoch
            if hasattr(dataset, "set_epoch"): dataset.set_epoch(epoch)
            if sampler is not None: sampler.set_epoch(epoch)
            if hasattr(loader, "set_epoch"): loader.set_epoch(epoch)
            net.train()
            total, count = 0., 0
            for row in loader:
                with accelerator.accumulate(net):
                    pred, _ = net(row["images"], row["imu"], R=row["R"])
                    loss = loss_fn(pred, row, options["burn_in"], options["horizons"])
                    if teacher is not None:
                        with torch.no_grad(): target, _ = teacher(row["images"], row["imu"], R=row["R"])
                        loss += options.get("distillation_weight", .2)*F.smooth_l1_loss(
                            pred[:, options["burn_in"]:], target[:, options["burn_in"]:], beta=.1)
                    if not torch.isfinite(loss): raise ValueError("Nonfinite training loss")
                    accelerator.backward(loss)
                    if accelerator.sync_gradients: accelerator.clip_grad_norm_(net.parameters(), 1.)
                    opt.step(); opt.zero_grad()
                    if accelerator.sync_gradients:
                        lr_schedule.step()
                        if averaged is not None: averaged.update_parameters(accelerator.unwrap_model(net))
                total += float(loss.detach()); count += 1
            sums = accelerator.reduce(torch.tensor([total, count], device=accelerator.device), reduction="sum")
            # Each rank evaluates disjoint complete episodes without DDP forward collectives.
            records = manifest["datasets"]["development"][accelerator.process_index::accelerator.num_processes]
            scored = averaged.module if averaged is not None else accelerator.unwrap_model(net)
            rows = evaluate(scored, data, records, accelerator.device)
            from accelerate.utils import gather_object
            rows = gather_object(rows)
            nominal = np.mean([r["ate"] for r in rows if r["crop_s"] == 0])
            moving_rows = [r["ate"] for r in rows if r["crop_s"] > 0]
            moving = float(np.mean(moving_rows)) if moving_rows else float(nominal)
            score = float(.5*(nominal+moving))
            sim3 = float(np.mean([r["sim3_ate"] for r in rows]))
            item = {"epoch": epoch+1, "loss": float(sums[0]/sums[1]), "nominal_ate": float(nominal),
                    "moving_ate": moving, "selection_score": score, "sim3_ate": sim3,
                    "lr": float(opt.param_groups[0]["lr"]), **data.stats(),
                    "optimizer_updates": (epoch+1)*steps, "exposure": getattr(dataset, "exposure", None), "rows": rows}
            progress.history.append(item); progress.epoch = epoch+1
            if score < progress.best:
                progress.best = score
                if accelerator.is_main_process:
                    state = {k:v.detach().cpu().contiguous() for k,v in scored.state_dict().items()}
                    save_file(state, str(out/"best.safetensors.partial"))  # atomic: a background
                    (out/"best.safetensors.partial").replace(out/"best.safetensors")  # upload may be reading it
            if accelerator.is_main_process:
                write_json(out/"metrics.json", progress.history)
                print(json.dumps({k:v for k,v in item.items() if k not in ("rows", "exposure")}), flush=True)
            checkpoint = out/"checkpoints"/f"epoch-{epoch+1:04d}"
            accelerator.save_state(str(checkpoint))
            accelerator.wait_for_everyone()
            if accelerator.is_main_process:
                write_json(checkpoint/"complete.json", {"epoch": epoch+1})
                if args.hub_repo:
                    write_json(out/"manifest.json", run)
                    if sync is None:
                        from teacher_hub import BackgroundSync
                        sync = BackgroundSync(out, args.hub_repo)
                    sync.epoch(epoch+1)
            patience = options.get("patience")
            best_epoch = min(progress.history, key=lambda h: h["selection_score"])["epoch"]
            if patience and epoch+1-best_epoch >= patience:
                if accelerator.is_main_process: print(f"Early stop: no gain since epoch {best_epoch}", flush=True)
                break
        run["status"] = "completed"
        if sync is not None: sync.finish()
    except BaseException as error:
        run.update(status="failed", error=type(error).__name__+": "+str(error))
        raise
    finally:
        if accelerator.is_main_process: write_json(out/"manifest.json", run)


if __name__ == "__main__": main()
