# Student-teacher work (2026-11-21): index

Two separate student-teacher experiments plus one new local test set. Everything lives in two folders:

| folder | what it is | teacher → student | deliverable | server result |
|---|---|---|---|---|
| [`disp_teacher/`](disp_teacher/README.md) | **Experiment 1:** learned 1 s *displacement* measurement added to B16 | big CNN (~400 M MAC) → half-width student (~100 M MAC) | **B17** `disp_teacher/final/gp_msckf_b17_dtstudent.wasm` | **0.992 m @ 419 M** (B16: 0.782 m @ 17 M). Worse. |
| [`proxy/`](proxy/README.md) | **Experiment 2:** better *startup-velocity* net inside m7 (the best-scoring build) | big net T1 / deployed net lcJ → students S0, S1, S2 | `proxy/final/gp_msckf_m7_s2k3.wasm` (not submitted) | not submitted; ties m7 locally |
| [`proxy/`](proxy/README.md) | **New test set:** simulated flights in unseen scenes, 5 speed bands, ≥ 1200 frames | none | `proxy/results/` | used to check whether local tests match the server |

## The short version
1. **B17 (displacement student) looked good locally but lost on the server.** It was −0.17 m better than B16 on the
   HF server-calibrated folds, and 0.21 m worse on the server.
2. **Why:** scraped per-episode server results (`proxy/server_results.json`). B16's bad server episodes are a
   rigid offset made in the first second, by the learned **startup** net. B17's student only starts at 1.2 s, so it
   cannot undo it. The HF test flights almost never show this failure (3-4 % vs 33 % on the server).
3. **Experiment 2 therefore targeted the startup net.** The students are distilled from the deployed net (S2) or a
   bigger teacher (S1). They improve the net on its own: velocity error on fast starts drops from 0.74 to 0.64 m/s.
   Inside the filter (m7 + S2 + speed-scaled sigma), the result is a **tie with m7**: +0.003 m on held-out HF, and
   −0.027 [−0.118, +0.043] m on 26 new proxy flights.
4. **The new proxy test set reproduces the server's ordering of classical builds** (G worse than B16, m7 worse than
   B16 by ~0.1 m). It does **not** reproduce the server's startup-offset failure, nor B17 losing to B16. So no local
   test set yet predicts the server for learned startup or displacement changes.

## Which file is which
| you want | file |
|---|---|
| B17, the submitted displacement-student build | `disp_teacher/final/gp_msckf_b17_dtstudent.wasm` (sha e4d23d80…) + `b17_solution.c` |
| B17's teacher / student weights | `disp_teacher/final/teacher_t3ft.pt`, `disp_teacher/final/student_s3.pt` |
| the startup-student build (optional submission) | `proxy/final/gp_msckf_m7_s2k3.wasm` (sha 66f9bb25…) + `m7_s2k3_solution.c` |
| the startup student's weights | `proxy/final/startup_student_S2.pt`, `proxy/final/lc_weights_S2.h` (C arrays) |
| server per-episode scores of every submission | `proxy/server_results.json` |
| new proxy flight results, per flight and build | `proxy/results/proxy_rows.json`, `proxy/results/summary_26flights.txt` |
| full lab notebooks (all numbers, caveats, reproduce commands) | `disp_teacher/NOTES.md`, `proxy/NOTES.md` |

## Builds named in the tables
| name | what it is |
|---|---|
| base | original gp_msckf |
| G | `final/submit/gp_msckf_startup_gate.wasm`, startup gate, no learned startup net (server 1.244 m) |
| B16 | tailcap B16 (server 0.782 m @ 17 M) |
| m7 / ms_m7 | B16 source + cheap-fuel defines (`proxy/m7_defines.txt`); **best server score: 0.89 m @ 7.3 M** |
| B17 | B16 + displacement student s3 (server 0.992 m @ 419 M) |
| m7_S2k3 | m7 + startup student S2 + `LC_SPD_K=0.3` (startup sigma grows with speed) |
| m7_spdk3 | m7 + `LC_SPD_K=0.3` only (no student) |

Not in git (regenerable or large): build outputs `*/out/`, training checkpoints `disp_teacher/runs/` and
`proxy/runs_lc/*/best.pt`, flight zips and caches in `C:/Users/alexa/vio_data/`.
