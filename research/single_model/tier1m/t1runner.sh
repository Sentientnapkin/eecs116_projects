#!/bin/bash
# sequential job runner: pops lines "NAME SRC DEFINES..." from jobs.txt (one eval at a time)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/tier1m
while true; do
  L=$(head -n1 jobs.txt 2>/dev/null)
  if [ -z "$L" ]; then sleep 20; [ -s jobs.txt ] || { [ -f stop_runner ] && exit 0; continue; }; continue; fi
  sed -i '1d' jobs.txt
  N=$(echo "$L" | awk '{print $1}'); S=$(echo "$L" | awk '{print $2}'); D=$(echo "$L" | cut -d' ' -f3-)
  REP=0; case $N in *r1) REP=1;; *r2) REP=2;; esac
  echo "$(date +%H:%M) start $N $S $D rep$REP" >> logs/runner.txt
  ./ev.sh $N $S "$D" $REP >> logs/runner.txt 2>&1
done
