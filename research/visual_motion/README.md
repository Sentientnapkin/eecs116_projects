# Visual-motion experiments

This directory preserves the older, separate visual-motion pipeline and its uncommitted
SEA-RAFT/CNN comparison, MLP heads, evaluation diagnostics and native student prototype.
It is opt-in; the current pipeline remains in `../odometry_*.py` and `../native_odometry/`.
Keeping its original module names here avoids replacing the newer model and preprocessing.

Run the commands in [VISUAL_MOTION.md](VISUAL_MOTION.md) from **this directory**, using
`configs/visual-motion-screen.json`. Supply data and checkpoint paths explicitly.
Generated caches and checkpoints remain in the preserved local visual-motion checkout at
`/data/backups/rganapa/Sebastian/eecs116_visual_motion/research/`.
For `--deployed`, set `TEACHER_GUEST_DIR` to the exported legacy guests.

Measured JSON reports are committed at `../results/eval/visual-motion/`.
`source-snapshot.json` records original file hashes before the documentation label cleanup and whitespace normalization.
The extra legacy default configurations were copied unchanged alongside the screen configuration.
The source snapshot does not establish a new deployment or performance qualification.
Only syntax and configuration validity were checked during consolidation; training,
replay, parity work and native student testing were not restarted.

Historical truth interventions are evaluation-only diagnostics. They are not inference inputs.
