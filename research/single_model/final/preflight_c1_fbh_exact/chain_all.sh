#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
P=research/single_model/final/preflight_c1_fbh_exact
w(){ while [ $(cut -d. -f1 /proc/loadavg) -gt 140 ]; do sleep 20; done; }
w; bash $P/rescore.sh a
w; bash $P/fresh_chain.sh
w; bash $P/rescore.sh b
echo done > $P/all.done
