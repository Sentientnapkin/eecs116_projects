#!/bin/bash
# build.sh [NAME] : cheap.c + weights.h -> ~/ws_cheap/cheap_NAME.wasm (inside WSL), then viobench check.
# eval:  bash build.sh NAME eval [ZIPDIR]   also scores it on every *.zip in ZIPDIR (default ~/data/ho240), 12 at once.
set -e
source "$HOME/.venv/bin/activate"
HERE=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/cheap
NAME=${1:-v1}
cd "$HOME"
WS=${WS:-ws_cheap}; [ -d $WS ] || viobench init native $WS > /dev/null
cd $WS
: > solution/solution.c   # DEFS="A=1 B=2" prepends #defines (experiments)
for def in $DEFS; do echo "#define ${def%%=*} ${def#*=}" >> solution/solution.c; done
cat "$HERE/${SRC:-cheap.c}" >> solution/solution.c
cp "$HERE/weights.h" solution/weights.h; [ -f "$HERE/mlp_weights.h" ] && cp "$HERE/mlp_weights.h" solution/mlp_weights.h
[ -f "$HERE/vis_weights.h" ] && cp "$HERE/vis_weights.h" solution/vis_weights.h
rm -f solution/solution.cpp
sed -i 's/viobench_solution(solution solution.cpp)/viobench_solution(solution solution.c)/; s/^target_compile_options(solution .*-fno-exceptions.*$//' solution/CMakeLists.txt
grep -q "VIO_FLAGS" solution/CMakeLists.txt || echo 'separate_arguments(VIO_FLAGS_LIST UNIX_COMMAND "$ENV{VIO_FLAGS}")
target_compile_options(solution PRIVATE ${VIO_FLAGS_LIST})' >> solution/CMakeLists.txt
grep -q "target_link_libraries(solution PRIVATE m)" solution/CMakeLists.txt || echo 'target_link_libraries(solution PRIVATE m)' >> solution/CMakeLists.txt
export VIO_FLAGS="${FLAGS--O3}"
rm -rf solution/build
viobench bundle solution -o "cheap_$NAME.wasm" > "build_$NAME.log" 2>&1 || { tail -30 "build_$NAME.log"; exit 1; }
ls -la "cheap_$NAME.wasm"
viobench check "cheap_$NAME.wasm" | tail -2
[ "$2" = eval ] || exit 0
DIR=${3:-$HOME/data/ho240}; OUT=ev_${NAME}; rm -rf $OUT; mkdir -p $OUT
ls $DIR/*.zip > $OUT/list; split -n r/12 -d $OUT/list $OUT/part_
for p in $OUT/part_*; do   # no -o: report-<name>/ without videos, one directory per part
  R=$OUT/r_$(basename $p); mkdir -p $R
  ( cd $R && viobench evaluate ../../cheap_$NAME.wasm $(cat ../../$p) > ../$(basename $p).log 2>&1 ) &
done
wait
python - $OUT <<'PY'
import json, glob, sys, os, numpy as np
from viobench.tools.datasets.storage import archive_hash
names = {archive_hash(p): os.path.basename(p)[:-4] for p in open(sys.argv[1] + "/list").read().split()}
eps = [e for f in sorted(glob.glob(sys.argv[1] + "/r_*/*/report.json")) for e in json.load(open(f))["episodes"]]
for e in eps: e["name"] = names.get(e.get("hash"), "?")
a = np.array([(e.get("metrics") or {}).get("ate_rmse", np.nan) for e in eps], float)
fu = np.array([e.get("fuel_per_frame_max") or (e.get("fuel") or {}).get("max", np.nan) for e in eps], float)
print(f"n={len(eps)} ATE mean {np.nanmean(a):.3f} median {np.nanmedian(a):.3f} | fuel/frame max {np.nanmax(fu):,.0f} median {np.nanmedian(fu):,.0f}")
json.dump(eps, open(sys.argv[1] + "/episodes.json", "w"))
PY
