"""Prepared training datasets on a private Hugging Face dataset repo, streamed through a
size-capped local cache.

Layout on the Hub: every prepared episode lives once in shards/<file>.npz (names are
content keys), and manifests/<name>.json snapshots say which shards form a dataset. A
snapshot is immutable once completed, so a run's manifest digest pins its exact data,
while generated flights keep growing the shard pool.

Training visits shards in groups: while one group trains, the next group downloads in a
background thread. A file is evicted, least recently used first, only when it is in
neither the current group, the next group, nor the pinned development set. That keeps
disk use near the budget however large the dataset on the Hub grows.
"""
import argparse
import json
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from huggingface_hub import HfApi, hf_hub_download
from torch.utils.data import Sampler

from pairs import digest

DATA_REPO = "SentientNapkin/viobench-teacher-data"


def ensure_private(repo=DATA_REPO):
    api = HfApi()
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    if not api.repo_info(repo, repo_type="dataset").private:
        raise RuntimeError(f"{repo} is public; refusing to store data there")
    return api


def push_shards(local_dir, files, repo=DATA_REPO, message="Add shards"):
    api = ensure_private(repo)
    api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=str(local_dir),
                      path_in_repo="shards", allow_patterns=sorted(files), commit_message=message)


def push_manifest(manifest, name, repo=DATA_REPO, message=None):
    api = ensure_private(repo)
    api.upload_file(path_or_fileobj=(json.dumps(manifest, indent=2, allow_nan=False)+"\n").encode(),
                    path_in_repo=f"manifests/{name}.json", repo_id=repo, repo_type="dataset",
                    commit_message=message or f"Manifest {name}")


