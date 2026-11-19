#!/bin/bash
# Quick check before the big batch: 30 s probes of the wide_* styles (4 flights each, so 4 different top speeds),
# showing the speed range each flight really covers and whether any crashed. Nothing is chosen automatically.
#   bash calibrate.sh
KIT=$(cd "$(dirname "$0")" && pwd)
REPO=$(cat "$KIT/.repo_path" 2>/dev/null) || { echo "run setup.sh first"; exit 1; }
. "$REPO/.venv/bin/activate"
FLIGHTS=$(cat "$KIT/.flights_path" 2>/dev/null || echo "$HOME/flights_gpu")
cd "$(dirname "$FLIGHTS")"
F=$(basename "$FLIGHTS")
mkdir -p $F/calib $F/logs
for name in wide_gentle wide_agile wide_long; do
  x=$(grep -v '^#' "$KIT/styles.txt" | awk -F'|' -v n="$name" '{gsub(/ /, "", $1)} $1 == n {print $2}')
  out=$F/calib/$name
  [ -n "$(ls $out/*.zip 2>/dev/null)" ] && continue
  VIOBENCH_TASK_EXTRA="$x" viobench simulate -o $out --episodes 2 --seed 300 --duration 30 --hover 1 --no-video \
    --scene-names ProcTHOR-Train-6 103997478_171030525 > $F/logs/calib-$name.log 2>&1
  if ls $out/*.zip >/dev/null 2>&1; then echo "probed $name: $(ls $out/*.zip | wc -l) flights"
  else echo "FAILED $name, no flights written. Log:"; grep -v '^conta:' $F/logs/calib-$name.log | tail -6; exit 1; fi
done
echo
echo "style        flight                          secs  avg m/s  top(p90) m/s  rms from start"
for d in $F/calib/*/; do
  python "$KIT/flight_stats.py" $d 2>/dev/null | grep '^STAT' | awk -v n=$(basename $d) -F'\t' \
    '{flag = ($3 < 29) ? "  <- ended early (crash?)" : ""; printf "%-12s %-30s %5.0f  %6.2f   %6.2f        %5.2f%s\n", n, $2, $3, $4, $7, $5, flag}'
done | tee $F/calib/table.txt
echo
echo "Hidden flights average ~1.0 m/s (0.66-1.34 per flight). Every flight above has its own top speed in 0.3-4 m/s."
echo "If any style crashed a lot or never got above ~1 m/s, send Claude $F/calib/table.txt; otherwise run make_flights.sh."
