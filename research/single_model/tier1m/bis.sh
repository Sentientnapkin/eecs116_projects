#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/tier1m
K="KLT_INT=1"
while pgrep -f "run_q --name a5f_nr" > /dev/null; do sleep 5; done
W=8 ./qe.sh g1 t1_b.c "$K PRIOR_EVERY=2 PRIOR_MERGE=1" >> logs/bis.txt 2>&1
W=8 ./qe.sh g2 t1_b.c "$K COVPROP=1 GRAY_G=1" >> logs/bis.txt 2>&1
W=8 ./qe.sh g3 t1_b.c "$K NET_SLICE=1 NET_UNITS=1 NET_UNITS_IDLE=3 NS_GRAYI=1 NS_PREPF=1" >> logs/bis.txt 2>&1
W=8 ./qe.sh g4 t1_b.c "$K DET_PERIOD=2 DET_STRIDE=4 DET_COOL=4 DET_BUDGET=12" >> logs/bis.txt 2>&1
W=8 ./qe.sh g5 t1_b.c "$K MAP_ZI=1 MAP_SPREAD=1 MAP_TRY=2 GATE2=1 ITER_TH=0.1 F_MIRV=1" >> logs/bis.txt 2>&1
