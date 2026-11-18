# Selective SSM robustness milestone

Use the original SSM with the corrected warp for nominal operation. Advance the expanded EMA to a larger moving-start check. The expanded SSM improved moving-start accuracy at essentially unchanged model fuel, but missed the nominal guardrail in development and did not improve the nominal accuracy–fuel frontier on fresh scenes.

## Diagnosis

On six native development scenes and three paired model seeds, the historical selective SSM was 0.098 m better than matched EMA from the original start. Resetting both estimators at five seconds under clean observations reversed that advantage. Adding the original combined corruption reproduced the historical 1.369 m versus 1.096 m result.

| Replay | Selective SSM ATE (m) | Matched EMA ATE (m) | SSM − EMA (m) |
| --- | ---: | ---: | ---: |
| Original start, clean | 0.912 | 1.010 | −0.098 |
| 2 s reset, clean | 0.983 | 0.947 | +0.036 |
| 5 s reset, clean | 1.348 | 1.096 | +0.252 |
| 5 s reset, constant gyro offset | 1.332 | 1.064 | +0.268 |
| 5 s reset, changing gyro offset | 1.375 | 1.105 | +0.270 |
| 5 s reset, image gaps | 1.346 | 1.095 | +0.251 |
| 5 s reset, IMU timestamp jitter | 1.341 | 1.096 | +0.245 |
| 5 s reset, original combined recipe | 1.369 | 1.096 | +0.273 |
| 12 s reset, clean | 1.149 | 1.078 | +0.071 |

Each crop is scored to the end of its parent, with identical duration across conditions within the crop. A new estimator starts with an empty packet, image history and calibration window. All model seeds see the same parent-seeded perturbation. The ablations separate constant and slowly varying gyro offsets, short missing-image bursts, and up to 1 ms of IMU jitter. The combined condition reproduces the historical recipe.

At the five-second reset, clean replays account for 0.252 m of the 0.273 m model gap. Clean orientation RMSE was 0.283 rad for both models and rose to 0.389 rad for both under combined stress. The models use identical calibration and attitude estimates in these replays. The SSM already had worse velocity RMSE with the clean reset, 0.223 versus 0.211 m/s, and higher three-second ATE, 0.443 versus 0.413 m. Changing gyro bias raises attitude and velocity errors in both models. Simultaneous effects can cancel in the integrated position, so a small mean ATE increase does not imply stable attitude. Short gaps and jitter explain little of the reversal at the tested severity.

A frozen-weight intervention with the parity-corrected runtime isolates the SSM's first memory value. The original recurrence initializes its state to the first projected embedding, effectively giving one observation full historical weight. Zero initial state reduced clean reset ATE at five seconds from 1.385 to 1.020 m and at twelve seconds from 1.170 to 0.881 m. It raised nominal ATE from 0.918 to 1.140 m. The result supports a reset-context failure and shows why a blanket memory change is costly. The per-frame replays retain attitude and velocity error, calibration activation and rejection counts, both bias trajectories, and recurrent norms and update magnitudes.

## Deployment parity

The historical reference and Wasm were fed the exact same 320×240 RGB arrays from the benchmark runner, with the same JSON-round-tripped intrinsics and extrinsics, frame timestamps, and f64 IMU packets. Frame hashes and IMU packet values matched. Resized images, integration intervals, calibration, and homographies matched before the first material difference at frame 5. The divergence entered at the perspective warp and mask and propagated to the CNN embedding, selective state, velocity, and camera position. Output serialization matched the in-guest trace. Two historical-path development replays reached 0.120 m and 0.114 m peak Euclidean position separation. Reapplying desktop OpenCV to frame 0 with the actual guest homography at frame 5 changed 91 warped pixels by up to four intensity units and three binary mask pixels. This isolates the disagreement to the warp implementation even when its operands are identical.

The corrected runtime applies the same explicit inverse mapping, 1/32-pixel rounding, bilinear interpolation and zero-border validity rule in both environments. The integer-coordinate OpenCV remap produced the same sampled results as the integer NumPy reference on tested flights and lowered the cost relative to the NumPy implementation. Historical records and checkpoints remain under their original preprocessor. The corrected runtime has a separate configuration and run identities.

