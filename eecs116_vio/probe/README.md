# Stage-3 probe: what the hidden test flights look like, and how to make local copies of them

Stage 3 (announced 2026-11-25) scores on **24 new hidden episodes**. What the course staff announced:
- The trajectory distribution is the same as stage 2.
- Horizontal FoV is uniform in 75–135°, fixed per episode.
- Motion blur: exposure is uniform in 0–50 ms, fixed per episode.
- 12 episodes are rooms, 6 an empty warehouse and 6 a forest.

The server only returns error metrics and fuel numbers, never the data. So we uploaded a **probe**: a submission
that makes the server's own reports leak statistics of each hidden episode. This folder has the probe, its decoder,
the decoded results, and the tools to generate and check local flights that match them.

**Quick map**

| file | what it is |
|---|---|
| `probe.c` | the probe guest (C, built to wasm). Release build: `../submissions/probe_stage3.wasm` |
| `build.sh` | builds `probe.c` inside WSL/Linux (`bash build.sh release`; `DEFS="DEBUGX=1" bash build.sh debug`) |
| `decode.py` | server or local result JSON -> per-episode statistics (plain Python, no viobench needed) |
| `../stage3/probe_decoded.json` | **the decoded statistics of the 24 hidden episodes** (the targets) |
| `../results_6b316c1f9da012f7.json` | the raw server result of the probe submission (id `6b316c1f9da012f7`) |
| `../stage3/41e08d67acd6a988.json` | our best submission ("GP + MSCKF w/ GSLV") re-scored on the 24 episodes |
| `gen/stage3_gen.py` | **flight generator** with stage-3 FoV, exposure blur, in-flight starts and the new scenes |
| `run_local.sh` | runs the probe on a folder of local flights |
| `compare.py` | prints local-flight statistics next to the server targets |
| `calib_run.sh`, `calib_check.py`, `validate.py` | the calibration/validation of the probe itself (see section 1.4) |

---

## 1. How the probe works

The server runs a submission on each hidden episode. Per episode it reports these error metrics:
- `ate_rmse`, `sim3_ate_rmse` and `sim3_scale`
- `rotation_rmse` and `rotation_max`
- `velocity_rmse` and `angular_velocity_rmse`
- `rpe_translation_rmse` and `rpe_rotation_rmse`
- `final_drift` and `distance_travelled`

It also reports these fuel statistics:
- `fuel_init`
- `fuel_per_frame_{median,p95,p99,max,mean}`
- `fuel_total`

The metric code is in `viobench/tools/runner/metrics.py` and the fuel code in `run.py`. The probe uses both groups of
numbers as channels.

### 1.1 Channel 1: outputs chosen so each error metric measures one true quantity

| probe output (every frame) | metric | what it then equals |
|---|---|---|
| position = (0, 0, 0) | `ate_rmse` | RMS distance of the drone from its start |
| | `final_drift` | distance from the start at the last frame |
| | `sim3_ate_rmse` | RMS spread of the path about its centroid (a constant estimate is only shifted by Sim(3), and `sim3_scale` stays exactly 1, which is a self-check) |
| | `rpe_translation_rmse` | RMS 1 s displacement, roughly the RMS speed. It is independent of the orientation output |
| orientation = integration of the **raw** gyro (no bias correction) | `rotation_rmse`, `rotation_max`, `rpe_rotation_rmse` | how far gyro-only attitude drifts: gyro bias and random walk |
| velocity = (0, 0, 10⁶) at frame 0, zero afterwards | `velocity_rmse` | the true **forward (camera z) speed at frame 0**. N·rmse² = 10¹² − 2·10⁶·v₀z + Σ\|v\|², so v₀z is exact to about 10⁻⁴ m/s. This separates hover starts from in-flight starts, which the IMU cannot do because steady flight feels like hovering |
| angular velocity = gyro line fit at t (camera axes) + (0, 10⁶, 0) | `angular_velocity_rmse` | the mean camera-y gyro error, i.e. the **yaw gyro bias** (camera y = −IMU z), exact to about 10⁻⁹ rad/s |

The "huge constant" trick works because the squared error is then dominated by a cross term that is *linear* in
the unknown. Metrics are JSON floats with 17 digits, so nothing is lost.

### 1.2 Channel 2: fuel carries numbers the probe computes from the hidden IMU data, images and config

Fuel is deterministic and fully under the guest's control. The probe:

1. **Does exactly the same work on every frame, whatever the data.** It has no data-dependent branches: maxima use
   selects, the log₂ is computed with bit tricks plus a polynomial, and histogram bins are indexed by comparisons. So
   an ordinary frame always costs **4,496,894 fuel**. This was measured to be identical on all 9,600 frames of 8
   local episodes.
2. **Then runs a burn loop costing exactly 11 fuel per iteration** (`volatile` countdown).
3. **Chooses the iteration count per frame** so that each order statistic the server reports lands on a group of
   frames that all burn the same amount:

