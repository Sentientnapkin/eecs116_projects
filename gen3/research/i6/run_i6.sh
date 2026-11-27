#!/bin/bash
# i6 pipeline (resumable): diag (inference) -> input ablations (sequential, per-variant done files out/abl_<v>.json)
cd /data/backups/rganapa/Sebastian/gen3/research/i6
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 CUDA_VISIBLE_DEVICES=5
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
while [ "$(cut -d. -f1 /proc/loadavg)" -gt 170 ]; do sleep 60; done
if [ ! -f out/DIAG_DONE ]; then $PY -B src/diag.py > logs/diag.log 2>&1 && touch out/DIAG_DONE && echo "- diag done $(date -u +%H:%M) -> out/diag.json" >> NOTES.md; fi
for try in 1 2 3; do
  [ -f out/ABL_DONE ] && break
  $PY -B src/abl.py >> logs/abl.log 2>&1
done
echo "- pipeline finished $(date -u +%H:%M)" >> NOTES.md; touch out/ALL_DONE