The hard position tolerance is 0.5 mm Euclidean per frame. Sampled intermediate checks require exact delivery and pixel values, 1e−12 s for integration intervals, 1e−7 for orientation and homographies, and 2e−5 for the embedding, memory, and prediction components. A constant three-axis velocity error at the component tolerance would allow about 1.0 mm drift over 30 s by itself, so the separate end-to-end position gate matters. Across six corrected development flights, the largest Euclidean position difference was 0.42 μm. No sampled stage exceeded its tolerance and the f64 serialization error was zero.

## Training and bias audit

Velocity targets are endpoint IMU-origin velocities in body axes. Native targets subtract the angular lever-arm term from finite-difference camera twist, then rotate the result into the IMU body frame. Each predicted velocity is rotated with the estimated attitude and integrated by trapezoids over the actual sample intervals. The camera offset and first-camera coordinate frame match deployment.

In the previous velocity/displacement objective, both velocities were rotated by the same estimated attitude. Equal body velocities gave zero loss even when that attitude misintegrated both. The new objective retains supervised body velocity and compares predicted camera displacement to archived camera positions in the truth first-camera gauge. It applies the configured 0.25, 1, 3 and 6 s horizons, including the 6 s horizon declared under the joint configuration. With frozen sensor preprocessing, that loss can teach velocity compensation for attitude error, while attitude itself still comes from the IMU pipeline. A regression test proves that an attitude error which vanished under the old objective produces a nonzero loss and a velocity gradient.

Each training window starts from a raw observed prefix. The original training used cached orientations and images with truncated recurrent chunks and up to 80 frames of burn-in. A chunk boundary did not necessarily reset calibration, image history, or orientation. This run samples 140–280 frames with 45% probability of a clean original-start window. The remaining windows sample raw start times and draw clean, constant-bias, changing-bias, gap, jitter, or combined observations. The nominal-only ablation uses the same new objective and budget with original starts. Windows are constructed in memory and never become additional scenes or cached augmented archives. Across 1,020 processed expanded SSM windows, 46.5% were unmodified original-start previews, 33.9% started above 0.15 m/s, and 448 had explicit sensor perturbations.

Reliability adds four causal sensor inputs to the existing calibrated and image-available bits. They encode time since a successful calibration check, elapsed time since reset, history availability, and IMU packet density. The state intervention changes the SSM's initial value only. Disturbances later in the stream leave the recurrence running.

The historical bias head receives a direct Smooth L1 gradient against the injected increment remaining after differential calibration and a gradient through an approximate integrated small-angle correction. Both share the encoder and recurrence with the motion objectives. There is no gradient through future exact gyro integration, rolling calibration, packet features, or image derotation. At deployment the predicted residual is low-pass filtered with a 0.8 s time constant, gated by input availability, and applied to subsequent integration. It does not retroactively rotate the accumulated attitude. A fresh paired replay of the same weights with feedback on and off changed the cached derotation on 99% of five-second combined-stress frames. It improved mean ATE by 0.023 m in that comparison, while mean attitude RMSE increased by 0.0004 rad. The bias model remained worse than the no-head controls in the original matched experiment. The result does not justify a new feedback model or a claim about recovering physical sensor bias.

## Data and simulation

The training roster contains 60 flights from 36 distinct scenes, with six separate native development scenes. The existing feature cache was already 7.6 GB and the data tree about 17 GB. Free space was about 25 GiB at the start. The trainer reused the old archives and constructed new variants in memory. Simulation writes only its new episode archives and a temporary render spool.

The upstream visual–inertial task ties autopilot yaw and route progress to forward travel. The independent-yaw pilot retained the planner, dynamics, IMU and renderer, varied the yaw target separately from the route, and removed the heading multiplier on route progress. At a threshold of 0.2 m/s in measured body axes, the generated 20 s training flight had 18.8% backward and 7.0% lateral frames. The corresponding development pilot had 26.5% backward and 39.0% lateral frames. No existing training or development parent had detectable backward frames at the same threshold. Lateral motion occupied about 1.4% of the original training frames. Both completed without a crash. These two flights were kept out of the main training comparison.

Four additional scenes were generated for final confirmation. Scenes 176–178 are benchmark-style 30 s episodes. Scene 179 is a separate 55 s episode with matched clean and disrupted moving-start replays. The longer flight starts its cropped replay at 0.237 m/s. The eight earlier reserved scenes were not used for model selection or rescored as a new holdout.

