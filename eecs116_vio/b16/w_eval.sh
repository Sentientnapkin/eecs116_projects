#!/bin/bash
# w_eval.sh NAME [hf|pub|fuel] : sandbox-evaluate ~/ws_m/ms_NAME.wasm, 16 processes in parallel.
#   hf   = all 171 HF server-calibrated flights (fast = rest starts, fastmid = mid-flight starts)
#   pub  = viobench public set (10 episodes)
#   fuel = 24 HF flights (every 7th) for a quick fuel/accuracy look
# Per-episode results -> ~/ws_m/ev_NAME_SET.json ; summary line printed.
source "$HOME/.venv/bin/activate"
cd "$HOME/ws_m"
NAME=$1; SET=${2:-hf}; J=${J:-16}
W=ms_$NAME.wasm; [ -f "$W" ] || { echo "no $W"; exit 1; }
OUT=evr_${NAME}_$SET; rm -rf $OUT; mkdir -p $OUT
case $SET in
  hf)   ls ~/data/hfcal/fast/*.zip ~/data/hfcal/fastmid/*.zip > $OUT/list ;;
  fuel) ls ~/data/hfcal/fast/*.zip ~/data/hfcal/fastmid/*.zip | awk 'NR%7==1' > $OUT/list ;;
  pub)  : > $OUT/list ;;
esac
if [ "$SET" = pub ]; then
  viobench evaluate $W -o $OUT/r0 > $OUT/r0.log 2>&1
else
  split -n r/$J -d $OUT/list $OUT/part_
  for p in $OUT/part_*; do
    ( viobench evaluate $W $(cat $p) -o $OUT/r_$(basename $p) > $OUT/$(basename $p).log 2>&1 ) &
  done
  wait
fi
python - $OUT $NAME $SET <<'PY'
import json, glob, sys, os, numpy as np
out, name, s = sys.argv[1:4]
eps = []
for f in sorted(glob.glob(f"{out}/r*/report.json")):
    eps += json.load(open(f))["episodes"]
lists = open(f"{out}/list").read().split()
kind = {}
for p in lists:
    kind[os.path.basename(p)[:-4]] = "mid" if "/fastmid/" in p else "rest"
rows = []
for e in eps:
    m = e.get("metrics") or {}
    rows.append(dict(hash=e["hash"], name=e.get("name", ""), ate=m.get("ate_rmse", float("nan")), rot=m.get("rotation_rmse", float("nan")),
                     fuel=e.get("fuel_per_frame_max", float("nan")), filled=m.get("filled_frames", 0), completed=e.get("completed")))
json.dump(rows, open(os.path.expanduser(f"~/ws_m/ev_{name}_{s}.json"), "w"), indent=0)
a = np.array([r["ate"] for r in rows]); fu = np.array([r["fuel"] for r in rows])
bad = sum(1 for r in rows if not r["completed"] or r["filled"])
print(f"{name:14s} {s:4s} n={len(rows):3d} ATE mean {np.nanmean(a):.3f} median {np.nanmedian(a):.3f} >3m {int(np.sum(a>3)):2d} | fuel max {np.nanmax(fu):>11,.0f} p90(ep max) {np.nanpercentile(fu,90):>11,.0f} | incomplete/filled {bad}")
PY
