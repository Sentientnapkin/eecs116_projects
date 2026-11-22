B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/build.sh
M="FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6"
bash $B b16s.c m6 $M MAP_MODE=0
bash $B b16s.c m7 $M MAP_TRY=3
cd ~/ws_m
EPS="$(ls ~/data/hfcal/fast/*.zip | sed -n '1p;40p' | tr '\n' ' ') $(ls ~/data/hfcal/fastmid/*.zip | sed -n '5p;50p' | tr '\n' ' ')"
for n in m6 m7; do bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/fuel_m.sh $n $EPS; done
source ~/.venv/bin/activate; python /mnt/c/Users/alexa/Projects/eecs116_vio/b16/peaks.py m6
