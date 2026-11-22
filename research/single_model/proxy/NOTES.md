# proxy: a local test set that behaves like the server, and a cheap startup student checked on it

Started 2026-11-21 after B17 (B16 + displacement student) scored 0.992 m on the server against B16's 0.782 m, although
the HF server-calibrated folds 2-3 had predicted 0.456 vs 0.629.

## Server data (scraped from viobench.rl.tools, `server_results.json`)
Per-episode unaligned and Sim(3) ATE of every submission on the current 12-episode set. Local wasm files found for:
base gp_msckf, G, B16 (= tailcap B16), B17, ms_m7 (best score: 0.89 m @ 7.3 M; ~/ws_m/ms_m7.wasm = b16s.c + bm3.sh m7
defines, rebuilt here bit-identically from `b16s_snapshot.c` + `m7_defines.txt`), low-fuel try (vio_fp_ds2),
low-fuel experiment (ms_c2), camera-direction build (vio_v2).

## Why the HF set misled (calib.py on the 56 HF folds 2-3 flights)
| pattern | server | HF |
|---|---|---|
| episodes where B16 is > 0.5 m worse than G | 33 % | 3-4 % |
| B16 episodes > 2 m | 17 % | 6-7 % |
| P(12-flight draw has B17 worse than B16) | (server: yes) | 0.04 |
B16's bad server episodes (004c, 2149, cd6d, 8950) have small Sim(3) error and large unaligned error: a rigid offset
made early. B17 (metric 1 s displacement updates from 1.2 s on) improved their Sim(3) but not their unaligned error, so
the offset is made in the first ~1 s, i.e. at startup. G (no learned startup net) is better than every lcJ build
(B16, ms_m7, B17) on exactly those episodes.

Deployed startup net lcJ, direct velocity error at its injection anchor on HF flights (lc_local.py eval):
speed <0.3 / 0.3-1 / 1-1.5 / 1.5-2.5 / >2.5 m/s: 0.08 / 0.16 / 0.24 / 0.37 / 0.68 m/s, z-rms 0.97 / 1.20 / 1.27 / 1.47 / 1.74
(z-rms 1 = honest sigma): wrong AND over-confident on fast starts.

