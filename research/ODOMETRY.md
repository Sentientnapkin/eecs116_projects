# Learned odometry: guide and current verdict

The model: a small CNN (trained end to end) embeds gyro-derotated image histories; with IMU features
it feeds a GRU or selective-SSM head that predicts body-frame velocity each frame, integrated through
the gyro attitude. This was called the "teacher" pipeline until 2026-11-18; Hub repo and manifest
names (`viobench-teacher-*`, `teacher-full`, ...) keep their old names so pinned revisions stay valid.

Work from this directory with `./odometry_env.sh <script> …` (Mac: base Python with PyTorch/MPS
plus the course benchmark packages). Generated data and results live in ignored directories
(`data/`, `results/`, `loop/` logs). Private Hugging Face repos:
`SentientNapkin/viobench-teacher-data` (datasets) and `SentientNapkin/viobench-teacher-lab` (runs).

## Pieces

| File | Role |
| --- | --- |
| `odometry_ledger.py` | Audited ledger of every raw parent flight: checksum, scene/seed/domain/tier, measured duration and frame rate, calibration, realized motion, consistency checks, split by scene. |
| `odometry_pool.py` | Shard preparation (`prepare`), generated-flight pool worker, and `expand` (bounded, Hub-verified preparation of ledger parents). |
| `odometry_store.py` | Hub layout: content-addressed `shards/<sha256>.npz` plus immutable `manifests/<name>.json`; streaming cache; `push`, `snapshot`, `compose`. |
| `odometry_data.py` | Dataset preparation, motion labels, `WindowPlan` (original and balanced samplers with exposure accounting). |
| `odometry_models.py` | CNN + local correlation encoder, GRU / selective SSM / EMA heads, optional attitude input, blind ablation. |
| `odometry_train.py` | Training with Accelerate checkpoints, weight EMA, cosine schedule, provenance snapshot, per-epoch Hub sync. |
| `odometry_eval.py` | Full-trajectory replays: trained runs, deployed guest models, zero output; per-flight, regime and scene-paired results. |
| `ekf_experiment.py` | CPU-only, three-seed fixed-covariance comparison. Selects settings on native training crops and freezes them before replaying development suites. |
| `launch.py` + `configs/experiments.json` | Named experiment definitions, decision gates, budgets; `launch.py <names>` starts them. |
| `native_campaign.py` + `configs/native_campaign.json` | Split-safe native flight campaign: roster, simulator workers (raw 640×480 archives, failure-only gates, truth-integration check), shard preparation and publishing. Reserved test split is never prepared. |
| `test_odometry.py` | Regressions: leakage, sampling determinism/exposure, loss horizons, causality, chunked streaming. |

## Commands

```bash
./odometry_env.sh odometry_ledger.py --source <research dir with data/> --pool data/gen-spool/gen-pool-v1.json
./odometry_env.sh odometry_pool.py expand --select proxy-train --worker 0 --workers 2
./odometry_env.sh odometry_store.py compose --name d1-expanded-tiers --base teacher-full \
    --records data/expand/proxy-train-0.json data/expand/proxy-train-1.json --expect-parents 232
./odometry_env.sh launch.py D0-ssm D1-ssm D2-ssm          # add --seed 218 for paired seeds
./odometry_env.sh odometry_eval.py --runs results/loop/D0-ssm results/loop/D1-ssm results/loop/D2-ssm \
    --deployed ema ssm --control D0-ssm --output results/eval/d-series [--set proxy-val]
./odometry_env.sh test_odometry.py
```

Off the Mac (e.g. the GPU box) run the same scripts with plain `python`. `launch.py --gpu N --tag gpu`
pins consecutive runs to consecutive devices, gives each run its own shard cache, and keeps
run names distinct on the Hub. Evaluation there needs no raw flights except for `--deployed`:

```bash
python odometry_eval.py --runs results/loop/D0-ssm-gpu results/loop/D2-ssm-gpu --control D0-ssm-gpu \
    --output results/eval/d-series --plots                       # dev: 14 replays, 6 scenes
python odometry_eval.py ... --set proxy-val --max-seconds 30     # holdout criterion: 68 replays, 12 scenes, first 30 s
python odometry_eval.py ... --set proxy-val                      # 90 s long-horizon diagnostic
```

Native campaign (GPU box; simulator in `/data/backups/rganapa/Sebastian/venv-sim`, see `gen/env.sh`):

```bash
N=40 /data/backups/rganapa/Sebastian/gen/run_campaign.sh          # generation workers (resume-safe)
python native_campaign.py prepare --split train dev --worker 0 --workers 24   # training env
python native_campaign.py publish --split train                  # then compose onto teacher-full-labeled
python odometry_eval.py ... --set campaign-dev                    # ProcTHOR and HSSD houses reported separately
```

`--set proxy-val` reads `data/expand/proxy-proxy_validation-0.json`; it is on the data repo as
`manifests/proxy-validation-records.json` (copy it to that path).

