#!/bin/bash
# featurize.sh LIST OUTPREFIX [JOBS]: python probe stats for every src in LIST (resumable), JOBS processes -> OUTPREFIX_<n>.jsonl
cd /data/backups/rganapa/Sebastian/gen3/twin
L=$1; O=$2; J=${3:-14}
split -n r/$J -d $L /data/backups/rganapa/Sebastian/gen3/twin/.chunk_$(basename $O)_
for c in .chunk_$(basename $O)_*; do
  ( while ! [ $(cut -d. -f1 /proc/loadavg) -lt 170 ]; do sleep 60; done
    xargs -a $c -n4 ../../venv-teacher/bin/python -I features.py ${O}_${c##*_}.jsonl ) &
done
wait; rm -f .chunk_$(basename $O)_*; echo FEATURIZE_DONE
