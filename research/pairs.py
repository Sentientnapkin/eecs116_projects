"""Versioned endpoint-velocity caches built from raw, reset sensor streams."""
import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
from common import Flight
from streaming import Inputs

CONFIG = Path(__file__).with_name("experiments.json")


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _digest(stream)


def _digest(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1 << 20), b""):
        h.update(block)
    return h.hexdigest()


def config():
    return json.loads(CONFIG.read_text())


def disturbance_seed(path, config):
    tag = Path(path).name.encode()
    return int.from_bytes(hashlib.sha256(tag).digest()[:4],"little") ^ config.get("disturbance_seed",651)


def added_gyro(t, disturbance, seed=651):
    time = np.asarray(t,dtype=float)
    rng=np.random.default_rng(seed)
    constant=rng.uniform(-.05,.05,3)
    if disturbance=="changing":
        rate=rng.uniform(.09,.3,3)
        phase=rng.uniform(0,2*np.pi,3)
        return constant + rng.uniform(.01,.03,3)*np.sin(time[...,None]*rate+phase)
    if disturbance=="constant":
        return np.broadcast_to(constant,(*time.shape,3))
    return np.zeros((*time.shape,3))


def corrupted_packet(packet, t, previous, disturbance, rng, seed):
    if not disturbance:
        return packet
    packet = packet.copy()
    packet[:,4:7] += added_gyro(packet[:,0],disturbance,seed)
    if disturbance=="changing" and len(packet):
        packet[:,0] = np.sort(np.clip(packet[:,0]+rng.uniform(-.001,.001,len(packet)),previous+1e-8,t))
    return packet


def sensor_rows(flight, cfg):
    stress = cfg.get("disturbance")
    seed=disturbance_seed(flight.path,cfg)
    rng = np.random.default_rng(seed)
    for i,(t,frame,packet) in enumerate(zip(flight.ft,flight.frames,flight.win)):
        prev = flight.ft[i-1] if i else t
        packet = corrupted_packet(packet,t,prev,stress,rng,seed)
        if stress=="changing" and i and i%137 in (0,1,2):
            frame = None
        yield t,frame,packet

def variant_rows(flight, condition, seed):
    """Corrupt sensor observations in reset-relative time, before feature construction."""
    if condition == "original-combined":
        yield from sensor_rows(flight, {"disturbance": "changing", "disturbance_seed": seed})
        return
    bias = {"constant": "constant", "changing": "changing", "combined": "changing"}.get(condition)
    jitter = condition in ("jitter", "combined")
    gaps = condition in ("gaps", "combined")
    rng = np.random.default_rng(disturbance_seed(flight.path, {"disturbance_seed": seed}))
    bias_seed = disturbance_seed(flight.path, {"disturbance_seed": seed})
    for i, (t, frame, packet) in enumerate(zip(flight.ft, flight.frames, flight.win)):
        if i and (bias or jitter) and len(packet):
            packet = packet.copy()
            packet[:,4:7] += added_gyro(packet[:,0], bias, bias_seed)
            if jitter:
                previous = flight.ft[i-1]
                stamps = packet[:,0]
                # Limit each displacement to a quarter of its adjacent sample spacings.
                separation = np.diff(stamps) / 4
                left = np.r_[max(0., stamps[0]-previous-1e-9), separation]
                right = np.r_[separation, max(0., t-stamps[-1])]
                if np.any(separation <= 0):
                    raise ValueError("source packet is not strictly ordered")
                stamps[:] = np.clip(stamps + np.clip(rng.uniform(-.001,.001,len(packet)), -left, right),
                                    previous+1e-9, t)
        if gaps and i and i%137 in (0,1,2):
            frame = None
        yield t, frame, packet


def build(path, cfg=None, crop=0., stop=None):
    cfg = config() if cfg is None else cfg
    provenance = {"parent": digest(path), "config": cfg, "crop_s": crop, "stop": stop,
                  "reset": "raw_before_streaming", "target": "endpoint_body_velocity",
                  "sources": {name: digest(Path(__file__).with_name(name))
                              for name in ("pairs.py", "common.py", "orientation.py", "streaming.py")}}
    key = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    output = Path("data/causal") / f"{key}.npz"
    if output.exists():
        with np.load(output, allow_pickle=False) as cached:
            if json.loads(str(cached["provenance"])) == provenance:
                return output
    flight = Flight(path, crop, stop)
    shape=flight.frames[0].shape[:2]
    inputs = Inputs(cfg, flight.K, shape, flight.T_bc[:3,:3])
    records = [inputs.step(t,frame,packet) for t,frame,packet in sensor_rows(flight,cfg)]
    images, imu, rotations, _ = [np.stack(group) for group in zip(*records)]
    added = added_gyro(flight.ft,cfg.get("disturbance"),disturbance_seed(path,cfg))
    if cfg.get("disturbance") and cfg.get("ordered_packet"):
        clean = Inputs(cfg,flight.K,shape,flight.T_bc[:3,:3])
        calibration = np.stack([clean.step(t,im,p,"imu")[1][-8:-5]
                                for t,im,p in zip(flight.ft,flight.frames,flight.win)])
        added = added + calibration - imu[:,-8:-5]
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f".{uuid4().hex}.npz")
    np.savez(temp, images=images, imu=imu, R=rotations.astype(np.float32),
             v=flight.v_body.astype(np.float32), bias_target=added.astype(np.float32), R_truth=flight.R.astype(np.float32),
             p=flight.p.astype(np.float32), times=flight.ft, T_bc=flight.T_bc,
             cam_gt=flight.cam_gt, scene=flight.scene, tier=flight.tier,
             provenance=json.dumps(provenance, sort_keys=True))
    os.replace(temp, output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern")
    parser.add_argument("--crop", type=float, default=0.)
    parser.add_argument("--policy", choices=("none", "startup", "evidence"), default=config()["policy"])
    args = parser.parse_args()
    paths = sorted(glob.glob(args.pattern))
    if not paths:
        parser.error("no matching flights")
    for path in paths:
        print(build(path, {**config(), "policy": args.policy}, args.crop), flush=True)
