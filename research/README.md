# Stage-2 VIO research

Run commands from this directory. Install or use an existing Python environment with NumPy, OpenCV and PyTorch. Native replay additionally uses the workspace VIOBench checkout and the bundled Python runtime from the workspace build directory. Local scoring uses unaligned first-camera position RMSE. Sim(3) ATE is a diagnostic.

`experiments.json` fixes the cache version, calibration thresholds, preprocessing, seeds and training schedule. The primary roster takes one lexicographically first base parent per scene from each of `data/train` and `data/val`. The latter scenes are development scenes. ProcTHOR-Train-162 through -165 are reserved for a future frozen comparison and excluded from the training and development loader. Each run fingerprints the exact parents and cached inputs. Old cache directories and results are historical.

## Reproduce

```sh
./run_all.sh
python -B seq_heads.py results/VISUAL_RUN
python -B seq_heads.py results/VISUAL_RUN --head selective
python -B bias_probe.py results/VISUAL_RUN
python -B bias_probe.py results/VISUAL_RUN --policy startup
python -B decompose.py results/VISUAL_RUN --diagnostics-only
```

The first command runs the causal tests, a visual smoke test and the two-seed visual comparison. It prints separate run directories. For preprocessing only, use `python -B pairs.py 'data/train/base-*.npz' --policy evidence`. Pass `--crop 5` to reset from raw observations at five seconds.

After verifying the filtered teacher, run `python -B learned_probe.py --distill-from results/TEMPORAL_RUN`. Replay the two students using the same native inputs with `--student-only --student-run results/STUDENT_RUN --calibration startup --skip-transfer`. Use the same visual and temporal run arguments.

Repeat the native command with `--calibration startup --skip-transfer` and the startup-trained rotation run to reproduce the paired native calibration control.

The native replay here used the workspace's cached public and smoke archives. On this Mac the commands below combine the existing base Python's PyTorch with Wasmtime and YAML from the already provisioned VIOBench environment.

```sh
export PYTHONPATH="$PWD/../../../../Final Project/viobench:$PWD/../../../../Final Project/classical_vio/research/data/local-python"
native_replay='import sys; sys.path.append("/opt/miniconda3/envs/eecs116/lib/python3.10/site-packages"); from decompose import main; main()'
/opt/miniconda3/bin/python -B -c "$native_replay" results/VISUAL_RUN results/TEMPORAL_RUN \
  --rotation-run results/ROTATION_RUN \
  --native '../../../../Final Project/classical_vio/build/dataset_example/cache/0386e5c941b50fe9972ddabff84c414540fb8989' \
  --native '../../../../Final Project/classical_vio/research/data/20261117T185910Z-generate-da8be58c/smoke/sim-ProcTHOR-Train-2-0000.zip'
python -B decompose.py results/VISUAL_RUN results/TEMPORAL_RUN --report \
  --smoke-run results/VISUAL_SMOKE_RUN --selective-run results/SELECTIVE_RUN \
  --rotation-run results/ROTATION_RUN --startup-rotation-run results/STARTUP_ROTATION_RUN \
  --diagnostic-run results/DIAGNOSTIC_RUN --deployment-run results/DEPLOYMENT_RUN \
  --native-startup-run results/NATIVE_STARTUP_RUN --pareto /path/to/snapshot.png \
  --student-run results/STUDENT_RUN --student-guest-run results/STUDENT_GUEST_RUN
```

## Evaluation and export

The first camera defines the pose origin. Gyro propagation starts from an arbitrary identity attitude gauge. Bias activation occurs after processing the first observed second and affects only later propagation. The evidence policy requires low gyro mean, near-gravity accelerometer magnitude and small image change across the window. Startup calibration uses the window without a stillness gate. Deployment discards the pre-origin IMU packet to match the proxy first-frame input. Every image produces a velocity, including the first, with explicit unavailable-image masks and a missing-IMU flag. There is no zero-velocity update.

Images resize with pixel-center intrinsics, then past images warp with the relative gyro rotation. Constant borders and a separately warped validity plane represent missing samples. The current frame and 0.25-second and 1-second histories use a preceding frame at or before each time offset. A derotated model uses gyro in the warp even when it has no explicit IMU network branch.

The supervised endpoint target is instantaneous body velocity. The shared loss adds 0.25-, 1- and 3-second displacement residuals in a common frame using truth orientation for the supervised term. Integrals use trapezoidal world-frame velocity and actual interval lengths. Horizons start at the last frame at or before the requested time. Deployment and full estimated-orientation replay use estimated attitude and the same integration rule. Pose includes the camera lever arm. Sequence checkpoints use ordered chunks with up to 60 prior frames for burn-in. Evaluation streams complete episodes. Moving-start replay crops raw data before reinitializing the complete estimator.

