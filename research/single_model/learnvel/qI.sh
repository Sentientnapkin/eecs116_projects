cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
while pgrep -f "bash qG.sh" >/dev/null; do sleep 60; done
S2=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; S3=/data/backups/rganapa/Sebastian/tmp/lv_pools/st3
R0=1 bash reps.sh glNP gln_v700b.c "TC_GAP=9 TC_MAXANCH=400 LV_PERIOD=10 LV_PSCALE=3.0 LV_BGC=1 LV_BGMAX=0.021" $S2 $S3
R0=1 bash reps.sh glN gln_v700b.c "" $S2 $S3
