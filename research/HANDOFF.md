# Handoff: learned odometry for VIOBench (EECS 116 Project 3, Stage 2)

Written 2026-11-18 ~23:30 UTC on the GPU box (`wnckcaina01`) for continuing the work in Codex.
Everything below is the state at that time; training runs keep going after this was written.

## 1. Goal, metric, rules

- **Goal:** lower **mean unaligned ATE (metres, log scale)** at competitive peak WebAssembly fuel per frame.
  Target set by Sebastian: **~0.5 m**. Best so far: **1.095 m dev** (`B-D0-ssm-x3`, 3 seeds).
- **Metric:** mean unaligned ATE only. **Never use Sim(3) ATE** (removed from all code, plots and decisions).
- **Rules:**
  - Sebastian (`SentientNapkin`) is the only author: commit with
    `git -c user.name=SentientNapkin -c user.email=sebastian.vargas.reiners@gmail.com commit ...`.
    Never add co-author lines. Never push to `main`; Sebastian merges.
  - No paid infrastructure, no VIOBench submissions (Sebastian submits).
  - Every WebAssembly solution must be compiled from **C or C++**.
  - Decisions need **3 seeds (217/218/219)**: identical runs differ by up to 0.29 m on dev.
  - Declare comparisons and gates in `configs/experiments.json` *before* results exist.
  - Generated data and results stay in git-ignored folders (`data/`, `results/loop/`); small eval JSON/PNG
    summaries under `results/eval/` are committed.

## 2. Machine and environment

- 8× H100 80 GB. GPU 0 also hosts someone else's 2 GB service (light use is fine).
- Root disk `/` is **100% full**: work only under `/data/backups/rganapa/Sebastian` (NFS, ~14 TB free) or
  `/dev/shm` (local tmpfs, ~880 GB) for small local caches.
- Training/eval environment (every shell):
  ```bash
  source /data/backups/rganapa/Sebastian/venv-teacher/bin/activate
  export HF_HOME=/data/backups/rganapa/Sebastian/hf TMPDIR=/data/backups/rganapa/Sebastian/tmp PIP_CACHE_DIR=/data/backups/rganapa/Sebastian/pip-cache
  cd /data/backups/rganapa/Sebastian/eecs116_projects/research
  ```
  (torch 2.15+cu132, numpy 2.5.5, cv2 5.1.0, accelerate 1.16, `viobench==0.0.1` installed for reading episodes.)
- Simulator environment (dataset generation only): `source /data/backups/rganapa/Sebastian/gen/env.sh`
  (venv `/data/backups/rganapa/Sebastian/venv-sim` with `viobench[sim]==0.0.1`, `hyperdrone`/`hyperlux` 0.1.10,
  OptiX renderer).
- `git push` from this box fails (no GitHub credentials). The branch is local only; push from a machine with
  credentials: `git push -u origin research/learned-odometry` (the old remote branch
  `claude/teacher-model-training-60911a` holds older commits and can be deleted afterwards).

## 3. Repository and code map

Repo `/data/backups/rganapa/Sebastian/eecs116_projects`, branch **`research/learned-odometry`** (HEAD `7cabf8f`),
everything under `research/`. The pipeline was called "teacher" until 2026-11-18 and was renamed to
**learned odometry** (it is not teacher–student distillation). Hub repo/manifest/run names keep old names.

**What the model is:** a small CNN (trained end to end) embeds gyro-derotated grayscale image histories
(128×96, 5 channels: current, short and long warped history, two masks) plus a local correlation volume; with
51 IMU features per frame it feeds a GRU or selective-SSM head that predicts body-frame velocity every frame
(20 Hz). Velocity is integrated through the gyro-estimated attitude (`R`) into camera positions.
Loss: smooth-L1 on velocity plus displacement error over 0.25/1/3 s horizons after 32 burn-in frames.
Training: batch 1 × accumulation 2, weight EMA 0.995, warmup + cosine LR, no early stopping.
Parameters: CNN 438K, projection 678K, SSM head 145K, sensor/output 25K (~1.29M total).