| frames | group | burn iterations | lands in (sorted rank) | reported as | payload = statistics of frames … |
|---|---|---|---|---|---|
| 0–589 | G0 | 0 | 0–589 | – | – |
| 590–1129 | G1 | 2¹⁶ + 4·X1 | 590–1129 | **median** (ranks 599/600) | X1 (frames 0–589): start-of-flight gyro RMS and accel deviation (first 1 s), gyro white-noise σ, dark-frame count |
| 1130–1184 | G2 | 2²³ + 4·X2 | 1130–1184 | **p95** (rank 1139.05) | X2 (0–1129): mean luminance, green and blue chromaticity, gradient energy |
| 1185–1198 | G3 | 2²⁶ + 4·X3 | 1185–1198 | **p99** (rank 1187.01) | X3 (0–1129): vertical blur ratio in 3 pitch-speed bins, accel white-noise σ |
| 1198 | (top of G3) | + 4·X0 | 1198 (unused by p99) | **total** | X0 (0–1129): gyro RMS, yaw-rate RMS, horizontal specific-force RMS, top and bottom luminance |
| 1199 | G4 | 2²⁹ + 4·X4 | 1199 | **max** | X4 (0–1129): check nibble 0xA, horizontal blur ratio in 3 yaw-speed bins, jerk RMS |
| init | – | 2¹² + 1024·XI | – | **fuel_init** | XI: fx in 0.01 px (gives the FoV), T_cam_imu-is-default flag, centred-square-pixels flag |

Each Xn is a packed integer of quantized fields: linear or log₂ scale, 4–8 bits each. `decode.py` has the exact bit
layout and ranges. Every channel carries its own check:
- the 2 guard bits (×4) must be zero;
- the max payload must start with 0xA;
- fuel minus base must be a multiple of 11;
- the total must divide exactly.

A broken assumption therefore shows up as a failed check, never as a silently wrong number. All 24 hidden episodes
passed every check.

**What the image statistics mean:**
- **Luminance Y** = (R + 2G + B)/4. **Chromaticity** g = ΣG/Σ(R+G+B) and b likewise. Forest is green; the warehouse
  is grey and blue-ish.
- **Gradient energy** = mean squared 1-pixel horizontal difference of green, a texture measure.
- **Blur ratio** = E[(I(x+1)−I(x))²] / E[(I(x+2)−I(x))²], computed on green. It is about 1 for fine texture and
  noise, and falls towards 0.25 for smooth or blurred images.
- The blur ratio is binned by the gyro-predicted rotational pixel speed (fx·|ω| at <60, 60–200 and >200 px/s;
  horizontal uses yaw, vertical uses pitch). Motion blur shows up as the ratio **falling as pixel speed rises**,
  and as an overall lower ratio than unblurred local renders.

**IMU statistics:**
- White-noise σ comes from second differences of the 200 Hz samples (var = 6σ²).
- "Start" statistics cover frames 0–19 (the first second).
- Jerk is the RMS of frame-to-frame changes in mean specific force divided by 0.05 s.

**Cost:** max 8.9·10⁹ fuel in one frame (about 6 s; the step limit is 60 s), and about 48 s per episode locally with
20 running at once.

### 1.3 How to decode

```
python eecs116_vio/fetch_results.py 6b316c1f9da012f7             # writes eecs116_vio/results_6b316c1f9da012f7.json
python eecs116_vio/probe/decode.py eecs116_vio/results_6b316c1f9da012f7.json eecs116_vio/stage3/probe_decoded.json
```
`fetch_results.py` needs the team token in `~/.viobench_token(.txt)`. The decoded JSON is already committed, so you
don't need to fetch anything.

### 1.4 How it was validated (before uploading)

`calib_run.sh` runs the release build and a debug build (`DEFS="DEBUGX=1"`, which prints the payloads) on 8
full-length local episodes from the 240-flight holdout. `calib_check.py` and `validate.py` then check:
- **Base fuel:** identical on every frame. The two payload-computing frames are constant too (+314 at frame 589,
  +819 at frame 1129), and init varies by ±300 with number parsing, against a quantum of 11,264.
- **Payloads:** they decode bit-exactly against the debug printout.
- **Focal length:** fx is within 0.01 px.
- **Start speed:** within 1.1·10⁻⁴ m/s of the truth.
- **Gyro σ:** within 1.5 % of a direct computation.
- **Path statistics:** identical to the ground truth.
- **Yaw-bias channel:** matches the saved outputs to their print precision.

If you change `probe.c`, re-run the calibration: the constants at the top of `decode.py` must match the new build.

---

## 2. What the 24 hidden episodes look like (decoded 2026-11-25)

The quantized fields are good to about ±5–10 %. The path and speed values are exact.

### 2.1 Summary by scene type

The episodes come **in order: 1–12 rooms, 13–18 warehouse, 19–24 forest**. The colour and texture make this
unambiguous. The last column is our current local test set (8 holdout flights, `ho240`) for comparison. The values
are min / median / max, as printed by `python compare.py` (the full table is in 3.4).

