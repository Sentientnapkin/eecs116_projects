cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; X="TC_GAP=19 TC_MAXANCH=400 LV_PERIOD=20 LV_PSCALE=2.0"
R0=1 bash reps.sh TQ3 lv.c "$X LV_TQ=1 LV_TQS=0.003" $P
R0=1 bash reps.sh TQ8 lv.c "$X LV_TQ=1 LV_TQS=0.008" $P
R0=1 bash reps.sh TQ3n lv.c "LV_TQ=1 LV_TQS=0.003" $P
