#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3/research/i3
for L in "b0|BASELINE" "or0|"; do n=${L%%|*}; f=${L#*|}; python3 tools/run_one.py v_$n "$f" i3s120 8 >> logs/validate.log 2>&1; done
touch logs/validate.done