## New proxy flights (gen_proxy.py, WSL simulator, llvmpipe)
Unseen scenes only (none in any training record or the HF set): 68 ProcTHOR + 28 HSSD-val houses (some HSSD houses
abort llvmpipe: buffer > maxStorageBufferBindingSize; those scenes are skipped automatically). 5 ProcTHOR scenes
appear in lcJ's (lab) training rosters (ProcTHOR-Train-1, 8, 9, 176, 179).
Speeds: D default planner (0.45-0.8 m/s cruise) / M 1.5-2.5 / K 3-4.5 (HF) / K2 4-6 (HF) / K3 6-8; lengths 60/75/90 s
(always >= the server's 1200 frames); half start mid-flight (3-30 s cropped). Scene split dev/test (proxy_split.json).

Throughput limit: llvmpipe renders at the 200 Hz motion-blur rate; the whole machine manages ~50-180 output frames/min
(shared with evaluations and training), i.e. ~1.5-2 h per 60-75 s flight per worker and only a handful of flights per
hour. GPU rendering (hyperlux OPTIX backend; WSL has libnvoptix) needs a full CUDA toolkit with nvcc (pip wheels ship
only ptxas): not installed (multi-GB download, not done without the user's OK). Most HSSD-val houses abort llvmpipe.

## Fingerprint matching (fingerprint.py) does not rescue HF
Matching each server episode to the HF flights whose ATE under 5 server-scored builds is closest (B17 left out) still
predicts B17 better than B16 (-0.10..-0.17 m for k=2..5): HF folds 2-3 contain no flight where B17 is worse.
By HF scene group (seen/dev/clean) no group shows the server pattern either.

## Startup students (lc_local.py; cache prep_lc_local.py = learned_c/prep2 pipeline on local zips)
Trained on HF folds 0-2 (102 flights, scene split for checkpoint choice); tested on HF folds 3-4 (52 flights, never used).
Direct velocity error at the injection anchor (all anchors / first anchor), m/s:
| net | all | 1.5-2.5 m/s | >2.5 m/s | first anchor |
|---|---|---|---|---|
| lcJ (deployed, 595 lab flights) | 0.235 | 0.418 | 0.744 | 0.126 |
| T1 teacher (res 128, width 2, from scratch, val only) | 0.242 (val) | | | |
| S0 fine-tune lcJ, NLL only | 0.239 | 0.401 | 0.613 | 0.138 |
| S1 fine-tune lcJ, KD from T1 | 0.240 | 0.405 | 0.588 | 0.135 |
| S2 fine-tune lcJ, KD from lcJ (self-distillation) | 0.233 | 0.395 | 0.640 | 0.126 |
T1 overfits 102 flights (z-rms 2.3); KD from it does not help. S2 keeps lcJ's accuracy and improves fast starts.
In-filter on m7 (HF folds 3-4, 52 flights, paired scene bootstrap vs m7 0.575):
m7+S2 +0.054 [-0.057,+0.235] | m7+S2+LC_SPD_K=0.3 +0.003 [-0.060,+0.080] (max 1.81 vs 2.46) | m7+LC_SPD_K=0.3 +0.075 [-0.020,+0.256].
On all 144 HF visible flights m7+LC_SPD_K=0.3: -0.028 [-0.091,+0.024]. Nothing measurably better than m7.

## Candidate (final/): m7 + startup student S2 + speed-calibrated sigma
`final/gp_msckf_m7_s2k3.wasm` sha256 66f9bb25ed41e1fd94e48706876dd56a7233265bb71a6b3c4aa79d551f5dcdf7 (538 KB) =
b16s_snapshot.c with S2 weights spliced (splice_lc.py) + m7 defines + LC_SPD_K=0.3. Reduced preflight: check ok, zero
imports, deterministic (lab causality/reset not run; only the net weights and one sigma factor differ from m7).
Peak fuel 7.0 M on HF folds 3-4 (m7 7.7 M there; server m7 7.3 M). Held-out HF in-filter: tie with m7 (+0.003 [-0.060,+0.080]).

## Proxy results (accumulating; px_sync_eval.sh scores b16 G m7 m7_S2k3 m7_spdk3 b17 on every new flight)
Latest table: work/evals/px_loop_last.txt; per-build rows work/evals/px_<build>/rows.json; calib.py-style checks need
>= ~20 flights to mean anything (the server's own 12 are already noisy: one episode moved B17's mean by 0.18 m).
Stop the generators: `wsl -d Ubuntu-24.04 -- bash .../proxy/stop_roster.sh roster.json` (and roster2.json).

### Proxy, 17 flights (2026-11-21 12:47; speeds M 3 / K 4 / K2 5 / K3 5, no D flight finished yet; 7 static-start, 10 mid-start)
mean unaligned ATE: b16 0.275 | G 0.543 | m7 0.372 | m7_S2k3 0.412 | m7_spdk3 0.388 | b17 0.256 (peak fuel m7 6.7 M)
paired (mean diff, 90 % bootstrap):  G-b16 +0.269 [+0.118,+0.444] (server +0.46)  m7-b16 +0.098 [+0.048,+0.145] (server +0.11)
b17-b16 -0.018 [-0.048,+0.009] (server +0.21: NOT reproduced)  m7_S2k3-m7 +0.040 [-0.000,+0.083]  m7_spdk3-m7 +0.016 [-0.022,+0.070]
Episodes with b16 > 0.5 m worse than G: 0/17 (server 4/12). Proxy errors are ~1/3 of the server's; the server's large
startup-offset episodes do not occur here either, so the proxy reproduces the classical orderings but not the B17 loss.
On the proxy the startup student (S2) is slightly worse than lcJ inside m7; it should not be expected to beat m7.

### Proxy, 26 flights (2026-11-21 21:20; speeds M 6 / K 7 / rest K2-K3)
mean: b16 0.366 | G 0.876 | m7 0.498 | m7_S2k3 0.471 | m7_spdk3 0.466 | b17 0.320 (peak fuel m7 / m7_S2k3 6.7 M)
paired: m7_S2k3-m7 -0.027 [-0.118,+0.043] | m7_spdk3-m7 -0.032 [-0.077,+0.015] | b17-b16 -0.046 [-0.113,+0.006]
G-b16 +0.510 [+0.224,+0.852] | m7-b16 +0.132 [+0.086,+0.181]; b16 > 0.5 m worse than G on 0/26 (server 4/12).
Verdict: the startup student ties m7 (slightly ahead, not significant); the proxy still does not show the server's
startup-offset failure mode, so it cannot confirm a fix for it. Per-flight numbers: results/proxy_rows.json.