| File | Purpose |
| --- | --- |
| `odometry_models.py` | `OdometryNet`: CNN + correlation, heads `gru`, `ssm`, `ema`, `gru_res`, `gru_ssm`; options `attitude_input`, `blind`, `imu_blind`. |
| `odometry_data.py` | Shard loading, motion labels, `WindowPlan` (original/balanced samplers, `domain_share`, exposure accounting; odd window counts rejected in original mode). |
| `odometry_train.py` | Accelerate training, resumable checkpoints (pickled model state: safetensors dropped cuDNN GRU weights), background Hub sync, `--set key=json` overrides. |
| `odometry_eval.py` | Full continuous replays: `--set dev | proxy-val | campaign-dev`, `--max-seconds 30`, `--plots`, `--control <run>` scene-paired bootstrap; zero-output and true-velocity (rotation floor) rows; campaign results split by ProcTHOR/HSSD. |
| `odometry_store.py` | Hub storage, streaming `ShardCache`, `compose` (immutable manifests). |
| `odometry_pool.py` | Shard preparation (`prepare`), gates: reject only non-finite truth, <2 m travel, stalls. |
| `odometry_ledger.py`, `odometry_hub.py`, `odometry_gen.py` | Parent-flight ledger; Hub sync (`BackgroundSync`); old continuous generator (superseded). |
| `native_campaign.py` + `configs/native_campaign.json` | Split-safe native flight campaign: roster, generation workers, audit, `prepare`, `publish`, metadata `upload`. |
| `launch.py` + `configs/experiments.json` | Named experiments, budgets, predeclared gates. `python launch.py <name> [--seed N] --gpu G --tag T`. One shard cache per run. |
| `configs/odometry.json` | Base model/training config (`distillation_weight` is an inert legacy key kept for resume). |
| `test_odometry.py` | 13 regression tests (leakage, sampler determinism, causality/streaming for all heads, CUDA checkpoint completeness, campaign split integrity, truth-integration check). Run `python test_odometry.py`. |
| `ODOMETRY.md` | Guide and current verdict. `loop/NOTES.md` is the detailed chronological log (read it for every number). |

## 4. Data

Hub dataset repo `SentientNapkin/viobench-teacher-data` (private), content-addressed `shards/<sha256>.npz`,
immutable `manifests/<name>.json`, ledger `ledger/ledger-20261118.json` (local copy `data/ledger/ledger.json`).

**Scene policy:** development ProcTHOR 166–171; final test 162–165, 172–175; confirmation 176–179 (quarantined);
proxy validation 150–161 (contaminated for generated-pool v2–v4 models); training everything else.

| Manifest | Contents |
| --- | --- |
| `teacher-full` / `-labeled` | D0: 48 proxy base + 12 native + 1 native yaw parents, crops 0/5 s. Dev roster: 7 native parents → 14 replays, 6 scenes. |
| `d1-expanded-tiers` / `-labeled` | All 280 proxy training parents (base/mid/agile) + same native; same dev roster. |
| `n1-campaign` | `teacher-full-labeled` + 592 native-campaign train parents (1,306 train records). Data revision `508d93ffd230e5c6dfb543312e768b678339382b`. |
| `n2-campaign-tiers` | `d1-expanded-tiers-labeled` + 592 campaign parents (1,770 train records). |
| `proxy-validation-records` | 68 proxy-val parents (90 s flights), recovered; local `data/expand/proxy-proxy_validation-0.json`. |
| `native-campaign-{train,dev}-records-*` | Campaign records; local `data/native-campaign/{train,dev}-records.json`, shards in `data/native-campaign/shards`. |

