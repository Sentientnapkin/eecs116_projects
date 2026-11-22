cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev
R0=1 bash reps.sh GR10 lvg_g64.c "LV_GRAV=1 LV_GPER=10" $P
R0=1 bash reps.sh GR10s2 lvg_g64.c "LV_GRAV=1 LV_GPER=10 LV_GSC=2.0" $P
R0=1 bash reps.sh GR20s2 lvg_g64.c "LV_GRAV=1 LV_GPER=20 LV_GSC=2.0" $P
