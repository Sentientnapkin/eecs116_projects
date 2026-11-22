cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model
P=/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev
bash learnvel/bp.sh P20 lv.c "LV_PERIOD=20 TC_GAP=19 TC_MAXANCH=400" $P
bash learnvel/bp.sh P20G lv.c "LV_PERIOD=20 TC_GAP=19 TC_MAXANCH=400 LV_GATE=11" $P
bash learnvel/bp.sh G11 lv.c "LV_GATE=11" $P
bash learnvel/bp.sh P40G lv.c "LV_PERIOD=40 TC_GAP=39 TC_MAXANCH=400 LV_GATE=11" $P
