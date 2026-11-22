#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
export TMPDIR=/data/backups/rganapa/Sebastian/tmp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
N=$1; SRC=$2; DEF=$3; shift 3
F=research/single_model/linejac
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
$PY -B -m research.single_model.linejac.mkwasm "$N" "$F/$SRC" "$DEF" > "$F/logs/$N.build.txt" 2>&1
sha256sum "research/results/single_model/lj_$N/solution.wasm" >> "$F/logs/$N.build.txt"
for P in "$@"; do
 if $PY -B "$F/complete.py" "$N" "research/results/single_model/lj_$N/solution.wasm" "$P"; then continue; fi
 WORKERS=${W:-48}; WF="$F/logs/${N%_r[12]}.workers"
 if [ -f "$WF" ]; then WORKERS=$(cat "$WF"); fi
 $PY -B -m research.single_model.linejac.runpool "$N" "research/results/single_model/lj_$N/solution.wasm" "$P" "$WORKERS" > "$F/logs/${N}__$(basename "$P").txt" 2>&1
 tail -1 "$F/logs/${N}__$(basename "$P").txt"
done
