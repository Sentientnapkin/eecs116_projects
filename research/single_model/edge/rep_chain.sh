#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/edge
N1="PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0"; N2="PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
CMB="EDGE_SPD=1 VI_MODE=1 VI_COSMAX=-0.26"
(./run.sh edge_cmb "$CMB" & ./run.sh edge_g_r1 "$N1" & wait)
(./run.sh edge_g_r2 "$N2" & ./run.sh edge_vb_r1 "VI_MODE=1 VI_COSMAX=-0.26 $N1" & wait)
(./run.sh edge_vb_r2 "VI_MODE=1 VI_COSMAX=-0.26 $N2" & ./run.sh edge_cmb_r1 "$CMB $N1" & wait)
./run.sh edge_cmb_r2 "$CMB $N2"
(./fresh.sh edge_cmb & ./fresh.sh edge_g_r1 & wait)
(./fresh.sh edge_g_r2 & ./fresh.sh edge_vb_r1 & wait)
(./fresh.sh edge_vb_r2 & ./fresh.sh edge_cmb_r1 & wait)
./fresh.sh edge_cmb_r2
