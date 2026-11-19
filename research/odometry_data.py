"""Portable, checksummed training data; reuse the audited causal sensor pipeline."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from common import Flight
from pairs import digest, variant_rows
from streaming import Inputs, CHANNELS

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def validate_roster(groups):
    scenes, identities = {}, {}
    for split, rows in groups.items():
        if not rows:
            raise ValueError(f"Empty {split} split")
        for row in rows:
            for key, table in (("scene", scenes), ("sha256", identities)):
                value = row[key]
                if value in table and table[value] != split:
                    raise ValueError(f"Split overlap: {key} {value}")
                table[value] = split


def prepare(config_path, output, pilot=False, max_frames=None):
    config = json.loads(Path(config_path).read_text())
    source = json.loads((ROOT/config["roster"]).read_text())
    groups = {"train": source["datasets"]["train"], "development": source["validation_roster"]}
    if pilot:
        groups = {"train": groups["train"][:3], "development": groups["development"][:2]}
    for path in config.get("additional_manifests", []):
        extra = json.loads((ROOT/path).read_text())
        if extra.get("status") != "completed":
            raise ValueError(f"Generation incomplete: {path}")
        for split in groups:
            groups[split] = groups[split] + extra["datasets"].get(split, [])
    groups = {k: list({r["sha256"]: r for r in rows}.values()) for k, rows in groups.items()}
    validate_roster(groups)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output/"manifest.json"
    if manifest_path.exists():
        raise ValueError("Use a new output directory; prepared datasets are immutable")
    sensor = json.loads((ROOT/config["sensor_config"]).read_text())["config"]
    sensor.update(width=config["model"]["width"], height=config["model"]["height"],
                  portable_pixels="remap", ordered_packet=True)
    result = {"status": "preparing", "pilot": pilot, "max_frames": max_frames,
              "sensor_config": sensor, "datasets": {k: [] for k in groups},
              "sources": {name: digest(ROOT/name) for name in
                          ("odometry_data.py", "streaming.py", "orientation.py", "common.py", "pairs.py")}}
    write_json(manifest_path, result)
    for split, parents in groups.items():
        for parent in parents:
            path = ROOT/parent["path"]
            if digest(path) != parent["sha256"]:
                raise ValueError(f"Changed archive: {path}")
            for crop in config["data"]["crops_s"]:
                f = Flight(path, crop=crop, stop=max_frames)
                # Valid static poses are necessary for camera-centre displacement losses.
                h, w = f.frames[0].shape[:2]
                state = Inputs(sensor, f.K, (h, w), f.T_bc[:3, :3])
                images, imu, rotation = [], [], []
                for t, frame, packet in variant_rows(f, "clean", config["seed"]):
                    im, u, rot, _ = state.step(t, frame, packet, "triple_derot")
                    images.append(im); imu.append(u); rotation.append(rot.copy())
                key = hashlib.sha256(f"{parent['sha256']}:{crop}".encode()).hexdigest()[:20]
                target = output/f"{split}-{key}.npz"
                np.savez_compressed(target, images=np.stack(images), imu=np.stack(imu),
                                    R=np.stack(rotation), v=f.v_body, times=f.ft,
                                    cam_gt=f.cam_gt, T_bc=f.T_bc)
                v = f.v_body
                record = {"file": target.name, "sha256": digest(target), "scene": parent["scene"],
                          "parent_sha256": parent["sha256"], "crop_s": crop, "frames": len(v),
                          "backward_fraction": float(np.mean(v[:, 0] < -.2)),
                          "lateral_fraction": float(np.mean(np.abs(v[:, 1]) > .2))}
                result["datasets"][split].append(record)
                write_json(manifest_path, result)
                print(split, parent["scene"], crop, len(v), flush=True)
    result["status"] = "completed"
    write_json(manifest_path, result)
    return manifest_path


def load_row(root, record):
    """`root` is a prepared directory or a store (odometry_store) that resolves records."""
    rows = getattr(root, "rows", None)
    if rows is not None and record["file"] in rows:
        return rows[record["file"]]  # shared, read-only
    path = root.path(record) if hasattr(root, "path") else Path(root)/record["file"]
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


class Preloaded:
    """A store whose records are decompressed into RAM once (in threads), so windows and
    development replays are slices instead of re-inflating a whole .npz per window.
    Identical arrays to load_row; opt-in via training.preload."""
    def __init__(self, store, records, threads=16):
        from concurrent.futures import ThreadPoolExecutor
        self.store = store
        records = list({r["file"]: r for r in records}.values())
        with ThreadPoolExecutor(threads) as pool:
            self.rows = dict(zip([r["file"] for r in records], pool.map(lambda r: load_row(store, r), records)))

    def __getattr__(self, name):
        return getattr(self.store, name)


class Windows(Dataset):
    def __init__(self, root, records, length, burn_in, windows_per_parent, seed):
        self.root = root if hasattr(root, "path") else Path(root)
        self.records = records
        self.length, self.burn = length, burn_in
        self.windows, self.seed, self.epoch = windows_per_parent, seed, 0
        if any(r["frames"] < length+burn_in for r in records):
            raise ValueError("Prepared episodes shorter than training window + burn-in")

    def __len__(self):
        return len(self.records)*self.windows

    def __getitem__(self, index):
        record = self.records[index//self.windows]
        row = load_row(self.root, record)
        size = self.length+self.burn
        rng = np.random.default_rng([self.seed, self.epoch, index])
        # Include raw-reset prefixes explicitly, as well as later contiguous windows.
        begin = 0 if index % self.windows == 0 else int(rng.integers(len(row["v"])-size+1))
        sample = {k: (v if k == "T_bc" else v[begin:begin+size]) for k, v in row.items()}
        return {k: torch.from_numpy(np.ascontiguousarray(v)).to(torch.float32) if k != "images"
                else torch.from_numpy(np.ascontiguousarray(v)) for k, v in sample.items()}


# ---------------------------------------------------------------------------------------
# Planned window sampling.
#
# Motion categories come from training labels only (truth body velocity and truth camera
# positions). They choose which windows are drawn and never enter model inputs.
# Definitions, per frame:
#   moving    speed > 0.2 m/s                  still/hover  speed < 0.05 m/s
#   backward  body forward velocity < -0.2     lateral      |body lateral velocity| > 0.2
#   vertical  |body vertical velocity| > 0.2   braking      moving and d(speed)/dt < -0.4 m/s^2
#   turning   horizontal travel faster than 0.2 m/s and its heading turning > 0.4 rad/s
# Speeds and derivatives use a 5-frame (0.25 s) moving average. Categories overlap; near-zero
# speed frames are only ever "hover", never backward/lateral/vertical.
# A window contains a category when at least max(3 frames, 10%) of its scored frames
# (after burn-in) carry the label.
# ---------------------------------------------------------------------------------------
CATEGORIES = ("backward", "lateral", "vertical", "braking", "turning", "hover")
MOVING, STILL = .2, .05


def load_fields(root, record, keys):
    rows = getattr(root, "rows", None)
    if rows is not None and record["file"] in rows:
        return {key: rows[record["file"]][key] for key in keys}
    path = root.path(record) if hasattr(root, "path") else Path(root)/record["file"]
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in keys}


def _smooth(x, n=5):
    kernel = np.ones(n)/n
    pad = np.pad(x, [(n//2, n//2)] + [(0, 0)]*(x.ndim-1), mode="edge")
    return np.apply_along_axis(lambda c: np.convolve(c, kernel, mode="valid"), 0, pad)


def motion_labels(v, times, cam_gt):
    v = _smooth(np.asarray(v, float))
    speed = np.linalg.norm(v, axis=1)
    accel = np.gradient(speed, times)
    velocity = _smooth(np.gradient(np.asarray(cam_gt, float), times, axis=0))
    horizontal = np.hypot(velocity[:, 0], velocity[:, 2])  # camera-0 axes: x right, y down, z forward
    heading = np.unwrap(np.arctan2(velocity[:, 0], velocity[:, 2]))
    turn = np.abs(_smooth(np.gradient(heading, times)))
    moving = speed > MOVING
    return {"backward": moving & (v[:, 0] < -MOVING), "lateral": moving & (np.abs(v[:, 1]) > MOVING),
            "vertical": moving & (np.abs(v[:, 2]) > MOVING), "braking": moving & (accel < -.4),
            "turning": (horizontal > MOVING) & (turn > .4), "hover": speed < STILL}


class WindowPlan:
    """Deterministic per-epoch list of (record, start, kind) windows plus exposure accounting.

    mode "original": the control. Each epoch visits windows_per_epoch/2 parents (cycling
      through reshuffled passes so parents are covered evenly) with one startup window and one
      uniformly placed window each, which equals the original sampler on the original roster.
    mode "balanced": each draw picks a kind from `mixture`; startup/uniform kinds pick a scene,
      then a parent within it, uniformly; category kinds pick uniformly among scenes having an
      eligible window, then parents within that scene having one, then an eligible start.
      `per_parent_cap` bounds draws per parent per epoch so hard examples come from many flights.
    """

    def __init__(self, records, labels, size, burn, options, seed):
        self.records, self.size, self.burn, self.seed = records, size, burn, seed
        self.mode = options.get("mode", "original")
        self.windows = int(options["windows_per_epoch"])
        if self.mode == "original" and self.windows % 2:
            raise ValueError("The original sampler draws windows in startup/uniform pairs: windows_per_epoch must be even")
        self.mixture = options.get("mixture", {"startup": .5, "uniform": .5})
        self.cap = options.get("per_parent_cap")
        need = max(3, int(np.ceil(options.get("min_fraction", .1)*(size-burn))))
        self.labels = labels
        self.eligible = []
        for lab in labels:
            n = len(next(iter(lab.values())))
            starts = np.arange(n-size+1)
            entry = {}
            for cat in CATEGORIES:
                cum = np.r_[0, np.cumsum(lab[cat])]
                count = cum[starts+size] - cum[starts+burn]
                entry[cat] = starts[count >= need]
            entry["n_starts"] = len(starts)
            self.eligible.append(entry)
        # Optional domain shares (e.g. {"native": 0.213, "proxy": 0.787}): each draw first picks a
        # domain by share, then scene/parent/window inside it. Requires a "domain" field per record.
        self.domain_share = options.get("domain_share")
        self.by_scene = {}
        for i, r in enumerate(records):
            key = (r.get("domain"), r["scene"]) if self.domain_share else (None, r["scene"])
            self.by_scene.setdefault(key, []).append(i)
        if self.domain_share and not set(self.domain_share) <= {d for d, _ in self.by_scene}:
            raise ValueError("domain_share names a domain with no records")

    def _pick_parent(self, rng, kind, counts, domain=None):
        pool = {k: v for k, v in self.by_scene.items() if domain is None or k[0] == domain}
        if kind in ("startup", "uniform"):
            scenes = list(pool)
        else:
            scenes = [s for s, idx in pool.items() if any(len(self.eligible[i][kind]) for i in idx)]
            if not scenes:
                return None
        for _ in range(50):
            scene = scenes[rng.integers(len(scenes))]
            parents = self.by_scene[scene] if kind in ("startup", "uniform") else \
                [i for i in self.by_scene[scene] if len(self.eligible[i][kind])]
            i = parents[rng.integers(len(parents))]
            if not self.cap or counts.get(i, 0) < self.cap:
                return i
        return i

    def plan(self, epoch):
        rng = np.random.default_rng([self.seed, epoch, 7])
        items = []
        if self.mode == "original":
            per_epoch = self.windows//2
            first, order = epoch*per_epoch, []
            passes = range(first//len(self.records), (first+per_epoch)//len(self.records)+1)
            for k in passes:
                order += [(k, int(i)) for i in np.random.default_rng([self.seed, k, 11]).permutation(len(self.records))]
            begin = first - passes[0]*len(self.records)
            for _, i in order[begin:begin+per_epoch]:
                items.append((i, 0, "startup"))
                items.append((i, int(rng.integers(self.eligible[i]["n_starts"])), "uniform"))
        else:
            kinds = list(self.mixture)
            weights = np.array([self.mixture[k] for k in kinds], float); weights /= weights.sum()
            counts = {}
            domains = list(self.domain_share or [])
            shares = np.array([self.domain_share[d] for d in domains], float) if domains else None
            while len(items) < self.windows:
                domain = domains[rng.choice(len(domains), p=shares/shares.sum())] if domains else None
                kind = kinds[rng.choice(len(kinds), p=weights)]
                i = self._pick_parent(rng, kind, counts, domain)
                if i is None:
                    kind, i = "uniform", self._pick_parent(rng, "uniform", counts, domain)
                counts[i] = counts.get(i, 0)+1
                if kind == "startup": start = 0
                elif kind == "uniform": start = int(rng.integers(self.eligible[i]["n_starts"]))
                else:
                    starts = self.eligible[i][kind]; start = int(starts[rng.integers(len(starts))])
                items.append((i, start, kind))
        return [items[j] for j in rng.permutation(len(items))]

    def exposure(self, items):
        """What the epoch actually presented: draw kinds, label fractions over scored frames,
        windows containing each category, unique parents/scenes, burn-in counted separately."""
        draws = {}
        scored = {c: 0 for c in CATEGORIES}
        containing = {c: 0 for c in CATEGORIES}
        total = 0
        need = max(3, int(np.ceil(.1*(self.size-self.burn))))
        mix = {}
        for i, start, kind in items:
            draws[kind] = draws.get(kind, 0)+1
            lab = self.labels[i]
            r = self.records[i]
            key = f"{r.get('domain', '?')}/{r.get('tier') or r.get('regime') or '?'}"
            mix[key] = mix.get(key, 0)+1
            for c in CATEGORIES:
                hits = int(lab[c][start+self.burn:start+self.size].sum())
                scored[c] += hits
                containing[c] += hits >= need
            total += self.size-self.burn
        n = len(items)
        return {"windows": n, "draws": draws, "scored_frames": total, "burn_in_frames": n*self.burn,
                "scored_label_fraction": {c: round(scored[c]/total, 4) for c in CATEGORIES},
                "windows_containing": {c: round(containing[c]/n, 4) for c in CATEGORIES},
                "unique_parents": len({i for i, _, _ in items}),
                "unique_scenes": len({self.records[i]["scene"] for i, _, _ in items}),
                "domain_tier_windows": mix}


class PlannedWindows(Dataset):
    def __init__(self, root, records, length, burn_in, options, seed):
        self.root = root if hasattr(root, "path") else Path(root)
        self.records, self.length, self.burn = records, length, burn_in
        if any(r["frames"] < length+burn_in for r in records):
            raise ValueError("Prepared episodes shorter than training window + burn-in")
        labels = []
        for r in records:
            f = load_fields(self.root, r, ("v", "times", "cam_gt"))
            labels.append(motion_labels(f["v"], f["times"], f["cam_gt"]))
        self.planner = WindowPlan(records, labels, length+burn_in, burn_in, options, seed)
        self.set_epoch(0)

    def set_epoch(self, epoch):
        self.epoch = epoch
        self.items = self.planner.plan(epoch)
        self.exposure = self.planner.exposure(self.items)

    def __len__(self):
        return self.planner.windows

    def __getitem__(self, index):
        i, begin, _ = self.items[index]
        row = load_row(self.root, self.records[i])
        size = self.length+self.burn
        sample = {k: (v if k == "T_bc" else v[begin:begin+size]) for k, v in row.items()}
        return {k: torch.from_numpy(np.ascontiguousarray(v)).to(torch.float32) if k != "images"
                else torch.from_numpy(np.ascontiguousarray(v)) for k, v in sample.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT/"configs/odometry.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    print(prepare(args.config, args.output, args.pilot, args.max_frames))
