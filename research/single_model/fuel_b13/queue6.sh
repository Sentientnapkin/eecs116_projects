#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f queue5.sh >/dev/null; do sleep 10; done
bash $E v4d b16s_q6.c "VIS4=1 MAP_TRY=2 FB_PERIOD=1" 0
bash $E v4e b16s_q6.c "VIS4=1 MAP_TRY=2 FB_PERIOD=2" 0
