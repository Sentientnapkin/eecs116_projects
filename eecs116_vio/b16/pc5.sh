B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/pq.sh
while pgrep -f build_m.sh > /dev/null; do sleep 3; done
bash $B build e6 FAST_KLT=1 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2 LC_SLICE=1 LC_GB=4 LC_PREP_PARTS=4 LC_C0R=4 LC_C1R=3 PREP_FAST=1 PROP_FAST=1 PRIOR_N=4 MAP_S=5 PRIOR_TRK=1 DET_ON_TRACK=1
bash $B run e6
source ~/.venv/bin/activate; python /mnt/c/Users/alexa/Projects/eecs116_vio/b16/prof_ph.py ~/prof/e6; python /mnt/c/Users/alexa/Projects/eecs116_vio/b16/prof_pk2.py ~/prof/e6 1.0 | head -1
