# Frozen velocity gyro calibration ablation

Source read: VIOBench commit `9b1b07906aff5a3e6f00155e7aecf967d90aa960`, actual provided OpenVINS `solution.cpp`, `rotation_update.h`, and README; learned `orientation.py`, `streaming.py`, `odometry_data.py`, `odometry_eval.py`; prior visual-attitude code and attitude branch notes.

The provided OpenVINS uses distributed visual rotation correspondences to distinguish rotation-only startup from translating motion, then estimates biases jointly with visual and IMU factors. Our learned path instead accepts rolling windows using gyro magnitude/dispersion, accelerometer magnitude, and image difference. Low texture or slow persistent rotation may pass these tests and be absorbed into the gyro bias. The previous campaign truth-velocity diagnostic found raw gyro propagation better than rolling calibration. It did not establish improvements with predicted velocity.

Before scoring, `configs/experiments.json:frozen_bias_ablation` declares precisely two interventions: raw zero-bias gyro propagation and freezing the gyro bias after the first accepted rolling window. No thresholds, model weights, or visual fits are searched. Matched seeds 217/218/219 retain their original preprocessed visual inputs, direct IMU features, and predicted body velocities. Only integration attitude changes. This is separate from the earlier failed visual correction and EKF arms.

Reproduce in this worktree:

```bash
cd /data/backups/rganapa/Sebastian/odometry-bias-ablation/research
CUDA_VISIBLE_DEVICES=5 /data/backups/rganapa/Sebastian/venv-teacher/bin/python bias_ablation.py \
  --raw-dev /data/backups/rganapa/Sebastian/gen/raw/dev \
  --output results/loop/frozen-bias --device cuda
```

All 120 campaign-dev crop records are scored; no reserved test records are loaded. Thirty-second scores cap all records, preserving the historical 25-second remainder of 30-second parents cropped at five seconds. Sixty-second scores include only replays with at least 59.89 seconds, and full scores use the complete stored durations. Motion labels are recomputed for each horizon. The report includes seed, scene, parent, catalog, crop-origin, and actual start-speed groups. Parent and scene group means expose dependence; overlapping crops are not independent trials.

The control must reconstruct each stored attitude from raw IMU and current resized images within 1e-6 maximum matrix-element error. A shortened replay must be exactly identical to its full replay prefix. Model inputs remain frozen intentionally: this screen does not validate a complete system because changing attitude inside `Inputs` also changes image derotation and gyro/bias features. A passing attitude-only screen would require complete input regeneration, original-dev/proxy guards, and C++/Wasm parity and whole-guest fuel before qualification. Original-dev raw data are unavailable here, so campaign improvement alone cannot qualify a deployment.

Offline finite velocity frames are reported as such. They do not establish raw guest completion or missing-frame behavior. Fuel is unmeasured for these diagnostic-only variants. Existing historical gates remain unchanged.
