cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev
R0=1 bash reps.sh BGC lv.c "LV_BGC=1" $P
R0=1 bash reps.sh BGC2 lv.c "LV_BGC=1 LV_BGMAX=0.021" $P
