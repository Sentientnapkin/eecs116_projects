cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh f1 FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0
SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh l2b FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1
cmp ~/ws_m/ms_l2b.wasm ~/ws_m/ms_l2.wasm && echo "l2 rebuild identical"
