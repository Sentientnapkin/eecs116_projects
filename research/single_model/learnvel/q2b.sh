cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev; X="TC_GAP=19 TC_MAXANCH=400"
bash learnvel/bp.sh G11 lv.c "LV_GATE=11" $P
bash learnvel/bp.sh P20L20 lv.c "LV_PERIOD=20 $X LV_PLIVE=20" $P
bash learnvel/bp.sh P20L15S2 lv.c "LV_PERIOD=20 $X LV_PLIVE=15 LV_PSCALE=2.0" $P
