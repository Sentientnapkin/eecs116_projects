cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; X="TC_GAP=19 TC_MAXANCH=400 LV_PERIOD=20 LV_PSCALE=2.0"
R0=1 bash reps.sh RS16 lv.c "$X LV_RESET=1 LV_RCHI=16.0" $P
R0=1 bash reps.sh RS9 lv.c "$X LV_RESET=1 LV_RCHI=9.0" $P
R0=1 bash reps.sh R16 lv.c "LV_RESET=1 LV_RCHI=16.0" $P
