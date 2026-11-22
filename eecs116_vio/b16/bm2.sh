B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/build.sh
M="FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8"
bash $B b16s.c m3 $M ITER_MAXF=6
bash $B b16s.c m4 $M CAP_LOSTC=8 CAP_OLDC=8 CAP_OLD=4 CAP_LOST=4
bash $B b16s.c m5 $M ITER_UPD=1
cd ~/ws_m
EPS="$(ls ~/data/hfcal/fast/*.zip | sed -n '1p;40p' | tr '\n' ' ') $(ls ~/data/hfcal/fastmid/*.zip | sed -n '5p;50p' | tr '\n' ' ')"
for n in m3 m4 m5; do bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/fuel_m.sh $n $EPS; done
