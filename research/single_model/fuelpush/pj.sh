#!/bin/bash
# pj.sh: profile governor configs (background, logs/pj.log)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/fuelpush
C="-DF_REUSE=1 -DVKDYN=1 -DF_FWD=1 -DF_LAZYH0=1 -DF32PU=1 -DF32HP=1 -DNS_COST=1 -DITER_GOV=1 -DGC_ROW=55e3 -DGC_ITER=45e3"
for B in 2.4e6 2.0e6; do
  W=32 bash prof.sh fp.c g$B "$C -DGOV_B=$B" 30 > logs/prof_g$B.txt 2>&1
  /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python top.py g$B 12 >> logs/prof_g$B.txt 2>&1
done
echo done >> logs/pj.log
