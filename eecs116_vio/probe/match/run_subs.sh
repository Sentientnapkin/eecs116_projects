#!/bin/bash
# run_subs.sh [JOBS] : run every wasm in probe/match/wasm/ (named <server submission id>.wasm) on every downloaded flight
# in ~/data/s3match/ (*.zip.ok, from fetch.py), writing eecs116_vio/stage3/match_runs/<server id>/<flight id>.json.
# Pairs that already have a report there are skipped (775 were done on the laptop), so it resumes after interrupts.
# Needs an activated viobench venv. About 16 s per (submission, flight) pair per core.
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(cd "$HERE/../../stage3" && pwd)/match_runs
JOBS=${1:-$(nproc)}
mkdir -p "$OUT"
for ok in ~/data/s3match/*.zip.ok; do
  fid=$(basename "${ok%.zip.ok}")
  for w in "$HERE"/wasm/*.wasm; do
    sid=$(basename "$w" .wasm)
    [ -f "$OUT/$sid/$fid.json" ] || echo "$sid $fid"
  done
done | xargs -P "$JOBS" -L1 bash -c '
  sid=$0; fid=$1; tmp=$(mktemp -d); cd "$tmp"
  if viobench evaluate "'"$HERE"'/wasm/$sid.wasm" ~/data/s3match/$fid.zip > log.txt 2>&1; then
    mkdir -p "'"$OUT"'/$sid" && cp report-*/report.json "'"$OUT"'/$sid/$fid.json"; else echo "FAILED $sid $fid: $(tail -1 log.txt)"; fi
  cd / && rm -rf "$tmp"'
echo "reports: $(ls "$OUT"/*/*.json 2>/dev/null | wc -l) (complete: 13 x 236 = 3068)"
