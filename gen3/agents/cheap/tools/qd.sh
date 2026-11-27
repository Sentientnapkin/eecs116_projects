#!/bin/bash
# queue daemon: runs "NAME WASM POOL" lines of logs/queue.txt one at a time (14 workers), waits while loadavg > 170
C=/data/backups/rganapa/Sebastian/gen3/agents/cheap; G=/data/backups/rganapa/Sebastian/gen3
touch $C/logs/queue.txt $C/logs/done.txt
while true; do
  line=$(grep -vxF -f $C/logs/done.txt $C/logs/queue.txt | grep -v '^$' | head -1)
  if [ -z "$line" ]; then sleep 20; continue; fi
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 30; done
  set -- $line
  cd $G && ../venv-teacher/bin/python -B evalpool.py $1 $2 $C/pools/$3 14 > $C/logs/ev_$1__$3.log 2>&1
  echo "$line" >> $C/logs/done.txt
done
