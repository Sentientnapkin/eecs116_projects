cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") >/dev/null && echo built $n; }
bld pf0 FAST_KLT=1 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 LC_SLICE=2 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2
bld pf1 FAST_KLT=1 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 LC_SLICE=2 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2 PROP_FAST=1
source ~/.venv/bin/activate; cd ~/ws_m
EPS="$(ls ~/data/hfcal/fast/*.zip | sed -n '1p;40p' | tr '\n' ' ') $(ls ~/data/hfcal/fastmid/*.zip | sed -n '5p' | tr '\n' ' ')"
for n in pf0 pf1; do bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/fuel_m.sh $n $EPS; done
for d in report_pf0/logs/*/; do e=$(basename $d); cmp -s report_pf0/logs/$e/estimate.tum report_pf1/logs/$e/estimate.tum && echo "identical $e" || echo "DIFFER $e"; done
