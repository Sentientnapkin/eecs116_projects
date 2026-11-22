#!/bin/bash
# Progress of the overnight batch.
cat ~/logs_night/progress.txt
echo "running: $(pgrep -fc 'viobench simulate') sim processes, $(ls ~/data/night/*/*.zip 2>/dev/null | wc -l)/37 flights saved"
for f in $(ls -t ~/logs_night/*.log | head -2); do echo "$(basename $f): $(tail -c 400 $f | tr '\r' '\n' | grep . | tail -1)"; done
