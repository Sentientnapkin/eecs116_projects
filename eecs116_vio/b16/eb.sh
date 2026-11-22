cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") | tr '\n' ' '; echo $n; }
bld e2 FAST_KLT=1 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 LC_SLICE=2 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2 GRAY_G=0
bld e3 FAST_KLT=1 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 LC_SLICE=2 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2 LC_SLICE=1 LC_GB=4 LC_PREP_PARTS=4 LC_C0R=8 LC_C1R=6
while pgrep -f "gb.sh" > /dev/null; do sleep 10; done
cd ~/ws_m; for n in e1 e2 e3; do bash $B/w_eval.sh $n hf; done
