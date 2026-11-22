# disp_teacher: Experiment 1, displacement teacher → student (B17)

Adds a learned **1 s relative-displacement measurement** to B16. A CNN sees 3 gyro-derotated frames, gravity and the
IMU preintegration, and predicts the metric displacement with a per-axis uncertainty. That prediction is fused as an
EKF update every clone. A large **teacher** is trained first; a 4× cheaper **student** is distilled from it and is
the one that ships.

**Result:** B17 = B16 + student s3. It was −0.173 m better than B16 on HF folds 2-3, but **0.992 m on the server (B16
0.782 m)**. The server's failures happen at startup (< 1 s), before this measurement starts. Details: `NOTES.md`,
and `../proxy/NOTES.md` for the diagnosis. Overview of all student-teacher work: `../STUDENT_TEACHER.md`.

## Pipeline (in order)
| step | file | role |
|---|---|---|
| 1 data | `build_cache.py` | teacher-data shards (HF) → per-flight training cache (617 flights) |
| 1 data | `dump_eps.py` | server-calibrated episodes → compact npz (truth + gray frames) |
| 1 data | `server_cache.py` | server-calibrated folds 0-1 → extra fine-tuning cache entries |
| 2 model | `model.py` | **teacher and student architectures** (`model.teacher()`, `model.student()`) and loss |
| 3 teacher | `train.py` | **train the teacher** (t2 from scratch; t3ft = fine-tune on server folds 0-1) |
| 4 student | `distill.py` | **distil teacher → student** (Laplace NLL + KD term + feature hint; s1 → s2 → s3) |
| 5 check | `domain_check.py` | offline 1 s displacement error vs B16's own, on server flights |
| 6 to C | `export_c.py` | fold BatchNorm, write weights as C arrays (`dt_weights.h`) |
| 6 to C | `dt_core.h` | C inference + MSCKF displacement update, inlined into the B16 source |
| 6 to C | `make_dt.py`, `build.sh` | splice + build the wasm (wasi-sdk 34, B16 flags) |
| 7 parity | `parity.py`, `parity_main.c` | C-vs-PyTorch output check (1e-6) |
| 8 eval | `evalrun.py` | score a wasm on the HF server-calibrated set (slices search/val/f23/f34) |
| 8 eval | `sweep.sh` | export + build + eval a list of variants |
| 9 ship | `preflight.py` | reduced preflight: check, zero imports, determinism |

## Outputs
* `final/`: B17 deliverable: `gp_msckf_b17_dtstudent.wasm`, `b17_solution.c`, `defines.txt`
  (`DT_ON=1 DT_EVERY=1 DT_INFL=3.0`), `teacher_t3ft.pt`, `student_s3.pt`, `preflight.json`, `SHA256SUMS`.
* `runs_*.log`: training logs of each teacher (t1, t2, t3ft) and student (s1, s2, s3).
* Not committed: `runs/` (checkpoints, ~110 MB), `out/` (builds and eval outputs, ~1 GB).