Rotation probes use nonoverlapping half-second windows, sample-level bias injection, a full per-sample gyro integration and rotation-warped bearing residuals. The geometric probe requires tracked support, conditioning, a small median fit residual and a bounded correction. The learned ridge probe predicts the right-multiplicative relative-rotation residual under the same gate and caps its update at 0.04 rad. Both change the accumulated orientation at accepted windows. The startup bias is an independent calibration state. Paired native-versus-injected calibration estimates measure recovery of the added component. Physical instantaneous simulator bias is unobserved.

Wasm exports contain only causal preprocessing, inference and frozen parameters. The deployment comparison measures guest trajectories and peak fuel including initialization-period frames. Native rotation modules also feed their corrected orientation to visual derotation, while the controlled proxy rotation experiment holds the translation predictions fixed. Error-budget scaling and centered smoothing are privileged diagnostics. Separate interventions share correlated error sources, so gains should be read in paired comparisons.

## Sources

- [DOGE](https://arxiv.org/abs/2412.08135)
- [OpenVINS stationarity and zero velocity](https://docs.openvins.com/update-zerovelocity.html)
- [Learned IMU bias prediction](https://arxiv.org/abs/2505.06748)

## Joint CNN–IMU experiments

The joint entry points extend the same cache, orientation chain and guest ABI. Run the commands from this directory. On this Mac, the renderer uses the existing Python 3.10 environment. Training uses the base Python with PyTorch, and appends the benchmark environment for native archive and Wasmtime support.

```sh
stage1_data="$PWD/../../../../Final Project/classical_vio/research/data"
bench_dir="$PWD/../../../../Final Project/viobench"
PYTHONPATH="$bench_dir:$stage1_data/sim-python:$stage1_data/local-python" \
HYPERLUX_CACHE_DIR="$stage1_data/hyperlux-cache" CONTA_CACHE="$stage1_data/scene-cache" \
PYTHONHASHSEED=0 /opt/miniconda3/envs/eecs116/bin/python -B gen.py --native-joint

/opt/miniconda3/bin/python -B gen.py --inventory
/opt/miniconda3/bin/python -B test_causal.py
/opt/miniconda3/bin/python -B seq_heads.py --joint --phase feedback-smoke
/opt/miniconda3/bin/python -B seq_heads.py --joint --phase screen --epochs 8 --chunks-per-parent 1

export PYTHONPATH="$bench_dir:$stage1_data/local-python"
joint_train='import sys; sys.path.append("/opt/miniconda3/envs/eecs116/lib/python3.10/site-packages"); from seq_heads import joint_main; joint_main()'
joint_deploy='import sys; sys.path.append("/opt/miniconda3/envs/eecs116/lib/python3.10/site-packages"); from decompose import joint_deploy; joint_deploy()'
/opt/miniconda3/bin/python -B gen.py --native-motion results/NATIVE_DATA_RUN
/opt/miniconda3/bin/python -B -c "$joint_train" --phase native-bias --data-run results/NATIVE_DATA_RUN
/opt/miniconda3/bin/python -B -c "$joint_train" --phase finalists --epochs 8 --chunks-per-parent 1 \
  --screen-run results/SCREEN_RUN --data-run results/NATIVE_DATA_RUN
/opt/miniconda3/bin/python -B -c "$joint_train" --phase teacher --epochs 8 --chunks-per-parent 1 \
  --finalists results/FINALISTS_RUN --data-run results/NATIVE_DATA_RUN
/opt/miniconda3/bin/python -B -c "$joint_deploy" \
  --finalists results/FINALISTS_RUN --data-run results/NATIVE_DATA_RUN --teacher results/TEACHER_RUN
/opt/miniconda3/bin/python -B decompose.py --joint --report \
  --inventory results/INVENTORY_RUN --data-run results/NATIVE_DATA_RUN --screen results/SCREEN_RUN \
  --feedback results/FEEDBACK_RUN --profile results/PROFILE_RUN --export-smoke results/EXPORT_RUN \
  --motion results/MOTION_RUN --pilot results/PILOT_RUN --guest-dev results/DEVELOPMENT_GUEST_RUN \
  --finalists results/FINALISTS_RUN --teacher results/TEACHER_RUN --final results/FINAL_RUN
```

For early fuel verification, run the deployment entry with `--smoke /path/to/old/smoke.zip`. Run it with `--profile` and the same archive to measure cumulative guest costs with an ABI identity path, orientation, image resize, warp, CNN, and full EMA inference. Profile outputs and random-weight smoke outputs are diagnostic.

The reduced native batch contains 12 train, six development, and eight reserved test scenes, one 30-second flight per scene. Allocation and seeds are fixed in the versioned configuration. Inspect `audit.json` before fitting. The native generation path uses the upstream simulator and nominal camera. Proxy images and the upstream camera retain their domain identities. Benchmark archive conversion uses the guest delivery resize, the supplied extrinsics, and the same pre-origin first-packet convention. Test archives are used for file and motion audits before the freeze. The final guest command checks disjoint scenes and writes its freeze manifest before evaluating.

Joint training caps each candidate at a configured number of epochs and saves the best development checkpoint. The smaller CPU schedule rotates the contiguous chunk used per parent across epochs, with up to 80 frames of preceding burn-in. The feedback-smoke run scopes its conclusions to four proxy training scenes and three development scenes. Nominal and moving-start stress results are separate. Stress starts from raw sensor streams and adds parent-seeded gyro disturbances in rad/s, timestamp jitter of at most 1 ms, and short image gaps. A missing camera frame has an explicit validity bit in the host tests. The VIOBench ABI delivers frames as RGB arrays. The fresh guest runs measure the archived nominal observations.

The filtered and recurrent variants share endpoint and 0.25, 1, 3 and 6-second displacement terms with estimated orientation. Auxiliary gyro supervision uses only known injected offsets after paired calibration. An additional differentiable orientation term approximates the effects of gyro bias in the loss. Checkpoint validation for feedback and paired closed-loop attribution use exact streaming integration and derotation. Geometry corrections and accelerometer-bias prediction are outside this experiment. The acceleration measurements are used as inputs and evidence for rolling calibration.

Peak process RSS in the guest reports includes the evaluator, PyTorch, episode data and Wasmtime. The configured Wasm memory limit is recorded independently. The reported RSS is not an isolated guest linear-memory measurement.

The teacher family is chosen using average development ATE across seeds. The compact comparison keeps label loss in both arms and adds the frozen teacher's motion outputs only for training parents.

## Selective SSM robustness

The [robustness milestone report](ROBUSTNESS.md) contains the parity diagnosis, paired development stress tests, training ablations, and fresh-scene Wasm comparison. Its reproduction commands use `robustness_env.sh` for development and deployment and `robust_sim.sh` for the simulator.

## Teacher models (GRU and selective SSM)

Run locally on MPS with `./teacher_env.sh`. `teacher_data.py` prepares checksummed
episodes. `teacher_train.py` trains with resumable Accelerate checkpoints, and
`--hub-repo` pushes each completed epoch to the private repo
`SentientNapkin/viobench-teacher-lab` (`teacher_hub.py init|push|pull`).
Resuming reproduces the uninterrupted loss exactly, including from a pulled copy.

### Performance: where a C/C++ (or Metal/CUDA) rewrite would help

Most of the arithmetic already runs in compiled code: convolutions, GRU,
matmuls, and `cv2` warps are C++/Metal kernels. Rewriting the whole pipeline
in C++ would not speed those up. The cost is Python driving many small
operations one at a time:

1. **SSM time loop** (`SelectiveBlock.forward`): one Python iteration per frame
   per layer, each launching several tiny GPU kernels. This is the main
   training bottleneck for the SSM head. Fix: a parallel associative scan in
   PyTorch, or a fused Metal/CUDA scan kernel (the Mamba approach).
2. **Data preparation and streaming features** (`streaming.Inputs.step`,
   `orientation.py`): per-frame Python with numpy, called about 160k times for
   the full dataset. Fix: C++ (pybind11), or a batched vectorized rewrite.
   This is a one-off cost per dataset, so it matters less for training than
   for deployment.
3. **Deployment inference**: the onboard estimator runs per frame on CPU, so
   the full streaming path (warps, feature extraction, recurrent head) is where
   a C++ implementation pays off most. Options include C++ with the existing
   weights exported via safetensors, or ONNX Runtime/Core ML.
4. **Smaller items**: the `frame_chunk` loop in `VisualMotion` and chunked
   evaluation replay (both batching choices, cheap to tune) and
   single-threaded `.npz` decompression in the `DataLoader`
   (`num_workers=0`; uncompressed or memory-mapped arrays avoid it).

Priority if training speed matters: (1), then (4). If onboard latency
matters: (3), then (2).
