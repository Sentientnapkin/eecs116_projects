Create a clean, presentation-ready **flowchart of a drone visual-inertial odometry (VIO) estimator**, for the final slide of a class project. Use a left-to-right main pipeline with a few side modules feeding in. Use rounded boxes for processing steps, parallelograms for inputs and outputs, diamonds for decisions, and dashed boxes for "runs only sometimes" modules. Colour-code by group (listed below). Keep the labels short, and put the one-line descriptions in smaller text under each box title. White background, flat style, no 3-D effects, readable at slide size.

**Title:** "GP + MSCKF with lines and learned velocity (GSLV): final submission"
**Subtitle:** "Server: 0.633 m mean error at 4.2 M fuel per frame. Area 5.8% (best of our 16 submissions)"

---

### Group A — Inputs (grey parallelograms, far left)
1. **Camera frame**: 320×240 RGB at 20 Hz
2. **IMU samples**: gyroscope + accelerometer, 10 samples per frame (200 Hz)

### Group B — Input safety (grey box, directly after the inputs)
3. **IMU sanitiser**: drops NaN, time-reversed, impossible or spiky samples

### Group C — Motion prediction (blue)
4. **IMU propagation**: integrate rotation and acceleration to predict pose and velocity
5. **Gaussian-process bias model**: smooth gyro and accelerometer bias estimates; clamp gyro bias to ±0.021 rad/s
6. **Clone window**: keep the last ~10 camera poses as filter states

Arrows: 3 → 4; 5 → 4; 4 → 6.

### Group D — Vision front end (green), from the camera frame
7. **Gray image + pyramid** (integer SIMD)
8. **Corner tracking (KLT)**: integer SIMD Lucas–Kanade, starting from the IMU-predicted position plus each track's own last motion
9. **Forward-backward check**: drop tracks that don't return within 0.5 px
10. **Corner detection**: refill empty grid cells
11. **3-D wall-line tracking**: track long straight edges
12. **Manhattan constraints** (diamond-like decision label: "line vertical or horizontal?"):
    - vertical lines → forced exactly vertical → **tilt information**
    - horizontal lines → snapped to the room's two axes → **heading information**

Arrows: camera → 7 → 8 → 9 → (13); 10 → 8; 7 → 11 → 12 → (13).

### Group E — MSCKF update (dark blue, centre of the chart, the biggest box)
13. **MSCKF measurement update**: triangulate each feature/line from the clone window, project out the feature, Kalman update of pose, velocity and biases
   - inside it, small sub-boxes:
     - "**Soft weighting**: features with reprojection error > 1 px count as 1/error (none rejected)"
     - "**Exact analytic line Jacobians**"
     - "**Iterated update**: re-linearise once if the state moved a lot"
14. **Revisit map**: re-match stored 3-D points (ZNCC patches) when an area is seen again. Dashed box, feeds into 13.

Arrows: 6 → 13; 9 → 13; 12 → 13; 14 → 13 (dashed).

### Group F — Learned velocity (orange, dashed boxes above the main line)
15. **Startup velocity net** (small CNN, ~1.7 M multiply-adds, plain C): at frames 5–8, frame pair + IMU → 3-D velocity with uncertainty
16. **Periodic re-anchor** (diamond): "every 10 frames (0.5 s), or velocity uncertainty > 0.25 m/s?" → yes → apply the net's velocity as a measurement with 3× its uncertainty

Arrows: camera + IMU → 15 → 16 → 13 (dashed, labelled "velocity measurement").

### Group G — Compute budget (purple, a thin bar spanning under groups D–F)
17. **Per-frame fuel governor**: every optional job (filter rows, net micro-steps, map matching, 2nd iteration) has a measured cost and fits under a ~3.6 M budget per frame; leftover work is deferred to later frames.

Show dotted lines from 17 to boxes 8, 13, 14 and 15, labelled "budgeted".

### Group H — Output safety and output (grey, far right)
18. **Divergence watchdog**: NaN or absurd state → restore the last good state
19. **Output guard**: never emit an invalid pose
20. **Output (parallelogram)**: 6-DoF pose (position + orientation) every frame

Arrows: 13 → 18 → 19 → 20.

---

### Small legend box (bottom-right corner)
- Blue: filter core
- Green: vision front end
- Orange: learned component
- Purple: compute budget
- Grey: input/output safety
- Dashed: runs only sometimes

### Optional small inset (bottom-left): "How we got here"
A tiny 4-step strip with arrows. Each step shows the server mean error and the peak fuel per frame:

| Step | Server error | Peak fuel |
|---|---|---|
| Baseline GP + MSCKF | 3.22 m | 19.5 M |
| Startup net + re-anchor | 0.78 m | 17.0 M |
| Low-fuel + hardened | 0.95 m | 4.0 M |
| **+ lines, Manhattan, periodic velocity (final)** | **0.63 m** | **4.2 M** |

Keep everything on one slide (16:9). Do not invent extra modules or numbers beyond those listed.