## Development training results

The screen required at least 0.020 m stress improvement and allowed at most 0.050 m nominal ATE increase over matching corrected baseline seeds. Stress is the equal-weight average of clean and combined ATE over the 2, 5 and 12 s reset points. Checkpoints were selected per seed, prioritizing stress under the nominal limit. If no candidate passed the screen, the smallest nominal regression advanced as a diagnostic finalist.

| Two-seed screen | Nominal ATE (m) | Clean moving ATE (m) | Combined moving ATE (m) | Stress ATE (m) | Nominal change vs. warm start (m) |
| --- | ---: | ---: | ---: | ---: | ---: |
| SSM, nominal-only retraining | 0.973 | 1.203 | 1.281 | 1.242 | +0.035 |
| SSM, expanded training | 0.992 | 1.038 | 1.131 | 1.085 | +0.054 |
| SSM, expanded + reliability | 0.993 | 1.038 | 1.130 | 1.084 | +0.055 |
| SSM, expanded + reliability + zero initial memory | 1.020 | 1.040 | 1.121 | 1.081 | +0.082 |
| EMA, expanded training | 1.002 | 1.019 | 1.087 | 1.053 | 0.000 |

Expanded training accounted for nearly all of the measured robustness gain. It cut stress ATE by 0.157 m relative to the nominal-only retraining control at a 0.019 m increase in nominal ATE. Reliability changed stress by less than 1 mm at this sample size. Zero-initial memory reduced the combined moving error by a further 9 mm versus reliability alone, but added about 27 mm nominal error. The two-seed stress gains for all three expanded SSMs cleared the stress threshold and missed the nominal threshold. The data-only expansion missed it by 4 mm and advanced under the fallback rule.

Adding the third seed changed the expanded SSM mean to **0.994 m nominal, 1.026 m moving clean, 1.113 m moving combined**. Its warm-start checkpoints averaged 0.918 m nominal and 1.210 m stress. Expansion cut stress by 0.140 m and raised nominal ATE by 0.076 m. The matched expanded EMA averaged **0.998 m nominal, 1.017 m moving clean, 1.074 m moving combined**. The nominal difference between the newly trained SSM and EMA was about 5 mm on development.

The finalist SSM consumed 1,020 windows and optimizer steps over its three seeds, with 214,920 processed frames. The matched EMA consumed 1,080 windows and steps with 227,091 processed frames. Both started from the matched historical checkpoints, received one window per parent per epoch, and used the same optimizer, 10-epoch cap, and three-epoch patience. Two-seed screen candidates completed 4–9 epochs per seed. Nominal and stress development curves fluctuated after the chosen epochs and did not show sustained improvement at the cutoff.

## Frozen guest confirmation

The development rule froze seed 1 for each retrained model by median nominal score across its three seeds. The original and inexpensive reference weights were reused with the corrected remap. Confirmation compared all six Wasm modules on three fresh nominal flights and a separately reported 55 s flight. Peak fuel includes every scored frame in all four scenes.

| Guest model | Nominal mean ATE (m) | 55 s clean ATE (m) | 50 s moving clean ATE (m) | 50 s moving combined ATE (m) | Max fuel/frame (M) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original SSM | 0.650 | 1.142 | 1.764 | 1.918 | 25.91 |
| Original matched EMA | 0.853 | 1.244 | 1.615 | 1.680 | 25.57 |
| Previous EMA | 0.906 | 0.956 | 1.667 | 1.632 | 16.93 |
| Previous compact student | 0.831 | 1.059 | 1.772 | 1.773 | 13.92 |
| Expanded SSM | 0.840 | 1.286 | 1.622 | 1.715 | 25.91 |
| Expanded matched EMA | 0.908 | 1.088 | 1.425 | 1.472 | 25.57 |

The expanded SSM improved the original SSM by 0.203 m on the disrupted moving-start flight. It lost 0.191 m nominally. The expanded matched EMA did better on both moving replays at slightly lower fuel. The expanded SSM's nominal ATE was lower than the expanded EMA's, but the original SSM achieved much better nominal accuracy at the same fuel and the compact student achieved slightly better nominal accuracy at about 54% of the fuel. The expanded SSM adds no point to the measured nominal frontier.

