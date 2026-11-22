cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS="-O3 -DLC_DEBUG" bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") >/dev/null; }
bld d0 FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 HALF_RES=1
bld d1 FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 HALF_RES=1 LC_SLICE=1
source ~/.venv/bin/activate; cd ~/ws_m
EP=$(ls ~/data/hfcal/fastmid/*.zip | sed -n 5p)
for n in d0 d1; do rm -rf rep_$n; viobench evaluate ms_$n.wasm $EP -o rep_$n > /dev/null 2>&1; echo "== $n"; grep -rh "LC " rep_$n/logs 2>/dev/null | head -6; done
ls rep_d1/logs/* | head -3
