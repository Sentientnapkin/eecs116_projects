#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3/research/i5
R=/data/backups/rganapa/Sebastian
export CUDAARCHS=90 HYPERLUX_CACHE_DIR=$PWD/cache CONTA_CACHE=$R/gen/conta XDG_CACHE_HOME=$R/gen/xdg HF_HOME=$R/hf PATH=$R/venv-sim11/bin:/usr/local/cuda/bin:$PATH PYTHONHASHSEED=0 TMPDIR=$PWD/tmp CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=4
for id in s3v3va-fo-9300459 s3v3va-fo-9300452 s3v3va-ro-9300051; do
  [ -f out_test/$id.json ] && continue
  echo "$(date -u +%T) start $id"; /usr/bin/time -v python -u rr.py $R/gen3/out/keep/$id.zip out_test 2>&1 | grep -v "^\s*\(Page\|Vol\|Invol\|Swap\|File\|Socket\|Signal\|Average\|Exit\|Minor\|Major\|Percent\|Command\)" ; echo "$(date -u +%T) end $id"
done
touch out_test/DONE
