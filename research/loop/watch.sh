#!/bin/bash
# Event stream for the overnight session: runner/scheduler lines, pool uploads, errors, low disk.
cd "$(dirname "$0")/.."
( tail -n 0 -F loop/runner.log loop/data_scheduler.log 2>/dev/null | grep --line-buffered -E "^[0-9]{2}:[0-9]{2} |deadline|Traceback|Error" ) &
( tail -n 0 -F data/gen-spool/pool.log 2>/dev/null | awk '/Traceback|RuntimeError|upload retry/ {print; fflush(); next}
   /uploaded/ { match($0, /train=[0-9]+/); n = substr($0, RSTART+6, RLENGTH-6)+0; if (int(n/20) > last) { last = int(n/20); print; fflush() } }' ) &
while true; do
  free=$(df -g . | awk 'NR==2{print $4}')
  if [ "$free" -lt 7 ]; then echo "LOW DISK: ${free} GB free"; fi
  for p in "research_loop"; do
    pgrep -f "$p" >/dev/null || echo "PROCESS DOWN: $p"
  done
  sleep 600
done
