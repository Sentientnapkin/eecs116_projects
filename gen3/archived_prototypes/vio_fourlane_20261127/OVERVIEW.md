# Four VIO research avenues — 2026-11-27

Current immutable server reference: gslv_s3_snace6e1.wasm, SHA256 1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8. User-provided official result: mean ATE 0.4443728206485426 m; median 0.410767624522633 m; peak WASM fuel 4032692; live claimed score 1.29%; all 24 episodes complete. Both checked local copies match this hash.

Requested lanes: accuracy (current MSCKF), fuel (current-system component and implementation reductions), extreme (cheap alternative frontier), learned (higher-compute learned and hybrid accuracy). All lane agents use gpt-6-luna. At most three child agents run simultaneously; detached scripts can continue after an agent finishes.

Do not modify the current artifact, submit to hidden evaluation, use stage-3 test, or kill existing jobs. Scripts and logs belong in this temporary directory; bulk outputs under /dev/shm/vio_fourlane_20261127, bounded per lane. /data has approximately 5 GB free. No large downloads or training jobs until adequate storage and resource availability is verified. Local screening is exploratory and cannot establish hidden-server improvement.

Historical score grids are stale: live baseline eligibility changed. Report raw ATE and measured peak fuel; do not claim present competition score from old comparison.json. Credit is best single submission, not union of a team's frontier points.

Existing evidence to reuse: gen3/research/i1 through i6, n1,n2,e1, plus earlier r1 through r11 and gen3/agents/anchors. i3 baseline is OLD A160ft+Ze0, not the current small-net build. Its depth labels are triangulated from tracked pixels and GT poses, not exact renderer depth; correspondence oracle projects these fitted landmarks. Velocity sweeps change both measurement noise and assumed sigma. Validate interventions and use matched current controls before concluding headroom.

Existing full-data velocity training watcher is alive but waiting for UPLOAD FINISHED; it still trains the old A160 recipe and compares old Ze0. No new full-data round was confirmed running during this audit. Uploader log records 11959 uploaded flights as of 00:07 UTC; this count is not proof generation/upload completion. Server twins completed calibration but reverse F_sp10 vs auto727, so are auxiliary diagnostics, not a validated replacement for development evaluation.

Each lane must provide an executable finite resumable queue, completion markers, results and failure logs. Verify detached process survives launch and starts actual work. No active-model polling loops. Do not promise automatic model resumption at a usage reset.
