cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") | tr '\n' ' '; echo $n; echo "$@" > $B/defs_$n.txt; }
while pgrep -f "q1.sh" > /dev/null; do sleep 15; done
G1="FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1"
bld x1 $G1 UPD_ROWCAP=12
bld x2 $G1 PRIOR_N=4 PRIOR_TRK=1
bld x3 $G1 DET_ON_TRACK=1 DETECT_MAX_CELLS=3
bld x4 $G1 GRAY_G=1 MAP_TRY=2 MAP_S=5
while pgrep -f "q2.sh" > /dev/null; do sleep 15; done
cd ~/ws_m; for n in x1 x2 x3 x4; do J=10 bash $B/w_eval.sh $n hf; done
