#!/bin/bash
# runner.sh : pops "NAME|SRC|DEFS|REP" lines from jobs.txt (flock) and runs ev.sh; run 2 copies for 2 streams x 24 workers
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/audit
while true; do
  [ -f stop_runner ] && exit 0
  L=$(flock jobs.lock bash -c 'l=$(head -1 jobs.txt); [ -n "$l" ] && sed -i 1d jobs.txt; echo "$l"')
  if [ -z "$L" ]; then sleep 20; continue; fi
  IFS='|' read -r N S D R <<< "$L"
  echo "$(date +%T) start $N" >> logs/runner.txt
  W=${RW:-20} ./ev.sh "$N" "$S" "$D" "$R" >> logs/runner.txt 2>&1
  echo "$(date +%T) done $N" >> logs/runner.txt
done
