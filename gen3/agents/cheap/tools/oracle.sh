#!/bin/bash
# oracle.sh TAG "DEFS" FLIGHT...: TEST ONLY: per-flight builds with ground-truth velocity in place of the net output; eval each on its flight
C=/data/backups/rganapa/Sebastian/gen3/agents/cheap; tag=$1; defs=$2; shift 2
for f in "$@"; do
  mkdir -p $C/pools/or_$f; ln -sf $(readlink -f $C/pools/v3val/$f.zip 2>/dev/null || readlink -f $C/pools/v1val/$f.zip) $C/pools/or_$f/
  rm -rf $C/srcO_$f; cp -r $C/src $C/srcO_$f
  PYTHONPATH=/dev/shm/sebastian-vio/viobench /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python $C/tools/mkoracle.py $C/pools/or_$f $f $C/srcO_$f/oracle.h >/dev/null
  (cd $C && ../../../venv-teacher/bin/python tools/build.py or_${tag}_$f srcO_$f "$defs" >/dev/null 2>&1)
  rm -rf $C/srcO_$f
done
cd /data/backups/rganapa/Sebastian/gen3
for f in "$@"; do ../venv-teacher/bin/python -B evalpool.py cg_or_${tag}_$f $C/builds/or_${tag}_$f/solution.wasm $C/pools/or_$f 1 > /dev/null 2>&1 & done; wait
for f in "$@"; do python3 -c "
import json;r=json.load(open('evals/cg_or_${tag}_${f}__or_${f}.json'))[0];print('$tag', r['id'], r['ate'] and round(r['ate'],2), r['peak'])"; done
