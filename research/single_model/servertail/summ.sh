#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/servertail
PY=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
for a in "$@"; do for p in st2dev st2conf; do echo "== $a $p"; $PY cmpr.py $p hfg $a | tail -4; done; for s in dev conf; do echo "== $a fresh $s"; $PY cmpr.py fresh_pool hfg $a $s | tail -4; done; done
