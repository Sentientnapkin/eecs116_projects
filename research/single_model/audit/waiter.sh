#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/audit
while pgrep -f "[e]v.sh ab_lat0" >/dev/null || pgrep -f "[e]v.sh ab_gate0_r1 " >/dev/null || pgrep -f "[r]un_fresh --name ab_hold0_r1" >/dev/null; do sleep 20; done
echo "$(date +%T) orphans done; second stream" >> logs/runner.txt
exec ./runner2.sh
