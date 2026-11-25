#!/bin/bash
# run_local.sh FLIGHT_DIR [JOBS] : run the probe on every flight zip in FLIGHT_DIR (JOBS at once, default 8),
# writing FLIGHT_DIR/probe_reports/<flight>/report-*/report.json. Then: python compare.py FLIGHT_DIR
# Needs a viobench venv (activate it first). Each 60 s flight takes ~15 s alone, ~45 s with 20 running at once.
set -e
DIR=$(cd "$1" && pwd); JOBS=${2:-8}
WASM=$(cd "$(dirname "$0")/../submissions" && pwd)/probe_stage3.wasm
OUT=$DIR/probe_reports; mkdir -p "$OUT"
ls "$DIR"/*.zip | xargs -P "$JOBS" -I{} bash -c '
  n=$(basename {} .zip); d='"$OUT"'/$n
  ls $d/report-*/report.json >/dev/null 2>&1 && exit 0
  mkdir -p $d && cd $d && viobench evaluate '"$WASM"' {} > log.txt 2>&1 && echo "done $n" || echo "FAILED $n (see $d/log.txt)"'