| statistic | rooms (12) | warehouse (6) | forest (6) | local holdout (8) |
|---|---|---|---|---|
| horizontal FoV ° | 80.5 / 100.0 / 121.3 | 80.5 / 107.6 / 122.2 | 80.5 / 101.5 / 134.3 | 111 / 119 / 129 |
| path length m | 26.6 / 64.1 / 76.8 | 59.2 / 81.5 / 97.5 | 56.3 / 74.1 / 77.7 | 48 / 58 / 71 |
| mean speed m/s | 0.44 / 1.07 / 1.28 | 0.99 / 1.36 / 1.63 | 0.94 / 1.24 / 1.30 | 0.81 / 0.97 / 1.19 |
| RMS distance from start m | 3.1 / 4.8 / 6.8 | **8.6 / 11.1 / 15.6** | 5.5 / 7.6 / 12.8 | 2.6 / 4.0 / 4.5 |
| RMS spread about centroid m | 1.8 / 3.0 / 3.6 | 4.9 / 8.2 / 11.3 | 3.8 / 6.8 / 8.8 | 2.0 / 2.9 / 3.5 |
| start forward speed m/s | −1.0 / 0.0 / +2.75 | −0.4 / 0.0 / 0.0 | −1.7 / +0.5 / +1.4 | 0.0 / 0.35 / 1.0 |
| gyro RMS rad/s | 0.14 / 1.22 / 1.52 | 0.34 / 0.59 / 0.98 | 0.26 / 0.44 / 1.07 | 0.58 / 0.63 / 0.75 |
| yaw-rate RMS rad/s | 0.04 / 0.30 / 0.45 | 0.25 / 0.28 / 0.30 | 0.17 / 0.26 / 0.34 | 0.45 / 0.50 / 0.55 |
| **roll+pitch RMS rad/s** | **0.14 / 1.15 / 1.49** | 0.20 / 0.51 / 0.93 | 0.20 / 0.35 / 1.01 | 0.29 / 0.40 / 0.51 |
| jerk RMS m/s³ | 2.6 / 5.3 / 6.3 | 2.6 / 3.6 / 5.0 | 2.9 / 3.1 / 4.5 | 2.6 / 2.9 / 2.9 |
| horizontal specific force RMS m/s² | 0.13 / 0.19 / 0.28 | 0.13 / 0.19 / 0.26 | 0.13 / 0.21 / 0.23 | 0.16 / 0.23 / 0.28 |
| gyro noise σ rad/s | 0.070 (all) | 0.070 | 0.070 | 0.070 |
| accel noise σ m/s² | 0.28 (all) | 0.27–0.28 | 0.28 | 0.28 |
| mean luminance (0–255) | 73 / 87 / 101 | 125 / 130 / 130 | 105 / 113 / 121 | 101 / 117 / 162 |
| chromaticity green | 0.31–0.32 | 0.33 | **0.36–0.37** | 0.32–0.33 |
| chromaticity blue | 0.25–0.33 | 0.31–0.33 | 0.29–0.30 | 0.29–0.33 |
| gradient energy | 36 / 84 / 225 | 77 / 101 / 113 | **305 / 433 / 763** | 97 / 235 / 355 |
| blur ratio x, <60 px/s | 0.36 / 0.40 / 0.43 | 0.39 / 0.43 / 0.46 | 0.45 / 0.45 / 0.52 | 0.45 / 0.48 / 0.58 |
| blur ratio x, 60–200 px/s | 0.30 / 0.33 / 0.43 | 0.30 / 0.35 / 0.43 | 0.32 / 0.35 / 0.52 | 0.45 / 0.50 / 0.56 |
| gyro-only attitude drift ° RMS | 16 / 36 / 41 | 11 / 33 / 38 | 25 / 33 / 47 | 9 / 21 / 38 |

### 2.2 Findings, one by one

1. **Camera.** All 24 episodes have the default T_cam_imu and square pixels centred in the image.
   - FoV spans 80.5–134.3°.
   - The **first four FoVs of every group are identical**: 100.02, 82.69, 80.54 and 115.18°. So the staff reused the
     same random seeds per group, and exposures probably repeat in the same pattern.
   - FoVs used: 80.5, 82.7, 90.4, 100.0, 103.0, 109.3, 112.6, 115.2, 118.4, 121.3, 122.2 and 134.3°.
2. **Starts.**
   - **About 4–5 of the 24 are hover starts**: start speed exactly 0 and a quiet gyro. These are episodes 1, 13, 14
     and 18. Episode 15 also has zero forward speed but a rotating gyro (0.74 rad/s).
   - All others **start in flight**, with forward speed from **−1.73 to +2.75 m/s**.
   - **Negative values are common** (10 episodes, 8 of them below −0.15 m/s): at frame 0 the drone moves backwards or sideways relative to
     where the camera points. Our local in-flight starts (cropped flights) always move forwards. Only the camera-z
     component is measured, so the full start speed is at least |v₀z|.
   - In 2 episodes (2 and 12) the start gyro RMS saturates the encoding at 2 rad/s: they start mid-manoeuvre.
