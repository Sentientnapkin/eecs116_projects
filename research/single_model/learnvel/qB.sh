cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
S2=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; S3=/data/backups/rganapa/Sebastian/tmp/lv_pools/st3
R0=1 bash reps.sh PB lv.c "TC_GAP=19 TC_MAXANCH=400 LV_PERIOD=20 LV_PSCALE=2.0 LV_BGC=1 LV_BGMAX=0.021" $S2 $S3
R0=1 bash reps.sh P30S2 lv.c "TC_GAP=29 TC_MAXANCH=400 LV_PERIOD=30 LV_PSCALE=2.0" $S2 $S3
