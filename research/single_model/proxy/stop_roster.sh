#!/bin/bash
# stop generator workers (and their per-flight children) of one roster file: stop_roster.sh roster_train.json
R=$1
for p in $(pgrep -f "gen_proxy.py (generate|one) --roster $R "); do
  [ "$p" != "$$" ] && kill "$p"
done
sleep 1
pgrep -fa "gen_proxy.py" | grep -v stop_roster | awk '{print $1, $4, $6, $10, $12}'
