# Agent board

Shared state for the ideator / solver / verifier loop (`/vio-round`). The coordinator (main session) owns this file.
Subagents read it at the start and the coordinator appends their results. Newest entries go at the top of each section.

## Standing facts
- Score = the area gain of our single best submission (log-log max fuel/frame vs mean unaligned ATE). Check with
  `python eecs116_vio/agents/area_gain.py FUEL ATE --refresh`.
- Current best (2026-11-27, after round 1): "GSLV smaller net bit exact kernels" = r1-fuelexact, 0.4444 m @ 2,983,995,
  server id f6b6a277d9108c72, claimed area **2.986** (was 2.848). Server fuel ratio vs the base 0.740 (local est. 0.761).
  Further pricing at 0.4444 m: 2.7M -> 3.03, 2.5M -> 3.07, 2.3M -> 3.11, 2.0M -> 3.17.
- One upload per team per day; the final presentations are 11/30. The user uploads; agents never submit.
- Proxy = twin120 (`agents/eval_twin120.sh`). It is calibrated to ~3% for IMU-only models; it is not yet checked for
  vision models, so for those compare a candidate against the current best's wasm on the same twin120 run.
- Never train on twin flights: run `agents/leak_check.py` on every training set. The "low fuel mlp, stage-3 neighbour
  training" upload scored 8.42 m on the server against ~6.8 m on the proxy, probably because its training set
  included the twins.
- One heavy WSL job at a time (`agents/heavy.sh`, `eval_twin120.sh` take ~/data/.heavy.lock). WSL is capped at 10 GB.
- **The GSLV source is on origin/main only** (9df49dc8): `gen3/preserved_best/{base_sn.c, flags.txt, gslv_s3_snace6e1.wasm}`
  (sha 1a169f28…, the uploaded wasm; a copy is in `agents/baseline/`). Teammate notes: `gen3/agents/anchors/NOTES.md`,
  past evals: `gen3/evals/*.json` (v3val 358 / v1val 120 pools). Read them with `git show origin/main:<path>`.
- **twin120 is contaminated for anything with the learned net**: 103 of its 120 flights are in the net training list
  `gen3/agents/smallnet/lists/trainall4.txt`. For GSLV-family candidates use the paired held-out eval instead:
  `agents/eval_set.sh WASM TAG` (52 flights in `sets/heldout_s3.txt`: not in trainall4, twin120, v3val, v1val or val749)
  then `python agents/paired.py TAG base_gslv`.
- **Nudge noise**: the same build with PIXEL_STD and DETECT_MIN_SCORE moved ±1% (snace6e1_r1/_r2) shifts the v3val mean
  by -3% / -4.5%. A candidate must beat the base by more than that spread, or the "gain" is a random draw.
  Teammate's twin120 run of the base: 0.594 vs 0.444 on the server, so 0.444 may itself have been a lucky draw.

## Verdicts
| date | tag | wasm sha256 | twin120 m | max fuel | est. gain | beats best? | verdict |
|---|---|---|---|---|---|---|---|
| 2026-11-27 | **r2-fuelexact** (`agents/exp/r2-fuelexact/r2-fuelexact.wasm`) | 83c19578� | 0.5936 (= base; bit-identical) | 2.84M twin120 / 2.76M heldout | 3.005-3.018 | yes (thin, +0.02-0.03) | **SUBMIT.** Bit-parity on 163 flights incl. stress; clean rebuild reproduces the sha; r2 < r1 peak on all 163 flights (worst ratio 0.9965 -> 2.988). Change: R2_CHAIN 8-term stack-chained accumulators. Verifier scripts: `exp/r2-fuelexact/verify/`. |
| 2026-11-27 | **r1-fuelexact** (`agents/exp/r1-fuelexact/r1-fuelexact.wasm`) | 4795edf1… | 0.5936 (= base; ATE bit-identical) | 3.05M twin120 / 3.14M heldout (base 4.01M / 4.08M) | 2.973 (2.937 at worst flight ratio) | **yes** | **SUBMIT.** Independent bit-parity on 163 unseen flights (120 twin + 19 fast + 24 black/white/dim stress), rebuild reproduces the sha; server fuel est. 4.03M × 0.761 = 3.07M. Not uploaded yet. Verifier scripts: `exp/r1-fuelexact/verify/`. |
| 2026-11-27 | selftest_s3nb (`submissions/cheap_mlp16_s3nb.wasm`, already uploaded) | 6f5636cb… | 6.994 | 2,261 | 0.40 | no | Pipeline self-test. Server says 8.42 m; twin120 says 6.99 m because the model was trained with twins included. A leak check would have stopped it. |