For the fixed-covariance B-D0 comparison, provide the three best-checkpoint run directories
in seed order (217, 218, 219). The driver reads prepared local shards and writes the frozen
settings and per-replay scores to the output directory.

```bash
runroot=/path/to/research/results/loop
runs=("$runroot/B-D0-ssm-x3-gpu" "$runroot/B-D0-ssm-x3-s218-gpu" "$runroot/B-D0-ssm-x3-s219-gpu")
for stage in tune dev proxy-val campaign-dev; do
    CUDA_VISIBLE_DEVICES="" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
        python ekf_experiment.py "$stage" --runs "${runs[@]}" --output results/loop/ekf-fixed
done
```

For an individual exploratory replay, `odometry_eval.py --ekf --ekf-params '<JSON object>'`
adds a fused result alongside direct integration. The filter uses the current accelerometer
packet and model velocity, with an optional body-frame accelerometer bias state.

To restore a run elsewhere: `odometry_hub.py pull --run <name>` brings its checkpoints,
`config.json`, and `source/` (a copy of the exact research sources and configs). Its
`manifest.json` records the git HEAD, uncommitted files, the data repo commit, packages and
the command line; `--resume` continues from a pulled checkpoint.

## Data identities

| Manifest | Contents | Notes |
| --- | --- | --- |
| `teacher-full` | Restricted control: 48 proxy base + 12 native + 1 native yaw parents, crops 0/5 s (122 shards); 7 native development parents (14 replays, 6 scenes). | The exact old teacher roster. Re-preparing a parent reproduces its shards bit for bit. |
| `d1-expanded-tiers` | `teacher-full` + all other 232 eligible proxy training parents (96 mid, 88 agile, 48 base; 586 shards). Same development roster. | Adds motion coverage, not scenes: the same 36 scenes. |
| `proxy-validation-records` | 136 records (68 parents, crops 0/5 s, 12 scenes) of the proxy-validation holdout; 90 s flights. | Recovered from the upload commits; two parents (scene 155, seed 906, `-00`/`-01`) have identical truth and are flagged `ambiguous_parent`. |
| `teacher-v2/v3/v4` | `teacher-full` + generated native pool snapshots. | Pool includes scenes 150–161 (proxy validation), so proxy validation is not a clean holdout for these. |

Scene policy (`odometry_ledger.py`): development 166–171; final test 162–165, 172–175;
confirmation 176–179 (quarantined: scored before); proxy validation 150–161; everything else
train. The ledger found 380 eligible raw parents, no duplicates and no scene in two splits.
Backward frames by training tier: base 0, mid 1,483 (24 scenes), agile 5,502 (22 scenes);
the restricted roster has 75 (one native yaw flight). Every benchmark-regime native flight
(development, final test, confirmation) has zero backward frames.

## Experiment record

See `loop/NOTES.md` for the chronological log and `results/eval/` for full replays.

## Current verdict (2026-11-18 evening, GPU box)

**Metric: mean unaligned ATE (m, log scale) only.** Sim(3)-aligned ATE is not used anywhere (removed
from training logs, evaluation and plots on 2026-11-18); earlier notes that quote it are historical.

- **Seed noise dominates single-run comparisons.** Identical D0-ssm runs differ by 0.29 m on dev
  (1.152 / 1.439 / 1.420) and 0.10 m on the 30 s holdout. The scene-paired bootstrap covers flight
  sampling only, so decisions use three-seed means. The morning's "D0 beats ssm-recipe and the
  deployed EMA" was one lucky seed.
- **Expanded proxy tiers (D1/D2): not adopted.** With three seeds, D2 ties D0 on ordinary native
  flights (1.201 vs 1.210) and on the 30 s holdout (1.347 vs 1.359), but loses the one native
  backward/lateral flight (backward sign 0.00 in all seeds). Backward motion learned from proxy
  renders does not transfer to native rendering.
- **Architecture is not the bottleneck at this data size.** 2/4-layer SSM, residual GRU and the
  GRU→SSM hybrid all land at 1.31–1.34 on the 30 s holdout, inside the control's seed range.
  Residual GRU is much better than the plain stacked GRU. 12 s context at matched scored frames
  hurts (fewer updates). Zeroing direct IMU features costs about 5%.
- **Training longer helps.** The same seed at 3× updates reaches 1.06 dev (vs 1.15 at 12 epochs);
  B-series seeds are running.
- **Native data is the open lever:** the native campaign (`native_campaign.py`; 600 train / 60 dev /
  88 reserved-test simulated flights, 25% independent yaw) feeds the declared N1-ssm-x3 vs
  B-D0-ssm-x3 comparison.
- Rotation floor: true velocity through our attitude scores 0.41 m (dev) and 0.35 m (holdout, 30 s);
  current models are at 1.1–1.4, so velocity remains the main error source.
- Nothing is ready for distillation or deployment yet; no model has a three-seed full-replay
  gain over the submitted EMA (dev 1.291, ordinary 1.055).
