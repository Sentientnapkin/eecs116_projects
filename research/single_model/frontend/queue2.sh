#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/frontend
./rep2.sh fe2_fall "FE_CELLFALL=1"
./rep2.sh fe2_fb "FE_FB=1"
./rep2.sh fe2_norm "FE_NORM=1"
./rep2.sh fe2_rs "FE_RS=1 FE_DEBUG=1"
echo done > queue2.done
