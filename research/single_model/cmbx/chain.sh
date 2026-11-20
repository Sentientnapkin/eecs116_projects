#!/bin/bash
D=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/cmbx
$D/rep.sh b8_spd "CMBX=0 EDGE_SPD=1"
$D/rep.sh b8_vi "CMBX=0 VI_MODE=1"
$D/rep.sh b8_vi50 "CMBX=0 VI_MODE=1 VI_COSMAX=-0.5"
touch $D/chain.done
