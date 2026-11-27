#!/bin/bash
# dev.sh NAME "DEFS" [POOL=smoke]: build + eval (12 workers, waits while load > 170) on a small dev pool + per-flight table vs goats / GSLV best
C=/data/backups/rganapa/Sebastian/gen3/agents/cheap; P=${3:-smoke}
$C/tools/mk.sh $1 "$2" >/dev/null || exit 1
while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 20; done
cd /data/backups/rganapa/Sebastian/gen3 && ../venv-teacher/bin/python -B evalpool.py cg_$1 $C/builds/$1/solution.wasm $C/pools/$P 12 > $C/logs/dev_$1.log 2>&1
python3 $C/tools/devtab.py $1 $P
