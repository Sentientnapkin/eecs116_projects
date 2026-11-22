cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
SRC=$B/b16s.c FLAGS="-O3 -DLC_DEBUG" bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_t.sh dp FAST_KLT=1 DETECT_MAX_CELLS=6 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 HALF_RES=1 LC_GRAY_INT=1 PREP_SIMD=1
source ~/.venv/bin/activate; cd ~/ws_t
EP=$(ls ~/data/hfcal/fastmid/*.zip | sed -n 5p)
rm -rf rep_dp; viobench evaluate ms_dp.wasm $EP -o rep_dp > /dev/null 2>&1
python3 -c "
import json
e=json.load(open('rep_dp/report.json'))['episodes'][0]; print(e['metrics']['ate_rmse'], e.get('stderr_tail','')[:400])"
