"""Regenerate one holdout flight locally, exactly as the teammate's native_campaign.py generate does.
    python regen_flight.py OUT.zip CATALOG SCENE SEED SETTING CROP   (CROP = 0 for a static 'fast-' flight)
Seed/crop come from the flight's episode.json or from replaying make_roster.py's RNG (scratchpad ho_eval/replay3.py).
Task overrides go in through this machine's VIOBENCH_TASK_EXTRA hook (same constants the server inserts)."""
import json, os, sys
import numpy as np

out, catalog, scene, seed, setting, crop = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], float(sys.argv[6])
K = {"CRUISE_SPEED_MIN": 3.0, "CRUISE_SPEED_MAX": 4.5, "MAX_ACCELERATION": 6.0, "MAX_JERK": 30.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
K2 = {"CRUISE_SPEED_MIN": 4.0, "CRUISE_SPEED_MAX": 6.0, "MAX_ACCELERATION": 8.0, "MAX_JERK": 40.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
ov = {"K": K, "K2": K2}[setting]
os.environ["VIOBENCH_TASK_EXTRA"] = " ".join(f"static constexpr T {k} = {float(v)!r};" for k, v in sorted(ov.items()))

from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate, hssd_scenes
from viobench.tools.datasets.storage import write_episode
from viobench.tools.datasets.episode import Episode


def crop_episode(e, start):  # verbatim logic of native_campaign.crop_episode
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


mid = crop > 0
seconds = round(60 + crop, 2) if mid else 60
sim = SimConfig(instances=1, duration_seconds=seconds, hold_seconds=0.2 if mid else 1.0, waypoints=max(8, round(seconds * 0.8)))
refs = hssd_scenes("val", [scene]) if catalog == "hssd-val" else scene_references([scene])
episode, = simulate(sim, refs, 1, seed=seed, name="native-campaign", log=lambda m: None)
episode.check_consistency()
if mid:
    episode = crop_episode(episode, crop)
write_episode(episode, out)
print("wrote", out, episode.num_frames, "frames", flush=True)
