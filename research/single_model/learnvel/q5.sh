cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; X="TC_GAP=19 TC_MAXANCH=400"
bash reps.sh P20 lv.c "LV_PERIOD=20 $X" $P
bash reps.sh P20S100 lv.c "LV_PERIOD=20 $X LV_PSCALE=100.0" $P
bash reps.sh P20S2 lv.c "LV_PERIOD=20 $X LV_PSCALE=2.0" $P
