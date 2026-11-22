#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/filtcons
while pgrep -f qladder.sh >/dev/null || pgrep -f "bp.sh nlog5" >/dev/null; do sleep 30; done
./qx.sh jobs2.txt 40
