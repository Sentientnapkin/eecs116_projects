#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
export TMPDIR=/data/backups/rganapa/Sebastian/tmp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=5
F=research/single_model/stlearn
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
while ! $PY -c "import json;d=json.load(open('$F/tables/cache_counts.json'));a=json.load(open('$F/work/repro_sources.json'));assert d['repro']==len(a) and d['repro']>0" 2>/dev/null; do sleep 15; done
mkdir -p "$F/work/data/work"
ln -sfn /data/backups/rganapa/Sebastian/tmp/stlearn_cache "$F/work/data/work/cache"
printf '%s\n' '- Starting t2 reproduction: GPU5,10,000 steps, original model/NLL/augmentation, safe-subset data, original hash%12 plus protected expanded-validation scenes.' >> "$F/NOTES.md"
$PY -B "$F/train.py" --data "$F/work/data" --records "$F/work/repro_records.json" --out "$F/final/repro_t2" --steps 10000 --bs 64 --workers 8 --eval_every 2000
printf '%s\n' '- t2 reproduction finished; curves/checkpoints under final/repro_t2. Expanded teacher remains a separate training stage.' >> "$F/NOTES.md"
