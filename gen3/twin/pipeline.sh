#!/bin/bash
# Detached, resumable twin pipeline. Each stage writes state/<stage>.done; rerunning skips finished stages.
# Run: setsid nohup bash pipeline.sh > pipeline.log 2>&1 &     Done marker: state/ALL.done
T=/data/backups/rganapa/Sebastian/gen3/twin; G=/data/backups/rganapa/Sebastian/gen3; PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
cd $T
note(){ echo "- $(date -u +%FT%H:%MZ) $*" >> $T/NOTES.md; echo "$*"; }
waitload(){ while [ $(cut -d. -f1 /proc/loadavg) -ge 170 ]; do sleep 120; done; }
featurize(){ # LIST TAG
  $PY todo.py $1 > state/todo_$2.txt; n=$(wc -l < state/todo_$2.txt); echo "featurize $2: $n todo"
  [ $n -eq 0 ] && return
  split -n r/14 -d state/todo_$2.txt state/chunk_$2_
  for c in state/chunk_$2_*; do ( waitload; xargs -a $c -n4 $PY -I features.py feat_$2_${c##*_}.jsonl ) & done; wait; rm -f state/chunk_$2_*
}
# 1. first featurization pass (an earlier run may still be going: wait for it)
while pgrep -u $(id -u) -f "features.py feat_s1_" > /dev/null; do sleep 120; done
if [ ! -f state/feat1.done ]; then featurize shortlist.txt r1; touch state/feat1.done; note "stage feat1 done: $(cat feat_*.jsonl | grep -vc error) featurized"; fi
# 2. after generation finishes (~22:00 UTC): re-index candidates, re-shortlist, featurize new + retry errors
while [ $(date -u +%H%M) -lt 2215 ] && [ $(date -u +%H) -ge 12 ]; do sleep 300; done
if [ ! -f state/feat2.done ]; then
  $PY match.py shortlist 60 | tee -a pipeline.log; featurize shortlist.txt r2; featurize shortlist.txt r3
  touch state/feat2.done; note "stage feat2 done (re-indexed after generation): $(cat feat_*.jsonl | grep -vc error) featurized rows; $($PY match.py shortlist 60)"
fi
# 3. matching
if [ ! -f state/match.done ]; then $PY match.py final > match.log 2>&1 && touch state/match.done && note "stage match done: twin24.txt twin120.txt coverage.txt ($(tail -1 coverage.txt))"; fi
# 4. pools (downloads remote twins into twin/zips)
if [ ! -f state/pools.done ]; then $PY mkpools.py > pools.log 2>&1 && touch state/pools.done && note "stage pools done: $(tr '\n' ' ' < pools.log | tail -c 200); zips $(du -sh zips 2>/dev/null | cut -f1)"; fi
# 5. calibration evals (14 workers): every build on twin24, twin120, v3val120
for b in gslvlj F_sp10 auto727 b16 m7 gate v4d cv2; do
  W=$($PY -c "import json;print(json.load(open('builds.json'))['$b'][0])")
  for pool in $G/pools/twin120 $G/pools/twin24 $T/pools/v3val120; do
    pn=$(basename $pool); [ -f state/eval_${b}_$pn.done ] && continue
    waitload; $PY seed_cache.py tw_$b $W $pool
    (cd $G && $PY -B evalpool.py tw_$b $W $pool 14) > state/eval_${b}_$pn.log 2>&1 && touch state/eval_${b}_$pn.done && \
      note "eval tw_$b $pn: $(grep -m1 'mean ATE' state/eval_${b}_$pn.log)"
  done
  [ "$b" = auto727 ] && $PY calib.py > /dev/null 2>&1   # early partial calibration after the 3 main builds
done
# 6. calibration + reweighting
$PY calib.py > calib.log 2>&1; $PY reweight.py > reweight.log 2>&1
note "stage calib done: see calib.txt, reweight.txt"
touch state/ALL.done
