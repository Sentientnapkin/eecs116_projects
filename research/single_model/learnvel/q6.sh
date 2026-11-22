cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; X="TC_GAP=19 TC_MAXANCH=400"
R0=1 bash reps.sh Nb2P20 lvn_b2.c "LV_PERIOD=20 $X" $P
R0=1 bash reps.sh Nbn05P20 lvn_bn05.c "LV_PERIOD=20 $X" $P