def push(local_dir, name, repo=DATA_REPO):
    """Upload a completed local prepared dataset: its shards, then its manifest snapshot.

    Shards are content-addressed on the Hub (<sha256>.npz), so datasets prepared with
    different settings from the same parent can never overwrite each other.
    """
    import os, shutil, tempfile
    local_dir = Path(local_dir)
    manifest = json.loads((local_dir/"manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError("Only completed datasets can be pushed")
    staging = Path(tempfile.mkdtemp(prefix="shards-", dir=local_dir.parent))
    try:
        for rows in manifest["datasets"].values():
            for r in rows:
                if r["file"] != f"{r['sha256']}.npz":
                    r["source_file"], target = r["file"], staging/f"{r['sha256']}.npz"
                    if not target.exists():
                        os.link(local_dir/r["file"], target)  # hard link: no extra disk
                    r["file"] = target.name
        files = {r["file"] for rows in manifest["datasets"].values() for r in rows}
        push_shards(staging, files, repo, f"Shards for {name} ({len(files)})")
    finally:
        shutil.rmtree(staging)
    push_manifest(manifest, name, repo)
    return f"https://huggingface.co/datasets/{repo}/blob/main/manifests/{name}.json ({len(files)} shards)"


def fetch_manifest(name, repo=DATA_REPO, cache_dir=None):
    path = hf_hub_download(repo, f"manifests/{name}.json", repo_type="dataset", local_dir=cache_dir)
    return json.loads(Path(path).read_text())


def snapshot(name, base, pools, repo=DATA_REPO, max_added=None):
    """Freeze base's splits plus the training records currently in each pool manifest.

    Development records always come from base, so scores stay comparable across snapshots.
    Pool scenes that collide with base development scenes are dropped.
    """
    root = fetch_manifest(base, repo)
    dev_scenes = {r["scene"] for r in root["datasets"]["development"]}
    train = list(root["datasets"]["train"])
    seen = {r["sha256"] for r in train}
    added = []
    for pool in pools:
        for r in fetch_manifest(pool, repo)["datasets"].get("train", []):
            if r["sha256"] not in seen and r["scene"] not in dev_scenes:
                added.append(r); seen.add(r["sha256"])
    if max_added is not None:
        added = added[:max_added]
    if f"manifests/{name}.json" in HfApi().list_repo_files(repo, repo_type="dataset"):
        raise ValueError(f"Manifest {name} already exists; snapshots are immutable, use a new name")
    manifest = dict(root, status="completed", snapshot={"base": base, "pools": pools,
                    "added_train_records": len(added)},
                    datasets={"train": train + added, "development": root["datasets"]["development"]})
    push_manifest(manifest, name, repo, f"Snapshot {name}: {len(train)} base + {len(added)} added")
    return manifest


class ShardCache:
    """Resolves manifest records to local paths, downloading and evicting on demand."""

    def __init__(self, name, cache_dir, budget_bytes, repo=DATA_REPO, workers=2):
        self.repo, self.name, self.budget = repo, name, budget_bytes
        self.root = Path(cache_dir)  # files land at root/shards/<file>
        self.dir = self.root/"shards"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.inflight = {}
        self.lru = OrderedDict()  # file -> bytes, oldest first
        self.protected = set()
        self.pool = ThreadPoolExecutor(workers)
        self.downloads = self.evictions = 0
        for path in self.dir.glob("*.npz"):
            self.lru[path.name] = path.stat().st_size

    def _download(self, name):
        hf_hub_download(self.repo, f"shards/{name}", repo_type="dataset", local_dir=self.root)
        return self.dir/name

    def manifest_path(self):
        return Path(hf_hub_download(self.repo, f"manifests/{self.name}.json", repo_type="dataset",
                                    local_dir=self.root))

    def _fetch(self, record):
        name = record["file"]
        path = self.dir/name
        if not path.exists() or digest(path) != record["sha256"]:
            path.unlink(missing_ok=True)
            self._download(name)
            if digest(path) != record["sha256"]:
                path.unlink(missing_ok=True)
                raise ValueError(f"Checksum mismatch after download: {name}")
            self.downloads += 1
        with self.lock:
            self.lru[name] = path.stat().st_size
            self.lru.move_to_end(name)
            self._evict()
        return path

    def _evict(self):
        total = sum(self.lru.values())
        for name in list(self.lru):
            if total <= self.budget:
                break
            if name in self.protected or name in self.inflight:
                continue
            total -= self.lru.pop(name)
            (self.dir/name).unlink(missing_ok=True)
            self.evictions += 1

    def prefetch(self, records):
        with self.lock:
            for r in records:
                if r["file"] not in self.inflight:
                    self.inflight[r["file"]] = self.pool.submit(self._fetch, r)

    def path(self, record):
        self.prefetch([record])
        future = self.inflight[record["file"]]
        path = future.result()
        with self.lock:
            if self.inflight.get(record["file"]) is future:
                del self.inflight[record["file"]]
            if record["file"] in self.lru:
                self.lru.move_to_end(record["file"])
        return path

    def protect(self, records):
        with self.lock:
            self.protected = {r["file"] for r in records}

    def stats(self):
        return {"downloads": self.downloads, "evictions": self.evictions,
                "cached_bytes": sum(self.lru.values()), "budget_bytes": self.budget}


class LocalStore:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, record):
        return self.root/record["file"]

    def manifest_path(self):
        return self.root/"manifest.json"

    def prefetch(self, records):
        pass

    def protect(self, records):
        pass

    def stats(self):
        return {}


def open_store(spec, cache_dir, budget_gb, repo=DATA_REPO):
    """`hf:<name>` streams from the Hub; anything else is a local prepared directory."""
    if spec.startswith("hf:"):
        return ShardCache(spec[3:], cache_dir, int(budget_gb*2**30), repo)
    return LocalStore(Path(spec).resolve())


class GroupedSampler(Sampler):
    """Shuffle parents into groups, shuffle windows within a group, prefetch the next group.

    Deterministic in (seed, epoch) and independent of the store, so streaming from the
    Hub trains on exactly what the same run would train on from a local directory.
    """

    def __init__(self, records, windows, group, seed, store, pinned=()):
        self.records, self.windows, self.group = records, windows, group
        self.seed, self.store, self.pinned, self.epoch = seed, store, list(pinned), 0

    def set_epoch(self, epoch):
        self.epoch = epoch

    def __len__(self):
        return len(self.records)*self.windows

    def __iter__(self):
        rng = np.random.default_rng([self.seed, self.epoch, 7919])
        order = rng.permutation(len(self.records))
        groups = [order[i:i+self.group] for i in range(0, len(order), self.group)]
        for k, members in enumerate(groups):
            upcoming = groups[k+1] if k+1 < len(groups) else []
            current = [self.records[i] for i in members]
            following = [self.records[i] for i in upcoming]
            self.store.protect(self.pinned + current + following)
            self.store.prefetch(current + following)
            indices = [int(i)*self.windows + w for i in members for w in range(self.windows)]
            yield from rng.permutation(indices).tolist()


def compose(name, base, record_files, repo=DATA_REPO, expected_new_parents=None):
    """Immutable snapshot: base train + development records unchanged, plus verified extra
    training records (e.g. data/expand/*.json). Rejects scene or parent leakage into dev."""
    from odometry_data import validate_roster
    if f"manifests/{name}.json" in HfApi().list_repo_files(repo, repo_type="dataset"):
        raise ValueError(f"Manifest {name} already exists; snapshots are immutable")
    root = fetch_manifest(base, repo)
    extra = [r for f in record_files for r in json.loads(Path(f).read_text())["records"]]
    if expected_new_parents is not None and len({r["parent_sha256"] for r in extra}) != expected_new_parents:
        raise ValueError(f"Expected {expected_new_parents} new parents, found {len({r['parent_sha256'] for r in extra})}")
    for r in root["datasets"]["train"]:
        r.setdefault("domain", "native" if not str(r.get("source_file", "")).startswith("train-") else "proxy")
    train = root["datasets"]["train"] + extra
    if len({r["sha256"] for r in train}) != len(train):
        raise ValueError("Duplicate shard in training records")
    dev = root["datasets"]["development"]
    validate_roster({"train": train, "development": dev})
    if {r.get("parent_sha256") for r in train} & {r.get("parent_sha256") for r in dev}:
        raise ValueError("Parent leakage between training and development")
    manifest = dict(root, status="completed", composed={"base": base, "added_records": len(extra),
                    "added_parents": len({r["parent_sha256"] for r in extra})},
                    datasets={"train": train, "development": dev})
    push_manifest(manifest, name, repo, f"Compose {name}: {base} + {len(extra)} records")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "push", "snapshot", "compose"))
    parser.add_argument("--records", nargs="*", default=[])
    parser.add_argument("--expect-parents", type=int)
    parser.add_argument("local_dir", nargs="?")
    parser.add_argument("--name", help="Manifest name on the Hub (push: default local folder name)")
    parser.add_argument("--base", default="teacher-full")
    parser.add_argument("--pool", action="append", default=[])
    parser.add_argument("--max-added", type=int)
    parser.add_argument("--repo", default=DATA_REPO)
    args = parser.parse_args()
    if args.action == "init":
        ensure_private(args.repo)
        print(f"https://huggingface.co/datasets/{args.repo} (private)")
    elif args.action == "push":
        print(push(args.local_dir, args.name or Path(args.local_dir).resolve().name, args.repo))
    elif args.action == "compose":
        m = compose(args.name, args.base, args.records, args.repo, args.expect_parents)
        print(args.name, {k: len(v) for k, v in m["datasets"].items()}, m["composed"])
    else:
        m = snapshot(args.name, args.base, args.pool, args.repo, args.max_added)
        print(args.name, {k: len(v) for k, v in m["datasets"].items()})