3. **The way the drone rotates is the biggest difference from our local flights.** On the server most of the
   rotation is **roll and pitch, not yaw**:
   - in rooms the median roll+pitch RMS is 1.15 rad/s against a yaw RMS of 0.30;
   - our local holdout flights (already the aggressive K/K2 autopilot styles: max acceleration 6–8 m/s², max jerk
     30–40) have roll+pitch 0.40 and yaw 0.50;
   - jerk is also about 2× higher on the server (rooms 5.3 vs 2.9).

   This matches what we saw in stage 2 (the server "rotates more for its actual speed"). It is the most likely reason
   our gyro-to-speed models did not transfer. The mean speeds are similar (1.1–1.4 vs 1.0 m/s), so the fix is **more
   aggressive tilting at the same speed**, not faster flight.
4. **Warehouse and forest flights cover more ground:** RMS distance from start is 8–16 m and 5–13 m, against 3–7 m in
   rooms. That fits a 36 × 24 m hall and a 50 m forest core, against small rooms. These scenes are less textured
   (warehouse) or extremely textured (forest).
5. **Motion blur is visible.** On the server the blur ratio is lower than on local unblurred renders (rooms
   0.36–0.43 vs 0.45–0.58 even at slow rotation), and it drops further at higher pixel speed. No episode was measured
   in the >200 px/s horizontal bin, because none has enough frames that fast.

   To turn the ratios into exposure times per episode, render one scene several times at known exposures with
   `gen/stage3_gen.py --kmin K --kmax K`, run `run_local.sh` and `compare.py`, and read off the ratio-to-exposure
   curve.
6. **IMU is unchanged from stage 2.** Gyro σ is 0.070 rad/s per sample and accel σ 0.28 m/s² per sample, identical to
   local flights. The yaw gyro bias is within ±0.024 rad/s, consistent with local `gyro_bias_init_max` 0.02 plus a
   0.0006 random walk.
7. **Lighting.**
   - Rooms are darker than our local rooms (mean luminance 87 vs 117).
   - The warehouse is uniformly bright (125–130) with a brighter floor than ceiling.
   - Forest has bright tops (sky, 119–153).
   - **Episode 3 (`92c12d5a`) has 3–20 black frames** in its first half (a blackout). All others have none.
8. **Where our best submission fails** (ATE in the last column of 3.1):
   - episode 20 (`616b85ed`, forest, start speed −1.73 m/s): 6.20 m;
   - episode 8 (`3cc7fd3d`, room, start +2.75 m/s, the fastest start): 3.04 m;
   - episode 21 (`4fb55ea9`, the most textured forest): 2.38 m;
   - episode 16 (`c31ed491`, warehouse): 2.19 m;
   - episode 18 (`6fd93fa3`, warehouse): 2.00 m.

   Fast or backward in-flight starts and large outdoor or hall scenes are the cases to cover first.

---

## 3. How to make stage-3-like test flights

The target is a local set whose `compare.py` ranges cover the server's ranges in 2.1, ideally per scene type.
Recommended mix: **12 room flights, 6 warehouse, 6 forest**, about 20 % hover starts, FoV U(75, 135), exposure
U(5, 50) ms. Make several such sets (e.g. 4 × 24 = 96 flights) so the results are not noise.

### 3.1 One-time setup (GPU computer, Linux)

Rendering needs a GPU: the CPU renderer manages about 12 simulation steps/s, so one 60 s flight takes about 17
minutes.

```bash
git clone <this repo> && cd eecs116_projects
bash gpu_kit/setup.sh ~/viobench          # viobench + our autopilot patch (VIOBENCH_TASK_EXTRA hook); prints "OK: GPU renderer in use"
. ~/viobench/.venv/bin/activate
pip install -U "hyperlux>=0.1.11" "hyperdrone>=0.1.11"   # 0.1.11 adds the Warehouse and Forest scenes
```

The patch adds one line to `hyperdrone_world.h.in` and `simulation.py`, so that the autopilot constants can be set
through the `VIOBENCH_TASK_EXTRA` environment variable. See `gpu_kit/README.txt` for the rest of that kit.

### 3.2 Generate flights

`gen/stage3_gen.py` wraps `viobench.tools.datasets.generate.simulation.simulate`:

