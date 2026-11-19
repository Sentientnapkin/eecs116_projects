#!/usr/bin/env bash
# Resume after dependencies exist. Does not install or modify the shared environment.
set -euo pipefail
SOURCE=/data/backups/rganapa/Sebastian/viobench-provided-openvins
RESEARCH=/data/backups/rganapa/Sebastian/odometry-provided-comparison/research
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH="$SOURCE:$SOURCE/viobench/solution/build/toolchain/venv/lib/python3.12/site-packages"
export TMPDIR=/data/backups/rganapa/Sebastian/tmp
export XDG_CACHE_HOME="$TMPDIR/provided-openvins-cache"
export CMAKE_BUILD_PARALLEL_LEVEL=8
"$PY" -m viobench bundle "$SOURCE/viobench/solution/examples/native/openvins" -o "$SOURCE/openvins.wasm" > "$SOURCE/build-final.log" 2>&1
sha256sum "$SOURCE/openvins.wasm" > "$SOURCE/artifact.sha256"
"$PY" -m viobench check "$SOURCE/openvins.wasm" > "$SOURCE/check.log" 2>&1
VIOBENCH_OPENVINS="$SOURCE/openvins.wasm" "$PY" -m pytest "$SOURCE/tests/test_openvins.py" "$SOURCE/tests/test_openvins_math.py" -q > "$SOURCE/startup-tracking-tests.log" 2>&1
"$PY" "$RESEARCH/provided_baseline/campaign.py" "$SOURCE/openvins.wasm" "$RESEARCH/results/loop/provided-openvins/public" --set public --workers 4 > "$SOURCE/public-replay.log" 2>&1
"$PY" "$RESEARCH/provided_baseline/campaign.py" "$SOURCE/openvins.wasm" "$RESEARCH/results/loop/provided-openvins/campaign-dev" --set campaign-dev --workers 12 > "$SOURCE/campaign-replay.log" 2>&1
