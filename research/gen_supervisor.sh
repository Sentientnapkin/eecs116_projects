#!/bin/bash
# Restart odometry_gen.py after native renderer crashes, marking the crashing scene as failed.
cd "$(dirname "$0")"
spool=data/gen-spool
while true; do
  ./gen_env.sh odometry_gen.py --spool "$spool" "$@" >> "$spool/gen.log" 2>&1
  code=$?
  [ $code -eq 0 ] && exit 0
  key=$(/opt/miniconda3/bin/python -c "import json;print(json.load(open('$spool/current.json'))['key'])" 2>/dev/null)
  echo "$(date +%H:%M) generator exited $code during $key; marking failed and restarting" >> "$spool/gen.log"
  [ -n "$key" ] && echo "{\"key\": \"$key\", \"status\": \"failed: native crash (exit $code)\"}" >> "$spool/generated.jsonl"
  rm -rf "$spool"/viobench-sim-* "$spool/partial"/*
  sleep 5
done
