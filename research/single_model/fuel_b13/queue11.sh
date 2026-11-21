#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f "fuel_b13/queue9.sh|fuel_b13/queue10.sh" >/dev/null; do sleep 10; done
bash $E k_ls4 b16s_q9.c "LC_SPREAD=4" 0
bash $E k_ms b16s_q9.c "MAP_SPREAD=1" 0
bash $E k_ls4ps b16s_q9.c "LC_SPREAD=4 LC_PSPLIT=1" 0
