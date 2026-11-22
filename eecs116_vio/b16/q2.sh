cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") | tr '\n' ' '; echo $n; echo "$@" > $B/defs_$n.txt; }
G1="FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1"
ES="LC_GB=4 LC_PREP_PARTS=4 LC_C0R=4 LC_C1R=3 PREP_FAST=1"
bld s1 $G1 LC_SLICE=3 LC_HOLD=1
bld s2 $G1 LC_SLICE=3 LC_HOLD=1 $ES
bld s3 $G1 LC_SLICE=1 LC_HOLD=2 $ES
while pgrep -f "q1.sh" > /dev/null; do sleep 15; done
cd ~/ws_m; for n in s2 s1 s3; do J=10 bash $B/w_eval.sh $n hf; done