| stage-3 property | how the script reproduces it |
|---|---|
| FoV U(75, 135)° per episode | `SimConfig(fov=105, fov_range=30)` (defaults `--fov 105 --fov-range 30`) |
| exposure 0–50 ms per episode | a custom camera averages the last k renders (one per 5 ms IMU step, k ~ U{1..10}) in linear light. This is how viobench itself integrates exposure ("exposure is integrated over rendered sub-frames in Python", `hyperdrone_world.h.in`); `episode.config["episode"]["exposure_seconds"] = k·0.005` |
| hover vs in-flight start | with probability `--hover-frac` (0.2): a 1 s hover, then 60 s. Otherwise: fly 60 + C s from a 0.2 s hover and drop the first C s, C ~ U(5, 25) (`--crop-min/--crop-max`) |
| rooms / warehouse / forest | `--scenes` takes ProcTHOR names (`ProcTHOR-Train-N`), HSSD ids (e.g. `108736611_177263226`), `Warehouse` and `Forest` (conta references `77d055df…` and `edc48445…` from hyperlux 0.1.11's `hyperdrone-originals` catalog) |
| trajectory style | the `VIOBENCH_TASK_EXTRA` environment variable: C++ autopilot constants, see 3.3 |

Example: one stage-3-like set of 24 flights.

```bash
cd eecs116_vio/probe/gen
STYLE='static constexpr T CRUISE_SPEED_MIN = 3.0; static constexpr T CRUISE_SPEED_MAX = 4.5; static constexpr T MAX_ACCELERATION = 6.0; static constexpr T MAX_JERK = 30.0; static constexpr T MAX_YAW_RATE = 2.0; static constexpr T ROADMAP_SPACING = 1.0; static constexpr T CONNECTION_DISTANCE = 6.0;'
export VIOBENCH_TASK_EXTRA="$STYLE"
python stage3_gen.py ~/s3/set1 --seed 1 --episodes 1 --scenes ProcTHOR-Train-2 ProcTHOR-Train-17 ProcTHOR-Train-48 ProcTHOR-Train-74 ProcTHOR-Train-98 ProcTHOR-Train-121 108736611_177263226 105515175_173104107 108736722_177263382 106879044_174887172 103997478_171030528 102816786
python stage3_gen.py ~/s3/set1 --seed 1 --episodes 6 --scenes Warehouse Forest
```

- Already-written flights are skipped, so re-running resumes.
- Each episode prints its exposure, FoV and start type, and they are also stored in the episode meta (`stage3_gen`).
- A flight is 100–600 MB: do not put flights in git. Copy them with scp or a USB drive.

The script was smoke-tested on the laptop's CPU renderer with ProcTHOR (hover and in-flight paths, exposure 10–30
ms). The Warehouse and Forest scenes and the GPU path have **not** been run yet. If `Warehouse` fails to load, check
that `python -c "import hyperlux; print(hyperlux.__version__)"` prints 0.1.11 or newer.

### 3.3 Matching the motion (the open problem)

The style above (called K) is what produced our 240-flight holdout. It matches the server's speed and path length in
rooms, but **not its roll/pitch rate (0.4 vs 1.15 rad/s) or jerk (2.9 vs 5.3)**. The autopilot is a neural policy
(RAPTOR) that follows a planned path. The constants it exposes, with the defaults from
`hyperlux/_vendor/rl-tools/include/rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization/visual_inertial_localization.h`:

| constant | default | effect |
|---|---|---|
| `CRUISE_SPEED_MIN` / `CRUISE_SPEED_MAX` | 0.45 / 0.8 | one top speed per flight, drawn uniformly in this range |
| `MAX_ACCELERATION`, `MAX_JERK` | 0.7, 2.0 | how hard the planned path can change speed or direction (tilt and tilt rate) |
| `MAX_YAW_RATE` | 0.8 | how fast it turns to face a new direction (server yaw RMS is only about 0.3, so this need not be high) |
| `PHASE_ACCELERATION`, `PHASE_JERK` | 0.2, 0.5 | how fast the pace along the path may change |
| `ROADMAP_SPACING`, `CONNECTION_DISTANCE` | 0.65, 4.0 | waypoint spacing (longer straight runs, more time at speed) |
| `TARGET_POSITION_ERROR_CLIP` | 1.0 | clamp on the position error the policy sees. Larger means more aggressive corrections, probably more tilting |
| `TRACKING_MARGIN` | 0.25 | safety margin of the path around obstacles |

`gpu_kit/styles.txt` has more presets (wide_gentle, wide_agile, wide_long, agile2, jerky) with notes on how the
planner uses each constant.

**Suggested sweep:** 20 s flights in 2–3 rooms are enough to estimate the rates. Try the following, one at a time
and then combined:
- `MAX_JERK` 60–120;
- `MAX_ACCELERATION` 10–15;
- `PHASE_JERK` 3–10;
- `TARGET_POSITION_ERROR_CLIP` 2–3;
- a lower `MAX_YAW_RATE` of about 1.0.

For each variant run `run_local.sh` and `compare.py`, and look at the `roll+pitch rms`, `yaw rms`, `jerk rms` and
`mean speed` rows. The goal is about 1.0–1.2 rad/s roll+pitch, about 0.3 yaw and jerk about 5 in rooms, at a mean
speed of about 1.1 m/s.

If no constant gets there, the server probably uses a different drone model or disturbances (for example wind)
rather than a different planner. Then try `hyperdrone_world.h.in` (the dynamics preset and randomization) next.

### 3.4 Check a generated set against the server

```bash
. ~/viobench/.venv/bin/activate
bash eecs116_vio/probe/run_local.sh ~/s3/set1 8      # probe on every flight (8 at once); about 15-45 s per flight
python eecs116_vio/probe/compare.py ~/s3/set1        # server rooms / warehouse / forest vs your set
```

`compare.py` with no argument prints just the server targets. With several folders it shows each as a column, which
makes comparing styles easy. Only 60 s flights (1,200 frames) decode, because the probe's frame groups assume 1,200.
This is the current output for the server against our 8 holdout flights (`ho_ref`):

