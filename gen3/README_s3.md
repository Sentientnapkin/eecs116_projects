---
license: other
tags: [visual-inertial-odometry, drone, simulation, motion-blur]
configs:
- config_name: manifest
  data_files: manifest.csv
---
# viobench stage-3 flights

Simulated quadrotor flights for visual-inertial odometry in the stage-3 conditions of the viobench course benchmark:
rooms, a large warehouse and a forest, with a wide-angle camera of varying field of view and motion blur.
Every flight is a native **viobench episode zip** (640x480 RGB PNG at 20 Hz, 200 Hz IMU, ground truth, EuRoC/ASL layout),
so `viobench evaluate solution.wasm raw/val/...zip` and `viobench.tools.datasets.read_episode` work on it directly.

@@STATE@@

@@TABLE@@

## What varies per flight (all recorded in `manifest.csv` and in each episode's `episode.json`)

| | |
|---|---|
| scene type (`setting_class`) | `room` (ProcTHOR and HSSD), `warehouse`, `forest` (about 50 / 25 / 25 %) |
| scene | rooms: the scene splits of [viobench-flights](https://huggingface.co/datasets/SentientNapkin/viobench-flights) (train / val / test share no rooms). Warehouse and forest: half in the official HyperDrone Originals scenes (hyperlux 0.1.11, `Warehouse`, `Forest`), half in procedural variants (`scene_variant`, see below) |
| horizontal FoV (`fov_deg`) | uniform 75-135 deg, fixed per flight (the simulator's own draw) |
| exposure (`exposure_s`) | uniform 0-50 ms; a frame averages ceil(exposure / 5 ms) renders taken 5 ms apart (`blur_space`: `linear` light, 75 %, or `srgb`, 25 %) |
| brightness (`brightness_scale`) | uniform 0.6-1.4, the simulator's render brightness |
| heading (`regime`) | about 65 % `free-yaw`: the camera heading is decoupled from the direction of travel (yaw = route direction + offset U(0, 2pi) + A sin(w t + phase), A U(0.2, 1.2) rad, w U(0.2, 0.9) rad/s, drawn per flight), so the drone often flies sideways or backwards relative to the camera and tilts more than it turns; about 35 % `benchmark` (the stock autopilot, camera faces the direction of travel) |
| motion (`motion_style`) | 13 autopilot styles (planner constants in `generator/roster.json` -> `styles`), mixed per scene type and heading regime toward stage-3-like tilt rate, turn rate, speed and path length, with wide coverage around them |
| start (`start`) | about 20 % `hover` starts (1 s hover); the rest `mid-flight`: the first 3-30 s of a longer flight are cropped off (`crop_start_s`), so the drone is already moving at frame 0, often backwards or sideways |
| extra light (`linear_gain`) | a per-flight gain in linear light on top of `brightness_scale`: rooms U(0.55, 1.1), warehouse U(0.8, 1.2), forest U(1.15, 1.8) |
| measured motion | `path_m`, `mean_speed`, `tilt_rms` (roll+pitch gyro RMS), `yaw_rms`, `gyro_rms`, `rms_dist_from_start`, `rms_spread`, `start_speed`, `start_fwd_speed` (camera-forward speed at frame 0) |

IMU noise and camera mount are the viobench defaults (unchanged from earlier stages).

## Quality flag

`quality` = `outside_scene` marks the rare flights (about 1 %) where the drone leaves the room geometry and most frames are black (mean luminance < 25 or > 30 % dark frames). Ground truth and IMU are still valid; filter them out for vision training unless you want blackout examples.

## Versions

`roster_version` 3 is the current design (all counts above). `roster_version` 1 flights came from an earlier mix with the stock heading only (plus a few `independent-yaw`); they are kept and labeled, and are useful as extra data, but the v3 `val` / `test` are the sets to report.

## Splits

- `train`: 10,000 v3 flights. Warehouse/forest flights use the official scenes and variants 1-20.
- `val`: 600 flights in validation rooms; warehouse/forest use the official scenes (`scene_variant = official`) and unseen variants 21-22.
- `test`: 600 flights in the held-out test rooms; warehouse/forest use the official scenes and unseen variants 23-24.

Use `val` for model selection and keep `test` for final numbers. The official warehouse and forest appear in all splits
(the benchmark itself uses them), so report unseen variants separately to measure generalization.

## Files

| path | |
|---|---|
| `raw/<split>/<setting_class>/<id>.zip` | the native episode (lossless) |
| `raw/<split>/<setting_class>/<id>.json` | its labels and measured statistics |
| `shards/<split>-NNNN.tar` | 25 flights each, 320x240 gray JPEG q95 frames + IMU + ground truth, for fast training; read with `load_shards.py` |
| `manifest.csv` | one row per flight; `path` and `shard` locate it |
| `generator/` | the exact generator, roster and planner styles (reproducible: same seed, same bytes) |
| `scenes/params.json` | the parameters of every warehouse/forest variant |

Streaming without a full download:

```python
from huggingface_hub import hf_hub_download
import pandas as pd
m = pd.read_csv(hf_hub_download("SentientNapkin/viobench-stage3", "manifest.csv", repo_type="dataset"))
z = hf_hub_download("SentientNapkin/viobench-stage3", m[m.split == "val"].path.iloc[0], repo_type="dataset")
```

## Scenes

The official scenes are the `hyperdrone-originals` catalog of hyperlux 0.1.11 (conta `77d055df...` warehouse,
`edc48445...` forest). Rebuilding them with Blender 5.3.0 from the shipped `warehouse.py` / `forest.py` reproduces those
hashes exactly; the variants change only the scripts' seed and a few constants (warehouse: rack occupancy, light intensity,
ambient; forest: tree, snag, log, rock and stump counts and ambient light). Variant GLBs are not redistributed here; rebuild
them from `scenes/params.json`.

Generated with viobench `e173f4a`, hyperdrone/hyperlux 0.1.11.
