#!/bin/bash
# fuel_m.sh NAME [episodes...]: sandbox-evaluate ~/ws_m/ms_NAME.wasm (default: 6 HF flights) and print the summary line
source "$HOME/.venv/bin/activate"
cd "$HOME/ws_m"
NAME=$1; shift
EPS=${@:-$(ls ~/data/hfcal/fast/*.zip | sed -n '1p;20p;40p;60p' | tr '\n' ' ') $(ls ~/data/hfcal/fastmid/*.zip | sed -n '5p;50p' | tr '\n' ' ')}
OUT=report_$NAME; rm -rf $OUT
viobench evaluate ms_$NAME.wasm $EPS -o $OUT > $OUT.log 2>&1 || { tail -5 $OUT.log; exit 1; }
python - $OUT/report.json $NAME <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); s = r["summary"]
print(f"{sys.argv[2]:16s} ATE {s['ate_rmse_mean']:.3f} | fuel max {s['fuel_per_frame_max']:>11,.0f}  p99 {s['fuel_per_frame_p99']:>11,.0f}  median {s['fuel_per_frame_median']:>11,.0f}")
PY
