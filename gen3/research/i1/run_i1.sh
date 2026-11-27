#!/bin/bash
# i1 pipeline: (1) component fuel profile of the baseline on all 358 v3val flights, (2) conv-stack fuel bench, (3) summaries.
cd /data/backups/rganapa/Sebastian/gen3/research/i1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
while [ "$(cut -d. -f1 /proc/loadavg)" -gt 170 ]; do sleep 60; done
[ -f bench.done ] || $PY bench.py bench.tsv > logs/bench.log 2>&1 &
BP=$!
$PY prof_run.py builds/i1_prof/solution.wasm flights_v3val.txt prof_v3val 7 > logs/prof.log 2>&1
$PY prof_sum.py prof_v3val prof_summary.md > logs/prof_sum.log 2>&1
wait $BP
echo "$(date -u +%F' '%T) i1 pipeline done: prof_summary.md, bench.tsv" >> NOTES.md
touch PIPE.done
