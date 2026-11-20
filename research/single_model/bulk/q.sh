#!/bin/bash
# usage: q.sh waitlog "name|defines" ...   : waits until waitlog has 'mean', then runs arms sequentially (backs off while load > 150)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/bulk
W=$1; shift
until grep -q " mean " logs/$W 2>/dev/null; do sleep 10; done
for a in "$@"; do
  while [ $(cut -d. -f1 /proc/loadavg) -gt 150 ]; do sleep 30; done
  N=${a%%|*}; D=${a#*|}; ./ev.sh $N "$D"
done