```
(min median max)                         rooms               warehouse                  forest                  ho_ref
hfov deg                 80.54  100.02  121.31   80.54  107.60  122.17   80.54  101.51  134.25  111.02  118.51  129.34
path length m            26.60   64.08   76.79   59.17   81.48   97.46   56.34   74.12   77.72   48.33   57.98   71.16
mean speed m/s            0.44    1.07    1.28    0.99    1.36    1.63    0.94    1.24    1.30    0.81    0.97    1.19
rms 1 s move m            0.51    1.07    1.33    1.07    1.42    1.68    1.10    1.29    1.43    0.93    1.14    1.30
rms dist from start m     3.13    4.80    6.83    8.63   11.07   15.64    5.48    7.63   12.79    2.60    4.02    4.49
rms spread m              1.78    3.02    3.59    4.94    8.24   11.28    3.79    6.84    8.78    2.03    2.88    3.48
start fwd speed m/s      -1.01   -0.01    2.75   -0.41    0.00    0.00   -1.73    0.48    1.42    0.00    0.35    1.02
|start fwd speed| m/s     0.00    0.63    2.75    0.00    0.00    0.41    0.03    0.94    1.73    0.00    0.35    1.02
start 1 s gyro rms        0.09    1.09    2.00    0.13    0.26    0.83    0.18    0.42    0.83    0.08    0.24    0.74
gyro rms rad/s            0.14    1.22    1.52    0.34    0.59    0.98    0.26    0.44    1.07    0.58    0.63    0.75
yaw rms rad/s             0.04    0.30    0.45    0.25    0.28    0.30    0.17    0.26    0.34    0.45    0.50    0.55
roll+pitch rms rad/s      0.14    1.15    1.49    0.20    0.51    0.93    0.20    0.35    1.01    0.29    0.40    0.51
jerk rms m/s3             2.60    5.33    6.28    2.60    3.64    5.04    2.91    3.08    4.51    2.60    2.91    2.91
accel xy rms m/s2         0.13    0.19    0.28    0.13    0.19    0.26    0.13    0.21    0.23    0.16    0.23    0.28
gyro sigma                0.07    0.07    0.07    0.07    0.07    0.07    0.07    0.07    0.07    0.07    0.07    0.07
accel sigma               0.28    0.28    0.28    0.27    0.28    0.28    0.28    0.28    0.28    0.28    0.28    0.28
Y mean                   72.86   87.02  101.19  125.48  129.52  129.52  105.24  113.33  121.43  101.19  117.38  161.90
chroma g                  0.31    0.32    0.32    0.33    0.33    0.33    0.36    0.36    0.37    0.32    0.33    0.33
chroma b                  0.25    0.30    0.33    0.31    0.32    0.33    0.29    0.29    0.30    0.29    0.30    0.33
gradient energy          35.89   84.14  224.57   77.05  100.75  112.90  304.85  432.78  762.61   96.90  234.85  355.19
blur x <60 px/s           0.36    0.40    0.43    0.39    0.43    0.46    0.45    0.45    0.52    0.45    0.48    0.58
blur x 60-200 px/s        0.30    0.33    0.43    0.30    0.35    0.43    0.32    0.35    0.52    0.45    0.50    0.56
gyro drift deg rms       16.35   35.61   41.32   10.94   33.32   37.59   25.21   33.15   46.73    9.42   20.75   38.32
```

### 3.5 Checklist for a finished stage-3 set

- [ ] 24 flights per set: 12 rooms (a mix of ProcTHOR and HSSD), 6 Warehouse, 6 Forest.
- [ ] About 20 % hover starts; in-flight starts include some moving backwards or sideways at frame 0, and some at
      2–3 m/s. Cropping at random times should give this; check the `start fwd speed` row.
- [ ] FoV covers 75–135° and exposure covers 5–50 ms (both printed per flight and stored in the episode config).
- [ ] `compare.py`: mean speed, path length and RMS distance from start fall inside the server ranges per scene type.
- [ ] roll+pitch RMS, yaw RMS and jerk are close to the server's (section 3.3). Mention it if they are not: this is
      the part we have not matched yet.
- [ ] At least one flight with a short blackout (the server has one episode with 3–20 black frames).

---

## 4. Per-episode tables (all 24 hidden episodes)

`best-sub ATE` = our best submission ("GP + MSCKF w/ GSLV", 4.4 M fuel) on that episode. The yaw gyro bias is in
IMU axes (z up). The blur ratios are binned by rotational pixel speed; "-" means no frames fell in that bin.

