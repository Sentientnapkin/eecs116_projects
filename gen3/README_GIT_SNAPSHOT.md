# Stage-3 research snapshot — 2026-11-27

This directory archives the source, experiment recipes, evaluation results and
research reports previously kept in the sibling `../gen3` workspace. The original
workspace and the current best estimator have not been modified by this archive.

Start with `research/BRIEF.md`, `research/loop2/coverage.json`, and
`research/overnight_20261127/REVIEW_AUDIT.json`. The audit takes precedence over older
report interpretations. The full snapshot provenance is in `SNAPSHOT_MANIFEST.json`.

## Evidence and limitations

- The preserved server best is `preserved_best/gslv_s3_snace6e1.wasm`, SHA-256
  `1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8`.
  Its reported server mean unaligned ATE is 0.4443728206485426 m and peak fuel
  is 4,032,692. Source and build flags are alongside it.
- The overnight wider five-context velocity model reached 0.2375004292 m/s
  mean vector error on its saved validation anchors. This is a standalone model
  result, not an integrated VIO ATE or WASM fuel result. Its checkpoints and
  training results are under `research/overnight_20261127/gpu/`.
- The 48-flight velocity oracle pool overlaps the 24-flight pilot and consists
  of 32 forest and 16 room flights, with no warehouses. It is not independent
  confirmation across all environments. See `REVIEW_AUDIT.json`.
- Corrected temporal correlations use 0.25 s between cached anchor positions.
  Older reports with incorrect lag labels are superseded by the audit.
- No replacement for the best estimator has been established by these results.
  Larger-window MSCKF experiments do not establish full bundle-adjustment or
  smoothing performance. Historical score snapshots do not represent the live
  competition frontier.

## Reproduction and data

Original scripts can contain absolute paths to the original sibling workspace,
`/tmp`, `/dev/shm`, and existing Python environments. `archived_prototypes/`
preserves the temporary experiment scripts; restore their referenced layout or
adjust the path constants before rerunning. Saved manifests specify the actual
flight selections, configurations and seeds. This is a provenance archive, not a
new unified execution interface. Do not rerun historical deletion/upload scripts
as a setup step.

Raw flights are available at
https://huggingface.co/datasets/SentientNapkin/viobench-stage3/tree/main.
Use streaming or bounded downloads; the user cap for local dataset storage is
600,000,000,000 bytes. Raw images, dense labels, track arrays, caches, generated
build copies and large scratch files are excluded from Git. Original files remain
in place. The selected model checkpoints and exact best deployment binary are
included. No hidden evaluator submission was made for this snapshot.