**Native campaign (built today on this box):** 600 train / 60 dev / 88 reserved-test simulated flights
(30/60/90 s, 25% independent-yaw autopilot for backward/lateral motion, varied hover and route density),
raw 640×480 archives kept at `/data/backups/rganapa/Sebastian/gen/raw/{train,dev,test}` (~100 GB, per-flight
audit JSON next to each zip). Realized: 592 train, 60 dev, 84 test (scenes ProcTHOR-Train-121/124 and two HSSD
houses always crash the simulator). Train: ProcTHOR 0–9/46–149/180–199 + HSSD Train125. Dev: ProcTHOR 166–171
+ 15 never-used HSSD Val43 houses. **Test (reserved, never prepared or scored):** ProcTHOR 162–165/172–175 + 28
HSSD Val43 houses. Roster + audits: private `SentientNapkin/viobench-native-campaign` (metadata only).
Generation: `N=40 /data/backups/rganapa/Sebastian/gen/run_campaign.sh` (shared JIT cache on `/dev/shm`;
leftovers one process per flight with `native_campaign.py generate --ids ...`).

**Evaluation sets:** dev (14 replays), proxy-val 30 s (68 replays, 12 unseen scenes; declared holdout
criterion), proxy-val 90 s (long-horizon diagnostic), campaign-dev (120 replays; ProcTHOR and HSSD separately,
30 s and full).

## 5. Results so far (mean unaligned ATE, m; 3-seed means unless noted)

| Model | Dev | Dev ordinary | Proxy-val 30 s | Campaign-dev 30 s |
| --- | --- | --- | --- | --- |
| Zero output | 2.591 | 2.669 | 2.041 | 2.843 |
| True velocity through our attitude (rotation floor) | 0.407 | 0.428 | 0.348 | 0.530 |
| Submitted EMA guest (32×24, Mac replay) | 1.291 | 1.055 | – | – |
| Submitted SSM guest | 1.395 | – | – | – |
| D0-ssm, 12 epochs | 1.337 (1.152/1.439/1.420) | 1.210 | 1.359 | – |
| D2-ssm (expanded proxy, balanced), 12 epochs | 1.509 | 1.201 | 1.347 | – |
| **B-D0-ssm-x3** (D0, 36 epochs) | **1.095** (1.054/1.120/1.111) | **0.921** | 1.276 | 1.353 |
| B-D2-ssm-x3 (expanded proxy, 36 epochs) | 1.250 | 0.952 | **1.128** | 1.402 (HSSD 1.133) |

Findings:
- **Training 3× longer (36 epochs, 4,392 updates) is the biggest win**; B-D0 beats the submitted EMA in every seed.
- Seed noise is large; the scene-paired bootstrap does not capture training randomness.
- Expanded proxy data helps unseen scenes and ordinary motion at 3× budget but **backward motion learned from proxy renders does not transfer to native** (backward sign ≈0 on native yaw flights; campaign-dev backward/lateral 4.9 vs 3.5).
- Architecture is not the bottleneck: 2/4-layer SSM, residual GRU, GRU→SSM all within seed noise (single seed, 12 epochs). Residual GRU ≫ plain GRU. 12 s context at matched data hurts. Zeroing direct IMU features costs ~5%.
- Velocity RMSE ~0.15 m/s; the rotation floor (0.41 dev) means **velocity improvements alone cannot reach 0.5 m** — attitude correction / fusion is required.

## 6. Running right now (do not cancel)

Detached training processes (launched by `launch.py`, logs `results/loop/<run>.log`, checkpoints
`results/loop/<run>/checkpoints/epoch-*/complete.json`, best weights `best.safetensors`, synced to the private
lab repo `SentientNapkin/viobench-teacher-lab` under `runs/<run>/`):

