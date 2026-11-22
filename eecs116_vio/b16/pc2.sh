B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/pq.sh
bash $B build e1 FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 LC_SLICE=2 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2
bash $B run e1
source ~/.venv/bin/activate; python /mnt/c/Users/alexa/Projects/eecs116_vio/b16/prof_ph.py ~/prof/e1
python /mnt/c/Users/alexa/Projects/eecs116_vio/b16/prof_pk2.py ~/prof/e1 1.0 | head -2
