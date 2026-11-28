#!/bin/bash
# eval_twin120.sh WASM [TAG] : score a built .wasm on the 120 twin flights (the calibrated server proxy, ~3%), inside WSL.
# Prints twin120 (mean over the 24 episodes of each episode's ~5-flight mean), twin24, max fuel/frame and the area gain,
# and writes eecs116_vio/agents/results/TAG.json.
#
# From PowerShell:  wsl.exe bash /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/eval_twin120.sh /mnt/c/.../x.wasm TAG
# From Git Bash:    prefix MSYS_NO_PATHCONV=1 so /mnt/c paths are not rewritten.
#
# Takes the shared heavy-job lock (~/data/.heavy.lock): only one heavy job runs at a time (WSL is capped at 10 GB).
# J parallel evaluate processes (default 8).
set -e
A=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents
S3=$A/../stage3
[ -f "$1" ] || { echo "no such wasm: $1"; exit 1; }
W=$(realpath "$1"); TAG=${2:-$(basename "$1" .wasm)}; J=${J:-8}
source ~/.venv/bin/activate
OUT=$HOME/data/agents/ev_$TAG; rm -rf "$OUT"; mkdir -p "$OUT" "$A/results"
cut -f2 "$S3/twin/twin120.txt" | tr -d '\r' | sort -u | sed "s|^|$HOME/data/s3match/|; s|\$|.zip|" > "$OUT/list"
viobench check "$W" | tail -2
exec 9> "$HOME/data/.heavy.lock"; echo "waiting for the heavy-job lock..."; flock 9; echo "lock taken $(date +%T)"
split -n r/$J -d "$OUT/list" "$OUT/part_"
for p in "$OUT"/part_*; do
  R="$OUT/r_$(basename "$p")"; mkdir -p "$R"
  ( cd "$R" && viobench evaluate "$W" $(cat "$p") > "$p.log" 2>&1 ) &
done
wait
python "$A/twin_summary.py" "$OUT" "$TAG" "$W"
