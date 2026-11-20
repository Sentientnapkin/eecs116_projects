# Server result: gp_msckf_startup_gate.wasm (submitted 2026-11-19 23:06 PT)

SHA-256 ac8251454f5cf9564a09b93ae37cf258442f4854b84fffbe2fad20d72582a9b6, label "GP + MSCKF w/ Startup Velo Gate", server current set = 12 episodes.

Mean unaligned ATE **1.244 m** (median 0.568, mean Sim(3) ATE 0.574), peak fuel 20.9 M per frame, 12/12 completed, 0 filled frames.
Previous gp_msckf (submitted 2026-11-19 19:05 PT): 3.22 m. Local pool prediction for the gated build: 0.976 m (planned expectation 1.2-1.3 m).
Claimed score area: 2.71% (previous best 0.386%).

Per-episode ATE (m), old gp_msckf -> gated build:
004c5894 2.94 -> 1.24 | 1c6e73f3 0.272 -> 0.288 | 21494468 2.74 -> 0.73 | 726458d9 0.271 -> 0.121 | 78ed493f 0.723 -> 0.973 | 8950399d 11.3 -> 0.307
89f8c99e 7.97 -> 0.299 | a61ad08d 1.57 -> 0.407 | cd6dc704 8.68 -> 1.09 | dd7a737e 0.585 -> 0.291 | e7aa5aee 0.918 -> **7.70** | f7c2546f 0.742 -> 1.48

The three old tails (11.3, 7.97, 8.68) are fixed. One episode regressed (e7aa5aee: 0.918 -> 7.70, Sim(3) scale 0.57, rotation RMSE 0.235 rad, velocity RMSE 1.5 m/s) and carries 52% of the total error; the other 11 episodes average 0.657 m.
The failure signature (over-extended trajectory, large velocity error) matches the "wrong-direction startup lock-out" mechanism in research/single_model/tails/NOTES.md; the tails patch (flow-based start-velocity override when the travel direction is >75 deg off the camera axis) targets it. Private episodes were not opened or analysed; this is an inference from the aggregate metrics only.
