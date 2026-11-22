#!/bin/bash
# bp.sh NAME "DEFS" POOL1 [POOL2 ...] : build geomstarve/gs.c (HM40 defines + DEFS) -> results/gs_NAME, run pools (W env, default 32)
# REP env: 1|2 adds the rep nudges. SRC env overrides source.
cd /data/backups/rganapa/Sebastian/eecs116_projects
export TMPDIR=/data/backups/rganapa/Sebastian/tmp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
N=$1; DEF="HARDEN=1 F_REUSE=1 GATE_MODE=0 TC_MAXANCH=40 TC_RE_SCALE=1.0 $2"; shift 2
case ${REP:-0} in 1) DEF="$DEF PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0";; 2) DEF="$DEF PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0";; esac
F=research/single_model/geomstarve; mkdir -p $F/logs
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
$PY -B -m research.single_model.geomstarve.mkwasm gs_$N ${SRC:-$F/gs.c} "$DEF" > $F/logs/$N.build.txt 2>&1 || { echo BUILD FAIL $N; exit 1; }
sha256sum research/results/single_model/gs_$N/solution.wasm >> $F/logs/$N.build.txt
for P in "$@"; do
  $PY -B -m research.single_model.geomstarve.runpool $N research/results/single_model/gs_$N/solution.wasm $P ${W:-32} > $F/logs/${N}__$(basename $P).txt 2>&1
  tail -1 $F/logs/${N}__$(basename $P).txt
done
