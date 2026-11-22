# proxy: server-like local test set + Experiment 2, startup-velocity teacher → student

Made after B17 lost on the server. It has three parts. Overview of all student-teacher work: `../STUDENT_TEACHER.md`.
Full numbers and caveats: `NOTES.md`.

## Part A: what does the server actually measure?
| file | role |
|---|---|
| `server_results.json` | per-episode unaligned + Sim(3) ATE of every submission, scraped from viobench.rl.tools |
| `calib.py` | does a local set behave like the server? Compares builds scored on both (paired diffs, P(sign)) |
| `fingerprint.py` | match each server episode to local flights with similar per-build errors (did not help) |
| `errcurve.py` | error at 3/5/10 s from estimate.tum: shows the error is made at startup |

## Part B: new proxy flights (the new tests)
Simulated in WSL (hyperdrone + viobench), unseen ProcTHOR/HSSD-val scenes, speeds D/M/K/K2/K3 (0.5 to 8 m/s),
60-90 s (≥ the server's 1200 frames), half start mid-flight.
| file | role |
|---|---|
| `gen_proxy.py` | roster (scene/speed/length plan) + generator (one crash-tolerant child per flight) |
| `roster.json`, `roster2.json` | test-flight plans (150 + 50); `proxy_split.json` dev/test scene split |
| `roster_train.json` | planned startup-student training flights (stopped: too slow on CPU rendering) |
| `launch_gen*.sh`, `launch_train_gen.sh`, `stop_roster.sh`, `rate.sh`, `wsl_names.sh`, `hssd_val.json` | run/stop/monitor generators in WSL |
| `dump_dir.py` | flight zips → npz |
| `evalproxy.py` | score a wasm on the proxy flights; breaks down by speed and start type |
| `px_sync_eval.sh` | copy new flights out of WSL and score all comparison builds |
| `results/` | `proxy_rows.json` (per flight × build), `summary_26flights.txt`, `summary_17flights.txt` |

**Result:** the proxy reproduces the server's ordering for classical builds, but not its startup-offset failures
(0/26 flights vs 4/12 server episodes), nor B17 losing to B16.

## Part C: startup-velocity teacher → student (inside m7)
The learned startup net (lcJ, 1.8 M MAC, frames 0 and 5 → initial velocity + sigma) is wrong and overconfident at speed.
| file | role |
|---|---|
| `prep_lc_local.py` | build the startup-net training cache from flight zips (same C-matched pipeline as `learned_c/prep2.py`) |
| `lc_local.py` | **teacher / student training and eval**: `eval` (direct velocity error), `teacher` (T1, big net), `student` (S0 NLL fine-tune, S1 KD from T1, S2 KD from lcJ), `export` (C header) |
| `splice_lc.py` | put new startup-net weights into the B16-family C source |
| `b16s_snapshot.c` | read-only copy of the B16/m7 source (has `#ifndef` guards, so defines can be overridden) |
| `m7_defines.txt` | the defines that make B16 into m7 (best server score) |
| `bv.sh` | build `out/NAME/solution.wasm` from a source + defines |
| `runs_lc/*/result.json`, `runs_lc_*.log` | per-run metrics and training logs (T1, S0, S1, S2) |

Students on held-out HF folds 3-4, velocity error (all / > 2.5 m/s), m/s: lcJ 0.235 / 0.744, S0 0.239 / 0.613,
S1 0.240 / 0.588, **S2 0.233 / 0.640**. In-filter (m7 + S2 + `LC_SPD_K=0.3`): ties m7.

## Deliverable: `final/`
`gp_msckf_m7_s2k3.wasm` (sha256 66f9bb25…, 538 KB, peak fuel ~7 M) = `m7_s2k3_solution.c`, with S2 weights
(`lc_weights_S2.h`, `startup_student_S2.pt`) and `defines.txt`. `preflight.json` passed: check ok, no imports,
deterministic. **Not submitted.** Expect about the same score as m7.
