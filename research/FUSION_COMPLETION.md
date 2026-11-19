# Completion of visual fusion and fuel work, 2026-11-19

All decisions use equal-replay mean **unaligned** position RMSE. No reserved split was accessed. Existing worktrees, artifacts, and unrelated jobs were preserved. The current worktree is `codex/fusion-finish`, starting at `odometry/vel-fusion-deploy` commit `353243fe71fc4e4e5f6af5cee3a05f24260c6b40`.

## Measured whole guests

The public roster is the exact ten 1,200-frame public archives. Campaign is the exact existing 120 development resets, including original and five-second crops, totaling 102,000 frames. All rows below completed every frame with zero filled frames. Full-duration campaign scores average all 120 resets; the continuously scored 30-second and 60-second prefixes are available on **83** and **30** resets respectively. They must not be confused with the historical capped-30-second average over all 120 resets, which includes shorter remaining flights. No estimator is reset at the prefix boundary.

| B-D0 seed 217 guest | Public full / 30s | Campaign full / available30s / available60s | Public / campaign maximum whole-guest fuel |
|---|---:|---:|---:|
| Historical kf_grid, SIMD4x16 | 1.491581 / 0.911189 | 1.642426 / 1.331774 / 2.480263 | 1,451,941,452 / 1,643,004,133 |
| Historical visual direction replacement, SIMD4x16 | 1.360556 / 0.868793 | 1.380669 / 1.110039 / 1.907734 | 1,451,974,473 / 1,643,036,065 |
| Staged6 replay, SIMD8x32 K2 | 1.491599 / 0.911215 | 1.642433 / 1.331784 / 2.480299 | 987,811,616 / 1,130,544,377 |

The historical fusion effect is 16.0% lower campaign full ATE against its matched kf_grid control, with three rather than four campaign resets above 5m. Per-flight regressions remain in the JSON, alongside scene, parent, catalog, start-speed, reset-origin and motion groups. These are actual executable measurements, independently of the Python reproduction problems below.

The staged guest combines the previously validated SIMD CNN kernel with the separately declared delayed visual measurement schedule. Its campaign full mean differs by **0.000006826m** from the historical kf_grid control. Campaign maximum fuel is 31.19% lower than that control, but remains **5.19% above** the submitted ordinary B-D0 guest's previously measured 1,074,756,366 peak. Public alone is insufficient to claim a lower overall peak.

The intermediate SIMD8x32 K2 kf_grid public control, before staging, used 1,238,422,032 maximum fuel at 1.491581m ATE. The 987,811,616 staged public peak therefore includes a 20.24% improvement from scheduling in addition to the CNN kernel change. Kernel-only or MAC estimates were not used.

The actual staged Wasm also passed an independently initialized, physically shortened 600-frame archive replay: timestamps and IMU packets match the original delivered prefix; all emitted pose and twist rows match the corresponding full replay **exactly**, with maximum component difference zero. The first camera timestamp is0.045s and its output pose is exactly the origin with identity rotation. The delayed history replay therefore preserves this measured causal prefix and does not rewrite past outputs. Campaign mean changes are tiny but not bitwise zero:71/120 flights regress by more than1e-8m, with maximum ATE regression0.000345m. No regression is hidden by rounding.

## Source and reproduction findings

The apparently inconsistent frozen N2 public control of 1.1711m already uses the improved kf_grid integration attitude. The roughly 1.780m raw N2 three-seed public score uses the ordinary rolling-gyro attitude. These are different controls; neither number invalidates the other. The former freezes learned image/IMU inputs and velocities while replacing only the integration attitude.

There are two concrete semantic differences between the historical C++ visual port and the current frozen Python reference:

1. `kf_grid.hpp` calls `recoverPose` with an initially empty mask. Python passes the RANSAC mask returned by `findEssentialMat`. OpenCV uses that input mask when selecting the best pose as well as when reporting cheirality support. This can change the selected rotation and whether a visual bias measurement is accepted.
2. Historical C++ translation fusion may use its direction even when the visual rotation's delta-norm acceptance failed. Python's `vis_ok` requires that rotation measurement to have been accepted.

This supersedes the earlier NOTES claim that a RANSAC-mask repair was already present and that all remaining differences were merely KLT floating point. Rebuilding the unmodified tracked kf_grid source for N2 seed218 reproduced historical artifact **089559dbb11ccc4ff5b912930497b725ddc39d2344b794521db9d19cfd849915 byte for byte**. The semantic discrepancy is therefore confirmed for that actual historical artifact.

Also, the historical exporter applies `ODO_KF_GRID` and OpenCV flags only to the Wasm compile. Its automatically produced `host.so` is the ordinary gyro guest. It cannot validate native visual-path parity. This completion explicitly compiled `host_visual.so` with the visual macros and linked OpenCV. Both a separate native4.13 build and a native4.12 build from the exact Wasm OpenCV source were measured.