## Experiments
<!-- tag, idea, owner, status, directory -->
- **r2-fuelexact** (2026-11-27, round 2 "more bit-exact fuel cuts"). Same rules as r1, starting from r1-fuelexact.
  Targets from the r1 profile of the peak frames: KLT / detection / pyramid (about 19%, integer work SIMD-able exactly),
  line gates 10.5%, and peak-frame structure (MSCKF k=34 + 3 line gates). Same solver resumed. `agents/exp/r2-fuelexact/`. Done: R2_CHAIN only (image-side cuts not done, cut for budget).
- **r1-fuelexact** (2026-11-27, user's direction: "push the fuel down while keeping the accuracy the same"). Bit-exact
  fuel cuts to the GSLV build (identical poses, fewer instructions), peak frames first. vio-solver done, verifier running.
  Solver claims: base rebuilt locally (sha 1a169f28 matches); blocked SIMD kernels in update()/gates, H zero-column
  skip, IEEE-safe flags; bit-identical on 52/52 heldout flights; peak 4.08M -> 3.14M (-23%), median per-flight max
  3.53M -> 2.73M; est. server 0.4444 @ 3.10M, gain 2.968. sha 4795edf1…; build via the folder's mk.sh/bld.sh (CMake drops
  repeated -mllvm tokens otherwise).
  `agents/exp/r1-fuelexact/`. Why bit-exact: at constant fuel cuts the allowed error increase is tiny (2.0M -> 3.5%,
  1.5M -> 6%, 1.0M -> 11%), smaller than the ±4.5% nudge noise; governor cuts already lost (snace6g27/g30 3-rep v3val
  0.628/0.623 vs 0.562).
  Held-out baseline: base_gslv on heldout_s3 = 0.6220 m, peak 4,077,458 (`results/base_gslv__heldout_s3.json`).

## Ideas
<!-- ranked; the ideator appends, the coordinator marks picked / rejected with a reason -->
Round 1 (2026-11-27, focus "beat 0.44 m at 4M"). Pricing: 0.40 m @ 4.03M -> 3.76, 0.35 -> 4.92, 0.44 @ 2M -> 3.26.
1. ~~Swap in A2_L / A2_Lkd net weights~~ -> Rejected (already tested, see below).
2. S-size small net (S_kd120, direct 0.3175 vs 0.350) in int16 SIMD. **Weak: already tested in-filter** at 3.0M,
   EDGE=0 config (smallnet NOTES §4, s3_S120_e0b30): raw 0.927 vs A2_kd 0.931, single run, within nudge noise.
   Not tested in the current snace6e1 (EDGE=1, ACE) config, but the better direct error did not carry into the filter.
3. Rotation about the origin: keep the first-frame pose as a fixed clone and report relative to its refined estimate.
   Cheap offline test: best 3-DOF rotation about the origin on local trajectories; kill if ATE drops < 5%.
   Speculative (yaw-only fix gave just 0.02 m).
4. Treat uploads as draws: on a day with no verified candidate, upload a nudge (snace6e1_r2: PIXEL_STD=1.485
   DETECT_MIN_SCORE=990). Only the best upload counts, so a nudge can't lower the score.
5. Wide overnight net (`research/overnight_20261127/gpu/seed6_wide`, oracle 0.568 -> 0.398). Needs a new int16
   exporter, probably > 1 day. Too big for the time left unless the exporter already exists.
6. Cap the per-frame peak at ~3.45M (the 4.03M max comes from one episode, d6337f). +0.07 alone; add to another candidate.
Server per-episode breakdown of the base: rooms 0.316, warehouse 0.480, forest 0.666; the top 5 episodes carry 37%;
rotation RMSE 4-4.7° on the 3 worst; FoV <= 83° episodes average 0.58 vs 0.37; Sim3 0.25, scale 0.94-1.03.

## Rejected (don't retry without new evidence)
- **A2_L / A2_Lkd net-weight swap** (round 1). The teammate already ran it, 3 reps each on v3val (258 scored flights):
  base 3-rep mean 0.5517, A2_L 0.5653 (worse), A2_Lkd 0.5514 (same); v1val also same or worse
  (`gen3/evals/swL_e1_*`). The ideator missed these files. The g27 variants are 0.06-0.08 m worse.