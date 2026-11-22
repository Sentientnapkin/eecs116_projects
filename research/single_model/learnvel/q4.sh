cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; X="TC_GAP=19 TC_MAXANCH=400"
bash learnvel/bp.sh P20S100 lv.c "LV_PERIOD=20 $X LV_PSCALE=100.0" $P
