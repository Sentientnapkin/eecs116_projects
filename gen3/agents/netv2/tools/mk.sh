#!/bin/bash
# mk.sh RUNDIR NAME ["FLAGS"] : export RUN's best.pt into gslv_s3.c (priors base) and build builds/NAME (default flags = F_sp10)
A=/data/backups/rganapa/Sebastian/gen3/agents/netv2; P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
R=$1; [[ $R == /* ]] || R=$A/runs/$R
BASE=${BASE:-/data/backups/rganapa/Sebastian/gen3/agents/priors/gslv_s3.c}
cd $A/tools && $P -B ${MKG:-mkgslv.py} $R $A/src/$2.c --base $BASE > /dev/null && $P -B build.py $A/src/$2.c $2 "${3:-PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0}"
