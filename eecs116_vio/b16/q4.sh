cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") | tr '\n' ' '; echo $n; echo "$@" > $B/defs_$n.txt; }
until grep -q "x4" $B/q3.out 2>/dev/null; do sleep 15; done
F3="FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=6 FLOW_PRED=1.0 PROP_FAST=1 LC_GRAY_INT=1"
bld y1 $F3 UPD_ROWCAP=16
bld y2 $F3 UPD_ROWCAP=24
while pgrep -f "q3.sh" > /dev/null; do sleep 15; done
cd ~/ws_m; for n in y1 y2; do J=10 bash $B/w_eval.sh $n hf; done