| Runs | Data | Status at handoff (best dev selection score) |
| --- | --- | --- |
| `N1-ssm-x3-gpu`, `-s218-gpu`, `-s219-gpu` | `n1-campaign` (D0 + native campaign), 36 epochs | epoch 33/36; 1.226 / 1.210 / 1.153 |
| `B-D2n-ssm-x3-gpu`, `-s218-gpu`, `-s219-gpu` | expanded proxy, native share 21.3%, balanced, 36 epochs (predeclared domain follow-up) | epoch 35/36; 1.335 / 1.384 / 1.303 |
| `N2-ssm-x3-gpu`, `-s218-gpu`, `-s219-gpu` | `n2-campaign-tiers`, balanced, 36 epochs | epoch 16/36; 1.214 / 1.166 / 1.217 |

The selection score is the training-time dev metric (mean of nominal and 5 s moving-start ATE); final numbers
come from full replays. **Next step when they finish** (compare against B-D0-ssm-x3 under the native-campaign
gates in `configs/experiments.json`):
```bash
R="results/loop/B-D0-ssm-x3-gpu results/loop/B-D0-ssm-x3-s218-gpu results/loop/B-D0-ssm-x3-s219-gpu results/loop/N1-ssm-x3-gpu results/loop/N1-ssm-x3-s218-gpu results/loop/N1-ssm-x3-s219-gpu results/loop/B-D2n-ssm-x3-gpu results/loop/B-D2n-ssm-x3-s218-gpu results/loop/B-D2n-ssm-x3-s219-gpu"
for s in "--set dev" "--set proxy-val --max-seconds 30" "--set campaign-dev --max-seconds 30" "--set campaign-dev"; do
  CUDA_VISIBLE_DEVICES=0 python odometry_eval.py $s --runs $R --control B-D0-ssm-x3-gpu --output results/eval/n-series --plots; done
```
Decide on 3-seed means: screen ≥10% lower dev mean ATE, ≤5% regression on ordinary dev flights, then check
proxy-val 30 s and campaign-dev (ProcTHOR/HSSD separately). Log in `loop/NOTES.md`, update the verdict in `ODOMETRY.md`.

Useful commands:
```bash
grep -h '^{"epoch' results/loop/N1-ssm-x3-gpu.log | tail -3 | cut -c1-200      # progress
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv
for pid in $(pgrep -x python); do tr '\0' ' ' < /proc/$pid/cmdline | grep -qE "teacher_train|odometry_train" && echo $pid; done
```

## 7. Parallel workstreams (Claude subagents) and their branches

