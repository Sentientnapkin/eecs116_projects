cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev
R0=1 bash reps.sh GRR9 lvg_g64.c "LV_GRAV=1 LV_GPER=10 LV_GRESET=1 LV_GRCHI=9.0" $P
R0=1 bash reps.sh GRR9b lvg_g64.c "LV_GRAV=1 LV_GPER=10 LV_GRESET=1 LV_GRCHI=9.0 LV_GRBG=0.01" $P
R0=1 bash reps.sh GRh lvg_g64.c "LV_GRAV=1 LV_GPER=10 LV_GSC=0.5" $P
