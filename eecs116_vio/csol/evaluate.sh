#!/bin/bash
# Run the wasm through viobench's sandbox on all practice flights; per-episode ATE and fuel from report.json.
source "$HOME/.venv/bin/activate"
cd "$HOME/ws_c"
WASM=${1:-vio_c.wasm}
OUT=report_$(basename "$WASM" .wasm)
rm -rf "$OUT"
viobench evaluate "$WASM" ${EPISODES:-"$HOME/data/agile_a" "$HOME/data/public" "$HOME/data/fast" "$HOME/data/mixed"} -o "$OUT" > "$OUT.log" 2>&1 || { tail -20 "$OUT.log"; exit 1; }
python - "$OUT/report.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
for e in r["episodes"]:
    m = e["metrics"]
    name = e.get("name") or e.get("episode") or e.get("hash", "")[:10]
    fuel = e.get("fuel", {}) if isinstance(e.get("fuel"), dict) else {}
    print(f"{str(name)[:34]:34s} ATE {m['ate_rmse']:6.2f} m  rot {m['rotation_rmse']*57.3:5.1f} deg  filled {m['filled_frames']}")
s = r["summary"]
print(f"\nMEAN ATE {s['ate_rmse_mean']:.2f} m | fuel per frame: max {s['fuel_per_frame_max']:,.0f}  p99 {s['fuel_per_frame_p99']:,.0f}  "
      f"p95 {s['fuel_per_frame_p95']:,.0f}  median {s['fuel_per_frame_median']:,.0f}  mean {s['fuel_per_frame_mean']:,.0f}")
PY
