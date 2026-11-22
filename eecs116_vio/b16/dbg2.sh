cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
SRC=$B/b16s.c FLAGS="-O3 -DLC_DEBUG" bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh dg FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 HALF_RES=1 LC_GRAY_INT=1
source ~/.venv/bin/activate; cd ~/ws_m
EP=$(ls ~/data/hfcal/fastmid/*.zip | sed -n 5p)
rm -rf rep_dg; viobench evaluate ms_dg.wasm $EP -o rep_dg > /dev/null 2>&1
grep -h "LC " rep_dg/logs/* 2>/dev/null | head -6 || python3 -c "import json;print(json.load(open('rep_dg/report.json'))['episodes'][0].get('stderr_tail','')[:600])"
grep -o '"ate_rmse": [0-9.]*' rep_dg/report.json rep_d0/report.json
