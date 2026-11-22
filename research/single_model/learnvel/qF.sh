cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
while kill -0 1828547 2>/dev/null; do sleep 30; done
S2=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; S3=/data/backups/rganapa/Sebastian/tmp/lv_pools/st3
R0=1 bash reps.sh rsP10S2 rs.c "TC_GAP=9 TC_MAXANCH=400 LV_PERIOD=10 LV_PSCALE=2.0" $S2 $S3
R0=1 bash reps.sh rsP10S3B rs.c "TC_GAP=9 TC_MAXANCH=400 LV_PERIOD=10 LV_PSCALE=3.0 LV_BGC=1 LV_BGMAX=0.021" $S2 $S3
R0=1 bash reps.sh rsB rs.c "LV_BGC=1 LV_BGMAX=0.021" $S2 $S3