Six agents were started from Claude Code, each in its own git worktree with its own branch off
`research/learned-odometry`. Brief they all follow: `/data/backups/rganapa/Sebastian/gen/AGENT_BRIEF.md`.
They may still be running or may have stopped when the Claude session ended; their **branches and any training
runs they launched persist**. To continue in Codex: inspect each branch (`git log research/learned-odometry..odometry/<name>`),
read its `research/loop/NOTES.md` entry, check its runs in that worktree's `research/results/loop/`, and finish the task.
Worktrees: `/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/agent-*` (each has `research/data`
symlinked to the main checkout's data).

| Branch | Task | GPUs | State at handoff |
| --- | --- | --- | --- |
| `odometry/throughput` | Profile and speed up training ≥10× per epoch-equivalent: exact parallel/chunked associative scan for the SSM (opt-in `model.ssm_scan`), DataLoader workers/prefetch, TF32/bf16, torch.compile/CUDA graphs; a fast larger-batch recipe with retuned LR validated at 3 seeds vs B-D0; measure batch saturation on 1 GPU, then DDP scaling 1→2→4 GPUs. | 0, 5 (+4, 6 briefly) | no commits yet |
| `odometry/hparam` | Hyperparameter search (LR, EMA, window, burn-in, horizons, widths, weight decay, grad clip), successive halving with 2 seeds at 12 epochs, top configs at 36 epochs × 3 seeds vs B-D0. | 1, 2, 3, 7 | driver committed (`b804b78`: driver + opt-in `training.weight_decay`, `training.grad_clip`) |
| `odometry/attitude` | Diagnose attitude error vs truth (raw campaign archives have true attitude via `common.Flight`), then a learned gyro-bias / rotation correction trained end to end through the displacement loss. Critical for 0.5 m. | 6 | no commits yet |
| `odometry/ekf` | Uncertainty head (Gaussian NLL), causal fixed-size EKF (position, velocity, accel bias, optionally gyro bias) fusing learned velocity with IMU propagation; tune noise on training flights only; first a fixed-covariance EKF post-processor on B-D0. | 4 | no commits yet |
| `odometry/refine` | Iterative refinement (RAFT/DPVO-style shared update operator correcting velocity from a photometric/correlation or inertial-consistency residual), causal and C-portable. | 7 | no commits yet |
| `odometry/deploy` | Deployment path for B-D0: per-frame MACs/params vs submitted EMA, wasm fuel estimates, then a **C/C++** inference port (CNN, correlation, projection, SSM, preprocessing, attitude, integration) with PyTorch parity tests, wasm build through the viobench toolchain, local fuel and ATE measurement. | CPU (5 if needed) | no commits yet |

Merge policy: review each branch, keep new paths opt-in, `test_odometry.py` green, adopt only what improves the
3-seed mean ATE. Suggested order once throughput lands: forward the fast path to the other workstreams.

**Separate session (not ours, read-only):** a Codex session in `/data/backups/rganapa/Sebastian/eecs116_visual_motion`
(branch `research/visual-motion`) compares frozen SEA-RAFT features vs the frozen CNN on the N1 data and is
porting CNN/EMA inference to C++ (`research/native_student/README.md`, `research/VISUAL_MOTION.md`). It reads
the campaign staging folder; coordinate rather than duplicate (especially the C++ port).

## 8. Plan to reach ~0.5 m

1. **Faster iteration** (throughput): everything else depends on it.
2. **Attitude**: learned gyro-bias/attitude correction; the rotation floor (0.41 dev, 1.04 at 90 s) must fall well below 0.5.
3. **Fusion**: uncertainty + EKF with gyro-bias state.
4. **Data**: N1/N2 results decide whether native campaign data is adopted; native backward/lateral flights are the fix for backward-motion failures.
5. **Recipe**: hyperparameters at 36+ epochs; longer training still improving.
6. **Refinement** if fuel allows.
7. **Deployment**: shrink (resolution, CNN width, projection, int8, distillation into a compact model) to a competitive fuel budget, C/C++ → wasm, parity, peak fuel, then Sebastian submits.
8. Final: evaluate the frozen candidate once on the reserved campaign test split and the original final-test scenes.

## 9. Pitfalls already hit (avoid repeating)

- **Shared caches across processes break.** One shard cache per run (launch.py does it); simulator JIT cache must be on local tmpfs, not NFS (clock skew, broken locks); a copied CMake build tree fails (absolute paths).
- **Never `pkill -f <pattern>`** when the pattern appears in your own command line (it killed the shell 3×). Kill by PID. Bash `until` loops must not use `exit` inside the condition.
- **Hub commit rate limit** (HTTP 429) stalled 7 runs for an hour; sync is now a background thread. Keep commits batched.
- **GRU checkpoints on CUDA** saved with safetensors silently lost 7/49 tensors; fixed (pickled checkpoints). Older `-gpu` GRU checkpoints are incomplete (best.safetensors files are fine).
- **Shard cache budget**: `n1-campaign` (22 GB) exceeded the 20 GB recipe cache; N runs use `--cache-gb 60`.
- **Native simulator aborts** kill a whole worker; rerun leftovers with `--ids` one process per flight.
- The renderer writes `optix7cache.db` (198 MB) into the working directory; it is git-ignored (it was once committed by mistake and removed from history).
- Single-seed results misled twice (seed 217 is lucky on D0). Always 3 seeds.
