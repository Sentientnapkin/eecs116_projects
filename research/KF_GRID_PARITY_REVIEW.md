# kf_grid port correctness and provenance review

Read-only peer review, 2026-11-19. This report records source inspection; it changes no estimator, thresholds, inference artifact or historical scores. Historical Python/native/Wasm equivalence is **not established** for the visual attitude path.

## Findings

**The historical `host.so` does not implement the visual attitude path.** At commit `b37831f`, `research/native_odometry/export.py` lines 117–121 compile `host.so` using the ordinary flags. Only the Wasm compile at lines 126–130 receives `opencv_flags`, which defines `ODO_KF_GRID` at line 29; `ODO_WASM_EXTRA_FLAGS` are also Wasm-only. Therefore a `host.so` next to a visual candidate is an ordinary learned-guest host library. Ordinary velocity/native parity does not validate kf_grid native/Wasm parity. A visual native comparison needs an explicitly built visual host and declared OpenCV version, plus matched causal inputs and accepted-window traces.

**The historical C++ implementation discards the RANSAC inlier mask before pose recovery.** At `b37831f`, `research/native_odometry/kf_grid.hpp` lines 163–168 call `findEssentialMat(..., mask)` but pass an empty `cheiral` to `recoverPose`. The same behavior remains at `353243f`, lines 212–217. Both comments claim this matches the reference. In contrast, the Python reference at `b059d44`, `research/attitude_bias.py` lines 83–88 explicitly calls `recoverPose(..., mask=mask)`.

This is a material estimator difference, not just a different returned point mask. The actual pinned runtime OpenCV 4.12 implementation, `modules/calib3d/src/five-point.cpp` lines 680–703, intersects each of the four candidate cheirality masks with the supplied input mask **before** counting and choosing the winning rotation/translation. Omitting the mask can change selected pose, inlier count and the downstream acceptance gate. A no-mask policy could be an explicitly declared different estimator, but it does not implement the documented Python transcription; no independent predeclaration or justification for that difference was found. Relative to the declared transcription, this is a port correctness bug.

**Historical artifact provenance is now identified, but the claimed fix is unsupported.** I verified historical N2 seed 218 artifact SHA-256 `089559dbb11ccc4ff5b912930497b725ddc39d2344b794521db9d19cfd849915` at `baselines/candidates/n2-218-ungated/odometry.wasm`. Agent `fusion_finish` separately reported a byte-identical rebuild of that historical control from `353243f`. That reproduction is evidence supplied by the fusion owner, not a rebuild performed during this review. It ties the measured historical artifact to the unmasked path.

The entry at `023198d`, `research/loop/NOTES.md` lines 174–177 says the RANSAC-mask port bug was fixed and attributes the remaining Python/Wasm differences to KLT floating point. Those assertions are superseded by this review: the tracked historical C++ still omits the mask and the historical artifact has been reproduced from that source. KLT/backend sensitivity may remain after this discrepancy is corrected, but cannot be isolated as the sole explanation from the old evidence. Similar aggregate ATE after a three-sigma innovation gate is not per-frame or accepted-window parity.

**The reviewed static-window implementation is causal.** Python `attitude_bias.py` lines 120–135 waits until the window has arrived, uses packets preceding the current frame to decide a bias, then re-integrates historical IMU into the current internal attitude. Earlier entries already stored in `out` remain unchanged. C++ `kf_grid.hpp` lines 53–77 re-integrates only the saved packets, called at lines 186–193 after the window threshold is reached; previously emitted guest states are not rewritten. This source inspection found no future-data use in that path. It does not certify all deployments or replace an executable causal-prefix check.

## Source references and hashes

Historical files are preserved in their original worktrees. Line numbers above refer to those exact commits; current fixes must be separately named.

| Commit / file | SHA-256 |
|---|---|
| `b37831f:research/native_odometry/kf_grid.hpp` | `45b682b095e72c5d0b4be880e7c59d3f778729df03459688fb46149dfbe8651f` |
| `353243f:research/native_odometry/kf_grid.hpp` | `5315d249f9998ecf15d2a6b8d229d3f6f1f29b81c869107bce3e8ebf16f79ca5` |
| `b37831f:research/native_odometry/export.py` | `ab34b89e9b7ae197bc14f4e6e03f33c681c861b8f6cf4bc5da3171d8393c7601` |
| `b059d44:research/attitude_bias.py` | `7baa9d2e7ca5988050e614ecff17058fa2ae5f8346c966ff5b94700897a6dd5b` |
| OpenCV 4.12 runtime `modules/calib3d/src/five-point.cpp` | `7c2ed215ee7a4d1ad6fa950f9d67e185587c41b1051ca61d4a6871f6a0f8c7bb` |

Local evidence:

- [Historical host build flags](/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/deploy-kfgrid/research/native_odometry/export.py:117)
- [Historical C++ pose recovery](/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/deploy-kfgrid/research/native_odometry/kf_grid.hpp:163)
- [Fusion C++ pose recovery](/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/vel-fusion-deploy/research/native_odometry/kf_grid.hpp:212)
- [Python pose recovery](/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/openvins-diag/research/attitude_bias.py:83)
- [Pinned OpenCV mask semantics](/dev/shm/sebastian-vio/viobench/viobench/solution/build/runtime/src/opencv/modules/calib3d/src/five-point.cpp:680)
- [Superseded historical note](/data/backups/rganapa/Sebastian/eecs116_projects/.worktrees/provided-openvins/research/loop/NOTES.md:174)

The measured historical Wasm scores remain valid measurements of their exact historical binaries; their interpretation as a faithful Python port is what changes. Preserve those controls and label corrected-mask builds separately. The fusion owner is handling fixes and executable parity checks; this review introduced no new inference or experiments.
