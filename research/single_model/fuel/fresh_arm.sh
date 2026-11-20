#!/bin/bash
# fresh_arm.sh "<name>|<defines>" ... : build v.c (cmake path, same as run_variant) and score on the 711-flight fresh pool
cd /data/backups/rganapa/Sebastian/eecs116_projects
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
for spec in "$@"; do
  name=${spec%%|*}; defs=${spec#*|}
  /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B - "$name" "$defs" <<'PY'
import sys; sys.path.insert(0,'.')
from research.single_model import run_variant as RV
from pathlib import Path
(RV.OUT/('fuel_fresh_'+sys.argv[1])).mkdir(parents=True,exist_ok=True)
RV.build(Path('research/single_model/fuel/v.c'),Path('research/single_model/fuel/CMakeLists.txt'),sys.argv[2],'fuel_fresh_'+sys.argv[1])
PY
  /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fuel.run_fresh_fuel --name $name --wasm research/results/single_model/fuel_fresh_$name/solution.wasm --workers 24 > research/results/single_model/fuel_fresh_$name.log 2>&1
done