| # | episode | scene | hFoV deg | path m | mean speed m/s | start fwd speed m/s | start 1 s gyro rad/s | RMS dist from start m | spread m | best-sub ATE m |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `30755ac2` | room | 100.0 | 26.6 | 0.44 | +0.00 | 0.09 | 3.82 | 1.80 | 0.19 |
| 2 | `500bc1fd` | room | 82.7 | 69.0 | 1.15 | -0.20 | 2.00 | 3.13 | 2.99 | 0.28 |
| 3 | `92c12d5a` | room | 80.5 | 41.1 | 0.68 | +0.06 | 0.60 | 4.96 | 2.78 | 0.29 |
| 4 | `9d8c612e` | room | 115.2 | 65.4 | 1.09 | -0.78 | 1.60 | 4.38 | 2.82 | 0.52 |
| 5 | `d6337f10` | room | 112.5 | 54.2 | 0.90 | +0.77 | 1.29 | 5.31 | 3.26 | 0.46 |
| 6 | `9affc13d` | room | 90.4 | 49.0 | 0.82 | -0.48 | 0.74 | 3.94 | 3.06 | 0.43 |
| 7 | `bffcea9d` | room | 100.0 | 75.6 | 1.26 | -0.23 | 0.93 | 5.73 | 3.52 | 0.58 |
| 8 | `3cc7fd3d` | room | 82.7 | 76.8 | 1.28 | +2.75 | 1.60 | 5.46 | 3.59 | 3.04 |
| 9 | `f794e777` | room | 80.5 | 67.7 | 1.13 | +1.39 | 1.15 | 6.83 | 2.75 | 0.31 |
| 10 | `7519dd96` | room | 115.2 | 50.6 | 0.84 | -1.01 | 0.74 | 6.26 | 3.17 | 1.11 |
| 11 | `e5cc48d7` | room | 109.3 | 62.8 | 1.05 | +0.89 | 1.03 | 4.64 | 1.78 | 0.19 |
| 12 | `293ef2a9` | room | 121.3 | 70.2 | 1.17 | -0.02 | 2.00 | 3.65 | 3.58 | 0.80 |
| 13 | `5672eb24` | warehouse | 100.0 | 77.9 | 1.30 | +0.00 | 0.13 | 8.63 | 8.03 | 0.52 |
| 14 | `f1412208` | warehouse | 82.7 | 59.2 | 0.99 | +0.00 | 0.14 | 9.67 | 4.94 | 0.59 |
| 15 | `72bef50e` | warehouse | 80.5 | 97.5 | 1.63 | +0.00 | 0.74 | 10.65 | 9.01 | 0.66 |
| 16 | `c31ed491` | warehouse | 115.2 | 94.0 | 1.57 | -0.41 | 0.83 | 14.33 | 8.45 | 2.19 |
| 17 | `34c68d36` | warehouse | 118.4 | 74.4 | 1.24 | -0.10 | 0.38 | 11.50 | 7.82 | 0.80 |
| 18 | `6fd93fa3` | warehouse | 122.2 | 85.0 | 1.42 | +0.00 | 0.13 | 15.64 | 11.28 | 2.00 |
| 19 | `dc4e9bfa` | forest | 100.0 | 70.2 | 1.17 | +0.03 | 0.53 | 6.79 | 4.75 | 1.01 |
| 20 | `616b85ed` | forest | 82.7 | 77.4 | 1.29 | -1.73 | 0.83 | 12.41 | 7.32 | 6.20 |
| 21 | `4fb55ea9` | forest | 80.5 | 77.7 | 1.30 | +0.94 | 0.20 | 7.43 | 6.36 | 2.38 |
| 22 | `9f250c4f` | forest | 115.2 | 56.3 | 0.94 | +0.94 | 0.53 | 5.48 | 3.79 | 0.97 |
| 23 | `1411ebe1` | forest | 134.2 | 77.7 | 1.30 | +1.42 | 0.18 | 12.79 | 8.78 | 1.63 |
| 24 | `ea5ede02` | forest | 103.0 | 70.9 | 1.18 | -0.66 | 0.31 | 7.83 | 7.51 | 1.13 |

