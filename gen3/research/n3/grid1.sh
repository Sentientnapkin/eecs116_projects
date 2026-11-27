#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3/research/n3
while read tag defs; do
 [ -f logs/g_$tag.done ] && continue
 while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 30; done
 r=$(STUBN=0.35 ../../../venv-teacher/bin/python sim.py src/ins_N.c "NET_SIG=0.44 $defs" 2>&1 | tail -1)
 echo "$tag | $defs | $r" >> res/grid1.txt; touch logs/g_$tag.done
done < $1
touch logs/$1.done
