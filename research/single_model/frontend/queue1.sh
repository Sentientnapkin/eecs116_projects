#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/frontend
run2() { ./run.sh "$1" "$2" & ./run.sh "$3" "$4" & wait; }
run2 fe_fb "FE_FB=1" fe_rs "FE_RS=1 FE_DEBUG=1"
run2 fe_norm "FE_NORM=1" fe_grid168 "GRID_X=16 GRID_Y=8"
run2 fe_grid108 "GRID_X=10 GRID_Y=8" fe_radw "FE_RADW=0.5"
run2 fe_rmax "FE_RMAX=1.4" fe_fall "FE_CELLFALL=1"
run2 fe_klt5 "KLT_R=5" fe_l3 "LEVELS=3"
echo done > queue1.done