| # | episode | gyro RMS | yaw RMS | roll+pitch RMS | jerk RMS | Y mean | Y top / bottom | chroma g / b | gradient energy | blur x (<60, 60-200, >200 px/s) | blur y | dark (first half) | yaw gyro bias rad/s | gyro drift deg RMS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `30755ac2` | 0.14 | 0.04 | 0.14 | 2.6 | 101 | 85 / 68 | 0.325 / 0.283 | 225 | 0.43, -, - | 0.45, -, - | 0 | +0.0176 | 41 |
| 2 | `500bc1fd` | 1.52 | 0.34 | 1.48 | 6.3 | 93 | 102 / 85 | 0.325 / 0.283 | 97 | 0.37, 0.33, - | 0.39, 0.35, 0.32 | 0 | +0.0198 | 38 |
| 3 | `92c12d5a` | 0.63 | 0.21 | 0.60 | 3.2 | 73 | 85 / 68 | 0.314 / 0.252 | 193 | 0.43, 0.43, - | 0.48, 0.42, 0.36 | 3-20 | +0.0198 | 40 |
| 4 | `9d8c612e` | 1.17 | 0.34 | 1.12 | 5.0 | 81 | 85 / 68 | 0.325 / 0.273 | 153 | 0.42, 0.33, - | 0.43, 0.39, 0.33 | 0 | +0.0239 | 41 |
| 5 | `d6337f10` | 1.27 | 0.45 | 1.19 | 5.6 | 81 | 85 / 68 | 0.325 / 0.263 | 165 | 0.43, 0.39, - | 0.46, 0.42, 0.36 | 0 | -0.0194 | 38 |
| 6 | `9affc13d` | 0.90 | 0.25 | 0.86 | 4.0 | 81 | 85 / 68 | 0.314 / 0.252 | 153 | 0.40, 0.33, - | 0.43, 0.35, 0.32 | 0 | -0.0080 | 21 |
| 7 | `bffcea9d` | 1.39 | 0.37 | 1.34 | 5.6 | 89 | 85 / 85 | 0.325 / 0.325 | 66 | 0.40, 0.30, - | 0.39, 0.33, 0.30 | 0 | +0.0169 | 32 |
| 8 | `3cc7fd3d` | 1.27 | 0.34 | 1.23 | 5.6 | 93 | 85 / 85 | 0.325 / 0.325 | 57 | 0.39, 0.32, - | 0.37, 0.33, 0.32 | 0 | +0.0179 | 41 |
| 9 | `f794e777` | 0.98 | 0.30 | 0.93 | 4.0 | 89 | 85 / 68 | 0.325 / 0.335 | 66 | 0.37, 0.35, - | 0.37, 0.33, 0.29 | 0 | +0.0024 | 31 |
| 10 | `7519dd96` | 0.53 | 0.12 | 0.51 | 2.9 | 81 | 85 / 85 | 0.325 / 0.325 | 71 | 0.39, -, - | 0.39, 0.32, - | 0 | +0.0165 | 32 |
| 11 | `e5cc48d7` | 1.52 | 0.30 | 1.49 | 6.3 | 89 | 85 / 102 | 0.325 / 0.325 | 36 | 0.36, 0.33, - | 0.39, 0.33, 0.32 | 0 | -0.0024 | 33 |
| 12 | `293ef2a9` | 1.39 | 0.28 | 1.36 | 5.6 | 85 | 85 / 102 | 0.325 / 0.314 | 49 | 0.37, 0.30, - | 0.37, 0.33, 0.32 | 0 | +0.0077 | 16 |
| 13 | `5672eb24` | 0.37 | 0.25 | 0.27 | 2.9 | 130 | 119 / 136 | 0.335 / 0.325 | 105 | 0.43, 0.32, - | 0.42, 0.33, - | 0 | +0.0135 | 30 |
| 14 | `f1412208` | 0.34 | 0.28 | 0.20 | 2.6 | 130 | 119 / 136 | 0.335 / 0.314 | 90 | 0.39, 0.30, - | 0.42, 0.33, - | 0 | +0.0160 | 36 |
| 15 | `72bef50e` | 0.98 | 0.30 | 0.93 | 5.0 | 125 | 119 / 136 | 0.335 / 0.335 | 113 | 0.46, 0.43, - | 0.43, 0.42, 0.37 | 0 | +0.0153 | 36 |
| 16 | `c31ed491` | 0.75 | 0.28 | 0.70 | 4.0 | 130 | 119 / 153 | 0.335 / 0.325 | 105 | 0.43, 0.36, - | 0.42, 0.35, 0.29 | 0 | +0.0189 | 38 |
| 17 | `34c68d36` | 0.48 | 0.30 | 0.38 | 3.2 | 125 | 119 / 136 | 0.335 / 0.325 | 97 | 0.43, 0.35, - | 0.43, 0.39, - | 0 | -0.0064 | 20 |
| 18 | `6fd93fa3` | 0.69 | 0.25 | 0.64 | 4.0 | 130 | 119 / 153 | 0.335 / 0.325 | 77 | 0.42, -, - | 0.40, 0.35, - | 0 | -0.0016 | 11 |
| 19 | `dc4e9bfa` | 0.48 | 0.30 | 0.38 | 2.9 | 109 | 119 / 119 | 0.355 / 0.294 | 355 | 0.46, 0.35, - | 0.50, 0.40, - | 0 | +0.0182 | 40 |
| 20 | `616b85ed` | 1.07 | 0.34 | 1.01 | 4.5 | 109 | 119 / 119 | 0.366 / 0.294 | 305 | 0.45, 0.36, - | 0.50, 0.40, 0.35 | 0 | +0.0109 | 28 |
| 21 | `4fb55ea9` | 0.53 | 0.28 | 0.45 | 3.6 | 105 | 102 / 119 | 0.366 / 0.294 | 763 | 0.52, 0.52, - | 0.59, 0.61, 0.61 | 0 | +0.0147 | 31 |
| 22 | `9f250c4f` | 0.37 | 0.17 | 0.33 | 2.9 | 121 | 153 / 119 | 0.355 / 0.304 | 655 | 0.52, -, - | 0.58, 0.49, - | 0 | +0.0210 | 47 |
| 23 | `1411ebe1` | 0.41 | 0.25 | 0.32 | 3.2 | 121 | 136 / 136 | 0.355 / 0.294 | 383 | 0.45, -, - | 0.52, 0.37, - | 0 | -0.0117 | 25 |
| 24 | `ea5ede02` | 0.26 | 0.17 | 0.20 | 2.9 | 117 | 136 / 136 | 0.366 / 0.294 | 482 | 0.45, 0.32, - | 0.52, 0.36, - | 0 | +0.0149 | 35 |

