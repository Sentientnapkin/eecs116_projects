"""Freeze spatial features from prepared causal triplets for the visual-motion screen."""
import argparse
import hashlib
import json
import subprocess
from argparse import Namespace
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import torch
import torch.nn.functional as F
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file

from teacher_models import Teacher

SEA_CODE = "9137517ba24e628442aec097d3afe71d03503b75"
SEA_MODEL = "MemorySlices/Tartan-C-T-TSKH-spring540x960-S"
SEA_REV = "31b9b4b711bd2d0d0d38cb99d93ba144beb2dc92"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def sea_raft(source, device):
    actual = subprocess.check_output(["git", "-C", source, "rev-parse", "HEAD"], text=True).strip()
    if actual != SEA_CODE or subprocess.check_output(["git", "-C", source, "status", "--porcelain"]):
        raise ValueError("Expected the pinned clean SEA-RAFT checkout")
    sys.path.insert(0, str(source.resolve()/"core"))
    import raft

    config = Namespace(**json.loads((source/"config/eval/spring-S.json").read_text()))
    # Every tensor is loaded strictly below, so ImageNet initializer downloads are redundant.
    fpn = raft.ResNetFPN
    with patch.object(raft, "ResNetFPN", lambda *a, **kw: fpn(*a, **(kw | {"init_weight": False}))):
        model = raft.RAFT(config)
    checkpoint = Path(hf_hub_download(SEA_MODEL, "model.safetensors", revision=SEA_REV))
    weights = load_file(checkpoint)
    # Safetensors stores the shared shortcut normalization under one of its two names.
    for key in model.state_dict().keys() - weights.keys():
        alias = key.replace(".downsample.1.", ".bn3.")
        if alias != key and alias in weights:
            weights[key] = weights[alias]
    model.load_state_dict(weights, strict=True)
    return model.to(device).eval(), checkpoint


def flow_features(model, images):
    """Current-to-warped-history vectors in resized-input pixels, pooled on a 3x4 grid."""
    frames = F.interpolate(images.float(), (96, 128), mode="bilinear", align_corners=False)
    current = frames[:, :1].expand(-1, 3, -1, -1).contiguous()
    features = []
    for history, warp_mask in ((1, 3), (2, 4)):
        previous = frames[:, history:history+1].expand_as(current).contiguous()
        # The four-level correlation pyramid needs at least 128 pixels per axis.
        pad = (0, 0, 16, 16)
        result = model(F.pad(current, pad, mode="replicate"),
                       F.pad(previous, pad, mode="replicate"), iters=4, test_mode=True)
        flow = result["flow"][-1][..., 16:-16, :]
        mask = (frames[:, warp_mask:warp_mask+1] >= 254.5).float()
        _, _, h, w = flow.shape
        x = torch.arange(w, device=flow.device)[None, None, :] + flow[:, 0]
        y = torch.arange(h, device=flow.device)[None, :, None] + flow[:, 1]
        grid = torch.stack((2*x/(w-1)-1, 2*y/(h-1)-1), dim=-1)
        mask = (F.grid_sample(mask, grid, align_corners=True) >= .999).float()
        pool = lambda t: F.adaptive_avg_pool2d(t, (3, 4))
        support = pool(mask)
        features.extend((pool(flow*mask)/support.clamp_min(1e-6), support))
    return torch.cat(features, dim=1).flatten(1)


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--cnn-run", type=Path)
    source.add_argument("--sea-source", type=Path)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    base = args.data/"manifest.json"
    manifest = json.loads(base.read_text())
    identity = {"prepared_manifest_sha256": digest(base), "extractor_sha256": digest(Path(__file__)),
                "layout": "frame-aligned float16 spatial features", "weights": {}}
    if args.cnn_run:
        checkpoint = args.cnn_run/"best.safetensors"
        cfg = json.loads((args.cnn_run/"config.json").read_text())["model"]
        model = Teacher(cfg)
        model.load_state_dict(load_file(checkpoint))
        visual = model.visual.to(args.device).eval()
        encode = lambda images: visual.spatial_features(images[None])[0]
        identity["weights"] = {"architecture": cfg, "code_sha256": digest(Path(__file__).with_name("teacher_models.py"))}
    else:
        model, checkpoint = sea_raft(args.sea_source, args.device)
        encode = lambda images: flow_features(model, images)
        identity["weights"] = {"code": SEA_CODE, "repo": SEA_MODEL, "revision": SEA_REV,
                               "preprocessing": "128x96 bilinear with 16px vertical replicate padding, grayscale repeated to RGB, current-to-gyro-warped histories",
                               "support": "sampled valid warp mask at flow endpoint, 3x4 grid, no uncertainty channel"}
    identity["weights"]["sha256"] = digest(checkpoint)
    if not args.smoke:
        args.output.mkdir(parents=True, exist_ok=False)
    manifest["visual_cache"] = identity
    for split, records in manifest["datasets"].items():
        for record in records:
            path = args.data/record["file"]
            original_sha = digest(path)
            if original_sha != record["sha256"]:
                raise ValueError(f"Prepared shard checksum changed: {path}")
            with np.load(path, allow_pickle=False) as episode:
                arrays = {name: episode[name] for name in episode.files}
            images = arrays["images"][:32] if args.smoke else arrays["images"]
            features = [encode(torch.from_numpy(images[i:i+args.batch]).to(args.device)).cpu().numpy()
                        for i in range(0, len(images), args.batch)]
            features = np.concatenate(features).astype(np.float16)
            if not np.isfinite(features).all():
                raise ValueError(f"Nonfinite features: {path}")
            manifest["visual_cache"]["size"] = features.shape[-1]
            print(split, record["file"], features.shape, flush=True)
            if args.smoke:
                print(f"Feature range {features.min():.4f} to {features.max():.4f}", flush=True)
                return
            arrays["images"] = features
            target = args.output/record["file"]
            np.savez_compressed(target, **arrays)
            record["prepared_sha256"] = original_sha
            record["sha256"] = digest(target)
    (args.output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")


if __name__ == "__main__":
    main()