The staged source was uncommitted on `odometry/fuel`; it has been preserved as `native_odometry_staged/` in this worktree. Its isolated rebuild is **byte-identical** to the previously tested staged guest:

`238f6901e793b8ad88bfee3fa1c322d920302ec1a474904edae0df16ec9b0c51`.

## Separately named parity repair: promising ATE, failed parity gate

Before scoring, `parity-repair-predeclared.json` declared an N2 seed218 paired public smoke. The new flags are `ODO_KFG_RECOVER_RANSAC_MASK` and, for fusion, `ODO_FUSION_REQUIRE_ACCEPTED_ROTATION`. They preserve the original default path and old artifacts. The smoke includes `ODO_KF_GRID_TRACE` for acceptance auditing and is explicitly a **diagnostic artifact**, not an untraced deployment candidate.

| Traced diagnostic guest | Public mean unaligned ATE | Peak whole-guest fuel |
|---|---:|---:|
| Mask-corrected kf_grid | 1.279878m | 1,451,963,652 |
| Mask-corrected + accepted-rotation translation direction | 1.086775m | 1,451,997,144 |

All 20 replays completed their 24,000 frames with zero filling. However, **Python/Wasm numerical parity failed**: accepted-window counts differ on all ten flights and maximum attitude separations range from 8.7 to 27.0 degrees. Aggregate accuracy gains do not establish equivalent computation.

The explicit native visual guest versus actual Wasm on public flight0000 differs by **0.051118m maximum position**, including when both use OpenCV4.12. The native4.13 result is the same to about 1e-13m. Native version mismatch alone does not explain this failure. The same-version native run passes exact first-camera pose and an independently initialized 26-frame reset/prefix replay. These checks are recorded rather than implying that an ordinary host.so passed the new visual path.

The six historical N2 port artifacts were built, including seeds217/218/219 and their exact kf_grid controls. Their full replay batch was stopped by explicit owned PIDs after these parity defects were found. Partial results were preserved. The failure gate prevents advancing to the requested three-seed full candidate qualification; no untraced corrected deployment or broader backend search was launched. Original-dev and proxy raw archives are also unavailable, so their original guardrails remain unmet even if public ATE improves.

## Closed negative/held arms

The six-model frozen visual-direction screen completed before this work: essential replacement improves campaign mean 1.3548→1.2026m, known-rotation replacement 1.3548→1.1677m. Blend, sign-only and local additive-bias arms are reported separately; sign-only is nearly unchanged and essential additive bias regresses to1.6500m. Truth-direction and true-velocity arms remain diagnostics and never enter guests. The old visual-attitude hybrid remains gated by its earlier failed screen.

The fuel screen is also complete: split's Python public1.3760m passes its +0.010m tolerance versus1.3689m reference, but its actual Wasm public1.520532m regresses against1.491581m control; staged4/staged6 without state replay miss the Python public gate. Replaying only arrived IMU packets when the delayed update completes restores the staged6r/staged8r frozen Python mean to1.3689m public and1.3505m campaign at recorded four-decimal precision. The staged6r whole guest was chosen for the targeted campaign completion above. Lower-feature/lower-pyramid arms and RANSAC-cap variants retain their measured negative or diagnostic results; no architecture training was inferred from fake-width profiling builds.

## Reproduction and evidence

From this worktree's `research/`, using `TMPDIR=/dev/shm/sebastian-vio/tmp`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`:

```bash
# Finish only the declared traced parity smoke (cached reports are preserved).
/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python parity_repair_smoke.py
# Audit Python4.12 vs Wasm and explicit visual native guest; see native build logs.
python3 build_visual_native.py
/data/backups/rganapa/Sebastian/venv-cv412/bin/python parity_audit.py
# Independently trim the actual public input and verify emitted staged guest prefix.
/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python staged_causal_check.py
# Recreate all grouped summaries without inference or reserved data.
/data/backups/rganapa/Sebastian/venv-cv412/bin/python summarize_fusion.py
```

The staged build uses `native_odometry_staged/export.py`, the B-D0 seed217 run and original teacher-full sensor manifest, the pinned wasi-sdk and OpenCV build, `--wasm-kernel simd-8x32-k2`, and `ODO_WASM_EXTRA_FLAGS='-DODO_KF_GRID_STAGED -DODO_KF_GRID_REPLAY -DODO_KFG_TRACK_PARTS=2'`. Source hashes, checkpoint and guest hashes, every per-flight result, filled/completed frames, paired regressions and subgroup dependence are in `results/eval/fusion-completion/`. The exact original raw commands and failed partial runs remain under `results/loop/fusion-completion/`; no user data were deleted.

Recommendation: preserve staged6r as an executable fuel improvement for the historical kf_grid path, and preserve visual direction as a useful measured mechanism. Neither is a newly qualified submission. Close the current experiments with the recorded parity failures rather than stacking them or treating traced gains as a final artifact. Resolving the acceptance/backend sensitivity and recovering original-dev/proxy raw guardrails are explicit remaining work for discussion.