The cost increase came from making image warps agree across environments. On the same development flight, the archived original SSM used 23.61M fuel/frame and the corrected remap used 25.89M, a 9.7% increase. On confirmation, robustness training changed SSM peak fuel by less than 0.02% relative to the corrected original. The expanded SSM Wasm was 50,327,082 bytes, including 284,724 bytes of weight data, and its linear memory reached 50,593,792 bytes. The matched expanded EMA measured 50,300,232 bytes of Wasm, 257,886 bytes of weight data, and 50,528,256 bytes of linear memory.

All 36 guest replays emitted complete, finite outputs. Independently replayed 160-frame prefixes matched bit for bit. The maximum guest-to-host position separation was 0.68 μm across all six modules. The disturbance replay exercised missing-image handling via a test adapter because the standard benchmark ABI always presents RGB. A production source of explicit missing-image notifications and live-server scoring remain unverified. The one longer flight is insufficient to establish a population-level stress ranking. Backward/lateral generalization also remains unmeasured.

Keep the original corrected SSM for nominal accuracy and the compact student where nominal fuel dominates. Carry the expanded EMA and the previous inexpensive EMA forward to a larger, scene-disjoint moving-start study. Use newly generated physical backward and lateral trajectories in that study. The current results do not justify shipping the trained reliability or zero-initial state variants, expanding the bias head, or starting a larger visual encoder or distillation sweep.

## Artifacts

- [Final per-flight guest comparison](results/20261118T024624Z-robust-plots-188ae8de/guest-paired.csv) and [frozen checkpoints](results/20261118T024045Z-robust-freeze-f8c4e92f/manifest.json)
- [Historical-path stress matrix](results/20261118T022128Z-robust-matrix-ef41afdd/paired.csv) and [corrected-runtime stress matrix](results/20261118T023559Z-robust-matrix-78ed86eb/paired.csv)
- [Stress conditions](results/20261118T024624Z-robust-plots-188ae8de/stress-conditions.png), [error over time](results/20261118T024624Z-robust-plots-188ae8de/error-over-time.png), and [learning curves](results/20261118T024624Z-robust-plots-188ae8de/learning-curves.png)
- [Nominal accuracy–fuel](results/20261118T024624Z-robust-plots-188ae8de/nominal-accuracy-fuel.png) and [guest stress](results/20261118T024624Z-robust-plots-188ae8de/guest-stress.png)
- [Parity trace summary](results/20261118T023559Z-robust-parity-081051d1/parity.json), [training motion audit](results/20261118T024147Z-robust-data-audit-24d12526/manifest.json), and [yaw pilot](results/20261118T023133Z-robust-yaw-pilot-b35de75e/manifest.json)

## Reproduce

Run from this directory. The launchers use the existing Mac conda environments and benchmark checkout.

```sh
bash robustness_env.sh parity --flights 2
bash robustness_env.sh parity --fixed --fast --flights 6
bash robustness_env.sh matrix
bash robustness_env.sh matrix --fixed
bash robustness_env.sh start-probe
bash robustness_env.sh bias-probe
bash robustness_env.sh legacy-fuel
bash robustness_env.sh train
bash robustness_env.sh select --screen results/SCREEN
bash robustness_env.sh train --variant SELECTED_SSM --seed 2
bash robustness_env.sh train --variant ema-expanded --seed 2
bash robustness_env.sh select --screen results/SCREEN --followup results/SSM_SEED2 --followup results/EMA_SEED2
bash robust_sim.sh yaw-pilot
bash robust_sim.sh confirmation
bash robustness_env.sh deploy --fast --freeze results/FREEZE/manifest.json --confirmation results/CONFIRMATION
bash robustness_env.sh audit-data --training results/SCREEN --training results/SSM_SEED2 --training results/EMA_SEED2
bash robustness_env.sh plot --matrix results/MATRIX --training results/SCREEN --training results/SSM_SEED2 --training results/EMA_SEED2 --guest results/GUEST
/opt/miniconda3/bin/python -B test_causal.py
```

Simulator launch requires Metal access and the checksummed ProcTHOR assets. GPU-denied attempts and diagnostic or training startup failures are retained alongside successful runs.
