"""Fit and screen inertial refinement on frozen, causally replayed B-D0 heads."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import numpy as np
from safetensors.torch import load_file, save_file
import torch

from odometry_data import WindowPlan, load_row, motion_labels, validate_roster, write_json
from odometry_eval import integrate, metrics
from odometry_ledger import split_for
from odometry_models import OdometryNet, Refiner
from odometry_train import refined_loss
from pairs import digest


@torch.no_grad()
def cache_head(net, path, records, device, max_seconds=None):
    """Stream in timestamp order and retain just the head context and loss inputs."""
    def read(record):
        row = load_row(path, record)
        if max_seconds is not None:
            keep = np.searchsorted(row["times"], row["times"][0]+max_seconds+1e-6, side="right")
            row = {key: value if key == "T_bc" else value[:keep] for key, value in row.items()}
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for begin in range(0, len(records), 8):
            group = records[begin:begin+8]
            raw = list(pool.map(read, group))
            lengths = [len(row["imu"]) for row in raw]
            maximum = max(lengths)

            def padded(key):
                output = np.zeros((len(raw), maximum, *raw[0][key].shape[1:]), dtype=raw[0][key].dtype)
                for target, row in zip(output, raw):
                    target[:len(row[key])] = row[key]
                return torch.from_numpy(output).to(device)

            images, imu, rotation = map(padded, ("images", "imu", "R"))
            state, contexts, bases = None, [], []
            for start in range(0, maximum, 16):
                frames = slice(start, start+16)
                context, state, _ = net.head(images[:, frames], imu[:, frames], state, rotation[:, frames])
                contexts.append(context)
                bases.append(net.output(context))
            context = torch.cat(contexts, 1)
            base = torch.cat(bases, 1)
            for i, (row, length) in enumerate(zip(raw, lengths)):
                cached = {key: torch.as_tensor(row[key], device=device)
                          for key in ("v", "times", "T_bc", "cam_gt")}
                cached.update(context=context[i, :length], base=base[i, :length],
                              imu=imu[i, :length], R=rotation[i, :length])
                rows.append(cached)
            print(f"Cached {len(rows)}/{len(records)} trajectories", flush=True)
    return rows


def windows(rows, items, size):
    return {key: torch.stack([rows[i][key] if key == "T_bc" else rows[i][key][start:start+size]
                              for i, start, _ in items]).float() for key in rows[0]}


@torch.no_grad()
def score_rows(rows, records, refiner=None):
    stream_keys = ("base", "context", "imu", "R")
    scores = []
    for begin in range(0, len(rows), 32):
        group = rows[begin:begin+32]
        if refiner is None:
            estimates = [row["base"] for row in group]
        else:
            streams = [torch.nn.utils.rnn.pad_sequence([r[k] for r in group], batch_first=True) for k in stream_keys]
            every, _ = refiner(*streams, None)
            estimates = every[-1]
        for row, estimate, record in zip(group, estimates, records[begin:begin+32]):
            truth = {k: row[k].cpu().numpy() for k in ("R", "T_bc", "times", "cam_gt", "v")}
            trajectory = integrate(estimate[:len(truth["times"])].cpu().numpy(), truth)
            ate = metrics(trajectory, truth["cam_gt"], truth["times"])["ate"]
            labels = motion_labels(truth["v"], truth["times"], truth["cam_gt"])
            scores.append(dict(file=record["file"], scene=record["scene"], crop_s=record["crop_s"],
                               catalog=record.get("catalog"), ate=ate,
                               ordinary=bool(labels["backward"].mean() <= .05 and labels["lateral"].mean() <= .1)))
    return scores


def dev_score(refiner, rows, records):
    scores = score_rows(rows, records, refiner)
    return float(np.mean([np.mean([r["ate"] for r in scores if bool(r["crop_s"]) == moving])
                          for moving in (False, True)]))


def fit(base, cfg, recipe, inputs, plan, development, records, out, iters, provenance):
    out.mkdir()
    cfg = dict(cfg, model=dict(cfg["model"], **recipe["model"], refine_iters=iters))
    kwargs = dict(device=next(base.parameters()).device)
    torch.manual_seed(cfg["seed"])
    refiner = Refiner(cfg["model"], cfg["model"]["embedding"], None).to(**kwargs)
    optimizer = torch.optim.AdamW(refiner.parameters(), lr=recipe["learning_rate"], weight_decay=.01)
    trained = torch.optim.swa_utils.AveragedModel(
        refiner, use_buffers=True, multi_avg_fn=torch.optim.swa_utils.get_ema_multi_avg_fn(recipe["weight_ema"]))
    burn, horizons = cfg["training"]["burn_in"], cfg["training"]["horizons"]
    gamma = cfg["model"]["refine_gamma"]
    best, history = float("inf"), []
    write_json(out/"config.json", cfg)
    for epoch in range(recipe["epochs"]):
        items = plan.plan(epoch)
        losses = []
        for i in range(0, len(items), recipe["batch_size"]):
            row = windows(inputs, items[i:i+recipe["batch_size"]], plan.size)
            optimizer.zero_grad(set_to_none=True)
            every, _ = refiner(row["base"], row["context"], row["imu"], row["R"], None)
            loss = refined_loss(every, row, burn, horizons, gamma)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite refinement loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(refiner.parameters(), 1.)
            optimizer.step()
            trained.update_parameters(refiner)
            losses.append(float(loss.detach()))
        score = dev_score(trained.module, development, records)
        history.append(dict(epoch=epoch+1, loss=float(np.mean(losses)), selection_score=score))
        print(out.name, history[-1], flush=True)
        if score < best:
            best = score
            weights = dict(base.state_dict(), **{f"refiner.{key}": value for key, value in trained.module.state_dict().items()})
            save_file({k: v.cpu().contiguous() for k, v in weights.items()}, str(out/"best.safetensors"))
        write_json(out/"metrics.json", history)
    write_json(out/"manifest.json", dict(status="completed", provenance=provenance, recipe=recipe))


def replay(net, suites, arms, seed, device, provenance):
    for name, (shards, records, cap) in suites.items():
        out = next(iter(arms.values())).parent/f"replay-{name}-s{seed}.json"
        if out.exists():
            continue
        for arm in arms.values():
            run = json.loads((arm/"manifest.json").read_text())
            if run["status"] != "completed" or run["provenance"] != provenance:
                raise ValueError(f"Unexpected checkpoint provenance in {arm}")
        inputs = cache_head(net, shards, records, device, cap)
        result = {0: score_rows(inputs, records)}
        for k, arm in arms.items():
            model = json.loads((arm/"config.json").read_text())["model"]
            layers = {key.removeprefix("refiner."): value for key, value
                      in load_file(arm/"best.safetensors").items() if key.startswith("refiner.")}
            refiner = Refiner(model, model["embedding"], None).to(device).eval()
            refiner.load_state_dict(layers)
            result[k] = score_rows(inputs, records, refiner)
        write_json(out, result)
        print(out.name, {k: float(np.mean([r["ate"] for r in rows])) for k, rows in result.items()}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Cached teacher-full directory (read-only)")
    parser.add_argument("--controls", type=Path, required=True, help="Read-only parent directory of the three B-D0 runs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true", help="Score completed arms on dev, proxy-val and campaign-dev")
    args = parser.parse_args()
    recipe = json.loads(Path(__file__).with_name("configs").joinpath("experiments.json").read_text())["refinement_screen"]
    manifest_path = args.data/"manifests"/"teacher-full.json"
    datasets = json.loads(manifest_path.read_text())["datasets"]
    train, development = datasets["train"], datasets["development"]
    validate_roster({"train": train, "development": development})
    if args.replay:
        root = args.data.parent.parent
        proxy = json.loads((root/"expand"/"proxy-proxy_validation-0.json").read_text())["records"]
        campaign = json.loads((root/"native-campaign"/"dev-records.json").read_text())["records"]
        if any(split_for(r["scene"]) != "proxy_validation" for r in proxy):
            raise ValueError("Expected only proxy validation records")
        if any(r.get("split") != "dev" for r in campaign):
            raise ValueError("Expected only campaign development records")
        suites = {
            "dev": (args.data/"shards", development, None),
            "proxy-val-30s": (root/"hub-cache"/"proxy-val"/"shards", [r for r in proxy if r["crop_s"] == 0], 30),
            "campaign-dev-30s": (root/"native-campaign"/"shards", campaign, 30),
        }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(4)
    args.output.mkdir(parents=True, exist_ok=True)
    for seed in recipe["seeds"]:
        arms = {k: args.output/f"refine-inertial-k{k}-s{seed}" for k in recipe["iterations"]}
        pending = {k: out for k, out in arms.items() if not (out/"manifest.json").exists()}
        if not args.replay:
            if not pending:
                continue
            if any(out.exists() for out in pending.values()):
                raise ValueError("Use a fresh output directory for incomplete arms")
        suffix = "" if seed == 217 else f"-s{seed}"
        control = args.controls/f"B-D0-ssm-x3{suffix}-gpu"
        source_weights = control/"best.safetensors"
        cfg = json.loads((control/"config.json").read_text())
        source_manifest = json.loads((control/"manifest.json").read_text())
        manifest_hash = digest(manifest_path)
        if cfg["seed"] != seed or manifest_hash != source_manifest["identity"]["data_manifest_sha256"]:
            raise ValueError("Control seed or data manifest mismatch")
        provenance = dict(control=str(control.resolve()), control_sha256=digest(source_weights),
                          data_manifest_sha256=manifest_hash)
        net = OdometryNet(cfg["model"]).to(device).eval()
        net.load_state_dict(load_file(source_weights))
        if args.replay:
            replay(net, suites, arms, seed, device, provenance)
            continue
        rows = cache_head(net, args.data/"shards", train+development, device)
        inputs, validation = rows[:len(train)], rows[len(train):]
        labels = [motion_labels(*(r[k].cpu().numpy() for k in ("v", "times", "cam_gt"))) for r in inputs]
        opts = cfg["training"]
        plan = WindowPlan(train, labels, opts["window_frames"]+opts["burn_in"], opts["burn_in"], opts["sampler"], seed)
        for k, out in pending.items():
            fit(net, cfg, recipe, inputs, plan, validation, development, out, k, provenance)


if __name__ == "__main__":
    main()
