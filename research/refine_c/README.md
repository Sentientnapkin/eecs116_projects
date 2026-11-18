# C inertial refinement

`odometry_refine_step` takes the odometry head's context and initial body velocity, the
current 51-feature IMU vector, and the row-major body-to-world rotation. Zero the
`OdometryRefineState` at the start of each replay. The state carries the previous
refined world velocity across frames. Within a frame the same learned update is
applied for the iteration count stored in the exported weights. Each update receives
the difference between the current velocity estimate and the IMU-propagated estimate.
When the IMU packet is missing, propagation uses constant world velocity.

From `research/`, export an inertial-only checkpoint and include the generated header
from your C or C++ caller. Compile `refine.c` as C99 and link the math library.

```sh
python -m refine_c.export_weights "$RUN" /path/to/weights.h
python -m refine_c.check "$RUN" "$DEV_SHARD" --wasi-cc "$WASI_SDK/bin/clang"
```

The parity command compares the native C and WASI kernels with PyTorch on a development
shard. Wasmtime fuel covers the refinement step, including its bridge call. The caller
supplies the visual encoder and odometry head. The optional correlation path runs in
PyTorch, with local bilinear offset lookup and average pooling over the feature grid.

In PyTorch, refinement is enabled with `model.refine_iters` greater than zero. The
C-supported configuration uses `model.refine_signals=["inertial"]`. The usual trainer
supervises all iterations. `odometry_refine.py` fits only the refiner on frozen B-D0
head outputs and uses the paired pilot declared in `configs/experiments.json`.
