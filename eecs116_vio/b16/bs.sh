B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/build.sh
SM="ITER_UPD=1 MAP_MODE=0 TC_MON=0 FB_PERIOD=0 MAX_UPDATE_FEATURES=5"
bash $B b16s.c s1 $SM LC_ENABLE=0 MAX_CLONES=3 GRID_X=5 GRID_Y=3
bash $B b16s.c s2 $SM LC_ENABLE=0 MAX_CLONES=4 GRID_X=6 GRID_Y=4
bash $B b16s.c s3 $SM LC_SPREAD=5 MAX_CLONES=3 GRID_X=5 GRID_Y=3
cd ~/ws_m
EPS="$(ls ~/data/hfcal/fast/*.zip | sed -n '1p;40p' | tr '\n' ' ') $(ls ~/data/hfcal/fastmid/*.zip | sed -n '5p;50p' | tr '\n' ' ')"
for n in s1 s2 s3; do bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/fuel_m.sh $n $EPS; done
