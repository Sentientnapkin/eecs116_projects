"""Resolve a published N1 roster from local shards and assemble verified feature caches."""
import argparse
import json
from pathlib import Path

from visual_motion_cache import digest


def link(target, source, expected):
    if digest(source) != expected:
        raise ValueError(f"Checksum mismatch: {source}")
    target.symlink_to(source.resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--campaign-dev", type=Path, required=True)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--reuse", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    manifest["n1_source_sha256"] = digest(args.manifest)
    manifest["campaign_dev_sha256"] = digest(args.campaign_dev)
    dev = json.loads(args.campaign_dev.read_text())["records"]
    train = manifest["datasets"]["train"]
    old_dev = manifest["datasets"]["development"]
    if not dev or {r.get("split") for r in dev} != {"dev"}:
        raise ValueError("Expected published campaign development records")
    if any(row.get("split") in {"test", "dev"} for row in train):
        raise ValueError("Reserved or development record in training")
    for field in ("scene", "parent_sha256"):
        if {r[field] for r in train} & {r[field] for r in old_dev + dev}:
            raise ValueError(f"Train/development overlap by {field}")

    covered = {}
    identity = None
    for root in args.reuse:
        cached = json.loads((root/"manifest.json").read_text())
        spec = dict(cached["visual_cache"])
        spec.pop("prepared_manifest_sha256")
        if identity is not None and spec != identity:
            raise ValueError("Cannot mix feature caches from different extractors")
        identity = spec
        for records in cached["datasets"].values():
            for row in records:
                covered[row["prepared_sha256"]] = (root/row["file"], row["sha256"])

    args.output.mkdir(parents=True, exist_ok=False)
    missing = {"datasets": {}, "status": "completed"}
    if identity:
        manifest["visual_cache"] = {**identity, "prepared_manifest_sha256": digest(args.manifest)}
    for split, records in (*manifest["datasets"].items(), ("campaign", dev)):
        for row in records:
            file, checksum = row["file"], row["sha256"]
            cached = covered.get(checksum)
            if cached:
                path, feature_checksum = cached
                link(args.output/file, path, feature_checksum)
                row.update(prepared_sha256=checksum, sha256=feature_checksum)
            else:
                path = next((folder/file for folder in args.source if (folder/file).is_file()), None)
                if path is None:
                    raise FileNotFoundError(file)
                if args.reuse:
                    (args.output/"missing").mkdir(exist_ok=True)
                    link(args.output/"missing"/file, path, checksum)
                    missing["datasets"].setdefault(split, []).append(row)
                else:
                    link(args.output/file, path, checksum)
    if missing["datasets"]:
        (args.output/"missing"/"manifest.json").write_text(json.dumps(missing, indent=2)+"\n")
    manifest["campaign_development"] = dev
    (args.output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")


if __name__ == "__main__":
    main()
