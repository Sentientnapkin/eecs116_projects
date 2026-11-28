#!/bin/bash
# eval_set.sh WASM TAG [SET] : run a .wasm on every flight of a set (default sets/heldout_s3.txt; names, '#' comments,
# zips in ~/data/s3match) and write per-flight ATE / fuel to results/TAG__SET.json. Takes the heavy-job lock.
# Compare two runs with:  python paired.py CAND_TAG BASE_TAG [SET]
# PowerShell: wsl.exe bash /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/eval_set.sh /mnt/c/.../x.wasm TAG
# Git Bash: prefix MSYS_NO_PATHCONV=1.  J parallel evaluate processes (default 8).
set -e
A=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents
[ -f "$1" ] || { echo "no such wasm: $1"; exit 1; }
W=$(realpath "$1"); TAG=$2; SET=${3:-heldout_s3}; J=${J:-8}
[ -n "$TAG" ] || { echo "usage: eval_set.sh WASM TAG [SET]"; exit 1; }
source ~/.venv/bin/activate
OUT=$HOME/data/agents/es_${TAG}__$SET; rm -rf "$OUT"; mkdir -p "$OUT" "$A/results"
grep -v '^#' "$A/sets/$SET.txt" | tr -d '\r' | sed '/^$/d' | sed "s|^|$HOME/data/s3match/|; s|\$|.zip|" > "$OUT/list"
for z in $(cat "$OUT/list"); do [ -f "$z" ] || { echo "missing flight $z"; exit 1; }; done
viobench check "$W" | tail -1
exec 9> "$HOME/data/.heavy.lock"; echo "waiting for the heavy-job lock..."; flock 9; echo "lock taken $(date +%T)"
split -n r/$J -d "$OUT/list" "$OUT/part_"
for p in "$OUT"/part_*; do
  R="$OUT/r_$(basename "$p")"; mkdir -p "$R"
  ( cd "$R" && viobench evaluate "$W" $(cat "$p") > "$p.log" 2>&1 ) &
done
wait
python - "$OUT" "$TAG" "$SET" "$W" "$A" <<'PY'
import glob, hashlib, json, os, sys
import numpy as np
from viobench.tools.datasets.storage import archive_hash
out, tag, s, w, a = sys.argv[1:6]
names = {archive_hash(p): os.path.basename(p)[:-4] for p in open(out + "/list").read().split()}
eps = [e for f in sorted(glob.glob(out + "/r_*/*/report.json")) for e in json.load(open(f))["episodes"]]
fl = {}
for e in eps:
    m = e.get("metrics") or {}
    fl[names.get(e.get("hash"), "?")] = {"ate": m.get("ate_rmse"), "sim3": m.get("sim3_ate_rmse"),
        "fuel_max": e.get("fuel_per_frame_max"), "fuel_p99": e.get("fuel_per_frame_p99"), "filled": m.get("filled_frames")}
res = {"tag": tag, "set": s, "wasm": w, "wasm_sha256": hashlib.sha256(open(w, "rb").read()).hexdigest(),
       "n_expected": len(names), "n_scored": sum(v["ate"] is not None for v in fl.values()), "flights": fl}
json.dump(res, open(f"{a}/results/{tag}__{s}.json", "w"), indent=1)
ate = np.array([v["ate"] for v in fl.values() if v["ate"] is not None], float)
fu = np.array([v["fuel_max"] for v in fl.values() if v["fuel_max"] is not None], float)
print(f"== {tag} on {s}: {res['n_scored']}/{res['n_expected']} flights  ATE mean {ate.mean():.4f}  max fuel {fu.max():,.0f}  sha {res['wasm_sha256'][:12]}")
PY
