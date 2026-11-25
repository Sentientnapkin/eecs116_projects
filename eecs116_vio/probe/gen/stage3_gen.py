"""Generate stage-3-like test flights: FoV U(75, 135) deg, motion blur (exposure 5-50 ms), hover or in-flight starts,
rooms + warehouse + forest. Targets and reasoning: eecs116_vio/probe/README.md.

    VIOBENCH_TASK_EXTRA="<autopilot constants>" python stage3_gen.py OUT_DIR --scenes S1 S2 ... [options]

Needs the gpu_kit viobench patch (VIOBENCH_TASK_EXTRA hook, gpu_kit/setup.sh). The Warehouse and Forest scenes need
hyperlux/hyperdrone >= 0.1.11 (pip install -U hyperlux hyperdrone).
Each scene gets --episodes flights. Per flight: hover start with probability --hover-frac (1 s hover, 60 s), otherwise an
in-flight start (fly 60 + C s from a short hover, then drop the first C s, C ~ U(--crop-min, --crop-max)).
Exposure: k ~ U{kmin..10} IMU-rate renders (5 ms each) averaged in linear light, which is how viobench integrates
exposure (hyperdrone_world.h.in: "exposure is integrated over rendered sub-frames in Python").
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

ORIGINALS = {"Warehouse": "conta:77d055df9fe567fd73201bd925647a65851b0642",   # hyperlux 0.1.11 hyperdrone-originals
             "Forest": "conta:edc4844529111a92755b95b3d845d61bb1faa04c"}


def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.maximum(x, 0), 1 / 2.4) - 0.055)


def blur_camera_factory(kmin, kmax):
    def blur_camera(rng, imu_rate_hz):
        k = int(rng.integers(kmin, kmax + 1))

        def develop(renders, _rng):  # renders: (k, H, W, 3) sRGB float32 in [0, 1], oldest first
            mean = srgb_to_linear(renders.astype(np.float64)).mean(axis=0)
            return np.clip(np.rint(linear_to_srgb(mean) * 255.0), 0, 255).astype(np.uint8)

        return k, develop, {"exposure_steps": k, "exposure_seconds": k / imu_rate_hz}
    return blur_camera


def crop_episode(e, start):
    """Drop the first `start` seconds: an in-flight start (same logic as eecs116_vio/b16/regen_flight.py)."""
    from viobench.tools.datasets.episode import Episode
    k = int(np.searchsorted(e.frame_times, e.frame_times[0] + start - 1e-9))
    shift = e.frame_times[k] - e.frame_times[0]
    t0 = e.frame_times[k] - e.frame_interval - 1e-6
    imu = e.imu[e.imu[:, 0] > t0].copy(); imu[:, 0] -= shift
    gt = e.ground_truth[e.ground_truth[:, 0] >= t0 - 0.02].copy(); gt[:, 0] -= shift
    config = json.loads(json.dumps(e.config))
    config["episode"]["num_frames"] = int(e.num_frames - k)
    c = Episode(name=e.name, config=config, frame_times=e.frame_times[k:] - shift, frames=np.asarray(e.frames)[k:],
                imu=imu, ground_truth=gt, T_body_camera=e.T_body_camera,
                meta={k2: v for k2, v in e.meta.items() if k2 not in ("hash", "path")} | {"crop_start_s": start})
    c.check_consistency()
    return c


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--scenes", nargs="+", required=True, help="ProcTHOR-Train-N, HSSD ids, Warehouse, Forest")
    p.add_argument("--episodes", type=int, default=2, help="flights per scene")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--hover-frac", type=float, default=0.2, help="server: about 4-5 of 24 are hover starts")
    p.add_argument("--crop-min", type=float, default=5.0)
    p.add_argument("--crop-max", type=float, default=25.0)
    p.add_argument("--fov", type=float, default=105.0)
    p.add_argument("--fov-range", type=float, default=30.0, help="FoV = fov + U(-range, range): 75-135 deg")
    p.add_argument("--kmin", type=int, default=1, help="exposure renders (5 ms each); the server draws 0-50 ms")
    p.add_argument("--kmax", type=int, default=10)
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--instances", type=int, default=1)
    a = p.parse_args()

    from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate
    from viobench.tools.datasets.storage import write_episode

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    camera = blur_camera_factory(a.kmin, a.kmax)
    for si, scene in enumerate(a.scenes):
        refs = {scene: ORIGINALS[scene]} if scene in ORIGINALS else scene_references([scene])
        for ei in range(a.episodes):
            name = f"s3-{scene}-{ei:02d}"
            if (out / f"{name}.zip").exists():
                continue
            seed = int(a.seed * 1000 + si * 50 + ei)
            hover = rng.random() < a.hover_frac
            crop = 0.0 if hover else round(float(rng.uniform(a.crop_min, a.crop_max)), 2)
            seconds = a.duration + crop
            sim = SimConfig(instances=a.instances, duration_seconds=seconds, hold_seconds=1.0 if hover else 0.2,
                            waypoints=max(8, round(seconds * 0.8)), fov=a.fov, fov_range=a.fov_range)
            episode = next(iter(simulate(sim, refs, 1, seed=seed, camera=camera, name="s3", log=lambda m: print(m, flush=True))))
            if crop:
                episode = crop_episode(episode, crop)
            episode.meta = dict(episode.meta) | {"stage3_gen": {"hover": hover, "crop_s": crop, "seed": seed,
                                                               "task_extra": os.environ.get("VIOBENCH_TASK_EXTRA", "")}}
            write_episode(episode, out / f"{name}.zip")
            print(f"wrote {name}.zip  hover={hover} crop={crop}s  exposure={episode.config['episode']['exposure_seconds'] * 1e3:.0f} ms  "
                  f"fov={episode.config['camera']['horizontal_fov_degrees']:.1f}", flush=True)


if __name__ == "__main__":
    main()
